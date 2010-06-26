from django.core import urlresolvers
from django.conf.urls.defaults import *
from django.conf import settings
from django.views.generic.simple import direct_to_template

from apps.voting import views as voting_views

urlpatterns = patterns('',
    url(r'^$', voting_views.dashboard,
        name='voting_dashboard'),
    url(r'^ballot/(?P<id>\d+)/$', voting_views.topic,
        name='ballot'),
    url(r'^vote/$', voting_views.vote,
        name='vote'),
    url(r'^agenda/(?P<id>\d+)/$', voting_views.agenda,
        name='agenda'),
)

