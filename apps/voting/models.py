import hashlib
from random import random
from datetime import datetime

from django.conf import settings
from django.db import models
from django.db.models import Q, Count
from django.core import urlresolvers
from django.core.mail import send_mail, send_mass_mail
from django.contrib.auth.models import User, Group, Permission

TYPE_PASS_FAIL = 'Pass / Fail'
TYPE_CHARTER = 'Charter Amendment'

EMAIL_OPEN_BALLOT = """
The topic '%s' with text:

  %s

is now open for voting at:

%s

%s

The deadline is %s.
"""

EMAIL_TOKEN_STRING = """
You will need to enter the following token exactly as shown in order to vote:

%s

Please do not share this token with anyone who did not receive the email.
Voters who can be shown to not have been eligible to receive the token will
have their votes invalidated.
"""

EMAIL_ADD_AGENDA_ITEM = """
A new item has been added to the %s Agenda, but is not yet
open for discussion.  Please go to

%s

for details.
"""

EMAIL_OPEN_AGENDA_ITEM_GENERIC = """
A new item on the %s Agenda is now open for discussion:

%s

Please see

%s

for details.
"""

EMAIL_OPEN_AGENDA_ITEM = """
The following item on the %s Agenda is now open for discussion:

%s

%s
"""

class MailingList(models.Model):
    class Meta:
        db_table = 'voting_mailing_list'
    address = models.EmailField()
    def __unicode__(self):
        return self.address

class Agenda(models.Model):
    name = models.CharField(max_length=255)
    permission = models.ForeignKey(Permission,
      limit_choices_to={'codename__in': ('can_vote', 'on_board')})

    uses_tokens = models.BooleanField(default=False)
    allows_abstentions = models.BooleanField(default=False)
    quorum = models.IntegerField(blank=True, default=1,
      help_text='Quorum must always be at least 1')
    secret_ballot = models.BooleanField(default=False)

    subscribers = models.ManyToManyField(User, related_name='subscribed_agendas',
                                               editable=False)

    def get_absolute_url(self):
        return urlresolvers.reverse('agenda', kwargs={'id': self.id})

    def __unicode__(self):
        return self.name

class AgendaItem(models.Model):
    class Meta:
        db_table = 'voting_agenda_item'
    name = models.CharField(max_length=255)
    agenda = models.ForeignKey(Agenda, related_name='items')
    notes = models.TextField(null=True, blank=True)
    owner = models.ForeignKey(User, null=True, blank=True,
                                    related_name='agenda_items')

    # NULL=pending, 1=open, 0=closed
    # See also the open, pending and closed properties.
    state = models.NullBooleanField(choices=((None, 'Pending'),
                                             (True, 'Open'),
                                             (False, 'Closed')))
    created = models.DateTimeField(auto_now_add=True, db_index=True, editable=False)
    updated = models.DateTimeField(null=True, auto_now=True, editable=False)

    subscribers = models.ManyToManyField(User, related_name='subscribed_items',
                                               editable=False)
    @property
    def open(self):
        return self.state is True

    @property
    def pending(self):
        return self.state is None

    @property
    def closed(self):
        return self.state is False

    def __unicode__(self):
        return self.name

def agenda_item_pre_save(sender, **kwargs):
    if kwargs['raw'] != True:
        item = kwargs['instance']

        newly_added = not item.id
        if newly_added and item.open:
            newly_opened = True
        elif item.open:
            old_item = AgendaItem.objects.get(id=item.id)
            newly_opened = not old_item.open
        else:
            newly_opened = False

        # Send mail about the agenda item.
        if item.notes:
            notes = item.notes
        else:
            notes = ''

        for list_config in item.agenda.agenda_mailing_lists.all():
            if list_config.on_agenda_item_open and newly_opened:
                if list_config.is_primary:
                    subject = "Open: %s" % item.name
                    message = EMAIL_OPEN_AGENDA_ITEM % (item.agenda, item.name,
                                                        notes)
                else:
                    subject="New %s item open" % item.agenda
                    message = EMAIL_OPEN_AGENDA_ITEM_GENERIC % \
                            (item.agenda, item.name,
                             settings.SITE_URL.rstrip('/') +
                             item.agenda.get_absolute_url())
                list_config.send_mail(subject=subject, message=message)

            elif list_config.on_agenda_item_add and newly_added:
                list_config.send_mail(
                subject="New %s item added" % item.agenda,
                message=EMAIL_ADD_AGENDA_ITEM % (item.agenda,
                    settings.SITE_URL.rstrip('/') + item.agenda.get_absolute_url()))

models.signals.pre_save.connect(agenda_item_pre_save, sender=AgendaItem)

