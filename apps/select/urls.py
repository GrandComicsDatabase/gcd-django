from django.conf.urls import patterns, url
from apps.select import views as select_views

urlpatterns = [
    url(r'^issue/(?P<issue_id>\d+)/cache/$', select_views.cache_content,
        name='cache_issue'),
    url(r'^story/(?P<story_id>\d+)/cache/$', select_views.cache_content,
        name='cache_story'),
    url(r'^cover/(?P<cover_story_id>\d+)/cache/$', select_views.cache_content,
        name='cache_cover'),

    url(r'^select_object/(?P<select_key>.+)/search/$',
      select_views.process_select_search, name='select_object_search'),
    url(r'^select_object/(?P<select_key>.+)/search_haystack/$',
      select_views.process_select_search_haystack, name='select_object_search_haystack'),
    url(r'^select_object/(?P<select_key>.+)/$', select_views.select_object,
      name='select_object'),

    url(r'^select_objects/(?P<select_key>.+)/$',
      select_views.process_multiple_selects, name='process_multiple_selects'),
]