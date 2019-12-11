# -*- coding: utf-8 -*-
import itertools
import operator
import re
import calendar
import os
import glob
from stdnum import isbn
from datetime import datetime, timedelta

from django import forms
from django.conf import settings
from django.db import models, transaction, IntegrityError
from django.db.models import F, Manager
from django.db.models.fields import Field, related, FieldDoesNotExist
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey, \
                                               GenericRelation
from django.utils.safestring import mark_safe
from django.utils.html import conditional_escape as esc
from django.core.validators import RegexValidator, URLValidator
from django.core.exceptions import ValidationError

from imagekit.cachefiles.backends import CacheFileState
from imagekit.models import ImageSpecField
from imagekit.processors import ResizeToFit
from taggit.managers import TaggableManager

from apps.oi import states, relpath

from apps.stddata.models import Country, Language, Date, Script
from apps.stats.models import RecentIndexedIssue, CountStats

from apps.gcd.models import (
    Publisher, IndiciaPublisher, BrandGroup, Brand, BrandUse, Series,
    SeriesBond, Cover, Image, Issue, Story, StoryCredit, Feature, BiblioEntry,
    Reprint, ReprintToIssue, ReprintFromIssue, IssueReprint,
    SeriesPublicationType, SeriesBondType, StoryType, CreditType, FeatureType,
    FeatureLogo, FeatureRelation, ImageType,
    Creator, CreatorArtInfluence, CreatorDegree, CreatorMembership,
    CreatorNameDetail, CreatorNonComicWork, CreatorSchool, CreatorRelation,
    NonComicWorkYear, Award, ReceivedAward, DataSource, STORY_TYPES,
    CREDIT_TYPES)

from apps.gcd.models.gcddata import GcdData

from apps.gcd.models.issue import issue_descriptor
from apps.gcd.models.story import show_feature

from apps.indexer.views import ErrorWithMessage

from functools import reduce

LANGUAGE_STATS = ['de']

MONTH_CHOICES = [(i, calendar.month_name[i]) for i in range(1, 13)]

# Changeset type "constants"
CTYPES = {
    'unknown': 0,
    'publisher': 1,
    'brand': 2,
    'indicia_publisher': 3,
    'series': 4,
    'issue_add': 5,
    'issue': 6,
    'cover': 7,
    'issue_bulk': 8,
    'variant_add': 9,
    'two_issues': 10,
    'reprint': 11,
    'image': 12,
    'brand_group': 13,
    'brand_use': 14,
    'series_bond': 15,
    'creator': 16,
    'creator_art_influence': 17,
    'received_award': 18,
    'creator_degree': 19,
    'creator_membership': 20,
    'creator_non_comic_work': 21,
    'creator_relation': 22,
    'creator_school': 23,
    'award': 24,
    'feature': 25,
    'feature_logo': 26,
    'feature_relation': 27,
}

CTYPES_INLINE = frozenset((CTYPES['publisher'],
                           CTYPES['brand'],
                           CTYPES['brand_group'],
                           CTYPES['brand_use'],
                           CTYPES['indicia_publisher'],
                           CTYPES['series'],
                           CTYPES['feature'],
                           CTYPES['feature_logo'],
                           CTYPES['feature_relation'],
                           CTYPES['cover'],
                           CTYPES['reprint'],
                           CTYPES['image'],
                           CTYPES['series_bond'],
                           CTYPES['award'],
                           CTYPES['creator'],
                           CTYPES['creator_art_influence'],
                           CTYPES['received_award'],
                           CTYPES['creator_degree'],
                           CTYPES['creator_membership'],
                           CTYPES['creator_non_comic_work'],
                           CTYPES['creator_relation'],
                           CTYPES['creator_school'],
                           ))

# Change types that *might* be bulk changes.  But might just have one revision.
CTYPES_BULK = frozenset((CTYPES['issue_bulk'],
                         CTYPES['issue_add']))

ACTION_ADD = 'add'
ACTION_DELETE = 'delete'
ACTION_MODIFY = 'modify'

IMP_BONUS_ADD = 10
IMP_COVER_VALUE = 5
IMP_IMAGE_VALUE = 5
IMP_APPROVER_VALUE = 3
IMP_DELETE = 1

# Reprint link type "constants"
REPRINT_TYPES = {
    'story_to_story': 0,
    'story_to_issue': 1,
    'issue_to_story': 2,
    'issue_to_issue': 3,
    'reprint': 0,
    'reprint_to_issue': 1,
    'reprint_from_issue': 2,
    'issue_reprint': 3
}

REPRINT_CLASSES = {
    0: Reprint,
    1: ReprintToIssue,
    2: ReprintFromIssue,
    3: IssueReprint
}

REPRINT_FIELD = {
    0: 'reprint',
    1: 'reprint_to_issue',
    2: 'reprint_from_issue',
    3: 'issue_reprint'
}


def update_count(field, delta, language=None, country=None):
    '''
    updates statistics, for all, per language, and per country
    CountStats with language=None is for all languages
    '''
    stat = CountStats.objects.get(name=field, language=None, country=None)
    stat.count = F('count') + delta
    stat.save()

    if language:
        stat = CountStats.objects.filter(name=field, language=language)
        if stat.count():
            stat = stat[0]
            stat.count = F('count') + delta
            stat.save()
        else:
            CountStats.objects.init_stats(language=language)

    if country:
        stat = CountStats.objects.filter(name=field, country=country)
        if stat.count():
            stat = stat[0]
            stat.count = F('count') + delta
            stat.save()
        else:
            CountStats.objects.init_stats(country=country)


def set_series_first_last(series):
    '''
    set first_issue and last_issue for given series
    '''
    issues = series.active_issues().order_by('sort_code')
    if issues.count() == 0:
        series.first_issue = None
        series.last_issue = None
    else:
        series.first_issue = issues[0]
        series.last_issue = issues[len(issues) - 1]
    series.save()


def validated_isbn(entered_isbn):
    '''
    returns ISBN10 or ISBN13 if valid ISBN, empty string otherwiese
    '''
    isbns = entered_isbn.split(';')
    valid_isbns = True
    for num in isbns:
        valid_isbns &= isbn.is_valid(num)
    if valid_isbns and len(isbns) == 1:
        return isbn.compact(isbns[0])
    elif valid_isbns and len(isbns) == 2:
        compacted_isbns = [isbn.compact(isbn.to_isbn13(i)) for i in isbns]
        # if two ISBNs it must be corresponding ISBN10 and ISBN13
        if compacted_isbns[0] == compacted_isbns[1]:
            # always store ISBN13 if both exist
            return compacted_isbns[0]
    return ''


def remove_leading_article(name):
    '''
    returns the name with the leading article (separated by "'"
    or whitespace) removed
    '''
    article_match = re.match(r"\S?\w+['\s]\s*(.*)$", name, re.UNICODE)
    if article_match:
        return article_match.group(1)
    else:
        return name


def on_sale_date_as_string(issue):
    date = ''
    if issue.year_on_sale:
        date += '{0:?<4d}'.format(issue.year_on_sale)
    elif issue.day_on_sale or issue.month_on_sale:
        date += '????'
    if issue.month_on_sale:
        date += '-{0:02d}'.format(issue.month_on_sale)
    elif issue.day_on_sale:
        date += '-??'
    if issue.day_on_sale:
        date += '-{0:02d}'.format(issue.day_on_sale)
    return date


def on_sale_date_fields(on_sale_date):
    year_string = on_sale_date[:4].strip('?')
    if year_string:
        year = int(year_string)
    else:
        year = None
    month = None
    day = None
    if len(on_sale_date) > 4:
        month_string = on_sale_date[5:7].strip('?')
        if month_string:
            month = int(month_string)
        if len(on_sale_date) > 7:
            day = int(on_sale_date[8:10].strip('?'))
    return year, month, day


def get_keywords(source):
    return '; '.join(str(i) for i in source.keywords.all()
                                                .order_by('name'))


def save_keywords(revision, source):
    if revision.keywords:
        source.keywords.set(*[x.strip() for x in revision.keywords.split(';')])
        revision.keywords = '; '.join(
            str(i) for i in source.keywords.all().order_by('name'))
        revision.save()
    else:
        source.keywords.set()


def _check_year(year):
    year = year.strip().strip('?')
    year_number = int(year)
    if len(year) != 4 or year_number < 0:
        raise forms.ValidationError('Enter valid years.')
    return year_number


def _imps_for_years(revision, field_name, year_began, year_ended):
    if field_name in (year_began, year_began + '_uncertain'):
        if not revision._seen_year_began and revision.__dict__['year_began']:
            revision._seen_year_began = True
            return True, 1
        return True, 0
    elif field_name in (year_ended, year_ended + '_uncertain'):
        if not revision._seen_year_ended and revision.__dict__['year_ended']:
            revision._seen_year_ended = True
            return True, 1
        return True, 0
    return False, None


class Changeset(models.Model):

    state = models.IntegerField(db_index=True)

    indexer = models.ForeignKey('auth.User', db_index=True,
                                related_name='changesets')
    along_with = models.ManyToManyField(User,
                                        related_name='changesets_assisting')
    on_behalf_of = models.ManyToManyField(User,
                                          related_name='changesets_source')

    # Changesets don't get an approver until late in the workflow,
    # and for legacy cases we don't know who they were.
    approver = models.ForeignKey('auth.User', db_index=True,
                                 related_name='approved_%(class)s', null=True)

    # In production, change_type is a tinyint(2) due to the small value set.
    change_type = models.IntegerField(db_index=True)
    migrated = models.BooleanField(default=False, db_index=True)
    date_inferred = models.BooleanField(default=False)

    imps = models.IntegerField(default=0)

    created = models.DateTimeField(auto_now_add=True, db_index=True)
    modified = models.DateTimeField(auto_now=True, db_index=True)

    def __init__(self, *args, **kwargs):
        models.Model.__init__(self, *args, **kwargs)
        self._inline_revision = None

    def _revision_sets(self):
        if self.change_type in [CTYPES['issue'], CTYPES['variant_add'],
                                CTYPES['two_issues']]:
            return (self.issuerevisions.all(),
                    self.storyrevisions.all(),
                    self.storycreditrevisions.all(),
                    self.coverrevisions.all(),
                    self.reprintrevisions.all())

        if self.change_type in [CTYPES['issue_add'], CTYPES['issue_bulk']]:
            return (self.issuerevisions.all().select_related('issue',
                                                             'series'),)

        if self.change_type == CTYPES['cover']:
            return (self.issuerevisions.all().select_related('issue',
                                                             'series'),
                    self.coverrevisions.all(),
                    self.storyrevisions.all())

        if self.change_type == CTYPES['feature']:
            return (self.featurerevisions.all(),)

        if self.change_type == CTYPES['feature_logo']:
            return (self.featurelogorevisions.all(),)

        if self.change_type == CTYPES['feature_relation']:
            return (self.featurerelationrevisions.all(),)

        if self.change_type == CTYPES['series']:
            return (self.seriesrevisions.all(),
                    self.issuerevisions.all().select_related('issue'),
                    self.storyrevisions.all(),
                    self.storycreditrevisions.all())

        if self.change_type == CTYPES['series_bond']:
            return (self.seriesbondrevisions.all()
                        .select_related('series_bond'),)

        if self.change_type == CTYPES['publisher']:
            return (self.publisherrevisions.all(), self.brandrevisions.all(),
                    self.indiciapublisherrevisions.all())

        if self.change_type == CTYPES['brand']:
            return (self.brandrevisions.all(), self.branduserevisions.all())

        if self.change_type == CTYPES['brand_group']:
            return (self.brandgrouprevisions.all(), self.brandrevisions.all(),
                    self.branduserevisions.all())

        if self.change_type == CTYPES['brand_use']:
            return (self.branduserevisions.all(),)

        if self.change_type == CTYPES['indicia_publisher']:
            return (self.indiciapublisherrevisions.all(),)

        if self.change_type == CTYPES['reprint']:
            return (self.reprintrevisions.all(),)

        if self.change_type == CTYPES['image']:
            return (self.imagerevisions.all(),)

        if self.change_type == CTYPES['award']:
            return (self.awardrevisions.all(),)

        if self.change_type == CTYPES['creator']:
            return (self.creatorrevisions.all(),
                    self.datasourcerevisions.all(),
                    self.creatornamedetailrevisions.all(),
                    self.creatorartinfluencerevisions.all(),
                    self.receivedawardrevisions.all(),
                    self.creatordegreerevisions.all(),
                    self.creatormembershiprevisions.all(),
                    self.creatornoncomicworkrevisions.all(),
                    self.creatorrelationrevisions.all(),
                    self.creatorschoolrevisions.all()
                    )

        if self.change_type == CTYPES['creator_art_influence']:
            return (self.creatorartinfluencerevisions.all(),
                    self.datasourcerevisions.all())

        if self.change_type == CTYPES['received_award']:
            return (self.receivedawardrevisions.all(),
                    self.datasourcerevisions.all())

        if self.change_type == CTYPES['creator_degree']:
            return (self.creatordegreerevisions.all(),
                    self.datasourcerevisions.all())

        if self.change_type == CTYPES['creator_membership']:
            return (self.creatormembershiprevisions.all(),
                    self.datasourcerevisions.all())

        if self.change_type == CTYPES['creator_non_comic_work']:
            return (self.creatornoncomicworkrevisions.all(),
                    self.datasourcerevisions.all())

        if self.change_type == CTYPES['creator_relation']:
            return (self.creatorrelationrevisions.all(),
                    self.datasourcerevisions.all())

        if self.change_type == CTYPES['creator_school']:
            return (self.creatorschoolrevisions.all(),
                    self.datasourcerevisions.all())

    @property
    def revisions(self):
        """
        Fake up an iterable (not actually a list) of all revisions,
        in canonical order.
        This also iterates over freshly created revisions in one of the
        existing ones, if done in the correct order.
        """
        return itertools.chain(*self._revision_sets())

    @property
    def cached_revisions(self):
        """
        Fake up an iterable (not actually a list) of all revisions,
        in canonical order.
        Revisions are cached, this is for the queue view speed-up.
        """
        if not hasattr(self, '_save_revisions'):
            self._save_revisions = self._revision_sets()
        return itertools.chain(*self._save_revisions)

    def revision_count(self):
        return reduce(operator.add,
                      [rs.count() for rs in self._revision_sets()])

    def inline(self):
        """
        If true, edit the revisions of the changeset inline in the changeset
        page.  Otherwise, render a page for the changeset that links to a
        separate edit page for each revision.
        """
        return self.change_type in CTYPES_INLINE

    def inline_revision(self, cache_safe=False):
        if self.inline():
            if self._inline_revision is None:
                if self.change_type == CTYPES['publisher']:
                    # to filter out all the imprints in a publisher deletion
                    # changeset, probably still need this for correct handling
                    # of old revisions in change history, approved, editor_log
                    if self.publisherrevisions.count() > 1:
                        self._inline_revision = \
                            self.publisherrevisions.filter(is_master=True)[0]
                    else:
                        self._inline_revision = \
                            self.publisherrevisions.get()
                if self.change_type == CTYPES['cover']:
                    self._inline_revision = self.coverrevisions.get()
                else:
                    if cache_safe is True:
                        return next(self.cached_revisions)
                    else:
                        self._inline_revision = next(self.revisions)
        return self._inline_revision

    def deleted(self):
        if self.inline():
            # everything but issues
            return self.inline_revision().deleted
        elif self.change_type == CTYPES['issue']:
            # single issue deletions
            return self.issuerevisions.get().deleted
        else:
            # bulk issue deletions not supported
            return False

    def editable(self):
        """
        Used for conditionals in templates, as bulk issue adds and edits as
        well as deletes cannot be edited after submission.
        """
        return (
            # TODO check creators re inline
            self.inline() or
            self.change_type in [CTYPES['issue'],
                                 CTYPES['variant_add'],
                                 CTYPES['two_issues'],
                                 CTYPES['series_bond'],
                                 CTYPES['creator'],
                                 CTYPES['creator_membership'],
                                 CTYPES['received_award'],
                                 CTYPES['creator_art_influence'],
                                 CTYPES['creator_non_comic_work']] or
            (
                self.change_type == CTYPES['issue_add'] and
                self.issuerevisions.count() == 1
            )
        ) and not self.deleted()

    def ordered_issue_revisions(self):
        """
        Used in the display.  Natural revision order must be by timestamp.
        """
        return self.issuerevisions.order_by('revision_sort_code', 'id')

    def queue_name(self):
        if self.change_type in CTYPES_BULK:
            ir_count = self.issuerevisions.count()
            if self.change_type == CTYPES['issue_bulk']:
                return str('%s and %d other issues' %
                               (self.issuerevisions.all()[0], ir_count - 1))
            if self.change_type == CTYPES['issue_add']:
                if ir_count == 1:
                    return str(self.issuerevisions.all()[0])
                elif ir_count > 1:
                    first = self.issuerevisions \
                                .order_by('revision_sort_code')[0]
                    last = self.issuerevisions \
                               .order_by('-revision_sort_code')[0]
                    return '%s %s - %s' % (first.series,
                                            first.display_number,
                                            last.display_number)
            return 'Unknown State'
        elif self.change_type == CTYPES['issue']:
            return self.cached_revisions.next().queue_name()
        elif self.change_type == CTYPES['two_issues']:
            issuerevisions = self.issuerevisions.all()
            name = issuerevisions[0].queue_name() + " and "
            if issuerevisions[0].variant_of == issuerevisions[1].issue:
                name += "base issue"
            else:
                name += issuerevisions[1].queue_name()
            return name
        elif self.change_type == CTYPES['variant_add']:
            return self.issuerevisions \
                       .get(variant_of__isnull=False).queue_name()
        elif self.change_type == CTYPES['image']:
            return self.imagerevisions.get().queue_name()
        elif self.change_type == CTYPES['series_bond']:
            return self.seriesbondrevisions.get().queue_name()
        elif self.change_type == CTYPES['creator']:
            return self.creatorrevisions.get().queue_name()
        else:
            return self.inline_revision(cache_safe=True).queue_name()

    def queue_descriptor(self):
        if self.change_type == CTYPES['issue_add']:
            return '[ADDED]'
        elif self.change_type == CTYPES['variant_add']:
            return '[VARIANT + BASE]'
        return self.cached_revisions.next().queue_descriptor()

    def changeset_action(self):
        """
        Produce a human-readable description of whether we're adding, removing
        or modifying data with this changeset.
        """
        if self.change_type in [CTYPES['issue_add'], CTYPES['variant_add']]:
            return ACTION_ADD
        elif self.change_type == CTYPES['issue_bulk']:
            return ACTION_MODIFY

        revision = next(self.cached_revisions)
        if revision.deleted:
            return ACTION_DELETE
        if not revision.previous_revision:
            return ACTION_ADD
        return ACTION_MODIFY

    def display_state(self):
        """
        Return the display text for the state.
        Makes it much easier to display state information in templates.
        """
        return states.DISPLAY_NAME[self.state]

    def _check_approver(self):
        """
        Check for a mentor, set to approver if necessary, and return the
        appropriate state for a submitted change.

        Set last issue even if we are part of a current series, because
        the is_current flag denotes that already and we may want to use the
        last issue to date sometimes.
        """
        if self.approver is None and (
                self.indexer.indexer.is_new and
                self.indexer.indexer.mentor is not None and
                self.change_type != CTYPES['cover']):
            self.approver = self.indexer.indexer.mentor

        new_state = states.PENDING
        if self.approver is not None:
            new_state = states.REVIEWING
        return new_state

    def submit(self, notes='', delete=False):
        """
        Submit changes for approval.
        If this is the first such submission or if the prior approver released
        the changes back to the general queue, then the changes go into the
        general approval queue.  If it is an edit in reply to a disapproval,
        then the changes go directly back into the approver's queue.
        """

        if (self.state != states.OPEN) and \
           not (delete and self.state == states.UNRESERVED):
            raise ErrorWithMessage(
                  "Only OPEN changes can be submitted for approval.")

        new_state = self._check_approver()

        self.comments.create(commenter=self.indexer,
                             text=notes,
                             old_state=self.state,
                             new_state=new_state)
        self.state = new_state

        # Since a submission is what puts the changeset in a non-editable
        # state, calculate the imps now.
        self.calculate_imps()
        self.save()

    def retract(self, notes=''):
        """
        Retract a submitted change.

        This can only be done if the change is not being examined.  Users
        should contact the examiner if they would like to further edit
        a change that is under examination.
        """

        if self.state != states.PENDING:
            raise ErrorWithMessage("Only PENDING changes my be retracted.")
        if self.approver is not None:
            raise ErrorWithMessage(
                  "Only changes with no approver may be retracted.")

        self.comments.create(commenter=self.indexer,
                             text=notes,
                             old_state=self.state,
                             new_state=states.OPEN)
        self.state = states.OPEN
        self.save()

    def discard(self, discarder, notes=''):
        """
        Discard a change without comitting it back to the data tables.

        This may be done either by the indexer, effectively releasign the
        reservation, or by an approver, effectively canceling it.
        """
        if self.state not in states.ACTIVE:
            raise ErrorWithMessage("Only OPEN, PENDING, DISCUSSED, or "
                                   "REVIEWING changes may be discarded.")

        self.comments.create(commenter=discarder,
                             text=notes,
                             old_state=self.state,
                             new_state=states.DISCARDED)

        self.state = states.DISCARDED
        self.save()
        for revision in self.revisions:
            if revision.source is not None:
                _free_revision_lock(revision.source)
                revision.previous_revision = None
            revision.committed = False
            revision.save()

        if self.approver:
            self.approver.indexer.add_imps(IMP_APPROVER_VALUE)

    def assign(self, approver, notes=''):
        """
        Set an approver who will examine the changes in this pending revision.

        This causes the revision to move out of the general queue and into
        the examiner's approval queue.
        """
        if self.state != states.PENDING:
            if self.state != states.REVIEWING or not self.review_is_overdue:
                raise ErrorWithMessage("Only PENDING changes can be reviewed.")

        # TODO: check that the approver has approval priviliges.
        if not isinstance(approver, User):
            raise TypeError("Please supply a valid approver.")

        self.comments.create(commenter=approver,
                             text=notes,
                             old_state=self.state,
                             new_state=states.REVIEWING)
        self.approver = approver
        self.state = states.REVIEWING
        self.save()

    def release(self, notes=''):
        if self.state not in states.ACTIVE or \
           self.approver is None:
            raise ErrorWithMessage(
                  "Only changes with an approver may be unassigned.")

        if self.state in [states.DISCUSSED, states.REVIEWING]:
            new_state = states.PENDING
        else:
            new_state = self.state

        self.comments.create(commenter=self.approver,
                             text=notes,
                             old_state=self.state,
                             new_state=new_state)
        self.approver = None
        self.state = new_state
        self.save()

    def discuss(self, commenter, notes=''):
        if self.state not in [states.OPEN, states.REVIEWING] or \
           self.approver is None:
            raise ErrorWithMessage(
                  "Only changes with an approver may be discussed.")

        self.comments.create(commenter=commenter,
                             text=notes,
                             old_state=self.state,
                             new_state=states.DISCUSSED)
        self.state = states.DISCUSSED
        self.save()

    def approve(self, notes=''):
        """
        Approve a pending index from an approver's queue into production.

        This moves the revision to approved and copies its data back to the
        production display table.
        """

        # TODO Save handling of double approvals.
        # Although we have the following check here and in the view-code, we
        # got rare double approvals, which for adds resulted in two created
        # objects. With the below if on revision.source we do have another
        # check, which will avoid double saves of objects due to the call of
        # _free_revision_lock. It is to be seen if this is now safe for adds,
        # they will get a source on the first save, but maybe the second one
        # is fast enough ? We might be able to use RevisionLock on a revision
        # for add ?
        if self.state not in [states.DISCUSSED, states.REVIEWING] or \
           self.approver is None:
            raise ErrorWithMessage(
                  "Only REVIEWING changes with an approver can be approved.")

        for revision in self.revisions:
            # TODO rethink the depency handling during committing
            #
            # We might have saved other revision due to dependences.
            # Other types, later in the itertools.chain, are fresh,
            # but revision of the same type can became stale
            # in self.revisions, so refresh_from_db. Could do a
            # check for type, i.e. same as before, to reduce db calls.
            revision.refresh_from_db()

            # For adds we might generate additional revisions, and call
            # commit_to_display when generating these approvals. Check
            # committed status to avoid double adds.
            # TODO check regarding stats
            # TODO revision generated later in the chain will be
            #      picked by up self.revisions anyway, so maybe not needed
            #      for purpose of avoiding double adds.
            #      But check shouldn't hurt anyway ?
            if revision.committed is not True:
                # adds have a (created) source only after commit_to_display
                if revision.source:
                    _free_revision_lock(revision.source)
                # first free the lock, commit_to_display might delete source
                revision.commit_to_display()

        self.comments.create(commenter=self.approver,
                             text=notes,
                             old_state=self.state,
                             new_state=states.APPROVED)

        self.state = states.APPROVED
        self.save()
        self.indexer.indexer.add_imps(self.total_imps())
        self.approver.indexer.add_imps(IMP_APPROVER_VALUE)

        # TODO remove once all type of revisions are re-factored
        for revision in self.revisions:
            revision.committed = True
            revision.save()

    def disapprove(self, notes=''):
        """
        Send the change back to the indexer for more work.
        """
        # TODO: Should we validate that a non-empty reason is supplied
        # through the approver_notes field here or in the view layer?
        # Where should validation go in general?

        if self.state not in [states.DISCUSSED, states.REVIEWING] or \
           self.approver is None:
            raise ErrorWithMessage(
              "Only REVIEWING changes with an approver can be disapproved.")
        self.comments.create(commenter=self.approver,
                             text=notes,
                             old_state=self.state,
                             new_state=states.OPEN)
        self.state = states.OPEN
        self.save()

    def review_is_overdue(self):
        if datetime.today() - timedelta(weeks=1) > self.modified:
            return True
        else:
            return False

    def calculate_imps(self):
        """
        Go through and add up the imps from the revisions, but don't commit
        to the database.
        """
        self.imps = 0
        if self.change_type in CTYPES_BULK:
            # Currently, bulk changes are only allowed when the changes
            # are uniform across all revisions in the change.  When we
            # allow non-uniform changes we may need to calculate all of
            # the imp revisions and take the maximum value or something.
            self.imps += self.revisions.next().calculate_imps()
        else:
            if self.change_type == CTYPES['cover']:
                # coverrevisions can have issuerevisions and storyrevisions
                # for variant uploads, but one shouldn't get imps for them
                revisions = self.coverrevisions.all()
            else:
                revisions = self.revisions

            for revision in revisions:
                # Deletions are a bit strange.  Essentially, you get one
                # point per button you press, however many objects that
                # button deletes.  Similar to bulk adds counting the same
                # as a single add.  Story objects are deleted one at a time,
                # and multiple of them can be deleted in a single changeset
                # without deleting the entire issue.  Issue and other objects,
                # however, are only deleted when the entire action of the
                # changeset is a deletion.  So they get one IMP_DELETE no
                # matter what else was in the changeset.

                if revision.deleted:
                    if isinstance(revision, StoryRevision) or \
                       isinstance(revision, ReprintRevision) or \
                       isinstance(revision, CreatorNameDetailRevision):
                        self.imps += IMP_DELETE
                    else:
                        self.imps = IMP_DELETE
                        return
                else:
                    self.imps += revision.calculate_imps()

    def magnitude(self):
        """
        A rough guide to the size of the change.  Currently implemented by
        examining the calculated imps, but may be switched to a changed field
        count of some sort if we change how imps work or decide that a
        different metric will work better as a size estimate.  For instance
        number of characters (as in letters, not the characters field) changed.
        """
        return self.imps

    def total_imps(self):
        """
        The total number of imps awarded for this changeset, including both
        field-calculated imps and bonuses such as the add bonus.
        """
        calculated = self.imps
        if self.change_type != CTYPES['cover'] and \
           self.change_type != CTYPES['image'] and \
           self.changeset_action() == ACTION_ADD:
            return calculated + IMP_BONUS_ADD
        return calculated

    def __str__(self):
        if self.inline():
            return str(self.inline_revision())
        if self.change_type in CTYPES_BULK:
            return self.queue_name()
        if self.change_type == CTYPES['issue']:
            return str(self.issuerevisions.all()[0])
        if self.change_type == CTYPES['two_issues']:
            return self.queue_name()
        if self.change_type == CTYPES['variant_add']:
            return self.queue_name() + ' [Variant]'
        if self.id:
            return 'Changeset: %d' % self.id
        return "Changeset"


