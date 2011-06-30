# -*- coding: utf-8 -*-
from django.core import urlresolvers
from django.conf.urls.defaults import *
from django.conf import settings
from django.views.generic.simple import direct_to_template
from django.contrib.auth.decorators import login_required 

from apps.oi import views as oi_views
from apps.oi import covers as oi_covers
from apps.oi import import_export as oi_import
from apps.oi import states

urlpatterns = patterns('',
    # General-purpose new record add page.
    url(r'^add/$', login_required(direct_to_template),
        { 'template': 'oi/edit/add.html' },
        name='add'),

    url(r'^mentoring/$', oi_views.mentoring,
        name='mentoring'),

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
    url(r'^series/(?P<series_id>\d+)/reorder/$',
        oi_views.reorder_series,
        name='reorder_series'),
    url(r'^series/(?P<series_id>\d+)/reorder/key_date/$',
        oi_views.reorder_series_by_key_date,
        name='reorder_series_key_date'),
    url(r'^series/(?P<series_id>\d+)/reorder/issue_number/$',
        oi_views.reorder_series_by_issue_number,
        name='reorder_series_issue_number'),

    # Issue URLs
    url(r'^series/(?P<series_id>\d+)/add_issue/$', oi_views.add_issue,
        name='add_issue'),
    url(r'^series/(?P<series_id>\d+)/add_issues/$', oi_views.add_issues,
        name='add_issues'),
    url(r'^series/(?P<series_id>\d+)/add_issues/(?P<method>\w+)/$',
        oi_views.add_issues,
        name='add_multiple_issues'),
    url(r'^issue/(?P<issue_id>\d+)/add_variant_issue/$', oi_views.add_variant_issue,
        name='add_variant_issue'),
    url(r'^issue/(?P<issue_id>\d+)/add_variant_issue/(?P<cover_id>\d+)/$', 
        oi_views.add_variant_issue, name='add_variant_issue'),

    url(r'^issue/(?P<issue_id>\d+)/export_issue/$', 
        oi_import.export_issue_to_file, 
        name='export_issue'),
    url(r'^issue/(?P<issue_id>\d+)/import_issue/(?P<changeset_id>\d+)/$', 
        oi_import.import_issue_from_file, 
        name='import_issue'),
    url(r'^issue/revision/(?P<issue_revision_id>\d+)/add_story/(?P<changeset_id>\d+)$',
        oi_views.add_story,
        name='add_story'),
    url(r'^issue/(?P<issue_id>\d+)/import_stories/(?P<changeset_id>\d+)/$', 
        oi_import.import_sequences_from_file, 
        name='import_stories'),
    url(r'^issue/(?P<issue_id>\d+)/reorder_stories/(?P<changeset_id>\d+)$',
        oi_views.reorder_stories,
        name='reorder_stories'),

    url(r'^bulk_issue_edit/$', 
        oi_views.edit_issues_in_bulk, 
        name='edit_issues_in_bulk'),

    # Story URLs 
    # can be changed to r'^(?P<model_name>\w+)/revision/(?P<id>\d+)/remove/
    # later if needed
    url(r'^story/revision/(?P<id>\d+)/remove/$', 
        oi_views.remove_story_revision, 
        name='remove_story_revision'),
    url(r'^story/revision/(?P<id>\d+)/delete/$', 
        oi_views.toggle_delete_story_revision, 
        name='toggle_delete_story_revision'),
    url(r'^story/revision/(?P<id>\d+)/move/$', oi_views.move_story_revision,
        name='move_story_revision'),

    # Cover URLs
    url(r'^edit_covers/(?P<issue_id>\d+)/$', oi_covers.edit_covers,
      name='edit_covers'),
    url(r'^upload_cover/(?P<issue_id>\d+)/$', oi_covers.upload_cover,
      name='upload_cover'),
    url(r'^upload_variant/(?P<issue_id>\d+)/$', oi_covers.upload_variant,
      name='upload_variant'),
    url(r'^replace_cover/(?P<cover_id>\d+)/$', oi_covers.upload_cover, 
      name='replace_cover'),
    url(r'^gatefold_cover/$',
      oi_covers.process_edited_gatefold_cover, name='gatefold_cover'),
    url(r'^uploaded_cover/(?P<revision_id>\d+)/$', oi_covers.uploaded_cover,
      name='upload_cover_complete'),
    url(r'^mark_cover_revision/(?P<revision_id>.+)/$', oi_covers.mark_cover,
      {'marked': True}, name='mark_cover_revision'),
    url(r'^unmark_cover_revision/(?P<revision_id>.+)/$', oi_covers.mark_cover,
      {'marked': False}, name='unmark_cover_revision'),
    url(r'^mark_cover/(?P<cover_id>.+)/$', oi_covers.mark_cover,
      {'marked': True}, name='mark_cover'),
    url(r'^unmark_cover/(?P<cover_id>.+)/$', oi_covers.mark_cover, 
      {'marked': False}, name='unmark_cover'),
    url(r'^cover/changeset/(?P<id>\d+)/move/$', oi_views.move_cover, 
      name='move_cover'),
    url(r'^cover/(?P<cover_id>\d+)/changeset/(?P<id>\d+)/move/$', oi_views.move_cover, 
      name='move_cover'),
    url(r'^cover/(?P<cover_id>\d+)/changeset/(?P<id>\d+)/undo_move$', 
      oi_views.undo_move_cover, name='undo_move_cover'),

    url(r'^ongoing/$', oi_views.ongoing),
    url(r'^ongoing/(?P<series_id>\d+)/delete/$', oi_views.delete_ongoing,
        name='delete_ongoing'),

    # Generic URLs
    url(r'^(?P<model_name>\w+)/(?P<id>\d+)/reserve/$', oi_views.reserve,
        name='reserve_revision'),
    url(r'^(?P<model_name>\w+)/(?P<id>\d+)/delete/$', oi_views.delete,
        name='delete_revision'),
    url(r'^(?P<model_name>\w+)/revision/(?P<id>\d+)/edit/$',
        oi_views.edit_revision,
        name='edit_revision'),
    url(r'^changeset/(?P<id>\d+)/edit/$', oi_views.edit, name='edit'),
    url(r'^changeset/(?P<id>\d+)/submit/$', oi_views.submit, name='submit'),
    url(r'^changeset/(?P<id>\d+)/retract/$', oi_views.retract, name='retract'),
    url(r'^changeset/(?P<id>\d+)/discard/$', oi_views.discard, name='discard'),
    url(r'^changeset/(?P<id>\d+)/(?P<has_comment>\d+)/confirm_discard/$', oi_views.confirm_discard,
        name='confirm_discard'),
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
    url(r'^(?P<model_name>\w+)/revision/(?P<id>\d+)/preview/$', oi_views.preview,
        name='preview_revision'),

    # queue URLs
    url(r'^queues/editing/$', oi_views.show_queue,
       {'queue_name': 'editing', 'state': states.OPEN },
        name='editing'),
    url(r'^queues/pending/$', oi_views.show_queue,
       {'queue_name': 'pending', 'state': states.PENDING },
        name='pending'),
    url(r'^queues/reviews/$', oi_views.show_queue,
       {'queue_name': 'reviews', 'state': states.REVIEWING },
        name='reviewing'),
    url(r'^queues/approved/$', oi_views.show_queue,
       {'queue_name': 'approved', 'state': states.APPROVED },
        name='approved'),
    url(r'^queues/covers_pending/$', oi_views.show_queue,
       {'queue_name': 'covers', 'state': states.PENDING },
        name='pending_covers'),

    url(r'^download/', oi_views.download, {}, name='download'),
)

urlpatterns += patterns('django.views.generic.simple',
    (r'^changeset/(?P<id>\d+)/$', 'redirect_to', {'url' : 'compare' })
)
