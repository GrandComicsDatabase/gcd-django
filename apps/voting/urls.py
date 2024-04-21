import django.urls as urlresolvers
from django.urls import path
from django.conf import settings

from apps.voting import views as voting_views

urlpatterns = [
    path('', voting_views.dashboard,
        name='voting_dashboard'),
    path('ballot/<int:id>/', voting_views.topic,
        name='ballot'),
    path('vote/', voting_views.vote,
        name='vote'),
    path('agenda/<int:id>/', voting_views.agenda,
        name='agenda'),
]