class ChangesetComment(models.Model):
    """
    Comment class for revision management.

    We are not using Django's comments contrib package for several reasons:

    1.  Additional fields- we want to associate comments with state
        transitions, which also tells us who made the comment (since
        currently comments can only be made by the person changing the
        revision state, or by the indexer when saving intermediate edits.

        TODO: The whole bit where the indexer can end up tacking on a bunch
        of comments rather than having just one that they build up and edit
        and send in with the submission is not quite right.  Needs work still.

    2.  We don't need the anti-spam measures as these will not be accessible
        by the general public.  If we get a spammer with an account we'll have
        bigger problems than comments, and other ways to deal with them.

    3.  Unneeded fields.  This isn't really an obstacle to use, but the
        django comments system copies over a number of fields that we would
        not want copied in case they change (email, for instance).
    """
    class Meta:
        db_table = 'oi_changeset_comment'
        ordering = ['created']

    commenter = models.ForeignKey(User)
    text = models.TextField()

    changeset = models.ForeignKey(Changeset, related_name='comments')

    content_type = models.ForeignKey(ContentType, null=True)
    revision_id = models.IntegerField(db_index=True, null=True)
    revision = GenericForeignKey('content_type', 'revision_id')

    old_state = models.IntegerField()
    new_state = models.IntegerField()
    created = models.DateTimeField(auto_now_add=True, editable=False)

    def display_old_state(self):
        return states.DISPLAY_NAME[self.old_state]

    def display_new_state(self):
        return states.DISPLAY_NAME[self.new_state]


def _get_revision_lock(object, changeset=None):
    try:
        with transaction.atomic():
            revision_lock = RevisionLock.objects.create(locked_object=object,
                                                        changeset=changeset)
    except IntegrityError:
        revision_lock = None
    return revision_lock


# This should not have @transaction.atomic, since the lock should stay till
# the end of the request ?
def _free_revision_lock(object):
    revision_lock = RevisionLock.objects.get(
      object_id=object.id,
      content_type=ContentType.objects.get_for_model(object))
    revision_lock.delete()


class RevisionLock(models.Model):
    """
    Indicates that a particular Changeset has a particular row locked.

    In order to have an active Revision for a given row, a Changeset
    must hold a lock on it.  Rows in this table represent locks,
    and the unique_together constraint on the content type and object id
    ensure that only one Changeset can hold an object's lock at a time.
    Locks are released by deleting the row.

    A lock with a NULL changeset is used to check that the object can
    be locked before creating a Changeset that would not be used
    if the lock fails.

    TODO: cron job to periodically scan for stale locks?
    """
    class Meta:
        db_table = 'oi_revision_lock'
        unique_together = ('content_type', 'object_id')

    changeset = models.ForeignKey(Changeset, null=True,
                                  related_name='revision_locks')

    content_type = models.ForeignKey(ContentType)
    object_id = models.IntegerField(db_index=True)
    locked_object = GenericForeignKey('content_type', 'object_id')


class RevisionManager(models.Manager):
    """
    Custom manager base class for revisions.
    """
    # We want to use these methods on reverse relation sets.
    use_for_related_fields = True

    def get_queryset(self):
        return RevisionQuerySet(self.model, using=self._db)

    def active(self):
        """
        Get the active revision, assuming that there is one.

        Throws the DoesNotExist or MultipleObjectsReturned exceptions on
        the appropriate Revision subclass, as it calls get() underneath.
        """
        return self.active_set().get()

    def active_set(self):
        """
        Get the active revision as a query set, which might be empty.

        Currently we do not expect multiple active revisions.
        """
        return self.filter(changeset__state__in=states.ACTIVE)

    def pending_deletions(self):
        """
        Filter to active revisions that are deleting their object.
        """
        return self.active_set().filter(deleted=True)

    def filter_pending_deletions(self, data_queryset):
        """
        Filter pending deletions out of a queryset of GcdBase-derived objects.

        Since this does not operate on Revision querysets, it should not be
        copied to the RevisionQuerySet class.
        """
        return data_queryset.exclude(
            revisions__deleted=True,
            revisions__changeset__state__in=states.ACTIVE).distinct()

    # H. TODO deprecated
    def clone_revision(self, instance, instance_class,
                       changeset, check=True, **kwargs):
        """
        Given an existing instance, create a new revision based on it.

        This new revision will be where the edits are made.
        If there are no revisions, first save a baseline so that the pre-edit
        values are preserved.
        Entirely new publishers should be started by simply instantiating
        a new PublisherRevision directly.
        """
        if not isinstance(instance, instance_class):
            raise TypeError("Please supply a valid %s." % instance_class)

        revision = self._do_create_revision(instance,
                                            changeset=changeset,
                                            **kwargs)

        # Link to the previous revision for the data object.
        # It is an error not to have a previous revision for
        # a pre-existing data object.
        previous_revision = type(revision).objects.get(
                            next_revision=None,
                            changeset__state=states.APPROVED,
                            committed=True,
                            **{revision.source_name: instance})
        revision.previous_revision = previous_revision
        revision.save()

        return revision


class RevisionQuerySet(models.QuerySet):
    """
    Propagates the RevisionManager methods to further querysets.
    """
    def active(self):
        return self.get(changeset__state__in=states.ACTIVE)

    def active_set(self):
        return self.filter(changeset__state__in=states.ACTIVE)

    def pending_deletions(self):
        return self.active_set().filter(deleted=True)


class Revision(models.Model):
    """
    Abstract base class implementing the workflow of a revisable object.

    This holds the data while it is being edited, and remains in the table
    as a history of each given edit, including those that are discarded.

    A state column trackes the progress of the revision, which should
    eventually end in either the APPROVED or DISCARDED state.

    Various classmethods exist to get information about the revision fields
    so that they can be handled generically.  All of these method names
    start with _get and end with a suffix indicating the return value:

    fields:       a dictionary mapping field attribute names to field objects
    field_names:  a set of field attribute names
    field_tuples: a set of tuples of attribute names that may cross relations
    """
    class Meta:
        abstract = True

    objects = RevisionManager()

    changeset = models.ForeignKey(Changeset, related_name='%(class)ss')
    previous_revision = models.OneToOneField('self', null=True,
                                             related_name='next_revision')

    # If True, this revision deletes the object in question.  Other fields
    # should not contain changes but should instead be a record of the object
    # at the time of deletion and therefore match the previous revision.
    # If changes are present, then they were never actually published and
    # should be ignored in terms of history.
    deleted = models.BooleanField(default=False, db_index=True)

    # If True, this revision has been committed back to the display tables.
    # If False, this revision will never be committed.
    # If None, this revision is still active, and may or may not be committed
    # at some point in the future.
    committed = models.NullBooleanField(default=None, db_index=True)

    comments = GenericRelation(ChangesetComment,
                               content_type_field='content_type',
                               object_id_field='revision_id')

    created = models.DateTimeField(auto_now_add=True, db_index=True)
    modified = models.DateTimeField(auto_now=True, db_index=True)

    is_changed = False

    # These are initialized on first use- see the corresponding classmethods.
    # Set to None as an empty iterable is a valid possible value.
    _regular_fields = None
    _irregular_fields = None
    _single_value_fields = None
    _multi_value_fields = None
    _meta_fields = None

    # Child classes must set these properly.  Unlike source, they cannot be
    # instance properties because they are needed during revision construction.
    # H.TODO source_name = NotImplemented
    source_class = NotImplemented
    # H.TODO no separate _get_source

    @property
    def source(self):
        """
        The thing of which this is a revision.
        Since this is different for each revision,
        the subclass must override this.
        """
        # Call separate method for polymorphism
        return self._get_source()

    def _get_source(self):
        raise NotImplementedError

    @property
    def source_name(self):
        """
        Used to key lookups in various shared view methods.
        """
        # Call separate method for polymorphism
        return self._get_source_name()

    def _get_source_name(self):
        raise NotImplementedError

    @source.setter
    def source(self, value):
        """
        Used with source_class by base revision code to create new objects.
        """
        raise NotImplementedError

    # #####################################################################
    # Properties indicating the type of action this Revision is performing.
    @property
    def added(self):
        """
        True if this is an open or committed add.
        """
        return not self.previous_revision and not self.discarded

    @property
    def edited(self):
        """
        True if this open or committed and neither an add nor a delete.
        NOTE: This does not necessarily mean there have been any edits.
        """
        return bool(self.previous_revision and not
                    (self.deleted or self.discarded))

    @property
    def discarded(self):
        """
        For symmetry with committed and open.
        """
        return self.committed is False

    @property
    def open(self):
        """
        For symmetry with committed and discarded.
        """
        return self.committed is None

    # #####################################################################
    # Field declarations and classification.

    @classmethod
    def _classify_fields(cls):
        """
        Populates the regular and irregular field dictionaries.

        This should be called at most once during the life of the class.
        It relies on the excluded field set to filter out irrelevant fields.
        """
        if cls._regular_fields is not None:
            # Already classified.
            return

        # NOTE: As of Django 1.9, reverse relations show up in the list
        #       of fields, but are not actually Field instances.  Since
        #       we don't want them anyway, use this to filter them out.
        #
        #       In a future release of Django this will change, but should
        #       be covered in the release notes.  And presumably there
        #       will be a different reliable way to filter them out.
        excluded_names = cls._get_excluded_field_names()
        meta_names = cls._get_meta_field_names()
        # TODO: use OrderedDict after update to python 3, that should allow
        # an automatic way to generate an ordered field_list per model
        data_fields = {
            f.get_attname(): f
            for f in cls.source_class._meta.get_fields()
            if isinstance(f, Field) and f.get_attname() not in excluded_names
        }
        rev_fields = {
            f.get_attname(): f
            for f in cls._meta.get_fields()
            if isinstance(f, Field) and f.get_attname() not in excluded_names
        }
        cls._regular_fields = {}
        cls._irregular_fields = {}
        cls._single_value_fields = {}
        cls._multi_value_fields = {}
        cls._meta_fields = {}

        for name, data_field in data_fields.items():
            # Currently we do not have relations that are meta fields,
            # so just handle those here and move on to the next field.
            if name in meta_names:
                cls._meta_fields[name] = data_field
                continue

            # Note that ForeignKeys and OneToOneFields show up under the
            # attribute name for the actual key ('parent_id' instead of
            # 'parent'), so strip the _id off for more convenient use.
            # You can still pass the 'parent' form to _meta.get_field().
            # TODO: Is there a more reliable way to do this?  Cannot
            #       seem to find anything in the Django 1.9 API.
            key_name = name
            if ((data_field.many_to_one or data_field.one_to_one) and
                    name.endswith('_id')):
                # If these aren't the same we have no idea what's going
                # on, so an AssertionError is appropriate.
                assert cls.source_class._meta.get_field(key_name) == data_field
                key_name = name[:-len('_id')]

            if name not in rev_fields:
                # No corresponding revision field, so it can't be regular.
                cls._irregular_fields[key_name] = data_field
                continue

            # The internal type is the field type i.e. CharField or ForeignKey.
            rev_field = rev_fields[name]
            rev_ftype = rev_field.get_internal_type()
            data_ftype = data_field.get_internal_type()
            rev_target = (rev_field.target_field.get_attname()
                          if isinstance(rev_field, related.RelatedField)
                          else None)
            data_target = (data_field.target_field.get_attname()
                           if isinstance(data_field, related.RelatedField)
                           else None)

            if rev_ftype == data_ftype and rev_target == data_target:
                # Non-relational fields have a .rel of None.  While we should
                # never have identically named foreign keys that point to
                # different things, it's better to check than assume.
                #
                # Most of these fields can be copied, including ManyToMany
                # fields, although ManyToMany fields may need to be treated
                # differently in other ways, so we track them separately
                # as well.
                cls._regular_fields[key_name] = data_field

                if data_field.many_to_many or data_field.one_to_many:
                    cls._multi_value_fields[key_name] = data_field
                else:
                    cls._single_value_fields[key_name] = data_field

            elif isinstance(data_field,
                            TaggableManager) and name == 'keywords':
                # Keywords are regular but not assignable in the same way
                # as single- or multi-value fields as the keywords are
                # stored as a single string in revisions.
                cls._regular_fields[key_name] = data_field

            else:
                # There's some mismatch, so we don't know how to handle this.
                cls._irregular_fields[key_name] = data_field

    @classmethod
    def _get_excluded_field_names(cls):
        """
        Field names that appear to be regular fields but should be ignored.

        Any data object field that has a matching (name, type, and if
        relevant related type) field on the revision that should *NOT*
        be copied back and forth should be included here.

        It is not necessary to include non-matching fields here, whether
        they affect revision field values or not.

        Fields listed here may or may not be present on any given data object,
        but if they are present they should be omitted from automatic
        classification.

        Subclasses may add to this set, but should never remove fields from it.

        Deprecated fields should NOT be included, as they should continue
        to be copied back and forth until the data is all removed, at
        which point the field should be dropped from the data object.
        """
        # Not all data objects have all of these, but since this
        # is just used in set subtractions, that is safe to do.
        # All of these fields are common to multiple revision types.
        #
        # id, created, and modified are automatic columns
        # tagged_items is the reverse relation for 'keywords'
        # image_resources are handled through their own ImageRevisions
        return frozenset({
            'id',
            'created',
            'modified',
            'deleted',
            'tagged_items',
            'image_resources',
        })

    @classmethod
    def _get_deprecated_field_names(cls):
        """
        The set of field names that should not be allowed in new objects.

        These fields are still present in both the data object and revision
        tables, and should therefore be copied out of the data objects in
        case old values are still present and need to be preserved until
        they can be migrated.  But new values should not be allowed.
        """
        return frozenset()

    @classmethod
    def _get_meta_field_names(cls):
        """
        Fields that are about other fields, and only copied from rev to data.

        These fields are not included in either the regular or irregular
        field sets, nor the single value or multi value sets.  They are
        handled completely separately.

        See also _get_meta_fields() for more information.
        """
        return frozenset()

    @classmethod
    def _get_regular_fields(cls):
        """
        Data fields that can be predictably transferred to and from revisions.

        For most fields, this just means copying the value.  For a few
        such as keywords, there is a different but standard way of transferring
        the values.  For ManyToManyFields, the add/remove/set/clear methods
        can be used.
        """
        cls._classify_fields()
        return cls._regular_fields

    @classmethod
    def _get_irregular_fields(cls):
        """
        Data object fields that cannot be handled by generic revision code.

        These fields either don't exist on the revision, or they do not
        match types and we do not understand the mismatch as a well-known
        special case (i.e. keywords as CharField vs TaggableManager).
        """
        cls._classify_fields()
        return cls._irregular_fields

    @classmethod
    def _get_single_value_fields(cls):
        """
        The subset of regular fields that have a single value.
        """
        cls._classify_fields()
        return cls._single_value_fields

    @classmethod
    def _get_multi_value_fields(cls):
        """
        The subset of regular fields that have a queryset value.
        """
        cls._classify_fields()
        return cls._multi_value_fields

    @classmethod
    def _get_meta_fields(cls):
        """
        Fields that are not managed as primary data.

        These fields are usually meta-data of some sort, such as flags
        indicating data that needs revisiting.  Alternatively, they
        may be additional information calculated from primary data
        but cached in database fields.

        These field values may be changed in the data object without
        using a Revision, and Revisions should not attempt to keep
        them in sync.

        When committing a revision, the field must be activley set
        correctly as it is not copied *from* the data object, but
        will be copied back *to* it.

        Note that fields that are calculated either entirely within
        the revision, or entirely within the data object, but are
        never copied in either direction should *not* be included
        here.  This classification is essentially for fields that
        are only copied from revision to data object.
        """
        cls._classify_fields()
        return cls._meta_fields

    @classmethod
    def _get_conditional_field_tuple_mapping(cls):
        """
        A dictionary of field names mapped to their conditions.

        The conditions are stored as a tuple of field names that can
        be applied to an instance to get the value.
        For example, ('series', 'has_isbn') would mean that you
        could get the value by looking at revision.series.has_isbn
        """
        return {}

    @classmethod
    def _get_parent_field_tuples(cls):
        """
        The set of parent-ish objects that this revision may need to update.

        This should include parent chains up to the root data object(s) that
        need updating, for instance an issue should include its publisher
        by way of the series foreign key (as opposed to publishers found
        through other links, which are either duplicate or should be
        ignored.

        Elements of the set are tuples to allow for multiple parent levels.
        ForeignKey, ManyToManyField, and OneToOneField are all valid
        field types for this method.

        Note that if multiple parents along a path require updating, then
        each level of parent must be included.  In the issue example,
        ('series',) and ('series', 'publisher') must both be included.

        This allows for the case where an intermediate object does not
        require updating.
        """
        return frozenset()

    @classmethod
    def _get_major_flag_field_tuples(cls):
        """
        The set of flags that require further processing upon commit.

        These are stored as tuples in the same way as
        _get_parent_field_tuples().
        """
        return frozenset()

    @classmethod
    def _get_stats_category_field_tuples(cls):
        """
        These fields, when present, determine CountStats categories to update.

        This implementation works for any class that does not have to get
        these fields from a parent object.
        """
        stats_tuples = set()
        for name in ('country', 'language'):
            try:
                # We just call get_field to see if it raises, so we
                # ignore the return value.
                cls._meta.get_field(name)
                stats_tuples.add((name,))
            except FieldDoesNotExist:
                pass

        return stats_tuples

    # #####################################################################
    # Methods for creating (cloning) a Revision from a data object,
    # including hook methods for use in customizing the cloning process.

    def _pre_initial_save(self, fork=False, fork_source=None,
                          exclude=frozenset(), **kwargs):
        """
        Called just before saving to the database to handle unusual fields.

        Note that if there is a source data object, it will already be set.

        See clone() for usage of fork, fork_source, and exclude.
        """
        pass

    def _post_m2m_add(self, fork=False, fork_source=None, exclude=frozenset()):
        """
        Called after initial save to database and m2m population.

        This is for handling unusual fields that require the revision to
        already exist in the database.

        See clone() for usage of fork, fork_source, and exclude.
        """
        pass

    @classmethod
    def clone(cls, data_object, changeset, fork=False, exclude=frozenset(),
              **kwargs):
        """
        Given an existing data object, create a new revision based on it.

        This new revision will be where the edits are made.

        'fork' may be set to true to create a revision for a new data
        object based on an existing data object.  The source and
        previous_revision fields will be left null in this case.  Due to
        this, the source will be passed separately to the customization
        methods as 'fork_source'.

        Entirely new data objects should be started by simply instantiating
        a new revision of the approparite type directly.

        A set (or set-like object) of field names to exclude from copying
        may be passed.  This is particularly useful for forking.
        """
        # We start with all assignable fields, since we want to copy
        # old values even for deprecated fields.
        rev_kwargs = {field: getattr(data_object, field)
                      for field
                      in cls._get_single_value_fields().keys() - exclude}

        # Keywords are not assignable but behave the same way whenever
        # they are present, so handle them here.
        if 'keywords' in cls._get_regular_fields().keys() - exclude:
            rev_kwargs['keywords'] = get_keywords(data_object)

        # Instantiate the revision.  Since we do not know the exact
        # field name for the data_object, set it through the source property.
        revision = cls(changeset=changeset, **rev_kwargs)

        if data_object and not fork:
            revision.source = data_object

            # Link to the previous revision for this data object.
            # It is an error not to have a previous revision for
            # a pre-existing data object.
            previous_revision = type(revision).objects.get(
                next_revision=None,
                changeset__state=states.APPROVED,
                **{revision.source_name: data_object})
            revision.previous_revision = previous_revision

        revision._pre_initial_save(fork=fork, fork_source=data_object,
                                   exclude=exclude, **kwargs)

        revision.save()

        # Populate all of the many to many relations that don't use
        # their own separate revision classes.
        for m2m in revision._get_multi_value_fields().keys() - exclude:
            getattr(revision, m2m).add(*list(getattr(data_object, m2m).all()))
        revision._post_m2m_add(fork=fork, fork_source=data_object,
                               exclude=exclude)

        return revision

    # ##################################################################
    # Methods for inventorying significant changes to the fields,
    # an handling those changes and the resulting updates to cached
    # values and statistics.

    def _reset_values(self):
        pass

    def _check_major_change(self, attrs):
        """
        Fill out the changes structure for a single attribute tuple.
        """
        old, new = self.source, self
        changes = {}

        # The name of the last foreign key is the name used for
        # tracking changes.  Except 'parent' is tracked as 'publisher'
        # for historical reasons.  Eventually we will likely switch
        # the 'parent' database fields to 'publisher'.
        name = 'publisher' if attrs[-1] == 'parent' else attrs[-1]

        old_rp = relpath.RelPath(self.source_class, *attrs)
        new_rp = relpath.RelPath(type(self), *attrs)

        old_value = old_rp.get_value(old, empty=self.added)
        new_value = new_rp.get_value(new, empty=self.deleted)

        changed = '%s changed' % name
        if self.added or self.deleted:
            changes[changed] = True
        elif old_rp.multi_valued:
            # Different QuerySet objects are never equal, even if they
            # express the same queries and have the same evaluation state.
            # So use sets for determining changes.
            changes[changed] = set(old_value) != set(new_value)
        else:
            changes[changed] = old_value != new_value

        if old_rp.boolean_valued:
            # We only care about the direction of change for booleans.
            # At this time, it is sufficient to treat None for a NullBoolean
            # as False.  This can produce a "changed" (False to or from None)
            # in which both "to" and "from" are False.  Strange but OK.
            #
            # Without the bool(), if old_value (for from) or new_value
            # (for to) are None, then the changes would be set to None
            # instead of True or False.
            changes['to %s' % name] = bool((not old_value) and new_value)
            changes['from %s' % name] = bool(old_value and (not new_value))
        else:
            changes['old %s' % name] = old_value
            changes['new %s' % name] = new_value

        return changes

    def _get_major_changes(self, extra_field_tuples=frozenset()):
        """
        Returns a dictionary for deciding what additional actions are needed.

        Major changes are generally ones that require updating statistics
        and/or cached counts in the display tables.  They may also require
        other actions.

        This method bundles up all of the flags and old vs new values
        needed for easy conditionals and easy calls to update_all_counts().

        extra_field_tuples is a way for child classes to put additional fields
        into the changes dictionary through a super() call without having
        to put them in any of the sets that trigger special handling.
        This is useful for oddball fields that trigger custom code when
        changed, but don't fall into any of the usual patterns.
        """
        changes = {}
        for name_tuple in (self._get_parent_field_tuples() |
                           self._get_major_flag_field_tuples() |
                           self._get_stats_category_field_tuples() |
                           extra_field_tuples):
            changes.update(self._check_major_change(name_tuple))
        return changes

    def _adjust_stats(self, changes, old_counts, new_counts):
        """
        Handles universal statistics updating.

        Child classes should call this with super() before proceeding
        to adjust counts stored in their display objects.
        """
        if self.source_class._update_stats and (old_counts != new_counts or
                                                changes.get('country changed',
                                                            False) or
                                                changes.get('language changed',
                                                            False)):
            CountStats.objects.update_all_counts(
                old_counts,
                country=changes.get('old country', None),
                language=changes.get('old language', None),
                negate=True)
            CountStats.objects.update_all_counts(
                new_counts,
                country=changes.get('new country', None),
                language=changes.get('new language', None))

        deltas = {
            k: new_counts.get(k, 0) - old_counts.get(k, 0)
            for k in old_counts.keys() | new_counts.keys()
        }
        if any(deltas.values()) or True in list(changes.values()):
            for parent_tuple in self._get_parent_field_tuples():
                self._adjust_parent_counts(parent_tuple, changes, deltas,
                                           old_counts, new_counts)

            self.source.update_cached_counts(deltas)
            self.source.save()

    def _adjust_parent_counts(self, parent_tuple, changes, deltas,
                              old_counts, new_counts):
        """
        Handles the counts adjustment for a single parent.
        """
        # Always use the last attribute name for the parent name.
        # But switch 'parent' to 'publisher' (historical reasons).
        parent = (
            'publisher' if parent_tuple[-1] == 'parent' else parent_tuple[-1])

        changed = changes['%s changed' % parent]
        old_value = changes['old %s' % parent]
        new_value = changes['new %s' % parent]

        multi = relpath.RelPath(type(self), *parent_tuple).multi_valued
        if changed:
            if old_value:
                if multi:
                    for v in old_value:
                        v.update_cached_counts(old_counts, negate=True)
                        v.save()
                else:
                    old_value.update_cached_counts(old_counts, negate=True)
                    old_value.save()
            if new_value:
                if multi:
                    for v in new_value:
                        v.update_cached_counts(new_counts)
                        v.save()
                else:
                    new_value.update_cached_counts(new_counts)
                    new_value.save()

        elif old_counts != new_counts:
            # Doesn't matter whether we use old or new as they are the same.
            if multi:
                for v in new_value:
                    v.update_cached_counts(deltas)
                    v.save()
            else:
                new_value.update_cached_counts(deltas)
                new_value.save()

    # #####################################################################
    # Methods for saving the Revision back to the data object, including
    # hook methods for customizing that process.

    def _pre_commit_check(self):
        """
        Runs sanity checks before anything else in commit_to_display.

        This method must not attempt to change anything, and should raise
        an exception if the check fails.  For conditions that can be
        fixed, use _handle_prerequisites.
        """
        pass

    def _handle_prerequisites(self, changes):
        """
        Creates/commits related revisions before committing this revision.

        This is where a revision subclass should look for other revisions
        that must be committed before the commit of this revision can
        proceed.  It should create and/or commit those prerequisite
        revisions as needed, updating this revision with the results
        if appropriate.

        This method should take into account the possibility that multiple
        revisions in a given changeset may have the same prerequisites, and
        either only perform actions that can be safely repeated or verify
        that prior revisions have not already handled things.

        This runs before the old stat counts are collected so that any
        changes from the prerequisites are accounted for in the stats,
        any any count updates are not double-counted.

        Note that prerequisite revisions may attempt to handle this
        revision as a dependent revision, so care must be taken to
        avoid loops.
        """
        pass

    def _pre_delete(self, changes):
        """
        Runs just before the data object is deleted in a deletion revision.
        """
        pass

    def _post_create_for_add(self, changes):
        """
        Runs after a new object is created during an add.

        This is where things like adding many-to-many objects can be done.
        """
        pass

    def _post_assign_fields(self, changes):
        """
        Runs once the added or edited display object is set up.

        Fields that can't be copied directly are handled here.
        Not run for deletions.
        """
        pass

    def _pre_save_object(self, changes):
        """
        Runs just before the display object is saved.

        This is where additional processing related to the major changes,
        such as conditional field adjustments, can be done.
        """
        pass

    def _post_save_object(self, changes):
        """
        Runs just after the display object is saved.

        Typically used to handle many-to-many fields.
        """
        pass

    def _handle_dependents(self, changes):
        """
        Creates/commits related revisions after committing this revision.

        This is where a revision subclass should ensure that any revisions
        that depend on this revision get handled created and/or committed
        appropriately.

        This runs at the very end of commit_to_display(), after the new
        stats have been collected and handled.  Otherwise any counts
        adjusted in the revisions handled here would be double-counted
        by this revision's stats code as well.

        Note that dependent revisions may attempt to handle this revision
        as a prerequisite, so care must be taken to avoid loops.
        To help with this, self.committed will be set to True and this
        revision will be saved to the database by the time this method
        is called.
        """
        pass

    def _copy_fields_to(self, target):
        """
        Used to copy fields from a revision to a display object.

        At the time when this is called, the revision may not yet have
        the display object set as self.source (in the case of a newly
        added object), so the target of the copy is given as a parameter.
        """
        fields_to_copy = self._get_single_value_fields().copy()
        fields_to_copy.update(self._get_meta_fields())
        c = self._get_conditional_field_tuple_mapping()
        for name in fields_to_copy:
            # If conditional, apply getattr until we produce the flag
            # value and only assign the field if that flag is True.
            if (name not in c or reduce(getattr, c[name], self)):
                setattr(target, name, getattr(self, name))

    def extra_forms(self, request):
        """
        Fetch additional forms of other/related objects for editing.
        """
        return {}

    def process_extra_forms(self, request, extra_forms):
        """
        Process additional forms of other/related objects on save.
        """
        pass

    def commit_to_display(self, clear_reservation=True):
        """
        Writes the changes from the revision back to the display object.

        Revisions should handle their own dependencies on other revisions.
        """
        self._pre_commit_check()
        changes = self._get_major_changes()

        self._handle_prerequisites(changes)
        old_stats = {} if self.added else self.source.stat_counts()

        if self.deleted:
            self._pre_delete(changes)
            self._reset_values()
        else:
            if self.added:
                self.source = self.source_class()
                self._post_create_for_add(changes)

            self._copy_fields_to(self.source)
            self._post_assign_fields(changes)

        self._pre_save_object(changes)
        self.source.save()

        if self.added:
            # Reset the source because now it has a database id,
            # which we must save.  Just saving the added source while
            # it is attached does not update the revision with the newly
            # created source id from the database.
            #
            # We do this because it is easier for all other code if it
            # only works with self.source, no matter whether it is
            # an add, edit, or delete.
            # TODO refresh_from_db instead ?
            self.source = self.source

        self.committed = True
        self.save()

        # Keywords must be handled post-save for added objects, and
        # are safe to handle here for other types of revisions.
        if 'keywords' in self._get_regular_fields():
            save_keywords(self, self.source)

        for multi in self._get_multi_value_fields():
            old_rp = relpath.RelPath(type(self), multi)
            new_rp = relpath.RelPath(type(self.source), multi)

            new_rp.set_value(self.source, old_rp.get_value(self))

        self._post_save_object(changes)
        if self.deleted:
            self.source.delete()
        new_stats = self.source.stat_counts()
        self._adjust_stats(changes, old_stats, new_stats)
        self._handle_dependents(changes)

    # #####################################################################
    # Methods not involved in the Revision lifecycle.

    def __str__(self):
        """
        String representation for debugging purposes only.

        No UI should rely on this representation being suitable for end users.
        """
        # It's possible to add and delete something at the same time,
        # although we don't currently allow it.  In theory one could
        # edit and delete, although we don't even have any way to indicate
        # that currently.
        action = []
        if self.added:
            action.append('adding')
        if self.edited:
            action.append('editing')
        if self.deleted:
            action.append('deleting')

        return '%r %s %s %r (%r) change %r' % (
            self.id,
            ' & '.join(action),
            self.source_class.__name__,
            self.source,
            None if self.source is None else self.source.id,
            None if self.changeset_id is None else self.changeset_id,
        )

    # #####################################################################
    # Old methods. t.b.c, if deprecated.

    def _changed(self):
        """
        The dictionary of change information between this revision and the
        previous revision of the same source object.
        """
        pass

    def field_list(self):
        """
        Public field list interface, in case we ever decide we want
        to process child class field lists before returning them.
        """
        return self._field_list()

    def _field_list(self):
        """
        Default implementation for objects that have no fields (like covers).
        """
        return []

    def _get_blank_values(self):
        """
        Create a dictionary with the "blank" values for all of the fields
        of this type of revision.  This is used to determine the change
        value of newly added objects.  Blank values are often not allowed
        in the database (i.e. NOT NULL columns) so this cannot be done
        with a revision instance.  Blank values should be set.
        """
        raise NotImplementedError

    def previous(self):
        # We never spontaneously gain a previous revision during normal
        # operation, so it's safe to cache this.
        if hasattr(self, '_prev_rev'):
            return self._prev_rev

        self._prev_rev = self.previous_revision

        # prev_rev is self.previous_revision, unless it is a variant issue add
        if self.added and type(self) == IssueRevision and self.variant_of:
            # for variant adds compare against base issue
            self._prev_rev = self.variant_of.revisions \
                                 .filter(committed=True,
                                         created__lt=self.created) \
                                 .latest('created')
        # edits which are not comitted do not have a stored previous revision
        elif self.committed is False and self.source:
            self._prev_rev = self.source.revisions \
                                 .filter(committed=True,
                                         created__lt=self.created) \
                                 .latest('created')
        return self._prev_rev

    def posterior(self):
        # This would be in the db cache anyway, but this way we
        # save db-calls in some cases.
        # During normal operation we cannot gain a new revision, so it's safe
        if hasattr(self, '_post_rev'):
            return self._post_rev

        self._post_rev = None
        if hasattr(self, 'next_revision'):
            self._post_rev = self.next_revision
        return self._post_rev

    def compare_changes(self):
        """
        Set up the 'changed' property so that it can be accessed conveniently
        from a template.  Template calling limitations prevent just
        using a parameter to compare one field at a time.
        """
        self.changed = {}
        self.is_changed = False

        if self.deleted:
            # deletion counts as changed to ease conditional for
            # collapsing sequences in bits/compare.html
            self.is_changed = True
            return

        prev_rev = self.previous()

        if prev_rev is None:
            self.is_changed = True
            prev_values = self._get_blank_values()
            get_prev_value = lambda field: prev_values[field]  # noqa: E731
        else:
            get_prev_value = lambda field: getattr(prev_rev,  # noqa: E731
                                                   field)

        for field_name in self.field_list():
            old = get_prev_value(field_name)
            new = getattr(self, field_name)
            if type(new) == str:
                field_changed = old.strip() != new.strip()
            elif isinstance(old, Manager):
                old = old.all().values_list('id', flat=True)
                new = new.all().values_list('id', flat=True)
                field_changed = set(old) != set(new)
            elif isinstance(new, Date):
                old = str(old)
                new = str(new)
                field_changed = old != new
            elif isinstance(new, Manager):
                new = new.all().values_list('id', flat=True)
                if new:
                    field_changed = True
                else:
                    field_changed = False
            else:
                field_changed = old != new
            self.changed[field_name] = field_changed
            self.is_changed |= field_changed
        if not self.is_changed and type(self) in [IssueRevision,
                                                  StoryRevision]:
            self.is_changed = self.has_reprint_revisions()

    def _start_imp_sum(self):
        """
        Hook for subclasses to initialize state for an IMP calculation.
        For instance, if a subclass is keeping track of whether either of a
        pair of fields that together represent an IMP have been seen, this
        hook can be used to clear that state before a new calculation begins.
        """
        pass

    def _imps_for(self, field_name):
        """
        Each revision subclass should override this and have it return the
        number of IMPs that a field should add to the total.  Note that this
        may be stateful as a change in one field may have already been
        accounted for due to a change in a related field.  Child classes may
        maintain state for this sort of tracking, and the _start_imp_sum hook
        should be overridden to clear any such state.
        """
        raise NotImplementedError

    def calculate_imps(self):
        """
        Calculate and return the number of Index Measurment Points that this
        revision is worth.  Relies on self.changed being set.
        """
        imps = 0
        self.compare_changes()
        if self.deleted or not self.is_changed:
            return imps

        other_imp = self._start_imp_sum()
        if other_imp:
            imps += other_imp
        for field_name in self.field_list():
            if field_name in self.changed and self.changed[field_name]:
                imps += self._imps_for(field_name)
        return imps

    def queue_name(self):
        """
        Long name form to display in queues.
        This allows revision objects to use their linked object's __str__
        method for compatibility in preview pages, but display a more
        verbose form in places like queues that need them.

        Derived classes should override _queue_name to supply a base string
        other than the standard unicode representation.
        """
        return self._queue_name()

    def _queue_name(self):
        return str(self)

    def queue_descriptor(self):
        """
        Display descriptor for queue name
        """
        if self.source is None:
            return '[ADDED]'
        if self.deleted:
            return '[DELETED]'
        return ''

    def save_added_revision(self, changeset, **kwargs):
        """
        Add the remaining arguments and many to many relations for an unsaved
        added revision produced by a model form.  The general workflow
        should be:

        revision = form.save(commit=False)
        revision.save_added_revision() # optionally with kwargs

        Since this prevents the form from adding any many to many
        relationships, the _do_save_added_revision method on each concrete
        revision class needs be certain to save any such relations that come
        from the form.
        """
        self.changeset = changeset
        self._do_complete_added_revision(**kwargs)
        self.save()

    def _do_complete_added_revision(self, **kwargs):
        """
        Hook for individual revisions to process additional parameters
        necessary to create a new revision representing an added record.
        By default no additional processing is done, so subclasses are
        free to override this method without calling it on the parent class.
        """
        pass

    def _create_dependent_revisions(self, delete=False, **kwargs):
        """
        Some Revisions have dependent objects, this locks the objects and
        creates the corresponding revisions.
        """
        pass

    def has_keywords(self):
        return self.keywords != ''


