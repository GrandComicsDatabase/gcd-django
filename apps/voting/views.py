from datetime import datetime

from django.conf import settings
from django.db.models import Q
from django.core import urlresolvers
from django.core.mail import send_mail
from django.http import HttpResponseRedirect
from django.template import RequestContext
from django.shortcuts import render_to_response, get_object_or_404
from django.contrib.auth.decorators import login_required, permission_required

from apps.gcd.views import render_error
from apps.voting.models import *

EMAIL_RESULT = """
All ballots have been received for the following topic from the %s agenda:

  %s

The results are:

%s

Please go to %s for more details.
"""

def dashboard(request):
    topics = Topic.objects.filter(deadline__gte=datetime.now())

    # Permissions are returned as appname.codename by get_all_permissions().
    if request.user.is_anonymous:
        my_topics = ()
        other_topics = topics
    else:
        codenames = [p.split('.', 1)[1] for p in request.user.get_all_permissions()]
        can_vote = Q(agenda__permission__codename__in=codenames)
        my_topics = topics.filter(can_vote)
        other_topics = topics.exclude(can_vote)

    return render_to_response('voting/dashboard.html', 
                              {
                                'topics': topics,
                                'agendas': Agenda.objects.all(),
                              },
                              context_instance=RequestContext(request))

def _calculate_results(unresolved):
    """
    Given a QuerySet of unresolved topics (with expired deadlines),
    resolve them into results, possibly indicating a tie of some sort.

    TODO: Handle ranked choice voting.
    TODO: Handle the case of abstaning being a "winning" option.
    """

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

        if topic.vote_type.max_votes == 1:
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

            _send_result_email(topic)

        else:
            # TODO: Implement Schulze method.
            pass

def _send_result_email(topic):
    for list_config in topic.agenda.agenda_mailing_lists.all():
        if list_config.on_vote_close:
            if topic.invalid:
                result = ('This vote failed to produce a valid result.  '
                          'The vote administrators will follow up as needed.')
            elif topic.vote_type.name == TYPE_PASS_FAIL:
                if topic.options.get(result=True).name == 'For':
                    result = 'The motion PASSED'
                else:
                    result = 'The motion FAILED'

            else:
                result = 'The following option(s) won:\n'
                for winner in topic.options.filter(result=True):
                    result += '  * %s\n' % winner.name

            email_body = EMAIL_RESULT % (topic.agenda, topic.text, result,
              settings.SITE_URL.rstrip('/') + topic.agenda.get_absolute_url())

            send_mail(from_email=settings.EMAIL_VOTING_FROM,
                      recipient_list=[list_config.mailing_list.address],
                      subject="GCD Vote Result: %s" % topic,
                      message=email_body,
                      fail_silently=(not settings.BETA))

@login_required
def topic(request, id):
    topic = get_object_or_404(Topic, id=id)

    if topic.options.filter(votes__voter=request.user).count():
        voted = True
    else:
        voted = False

    return render_to_response('voting/topic.html',
                              {
                                'topic': topic,
                                'voted': voted,
                                'closed': topic.deadline < datetime.now(),
                              },
                              context_instance=RequestContext(request))

@login_required
def vote(request):
    option = get_object_or_404(Option, id=request.POST['option'])
    if 'rank' in request.POST:
        rank = request.POST['rank'].strip()
    else:
        rank = None
    if option.topic.token is not None and \
       request.POST['token'].strip() != option.topic.token:
        return render_error(request,
          'You must supply an authorization token in order to vote on this topic.')
    vote = Vote(option=option, voter=request.user, rank=rank)
    vote.save()
    return HttpResponseRedirect(urlresolvers.reverse('ballot',
      kwargs={ 'id': option.topic.id }))

def agenda(request, id):
    agenda = get_object_or_404(Agenda, id=id)

    past_due = Q(deadline__lte=datetime.now())
    open = agenda.topics.exclude(past_due)
    closed = agenda.topics.filter(past_due)

    _calculate_results(closed.filter(result_calculated=False))

    return render_to_response('voting/agenda.html',
                              {
                                'agenda': agenda,
                                'closed_topics': closed.order_by('-deadline'),
                                'open_topics': open.order_by('-deadline')
                              },
                              context_instance=RequestContext(request))

