import hashlib
import os.path
from datetime import datetime
from pyvotecore.schulze_method import SchulzeMethod

from django.conf import settings
from django.db.models import Q
from django.core import urlresolvers
from django.core.mail import send_mail
from django.http import HttpResponseRedirect
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required, permission_required

from apps.indexer.views import render_error
from apps.voting.models import *
from functools import reduce

EMAIL_RESULT = """
All ballots have been received for the following topic from the %s agenda:

  %s

The results are:

%s

Please go to %s for more details.
"""

EMAIL_RECEIPT = """
This is your receipt for your vote in the secret ballot election for %s.
You voted for:
%s

If anything has gone wrong with your vote, or if the election allows you to
change your vote and you wish to change it, you will need to provide the
following two pieces of information to the voting administrator (%s)
in order to match account to your votes.  Note that changing your vote
may require you to disclose your vote choices to the voting administrator.

secret key:
'%s'
vote id:
'%s'
"""


def _classify_topics(topics, user):
    # Permissions are returned as appname.codename by get_all_permissions().
    if user.is_anonymous():
        my_topics = ()
        forbidden_topics = topics
    elif user.is_superuser:
        # Superusers have all permissions, which can be very expensive in
        # the else clause.  Non-superusers tend to have just a few permissions.
        my_topics = topics
        forbidden_topics = ()
    else:
        q_list = []
        # You can't actually get a query_set of the user's permissions, just this
        # list of strings that stuff the app label and code name together.  So
        # we have to build queries that match each of the actual permissions, and
        # then OR those all together.
        for p in user.get_all_permissions():
            app_label, code_name = p.split('.', 1)
            q_list.append(Q(agenda__permission__codename=code_name,
                            agenda__permission__content_type__app_label=app_label))

        can_vote = reduce(lambda x, y: x | y, q_list)
        my_topics = topics.filter(can_vote)
        forbidden_topics = topics.exclude(can_vote)

    voted_topics = []
    pending_topics = []
    for topic in my_topics:
        if topic.has_vote_from(user):
            voted_topics.append(topic)
        else:
            pending_topics.append(topic)
    return (pending_topics, voted_topics, forbidden_topics)


def dashboard(request):
    topics = Topic.objects.filter(deadline__gte=datetime.now(), open=True,
                                  result_calculated=False)

    # We ignore the forbidden topics on the dashboard and only show relevant topics.
    pending_topics, voted_topics, forbidden_topics = \
      _classify_topics(topics, request.user)
    return render(request, 'voting/dashboard.html',
                  {'voted_topics': voted_topics,
                   'pending_topics': pending_topics,
                   'agendas': Agenda.objects.all()})


def _calculate_results(unresolved):
    """
    Given a QuerySet of unresolved topics (with expired deadlines),
    resolve them into results, possibly indicating a tie of some sort.

    TODO: Handle the case of abstaning being a "winning" option.
    """

    extra = ''
    for topic in unresolved:
        # if topic.agenda.quorum:
            # raise Exception, '%d / %d' % (topic.agenda.quorum, topic.num_voters())
        if topic.agenda.quorum and topic.num_voters() < topic.agenda.quorum:
            # Mark invalid with no results.  Somewhat counter-intuitively,
            # we consider the results to have been "calculated" in this case
            # (specifically, we calculated that there are no valid results).
            topic.invalid = True
            topic.result_calculated = True
            topic.save()
            continue

        # Currently, proceed with results even if there are fewer results
        # than expected.  It is conceivable that this is a valid outcome,
        # for instance, if only three candidates receive any votes in a Board
        # election, then there should be only three winners even though there
        # are four or five positions.

        options = topic.counted_options().filter(num_votes__gt=0)
        num_options = options.count()

        if topic.vote_type.name == TYPE_CHARTER:
            # Charter amendments require a 2/3 majority.
            for_option = options.get(name='For')
            against_option = options.get(name='Against')
            total_votes = for_option.num_votes + against_option.num_votes
            if for_option.num_votes >= (total_votes * (2.0 / 3.0)):
                for_option.result = True
                for_option.save()
            else:
                against_option.result = True
                against_option.save()

            # It's not possible for this sort of measure to tie- it either reaches
            # the two-thirds threshold or it does not.
            topic.invalid = False
            topic.result_calculated = True
            topic.save()
            extra = ('\n\nPlease note that Charter Amendments require a 2/3 '
                     'majority to pass.')

        elif not topic.vote_type.max_votes:
            # evaluate Schulze method. First collect votes, than use library.
            voters = User.objects.filter(votes__option__topic=topic).distinct()
            options = topic.options.all()
            ballots = []
            for voter in voters:
                votes = Vote.objects.filter(option__in=options, voter=voter)\
                                    .order_by('rank')
                ordered_votes = []
                last_rank = votes[0].rank-1
                current_rank = 0
                for vote in votes:
                    if vote.rank == last_rank:
                        ordered_votes[-1].append(vote.option_id)
                    else:
                        ordered_votes.append([vote.option_id])
                        last_rank = vote.rank
                        current_rank += 1
                    vote.rank = current_rank
                    vote.save()
                ballot = {'ballot': ordered_votes}
                ballots.append(ballot)
            result = SchulzeMethod(ballots, ballot_notation = "grouping")
            if hasattr(result,'tied_winners'):
                # Schulze method can be tied as well, treat as other ties
                options = Option.objects.filter(id__in=result.tied_winners)
                for option in options:
                    option.result = True
                    option.save()
                topic.invalid = True
                topic.result_calculated = True
                topic.save()
            else:
                option = Option.objects.get(id=result.winner)
                option.result = True
                option.save()
                options = options.exclude(id=result.winner)
                for option in options:
                    option.result = False
                    option.save()
                topic.result_calculated = True
                topic.save()

        elif topic.vote_type.max_votes <= topic.vote_type.max_winners:
            # Flag ties that affect the validity of the results,
            # and set any tied options after the valid winning range
            # to a "winning" result as well, indicating that they are all
            # equally plausible as winners despite producing more winners
            # than are allowed.
            i = topic.vote_type.max_winners
            while (i > 0 and i < num_options and
                   options[i-1].num_votes == options[i].num_votes):
                topic.invalid = True

                # Note that setting options[i].result = True and then
                # saving options[i] does not work, probably as a side effect
                # of evaluationg the options queryset (it's not actualy an array)
                option = options[i]
                option.result = True
                option.save()
                i += 1

            # Set all non-tied winning results.
            for option in options[0:topic.vote_type.max_winners]:
                option.result = True
                option.save()

            topic.result_calculated = True
            topic.save()

        else:
            return

        _send_result_email(topic, extra)