class OngoingReservation(models.Model):
    """
    Represents the ongoing revision on all new issues in a series.

    Whenever an issue is added to a series, if there is an ongoing reservation
    for that series the issue is immediately reserved to the ongoing
    reservation holder.
    """
    class Meta:
        db_table = 'oi_ongoing_reservation'

    indexer = models.ForeignKey(User, related_name='ongoing_reservations')
    series = models.OneToOneField(Series, related_name='ongoing_reservation')
    along_with = models.ManyToManyField(User, related_name='ongoing_assisting')
    on_behalf_of = models.ManyToManyField(User, related_name='ongoing_source')

    """
    The creation timestamp for this reservation.
    """
    created = models.DateTimeField(auto_now_add=True, db_index=True)

    def __str__(self):
        return '%s reserved by %s' % (self.series, self.indexer.indexer)


class PublisherRevisionBase(Revision):
    class Meta:
        abstract = True

    name = models.CharField(max_length=255)

    year_began = models.IntegerField(null=True, blank=True)
    year_ended = models.IntegerField(null=True, blank=True)
    year_began_uncertain = models.BooleanField(default=False)
    year_ended_uncertain = models.BooleanField(default=False)

    notes = models.TextField(blank=True)
    keywords = models.TextField(blank=True, default='')
    url = models.URLField(blank=True)

    def __str__(self):
        if self.source is None:
            return self.name
        return str(self.source)

    ######################################
    # TODO old methods, t.b.c

    # order exactly as desired in compare page
    # use list instead of set to control order
    _base_field_list = ['name',
                        'year_began',
                        'year_began_uncertain',
                        'year_ended',
                        'year_ended_uncertain',
                        'url',
                        'notes',
                        'keywords']

    def _field_list(self):
        return self._base_field_list

    def _start_imp_sum(self):
        self._seen_year_began = False
        self._seen_year_ended = False

    def _imps_for(self, field_name):
        years_found, value = _imps_for_years(self, field_name,
                                             'year_began', 'year_ended')
        if years_found:
            return value
        elif field_name in self._base_field_list:
            return 1
        return 0


class PublisherRevisionManager(RevisionManager):

    def clone_revision(self, publisher, changeset):
        return PublisherRevision.clone(publisher, changeset)


class PublisherRevision(PublisherRevisionBase):
    class Meta:
        db_table = 'oi_publisher_revision'
        ordering = ['-created', '-id']

    objects = PublisherRevisionManager()

    publisher = models.ForeignKey('gcd.Publisher', null=True,
                                  related_name='revisions')

    country = models.ForeignKey('stddata.Country', db_index=True)

    # Deprecated fields about relating publishers/imprints to each other
    # TODO can these be removed, or does it make problems for the
    # change history of publishers ? Should not need to worry
    # about change history of old imprints
    is_master = models.BooleanField(default=True, db_index=True)
    parent = models.ForeignKey('gcd.Publisher', default=None,
                               null=True, blank=True, db_index=True,
                               related_name='imprint_revisions')

    date_inferred = models.BooleanField(default=False)

    source_name = 'publisher'
    source_class = Publisher

    @property
    def source(self):
        return self.publisher

    @source.setter
    def source(self, value):
        self.publisher = value

    _update_stats = True

    def _create_dependent_revisions(self, delete=False):
        if delete:
            for indicia_publisher in self.publisher\
                                         .active_indicia_publishers():
                # indicia_publisher is deletable if publisher is deletable
                indicia_publishers_lock = _get_revision_lock(
                                          indicia_publisher,
                                          changeset=self.changeset)
                if indicia_publishers_lock is None:
                    raise IntegrityError("needed IndiciaPublisher lock not"
                                         " possible")
                indicia_publisher_revision = IndiciaPublisherRevision.clone(
                                                indicia_publisher,
                                                self.changeset)
                indicia_publisher_revision.deleted = True
                indicia_publisher_revision.save()
            for brand_use in self.publisher.branduse_set.all():
                brand_use_lock = _get_revision_lock(brand_use,
                                                    changeset=self.changeset)
                if brand_use_lock is None:
                    raise IntegrityError("needed BrandUse lock not possible")
                brand_use_revision = BrandUseRevision.clone(brand_use,
                                                            self.changeset)
                brand_use_revision.deleted = True
                brand_use_revision.save()

    def get_absolute_url(self):
        if self.publisher is None:
            return "/publisher/revision/%i/preview" % self.id
        return self.publisher.get_absolute_url()

    ######################################
    # TODO old methods, t.b.c

    def _queue_name(self):
        return '%s (%s, %s)' % (self.name, self.year_began,
                                 self.country.code.upper())

    def _field_list(self):
        fields = []
        fields.extend(PublisherRevisionBase._field_list(self))
        fields.insert(fields.index('url'), 'country')
        fields.extend(('is_master', 'parent'))
        return fields

    def _get_blank_values(self):
        return {
            'name': '',
            'country': None,
            'year_began': None,
            'year_ended': None,
            'year_began_uncertain': None,
            'year_ended_uncertain': None,
            'url': '',
            'notes': '',
            'keywords': '',
            'is_master': True,
            'parent': None,
        }

    def _imps_for(self, field_name):
        # We don't actually ever change parent and is_master since imprint
        # objects are hidden from direct access by the indexer.
        if field_name == 'country':
            return 1
        return PublisherRevisionBase._imps_for(self, field_name)


class IndiciaPublisherRevisionManager(RevisionManager):

    def clone_revision(self, indicia_publisher, changeset):
        return IndiciaPublisherRevision.clone(indicia_publisher, changeset)


class IndiciaPublisherRevision(PublisherRevisionBase):
    class Meta:
        db_table = 'oi_indicia_publisher_revision'
        ordering = ['-created', '-id']

    objects = IndiciaPublisherRevisionManager()

    indicia_publisher = models.ForeignKey('gcd.IndiciaPublisher', null=True,
                                          related_name='revisions')

    is_surrogate = models.BooleanField(default=False)

    country = models.ForeignKey('stddata.Country', db_index=True,
                                related_name='indicia_publishers_revisions')

    parent = models.ForeignKey('gcd.Publisher',
                               null=True, blank=True, db_index=True,
                               related_name='indicia_publisher_revisions')

    source_name = 'indicia_publisher'
    source_class = IndiciaPublisher

    @property
    def source(self):
        return self.indicia_publisher

    @source.setter
    def source(self, value):
        self.indicia_publisher = value

    @classmethod
    def _get_parent_field_tuples(cls):
        return frozenset({('parent',)})

    def _do_complete_added_revision(self, parent):
        self.parent = parent

    def get_absolute_url(self):
        if self.indicia_publisher is None:
            return "/indicia_publisher/revision/%i/preview" % self.id
        return self.indicia_publisher.get_absolute_url()

    ######################################
    # TODO old methods, t.b.c

    def _field_list(self):
        fields = []
        fields.extend(PublisherRevisionBase._field_list(self))
        fields.insert(fields.index('url'), 'is_surrogate')
        fields.insert(fields.index('url'), 'country')
        fields.append(('parent'))
        return fields

    def _get_blank_values(self):
        return {
            'name': '',
            'country': None,
            'year_began': None,
            'year_ended': None,
            'year_began_uncertain': None,
            'year_ended_uncertain': None,
            'is_surrogate': None,
            'url': '',
            'notes': '',
            'keywords': '',
            'parent': None,
        }

    def _imps_for(self, field_name):
        if field_name in ['is_surrogate', 'parent', 'country']:
            return 1
        return PublisherRevisionBase._imps_for(self, field_name)

    def _queue_name(self):
        return '%s: %s (%s, %s)' % (self.parent.name,
                                     self.name,
                                     self.year_began,
                                     self.country.code.upper())


class BrandGroupRevisionManager(RevisionManager):

    def clone_revision(self, brand_group, changeset):
        return BrandGroupRevision.clone(brand_group, changeset)


class BrandGroupRevision(PublisherRevisionBase):
    class Meta:
        db_table = 'oi_brand_group_revision'
        ordering = ['-created', '-id']

    objects = BrandGroupRevisionManager()

    brand_group = models.ForeignKey('gcd.BrandGroup', null=True,
                                    related_name='revisions')

    parent = models.ForeignKey('gcd.Publisher',
                               null=True, blank=True, db_index=True,
                               related_name='brand_group_revisions')

    source_name = 'brand_group'
    source_class = BrandGroup

    @property
    def source(self):
        return self.brand_group

    @source.setter
    def source(self, value):
        self.brand_group = value

    @classmethod
    def _get_parent_field_tuples(cls):
        return frozenset({('parent',)})

    def _handle_dependents(self, changes):
        if self.added:
            brand_revision = BrandRevision(
                changeset=self.changeset,
                name=self.name,
                year_began=self.year_began,
                year_ended=self.year_ended,
                year_began_uncertain=self.year_began_uncertain,
                year_ended_uncertain=self.year_ended_uncertain)
            brand_revision.save()
            brand_revision.group.add(self.brand_group)
            brand_revision.commit_to_display()

    def _do_complete_added_revision(self, parent):
        self.parent = parent

    def get_absolute_url(self):
        if self.brand_group is None:
            return "/brand_group/revision/%i/preview" % self.id
        return self.brand_group.get_absolute_url()

    ######################################
    # TODO old methods, t.b.c

    def _field_list(self):
        fields = []
        fields.extend(PublisherRevisionBase._field_list(self))
        fields.append('parent')
        return fields

    def _get_blank_values(self):
        return {
            'name': '',
            'year_began': None,
            'year_ended': None,
            'year_began_uncertain': None,
            'year_ended_uncertain': None,
            'url': '',
            'notes': '',
            'keywords': '',
            'parent': None,
        }

    def _imps_for(self, field_name):
        if field_name == 'parent':
            return 1
        return PublisherRevisionBase._imps_for(self, field_name)

    def _queue_name(self):
        return '%s: %s (%s)' % (self.parent.name, self.name, self.year_began)


class BrandRevisionManager(RevisionManager):
    def clone_revision(self, brand, changeset):
        return BrandRevision.clone(brand, changeset)


class BrandRevision(PublisherRevisionBase):
    class Meta:
        db_table = 'oi_brand_revision'
        ordering = ['-created', '-id']

    objects = BrandRevisionManager()

    brand = models.ForeignKey('gcd.Brand', null=True, related_name='revisions')
    # parent needs to be kept for old revisions
    parent = models.ForeignKey('gcd.Publisher',
                               null=True, blank=True, db_index=True,
                               related_name='brand_revisions')
    group = models.ManyToManyField('gcd.BrandGroup', blank=False,
                                   related_name='brand_revisions')

    source_name = 'brand'
    source_class = Brand

    @property
    def source(self):
        return self.brand

    @source.setter
    def source(self, value):
        self.brand = value

    @classmethod
    def _get_parent_field_tuples(cls):
        return frozenset({('group',)})

    def _create_dependent_revisions(self, delete=False):
        if delete:
            for brand_use in self.brand.in_use.all():
                # TODO check if transaction rollback works
                brand_use_lock = _get_revision_lock(
                                brand_use,
                                changeset=self.changeset)
                if brand_use_lock is None:
                    return False

                use_revision = BrandUseRevision.clone(brand_use,
                                                      self.changeset)
                use_revision.deleted = True
                use_revision.save()

    def _handle_dependents(self, changes):
        if self.added:
            parent_ids = set(self.brand.group.values_list('parent_id',
                                                          flat=True))
            for parent_id in parent_ids:
                use = BrandUseRevision(
                    changeset=self.changeset,
                    emblem=self.brand,
                    publisher_id=parent_id,
                    year_began=self.year_began,
                    year_began_uncertain=self.year_began_uncertain,
                    year_ended=self.year_ended,
                    year_ended_uncertain=self.year_ended_uncertain)
                use.save()
                use.commit_to_display()

    def get_absolute_url(self):
        if self.brand is None:
            return "/brand/revision/%i/preview" % self.id
        return self.brand.get_absolute_url()

    ######################################
    # TODO old methods, t.b.c

    def _field_list(self):
        fields = []
        fields.extend(PublisherRevisionBase._field_list(self))
        fields.append('parent')
        fields.insert(fields.index('url'), 'group')
        return fields

    def _get_blank_values(self):
        return {
            'name': '',
            'year_began': None,
            'year_ended': None,
            'year_began_uncertain': None,
            'year_ended_uncertain': None,
            'url': '',
            'notes': '',
            'keywords': '',
            'parent': None,
            'group': None,
        }

    def _imps_for(self, field_name):
        if field_name == 'group':
            return 1
        return PublisherRevisionBase._imps_for(self, field_name)

    def _queue_name(self):
        return '%s: %s (%s)' % (self.group.all()[0].name, self.name,
                                 self.year_began)


class PreviewBrand(Brand):
    class Meta:
        proxy = True

    @property
    def group(self):
        return self._group.all()


class BrandUseRevisionManager(RevisionManager):

    def clone_revision(self, brand_use, changeset):
        return BrandUseRevision.clone(brand_use, changeset)


def get_brand_use_field_list():
    return ['year_began', 'year_began_uncertain',
            'year_ended', 'year_ended_uncertain', 'notes']


class BrandUseRevision(Revision):
    class Meta:
        db_table = 'oi_brand_use_revision'
        ordering = ['-created', '-id']

    objects = BrandUseRevisionManager()

    brand_use = models.ForeignKey('gcd.BrandUse', null=True,
                                  related_name='revisions')

    emblem = models.ForeignKey('gcd.Brand', null=True,
                               related_name='use_revisions')

    publisher = models.ForeignKey('gcd.Publisher', null=True, db_index=True,
                                  related_name='brand_use_revisions')

    year_began = models.IntegerField(db_index=True, null=True)
    year_ended = models.IntegerField(null=True)
    year_began_uncertain = models.BooleanField(default=False)
    year_ended_uncertain = models.BooleanField(default=False)
    notes = models.TextField(max_length=255, blank=True)

    source_name = 'brand_use'
    source_class = BrandUse

    @property
    def source(self):
        return self.brand_use

    @source.setter
    def source(self, value):
        self.brand_use = value

    def _pre_delete(self, changes):
        for revision in self.source.revisions.all():
            setattr(revision, 'brand_use_id', None)
            revision.save()
        self.brand_use_id = None

    def _do_complete_added_revision(self, emblem, publisher):
        """
        Do the necessary processing to complete the fields of a new
        BrandUse revision for adding a record before it can be saved.
        """
        self.publisher = publisher
        self.emblem = emblem

    def __str__(self):
        return 'brand emblem %s used by %s.' % (self.emblem, self.publisher)

    ######################################
    # TODO old methods, t.b.c

    def _field_list(self):
        fields = get_brand_use_field_list()
        return fields

    def _get_blank_values(self):
        return {
            'publisher': None,
            'year_began': None,
            'year_ended': None,
            'year_began_uncertain': None,
            'year_ended_uncertain': None,
            'notes': ''
        }

    def _start_imp_sum(self):
        self._seen_year_began = False
        self._seen_year_ended = False

    def _imps_for(self, field_name):
        if field_name in ('year_began', 'year_began_uncertain'):
            if not self._seen_year_began:
                self._seen_year_began = True
                return 1
        elif field_name in ('year_ended', 'year_ended_uncertain'):
            if not self._seen_year_ended:
                self._seen_year_ended = True
                return 1
        else:
            return 1
        return 0

    def _queue_name(self):
        return '%s at %s (%s)' % (self.emblem.name, self.publisher.name,
                                   self.year_began)


class CoverRevisionManager(RevisionManager):
    """
    Custom manager allowing the cloning of revisions from existing rows.
    """

    def clone_revision(self, cover, changeset):
        """
        Given an existing Cover instance, create a new revision based on it.

        This new revision will be where the replacement is stored.
        """
        return RevisionManager.clone_revision(self,
                                              instance=cover,
                                              instance_class=Cover,
                                              changeset=changeset)

    def _do_create_revision(self, cover, changeset, **ignore):
        """
        Helper delegate to do the class-specific work of clone_revision.
        """
        revision = CoverRevision(
            # revision-specific fields:
            cover=cover,
            changeset=changeset,

            # copied fields:
            issue=cover.issue)

        revision.save()
        return revision


class CoverRevision(Revision):
    class Meta:
        db_table = 'oi_cover_revision'
        ordering = ['-created', '-id']

    objects = CoverRevisionManager()

    cover = models.ForeignKey(Cover, null=True, related_name='revisions')
    issue = models.ForeignKey(Issue, related_name='cover_revisions')

    marked = models.BooleanField(default=False)
    is_replacement = models.BooleanField(default=False)
    is_wraparound = models.BooleanField(default=False)
    front_left = models.IntegerField(default=0, null=True)
    front_right = models.IntegerField(default=0, null=True)
    front_bottom = models.IntegerField(default=0, null=True)
    front_top = models.IntegerField(default=0, null=True)

    file_source = models.CharField(max_length=255, null=True)

    def _get_source(self):
        return self.cover

    def _get_source_name(self):
        return 'cover'

    def _get_blank_values(self):
        """
        Covers don't do field comparisons, so just return an empty
        dictionary so we don't throw an exception if code calls this.
        """
        return {}

    def calculate_imps(self, prev_rev=None):
        if self.changeset.change_type != CTYPES['cover']:
            return 1
        return IMP_COVER_VALUE

    def _imps_for(self, field_name):
        """
        Covers are done purely on a flat point model and don't really have
        fields.  We shouldn't get here, but just in case, return 0 to be safe.
        """
        return 0

    def commit_to_display(self):
        # the file handling is in the view/covers code
        cover = self.cover

        if cover is None:
            # check for variants having added issue records
            issue_revisions = self.changeset.issuerevisions.all()
            if len(issue_revisions) == 0:
                cover = Cover(issue=self.issue)
            elif len(issue_revisions) == 1:
                if not issue_revisions[0].issue:
                    issue_revisions[0].commit_to_display()
                cover = Cover(issue=issue_revisions[0].issue)
                self.issue = cover.issue
            else:
                raise NotImplementedError
            cover.save()
        elif self.deleted:
            cover.delete()
            cover.save()
            update_count('covers', -1,
                         language=cover.issue.series.language,
                         country=cover.issue.series.country)
            if cover.issue.series.scan_count == 0:
                series = cover.issue.series
                series.has_gallery = False
                series.save()
            return

        if self.cover and self.is_replacement is False:
            # this is a move of a cover
            if self.changeset.change_type in [CTYPES['variant_add'],
                                              CTYPES['two_issues']]:
                old_issue = cover.issue
                issue_rev = self.changeset.issuerevisions\
                                          .exclude(issue=old_issue).get()
                cover.issue = issue_rev.issue
                cover.save()
                if issue_rev.series != old_issue.series:
                    if (issue_rev.series.language !=
                        old_issue.series.language) \
                       or (issue_rev.series.country !=
                           old_issue.series.country):
                        update_count('covers', -1,
                                     language=old_issue.series.language,
                                     country=old_issue.series.country)
                        update_count('covers', 1,
                                     language=issue_rev.series.language,
                                     country=issue_rev.series.country)
                    if not issue_rev.series.has_gallery:
                        issue_rev.series.has_gallery = True
                        issue_rev.series.save()
                    if old_issue.series.scan_count == 0:
                        old_issue.series.has_gallery = False
                        old_issue.series.save()
            else:
                # implement in case we do different kind if cover moves
                raise NotImplementedError
        else:
            from apps.oi.covers import copy_approved_cover
            if self.cover is None:
                self.cover = cover
                self.save()
                update_count('covers', 1,
                             language=cover.issue.series.language,
                             country=cover.issue.series.country)
                if not cover.issue.series.has_gallery:
                    series = cover.issue.series
                    series.has_gallery = True
                    series.save()
            copy_approved_cover(self)
            cover.marked = self.marked
            cover.last_upload = self.changeset.comments \
                                    .latest('created').created
            cover.is_wraparound = self.is_wraparound
            cover.front_left = self.front_left
            cover.front_right = self.front_right
            cover.front_top = self.front_top
            cover.front_bottom = self.front_bottom
            cover.save()

    def base_dir(self):
        return (settings.MEDIA_ROOT + settings.NEW_COVERS_DIR +
                self.changeset.created.strftime('%B_%Y/').lower())

    def approved_file(self):
        if not settings.BETA:
            if (self.created > settings.NEW_SITE_COVER_CREATION_DATE and
                not (self.deleted and
                     (self.previous().created <
                      settings.NEW_SITE_COVER_CREATION_DATE))):
                if self.changeset.state == states.APPROVED or self.deleted:
                    if self.deleted:
                        suffix = "/uploads/%d_%s" % (
                            self.cover.id,
                            self.previous().changeset
                                           .created.strftime('%Y%m%d_%H%M%S'))
                    else:
                        suffix = "/uploads/%d_%s" % (
                            self.cover.id,
                            self.changeset.created.strftime('%Y%m%d_%H%M%S'))
                    return "%s%s%d%s%s" % (
                        settings.IMAGE_SERVER_URL,
                        settings.COVERS_DIR,
                        int(self.cover.id / 1000),
                        suffix,
                        os.path.splitext(glob.glob(self.cover.base_dir() +
                                                   suffix + '*')[0])[1])
                else:
                    filename = "%s/%d" % (self.base_dir(), self.id)
                    return "%s%s%s%d%s" % (
                        settings.IMAGE_SERVER_URL,
                        settings.NEW_COVERS_DIR,
                        self.changeset.created.strftime('%B_%Y/').lower(),
                        self.id,
                        os.path.splitext(glob.glob(filename + '*')[0])[1])
            else:
                return "not supported for covers from the old site"
        else:
            return "not supported on BETA"

    def get_absolute_url(self):
        if self.cover is None:
            return "/cover/revision/%i/preview" % self.id
        return self.cover.get_absolute_url()

    def __str__(self):
        return str(self.issue)


