# -*- coding: utf-8 -*-
from django.db import models
from django.contrib.auth.models import User

from apps.gcd.models import Country, Language

class Indexer(models.Model):
    """ indexer from gcd database"""

    class Meta:
        db_table = 'Indexers'
        app_label = 'gcd'
        ordering = ['user__last_name', 'user__first_name']
        permissions = (
            ('can_mentor', 'Can mentor new indexers'),
        )

    class Admin:
        pass

    id = models.AutoField(primary_key=True, db_column='ID')

    user = models.OneToOneField(User)

    country = models.ForeignKey(Country, related_name='indexers')
    languages = models.ManyToManyField(Language, related_name='indexers')
    interests = models.TextField(null=True, blank=True)

    max_reservations = models.IntegerField()
    max_ongoing = models.IntegerField()

    mentor = models.ForeignKey(User, related_name='mentees', null=True)
    is_new = models.BooleanField()
    is_banned = models.BooleanField()
    deceased = models.BooleanField()

    registration_key = models.CharField(max_length=40, null=True,
                                        editable=False)
    registration_expires = models.DateField(null=True)

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