class AgendaMailingList(models.Model):
    class Meta:
        db_table = 'voting_agenda_mailing_list'
    agenda = models.ForeignKey(Agenda, related_name='agenda_mailing_lists')
    mailing_list = models.ForeignKey(MailingList, null=True, blank=True,
                                     related_name='agenda_mailing_lists')
    group = models.ForeignKey(Group, null=True, blank=True)
    on_agenda_item_add = models.BooleanField(default=False)
    on_agenda_item_open = models.BooleanField(default=False)
    on_vote_open = models.BooleanField(default=False)
    on_vote_close = models.BooleanField(default=False)
    is_primary = models.BooleanField(default=False)
    reminder = models.BooleanField(default=False)
    display_token = models.BooleanField(default=False)

    def send_mail(self, subject, message):
        if self.mailing_list is not None:
            send_mail(from_email=settings.EMAIL_VOTING_FROM,
                      recipient_list=(self.mailing_list.address,),
                      subject=subject,
                      message=message,
                      fail_silently=(not settings.BETA))

        if self.group is not None:
            recipients = self.group.user_set.filter(is_active=True,
                                                    indexer__is_banned=False,
                                                    indexer__deceased=False) \
                                            .exclude(email='') \
                                            .select_related('indexer')
            mass = [ (subject, message, settings.EMAIL_VOTING_FROM, (r.email,))
                     for r in recipients ]
            send_mass_mail(mass, fail_silently=(not settings.BETA))

class VoteTypeManager(models.Manager):
    def get_by_natural_key(self, name):
        return self.get(name=name)

class VoteType(models.Model):
    """
    Determines how to count the votes.
    """
    class Meta:
        db_table = 'voting_vote_type'

    objects = VoteTypeManager()

    name = models.CharField(max_length=255)
    max_votes = models.IntegerField(default=1, null=True, blank=True,
      help_text='Having more votes than winners sets up ranked choice voting.  '
                'Leave max votes blank to allow as many ranks as options.')
    max_winners = models.IntegerField(default=1,
      help_text='Having more than one winner allows votes to be cast for up to '
                'that many options.')

    def natural_key(self):
        return (self.name,)

    def __unicode__(self):
        return self.name

class Topic(models.Model):
    class Meta:
        ordering = ('created',)

    name = models.CharField(max_length=255)
    text = models.TextField(null=True, blank=True)
    agenda_items = models.ManyToManyField(AgendaItem, related_name='topics',
      limit_choices_to={'state': True})
    agenda = models.ForeignKey(Agenda, related_name='topics')
    vote_type = models.ForeignKey(VoteType, related_name='topics',
      help_text='Pass / Fail types will automatically create their own Options '
                'if none are specified directly.  For other types, add Options '
                'below.')
    author = models.ForeignKey(User, related_name='topics')
    second = models.ForeignKey(User, null=True, blank=True,
                                     related_name='seconded_topics')

    open = models.BooleanField(default=False)
    created = models.DateTimeField(auto_now_add=True, db_index=True, editable=False)
    deadline = models.DateTimeField(db_index=True)

    token = models.CharField(max_length=255, null=True, editable=False)

    result_calculated = models.BooleanField(default=False, editable=False,
                                            db_index=True)
    invalid = models.BooleanField(default=False, editable=False)

    subscribers = models.ManyToManyField(User, related_name='subscribed_topics',
                                               editable=False)

    @property
    def pending(self):
        return not self.open

    def get_absolute_url(self):
        """
        Note that the primary page for a topic is known as the ballot page.
        """
        return urlresolvers.reverse('ballot', kwargs={'id': self.id})

    def counted_options(self):
        """
        Return the options with their vote counts.
        """
        return \
          self.options.annotate(num_votes=Count('votes')).order_by('-num_votes')

    def results(self):
        """
        Filters for options that have been marked as results (meaning the
        option(s) that "won" the vote) specifically as counted_options
        so that they are sorted and carry the annotations we'll use to
        display them in the UI.
        """
        return self.counted_options().filter(result=True)

    def num_voters(self):
        """
        Returns the number of distinct voters who voted on the topic.
        Primarily used to determine if a quorum has been reached.
        """
        if self.agenda.secret_ballot:
            # We only use one receipt per ballot even if there are multiple
            # votes for that ballot.
            return Receipt.objects.filter(topic=self).count()
        return User.objects.filter(votes__option__topic=self).distinct().count()

    def expected_voters(self):
        expected_voters = self.agenda.expected_voters\
                              .filter(Q(tenure_began__lte=self.deadline) &
                                      (Q(tenure_ended__isnull=True) |
                                       Q(tenure_ended__gte=self.deadline)))\
                              .order_by('tenure_began', 'tenure_ended',
                                        'voter__last_name',
                                        'voter__first_name')\
                              .select_related('voter')
        return expected_voters

    def absent_voters(self):
        """
        If there is a pre-set list of expected voters for this agenda, displays the
        voters who did not vote.  Returns an empty list if the voter pool
        is flexible.  Primarily intended for Board votes.
        """
        expected_for_topic = self.expected_voters()
        if expected_for_topic.count() == 0:
            return []
        voters = User.objects.filter(votes__option__topic=self).distinct()
        return expected_for_topic.exclude(voter__in=voters.values_list('id',
                                                                       flat=True))

    def has_vote_from(self, user):
        votes = self.options.filter(votes__voter=user)
        receipts = self.receipts.filter(voter=user)
        return votes.count() > 0 or receipts.count() > 0

    def __unicode__(self):
        return self.name

