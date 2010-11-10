# -*- coding: utf-8 -*-
from django.db import models, settings
from django.contrib.auth.models import User, Group

from apps.gcd.models import Country, Language

#TODO: Should not be importing from OI.  Reconsider app split.
from apps.oi import states

IMPS_FOR_APPROVAL = 3

class Indexer(models.Model):
    """
    Indexer table that was originally the main accounts table in the GCD DB.
    Now serves as the profile table in the Django-based implementation.
    """
    class Meta:
        app_label = 'gcd'
        ordering = ['user__last_name', 'user__first_name']
        permissions = (
            ('can_upload_cover', 'Can upload covers'),
            ('can_reserve', 'Can reserve a record for add, edit or delete'),
            ('can_approve', 'Can approve a change to a record'),
            ('can_cancel', 'Can cancel a pending change they did not open'),
            ('can_mentor', 'Can mentor new indexers'),
            ('can_vote', 'Can vote in GCD elections'),
            ('can_publish', 'Can publish non-database content on the web site'),
            ('on_board', 'Is on the Board of Directors'),
        )

    user = models.OneToOneField(User)

    country = models.ForeignKey(Country, related_name='indexers')
    languages = models.ManyToManyField(Language, related_name='indexers',
                                       db_table='gcd_indexer_languages')
    interests = models.TextField(null=True, blank=True)

    max_reservations = models.IntegerField(default=1)
    max_ongoing = models.IntegerField(default=0)

    mentor = models.ForeignKey(User, related_name='mentees', null=True, blank=True)
    is_new = models.BooleanField(db_index=True)
    is_banned = models.BooleanField(db_index=True)
    deceased = models.BooleanField(db_index=True)

    registration_key = models.CharField(max_length=40, null=True,
                                        editable=False)
    registration_expires = models.DateField(null=True, blank=True)

    imps = models.IntegerField(default=0)
    notify_on_approve = models.BooleanField(db_index=True, default=False)
    collapse_compare_view = models.BooleanField(db_index=True, default=False)

    def can_reserve_another(self):
        if self.is_new:
            if (self.user.changesets.filter(state__in=states.ACTIVE).count() >=
                self.max_reservations):
                return False 
        elif (self.user.changesets.filter(state=states.OPEN).count() >=
              self.max_reservations):
            return False 
        return True

    def can_reserve_another_ongoing(self):
        return self.user.ongoing_reservations.count() < self.max_ongoing

    def calculate_imps(self):
        """
        Re-calculate indexing imps from scratch.
        Normally, we let the OI add imps as things are approved, but this
        is useful for migrations.
        As with the method on the Changeset object, does *NOT* save object.
        """
        imps = 0
        for c in self.user.changesets.filter(state=states.APPROVED):
            imps += c.total_imps()
        imps += (IMPS_FOR_APPROVAL *
                 self.user.approved_changesets.all(
                   state__in=(states.APPROVED, states.DISCARDED)).count())
        self.imps = imps

    def total_imps(self):
        """
        Add up all types of imps and return the full number.
        """
        total_imps = self.imps

        # For now just walk the grants table.  If this gets expensive, we'll
        # want to cache the grants in a column on the gcd_indexer table.
        # TODO: Look up how to do the sum in the database.
        for grant in self.imp_grant_set.all():
            total_imps += grant.imps
        return total_imps

    def add_imps(self, value):
        self.imps += value
        if self.imps >= settings.MEMBERSHIP_IMPS and \
          self.imps - value < settings.MEMBERSHIP_IMPS:
            self.user.groups.add(Group.objects.get(name='member'))
        self.save()

    def get_absolute_url(self):
        return self.user.get_absolute_url()

    def __unicode__(self):
        if self.user.first_name and self.user.last_name:
            full_name = u'%s %s' % (self.user.first_name, self.user.last_name)
        elif self.user.first_name:
            full_name = self.user.first_name
        else:   
            full_name = self.user.last_name
        if self.deceased:
            full_name = full_name + u' (R.I.P.)'

        return full_name

class ImpGrant(models.Model):
    class Meta:
        db_table = 'gcd_imp_grant'
        app_label = 'gcd'

    indexer = models.ForeignKey(Indexer, related_name='imp_grant_set')
    imps = models.IntegerField()
    grant_type = models.CharField(max_length=50)
    notes = models.TextField()

