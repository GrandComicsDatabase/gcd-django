# -*- coding: utf-8 -*-
from django.contrib.auth.models import User, Group
from apps.gcd.models.indexer import Indexer
from django.db import connection
from _mysql_exceptions import OperationalError, IntegrityError

def pre_convert_users():
    # some cleanup of the indexer table
    a = Indexer.objects.filter(username='blank')
    for i in a:
        i.delete()
    
    # double usernames
    a = Indexer.objects.filter(username='DOCV')
    if a.count() > 1:
        use = a.exclude(eMail=None)[0]
        not_use = a.filter(eMail=None)[0]
        indexed_series = not_use.index_credit_set.all()
        for i in indexed_series:
            i.indexer_id = use.id
            i.save()
        not_use.delete()
    a=Indexer.objects.filter(username='TLMJV').filter(active=0)
    if a.count() > 0:
        b=a[0]
        b.username='TLMJV_2'
        b.save()

    # empty username
    a=Indexer.objects.filter(id=462)[0]
    if a.username=='':
        a.username='TLAJM_EMPTY'
        a.active=0
        a.save()

    # delete some (=one currently) indexers
    a=Indexer.objects.filter(name__contains='DELETE')
    for i in a:
        i.delete()

    # are some more, fix in db later
    a=Indexer.objects.filter(country_code = 'USA')
    for i in a:
        i.country_code = 'us'
        i.save()
    a=Indexer.objects.filter(country_code__startswith  = 'MEX')
    for i in a:
        i.country_code = 'mx'
        i.save()
    a=Indexer.objects.filter(country_code__contains ='SWEDEN')
    for i in a:
        i.country_code = 'se'
        i.save()
    a=Indexer.objects.filter(country_code__contains ='POLAND')
    for i in a:
        i.country_code = 'pl'
        i.save()
    a=Indexer.objects.filter(country_code__startswith ='AUS')
    for i in a:
        i.country_code = 'au'
        i.save()
    a=Indexer.objects.filter(country_code__startswith ='CAN')
    for i in a:
        i.country_code = 'ca'
        i.save()
    a=Indexer.objects.filter(country_code__startswith ='CHILE')
    for i in a:
        i.country_code = 'cl'
        i.save()
    a=Indexer.objects.filter(country_code ='ARGENTINA')
    for i in a:
        i.country_code = 'ar'
        i.save()

    # create the additional column for the indexer table to
    # link to the django user table
    cursor = connection.cursor()
    cursor.execute("ALTER TABLE Indexers ADD COLUMN User int(11) default NULL;")

    # create our groups
    # we will later set permissions for the groups
    group = Group.objects.create()
    group.name = 'editor'
    group.save()

    group = Group.objects.create()
    group.name = 'indexer'
    group.save()

    group = Group.objects.create()
    group.name = 'admin'
    group.save()

def convert_users():
    """ converts Indexer data from comics.org into django auth table"""
    
    editor_group = Group.objects.filter(name='editor')[0]
    indexer_group = Group.objects.filter(name='indexer')[0]
    admin_group = Group.objects.filter(name='admin')[0]

    # do the conversion
    users = Indexer.objects.all()
    for user in users:
        # if we don't have an email set inactive
        if user.email == None:
            new_user = User.objects.create_user(user.username, '',
                                                user.password)
            user.active = 0
            user.save()
        else:
            new_user = User.objects.create_user(user.username, user.email,
                                                user.password)
        if user.first_name:
            new_user.first_name = user.first_name
        # grmbl, django hast limit on names, no longer than 30
        if user.last_name:
            new_user.last_name = user.last_name[:30]
        # all inactive old_users get no working pwd
        # in django inactive keep password, i.e. set active -> use old pwd
        if user.active == 0:
            new_user.is_active = False
            new_user.set_unusable_password()
        # setting groups
        if user.access_level >= 1:
            new_user.groups.add(indexer_group)
        if user.access_level >= 2:
            new_user.groups.add(editor_group)
        if user.access_level >= 3:
            new_user.groups.add(admin_group)
        new_user.save()
        user.user = new_user
        user.save()

# after the conversion we can delete some fields in the indexer table
# due to the length limit on the names we need to decide if we use django
# names or ours