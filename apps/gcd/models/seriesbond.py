# -*- coding: utf-8 -*-
from django.db import models
from functools import total_ordering

BOND_TRACKING = {1, 2, 3, 4, 5, 6}
SUBNUMBER_TRACKING = 4
MERGE_TRACKING = {5, 6}

class SeriesBondType(models.Model):
    class Meta:
        app_label = 'gcd'
        db_table = 'gcd_series_bond_type'

    # technical name, not to be changed
    name = models.CharField(max_length=255, db_index=True)
    # short description, e.g. shown in selection boxes
    description = models.TextField()
    notes = models.TextField(blank=True)

    def __unicode__(self):
        return self.description

class SeriesBond(models.Model):
    class Meta:
        app_label = 'gcd'
        db_table = 'gcd_series_bond'

    origin = models.ForeignKey('Series', related_name='to_series_bond')
    target = models.ForeignKey('Series', related_name='from_series_bond')
    origin_issue = models.ForeignKey('Issue', null=True,
                                     related_name='to_series_issue_bond')
    target_issue = models.ForeignKey('Issue', null=True,
                                     related_name='from_series_issue_bond')
    bond_type = models.ForeignKey(SeriesBondType)
    # we don't use modelforms to edit seriesbonds, no blank=True needed
    notes = models.TextField(max_length=255)

    # Fields related to change management.
    reserved = models.BooleanField(default=False, db_index=True)

    @property
    def modified(self):
        return self.revisions.filter(changeset__state=5).latest().modified
    
    # we check for deleted in the oi for models, so set to False
    deleted = False
    def deletable(self):
        return True

    def __unicode__(self):
        if self.origin_issue:
            object_string = '%s' % self.origin_issue
        else:
            object_string = '%s' % self.origin
        if self.target_issue:
            object_string += ' continues at %s' % self.target_issue
        else:
            object_string += ' continues at %s' % self.target
        return object_string

@total_ordering
class SeriesRelativeBond(object):
    """
    Proxy for SeriesBond from the perspective of one of the series involved.

    SeriesBonds are directional, connecting an origin to a target.  However,
    when processing bonds in terms of a particular series, this means that
    the series in question is on the origin end of some bonds and the target
    end of others.  Often this is what you want.

    However, if you need to uniformaly process all bonds related to a series
    (or all bonds of a particular type or set of types related to a series),
    there's a lot of confusing work to do to keep track of which side of
    each *individual* bond you are on.  The main example of this is
    sorting all bonds based on their position within the series.

    This class takes a series and a bond and provides accessors relative
    to that series.  It is an error to instantiate this with a bond that
    does not connect to the given series.

    Since the main reason for this class is to deal with bonds within
    a series, and the primary differentiator is the issue, this
    class also defaults bond targets to the first issue and bond origins        
    to the last issue.  This can be overridden.
    """

    def __init__(self, series, bond,
                 get_target_issue_default=lambda b: b.target.first_issue,
                 get_origin_issue_default=lambda b: b.origin.last_issue):
        self._series = series
        self.bond = bond

        # Currently, having a link from a series to itself will produce
        # all sorts of odd behavior, like showing up twice in displays,
        # so we're not going to try to address it here.  Such a link
        # will always show up as relative from the origin side.

        # near_series is always self._series, but present for symmetry.
        # The default and whether it was needed is exposed because
        # display logic may change based on whether the default was
        # needed and/or whether the specified issue is the same as the default.
        # A default may be valid for sorting but undesirable for display.

        if self._series == self.bond.origin:
            self.near_series = self.bond.origin
            self.near_issue_default = get_origin_issue_default(self.bond)
            self.near_issue = self.bond.origin_issue or self.near_issue_default
            self.has_explicit_near_issue = self.bond.origin_issue is not None

            self.far_series = self.bond.target
            self.far_issue_default = get_target_issue_default(self.bond)
            self.far_issue = self.bond.target_issue or self.far_issue_default
            self.has_explicit_far_issue = self.bond.target_issue is not None

            # Links out go after links in.
            self._directional_sort_code = 1

        elif self._series == self.bond.target:
            self.near_series = self.bond.target
            self.near_issue_default = get_target_issue_default(self.bond)
            self.near_issue = self.bond.target_issue or self.near_issue_default
            self.has_explicit_near_issue = self.bond.target_issue is not None

            self.far_series = self.bond.origin
            self.far_issue_default = get_origin_issue_default(self.bond)
            self.far_issue = self.bond.origin_issue or self.far_issue_default
            self.has_explicit_far_issue = self.bond.origin_issue is not None

            # Links in come before links out.
            self._directional_sort_code = 0

    def __eq__(self, other):
        if not isinstance(other, SeriesRelativeBond):
            return NotImplemented

        return bool(self.near_issue == other.near_issue and
                    self.far_issue == self.far_issue and
                    self.bond.bond_type == other.bond.bond_type and
                    self._directional_sort_code == other._directional_sort_code)

    def __lt__(self, other):
        # The order of things tried is:
        # 1.  order of nearby issues
        # 2.  direction of the bond
        # 3.  if both far series are the same, order of far issues
        # 4.  on_sale_date of the far issues
        # 5.  key_date of the far issues
        # 6.  mix and match on_sale/key_dates of the far issues
        # 7.  default to year_began of far_series if no issue dates available
        # 8.  far issue database id
        #
        # Since it is possible for both series to have begun in the same year,
        # the issue database id is an arbitrary but consistent way to ensure
        # a total ordering.  Otherwise you can end up with inconsistent
        # comparisions since the __eq__ check is not nearly as elaborate.
        # It seems better to have only one complicated check.

        if self.near_issue != other.near_issue:
            return self.near_issue.sort_code < other.near_issue.sort_code

        if self._directional_sort_code != other._directional_sort_code:
            return self._directional_sort_code < other._directional_sort_code

        if self.far_series == other.far_series:
            if self.far_issue.sort_code != other.far_issue.sort_code:
                return self.far_issue.sort_code < other.far_issue.sort_code

        if self.far_issue.on_sale_date and other.far_issue.on_sale_date:
            return self.far_issue.on_sale_date < other.far_issue.on_sale_date
        if self.far_issue.key_date and other.far_issue.key_date:
            return self.far_issue.key_date < other.far_issue.key_date

        self_mixed_date = (self.far_issue.on_sale_date or
                           self.far_issue.key_date)
        other_mixed_date = (other.far_issue.on_sale_date or
                            other.far_issue.key_date)
        if None not in (self_mixed_date, other_mixed_date):
            return self_mixed_date < other_mixed_date

        self_fallback_year = (self_mixed_date or
                              ('%d-00-00' % self.far_series.year_began))
        other_fallback_year = (other_mixed_date or
                               ('%d-00-00' % other.far_series.year_began))
        if self_fallback_year != other_fallback_year:
            return self_fallback_year < other_fallback_year

        # Arbitrary last resort- see comment at the top for explanation.
        return self.far_issue.id < other.far_issue.id
