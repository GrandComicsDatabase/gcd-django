import hashlib
from random import random

from django.conf import settings
from django.db import models
from django.db.models import Count
from django.core import urlresolvers
from django.core.mail import send_mail
from django.contrib.auth.models import User, Permission

TYPE_PASS_FAIL = 'Pass / Fail'

EMAIL_OPEN_BALLOT = """
The topic '%s' with text:

  %s

is now open for voting at:

%s

%s
"""

EMAIL_TOKEN_STRING = """
You will need to enter the following token exactly as shown in order to vote:

%s

Please do not share this token with anyone who did not recieve the email.
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
A new item on the %s Agenda is now open for discussion.  Please see

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
        notes = u''

    for list_config in item.agenda.agenda_mailing_lists.all():
        if list_config.on_agenda_item_open and newly_opened:
            if list_config.is_primary:
                subject="Open: %s" % item.name,
                message = EMAIL_OPEN_AGENDA_ITEM % (item.agenda, item.name, notes)
            else:
                subject="New %s item open" % item.agenda
                message = EMAIL_OPEN_AGENDA_ITEM_GENERIC % \
                          (list_config.mailing_list.address,
                           item.agenda.get_absolute_url())
            send_mail(from_email=settings.EMAIL_VOTING_FROM,
                      recipient_list=[list_config.mailing_list.address],
                      subject=subject,
                      message=message,
                      fail_silently=(not settings.BETA))

        elif list_config.on_agenda_item_add and newly_added:
            send_mail(from_email=settings.EMAIL_VOTING_FROM,
                      recipient_list=[list_config.mailing_list.address],
                      subject="New %s item added" % item.agenda,
                      message=EMAIL_ADD_AGENDA_ITEM % (item.agenda,
                                item.agenda.get_absolute_url()),
                      fail_silently=(not settings.BETA))

models.signals.pre_save.connect(agenda_item_pre_save, sender=AgendaItem)

class AgendaMailingList(models.Model):
    class Meta:
        db_table = 'voting_agenda_mailing_list'
    agenda = models.ForeignKey(Agenda, related_name='agenda_mailing_lists')
    mailing_list = models.ForeignKey(MailingList,
                                     related_name='agenda_mailing_lists')
    on_agenda_item_add = models.BooleanField()
    on_agenda_item_open = models.BooleanField()
    on_vote_open = models.BooleanField()
    on_vote_close = models.BooleanField()
    is_primary = models.BooleanField()
    reminder = models.BooleanField()
    display_token = models.BooleanField(default=False)

class VoteType(models.Model):
    """
    Determines how to count the votes.
    """
    class Meta:
        db_table = 'voting_vote_type'

    name = models.CharField(max_length=255)
    max_votes = models.IntegerField(default=1, null=True, blank=True,
      help_text='Having more votes than winners sets up ranked choice voting.  '
                'Leave max votes blank to allow as many ranks as options.')
    max_winners = models.IntegerField(default=1,
      help_text='Having more than one winner allows votes to be cast for up to '
                'that many options.')

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

    def __unicode__(self):
        return self.name

def topic_pre_save(sender, **kwargs):
    """
    Callback to initialize the token and/or create standard options if needed.
    Note that this function must be defined outside of any class.
    """
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
    topic = kwargs['instance']
    if topic.vote_type.name == TYPE_PASS_FAIL and topic.options.count() == 0:
        topic.options.create(name='For', ballot_position=0)
        topic.options.create(name='Against', ballot_position=1)
        if topic.agenda.allows_abstentions:
            topic.options.create(name='Abstain', ballot_position=2)

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
              token_string)

            send_mail(from_email=settings.EMAIL_VOTING_FROM,
                      recipient_list=[list_config.mailing_list.address],
                      subject="GCD Ballot Open: %s" % topic,
                      message=email_body,
                      fail_silently=(not settings.BETA))

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
        string = u'%s: %s' % (self.voter.indexer, self.option)
        if self.rank is not None:
            return string + (' %d' % self.rank)
        return string

