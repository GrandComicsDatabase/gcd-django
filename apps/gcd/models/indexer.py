# -*- coding: utf-8 -*-
from django.db import models
from django.contrib.auth.models import User

from apps.gcd.models import Country, Language

#TODO: Should not be importing from OI.  Reconsider app split.
from apps.oi import states

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
        )

    class Admin:
        pass

    user = models.OneToOneField(User)

    country = models.ForeignKey(Country, related_name='indexers')
    languages = models.ManyToManyField(Language, related_name='indexers',
                                       db_table='gcd_indexer_languages')
    interests = models.TextField(null=True, blank=True)

    max_reservations = models.IntegerField(default=1)
    max_ongoing = models.IntegerField(default=0)

    mentor = models.ForeignKey(User, related_name='mentees', null=True)
    is_new = models.BooleanField(db_index=True)
    is_banned = models.BooleanField(db_index=True)
    deceased = models.BooleanField(db_index=True)

    registration_key = models.CharField(max_length=40, null=True,
                                        editable=False)
    registration_expires = models.DateField(null=True)

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

