import django.urls as urlresolvers
from django.conf.urls import url
from django.conf import settings

from apps.voting import views as voting_views

urlpatterns = [
    url(r'^$', voting_views.dashboard,
        name='voting_dashboard'),
    url(r'^ballot/(?P<id>\d+)/$', voting_views.topic,
        name='ballot'),
    url(r'^vote/$', voting_views.vote,
        name='vote'),
    url(r'^agenda/(?P<id>\d+)/$', voting_views.agenda,
        name='agenda'),
]