def topic_pre_save(sender, **kwargs):
    """
    Callback to initialize the token and/or create standard options if needed.
    Note that this function must be defined outside of any class.
    """
    if kwargs['raw'] != True:
        topic = kwargs['instance']
        if topic.agenda.uses_tokens and topic.token is None:
            salt = hashlib.sha1(str(random())).hexdigest()[:5]
            topic.token = hashlib.sha1(salt + topic.name).hexdigest()

        if topic.id is not None:
            old_topic = Topic.objects.get(pk=topic.id)
            opened = not old_topic.open and topic.open
        else:
            opened = topic.open

        # We can't send email in pre_save because we don't have an id yet if this
        # is a newly added topic.  So set a flag to be read in topic_post_save().
        if opened:
            topic.post_save_send_mail = True
        else:
            topic.post_save_send_mail = False

def topic_post_save(sender, **kwargs):
    if kwargs['raw'] != True:
        topic = kwargs['instance']
        if topic.vote_type.name in (TYPE_PASS_FAIL, TYPE_CHARTER) and \
        topic.options.count() == 0:
            topic.options.create(name='For', ballot_position=0)
            topic.options.create(name='Against', ballot_position=1)
        if topic.agenda.allows_abstentions and \
        topic.options.filter(name__iexact='Abstain').count() == 0:
            # Set the ballot position to something really high.  Ballot positions
            # are relative not absolute, so as long as it's larger than any likely
            # number of ballot positions, this will put the 'Abstain' at the end
            # of the ballot.  And if it somehow doesn't, that's not really a big
            # deal anyway and easily fixed by the admin.
            topic.options.create(name='Abstain', ballot_position=1000000)

        if not topic.post_save_send_mail:
            return

        # Send mail that we have a new ballot up for vote.
        for list_config in topic.agenda.agenda_mailing_lists.all():
            if list_config.on_vote_open:
                token_string = ''
                if topic.token and list_config.display_token:
                    token_string = EMAIL_TOKEN_STRING % topic.token

                email_body = EMAIL_OPEN_BALLOT % (
                topic,
                topic.text,
                settings.SITE_URL.rstrip('/') + topic.get_absolute_url(),
                token_string,
                topic.deadline.strftime('%d %B %Y %H:%M:%S ') + settings.TIME_ZONE)

                list_config.send_mail("GCD Ballot Open: %s" % topic, email_body)

models.signals.pre_save.connect(topic_pre_save, sender=Topic)
models.signals.post_save.connect(topic_post_save, sender=Topic)

class Option(models.Model):
    class Meta:
        ordering = ('ballot_position', 'name',)
        # order_with_respect_to = 'topic'

    name = models.CharField(max_length=255)
    text = models.TextField(null=True, blank=True)
    ballot_position = models.IntegerField(null=True, blank=True,
      help_text='Optional whole number used to arrange the options in an '
                'order other than alphabetical by name.')
    topic = models.ForeignKey('Topic', null=True, related_name='options')
    voters = models.ManyToManyField(User, through='Vote',
                                          related_name='voted_options')
    result = models.NullBooleanField(blank=True)

    def rank(self, user):
        return self.votes.get(voter=user).rank

    def __unicode__(self):
        return self.name

class Receipt(models.Model):
    """
    Tracks which users have voted for a given topic when there is a secret ballot.
    """
    topic = models.ForeignKey(Topic, related_name='receipts')
    voter = models.ForeignKey(User, related_name='receipts')
    vote_key = models.CharField(max_length=64)

class Vote(models.Model):
    # voter is NULL when the vote is secret.
    voter = models.ForeignKey(User, null=True, related_name='votes')
    option = models.ForeignKey(Option, related_name='votes')
    rank = models.IntegerField(null=True)
    created = models.DateTimeField(auto_now_add=True, editable=False)
    updated = models.DateTimeField(null=True, auto_now=True, editable=False)

    def __unicode__(self):
        string = '%s: %s' % (self.voter.indexer, self.option)
        if self.rank is not None:
            return string + (' %d' % self.rank)
        return string

class ExpectedVoter(models.Model):
    voter = models.ForeignKey(User, related_name='voting_expectations')
    agenda = models.ForeignKey(Agenda, related_name='expected_voters')
    tenure_began = models.DateTimeField()
    tenure_ended = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'voting_expected_voter'
        ordering = ('tenure_began', 'tenure_ended',
                    'voter__last_name', 'voter__first_name')

    def __unicode__(self):
        uni = '%s (%s - ' % (self.voter_name(), self.tenure_began)
        if self.tenure_ended is None:
            return uni + 'present)'
        return uni + ('%s)' % self.tenure_ended)

    def voter_name(self):
        if (self.voter.first_name != ''):
            # If last name is empty, this just adds a harmless trailing space.
            return '%s %s' % (self.voter.first_name, self.voter.last_name)
        return self.voter.last_name
    voter_name.admin_order_field = 'voter__last_name'

