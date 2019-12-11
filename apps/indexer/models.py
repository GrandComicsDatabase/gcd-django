# -*- coding: utf-8 -*-


from django.conf import settings
from django.db import models
from django.contrib.auth.models import User, Group
from django.core.mail import EmailMessage
from django.template.loader import get_template

from apps.stddata.models import Country, Language

# TODO: Should not be importing from OI.  Reconsider app split.
from apps.oi import states

IMPS_FOR_APPROVAL = 3


class Indexer(models.Model):
    """
    Indexer table that was originally the main accounts table in the GCD DB.
    Now serves as the profile table in the Django-based implementation.
    """
    class Meta:
        ordering = ['user__last_name', 'user__first_name']
        permissions = (
            ('can_upload_cover', 'Can upload covers'),
            ('can_reserve', 'Can reserve a record for add, edit or delete'),
            ('can_approve', 'Can approve a change to a record'),
            ('can_cancel', 'Can cancel a pending change they did not open'),
            ('can_mentor', 'Can mentor new indexers'),
            ('can_vote', 'Can vote in GCD elections'),
            ('can_publish',
             'Can publish non-database content on the web site'),
            ('can_contact', 'Can see list of users who have opted-in'),
            ('on_board', 'Is on the Board of Directors'),
        )

    user = models.OneToOneField(User)

    country = models.ForeignKey(Country, related_name='indexers')
    languages = models.ManyToManyField(Language, related_name='indexers',
                                       db_table='gcd_indexer_languages')
    interests = models.TextField(null=True, blank=True)
    opt_in_email = models.BooleanField(default=False, db_index=True)
    from_where = models.TextField(blank=True)
    seen_privacy_policy = models.BooleanField(default=False, db_index=True)

    max_reservations = models.IntegerField(default=1)
    max_ongoing = models.IntegerField(default=0)

    mentor = models.ForeignKey(User, related_name='mentees', null=True,
                               blank=True)
    is_new = models.BooleanField(default=False, db_index=True)
    is_banned = models.BooleanField(default=False, db_index=True)
    deceased = models.BooleanField(default=False, db_index=True)

    registration_key = models.CharField(max_length=40, null=True,
                                        db_index=True, editable=False)
    registration_expires = models.DateField(null=True, blank=True,
                                            db_index=True)

    imps = models.IntegerField(default=0)
    # display options
    issue_detail = models.IntegerField(default=1)
    # editing options
    notify_on_approve = models.BooleanField(db_index=True, default=True)
    collapse_compare_view = models.BooleanField(db_index=True, default=False)
    show_wiki_links = models.BooleanField(db_index=True, default=True)

    def can_reserve_another(self):
        from apps.oi.models import CTYPES

        if self.is_new:
            if (self.user.changesets.filter(state__in=states.ACTIVE)
               .exclude(change_type=CTYPES['cover']).count() >=
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
        old_imps = self.imps
        self.imps = models.F('imps') + value
        self.save()
        if (old_imps < settings.MEMBERSHIP_IMPS and
           Indexer.objects.get(pk=self.pk).imps >= settings.MEMBERSHIP_IMPS):
            self.user.groups.add(Group.objects.get(name='member'))
            self.send_member_email()

    def send_member_email(self):
        email = EmailMessage(from_email=settings.EMAIL_CHAIRMAN,
                             to=[self.user.email],
                             subject='GCD full member',
                             body=get_template('indexer/new_member_mail.html')
                             .render({'site_name': settings.SITE_NAME,
                                      'chairman': settings.CHAIRMAN}
                                     ),
                             cc=[settings.EMAIL_CHAIRMAN])
        email.send(fail_silently=(not settings.BETA))

    def get_absolute_url(self):
        return self.user.get_absolute_url()

    def __str__(self):
        if self.user.first_name and self.user.last_name:
            full_name = '%s %s' % (self.user.first_name, self.user.last_name)
        elif self.user.first_name:
            full_name = self.user.first_name
        else:
            full_name = self.user.last_name
        if self.deceased:
            full_name = full_name + ' (R.I.P.)'

        return full_name


class ImpGrant(models.Model):
    class Meta:
        db_table = 'indexer_imp_grant'

    indexer = models.ForeignKey(Indexer, related_name='imp_grant_set')
    imps = models.IntegerField()
    grant_type = models.CharField(max_length=50)
    notes = models.TextField()


class Error(models.Model):
    """
    Store errors from gcd database.
    """
    class Admin:
        pass

    error_key = models.CharField(primary_key=True, max_length=40,
                                 editable=False)
    error_text = models.TextField(null=True, blank=True)

    is_safe = models.BooleanField(default=False)

    def __str__(self):
        return self.error_text