class SeriesRevisionManager(RevisionManager):
    def clone_revision(self, series, changeset):
        return SeriesRevision.clone(series, changeset)


def get_series_field_list():
    return ['name', 'leading_article', 'imprint', 'format', 'color',
            'dimensions', 'paper_stock', 'binding', 'publishing_format',
            'publication_type', 'is_singleton', 'year_began',
            'year_began_uncertain', 'year_ended', 'year_ended_uncertain',
            'is_current', 'country', 'language', 'has_barcode',
            'has_indicia_frequency', 'has_isbn', 'has_issue_title',
            'has_volume', 'has_rating', 'is_comics_publication',
            'has_about_comics', 'tracking_notes', 'notes', 'keywords']


class SeriesRevision(Revision):
    class Meta:
        db_table = 'oi_series_revision'
        ordering = ['-created', '-id']

    objects = SeriesRevisionManager()

    series = models.ForeignKey(Series, null=True, related_name='revisions')

    # When adding a series, this requests the ongoing reservation upon
    # approval of the new series.  The request will be granted unless the
    # indexer has reached their maximum number of ongoing reservations
    # at the time of approval.
    reservation_requested = models.BooleanField(default=False)

    name = models.CharField(max_length=255)
    leading_article = models.BooleanField(default=False)

    # The "format" field is a legacy field that is being split into
    # color, dimensions, paper_stock, binding, and publishing_format
    format = models.CharField(max_length=255, blank=True)
    color = models.CharField(max_length=255, blank=True)
    dimensions = models.CharField(max_length=255, blank=True)
    paper_stock = models.CharField(max_length=255, blank=True)
    binding = models.CharField(max_length=255, blank=True)
    publishing_format = models.CharField(max_length=255, blank=True)
    publication_type = models.ForeignKey(SeriesPublicationType,
                                         null=True, blank=True)

    year_began = models.IntegerField()
    year_ended = models.IntegerField(null=True, blank=True)
    year_began_uncertain = models.BooleanField(default=False)
    year_ended_uncertain = models.BooleanField(default=False)
    is_current = models.BooleanField(default=False)

    publication_notes = models.TextField(blank=True)

    # Fields for tracking relationships between series.
    tracking_notes = models.TextField(blank=True)

    # Fields for handling the presence of certain issue fields
    has_barcode = models.BooleanField(default=False)
    has_indicia_frequency = models.BooleanField(default=False)
    has_isbn = models.BooleanField(default=False)
    has_issue_title = models.BooleanField(default=False)
    has_volume = models.BooleanField(default=False)
    has_rating = models.BooleanField(default=False)
    has_about_comics = models.BooleanField(default=False)

    is_comics_publication = models.BooleanField(default=False)
    is_singleton = models.BooleanField(default=False)

    notes = models.TextField(blank=True)
    keywords = models.TextField(blank=True, default='')

    # Country and Language info.
    country = models.ForeignKey(Country, related_name='series_revisions')
    language = models.ForeignKey(Language, related_name='series_revisions')

    # Fields related to the publishers table.
    publisher = models.ForeignKey(Publisher, related_name='series_revisions')
    imprint = models.ForeignKey(Publisher, null=True, blank=True, default=None,
                                related_name='imprint_series_revisions')
    date_inferred = models.BooleanField(default=False)

    source_name = 'series'
    source_class = Series

    @property
    def source(self):
        return self.series

    @source.setter
    def source(self, value):
        self.series = value

    @classmethod
    def _get_excluded_field_names(cls):
        return frozenset(
            super(SeriesRevision, cls)._get_excluded_field_names() |
            {'open_reserve', 'publication_dates'}
        )

    @classmethod
    def _get_parent_field_tuples(cls):
        return frozenset({('publisher',)})

    @classmethod
    def _get_major_flag_field_tuples(self):
        return frozenset({
            ('is_comics_publication',),
            ('is_current',),
            ('is_singleton',),
        })

    @classmethod
    def _get_deprecated_field_names(cls):
        return frozenset({'format'})

    def _pre_initial_save(self, fork=False, fork_source=None,
                          exclude=frozenset(), **kwargs):
        self.leading_article = self.series.name != self.series.sort_name

    def _do_complete_added_revision(self, publisher):
        """
        Do the necessary processing to complete the fields of a new
        series revision for adding a record before it can be saved.
        """
        self.publisher = publisher
        if self.is_singleton:
            self.year_ended = self.year_began
            self.year_ended_uncertain = self.year_began_uncertain

    def _TODO_handle_prerequisites(self, changes):
        # Handle deletion of the singleton issue before getting the
        # series stat counts to avoid double-counting the deletion.
        # TODO currently never used, has_dependents does not handle
        # singletons separately, so active_issues.count prevents joint delete
        if self.deleted and self.series.is_singleton:
            issue_revision = IssueRevision.clone(
                instance=self.series.issue_set[0], changeset=self.changeset)
            issue_revision.deleted = True
            issue_revision.save()
            # TODO if joint delete changed, check here in regard to counting
            issue_revision.commit_to_display()

    def _post_assign_fields(self, changes):
        if self.leading_article:
            self.series.sort_name = remove_leading_article(self.name)
        else:
            self.series.sort_name = self.name

    def _pre_save_object(self, changes):
        if changes['from is_current']:
            reservation = self.series.get_ongoing_reservation()
            if reservation:
                reservation.delete()

        if changes['to is_comics_publication']:
            # TODO: But don't we count covers for some non-comics?
            self.series.has_gallery = bool(self.series.scan_count)

    def _handle_dependents(self, changes):
        # Handle adding the singleton issue last, to avoid double-counting
        # the addition in statistics.
        if changes['to is_singleton'] and self.series.issue_count == 0:
            issue_revision = IssueRevision(changeset=self.changeset,
                                           series=self.series,
                                           after=None,
                                           number='[nn]',
                                           publication_date=self.year_began,
                                           reservation_requested=
                                           self.reservation_requested)
            # We assume that a non-four-digit year is a typo of some
            # sort, and do not propagate it.  The approval process
            # should catch that sort of thing.
            # TODO: Consider a validator on year_began?
            if len(str(self.year_began)) == 4:
                issue_revision.key_date = '%d-00-00' % self.year_began
            issue_revision.save()

    def get_absolute_url(self):
        if self.series is None:
            return "/series/revision/%i/preview" % self.id
        return self.series.get_absolute_url()

    def __str__(self):
        if self.series is None:
            return '%s (%s series)' % (self.name, self.year_began)
        return str(self.series)

    ######################################
    # TODO old methods, t.b.c

    def _field_list(self):
        fields = get_series_field_list()
        if self.previous() and (self.previous().publisher != self.publisher):
            fields = fields[0:2] + ['publisher'] + fields[2:]
        return fields + ['publication_notes']

    def _get_blank_values(self):
        return {
            'name': '',
            'leading_article': False,
            'format': '',
            'color': '',
            'dimensions': '',
            'paper_stock': '',
            'binding': '',
            'publishing_format': '',
            'publication_type': None,
            'is_singleton': False,
            'notes': '',
            'keywords': '',
            'year_began': None,
            'year_ended': None,
            'year_began_uncertain': None,
            'year_ended_uncertain': None,
            'is_current': None,
            'publication_notes': '',
            'tracking_notes': '',
            'country': None,
            'language': None,
            'publisher': None,
            'imprint': None,
            'has_barcode': True,
            'has_indicia_frequency': False,
            'has_isbn': True,
            'has_issue_title': False,
            'has_volume': False,
            'has_rating': False,
            'has_about_comics': False,
            'is_comics_publication': True,
        }

    def _start_imp_sum(self):
        self._seen_year_began = False
        self._seen_year_ended = False

    def _imps_for(self, field_name):
        years_found, value = _imps_for_years(self, field_name,
                                             'year_began', 'year_ended')
        if years_found:
            return value
        return 1


class SeriesBondRevisionManager(RevisionManager):

    def clone_revision(self, series_bond, changeset):
        """
        Create a new revision based on a SeriesBond instance.

        This new revision will be where the edits are made.
        """
        return RevisionManager.clone_revision(self,
                                              instance=series_bond,
                                              instance_class=SeriesBond,
                                              changeset=changeset)

    def _do_create_revision(self, series_bond, changeset):
        """
        Helper delegate to do the class-specific work of clone_revision.
        """
        revision = SeriesBondRevision(
            # revision-specific fields:
            series_bond=series_bond,
            changeset=changeset,

            # copied fields:
            origin=series_bond.origin,
            origin_issue=series_bond.origin_issue,
            target=series_bond.target,
            target_issue=series_bond.target_issue,
            bond_type=series_bond.bond_type,
            notes=series_bond.notes)

        revision.save()
        return revision


def get_series_bond_field_list():
    return ['bond_type', 'notes']


class SeriesBondRevision(Revision):
    class Meta:
        db_table = 'oi_series_bond_revision'
        ordering = ['-created', '-id']
        get_latest_by = "created"

    objects = SeriesBondRevisionManager()

    series_bond = models.ForeignKey(SeriesBond, null=True,
                                    related_name='revisions')

    origin = models.ForeignKey(Series, null=True,
                               related_name='origin_bond_revisions')
    origin_issue = models.ForeignKey(
        Issue, null=True, related_name='origin_series_bond_revisions')
    target = models.ForeignKey(Series, null=True,
                               related_name='target_bond_revisions')
    target_issue = models.ForeignKey(
        Issue, null=True, related_name='target_series_bond_revisions')

    bond_type = models.ForeignKey(SeriesBondType, null=True,
                                  related_name='bond_revisions')
    notes = models.TextField(max_length=255, default='', blank=True)

    def _field_list(self):
        return (['origin', 'origin_issue', 'target', 'target_issue'] +
                get_series_bond_field_list())

    def _get_blank_values(self):
        return {
            'origin': None,
            'origin_issue': None,
            'target': None,
            'target_issue': None,
            'bond_type': None,
            'notes': '',
        }

    def _start_imp_sum(self):
        self._seen_origin = False
        self._seen_target = False

    def _imps_for(self, field_name):
        """
        Only one point per origin/target change
        """
        if field_name in ('origin', 'origin_issue'):
            if not self._seen_origin:
                self._seen_origin = True
                return 1
        if field_name in ('target',
                          'target_issue'):
            if not self._seen_target:
                self._seen_target = True
                return 1
        if field_name in get_series_bond_field_list():
            return 1
        return 0

    def _get_source(self):
        return self.series_bond

    def _get_source_name(self):
        return 'series_bond'

    def _queue_name(self):
        return '%s continues at %s' % (self.origin, self.target)

    def commit_to_display(self):
        series_bond = self.series_bond
        if self.deleted:
            for revision in series_bond.revisions.all():
                setattr(revision, "series_bond_id", None)
                revision.save()
            series_bond.delete()
            return

        if series_bond is None:
            series_bond = SeriesBond()
        series_bond.origin = self.origin
        series_bond.origin_issue = self.origin_issue
        series_bond.target = self.target
        series_bond.target_issue = self.target_issue
        series_bond.notes = self.notes
        series_bond.bond_type = self.bond_type

        series_bond.save()
        if self.series_bond is None:
            self.series_bond = series_bond
            self.save()

    def __str__(self):
        if self.origin_issue:
            object_string = '%s' % self.origin_issue
        else:
            object_string = '%s' % self.origin
        if self.target_issue:
            object_string += ' continues at %s' % self.target_issue
        else:
            object_string += ' continues at %s' % self.target
        return object_string


class IssueRevisionManager(RevisionManager):
    def clone_revision(self, issue, changeset):
        return IssueRevision.clone(issue, changeset)


def get_issue_field_list():
    return ['number', 'title', 'no_title', 'volume',
            'no_volume', 'volume_not_printed', 'display_volume_with_number',
            'indicia_publisher', 'indicia_pub_not_printed',
            'brand', 'no_brand', 'publication_date', 'year_on_sale',
            'month_on_sale', 'day_on_sale', 'on_sale_date_uncertain',
            'key_date', 'indicia_frequency', 'no_indicia_frequency', 'price',
            'page_count', 'page_count_uncertain', 'editing', 'no_editing',
            'isbn', 'no_isbn', 'barcode', 'no_barcode', 'rating', 'no_rating',
            'notes', 'keywords']


