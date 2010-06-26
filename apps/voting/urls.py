from django.core import urlresolvers
from django.conf.urls.defaults import *
from django.conf import settings
from django.views.generic.simple import direct_to_template

from apps.voting import views as voting_views

urlpatterns = patterns('',
    url(r'^dashboard/$', voting_views.dashboard,
        name='voting_dashboard'),
    url(r'^topic/(?P<id>\d+)/$', voting_views.topic,
        name='topic'),
    url(r'closed_topics/(?P<agenda_id>\d+)/$', voting_views.closed_topics,
        name='closed_topics'),
    url(r'^vote/$', voting_views.vote,
        name='vote'),
    url(r'^agenda/(?P<id>\d+)/$', voting_views.agenda,
        name='agenda'),
)

