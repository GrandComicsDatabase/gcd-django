from django.core import urlresolvers
from django.conf.urls.defaults import *
from django.conf import settings
from django.views.generic.simple import direct_to_template

from apps.oi import views as oi_views

urlpatterns = patterns('',
    # General-purpose new record add page.
    url(r'^add/$', direct_to_template,
        { 'template': 'oi/edit/add.html' },
        name='add'),

    # Publisher URLs
    url(r'^publisher/(?P<id>\d+)/reserve/$', oi_views.reserve,
        { 'model_name': 'publisher' }, name='reserve_publisher'),
    url(r'^publisher/(?P<id>\d+)/edit/$', oi_views.direct_edit,
        { 'model_name': 'publisher' }, name='direct_edit_publisher'),
    url(r'^publisher/revision/(?P<id>\d+)/submit/$', oi_views.submit,
        { 'model_name': 'publisher' }, name='submit_publisher'),
    url(r'^publisher/revision/(?P<id>\d+)/process/$', oi_views.process,
        { 'model_name': 'publisher' }, name='process_publisher'),
    url(r'^publisher/revision/(?P<id>\d+)/edit/$', oi_views.edit,
        { 'model_name': 'publisher' }, name='edit_publisher'),
    url(r'^publisher/revision/(?P<id>\d+)/discard/$', oi_views.discard,
        { 'model_name': 'publisher' }, name='discard_publisher'),
    url(r'^publisher/revision/(?P<id>\d+)/assign/$', oi_views.assign,
        { 'model_name': 'publisher' }, name='assign_publisher'),
    url(r'^publisher/revision/(?P<id>\d+)/release/$', oi_views.release,
        { 'model_name': 'publisher' }, name='release_publisher'),
    url(r'^publisher/revision/(?P<id>\d+)/approve/$', oi_views.approve,
        { 'model_name': 'publisher' }, name='approve_publisher'),
    url(r'^publisher/revision/(?P<id>\d+)/disapprove/$', oi_views.disapprove,
        { 'model_name': 'publisher' }, name='disapprove_publisher'),
    url(r'^publisher/add/$',
        oi_views.add_publisher,
        name='add_publisher'),
    url(r'^imprint/add/parent/(?P<parent_id>\d+)/$',
        oi_views.add_publisher,
        name='add_imprint'),
    url(r'^publisher/revision/(?P<id>\d+)/preview/$', oi_views.preview,
        { 'model_name': 'publisher' }, name='preview_publisher'),

    # Series URLs
    url(r'^series/(?P<id>\d+)/reserve/$', oi_views.reserve,
        { 'model_name': 'series' }, name='reserve_series'),
    url(r'^series/(?P<id>\d+)/edit/$', oi_views.direct_edit,
        { 'model_name': 'series' }, name='direct_edit_series'),
    url(r'^series/revision/(?P<id>\d+)/submit/$', oi_views.submit,
        { 'model_name': 'series' }, name='submit_series'),
    url(r'^series/revision/(?P<id>\d+)/process/$', oi_views.process,
        { 'model_name': 'series' }, name='process_series'),
    url(r'^series/revision/(?P<id>\d+)/edit/$', oi_views.edit,
        { 'model_name': 'series' }, name='edit_series'),
    url(r'^series/revision/(?P<id>\d+)/discard/$', oi_views.discard,
        { 'model_name': 'series' }, name='discard_series'),
    url(r'^series/revision/(?P<id>\d+)/assign/$', oi_views.assign,
        { 'model_name': 'series' }, name='assign_series'),
    url(r'^series/revision/(?P<id>\d+)/release/$', oi_views.release,
        { 'model_name': 'series' }, name='release_series'),
    url(r'^series/revision/(?P<id>\d+)/approve/$', oi_views.approve,
        { 'model_name': 'series' }, name='approve_series'),
    url(r'^series/revision/(?P<id>\d+)/disapprove/$', oi_views.disapprove,
        { 'model_name': 'series' }, name='disapprove_series'),
    url(r'series/add/publisher/(?P<publisher_id>\d+)/$',
        oi_views.add_series,
        name='add_series'),
    url(r'^series/revision/(?P<id>\d+)/preview/$', oi_views.preview,
        { 'model_name': 'series' }, name='preview_series'),

    # Issue URLs
    url(r'series/(?P<series_id>\d+)/add_issues/$', oi_views.add_issues,
        name='add_issues'),

    url(r'^ongoing/$', oi_views.ongoing),

    url(r'^queues/editing/$', oi_views.show_editing,
        name='editing'),
    url(r'^queues/pending/$', oi_views.show_pending,
        name='pending'),
    url(r'^queues/reviews/$', oi_views.show_reviews,
        name='reviewing'),
)