def _send_result_email(topic, extra=''):
    for list_config in topic.agenda.agenda_mailing_lists.all():
        if list_config.on_vote_close:
            result = None
            if topic.invalid:
                result = ('This vote failed to produce a valid result, '
                          'possibly because of a tie.  '
                          'The vote administrators will follow up as needed.')
            elif topic.vote_type.name in (TYPE_PASS_FAIL, TYPE_CHARTER):
                result_name = topic.options.get(result=True).name
                if result_name == 'For':
                    result = 'The motion PASSED'
                elif result_name == 'Against':
                    result = 'The motion FAILED'

            if result is None:
                # Either it's not a pass/fail or charter, or the options
                # were renamed so we can't convert to PASS/FAIL.
                result = 'The following option(s) won:\n'
                for winner in topic.options.filter(result=True):
                    result += '  * %s\n' % winner.name

            result += extra
            email_body = EMAIL_RESULT % (topic.agenda, topic.text, result,
              settings.SITE_URL.rstrip('/') + topic.get_absolute_url())

            list_config.send_mail(subject="GCD Vote Result: %s" % topic,
                                  message=email_body)


@login_required
def topic(request, id):
    topic = get_object_or_404(Topic, id=id)

    if not request.user.has_perm('indexer.can_vote'):
        return render_error(request,
                            'You do not have permission to vote on this topic.')
    # Note that if this was a secret ballot, this will be an empty
    # queryset.  That is OK, the UI won't look at it in that case.
    # But this is why "voted" is not just a check for at least one vote here.
    votes = topic.options.filter(votes__voter=request.user)

    return render(request, 'voting/topic.html',
                  {'topic': topic,
                   'voted': topic.has_vote_from(request.user),
                   'votes': votes,
                   'closed': topic.deadline < datetime.now() \
                             or topic.result_calculated,
                   'settings': settings})