class IssueRevision(Revision):
    class Meta:
        db_table = 'oi_issue_revision'
        ordering = ['-created', '-id']

    objects = IssueRevisionManager()

    issue = models.ForeignKey(Issue, null=True, related_name='revisions')

    # If not null, insert or move the issue after the given issue
    # when saving back the the DB. If null, place at the beginning of
    # the series.
    after = models.ForeignKey(
        Issue, null=True, blank=True, related_name='after_revisions')

    # This is used *only* for multiple issues within the same changeset.
    # It does NOT correspond directly to gcd_issue.sort_code, which must be
    # calculated at the time the revision is committed.
    revision_sort_code = models.IntegerField(null=True)

    # When adding an issue, this requests the reservation upon approval of
    # the new issue.  The request will be granted unless an ongoing reservation
    # is in place at the time of approval.
    reservation_requested = models.BooleanField(default=False)

    number = models.CharField(max_length=50)

    title = models.CharField(max_length=255, default='', blank=True)
    no_title = models.BooleanField(default=False)

    volume = models.CharField(max_length=50, blank=True, default='')
    no_volume = models.BooleanField(default=False)
    volume_not_printed = models.BooleanField(default=False)
    display_volume_with_number = models.BooleanField(default=False)
    variant_of = models.ForeignKey(Issue, null=True,
                                   related_name='variant_revisions')
    variant_name = models.CharField(max_length=255, blank=True, default='')

    publication_date = models.CharField(max_length=255, blank=True, default='')
    key_date = models.CharField(
        max_length=10, blank=True, default='',
        validators=[RegexValidator(
            r'^(17|18|19|20)\d{2}(\.|-)(0[0-9]|1[0-3])(\.|-)\d{2}$')])
    year_on_sale = models.IntegerField(db_index=True, null=True, blank=True)
    month_on_sale = models.IntegerField(db_index=True, null=True, blank=True)
    day_on_sale = models.IntegerField(db_index=True, null=True, blank=True)
    on_sale_date_uncertain = models.BooleanField(default=False)
    indicia_frequency = models.CharField(max_length=255, blank=True,
                                         default='')
    no_indicia_frequency = models.BooleanField(default=False)

    price = models.CharField(max_length=255, blank=True, default='')
    page_count = models.DecimalField(max_digits=10, decimal_places=3,
                                     null=True, blank=True, default=None)
    page_count_uncertain = models.BooleanField(default=False)

    editing = models.TextField(blank=True, default='')
    no_editing = models.BooleanField(default=False)
    notes = models.TextField(blank=True, default='')
    keywords = models.TextField(blank=True, default='')

    series = models.ForeignKey(Series, related_name='issue_revisions')
    indicia_publisher = models.ForeignKey(
        IndiciaPublisher, null=True, blank=True, default=None,
        related_name='issue_revisions')
    indicia_pub_not_printed = models.BooleanField(default=False)
    brand = models.ForeignKey(
        Brand, null=True, default=None, blank=True,
        related_name='issue_revisions')
    no_brand = models.BooleanField(default=False)

    isbn = models.CharField(max_length=32, blank=True, default='')
    no_isbn = models.BooleanField(default=False)

    barcode = models.CharField(max_length=38, blank=True, default='')
    no_barcode = models.BooleanField(default=False)

    rating = models.CharField(max_length=255, blank=True, default='')
    no_rating = models.BooleanField(default=False)

    date_inferred = models.BooleanField(default=False)

    source_name = 'issue'
    source_class = Issue

    @property
    def source(self):
        return self.issue

    @source.setter
    def source(self, value):
        self.issue = value

    @property
    def series_changed(self):
        """ True if the series changed and this is neither add nor delete. """
        return ((not self.deleted) and
                (self.previous_revision is not None) and
                self.previous_revision.series != self.series)

    @classmethod
    def fork_variant(cls, issue, changeset,
                     variant_name, variant_cover_revision=None,
                     reservation_requested=False):
        current_variants = issue.variant_set.all().order_by('-sort_code')
        if current_variants:
            add_after = current_variants[0]
        else:
            add_after = issue

        variant_revision = IssueRevision.clone(
            issue, changeset, fork=True, exclude={
                'publication_date',
                'key_date',
                'on_sale_date',
                'on_sale_date_uncertain',
                'price',
                'brand',
                'no_brand',
                'isbn',
                'no_isbn',
                'barcode',
                'no_barcode',
                'keywords',
            })
        variant_revision.add_after = add_after
        variant_revision.variant_of = issue
        variant_revision.variant_name = variant_name
        variant_revision.reservation_requested = reservation_requested
        variant_revision.save()

        if variant_cover_revision:
            cover_sequence_revision = StoryRevision(
                changeset=changeset,
                type=StoryType.objects.get(name='cover'),
                no_script=True,
                pencils='?',
                inks='?',
                colors='?',
                no_letters=True,
                no_editing=True,
                sequence_number=0,
                page_count=2 if variant_cover_revision.is_wraparound else 1)
            cover_sequence_revision.save()
        else:
            cover_sequence_revision = None

        return variant_revision, cover_sequence_revision

    @classmethod
    def _get_stats_category_field_tuples(cls):
        return frozenset({('series', 'country',), ('series', 'language',)})

    @classmethod
    def _get_conditional_field_tuple_mapping(cls):
        has_title = ('series', 'has_issue_title')
        has_barcode = ('series', 'has_barcode')
        has_isbn = ('series', 'has_isbn')
        has_volume = ('series', 'has_volume')
        has_ind_freq = ('series', 'has_indicia_frequency')
        return {
            'title': has_title,
            'no_title': has_title,
            'barcode': has_barcode,
            'no_barcode': has_barcode,
            'isbn': has_isbn,
            'no_isbn': has_isbn,
            'valid_isbn': has_isbn,
            'volume': has_volume,
            'no_volume': has_volume,
            'display_volume_with_issue': has_volume,
            'indicia_frequency': has_ind_freq,
            'no_indicia_frequency': has_ind_freq,
        }

    @classmethod
    def _get_parent_field_tuples(cls):
        # There are several routes to a publisher object, but
        # if there are differences, it is the publisher of the series
        # that should get the count adjustments.
        return frozenset({
            ('series',),
            ('series', 'publisher'),
            ('indicia_publisher',),
            ('brand',),
            ('brand', 'group'),
        })

    def _pre_initial_save(self, fork=False, fork_source=None,
                          exclude=frozenset(), **kwargs):
        source = fork_source if fork_source else self.issue
        if source.on_sale_date and 'on_sale_date' not in exclude:
            (self.year_on_sale,
             self.month_on_sale,
             self.day_on_sale) = on_sale_date_fields(source.on_sale_date)

    def _do_complete_added_revision(self, series, variant_of=None):
        """
        Do the necessary processing to complete the fields of a new
        issue revision for adding a record before it can be saved.
        """
        self.series = series
        if variant_of:
            self.variant_of = variant_of

    def _same_series_revisions(self):
        return self.changeset.issuerevisions.filter(series=self.series)

    def _same_series_open_with_after(self):
        return self._same_series_revisions().filter(after__isnull=False,
                                                    committed=None)

    def _open_prereq_revisions(self):
        # Adds and moves go first to last, deletes last to first.
        if self.deleted:
            return self._same_series_revisions().exclude(id__lte=self.id) \
                                                .filter(committed=None) \
                                                .order_by('-revision_sort_code')
        else:
            return self._same_series_revisions().exclude(id__gte=self.id) \
                                                .filter(committed=None) \
                                                .filter(issue=None) \
                                                .order_by('revision_sort_code')

    def _committed_prereq_revisions(self):
        # We pop off of open prereqs and push onto committed, so reverse sort.
        sort = 'revision_sort_code' if self.deleted else '-revision_sort_code'
        return self._same_series_revisions().exclude(id=self.id) \
                                            .filter(committed=True) \
                                            .order_by(sort)

    def _pre_commit_check(self):
        # If any other issue from this series has been committed, we have
        # already gone through this logic, so skip it.
        if self._same_series_revisions().filter(committed=True).exists():
            return

        # Verify that we have at most one uncommitted revision with this
        # series that has a non-null 'after' field.  This means that for now
        # we can only support one contiguous run of added/moved issues per
        # series.
        #
        # TODO: This may need further tweaking for various cases of working
        #       with variants, moving covers, etc. but is sufficient for
        #       general single and bulk issue operations.
        after = self._same_series_open_with_after()
        if after.count() > 1:
            raise ValueError(
                ("%s, %s: Only one IssueRevision per series within a "
                 "changeset can have 'after' set.  All others are assumed "
                 "to follow it based on the 'revision_sort_code' field.") %
                (self.changeset, self))
        if after.exists() and (after.first() !=
                               self._same_series_revisions()
                                   .filter(issue=None)
                                   .order_by('revision_sort_code')
                                   .first()):
            raise ValueError(
                ("%s, %s: The IssueRevision that specifies an 'after' must "
                 "have the lowest revision_sort_code.") %
                (self.changeset, after.first()))

    def _ensure_sort_code_space(self):
        first_rev = self._same_series_open_with_after().first()
        after_code = -1 if first_rev is None else first_rev.after.sort_code

        # Include deleted issues due to unique constraint on sort_code.
        later_issues = Issue.objects.filter(
            series=self.series,
            sort_code__gt=after_code).order_by('-sort_code')

        if not later_issues.exists():
            # We're appending to the series, no space needed.
            return

        num_issues = self._same_series_revisions().count()
        if later_issues.last().sort_code - after_code > num_issues:
            # Someone else already made space here.
            return

        for later_issue in later_issues:
            later_issue.sort_code += num_issues
            later_issue.save()

    def _handle_prerequisites(self, changes):
        if self.edited and not self.series_changed:
            # order of revision commit doesn't matter, as we do issue
            # sort_code reorderings separately from the main editing
            # workflow, at least for now.
            return

        if not self.deleted:
            self._ensure_sort_code_space()

        current_prereq_qs = self._open_prereq_revisions().all()
        current_prereq_count = current_prereq_qs.count()

        stats_changed = False
        while current_prereq_count:
            stats_changed = True
            current_prereq_qs.first().commit_to_display()
            # Always eval a new queryset as committing may cause other commits.
            # Calling all() produces an identical but unevaluated queryset.
            current_prereq_qs = current_prereq_qs.all()
            new_prereq_count = current_prereq_qs.count()

            if new_prereq_count >= current_prereq_count:
                # We should never *gain* revisions- even if we create
                # revisions during a commit, those newly created revisions
                # should themselves be committed before the other commit
                # completes.  Prevent infinite loops by raising.
                # TODO we can add revisions for later commit in some
                #      cases, e.g. when they are in a later part of
                #      the itertools.chain. Check on this assumption.
                raise RuntimeError("Committing revisions did not reduce the "
                                   "number of uncommitted revisions!")

            current_prereq_count = new_prereq_count

        # refresh the series, otherwise the updated issue_counts from the other
        # issues (i.e. current_prereq_qs) in a bulk-add are overwritten
        # TODO rethink this handling, rethink F
        # TODO what if series changes publisher
        if stats_changed:
            self.series.refresh_from_db()

    def _post_assign_fields(self, changes):
        self.issue.on_sale_date = on_sale_date_as_string(self)

        if self.series.has_isbn:
            self.issue.valid_isbn = validated_isbn(self.issue.isbn)

        # TODO: Support adding base + variant by adding a variant_of_rev
        #       field to IssueRevision and setting variant_of to the
        #       committed issue of the variant_of_rev field automatically,
        #       committing the variant_of_rev if necessary.
        #       Idea may be good for other new dependent object situations.
        if self.added or self.series_changed:
            if not self.after:
                # If we're handling a run of issues, this is the
                # previous issue in the run, if any.
                committed = self._committed_prereq_revisions().first()
                if committed:
                    self.after = committed.issue

            if self.after:
                self.issue.sort_code = self.after.sort_code + 1
            else:
                self.issue.sort_code = 0

    def _post_save_object(self, changes):
        self.series.set_first_last_issues()
        if self.series_changed:
            old_series = self.previous_revision.series
            old_series.set_first_last_issues()

            # new series might have gallery after move
            if not self.series.has_gallery and \
               self.issue.active_covers().count():
                self.series.has_gallery = True
                self.series.save()

            # old series might have lost gallery after move
            if old_series.scan_count == 0:
                old_series.has_gallery = False
                old_series.save()

    def _handle_dependents(self, changes):
        # These story revisions will handle their own stats when committed.
        # They will also update the issue's is_indexed field.
        for story in self.changeset.storyrevisions.filter(issue=None):
            story.issue = self.issue
            story.save()

    def get_absolute_url(self):
        if self.issue is None:
            return "/issue/revision/%i/preview" % self.id
        return self.issue.get_absolute_url()

    ######################################
    # TODO old methods, t.b.c

    @property
    def display_number(self):
        number = issue_descriptor(self)
        if number:
            return '#' + number
        else:
            return ''

    @property
    def other_issue_revision(self):
        if self.changeset.change_type in [CTYPES['variant_add'],
                                          CTYPES['two_issues']]:
            if not hasattr(self, '_saved_other_issue'):
                self._saved_other_issue_revision = self.changeset\
                    .issuerevisions.exclude(issue=self.issue)[0]
            return self._saved_other_issue_revision
        else:
            raise ValueError

    def can_add_reprints(self):
        if self.variant_of and self.ordered_story_revisions().count() > 0:
            return False
        return True

    # we need two checks if relevant reprint revisions exist:
    # 1) revisions which are active and link self.issue with a story/issue
    #    in the current direction under consideration
    # 2) existing reprints which are locked and which link self.issue
    #    with a story/issue in the current direction under consideration
    # if this is the case we return reprintrevisions and not reprint links
    # returned reprint links are three cases:
    # a) revisions in the current changeset which link self.issue with a
    #    story/issue in the current direction under consideration
    # b) newly added and active revisions in other changesets
    #    we do not need .exclude(changeset__id=self.changeset_id)\ the new
    #    ones from the current changeset we want anyway
    # c) for the current corresponding reprint links the latest revisions
    #    which are not in the current changeset, the latest can be fetched
    #    via next_revision=None, that way we get either approved or active ones

    def old_revisions_base(self):
        revs = ReprintRevision.objects \
                              .exclude(changeset__id=self.changeset_id)\
                              .exclude(changeset__state=states.DISCARDED)
        return revs

    def from_reprints_oi(self, preview=False):
        if self.issue is None:
            return ReprintToIssue.objects.none()
        from_reprints = self.issue.from_reprints.all()
        if self.issue.target_reprint_revisions.active_set()\
               .filter(origin_issue=None).count() \
                or RevisionLock.objects.filter(
                  object_id__in=from_reprints.values_list(
                                              'id', flat=True)).exists():
            new_revisions = self.issue.target_reprint_revisions\
                                .filter(changeset__id=self.changeset_id)\
                                .filter(origin_issue=None)
            if not preview:
                new_revisions |= \
                    self.issue.target_reprint_revisions.active_set()\
                        .filter(in_type=None, origin_issue=None)
            else:
                new_revisions = new_revisions.exclude(deleted=True)
            existing_reprints = from_reprints
            old_revisions = self.old_revisions_base()\
                                .filter(reprint_to_issue__in=existing_reprints,
                                        next_revision=None)
            return new_revisions | old_revisions
        else:
            return from_reprints

    def from_issue_reprints_oi(self, preview=False):
        if self.issue is None:
            return IssueReprint.objects.none()
        from_issue_reprints = self.issue.from_issue_reprints.all()
        if self.issue.target_reprint_revisions.active_set()\
               .exclude(origin_issue=None).count() \
                or RevisionLock.objects.filter(
                  object_id__in=from_issue_reprints.values_list(
                                                    'id', flat=True)).exists():
            new_revisions = self.issue.target_reprint_revisions\
                                .filter(changeset__id=self.changeset_id)\
                                .exclude(origin_issue=None)
            if not preview:
                new_revisions |= \
                    self.issue.target_reprint_revisions.active_set()\
                        .filter(in_type=None)\
                        .exclude(origin_issue=None)
            else:
                new_revisions = new_revisions.exclude(deleted=True)
            existing_reprints = from_issue_reprints
            old_revisions = self.old_revisions_base()\
                                .filter(issue_reprint__in=existing_reprints,
                                        next_revision=None)
            return new_revisions | old_revisions
        else:
            return from_issue_reprints

    def to_reprints_oi(self, preview=False):
        if self.issue is None:
            return ReprintFromIssue.objects.none()
        to_reprints = self.issue.to_reprints.all()
        if self.issue.origin_reprint_revisions.active_set()\
               .filter(target_issue=None).count() \
                or RevisionLock.objects.filter(
                  object_id__in=to_reprints.values_list(
                                            'id', flat=True)).exists():
            new_revisions = self.issue.origin_reprint_revisions\
                                .filter(changeset__id=self.changeset_id)\
                                .filter(target_issue=None)
            if not preview:
                new_revisions |= \
                    self.issue.origin_reprint_revisions.active_set()\
                        .filter(in_type=None, target_issue=None)
            else:
                new_revisions = new_revisions.exclude(deleted=True)
            existing_reprints = to_reprints
            old_revisions = \
                self.old_revisions_base()\
                    .filter(reprint_from_issue__in=existing_reprints,
                            next_revision=None)
            return new_revisions | old_revisions
        else:
            return to_reprints

    def to_issue_reprints_oi(self, preview=False):
        if self.issue is None:
            return IssueReprint.objects.none()
        to_issue_reprints = self.issue.to_issue_reprints.all()
        if self.issue.origin_reprint_revisions.active_set()\
               .exclude(target_issue=None).count() \
                or RevisionLock.objects.filter(
                  object_id__in=to_issue_reprints.values_list(
                                                  'id', flat=True)).exists():
            new_revisions = self.issue.origin_reprint_revisions\
                                .filter(changeset__id=self.changeset_id)\
                                .exclude(target_issue=None)
            if not preview:
                new_revisions |= \
                    self.issue.origin_reprint_revisions.active_set()\
                        .filter(in_type=None)\
                        .exclude(target_issue=None)
            else:
                new_revisions = new_revisions.exclude(deleted=True)
            existing_reprints = to_issue_reprints
            old_revisions = self.old_revisions_base()\
                                .filter(issue_reprint__in=existing_reprints,
                                        next_revision=None)
            return new_revisions | old_revisions
        else:
            return to_issue_reprints

    def has_reprint_revisions(self):
        if self.issue is None:
            return False
        if self.issue.target_reprint_revisions\
               .filter(changeset__id=self.changeset_id).count():
            return True
        elif self.issue.origin_reprint_revisions\
                 .filter(changeset__id=self.changeset_id).count():
            return True
        # TODO: before there was the reserved=True here in the filter, why ?
        if self.issue.to_reprints\
               .filter(revisions__changeset=self.changeset)\
               .count():
            return True
        if self.issue.from_reprints\
               .filter(revisions__changeset=self.changeset)\
               .count():
            return True
        if self.issue.to_issue_reprints\
               .filter(revisions__changeset=self.changeset)\
               .count():
            return True
        if self.issue.from_issue_reprints\
               .filter(revisions__changeset=self.changeset)\
               .count():
            return True
        if self.changeset.state == states.APPROVED:
            active = ReprintRevision.objects.\
                filter(next_revision__in=self.changeset.reprintrevisions.all())
            if active.filter(origin_issue=self.issue):
                return True
            if active.filter(target_issue=self.issue):
                return True
        return False

    # IssueRevisions cannot have reprint links, need to fake for compare-view,
    def _empty_reprint_revisions(self):
        return ReprintRevision.objects.none()
    origin_reprint_revisions = property(_empty_reprint_revisions)
    target_reprint_revisions = property(_empty_reprint_revisions)

    # TODO what can be re-used/share with PreviewIssue
    def active_stories(self):
        return self.story_set.exclude(deleted=True)

    @property
    def story_set(self):
        return self.ordered_story_revisions()

    def _story_revisions(self):
        if self.source is None:
            return self.changeset.storyrevisions.filter(issue__isnull=True)\
                                 .select_related('changeset', 'type')
        return self.changeset.storyrevisions.filter(issue=self.source)\
                             .select_related('changeset', 'issue', 'type')

    def ordered_story_revisions(self):
        return self._story_revisions().order_by('sequence_number')

    def next_sequence_number(self):
        stories = self._story_revisions()
        if stories.count():
            return stories.order_by('-sequence_number')[0].sequence_number + 1
        return 0

    def _field_list(self):
        fields = get_issue_field_list()
        if self.changeset.change_type == CTYPES['issue_add'] or \
           self.changeset.change_type == CTYPES['variant_add'] and \
           self.variant_of:
            fields = ['after'] + fields
        if not self.series.has_barcode and \
           self.changeset.change_type != CTYPES['issue_bulk']:
            fields.remove('barcode')
            fields.remove('no_barcode')
        if not self.series.has_indicia_frequency and \
           self.changeset.change_type != CTYPES['issue_bulk']:
            fields.remove('indicia_frequency')
            fields.remove('no_indicia_frequency')
        if not self.series.has_isbn and \
           self.changeset.change_type != CTYPES['issue_bulk']:
            fields.remove('isbn')
            fields.remove('no_isbn')
        if not self.series.has_issue_title and \
           self.changeset.change_type != CTYPES['issue_bulk']:
            fields.remove('title')
            fields.remove('no_title')
        if not self.series.has_volume and \
           self.changeset.change_type != CTYPES['issue_bulk']:
            fields.remove('volume')
            fields.remove('no_volume')
            fields.remove('volume_not_printed')
            fields.remove('display_volume_with_number')
        if self.variant_of or (self.issue and self.issue.variant_set.count()) \
           or self.changeset.change_type == CTYPES['variant_add']:
            fields = fields[0:1] + ['variant_name'] + fields[1:]
        if self.previous() and (self.previous().series != self.series):
            fields = ['series'] + fields
        return fields

    def _get_blank_values(self):
        return {
            'number': '',
            'title': '',
            'no_title': False,
            'volume': '',
            'no_volume': False,
            'volume_not_printed': False,
            'display_volume_with_number': None,
            'publication_date': '',
            'price': '',
            'key_date': '',
            'year_on_sale': None,
            'month_on_sale': None,
            'day_on_sale': None,
            'on_sale_date_uncertain': False,
            'indicia_frequency': '',
            'no_indicia_frequency': False,
            'series': None,
            'indicia_publisher': None,
            'indicia_pub_not_printed': False,
            'brand': None,
            'no_brand': False,
            'page_count': None,
            'page_count_uncertain': False,
            'editing': '',
            'no_editing': False,
            'isbn': '',
            'no_isbn': False,
            'barcode': '',
            'no_barcode': False,
            'rating': '',
            'no_rating': False,
            'notes': '',
            'sort_code': None,
            'after': None,
            'variant_name': '',
            'keywords': ''
        }

    def _start_imp_sum(self):
        self._seen_volume = False
        self._seen_title = False
        self._seen_indicia_publisher = False
        self._seen_indicia_frequency = False
        self._seen_brand = False
        self._seen_page_count = False
        self._seen_editing = False
        self._seen_isbn = False
        self._seen_barcode = False
        self._seen_rating = False
        self._seen_on_sale_date = False

    def _imps_for(self, field_name):
        if field_name in ('number', 'publication_date', 'key_date', 'series',
                          'price', 'notes', 'variant_name', 'keywords'):
            return 1
        if not self._seen_volume and \
           field_name in ('volume', 'no_volume', 'volume_not_printed',
                          'display_volume_with_number'):
            self._seen_volume = True
            return 1
        if not self._seen_title and field_name in ('title', 'no_title'):
            self._seen_title = True
            return 1
        if not self._seen_indicia_publisher and \
           field_name in ('indicia_publisher', 'indicia_pub_not_printed'):
            self._seen_indicia_publisher = True
            return 1
        if not self._seen_indicia_frequency and \
           field_name in ('indicia_frequency', 'no_indicia_frequency'):
            self._seen_indicia_frequency = True
            return 1
        if not self._seen_brand and field_name in ('brand', 'no_brand'):
            self._seen_brand = True
            return 1
        if not self._seen_page_count and \
           field_name in ('page_count', 'page_count_uncertain'):
            self._seen_page_count = True
            if field_name == 'page_count':
                return 1

            # checking the 'uncertain' box  without also at least guessing
            # the page count itself doesn't count as IMP-worthy information.
            if field_name == 'page_count_uncertain' and \
               self.page_count is not None:
                return 1
        if not self._seen_editing and field_name in ('editing', 'no_editing'):
            self._seen_editing = True
            return 1
        if not self._seen_isbn and field_name in ('isbn', 'no_isbn'):
            self._seen_isbn = True
            return 1
        if not self._seen_barcode and field_name in ('barcode', 'no_barcode'):
            self._seen_barcode = True
            return 1
        if not self._seen_rating and field_name in ('rating', 'no_rating'):
            self._seen_rating = True
            return 1
        if not self._seen_on_sale_date and \
           field_name in ('year_on_sale', 'month_on_sale',
                          'day_on_sale', 'on_sale_date_uncertain'):
            self._seen_on_sale_date = True
            if field_name in ('year_on_sale', 'month_on_sale', 'day_on_sale'):
                return 1

            if field_name == 'on_sale_date_uncertain':
                if self.year_on_sale or self.month_on_sale or self.day_on_sale:
                    return 1
        # Note, the "after" field does not directly contribute IMPs.
        return 0

    def _create_dependent_revisions(self, delete=False):
        for story in self.issue.active_stories():
            # currently stories cannot be reserved without the issue, but
            # check anyway
            # TODO check if transaction rollback works
            story_lock = _get_revision_lock(story, changeset=self.changeset)
            if story_lock is None:
                raise IntegrityError("needed Story lock not possible")
            story_revision = StoryRevision.clone(story, self.changeset)
            if delete:
                story_revision.toggle_deleted()
            for credit in story.active_credits:
                credit_lock = _get_revision_lock(credit,
                                                 changeset=self.changeset)
                if credit_lock is None:
                    raise IntegrityError("needed Credit lock not possible")
                credit_revision = StoryCreditRevision.clone(
                  credit, self.changeset, story_revision=story_revision)
                if delete:
                    credit_revision.toggle_deleted()
        if delete:
            for cover in self.issue.active_covers():
                # cover can be reserved, so this can fail
                # TODO check if transaction rollback works
                cover_lock = _get_revision_lock(cover,
                                                changeset=self.changeset)
                if cover_lock is None:
                    raise IntegrityError("needed Cover lock not possible")
                # TODO change CoverRevision handling to normal one
                cover_revision = CoverRevision(changeset=self.changeset,
                                               issue=cover.issue,
                                               cover=cover, deleted=True)
                cover_revision.save()

    def _check_first_last(self):
        set_series_first_last(self.series)

    def full_name(self):
        if self.variant_name:
            return '%s %s [%s]' % (self.series.full_name(),
                                    self.display_number,
                                    self.variant_name)
        else:
            return '%s %s' % (self.series.full_name(), self.display_number)

    def short_name(self):
        if self.variant_name:
            return '%s %s [%s]' % (self.series.name,
                                    self.display_number,
                                    self.variant_name)
        else:
            return '%s %s' % (self.series.name, self.display_number)

    def __str__(self):
        """
        Re-implement locally instead of using self.issue because it may change.
        """
        if self.variant_name:
            return '%s %s [%s]' % (self.series, self.display_number,
                                    self.variant_name)
        elif self.display_number:
            return '%s %s' % (self.series, self.display_number)
        else:
            return '%s' % self.series


class PreviewIssue(Issue):
    # TODO add and use PreviewIssue.init
    class Meta:
        proxy = True

    def get_prev_next_issue(self):
        if self.id:
            return self._get_prev_next_issue()
        if self.after is not None:
            [p, n] = self.after.get_prev_next_issue()
            return [self.after, n]
        return [None, None]

    def active_variants(self):
        if self.id == 0:
            return Cover.objects.none()
        # TODO in case of variant add together with issue, would
        # need to do something like the following to be correct.
        # We can do something like this with other_variants, there
        # we have a list. Better to use that one in templates for checks
        # when displaying something which is preview-relevant.
        # maybe iterchain helps, but that does not provide a count
        # if self.revision.changeset.issuerevisions.filter(variant_of=self)\
        # .exists():
        # return (self._active_variants() | self.revision.changeset
        # .issuerevisions
        # .filter(variant_of=self))
        # else:
        return self._active_variants()

    def other_variants(self):
        if self.variant_of:
            variants = self.variant_of.active_variants()
            if self.id:
                variants = variants.exclude(id=self.id)
        else:
            variants = self.active_variants()
        variants = list(variants)

        # check for newly added variants
        if self.revision.changeset.issuerevisions.filter(variant_of=self,
                                                         issue=None)\
                                                 .exists():
            variants.extend(self.revision.changeset.issuerevisions
                                         .filter(variant_of=self,
                                                 issue=None))
        return variants

    def active_covers(self):
        if self.can_have_cover():
            if self.id != 0:
                return self._active_covers()
        return Cover.objects.none()

    def active_stories(self):
        stories = self.revision.story_set.exclude(deleted=True)\
                                     .order_by('sequence_number')\
                                     .select_related('type')
        active_stories = []
        for story in stories:
            preview_story = PreviewStory.init(story)
            preview_story.issue = self
            active_stories.append(preview_story)
        return active_stories

    def shown_stories(self):
        if self.variant_of:
            if self.issuerevisions.filter(issue=self.variant_of).exists():
                # if base_issue is part of the changeset use the storyrevisions
                # TODO add and use PreviewIssue.init
                base_issue_revision = self.issuerevisions\
                                 .filter(issue=self.variant_of).get()
                base_issue = PreviewIssue(base_issue_revision.source)
                base_issue.storyrevisions = base_issue_revision.changeset\
                                                               .storyrevisions
                base_issue.id = base_issue_revision.source.id
                base_issue.revision = base_issue_revision
                base_issue.series = base_issue_revision.series
                stories = base_issue.active_stories()
            else:
                base_issue = self.variant_of
                stories = list(base_issue.active_stories())
        else:
            stories = self.active_stories()
        if self.series.is_comics_publication:
            if (len(stories) > 0):
                cover_story = stories.pop(0)
                if self.variant_of:
                    # can have only one sequence, the variant cover
                    own_stories = self.active_stories()
                    if own_stories:
                        cover_story = own_stories[0]
            elif self.variant_of and len(self.active_stories()):
                cover_story = self.active_stories()[0]
            else:
                cover_story = None
        else:
            cover_story = None
        return cover_story, stories

    # we do not use ignore on preview, since target does not exist
    # for revision and property cannot be filtered on
    def has_reprints(self):
        """Simplifies UI checks for conditionals, notes and reprint fields"""
        return self.from_reprints.count() or \
            self.to_reprints.count() or \
            self.from_issue_reprints.count() or \
            self.to_issue_reprints.count()

    @property
    def from_reprints(self):
        return self.revision.from_reprints_oi(preview=True)

    @property
    def to_reprints(self):
        return self.revision.to_reprints_oi(preview=True)

    @property
    def from_issue_reprints(self):
        return self.revision.from_issue_reprints_oi(preview=True)

    @property
    def to_issue_reprints(self):
        return self.revision.to_issue_reprints_oi(preview=True)

    def has_keywords(self):
        return self.revision.has_keywords()


def get_story_field_list():
    return ['sequence_number', 'title', 'title_inferred', 'first_line',
            'type', 'feature', 'feature_object', 'feature_logo', 'genre',
            'job_number', 'script', 'no_script', 'pencils', 'no_pencils',
            'inks', 'no_inks', 'colors', 'no_colors', 'letters', 'no_letters',
            'editing', 'no_editing', 'page_count', 'page_count_uncertain',
            'characters', 'synopsis', 'reprint_notes', 'notes', 'keywords']


class StoryCreditRevision(Revision):
    class Meta:
        db_table = 'oi_story_credit_revision'
        ordering = ['credit_type__sort_code', 'id']

    story_credit = models.ForeignKey(StoryCredit, null=True,
                                     related_name='revisions')

    creator = models.ForeignKey(CreatorNameDetail)
    credit_type = models.ForeignKey(CreditType)
    story_revision = models.ForeignKey('StoryRevision',
                                       related_name='story_credit_revisions')

    is_credited = models.BooleanField(default=False, db_index=True)
    is_signed = models.BooleanField(default=False, db_index=True)

    uncertain = models.BooleanField(default=False, db_index=True)

    signed_as = models.CharField(max_length=255, blank=True)
    credited_as = models.CharField(max_length=255, blank=True)

    # record for a wider range of creative work types, or how it is credited
    credit_name = models.CharField(max_length=255, blank=True)

    source_name = 'story_credit'
    source_class = StoryCredit

    @property
    def source(self):
        return self.story_credit

    @source.setter
    def source(self, value):
        self.story_credit = value

    def _pre_save_object(self, changes):
        self.story_credit.story = self.story_revision.story

    def _do_complete_added_revision(self, story_revision):
        self.story_revision = story_revision

    def _pre_initial_save(self, fork=False, fork_source=None,
                          exclude=frozenset(), **kwargs):
        self.story_revision = kwargs['story_revision']

    def __unicode__(self):
        return "%s: %s (%s)" % (self.story_revision, self.creator,
                                 self.credit_type)

    ######################################
    # TODO old methods, t.b.c

    _base_field_list = ['creator', 'credit_type', 'is_credited', 'is_signed',
                        'uncertain', 'signed_as', 'credited_as', 'credit_name']

    def _field_list(self):
        return self._base_field_list

    def _get_blank_values(self):
        return {
            'creator': None,
            'credit_type': None,
            'story': None,
            'is_credited': False,
            'is_signed': False,
            'uncertain': False,
            'signed_as': '',
            'credited_as': '',
            'credit_name': '',
        }

    def _imps_for(self, field_name):
        # imps already come from StoryRevision, since is_changed is True there
        return 0


class StoryRevisionManager(RevisionManager):
    def clone_revision(self, story, changeset):
        return StoryRevision.clone(story, changeset)


