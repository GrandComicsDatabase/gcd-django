from django.conf.urls.defaults import *
from django.conf import settings

urlpatterns = patterns('',

    (r'^$', 'apps.inducks.views.index'),

    # Issue
    (r'^issue/(?P<issue_id>.+)/$', 'apps.inducks.views.details.issue'),
    # Series
    (r'^series/(?P<series_id>.+)/$', 'apps.inducks.views.details.series'),

)
