# -*- coding: utf-8 -*-
from django.db import models
from django.contrib.auth.models import User


class Indexer(models.Model):
    """ indexer from gcd database"""

    class Meta:
        db_table = 'Indexers'
        app_label = 'gcd'
        ordering = ['name']

    class Admin:
        pass

    id = models.AutoField(primary_key=True, db_column='ID')

    user = models.OneToOneField(User)

    username = models.CharField(max_length=255)

    first_name = models.CharField(max_length=255, db_column='FirstName',
                                  null=True)
    last_name = models.CharField(max_length = 255, db_column='LastName',
                                 null=True)
    name = models.CharField(max_length=255, db_column='Name', null=True)

    password = models.CharField(max_length=255)
    
    access_level = models.IntegerField(db_column = 'userlevel')
    
    email = models.CharField(db_column = 'eMail', max_length=255)
    
    active = models.IntegerField(db_column = 'Active')
    # This is not quite the country code from other fields, but is clearly
    # supposed to use two-letter codes even though not all entries do.
    country_code = models.CharField(max_length=255, db_column='Country',
                                    null=True, blank=True)

    def __unicode__(self):
        if self.name is not None:
            return self.name
        elif self.first_name is not None and self.last_name is not None:
            return u'%s %s' % (self.first_name, self.last_name)
        elif self.first_name is not None:
            return self.first_name
        elif self.last_name is not None:
            return self.last_name
        return self.username