class StoryRevision(Revision):
    class Meta:
        db_table = 'oi_story_revision'
        ordering = ['-created', '-id']

    objects = StoryRevisionManager()

    story = models.ForeignKey(Story, null=True,
                              related_name='revisions')

    title = models.CharField(max_length=255, blank=True)
    title_inferred = models.BooleanField(default=False)
    first_line = models.CharField(max_length=255, blank=True)
    feature = models.CharField(max_length=255, blank=True)
    feature_object = models.ManyToManyField(Feature, blank=True)
    feature_logo = models.ManyToManyField(FeatureLogo, blank=True)
    type = models.ForeignKey(StoryType)
    sequence_number = models.IntegerField()

    page_count = models.DecimalField(max_digits=10, decimal_places=3,
                                     null=True, blank=True)
    page_count_uncertain = models.BooleanField(default=False)

    script = models.TextField(blank=True)
    pencils = models.TextField(blank=True)
    inks = models.TextField(blank=True)
    colors = models.TextField(blank=True)
    letters = models.TextField(blank=True)
    editing = models.TextField(blank=True)

    no_script = models.BooleanField(default=False)
    no_pencils = models.BooleanField(default=False)
    no_inks = models.BooleanField(default=False)
    no_colors = models.BooleanField(default=False)
    no_letters = models.BooleanField(default=False)
    no_editing = models.BooleanField(default=False)

    job_number = models.CharField(max_length=25, blank=True)
    genre = models.CharField(max_length=255, blank=True)
    characters = models.TextField(blank=True)
    synopsis = models.TextField(blank=True)
    reprint_notes = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    keywords = models.TextField(blank=True, default='')

    issue = models.ForeignKey(Issue, null=True, related_name='story_revisions')
    date_inferred = models.BooleanField(default=False)

    source_name = 'story'
    source_class = Story

    @property
    def source(self):
        return self.story

    @source.setter
    def source(self, value):
        self.story = value

    @classmethod
    def _get_stats_category_field_tuples(cls):
        return frozenset({('issue', 'series', 'country',),
                          ('issue', 'series', 'language',)})

    @classmethod
    def copied_revision(cls, story, changeset, issue):
        """
        Given an existing story, create a new revision based on it for a
        new story with the copied data. 'fork' is set to true in such a case.
        """
        revision = StoryRevision.clone(story, changeset, fork=True)
        issue_revision = changeset.issuerevisions.get(issue=issue)
        revision.issue = issue
        revision.sequence_number = issue_revision.next_sequence_number()
        if revision.issue.series.language != story.issue.series.language:
            if revision.letters:
                revision.letters = '?'
            revision.title = ''
            revision.title_inferred = False
            revision.first_line = ''
        revision.save()
        for credit in story.active_credits:
            StoryCreditRevision.clone(credit, revision.changeset,
                                      fork=True, story_revision=revision)
        return revision

    def _get_major_changes(self, extra_field_tuples=frozenset()):
        # We need to look at issue for index status changes, but it does
        # not otherwise behave like a normal parent field, nor does it
        # fit into any of the other unusual field classifications.
        extras = {('issue',)}

        if extra_field_tuples:
            # extra_field_tuples might be a frozenset, so add to our new
            # set rather than the other way around.
            extras.add(extra_field_tuples)

        return super(StoryRevision, self)._get_major_changes(
            extra_field_tuples=extras)

    def compare_changes(self):
        super(StoryRevision, self).compare_changes()
        for credit_type in CREDIT_TYPES:
            if not self.deleted and not self.changed[credit_type]:
                credits = self.story_credit_revisions.filter(
                               credit_type__name=credit_type)
                if credits:
                    for credit in credits:
                        credit.compare_changes()
                        if credit.is_changed:
                            self.changed[credit_type] = True
                            self.is_changed = True
                            break

    def _do_complete_added_revision(self, issue):
        """
        Do the necessary processing to complete the fields of a new
        story revision for adding a record before it can be saved.
        """
        self.issue = issue

    def _reset_values(self):
        if self.deleted:
            # users can edit story revisions before deleting them.
            # ensure that the final deleted revision matches the
            # final state of the story.
            self.title = self.story.title
            self.title_inferred = self.story.title_inferred
            self.first_line = self.first_line
            self.feature = self.story.feature
            self.page_count = self.story.page_count
            self.page_count_uncertain = self.story.page_count_uncertain

            self.script = self.story.script
            self.pencils = self.story.pencils
            self.inks = self.story.inks
            self.colors = self.story.colors
            self.letters = self.story.letters
            self.editing = self.story.editing

            self.no_script = self.story.no_script
            self.no_pencils = self.story.no_pencils
            self.no_inks = self.story.no_inks
            self.no_colors = self.story.no_colors
            self.no_letters = self.story.no_letters
            self.no_editing = self.story.no_editing

            self.notes = self.story.notes
            self.synopsis = self.story.synopsis
            self.characters = self.story.characters
            self.reprint_notes = self.story.reprint_notes
            self.genre = self.story.genre
            self.type = self.story.type
            self.job_number = self.story.job_number
            self.sequence_number = self.story.sequence_number
            self.save()

    def _post_m2m_add(self, fork=False, fork_source=None, exclude=frozenset()):
        # fields of BiblioEntry need to be handled separately
        if self.type.id == STORY_TYPES['about comics']:
            biblio_revision = BiblioEntryRevision(storyrevision_ptr=self)
            # need to copy everything
            biblio_revision.__dict__.update(self.__dict__)
            source_story = biblio_revision.source
            if fork is True:
                source_story = fork_source
            # copy single value fields which are specific to biblio_entry
            for field in biblio_revision.\
                           _get_single_value_fields().keys() - \
                         biblio_revision.storyrevision_ptr.\
                           _get_single_value_fields().keys():
                setattr(biblio_revision, field,
                        getattr(source_story.biblioentry, field))
            biblio_revision.save()

    def _handle_dependents(self, changes):
        # fields of BiblioEntry need to be handled separately
        if self.type.id == STORY_TYPES['about comics']:
            if not hasattr(self.source, 'biblioentry'):
                biblio_entry = BiblioEntry(story_ptr=self.source)
                biblio_entry.__dict__.update(self.source.__dict__)
                biblio_entry.save()
                self.biblioentryrevision.save()
            self.biblioentryrevision._copy_fields_to(
              self.biblioentryrevision.source.biblioentry)
            self.biblioentryrevision.source.biblioentry.save()
        elif hasattr(self.source, 'biblioentry'):
            # former BiblioEntry, delete add-on type
            super(GcdData, self.biblioentryrevision.source.biblioentry)\
                  .delete(keep_parents=True)

        # While committing an issue is a prerequisite for the story,
        # accounting for index status changes is dependent upon the
        # story commit.
        issues = [] if self.added else [changes['old issue']]
        if changes['issue changed'] and not self.deleted:
            issues.append(changes['new issue'])

        # import pytest
        for issue in issues:
            delta = issue.set_indexed_status()
            if delta:
                if self.edited:
                    assert issue.series.country is not None
                    assert issue.series.language is not None
                CountStats.objects.update_all_counts(
                    {'issue indexes': delta},
                    country=issue.series.country,
                    language=issue.series.language)
            # this is done for every story, but does not result in double
            # entries in RecentIndexedIssue, check is in update_recents
            #
            # maybe can be done using changes[] on the changeset level ?
            if issue.is_indexed:
                RecentIndexedIssue.objects.update_recents(issue)

    def extra_forms(self, request):
        from apps.oi.forms.story import StoryRevisionFormSet
        credits_formset = StoryRevisionFormSet(request.POST or None,
          instance=self,
          queryset=self.story_credit_revisions.filter(deleted=False))
        return {'credits_formset': credits_formset, }

    def process_extra_forms(self, request, extra_forms):
        credits_formset = extra_forms['credits_formset']
        for credit_form in credits_formset:
            if credit_form.is_valid() and credit_form.cleaned_data:
                cd = credit_form.cleaned_data
                if 'id' in cd and cd['id']:
                    credit_form.save()
                else:
                    credit_revision = credit_form.save(commit=False)
                    credit_revision.save_added_revision(
                      changeset=self.changeset, story_revision=self)
                    if credit_revision.credit_type.id in [7, 8, 9]:
                        if credit_revision.credit_type.id == 9:
                            credit_revision.credit_name = 'painting'
                        credit_revision.credit_type = \
                          CreditType.objects.get(id=2)
                        credit_revision.save()
                        credit_revision.id = None
                        credit_revision.credit_type = \
                          CreditType.objects.get(id=3)
                        credit_revision.save()
                        if cd['credit_type'].id in [8, 9]:
                            credit_revision.id = None
                            credit_revision.credit_type = \
                              CreditType.objects.get(id=4)
                            credit_revision.save()
            elif not credit_form.is_valid() and \
              credit_form not in credits_formset.deleted_forms:
                raise ValueError
        removed_credits = credits_formset.deleted_forms
        if removed_credits:
            for removed_credit in removed_credits:
                if removed_credit.cleaned_data['id']:
                    if removed_credit.cleaned_data['id'].story_credit:
                        removed_credit.cleaned_data['id'].deleted = True
                        removed_credit.cleaned_data['id'].save()
                    else:
                        removed_credit.cleaned_data['id'].delete()

    def deletable(self):
        if self.changeset.reprintrevisions \
                         .filter(origin_story=self.story).count() \
                or self.changeset.reprintrevisions \
                                 .filter(target_story=self.story).count() \
                or (self.story and self.story.has_reprints(notes=False)):
            return False
        else:
            return True

    def toggle_deleted(self):
        """
        Mark this revision as deleted, meaning that instead of copying it
        back to the display table, the display table entry will be removed
        when the revision is committed.
        """
        self.deleted = not self.deleted
        self.save()

    def get_absolute_url(self):
        if self.story is None:
            return "/issue/revision/%i/preview/#%i" % (
                self.my_issue_revision.id, self.id)
        return self.story.get_absolute_url()

    def has_feature(self):
        """
        feature_logo entry automatically results in corresponding
        feature_object entry, therefore no check needed
        """
        return self.feature or self.feature_object.count()

    def show_feature(self):
        return show_feature(self)

    def __str__(self):
        """
        Re-implement locally instead of using self.story because it may change.
        """
        return '%s (%s: %s)' % (self.feature, self.type, self.page_count)

    ######################################
    # TODO old methods, t.b.c.

    @property
    def my_issue_revision(self):
        if not hasattr(self, '_saved_my_issue_revision'):
            self._saved_my_issue_revision = \
                self.changeset.issuerevisions.filter(issue=self.issue)[0]
        return self._saved_my_issue_revision

    def moveable(self):
        """
        A story revision is moveable
        a) if it is not currently attached to an issue and is a revision of a
           previously existing story. Therefore it is a story which was moved
           to the version issue, this way it can be moved back.
        b) an issue version of mine in this changeset has no story attached and
           it is a cover sequence. Therefore one cover sequence can be moved
           from the base to the version issue.

        These conditions work for our current only case of a story move: i.e.
        issue versions.
        """
        if self.changeset.change_type == CTYPES['variant_add'] or \
           self.changeset.change_type == CTYPES['two_issues']:
            if self.issue is None:
                if self.story is None:
                    return False
                return True

            if self.deleted:
                return False

            if self.my_issue_revision.other_issue_revision.variant_of \
               is not None:
                # variants can only have one sequence, and it needs to be cover
                if self.changeset.storyrevisions \
                                 .exclude(issue=self.issue).count() \
                        or self.type != StoryType.objects.get(name='Cover'):
                    return False
                else:
                    return True
            return True
        else:
            return False

    def _field_list(self):
        fields = get_story_field_list()
        if self.previous() and (self.previous().issue_id != self.issue_id):
            fields = ['issue'] + fields
        return fields

    def _get_blank_values(self):
        return {
            'title': '',
            'title_inferred': False,
            'first_line': '',
            'feature': '',
            'feature_object': None,
            'feature_logo': None,
            'page_count': None,
            'page_count_uncertain': False,
            'script': '',
            'pencils': '',
            'inks': '',
            'colors': '',
            'letters': '',
            'editing': '',
            'no_script': False,
            'no_pencils': False,
            'no_inks': False,
            'no_colors': False,
            'no_letters': False,
            'no_editing': True,
            'notes': '',
            'keywords': '',
            'synopsis': '',
            'characters': '',
            'reprint_notes': '',
            'genre': '',
            'type': None,
            'job_number': '',
            'sequence_number': None,
            'issue': None,
        }

    def calculate_imps(self):
        imps = super(StoryRevision, self).calculate_imps()
        if hasattr(self, 'biblioentryrevision'):
            imps += self.biblioentryrevision.calculate_imps()
        return imps

    def _start_imp_sum(self):
        self._seen_script = False
        self._seen_pencils = False
        self._seen_inks = False
        self._seen_colors = False
        self._seen_letters = False
        self._seen_editing = False
        self._seen_page_count = False
        self._seen_title = False
        self._seen_feature = False

    def _imps_for(self, field_name):
        if field_name in ('first_line', 'type',
                          'characters', 'synopsis', 'job_number',
                          'reprint_notes', 'notes', 'keywords', 'issue'):
            return 1
        if field_name == 'genre':
            if not self.story:
                return 1
            if self.story.genre.find(';') > 0:
                old_genre = self.story.genre.lower().split("; ")
                old_genre.sort()
                old_genre = "; ".join(old_genre)
            else:
                old_genre = self.story.genre.lower()
            if self.genre.lower() != old_genre:
                return 1
            else:
                return 0

        if not self._seen_feature and field_name in ('feature',
                                                     'feature_object',
                                                     'feature_logo'):
            self._seen_feature = True
            return 1

        if not self._seen_title and field_name in ('title', 'title_inferred'):
            self._seen_title = True
            return 1

        if not self._seen_page_count and \
           field_name in ('page_count', 'page_count_uncertain'):
            self._seen_page_count = True
            if field_name == 'page_count':
                return 1

            # checking the 'uncertain' box  without also at least guessing
            # the page count itself doesn't count as IMP-worthy information.
            if field_name == 'page_count_uncertain' and \
               self.page_count is not None:
                return 1

        for name in ('script', 'pencils', 'inks', 'colors',
                     'letters', 'editing'):
            attr = '_seen_%s' % name
            no_name = 'no_%s' % name
            if not getattr(self, attr) and field_name in (name, no_name):
                setattr(self, attr, True)

                # Just putting in a question mark isn't worth an IMP.
                # Note that the input data is already whitespace-stripped.
                # StoryCredits give also positive is_changed and corresponding
                # IMP here.
                if field_name == name and getattr(self, field_name) == '?':
                    return 0
                return 1
        return 0

    # we need two checks if relevant reprint revisions exist:
    # 1) revisions which are active and link self.story with a story/issue
    #    in the current direction under consideration
    # 2) existing reprints which are locked and which link self.story
    #    with a story/issue in the current direction under consideration
    # if this is the case we return reprintrevisions and not reprint links
    # returned reprint links are three cases:
    # a) revisions in the current changeset which link self.story with a
    #    story/issue in the current direction under consideration
    # b) newly added and active revisions in other changesets
    #    we do not need .exclude(changeset__id=self.changeset_id)\ the new
    #    ones from the current changeset we want anyway
    # c) for the current corresponding reprint links the latest revisions
    #    which are not in the current changeset, the latest can be fetched
    #    via next_revision=None, that way we get either approved or
    #    active ones

    # for newly added stories it is easy, just show reprintrevision which
    # point to the new story in the right ways

    def old_revisions_base(self):
        revs = ReprintRevision.objects \
                              .exclude(changeset__id=self.changeset_id)\
                              .exclude(changeset__state=states.DISCARDED)
        return revs

    def from_reprints_oi(self, preview=False):
        if self.story is None:
            return self.target_reprint_revisions\
                       .filter(changeset__id=self.changeset_id,
                               origin_issue=None)
        from_reprints = self.story.from_reprints.all()
        if self.story.target_reprint_revisions.active_set()\
               .filter(origin_issue=None).count() \
                or RevisionLock.objects.filter(
                  object_id__in=from_reprints.values_list(
                                              'id', flat=True)).exists():
            new_revisions = self.story.target_reprint_revisions\
                                .filter(changeset__id=self.changeset_id)\
                                .filter(origin_issue=None)
            if not preview:
                new_revisions |= \
                    self.story.target_reprint_revisions.active_set()\
                        .filter(in_type=None, origin_issue=None)
            else:
                new_revisions = new_revisions.exclude(deleted=True)
            existing_reprints = from_reprints
            old_revisions = self.old_revisions_base()\
                                .filter(reprint__in=existing_reprints,
                                        next_revision=None)
            return new_revisions | old_revisions
        else:
            return from_reprints

    @property
    def from_reprints(self):
        return self.from_reprints_oi(preview=True)

    def from_issue_reprints_oi(self, preview=False):
        if self.story is None:
            return self.target_reprint_revisions\
                       .filter(changeset__id=self.changeset_id)\
                       .exclude(origin_issue=None)
        from_issue_reprints = self.story.from_issue_reprints.all()
        if self.story.target_reprint_revisions.active_set()\
               .exclude(origin_issue=None).count() \
                or RevisionLock.objects.filter(
                  object_id__in=from_issue_reprints.values_list(
                                                    'id', flat=True)).exists():
            new_revisions = self.story.target_reprint_revisions\
                                .filter(changeset__id=self.changeset_id)\
                                .exclude(origin_issue=None)
            if not preview:
                new_revisions |= \
                    self.story.target_reprint_revisions.active_set()\
                        .filter(in_type=None)\
                        .exclude(origin_issue=None)
            else:
                new_revisions = new_revisions.exclude(deleted=True)
            existing_reprints = from_issue_reprints
            old_revisions = \
                self.old_revisions_base()\
                    .filter(reprint_from_issue__in=existing_reprints,
                            next_revision=None)
            return new_revisions | old_revisions
        else:
            return from_issue_reprints

    @property
    def from_issue_reprints(self):
        return self.from_issue_reprints_oi(preview=True)

    def to_reprints_oi(self, preview=False):
        if self.story is None:
            return self.origin_reprint_revisions\
                       .filter(changeset__id=self.changeset_id,
                               target_issue=None)

        to_reprints = self.story.to_reprints.all()
        if self.story.origin_reprint_revisions.active_set()\
               .filter(target_issue=None).count() \
                or RevisionLock.objects.filter(
                  object_id__in=to_reprints.values_list(
                                            'id', flat=True)).exists():
            new_revisions = self.story.origin_reprint_revisions\
                                .filter(changeset__id=self.changeset_id)\
                                .filter(target_issue=None)
            if not preview:
                new_revisions |= \
                    self.story.origin_reprint_revisions.active_set()\
                        .filter(in_type=None, target_issue=None)
            else:
                new_revisions = new_revisions.exclude(deleted=True)
            existing_reprints = to_reprints
            old_revisions = \
                self.old_revisions_base()\
                    .filter(reprint__in=existing_reprints, next_revision=None)
            return new_revisions | old_revisions
        else:
            return to_reprints

    def to_issue_reprints_oi(self, preview=False):
        if self.story is None:
            return self.origin_reprint_revisions\
                       .filter(changeset__id=self.changeset_id)\
                       .exclude(target_issue=None)
        to_issue_reprints = self.story.to_issue_reprints.all()
        if self.story.origin_reprint_revisions.active_set()\
               .exclude(target_issue=None).count() \
                or RevisionLock.objects.filter(
                  object_id__in=to_issue_reprints.values_list(
                                                  'id', flat=True)).exists():
            new_revisions = \
                self.story.origin_reprint_revisions\
                    .filter(changeset__id=self.changeset_id)\
                    .exclude(target_issue=None)
            if not preview:
                new_revisions |= \
                    self.story.origin_reprint_revisions.active_set()\
                        .filter(in_type=None)\
                        .exclude(target_issue=None)
            else:
                new_revisions = new_revisions.exclude(deleted=True)
            existing_reprints = to_issue_reprints
            old_revisions = \
                self.old_revisions_base()\
                    .filter(reprint_to_issue__in=existing_reprints,
                            next_revision=None)
            return new_revisions | old_revisions
        else:
            return to_issue_reprints

    def has_reprint_revisions(self):
        if self.story is None:
            if self.target_reprint_revisions\
                   .filter(changeset__id=self.changeset_id).count():
                return True
            elif self.origin_reprint_revisions\
                     .filter(changeset__id=self.changeset_id).count():
                return True
            else:
                return False
        if self.story.target_reprint_revisions\
               .filter(changeset__id=self.changeset_id).count():
            return True
        if self.story.origin_reprint_revisions\
               .filter(changeset__id=self.changeset_id).count():
            return True
        # TODO: before there was the reserved=True here in the filter, why ?
        if self.story.to_reprints\
               .filter(revisions__changeset=self.changeset)\
               .count():
            return True
        if self.story.from_reprints\
               .filter(revisions__changeset=self.changeset)\
               .count():
            return True
        if self.story.to_issue_reprints\
               .filter(revisions__changeset=self.changeset)\
               .count():
            return True
        if self.story.from_issue_reprints\
               .filter(revisions__changeset=self.changeset)\
               .count():
            return True
        return False


class PreviewStory(Story):
    class Meta:
        proxy = True

    @classmethod
    def init(cls, story_revision):
        preview_story = PreviewStory()
        story_revision._copy_fields_to(preview_story)
        preview_story.keywords = story_revision.keywords
        preview_story.revision = story_revision
        if story_revision.source:
            preview_story.id = story_revision.source.id
        else:
            preview_story.id = 0
        return preview_story

    @property
    def active_credits(self):
        return self.revision.story_credit_revisions.exclude(deleted=True)

    @property
    def feature_logo(self):
        return self.revision.feature_logo.all()

    def has_credits(self):
        """
        Simplifies UI checks for conditionals.  Credit fields.
        """
        return self.script or \
               self.pencils or \
               self.inks or \
               self.colors or \
               self.letters or \
               self.editing or \
               self.active_credits.exists()

    @property
    def from_reprints(self):
        return self.revision.from_reprints_oi(preview=True)

    @property
    def to_reprints(self):
        return self.revision.to_reprints_oi(preview=True)

    @property
    def from_issue_reprints(self):
        return self.revision.from_issue_reprints_oi(preview=True)

    @property
    def to_issue_reprints(self):
        return self.revision.to_issue_reprints_oi(preview=True)

    def has_keywords(self):
        return self.revision.has_keywords()

    def has_feature(self):
        return self.revision.feature or self.revision.feature_object.count()

    def show_feature(self):
        return self._show_feature(self.revision)

    def show_feature_logo(self):
        return self._show_feature_logo(self.revision)

    @property
    def biblioentry(self):
        if hasattr(self.revision, 'biblioentryrevision'):
            return self.revision.biblioentryrevision
        else:
            return None


class BiblioEntryRevision(StoryRevision):
    class Meta:
        db_table = 'oi_biblio_entry_revision'
        ordering = ['-created', '-id']

    objects = RevisionManager()

    page_began = models.IntegerField(null=True, blank=True)
    page_ended = models.IntegerField(null=True, blank=True)
    abstract = models.TextField(blank=True)
    doi = models.TextField(blank=True)

    source_name = 'biblio_entry'
    source_class = BiblioEntry

    _regular_fields = None

    def previous(self):
        previous = super(StoryRevision, self).previous()
        if previous and hasattr(previous, 'biblioentryrevision'):
            return previous.biblioentryrevision
        else:
            return None

    def _field_list(self):
        fields = ['page_began', 'page_ended', 'abstract', 'doi']
        # TODO after python 3 and OrderedDict, this might work
        # fields += list(self._get_single_value_fields()
        # .viewkeys() -
        # self.storyrevision_ptr._get_single_value_fields().viewkeys())
        return fields

    def _imps_for(self, field_name):
        return 1

    def calculate_imps(self):
        imps = super(StoryRevision, self).calculate_imps()
        return imps

    def _get_blank_values(self):
        return {
            'page_began': None,
            'page_ended': None,
            'abstract': '',
            'doi': '',
        }

    def compare_changes(self):
        if self.type.id != STORY_TYPES['about comics']:
            self.deleted = True

        return super(StoryRevision, self).compare_changes()


class FeatureRevisionManager(RevisionManager):
    def clone_revision(self, feature, changeset):
        return FeatureRevision.clone(feature, changeset)


class FeatureRevision(Revision):
    class Meta:
        db_table = 'oi_feature_revision'
        ordering = ['-created', '-id']

    objects = FeatureRevisionManager()

    feature = models.ForeignKey(Feature, null=True,
                                related_name='revisions')

    name = models.CharField(max_length=255)
    leading_article = models.BooleanField(default=False)
    genre = models.CharField(max_length=255)
    language = models.ForeignKey(Language)
    feature_type = models.ForeignKey(FeatureType)
    year_created = models.IntegerField(db_index=True, blank=True, null=True)
    year_created_uncertain = models.BooleanField(default=False)
    notes = models.TextField(blank=True)
    keywords = models.TextField(blank=True, default='')

    source_name = 'feature'
    source_class = Feature

    @property
    def source(self):
        return self.feature

    @source.setter
    def source(self, value):
        self.feature = value

    def _pre_initial_save(self, fork=False, fork_source=None,
                          exclude=frozenset(), **kwargs):
        self.leading_article = self.feature.name != self.feature.sort_name

    def _post_assign_fields(self, changes):
        if self.leading_article:
            self.feature.sort_name = remove_leading_article(self.name)
        else:
            self.feature.sort_name = self.name

    def get_absolute_url(self):
        if self.feature is None:
            return "/feature/revision/%i/preview" % self.id
        return self.feature.get_absolute_url()

    def __str__(self):
        return '%s' % (self.name)

    ######################################
    # TODO old methods, t.b.c

    _base_field_list = ['name', 'leading_article', 'genre', 'language',
                        'feature_type', 'year_created',
                        'year_created_uncertain', 'notes', 'keywords']

    def _field_list(self):
        return self._base_field_list

    def _get_blank_values(self):
        return {
            'name': '',
            'leading_article': False,
            'genre': '',
            'language': None,
            'feature_type': None,
            'year_created': None,
            'year_created_uncertain': False,
            'notes': '',
            'keywords': '',
        }

    def _start_imp_sum(self):
        self._seen_year_created = False

    def _imps_for(self, field_name):
        if field_name in ('year_created',
                          'year_created_uncertain'):
            if not self._seen_year_created:
                self._seen_year_created = True
                return 1
        elif field_name in self._field_list():
            return 1
        return 0

    def _queue_name(self):
        return '%s (%s)' % (self.name, self.year_created)


class FeatureLogoRevisionManager(RevisionManager):
    def clone_revision(self, feature_logo, changeset):
        return FeatureLogoRevision.clone(feature_logo, changeset)


class FeatureLogoRevision(Revision):
    class Meta:
        db_table = 'oi_feature_logo_revision'
        ordering = ['-created', '-id']

    objects = FeatureLogoRevisionManager()

    feature = models.ManyToManyField(Feature, related_name='logo_revisions')
    feature_logo = models.ForeignKey(FeatureLogo, null=True,
                                     related_name='revisions')

    name = models.CharField(max_length=255)
    leading_article = models.BooleanField(default=False)
    year_began = models.IntegerField(db_index=True, null=True, blank=True)
    year_ended = models.IntegerField(null=True, blank=True)
    year_began_uncertain = models.BooleanField(default=False)
    year_ended_uncertain = models.BooleanField(default=False)
    notes = models.TextField(blank=True)

    source_name = 'feature_logo'
    source_class = FeatureLogo

    @property
    def source(self):
        return self.feature_logo

    @source.setter
    def source(self, value):
        self.feature_logo = value

    def _pre_initial_save(self, fork=False, fork_source=None,
                          exclude=frozenset(), **kwargs):
        self.leading_article = (self.feature_logo.name !=
                                self.feature_logo.sort_name)

    def _post_assign_fields(self, changes):
        if self.leading_article:
            self.feature_logo.sort_name = remove_leading_article(self.name)
        else:
            self.feature_logo.sort_name = self.name

    def get_absolute_url(self):
        if self.feature_logo is None:
            return "/feature_logo/revision/%i/preview" % self.id
        return self.feature_logo.get_absolute_url()

    def __str__(self):
        return '%s' % (self.name)

    ######################################
    # TODO old methods, t.b.c

    _base_field_list = ['name', 'leading_article', 'feature', 'year_began',
                        'year_began_uncertain', 'year_ended',
                        'year_ended_uncertain', 'notes']

    def _field_list(self):
        return self._base_field_list

    def _get_blank_values(self):
        return {
            'feature': None,
            'name': '',
            'leading_article': False,
            'year_began': None,
            'year_ended': None,
            'year_began_uncertain': False,
            'year_ended_uncertain': False,
            'notes': '',
        }

    def _start_imp_sum(self):
        self._seen_year_began = False
        self._seen_year_ended = False

    def _imps_for(self, field_name):
        years_found, value = _imps_for_years(self, field_name,
                                             'year_began', 'year_ended')
        if years_found:
            return value
        elif field_name in self._base_field_list:
            return 1
        return 0

    def _queue_name(self):
        return '%s (%s)' % (self.name, self.year_began)


class FeatureRelationRevisionManager(RevisionManager):
    def clone_revision(self, feature_relation, changeset):
        return FeatureLogoRevision.clone(feature_relation, changeset)


class FeatureRelationRevision(Revision):
    """
    Relations between features.
    """

    class Meta:
        db_table = 'oi_feature_relation_revision'
        ordering = ('to_feature', 'relation_type', 'from_feature')
        verbose_name_plural = 'Feature Relation Revisions'

    objects = FeatureRelationRevisionManager()
    feature_relation = models.ForeignKey('gcd.FeatureRelation',
                                         null=True,
                                         related_name='revisions')

    to_feature = models.ForeignKey('gcd.Feature',
                                   related_name='to_feature_revisions')
    relation_type = models.ForeignKey('gcd.FeatureRelationType',
                                      related_name='revisions')
    from_feature = models.ForeignKey('gcd.Feature',
                                     related_name='from_feature_revisions')
    notes = models.TextField(blank=True)

    _base_field_list = ['from_feature', 'relation_type', 'to_feature', 'notes']

    def _field_list(self):
        field_list = self._base_field_list
        return field_list

    def _get_blank_values(self):
        return {
            'from_feature': None,
            'to_feature': None,
            'relation_type': None,
            'notes': ''
        }

    def _get_source(self):
        return self.feature_relation

    def _get_source_name(self):
        return 'feature_relation'

    def _imps_for(self, field_name):
        return 1

    # TODO general code ?
    def commit_to_display(self):
        feature_relation = self.feature_relation

        if feature_relation is None:
            feature_relation = FeatureRelation()
        elif self.deleted:
            feature_relation.delete()
            return

        feature_relation.to_feature = self.to_feature
        feature_relation.from_feature = self.from_feature
        feature_relation.relation_type = self.relation_type
        feature_relation.notes = self.notes
        feature_relation.save()

        if self.feature_relation is None:
            self.feature_relation = feature_relation
            self.save()

    def __str__(self):
        return '%s >%s< %s' % (str(self.from_feature),
                                str(self.relation_type),
                                str(self.to_feature)
                                )


class ReprintRevisionManager(RevisionManager):

    def clone_revision(self, reprint, changeset):
        """
        Given an existing Reprint instance, create a new revision based on it.

        This new revision will be where the edits are made.
        """
        return RevisionManager.clone_revision(self,
                                              instance=reprint,
                                              instance_class=type(reprint),
                                              changeset=changeset)

    def _do_create_revision(self, reprint, changeset):
        """
        Helper delegate to do the class-specific work of clone_revision.
        """
        if isinstance(reprint, Reprint):
            revision = ReprintRevision(
                # revision-specific fields:
                reprint=reprint,
                in_type=REPRINT_TYPES['story_to_story'],
                # copied fields:
                origin_story=reprint.origin,
                target_story=reprint.target,
            )
        if isinstance(reprint, ReprintFromIssue):
            revision = ReprintRevision(
                # revision-specific fields:
                reprint_from_issue=reprint,
                in_type=REPRINT_TYPES['issue_to_story'],
                # copied fields:
                target_story=reprint.target,
                origin_issue=reprint.origin_issue,
            )
        if isinstance(reprint, ReprintToIssue):
            revision = ReprintRevision(
                # revision-specific fields:
                reprint_to_issue=reprint,
                in_type=REPRINT_TYPES['story_to_issue'],
                # copied fields:
                origin_story=reprint.origin,
                target_issue=reprint.target_issue,
            )
        if isinstance(reprint, IssueReprint):
            revision = ReprintRevision(
                # revision-specific fields:
                issue_reprint=reprint,
                in_type=REPRINT_TYPES['issue_to_issue'],
                # copied fields:
                origin_issue=reprint.origin_issue,
                target_issue=reprint.target_issue,
            )
        revision.changeset = changeset
        revision.notes = reprint.notes
        revision.save()
        return revision


def get_reprint_field_list():
    return ['notes']


