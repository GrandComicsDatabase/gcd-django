from django.core import urlresolvers
from django.conf.urls.defaults import *
from django.conf import settings
from django.views.generic.simple import direct_to_template

from apps.oi import views as oi_views
from apps.oi import states

urlpatterns = patterns('',
    # General-purpose new record add page.
    url(r'^add/$', direct_to_template,
        { 'template': 'oi/edit/add.html' },
        name='add'),

    # Publisher URLs
    url(r'^publisher/add/$',
        oi_views.add_publisher,
        name='add_publisher'),
    url(r'^indicia_publisher/add/parent/(?P<parent_id>\d+)/$',
        oi_views.add_indicia_publisher,
        name='add_indicia_publisher'),
    url(r'^brand/add/parent/(?P<parent_id>\d+)/$',
        oi_views.add_brand,
        name='add_brand'),

    # Series URLs
    url(r'^series/add/publisher/(?P<publisher_id>\d+)/$',
        oi_views.add_series,
        name='add_series'),

    # Issue URLs
    url(r'^series/(?P<series_id>\d+)/add_issue/$', oi_views.add_issue,
        name='add_issue'),

    url(r'^issue/(?P<issue_id>\d+)/add_story/(?P<changeset_id>\d+)$',
        oi_views.add_story,
        name='add_story'),

    # Generic URLs
    url(r'^(?P<model_name>\w+)/(?P<id>\d+)/reserve/$', oi_views.reserve,
        name='reserve_revision'),
    url(r'^(?P<model_name>\w+)/revision/(?P<id>\d+)/edit/$',
        oi_views.edit_revision,
        name='edit_revision'),
    url(r'^changeset/(?P<id>\d+)/edit/$', oi_views.edit, name='edit'),
    url(r'^changeset/(?P<id>\d+)/submit/$', oi_views.submit, name='submit'),
    url(r'^changeset/(?P<id>\d+)/retract/$', oi_views.retract, name='retract'),
    url(r'^changeset/(?P<id>\d+)/discard/$', oi_views.discard, name='discard'),
    url(r'^changeset/(?P<id>\d+)/assign/$', oi_views.assign, name='assign'),
    url(r'^changeset/(?P<id>\d+)/release/$', oi_views.release, name='release'),
    url(r'^changeset/(?P<id>\d+)/approve/$', oi_views.approve, name='approve'),
    url(r'^changeset/(?P<id>\d+)/disapprove/$', oi_views.disapprove,
        name='disapprove'),
    url(r'^changeset/(?P<id>\d+)/process/$', oi_views.process, name='process'),
    url(r'^(?P<model_name>\w+)/revision/(?P<id>\d+)/process/$',
        oi_views.process_revision,
        name='process_revision'),
    url(r'^changeset/(?P<id>\d+)/compare/$', oi_views.compare, name='compare'),
    url(r'^(?P<model_name>\w+)/revision/(?P<id>\d+)/compare/$', oi_views.compare,
        name='compare_revision'),
    url(r'^(?P<model_name>\w+)/revision/(?P<id>\d+)/preview/$', oi_views.preview,
        name='preview_revision'),

    url(r'^ongoing/$', oi_views.ongoing),
    url(r'^ongoing/(?P<series_id>\d+)/delete/$', oi_views.delete_ongoing,
        name='delete_ongoing'),

    url(r'^queues/editing/$', oi_views.show_queue,
       {'queue_name': 'editing', 'state': states.OPEN },
        name='editing'),
    url(r'^queues/pending/$', oi_views.show_queue,
       {'queue_name': 'pending', 'state': states.PENDING },
        name='pending'),
    url(r'^queues/reviews/$', oi_views.show_queue,
       {'queue_name': 'reviews', 'state': states.REVIEWING },
        name='reviewing'),
)

