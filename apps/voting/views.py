from datetime import datetime

from django.db.models import Q
from django.core import urlresolvers
from django.http import HttpResponseRedirect
from django.template import RequestContext
from django.shortcuts import render_to_response, get_object_or_404
from django.contrib.auth.decorators import login_required, permission_required

from apps.gcd.views import render_error
from apps.voting.models import *


def dashboard(request):
    # Permissions are returned as appname.codename by get_all_permissions().
    codenames = [p.split('.', 1)[1] for p in request.user.get_all_permissions()]
    can_vote = Q(agenda__permission__codename__in=codenames)
    topics = Topic.objects.filter(deadline__gte=datetime.now())
    my_topics = topics.filter(can_vote)
    other_topics = topics.exclude(can_vote)
    return render_to_response('voting/dashboard.html', 
                              {
                                'topics': topics,
                                'agendas': Agenda.objects.all(),
                              },
                              context_instance=RequestContext(request))

def topic(request, id):
    topic = get_object_or_404(Topic, id=id)

    if topic.deadline < datetime.now():
        return HttpResponseRedirect(
          urlresolvers.reverse('closed_topics',
                               kwargs={agenda_id: topic.agenda.id}))

    if topic.options.filter(votes__voter=request.user).count():
        voted = True
    else:
        voted = False

    return render_to_response('voting/topic.html',
                              {'topic': topic, 'voted': voted },
                              context_instance=RequestContext(request))

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
    return HttpResponseRedirect(urlresolvers.reverse('topic',
      kwargs={ 'id': option.topic.id }))

def agenda(request, id):
    agenda = get_object_or_404(Agenda, id=id)
    return render_to_response('voting/agenda.html',
                               context_instance=RequestContext(request))

def closed_topics(request, agenda_id):
    topics = Topic.objects.filter(deadline__lt=datetime.now(), agenda_id=agenda_id)
    return render_to_response('voting/closed.html',
                              context_instance=RequestContext(request))