class ReprintRevision(Revision):
    """
    One Revision Class for all four types of reprints.

    Otherwise we would have to generate reprint revisions while editing one
    link, e.g. changing an issue_to_story reprint to a story_to_story one, or
    changing reprint direction from issue_to_story to story_to_issue.
    """
    class Meta:
        db_table = 'oi_reprint_revision'
        ordering = ['-created', '-id']
        get_latest_by = "created"

    objects = ReprintRevisionManager()

    reprint = models.ForeignKey(Reprint, null=True,
                                related_name='revisions')
    reprint_from_issue = models.ForeignKey(ReprintFromIssue, null=True,
                                           related_name='revisions')
    reprint_to_issue = models.ForeignKey(ReprintToIssue, null=True,
                                         related_name='revisions')
    issue_reprint = models.ForeignKey(IssueReprint, null=True,
                                      related_name='revisions')

    origin_story = models.ForeignKey(Story, null=True,
                                     related_name='origin_reprint_revisions')
    origin_revision = models.ForeignKey(
        StoryRevision, null=True, related_name='origin_reprint_revisions')

    @property
    def origin(self):
        if self.origin_story:
            return self.origin_story
        elif self.origin_revision:
            return self.origin_revision
        else:
            raise AttributeError

    origin_issue = models.ForeignKey(
        Issue, null=True, related_name='origin_reprint_revisions')

    @property
    def origin_sort(self):
        if self.origin_issue:
            if self.origin_issue.key_date:
                sort = self.origin_issue.key_date
            else:
                sort = '9999-99-99'
            return "%s-%d-%d" % (sort, self.origin_issue.series.year_began,
                                 self.origin_issue.sort_code)
        else:
            if self.origin.issue.key_date:
                sort = self.origin.issue.key_date
            else:
                sort = '9999-99-99'
            return "%s-%d-%d" % (sort, self.origin.issue.series.year_began,
                                 self.origin.issue.sort_code)

    target_story = models.ForeignKey(Story, null=True,
                                     related_name='target_reprint_revisions')
    target_revision = models.ForeignKey(
        StoryRevision, null=True, related_name='target_reprint_revisions')

    @property
    def target(self):
        if self.target_story:
            return self.target_story
        elif self.target_revision:
            return self.target_revision
        else:
            raise AttributeError

    target_issue = models.ForeignKey(Issue, null=True,
                                     related_name='target_reprint_revisions')

    @property
    def target_sort(self):
        if self.target_issue:
            if self.target_issue.key_date:
                sort = self.target_issue.key_date
            else:
                sort = '9999-99-99'
            return "%s-%d-%d" % (sort, self.target_issue.series.year_began,
                                 self.target_issue.sort_code)
        else:
            if self.target.issue.key_date:
                sort = self.target.issue.key_date
            else:
                sort = '9999-99-99'
            return "%s-%d-%d" % (sort, self.target.issue.series.year_began,
                                 self.target.issue.sort_code)

    notes = models.TextField(max_length=255, default='')

    in_type = models.IntegerField(db_index=True, null=True)
    out_type = models.IntegerField(db_index=True, null=True)

    def _get_source(self):
        source = self._get_source_name()
        if source:
            return getattr(self, source)
        else:
            return None

    def _get_source_name(self):
        # is also used to determine which prevision revision to use
        # when reserving a reprint link
        if self.deleted and self.changeset.state == states.APPROVED:
            return None
        if self.out_type is not None:
            reprint_type = self.out_type
        elif self.in_type is not None:
            reprint_type = self.in_type
        else:
            return None
        # reprint link objects can be deleted, so the source may be gone
        # and we need to catch that
        if reprint_type == REPRINT_TYPES['story_to_story'] and \
           self.reprint:
            return "reprint"
        if reprint_type == REPRINT_TYPES['issue_to_story'] and \
           self.reprint_from_issue:
            return "reprint_from_issue"
        if reprint_type == REPRINT_TYPES['story_to_issue'] and \
           self.reprint_to_issue:
            return "reprint_to_issue"
        if reprint_type == REPRINT_TYPES['issue_to_issue'] and \
           self.issue_reprint:
            return "issue_reprint"
        return None

    def _field_list(self):
        return ['origin_story', 'origin_revision', 'origin_issue',
                'target_story', 'target_revision', 'target_issue',
                'notes']

    def _get_blank_values(self):
        return {
            'origin_story': None,
            'origin_revision': None,
            'origin_issue': None,
            'target_story': None,
            'target_revision': None,
            'target_issue': None,
            'notes': '',
        }

    def _start_imp_sum(self):
        self._seen_origin = False
        self._seen_target = False

    def _imps_for(self, field_name):
        """
        All current reprint fields are simple one point fields.
        Only one point for changing origin issue to origin story, etc.
        """
        if field_name in ('origin_story', 'origin_story_revision',
                          'origin_issue'):
            if not self._seen_origin:
                self._seen_origin = True
                return 1
        if field_name in ('target_story', 'target_story_revision',
                          'target_issue'):
            if not self._seen_target:
                self._seen_target = True
                return 1
        if field_name == 'notes':
            return 1
        return 0

    def commit_to_display(self):
        if self.deleted:
            deleted_link = self.source
            field_name = REPRINT_FIELD[self.in_type] + '_id'
            for revision in deleted_link.revisions.all():
                setattr(revision, field_name, None)
                revision.save()
            deleted_link.delete()
            return
        # first figure out which reprint out_type it is, it depends
        # on which fields are set
        if self.origin_story or self.origin_revision:
            if self.origin_revision:
                self.origin_story = self.origin_revision.story
                self.origin_revision = None
            origin = self.origin_story
            if self.target_story or self.target_revision:
                if self.target_revision:
                    self.target_story = self.target_revision.story
                    self.target_revision = None
                out_type = REPRINT_TYPES['story_to_story']
                target = self.target_story
            else:
                out_type = REPRINT_TYPES['story_to_issue']
                # TODO: The following line was present but flake8 notes
                #       that the local variable "target_issue" is unused.
                # target_issue = self.target_issue
        else:  # issue is source
            if self.target_story or self.target_revision:
                if self.target_revision:
                    self.target_story = self.target_revision.story
                    self.target_revision = None
                out_type = REPRINT_TYPES['issue_to_story']
                target = self.target_story
            else:
                out_type = REPRINT_TYPES['issue_to_issue']

        if self.in_type is not None and self.in_type != out_type:
            deleted_link = self.source
            field_name = REPRINT_FIELD[self.in_type]
            for revision in deleted_link.revisions.all():
                setattr(revision, field_name, None)
                revision.save()
            setattr(self, field_name, None)
            deleted_link.delete()
        self.out_type = out_type

        # actual save of the data
        if out_type == REPRINT_TYPES['story_to_story']:
            if self.in_type != out_type:
                self.reprint = Reprint.objects.create(origin=origin,
                                                      target=target,
                                                      notes=self.notes)
            else:
                self.reprint.origin = origin
                self.reprint.target = target
                self.reprint.notes = self.notes
                self.reprint.save()
        elif out_type == REPRINT_TYPES['issue_to_story']:
            if self.in_type != out_type:
                self.reprint_from_issue = ReprintFromIssue.objects.create(
                    origin_issue=self.origin_issue,
                    target=target,
                    notes=self.notes)
            else:
                self.reprint_from_issue.origin_issue = self.origin_issue
                self.reprint_from_issue.target = target
                self.reprint_from_issue.notes = self.notes
                self.reprint_from_issue.save()
        elif out_type == REPRINT_TYPES['story_to_issue']:
            if self.in_type != out_type:
                self.reprint_to_issue = ReprintToIssue.objects.create(
                    origin=origin,
                    target_issue=self.target_issue,
                    notes=self.notes)
            else:
                self.reprint_to_issue.origin = origin
                self.reprint_to_issue.target_issue = self.target_issue
                self.reprint_to_issue.notes = self.notes
                self.reprint_to_issue.save()
        elif out_type == REPRINT_TYPES['issue_to_issue']:
            if self.in_type != out_type:
                self.issue_reprint = IssueReprint.objects.create(
                    origin_issue=self.origin_issue,
                    target_issue=self.target_issue,
                    notes=self.notes)
            else:
                self.issue_reprint.origin_issue = self.origin_issue
                self.issue_reprint.target_issue = self.target_issue
                self.issue_reprint.notes = self.notes
                self.issue_reprint.save()
        self.save()

    def get_compare_string(self, base_issue, do_compare=False):
        from apps.gcd.templatetags.credits import show_title
        moved = False
        if do_compare:
            self.compare_changes()
        if (self.origin_story and self.origin_story.issue == base_issue) \
                or (self.origin_revision and
                    self.origin_revision.issue == base_issue) \
                or self.origin_issue == base_issue:
            direction = 'in'
            if do_compare and self.previous_revision:
                if 'origin_issue' in self.changed and \
                        self.changed['origin_issue']:
                    if self.origin_issue and \
                            self.origin_issue == \
                            self.previous_revision.target_issue:
                        moved = False
                    else:
                        moved = True
                elif 'origin_story' in self.changed and \
                        self.changed['origin_story']:
                    if self.origin_story and \
                            self.origin_story == \
                            self.previous_revision.target_story:
                        moved = False
                    else:
                        moved = True
            if self.target_issue:
                story = None
                issue = self.target_issue
            else:
                if self.target_story:
                    story = self.target_story
                else:
                    story = self.target_revision
        else:
            direction = 'from'
            if do_compare and self.previous_revision:
                if 'target_issue' in self.changed and \
                        self.changed['target_issue']:
                    if self.target_issue and \
                            self.target_issue == \
                            self.previous_revision.origin_issue:
                        moved = False
                    else:
                        moved = True
                elif 'target_story' in self.changed and \
                        self.changed['target_story']:
                    if self.target_story and \
                            self.target_story == \
                            self.previous_revision.origin_story:
                        moved = False
                    else:
                        moved = True
            if self.origin_issue:
                story = None
                issue = self.origin_issue
            else:
                if self.origin_story:
                    story = self.origin_story
                else:
                    story = self.origin_revision
        if story:
            issue = story.issue
            reprint = '%s %s <br><i>sequence</i> ' \
                      '<a target="_blank" href="%s#%d">%s %s</a>' % \
                      (direction, esc(issue.full_name()),
                       issue.get_absolute_url(), story.id, esc(story),
                       show_title(story, True))
        else:
            reprint = '%s <a target="_blank" href="%s">%s</a>' % \
                      (direction, issue.get_absolute_url(),
                       esc(issue.full_name()))
        if self.notes:
            reprint = '%s [%s]' % (reprint, esc(self.notes))
        if moved:
            from apps.gcd.templatetags.display import show_story_short
            if self.previous_revision.target_issue == base_issue or \
               self.previous_revision.origin_issue == base_issue:
                reprint += '<br>reprint link was moved from issue'
            elif self.previous_revision.target_story and \
                    self.previous_revision.target_story.issue == base_issue:
                reprint += \
                    '<br>reprint link was moved from %s]' % \
                    show_story_short(self.previous_revision.target_story)
            else:
                reprint += \
                    '<br>reprint link was moved from %s]' % \
                    show_story_short(self.previous_revision.origin_story)
        return mark_safe(reprint)

    def __str__(self):
        from apps.gcd.templatetags.credits import show_title
        if self.origin_story or self.origin_revision:
            if self.origin_story:
                origin = self.origin_story
            else:
                origin = self.origin_revision
            reprint = '%s %s of %s ' % (
                origin, show_title(origin, True), origin.issue)
        else:
            reprint = '%s ' % (self.origin_issue)
        if self.target_story or self.target_revision:
            if self.target_story:
                target = self.target_story
            else:
                target = self.target_revision
            reprint += 'reprinted in %s %s of %s' % (
                target, show_title(target, True), target.issue)
        else:
            reprint += 'reprinted in %s' % (self.target_issue)
        if self.notes:
            reprint = '%s [%s]' % (reprint, esc(self.notes))
        if self.deleted:
            reprint += ' [DELETED]'
        return mark_safe(reprint)


class ImageRevisionManager(RevisionManager):

    def clone_revision(self, image, changeset):
        """
        Given an existing Image instance, create a new revision based on it.

        This new revision will be where the replacement is stored.
        """
        return RevisionManager.clone_revision(self,
                                              instance=image,
                                              instance_class=Image,
                                              changeset=changeset)

    def _do_create_revision(self, image, changeset, **ignore):
        """
        Helper delegate to do the class-specific work of clone_revision.
        """
        revision = ImageRevision(
            # revision-specific fields:
            image=image,
            changeset=changeset,

            # copied fields:
            content_type=image.content_type,
            object_id=image.object_id,
            type=image.type)

        revision.save()
        return revision


def _clear_image_cache(cached_image):
    cached_image.storage.delete(cached_image)
    cached_image.cachefile_backend.set_state(cached_image,
                                             CacheFileState.DOES_NOT_EXIST)


class ImageRevision(Revision):
    class Meta:
        db_table = 'oi_image_revision'
        ordering = ['created', '-id']

    objects = ImageRevisionManager()

    image = models.ForeignKey(Image, null=True, related_name='revisions')

    content_type = models.ForeignKey(ContentType, null=True)
    object_id = models.PositiveIntegerField(db_index=True, null=True)
    object = GenericForeignKey('content_type', 'object_id')

    type = models.ForeignKey(ImageType)

    image_file = models.ImageField(upload_to='%s/%%m_%%Y' %
                                             settings.NEW_GENERIC_IMAGE_DIR)
    scaled_image = ImageSpecField([ResizeToFit(width=400)],
                                  source='image_file',
                                  format='JPEG', options={'quality': 90})

    marked = models.BooleanField(default=False)
    is_replacement = models.BooleanField(default=False)

    def description(self):
        return '%s for %s' % (self.type.description,
                               str(self.object.full_name()))

    def _get_source(self):
        return self.image

    def _get_source_name(self):
        return 'image'

    def _get_blank_values(self):
        """
        Images don't do field comparisons, so just return an empty
        dictionary so we don't throw an exception if code calls this.
        """
        return {}

    def calculate_imps(self, prev_rev=None):
        return IMP_IMAGE_VALUE

    def _imps_for(self, field_name):
        """
        Images are done purely on a flat point model and don't really have
        fields.  We shouldn't get here, but just in case, return 0 to be safe.
        """
        return 0

    def commit_to_display(self):
        image = self.image
        if self.is_replacement:
            prev_rev = self.previous()
            # copy replaced image back to revision
            prev_rev.image_file.save(str(prev_rev.id) + '.jpg',
                                     content=image.image_file)
            image.image_file.delete()
        elif self.deleted:
            image.delete()
            return
        elif image is None:
            if self.type.unique and not self.is_replacement:
                if Image.objects.filter(
                        content_type=ContentType.objects
                                                .get_for_model(self.object),
                        object_id=self.object.id,
                        type=self.type,
                        deleted=False).count():
                    raise ErrorWithMessage(
                          '%s has an %s. Additional images cannot be uploaded,'
                          ' only replacements are possible.' %
                          (self.object, self.type.description))

            # first generate instance
            image = Image(content_type=self.content_type,
                          object_id=self.object_id,
                          type=self.type,
                          marked=self.marked)
            image.save()

        # then add the uploaded file
        image.image_file.save(str(image.id) + '.jpg', content=self.image_file)
        self.image_file.delete()
        self.image = image
        if self.is_replacement:
            _clear_image_cache(image.scaled_image)
            _clear_image_cache(image.thumbnail)
            _clear_image_cache(image.icon)
        self.save()

    def __str__(self):
        if self.source is None:
            return 'Image for %s' % str(self.object)
        return str(self.source)


class AwardRevisionManager(RevisionManager):
    def clone_revision(self, award, changeset):
        return AwardRevision.clone(award, changeset)


class AwardRevision(Revision):
    """
    record the different comic awards
    """

    class Meta:
        db_table = 'oi_award_revision'
        ordering = ['created', '-id']
        verbose_name_plural = 'Award Revisions'

    objects = AwardRevisionManager()
    award = models.ForeignKey('gcd.Award', null=True, related_name='revisions')
    name = models.CharField(max_length=200)
    notes = models.TextField(blank=True)

    source_name = 'award'
    source_class = Award

    @property
    def source(self):
        return self.award

    @source.setter
    def source(self, value):
        self.award = value

    def get_absolute_url(self):
        if self.award is None:
            return "/award/revision/%i/preview" % self.id
        return self.award.get_absolute_url()

    def __str__(self):
        return self.name

    # #####################################################################
    # Old methods. t.b.c, if deprecated.

    _base_field_list = ['name',
                        'notes',
                        ]

    def _field_list(self):
        return self._base_field_list

    def _get_blank_values(self):
        return {
            'name': '',
            'notes': '',
        }

    def _imps_for(self, field_name):
        if field_name in self._base_field_list:
            return 1
        return 0


class ReceivedAwardRevisionManager(RevisionManager):
    def clone_revision(self, received_award, changeset):
        return ReceivedAwardRevision.clone(received_award, changeset)


class ReceivedAwardRevision(Revision):
    class Meta:
        db_table = 'oi_received_award_revision'
        ordering = ['created', '-id']
        verbose_name_plural = 'Received Award Revisions'

    objects = ReceivedAwardRevisionManager()
    received_award = models.ForeignKey('gcd.ReceivedAward',
                                       null=True,
                                       related_name='revisions')
    content_type = models.ForeignKey(ContentType, null=True, blank=True)
    object_id = models.PositiveIntegerField(null=True, blank=True)
    recipient = GenericForeignKey('content_type', 'object_id')

    award = models.ForeignKey(Award, null=True, blank=True)
    award_name = models.CharField(max_length=255, blank=True)
    no_award_name = models.BooleanField(default=False)
    award_year = models.PositiveSmallIntegerField(null=True, blank=True)
    award_year_uncertain = models.BooleanField(default=False)
    notes = models.TextField(blank=True)

    source_name = 'received_award'
    source_class = ReceivedAward

    @property
    def source(self):
        return self.received_award

    @source.setter
    def source(self, value):
        self.received_award = value

    def _do_complete_added_revision(self, recipient=None, award=None):
        self.recipient = recipient
        self.award = award

    def _create_dependent_revisions(self, delete=False):
        data_sources = self.received_award.data_source.all()
        reserve_data_sources(data_sources, self.changeset, self, delete)

    def get_absolute_url(self):
        if self.received_award is None:
            return "/received_award/revision/%i/preview" % self.id
        return self.received_award.get_absolute_url()

    def __str__(self):
        if self.award:
            name = '%s - %s' % (self.award.name, self.award_name)
        else:
            name = '%s' % (self.award_name)
        if self.award_year:
            return '%s: %s (%d)' % (self.recipient, name, self.award_year)
        else:
            return '%s: %s' % (self.recipient, name)

    # #####################################################################
    # Old methods. t.b.c, if deprecated.

    _base_field_list = ['award',
                        'award_name',
                        'no_award_name',
                        'award_year',
                        'award_year_uncertain',
                        'notes',
                        ]

    def _field_list(self):
        return self._base_field_list

    def _get_blank_values(self):
        return {
            'award': '',
            'award_name': '',
            'no_award_name': False,
            'award_year': None,
            'award_year_uncertain': False,
            'notes': '',
        }

    def _start_imp_sum(self):
        self._seen_year = False
        self._seen_award_name = False

    def _imps_for(self, field_name):
        if field_name in ('award_year',
                          'award_year_uncertain'):
            if not self._seen_year:
                self._seen_year = True
                return 1
        elif field_name in ('award_name',
                            'no_award_name'):
            if not self._seen_award_name:
                self._seen_award_name = True
                return 1
        elif field_name in self._base_field_list:
            return 1
        return 0


class PreviewReceivedAward(ReceivedAward):
    class Meta:
        proxy = True

    @property
    def data_source(self):
        return DataSourceRevision.objects.filter(
          revision_id=self.revision.id,
          content_type=ContentType.objects.get_for_model(self.revision))


class DataSourceRevisionManager(RevisionManager):
    def clone_revision(self, data_source, changeset, sourced_revision):
        """
        Given an existing DataSource instance, create a new revision
        based on it.

        This new revision will be where the replacement is stored.
        """
        return RevisionManager.clone_revision(
                self,
                instance=data_source,
                instance_class=DataSource,
                changeset=changeset,
                sourced_revision=sourced_revision)

    def _do_create_revision(self, data_source, changeset,
                            sourced_revision, **ignore):
        """
        Helper delegate to do the class-specific work of c  lone_revision.
        """
        revision = DataSourceRevision(
                # revision-specific fields:
                data_source=data_source,
                changeset=changeset,
                # copied fields:
                sourced_revision=sourced_revision,
                source_description=data_source.source_description,
                source_type=data_source.source_type,
                field=data_source.field
        )

        revision.save()
        return revision


class DataSourceRevision(Revision):
    """
    Indicates the various sources of data
    """

    class Meta:
        db_table = 'oi_data_source_revision'
        ordering = ['created', '-id']
        verbose_name_plural = 'Data Source Revisions'

    objects = DataSourceRevisionManager()
    content_type = models.ForeignKey(ContentType, null=True)
    revision_id = models.IntegerField(db_index=True, null=True)
    sourced_revision = GenericForeignKey('content_type', 'revision_id')

    data_source = models.ForeignKey('gcd.DataSource',
                                    related_name='revisions',
                                    null=True)
    source_type = models.ForeignKey('gcd.SourceType')
    source_description = models.TextField()
    field = models.CharField(max_length=256)

    def _get_blank_values(self):
        return {
            'data_source': None,
            'source_type': None,
            'source_description': '',
            'field': '',
        }

    def _get_source(self):
        return self.data_source

    def _get_source_name(self):
        return 'data_source'

    def _field_list(self):
        field_list = ['source_description', 'source_type']
        return field_list

    def _imps_for(self, field_name):
        return 1

    def commit_to_display(self):
        # TODO add delete (and other stuff ?)
        data_source = self.data_source

        if data_source is None:
            data_source = DataSource(field=self.field)
        data_source.source_type = self.source_type
        data_source.source_description = self.source_description
        data_source.save()

        if self.data_source is None:
            source_object = self.sourced_revision.source
            source_object.data_source.add(data_source)
            self.data_source = data_source
            self.save()

    def __str__(self):
        return '%s - %s' % (
            str(self.field), str(self.source_type.type))


def process_data_source(creator_form, field_name, changeset=None,
                        revision=None, sourced_revision=None):
    data_source = creator_form.cleaned_data.get('%s_source_type' % field_name)
    data_source_description = creator_form.cleaned_data.get(
                                          '%s_source_description' % field_name)

    if revision:
        # existing revision, only update data
        revision.source_type = data_source
        revision.source_description = data_source_description
        revision.save()
    elif data_source or data_source_description:
        # new revision, create and set meta data
        revision = DataSourceRevision.objects.create(
                                source_type=data_source,
                                source_description=data_source_description,
                                changeset=changeset,
                                sourced_revision=sourced_revision,
                                field=field_name)


def reserve_data_sources(data_sources, changeset, sourced_revision,
                         delete=False):
    for data_source in data_sources:
        data_source_lock = _get_revision_lock(data_source,
                                              changeset=changeset)
        if data_source_lock is None:
            raise IntegrityError("needed DataSource lock not possible")
        data_source = DataSourceRevision.objects.clone_revision(
          data_source, changeset=changeset, sourced_revision=sourced_revision)
        if delete:
            data_source.deleted = True
            data_source.save()


def _get_creator_sourced_fields():
    return {'birth_place': 'birth_city_uncertain',
            'death_place': 'death_city_uncertain',
            'bio': 'bio'}


def get_creator_field_list():
    return ['birth_date', 'birth_country', 'birth_country_uncertain',
            'birth_province', 'birth_province_uncertain',
            'birth_city', 'birth_city_uncertain',
            'death_date', 'death_country', 'death_country_uncertain',
            'death_province', 'death_province_uncertain',
            'death_city', 'death_city_uncertain',
            'whos_who', 'bio', 'notes'
            ]


class CreatorRevisionManager(RevisionManager):
    def clone_revision(self, creator, changeset):
        return CreatorRevision.clone(creator, changeset)


class CreatorRevision(Revision):
    class Meta:
        db_table = 'oi_creator_revision'
        ordering = ['created', '-id']

    objects = CreatorRevisionManager()

    creator = models.ForeignKey('gcd.Creator',
                                null=True,
                                related_name='revisions')

    gcd_official_name = models.CharField(max_length=255, db_index=True)

    # TODO change from null=True
    birth_date = models.ForeignKey(Date, related_name='+', null=True,
                                   blank=True)
    death_date = models.ForeignKey(Date, related_name='+', null=True,
                                   blank=True)

    birth_country = models.ForeignKey('stddata.Country',
                                      related_name='cr_birth_country',
                                      null=True, blank=True)
    birth_country_uncertain = models.BooleanField(default=False)
    birth_province = models.CharField(max_length=50, blank=True)
    birth_province_uncertain = models.BooleanField(default=False)
    birth_city = models.CharField(max_length=200, blank=True)
    birth_city_uncertain = models.BooleanField(default=False)

    death_country = models.ForeignKey('stddata.Country',
                                      related_name='cr_death_country',
                                      null=True, blank=True)
    death_country_uncertain = models.BooleanField(default=False)
    death_province = models.CharField(max_length=50, blank=True)
    death_province_uncertain = models.BooleanField(default=False)
    death_city = models.CharField(max_length=200, blank=True)
    death_city_uncertain = models.BooleanField(default=False)

    whos_who = models.URLField(blank=True, default='')
    bio = models.TextField(blank=True, default='')

    notes = models.TextField(blank=True, default='')

    source_name = 'creator'
    source_class = Creator

    @property
    def source(self):
        return self.creator

    @source.setter
    def source(self, value):
        self.creator = value

    def _pre_initial_save(self, fork=False, fork_source=None,
                          exclude=frozenset(), **kwargs):
        # clone date instances
        birth_date = self.creator.birth_date
        birth_date.pk = None
        birth_date.save()
        self.birth_date = birth_date

        death_date = self.creator.death_date
        death_date.pk = None
        death_date.save()
        self.death_date = death_date

    def _create_dependent_revisions(self, delete=False):
        name_details = self.creator.active_names()
        for name_detail in name_details:
            name_lock = _get_revision_lock(name_detail,
                                           changeset=self.changeset)
            if name_lock is None:
                raise IntegrityError("needed Name lock not possible")
            creator_name = CreatorNameDetailRevision.objects\
                           .clone_revision(name_detail, self.changeset,
                                           self)  # noqa: E127
            creator_name.save_added_revision(
                changeset=self.changeset, creator_revision=self)

            if delete:
                creator_name.deleted = True
                creator_name.save()

        data_sources = self.creator.data_source.all()
        reserve_data_sources(data_sources, self.changeset, self, delete)

        if delete:
            for creator_art_influence in self.creator.active_art_influences():
                influence_lock = _get_revision_lock(creator_art_influence,
                                                    changeset=self.changeset)
                if influence_lock is None:
                    raise IntegrityError("needed CreatorArtInfluence lock not"
                                         " possible")
                creator_art_influence_revision = \
                    CreatorArtInfluenceRevision.clone(creator_art_influence,
                                                      self.changeset)
                creator_art_influence_revision.deleted = True
                creator_art_influence_revision.save()

            for received_award in self.creator.active_awards():
                award_lock = _get_revision_lock(received_award,
                                                changeset=self.changeset)
                if award_lock is None:
                    raise IntegrityError("needed ReceivedAward lock not "
                                         "possible")
                received_award_revision = \
                    ReceivedAwardRevision.clone(received_award,
                                                self.changeset)
                received_award_revision.deleted = True
                received_award_revision.save()

            for creator_degree in self.creator.active_degrees():
                degree_lock = _get_revision_lock(creator_degree,
                                                 changeset=self.changeset)
                if degree_lock is None:
                    raise IntegrityError("needed CreatorDegree lock not "
                                         "possible")
                creator_degree_revision = \
                    CreatorDegreeRevision.clone(creator_degree,
                                                self.changeset)
                creator_degree_revision.deleted = True
                creator_degree_revision.save()

            for creator_membership in self.creator.active_memberships():
                membership_lock = _get_revision_lock(creator_membership,
                                                     changeset=self.changeset)
                if membership_lock is None:
                    raise IntegrityError("needed CreatorMembership lock not "
                                         "possible")
                creator_membership_revision = \
                    CreatorMembershipRevision.clone(creator_membership,
                                                    self.changeset)
                creator_membership_revision.deleted = True
                creator_membership_revision.save()

            for creator_non_comic_work in \
                    self.creator.active_non_comic_works():
                noncomicwork_lock = _get_revision_lock(
                  creator_non_comic_work, changeset=self.changeset)
                if noncomicwork_lock is None:
                    raise IntegrityError("needed CreatorNonComicWork lock not"
                                         " possible")
                creator_non_comic_work_revision = \
                    CreatorNonComicWorkRevision.clone(creator_non_comic_work,
                                                      self.changeset)
                creator_non_comic_work_revision.deleted = True
                creator_non_comic_work_revision.save()

            for creator_school in self.creator.active_schools():
                school_lock = _get_revision_lock(creator_school,
                                                 changeset=self.changeset)
                if school_lock is None:
                    raise IntegrityError("needed CreatorSchool lock not "
                                         "possible")
                creator_school_revision = \
                    CreatorSchoolRevision.clone(creator_school,
                                                self.changeset)
                creator_school_revision.deleted = True
                creator_school_revision.save()

    def extra_forms(self, request):
        from apps.oi.forms.creator import CreatorRevisionFormSet
        from apps.oi.forms.support import CREATOR_HELP_LINKS
        from apps.oi.forms import get_date_revision_form

        creator_names_formset = CreatorRevisionFormSet(
          request.POST or None, instance=self,
          queryset=self.cr_creator_names.filter(deleted=False))
        form_class = get_date_revision_form(self,
                                            user=request.user,
                                            date_help_links=CREATOR_HELP_LINKS)
        birth_date_form = form_class(request.POST or None,
                                     prefix='birth_date',
                                     instance=self.birth_date)
        death_date_form = form_class(request.POST or None,
                                     prefix='death_date',
                                     instance=self.death_date)
        birth_date_form.fields['date'].label = 'Birth date'
        death_date_form.fields['date'].label = 'Death date'

        return {'creator_names_formset': creator_names_formset,
                'birth_date_form': birth_date_form,
                'death_date_form': death_date_form
                }

    def process_extra_forms(self, request, extra_forms):
        creator_names_formset = extra_forms['creator_names_formset']
        for creator_name_form in creator_names_formset:
            if creator_name_form.is_valid() and creator_name_form.cleaned_data:
                cd = creator_name_form.cleaned_data
                if 'id' in cd and cd['id']:
                    creator_revision = creator_name_form.save()
                else:
                    creator_revision = creator_name_form.save(commit=False)
                    creator_revision.save_added_revision(
                      changeset=self.changeset, creator_revision=self)
                if cd['is_official_name']:
                    self.gcd_official_name = cd['name']
            elif (
              not creator_name_form.is_valid() and
              creator_name_form not in creator_names_formset.deleted_forms
            ):
                raise ValueError

        removed_names = creator_names_formset.deleted_forms
        for removed_name in removed_names:
            if removed_name.cleaned_data['id']:
                if removed_name.cleaned_data['id'].creator_name_detail:
                    removed_name.cleaned_data['id'].deleted = True
                    removed_name.cleaned_data['id'].save()
                else:
                    removed_name.cleaned_data['id'].delete()

        birth_date_form = extra_forms['birth_date_form']
        death_date_form = extra_forms['death_date_form']
        self.birth_date = birth_date_form.save()
        self.death_date = death_date_form.save()
        self.save()
        # TODO support more than one revision
        data_source_revision = self.changeset\
            .datasourcerevisions.filter(field='birth_date')
        if data_source_revision:
            data_source_revision = data_source_revision[0]
        process_data_source(birth_date_form, 'birth_date', self.changeset,
                            revision=data_source_revision,
                            sourced_revision=self)
        data_source_revision = self.changeset\
            .datasourcerevisions.filter(field='death_date')
        if data_source_revision:
            data_source_revision = data_source_revision[0]
        process_data_source(death_date_form, 'death_date', self.changeset,
                            revision=data_source_revision,
                            sourced_revision=self)

    def _pre_save_object(self, changes):
        name = self.changeset.creatornamedetailrevisions.get(
                                                         is_official_name=True)
        self.creator.sort_name = name.sort_name

        if self.added:
            # clone date instances
            birth_date = self.birth_date
            birth_date.pk = None
            birth_date.save()
            self.creator.birth_date = birth_date

            death_date = self.death_date
            death_date.pk = None
            death_date.save()
            self.creator.death_date = death_date
        else:
            ctr = self.creator
            ctr.birth_date.set(year=self.birth_date.year,
                               month=self.birth_date.month,
                               day=self.birth_date.day,
                               year_uncertain=self.birth_date.year_uncertain,
                               month_uncertain=self.birth_date.month_uncertain,
                               day_uncertain=self.birth_date.day_uncertain,
                               empty=True)
            ctr.birth_date.save()
            ctr.death_date.set(year=self.death_date.year,
                               month=self.death_date.month,
                               day=self.death_date.day,
                               year_uncertain=self.death_date.year_uncertain,
                               month_uncertain=self.death_date.month_uncertain,
                               day_uncertain=self.death_date.day_uncertain,
                               empty=True)
            ctr.death_date.save()

    def _handle_dependents(self, changes):
        # for new creator, we need to save the record_id in the name revisions
        if self.added:
            for name in self.changeset.creatornamedetailrevisions.all():
                name.creator = self.creator
                name.save()

    def get_absolute_url(self):
        if self.creator is None:
            return "/creator/revision/%i/preview" % self.id
        return self.creator.get_absolute_url()

    def __str__(self):
        return '%s' % str(self.gcd_official_name)

    # #####################################################################
    # Old methods. t.b.c, if deprecated.

    def _field_list(self):
        return get_creator_field_list()

    def _get_blank_values(self):
        return {
            'gcd_official_name': '',
            'cr_creator_names': '',
            'birth_date': '',
            'death_date': '',
            'whos_who': '',
            'birth_country': None,
            'birth_country_uncertain': False,
            'birth_province': '',
            'birth_province_uncertain': False,
            'birth_city': '',
            'birth_city_uncertain': False,
            'death_country': None,
            'death_country_uncertain': False,
            'death_province': '',
            'death_province_uncertain': False,
            'death_city': '',
            'death_city_uncertain': False,
            'bio': '',
            'notes': '',
        }

    def _start_imp_sum(self):
        self._seen_birth_country = False
        self._seen_birth_province = False
        self._seen_birth_city = False
        self._seen_death_country = False
        self._seen_death_province = False
        self._seen_death_city = False

    def _imps_for(self, field_name):
        if field_name in ('birth_country',
                          'birth_country_uncertain'):
            if not self._seen_birth_country:
                self._seen_birth_country = True
                return 1
        elif field_name in ('birth_province',
                            'birth_province_uncertain'):
            if not self._seen_birth_province:
                self._seen_birth_province = True
                return 1
        elif field_name in ('birth_city',
                            'birth_city_uncertain'):
            if not self._seen_birth_city:
                self._seen_birth_city = True
                return 1
        elif field_name in ('death_country',
                            'death_country_uncertain'):
            if not self._seen_death_country:
                self._seen_death_country = True
                return 1
        elif field_name in ('death_province',
                            'death_province_uncertain'):
            if not self._seen_death_province:
                self._seen_death_province = True
                return 1
        elif field_name in ('death_city',
                            'death_city_uncertain'):
            if not self._seen_death_city:
                self._seen_death_city = True
                return 1
        elif field_name in self._field_list():
            return 1
        return 0