@permission_required('indexer.can_vote')
def vote(request):
    if request.method != 'POST':
        return render_error(request,
                            'Please access this page through the correct form.')

    first = True
    topic = None
    voter = None
    option_params = request.POST.getlist('option')
    ranks = {}
    if not option_params:
        # ranked_choice, collect all ranks
        values = list(request.POST.keys())
        for value in values:
            if value.startswith('option'):
                if request.POST[value]:
                    try:
                        ranks[int(value[7:])] = int(request.POST[value])
                    except ValueError:
                        return render_error(request,
                        'You must enter a full number for the ranking.')
                else:
                    ranks[int(value[7:])] = None
        options = Option.objects.filter(id__in=list(ranks.keys()))
    else:
        options = Option.objects.filter(id__in=option_params)
        # Get all of these now because we may need to iterate twice.
        options = options.select_related('topic__agenda', 'topic__vote_type').all()
    if not options:
        return render_error(request,
                            'You must choose at least one option to vote.')
    for option in options:
        if first is True:
            first = False
            topic = option.topic
            if not request.user.has_perm('%s.%s' %
                (topic.agenda.permission.content_type.app_label,
                 topic.agenda.permission.codename)):
                return render_error(request,
                  'We are sorry, but you do not have permission to vote '
                  'on this ballot.  You must have the "%s" permission.' %
                   topic.agenda.permission.name)

            if topic.token is not None and \
               request.POST['token'].strip() != topic.token:
                return render_error(request,
                  'You must supply an authorization token in order '
                  'to vote on this topic.')

            if topic.vote_type.max_votes is not None and \
               len(option_params) > topic.vote_type.max_votes:
                plural = 's' if len(option_params) > 1 else ''
                return render_error(request,
                  'You may not vote for more than %d option%s' %
                  (topic.vote_type.max_votes, plural))

            if topic.agenda.secret_ballot:
                receipts = Receipt.objects.filter(topic=topic, voter=request.user)
                already_voted = receipts.count() > 0
            else:
                voter = request.user
                already_voted = Vote.objects.filter(option__topic=topic,
                                                    voter=request.user).count() > 0

            if already_voted:
                return render_error(request,
                  'You have already voted on this ballot.  If you wish to change '
                  'your vote, please contact the voting administrator at ' +
                  settings.EMAIL_VOTING_ADMIN)

        if not option_params:
            # for ranked choice options can be empty, set these last in ranking
            if option.id in ranks:
                rank = ranks[option.id]
            if not rank:
                rank = max(ranks.values()) + 1
        else:
            rank = None
        vote = Vote(option=option, voter=voter, rank=rank)
        vote.save()

    if topic.agenda.secret_ballot:
        # We email the salt and the vote string to the voter, and store
        # the receipt key in the database.  This way they can prove that
        # they voted a particular way by sending us back those two values,
        # and repair or change a vote.
        vote_ids = ', '.join(option_params)
        salt = hashlib.sha1(str(random())).hexdigest()[:5]
        key = hashlib.sha1(salt + vote_ids).hexdigest()

        receipt = Receipt(voter=request.user,
                          topic=option.topic,
                          vote_key=key)
        receipt.save()

        # Log the data as a backup in case of mail sending/receiving problems.
        # Technically, this makes it not a secret ballot, but it takes some
        # work to interpret the log, and there's always been a human counting
        # the ballots before, so this allows for at least as much secrecy
        # as before.
        # Use unbuffered appends because we don't want concurrent writes to get
        # spliced due to buffering.
        path = os.path.join(settings.VOTING_DIR, 'vote_record_%d' % topic.id)
        voting_record = open(path, 'a', 0)
        voting_record.write('%d | %s | %s | %s\n' %
                            (request.user.id, salt, vote_ids, key))
        voting_record.close()

        vote_values = "\n".join([str(o) for o in options])
        send_mail(from_email=settings.EMAIL_VOTING_FROM,
                  recipient_list=[request.user.email],
                  subject="GCD secret ballot receipt",
                  message=EMAIL_RECEIPT % (topic, vote_values,
                                           settings.EMAIL_VOTING_ADMIN,
                                           salt, vote_ids),
                  fail_silently=(not settings.BETA))

    if topic.expected_voters().count() > 0 and len(topic.absent_voters()) == 0:
        _calculate_results([topic,])

    return HttpResponseRedirect(urlresolvers.reverse('ballot',
                                kwargs={ 'id': option.topic.id }))


def agenda(request, id):
    agenda = get_object_or_404(Agenda, id=id)

    # The "open" field on the topic object is somewhat misleading.
    # It means that the topic has been approved for an active ballot.
    # Ballots that are complete still have open=True, and ballots that were never
    # approved (much less completed) still have open=False.  This translates
    # the conditions into what you would expect for open or closed ballots.
    past_due = Q(deadline__lte=datetime.now())
    open = agenda.topics.exclude(past_due | Q(open=False))\
                        .filter(result_calculated=False)
    closed = agenda.topics.filter((past_due & Q(open=True)) |
                                  Q(result_calculated=True))

    pending_items = agenda.items.filter(state__isnull=True)
    open_items = agenda.items.filter(state=True)

    _calculate_results(closed.filter(result_calculated=False))

    pending_topics, voted_topics, forbidden_topics = \
      _classify_topics(open.order_by('-deadline'), request.user)

    # result_counts = map(lambda t: (t.name, t.results().count()), closed)
    # raise Exception, result_counts
    return render(request, 'voting/agenda.html',
                  {'agenda': agenda,
                   'closed_topics': closed.order_by('-deadline'),
                   'pending_topics': pending_topics,
                   'voted_topics': voted_topics,
                   'forbidden_topics': forbidden_topics,
                   'open_items': open_items,
                   'pending_items': pending_items})