class PreviewCreator(Creator):
    class Meta:
        proxy = True

    def active_names(self):
        return self.revision.changeset.creatornamedetailrevisions\
                                      .filter(deleted=False)

    @property
    def data_source(self):
        return DataSourceRevision.objects.filter(
          revision_id=self.revision.id,
          content_type=ContentType.objects.get_for_model(self.revision))


class CreatorRelationRevisionManager(RevisionManager):
    def clone_revision(self, creator_relation, changeset):
        """
        Given an existing CreatorRelation instance, create a new revision based
        on it.

        This new revision will be where the replacement is stored.
        """
        return RevisionManager.clone_revision(self,
                                              instance=creator_relation,
                                              instance_class=CreatorRelation,
                                              changeset=changeset,
                                              )

    def _do_create_revision(self, creator_relation, changeset, **ignore):
        """
        Helper delegate to do the class-specific work of clone_revision.
        """
        revision = CreatorRelationRevision(
            # revision-specific fields:
            creator_relation=creator_relation,
            changeset=changeset,
            # copied fields:
            to_creator=creator_relation.to_creator,
            from_creator=creator_relation.from_creator,
            relation_type=creator_relation.relation_type,
            notes=creator_relation.notes
        )
        revision.save()
        if creator_relation.creator_name.count():
            revision.creator_name.add(*list(creator_relation.
                                            creator_name.all().
                                            values_list('id', flat=True)))
        return revision


class CreatorRelationRevision(Revision):
    """
    Relations between creators to relate any GCD Official name to any other
    name.
    """

    class Meta:
        db_table = 'oi_creator_relation_revision'
        ordering = ('to_creator', 'relation_type', 'from_creator')
        verbose_name_plural = 'Creator Relation Revisions'

    objects = CreatorRelationRevisionManager()
    creator_relation = models.ForeignKey('gcd.CreatorRelation',
                                         null=True,
                                         related_name='revisions')

    to_creator = models.ForeignKey('gcd.Creator',
                                   related_name='to_creator_revisions')
    relation_type = models.ForeignKey('gcd.RelationType',
                                      related_name='revisions')
    from_creator = models.ForeignKey('gcd.Creator',
                                     related_name='from_creator_revisions')
    creator_name = models.ManyToManyField(
                          'gcd.CreatorNameDetail', blank=True,
                          related_name='creator_relation_revisions')
    notes = models.TextField(blank=True)

    _base_field_list = ['from_creator', 'relation_type', 'to_creator',
                        'creator_name', 'notes']

    def _field_list(self):
        field_list = self._base_field_list
        return field_list

    def _get_blank_values(self):
        return {
            'from_creator': None,
            'to_creator': None,
            'relation_type': None,
            'creator_name': None,
            'notes': ''
        }

    def _get_source(self):
        return self.creator_relation

    def _get_source_name(self):
        return 'creator_relation'

    def _imps_for(self, field_name):
        return 1

    def _create_dependent_revisions(self, delete=False):
        data_sources = self.creator_relation.data_source.all()
        reserve_data_sources(data_sources, self.changeset, self, delete)

    def commit_to_display(self):
        creator_relation = self.creator_relation

        if creator_relation is None:
            creator_relation = CreatorRelation()
        elif self.deleted:
            creator_relation.delete()
            return

        creator_relation.to_creator = self.to_creator
        creator_relation.from_creator = self.from_creator
        creator_relation.relation_type = self.relation_type
        creator_relation.notes = self.notes
        creator_relation.save()
        creator_relation.creator_name.clear()
        if self.creator_name.count():
            creator_relation.creator_name.add(*list(self.creator_name.all().
                                                    values_list('id',
                                                                flat=True)))

        if self.creator_relation is None:
            self.creator_relation = creator_relation
            self.save()

    def __str__(self):
        return '%s >%s< %s' % (str(self.from_creator),
                                str(self.relation_type),
                                str(self.to_creator)
                                )


class CreatorNameDetailRevisionManager(RevisionManager):
    def clone_revision(self, creator_name_detail, changeset, creator_revision):
        return CreatorNameDetailRevision.clone(creator_name_detail, changeset)


class CreatorNameDetailRevision(Revision):
    """
    record of the creator's name
    """

    class Meta:
        db_table = 'oi_creator_name_detail_revision'
        ordering = ['-is_official_name', 'type__id', 'created', '-id']
        verbose_name_plural = 'Creator Name Detail Revisions'

    objects = CreatorNameDetailRevisionManager()
    creator_name_detail = models.ForeignKey('gcd.CreatorNameDetail',
                                            null=True,
                                            related_name='revisions')
    creator_revision = models.ForeignKey(CreatorRevision,
                                         related_name='cr_creator_names',
                                         null=True)
    creator = models.ForeignKey(Creator, related_name='name_revisions',
                                null=True)
    name = models.CharField(max_length=255, db_index=True)
    sort_name = models.CharField(max_length=255, default='', blank=True)
    is_official_name = models.BooleanField(default=False)
    given_name = models.CharField(max_length=255, db_index=True, default='',
                                  blank=True)
    family_name = models.CharField(max_length=255, db_index=True, default='',
                                   blank=True)
    type = models.ForeignKey('gcd.NameType',
                             related_name='revision_name_details',
                             null=True)
    in_script = models.ForeignKey(Script, default=Script.LATIN_PK)

    source_name = 'creator_name_detail'
    source_class = CreatorNameDetail

    @property
    def source(self):
        return self.creator_name_detail

    @source.setter
    def source(self, value):
        self.creator_name_detail = value

    def _do_complete_added_revision(self, creator_revision):
        self.creator_revision = creator_revision

    def _post_create_for_add(self, changes):
        self.creator = self.creator_revision.creator

    def __str__(self):
        return '%s - %s (%s)' % (
            str(self.creator), str(self.name), str(self.type.type))

    # #####################################################################
    # Old methods. t.b.c, if deprecated.

    def _field_list(self):
        field_list = ['name', 'sort_name', 'is_official_name', 'given_name',
                      'family_name', 'type', 'in_script']
        return field_list

    def _get_blank_values(self):
        return {
            'name': '',
            'sort_name': '',
            'given_name': '',
            'family_name': '',
            'is_official_name': False,
            'type': None,
            'in_script': ''
        }

    def _imps_for(self, field_name):
        if field_name == 'sort_name':
            if self.sort_name == self.name:
                return 0
            else:
                return 1
        if field_name in self._field_list():
            return 1
        return 0


class CreatorSchoolRevisionManager(RevisionManager):
    def clone_revision(self, creator_school, changeset):
        return CreatorSchoolRevision.clone(creator_school, changeset)


class CreatorSchoolRevision(Revision):
    """
    record the schools creators attended
    """

    class Meta:
        db_table = 'oi_creator_school_revision'
        ordering = ['created', '-id']
        verbose_name_plural = 'Creator School Revisions'

    objects = CreatorSchoolRevisionManager()
    creator_school = models.ForeignKey('gcd.CreatorSchool',
                                       null=True,
                                       related_name='revisions')
    creator = models.ForeignKey('gcd.Creator',
                                related_name='school_revisions')
    school = models.ForeignKey('gcd.School',
                               related_name='cr_schools')
    school_year_began = models.PositiveSmallIntegerField(null=True, blank=True)
    school_year_began_uncertain = models.BooleanField(default=False)
    school_year_ended = models.PositiveSmallIntegerField(null=True, blank=True)
    school_year_ended_uncertain = models.BooleanField(default=False)
    notes = models.TextField(blank=True)

    source_name = 'creator_school'
    source_class = CreatorSchool

    @property
    def source(self):
        return self.creator_school

    @source.setter
    def source(self, value):
        self.creator_school = value

    def _do_complete_added_revision(self, creator):
        self.creator = creator

    def _create_dependent_revisions(self, delete=False):
        data_sources = self.creator_school.data_source.all()
        reserve_data_sources(data_sources, self.changeset, self, delete)

    def get_absolute_url(self):
        if self.creator_school is None:
            return "/creator_school/revision/%i/preview" % self.id
        return self.creator_school.get_absolute_url()

    def __str__(self):
        return '%s - %s' % (
            str(self.creator), str(self.school.school_name))

    # #####################################################################
    # Old methods. t.b.c, if deprecated.

    _base_field_list = ['school',
                        'school_year_began', 'school_year_began_uncertain',
                        'school_year_ended', 'school_year_ended_uncertain',
                        'notes']

    def _field_list(self):
        return self._base_field_list

    def _get_blank_values(self):
        return {
            'school': None,
            'school_year_began': None,
            'school_year_began_uncertain': False,
            'school_year_ended': None,
            'school_year_ended_uncertain': False,
            'notes': ''
        }

    def _start_imp_sum(self):
        self._seen_year_began = False
        self._seen_year_ended = False

    def _imps_for(self, field_name):
        if field_name in ('school_year_began',
                          'school_year_began_uncertain'):
            if not self._seen_year_began:
                self._seen_year_began = True
                return 1
        elif field_name in ('school_year_ended',
                            'school_year_ended_uncertain'):
            if not self._seen_year_ended:
                self._seen_year_ended = True
                return 1
        elif field_name in self._base_field_list:
            return 1
        return 0


class PreviewCreatorSchool(CreatorSchool):
    class Meta:
        proxy = True

    @property
    def data_source(self):
        return DataSourceRevision.objects.filter(
          revision_id=self.revision.id,
          content_type=ContentType.objects.get_for_model(self.revision))


class CreatorDegreeRevisionManager(RevisionManager):
    def clone_revision(self, creator_degree, changeset):
        return CreatorDegreeRevision.clone(creator_degree, changeset)


class CreatorDegreeRevision(Revision):
    """
    record the degrees creators received
    """

    class Meta:
        db_table = 'oi_creator_degree_revision'
        ordering = ['created', '-id']
        verbose_name_plural = 'Creator Degree Revisions'

    objects = CreatorDegreeRevisionManager()
    creator_degree = models.ForeignKey('gcd.CreatorDegree',
                                       null=True,
                                       related_name='revisions')
    creator = models.ForeignKey('gcd.Creator',
                                related_name='degree_revisions')
    school = models.ForeignKey('gcd.School',
                               related_name='creator_degrees',
                               null=True)
    degree = models.ForeignKey('gcd.Degree',
                               related_name='creator_degrees')
    degree_year = models.PositiveSmallIntegerField(null=True, blank=True)
    degree_year_uncertain = models.BooleanField(default=False)
    notes = models.TextField(blank=True)

    source_name = 'creator_degree'
    source_class = CreatorDegree

    @property
    def source(self):
        return self.creator_degree

    @source.setter
    def source(self, value):
        self.creator_degree = value

    def _do_complete_added_revision(self, creator):
        self.creator = creator

    def _create_dependent_revisions(self, delete=False):
        data_sources = self.creator_degree.data_source.all()
        reserve_data_sources(data_sources, self.changeset, self, delete)

    def get_absolute_url(self):
        if self.creator_degree is None:
            return "/creator_degree/revision/%i/preview" % self.id
        return self.creator_degree.get_absolute_url()

    def __str__(self):
        return '%s - %s' % (
            str(self.creator), str(self.degree.degree_name))

    # #####################################################################
    # Old methods. t.b.c, if deprecated.

    _base_field_list = ['school', 'degree',
                        'degree_year', 'degree_year_uncertain', 'notes']

    def _field_list(self):
        return self._base_field_list

    def _get_blank_values(self):
        return {
            'school': None,
            'degree': None,
            'degree_year': None,
            'degree_year_uncertain': False,
            'notes': ''
        }

    def _start_imp_sum(self):
        self._seen_year = False

    def _imps_for(self, field_name):
        if field_name in ('degree_year',
                          'degree_year_uncertain'):
            if not self._seen_year:
                self._seen_year = True
                return 1
        elif field_name in self._base_field_list:
            return 1
        return 0


class PreviewCreatorDegree(CreatorDegree):
    class Meta:
        proxy = True

    @property
    def data_source(self):
        return DataSourceRevision.objects.filter(
          revision_id=self.revision.id,
          content_type=ContentType.objects.get_for_model(self.revision))


class CreatorMembershipRevisionManager(RevisionManager):
    def clone_revision(self, creator_membership, changeset):
        return CreatorMembershipRevision.clone(creator_membership, changeset)


class CreatorMembershipRevision(Revision):
    """
    record the membership of creator
    """

    class Meta:
        db_table = 'oi_creator_membership_revision'
        ordering = ['created', '-id']
        verbose_name_plural = 'Creator Membership Revisions'

    objects = CreatorMembershipRevisionManager()
    creator_membership = models.ForeignKey('gcd.CreatorMembership',
                                           null=True,
                                           related_name='revisions')
    creator = models.ForeignKey('gcd.Creator',
                                related_name='membership_revisions')
    organization_name = models.CharField(max_length=200)
    membership_type = models.ForeignKey('gcd.MembershipType',
                                        related_name='cr_membershiptype',
                                        null=True,
                                        blank=True)
    membership_year_began = models.PositiveSmallIntegerField(null=True,
                                                             blank=True)
    membership_year_began_uncertain = models.BooleanField(default=False)
    membership_year_ended = models.PositiveSmallIntegerField(null=True,
                                                             blank=True)
    membership_year_ended_uncertain = models.BooleanField(default=False)
    notes = models.TextField(blank=True)

    source_name = 'creator_membership'
    source_class = CreatorMembership

    @property
    def source(self):
        return self.creator_membership

    @source.setter
    def source(self, value):
        self.creator_membership = value

    def _do_complete_added_revision(self, creator):
        self.creator = creator

    def _create_dependent_revisions(self, delete=False):
        data_sources = self.creator_membership.data_source.all()
        reserve_data_sources(data_sources, self.changeset, self, delete)

    def get_absolute_url(self):
        if self.creator_membership is None:
            return "/creator_membership/revision/%i/preview" % self.id
        return self.creator_membership.get_absolute_url()

    def __str__(self):
        return '%s: %s' % (self.creator, str(self.organization_name))

    # #####################################################################
    # Old methods. t.b.c, if deprecated.

    _base_field_list = ['organization_name',
                        'membership_type',
                        'membership_year_began',
                        'membership_year_began_uncertain',
                        'membership_year_ended',
                        'membership_year_ended_uncertain',
                        'notes',
                        ]

    def _field_list(self):
        return self._base_field_list

    def _get_blank_values(self):
        return {
            'organization_name': '',
            'membership_type': None,
            'membership_year_began': None,
            'membership_year_began_uncertain': False,
            'membership_year_ended': None,
            'membership_year_ended_uncertain': False,
            'notes': '',
        }

    def _start_imp_sum(self):
        self._seen_year_began = False
        self._seen_year_ended = False

    def _imps_for(self, field_name):
        if field_name in ('membership_year_began',
                          'membership_year_began_uncertain'):
            if not self._seen_year_began:
                self._seen_year_began = True
                return 1
        elif field_name in ('membership_year_ended',
                            'membership_year_ended_uncertain'):
            if not self._seen_year_ended:
                self._seen_year_ended = True
                return 1
        elif field_name in self._base_field_list:
            return 1
        return 0


class PreviewCreatorMembership(CreatorMembership):
    class Meta:
        proxy = True

    @property
    def data_source(self):
        return DataSourceRevision.objects.filter(
          revision_id=self.revision.id,
          content_type=ContentType.objects.get_for_model(self.revision))


class CreatorArtInfluenceRevisionManager(RevisionManager):
    def clone_revision(self, creator_art_influence, changeset):
        return CreatorArtInfluenceRevision.clone(creator_art_influence,
                                                 changeset)


class CreatorArtInfluenceRevision(Revision):
    """
    record the art influences of creator
    """

    class Meta:
        db_table = 'oi_creator_art_influence_revision'
        ordering = ['created', '-id']
        verbose_name_plural = 'Creator Art Influence Revisions'

    objects = CreatorArtInfluenceRevisionManager()
    creator_art_influence = models.ForeignKey('gcd.CreatorArtInfluence',
                                              null=True,
                                              related_name='revisions')
    creator = models.ForeignKey('gcd.Creator',
                                related_name='art_influence_revisions')
    influence_name = models.CharField(max_length=200, blank=True)
    influence_link = models.ForeignKey('gcd.Creator',
                                       null=True,
                                       blank=True,
                                       related_name='influenced_revisions')
    notes = models.TextField(blank=True)

    source_name = 'creator_art_influence'
    source_class = CreatorArtInfluence

    @property
    def source(self):
        return self.creator_art_influence

    @source.setter
    def source(self, value):
        self.creator_art_influence = value

    def _do_complete_added_revision(self, creator):
        self.creator = creator

    def _create_dependent_revisions(self, delete=False):
        data_sources = self.creator_art_influence.data_source.all()
        reserve_data_sources(data_sources, self.changeset, self, delete)

    def get_absolute_url(self):
        if self.creator_art_influence is None:
            return "/creator_art_influence/revision/%i/preview" % self.id
        return self.creator_art_influence.get_absolute_url()

    def __str__(self):
        if self.influence_name:
            influence = self.influence_name
        else:
            influence = self.influence_link

        return '%s: %s' % (self.creator, influence)

    # #####################################################################
    # Old methods. t.b.c, if deprecated.

    _base_field_list = ['influence_name',
                        'influence_link',
                        'notes',
                        ]

    def _field_list(self):
        return self._base_field_list

    def _get_blank_values(self):
        return {
            'influence_name': '',
            'influence_link': None,
            'notes': '',
        }

    def _imps_for(self, field_name):
        if field_name in self._base_field_list:
            return 1
        return 0


class PreviewCreatorArtInfluence(CreatorArtInfluence):
    class Meta:
        proxy = True

    @property
    def data_source(self):
        return DataSourceRevision.objects.filter(
          revision_id=self.revision.id,
          content_type=ContentType.objects.get_for_model(self.revision))


class MultiURLValidator(URLValidator):
    def __call__(self, value):
        for url in value.split('\n'):
            try:
                super(URLValidator, self).__call__(url.strip())
            except ValidationError as e:
                if e.message != 'Enter a valid URL.':
                    raise
                else:
                    raise ValidationError('Enter one or more valid URLs, '
                                          'one per line.')


class CreatorNonComicWorkRevisionManager(RevisionManager):
    def clone_revision(self, creator_non_comic_work, changeset):
        return CreatorNonComicWorkRevision.clone(creator_non_comic_work,
                                                 changeset)


class CreatorNonComicWorkRevision(Revision):
    """
    record the non comic work of creator
    """

    class Meta:
        db_table = 'oi_creator_non_comic_work_revision'
        ordering = ['created', '-id']
        verbose_name_plural = 'Creator NonComicWork Revisions'

    objects = CreatorNonComicWorkRevisionManager()
    creator_non_comic_work = models.ForeignKey('gcd.CreatorNonComicWork',
                                               null=True,
                                               related_name='revisions')
    creator = models.ForeignKey('gcd.Creator',
                                related_name='non_comic_work_revisions')
    work_type = models.ForeignKey('gcd.NonComicWorkType',
                                  null=True,
                                  blank=True,
                                  related_name='cr_worktype')
    publication_title = models.CharField(max_length=200)
    employer_name = models.CharField(max_length=200, blank=True)
    work_title = models.CharField(max_length=255, blank=True)
    work_role = models.ForeignKey('gcd.NonComicWorkRole',
                                  null=True,
                                  blank=True,
                                  related_name='cr_workrole')
    work_years = models.TextField(blank=True)
    work_urls = models.TextField(blank=True, validators=[MultiURLValidator()])
    notes = models.TextField(blank=True)

    source_name = 'creator_non_comic_work'
    source_class = CreatorNonComicWork

    @property
    def source(self):
        return self.creator_non_comic_work

    @source.setter
    def source(self, value):
        self.creator_non_comic_work = value

    def _pre_initial_save(self, fork=False, fork_source=None,
                          exclude=frozenset(), **kwargs):
        self.work_years = self.creator_non_comic_work.display_years()

    def _do_complete_added_revision(self, creator):
        self.creator = creator

    def _create_dependent_revisions(self, delete=False):
        data_sources = self.creator_non_comic_work.data_source.all()
        reserve_data_sources(data_sources, self.changeset, self, delete)

    def _save_work_years(self, ncw, year, year_uncertain):
        ncw_year, created = NonComicWorkYear.objects\
          .get_or_create(non_comic_work=ncw, work_year=year)
        ncw_year.work_year_uncertain = year_uncertain
        ncw_year.save()
        if not created:
            self.existing_years.remove(ncw_year.id)

    def _post_save_object(self, changes):
        if self.work_years:
            ncw = self.creator_non_comic_work
            self.existing_years = list(NonComicWorkYear.objects
                                       .filter(non_comic_work=ncw)
                                       .values_list('id', flat=True))
            for year in self.work_years.split(';'):
                range_split = year.split('-')
                if len(range_split) == 2:
                    year_began = _check_year(range_split[0])
                    year_end = _check_year(range_split[1])
                    if year_began > year_end:
                        raise ValueError

                    self._save_work_years(ncw, year_began,
                                          '?' in range_split[0])
                    self._save_work_years(ncw, year_end,
                                          '?' in range_split[1])

                    if '?' in range_split[1] and '?' in range_split[0]:
                        years_uncertain = True
                    else:
                        years_uncertain = False
                    for i in range(year_began + 1, year_end):
                        self._save_work_years(ncw, i, years_uncertain)
                else:
                    year_number = _check_year(year)
                    self._save_work_years(ncw, year_number, '?' in year)

            # remove years which are not present in value anymore
            for i in self.existing_years:
                ncw_year = NonComicWorkYear.objects.get(id=i)
                ncw_year.delete()

    def get_absolute_url(self):
        if self.creator_non_comic_work is None:
            return "/creator_non_comic_work/revision/%i/preview" % self.id
        return self.creator_non_comic_work.get_absolute_url()

    def __str__(self):
        return '%s: %s' % (str(self.creator),
                            str(self.publication_title))

    # #####################################################################
    # Old methods. t.b.c, if deprecated.

    _base_field_list = ['work_type',
                        'publication_title',
                        'employer_name',
                        'work_title',
                        'work_role',
                        'work_years',
                        'work_urls',
                        'notes',
                        ]

    def _field_list(self):
        return self._base_field_list

    def _get_blank_values(self):
        return {
            'work_type': '',
            'publication_title': '',
            'employer_name': '',
            'work_title': '',
            'work_role': '',
            'work_years': '',
            'work_urls': '',
            'notes': '',
        }

    def _imps_for(self, field_name):
        if field_name in self._base_field_list:
            return 1
        return 0


class PreviewCreatorNonComicWork(CreatorNonComicWork):
    class Meta:
        proxy = True

    def display_years(self):
        return self.revision.work_years

    @property
    def data_source(self):
        return DataSourceRevision.objects.filter(
          revision_id=self.revision.id,
          content_type=ContentType.objects.get_for_model(self.revision))
