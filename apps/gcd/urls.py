# -*- coding: utf-8 -*-
from django.conf.urls.defaults import *
from django.conf import settings

urlpatterns = patterns('',
    ###########################################################################
    # GCD URLs.
    #
    # General forms, where <entity> is publisher, series or issue and
    # <credit> is writer, penciller, etc.:
    #   gcd/<entity>/<id>/ shows details for the given entity.
    #   gcd/<entity>/name/<name> searches for entities by name.
    #   gcd/<credit>/name/<name> searches for stories by the named credit.
    #
    # In many cases a suffix of /sort/<sort type>/ is an optional extension.
    # In such cases, the form specifying the sort type must be listed first
    # or else it will never be used because the shorter form will always match.
    ###########################################################################

    (r'^$', 'apps.gcd.views.index'),
    (r'^search/$', 'apps.gcd.views.search.search'),
    (r'^search/advanced/$', 'apps.gcd.views.search.advanced_search'),
    (r'^search/advanced/process/$',
     'apps.gcd.views.search.process_advanced'),

    # Publisher
    (r'^publisher/(?P<publisher_id>\d+)/$',
     'apps.gcd.views.details.publisher'),
    (r'^publisher/name/(?P<publisher_name>.+)/sort/(?P<sort>.+)/$',
     'apps.gcd.views.search.publishers_by_name'),
    (r'^publisher/name/(?P<publisher_name>.+)/$',
     'apps.gcd.views.search.publishers_by_name'),
    (r'^publisher/(?P<publisher_id>\d+)/imprints/$',
     'apps.gcd.views.details.imprints'),

    # Imprint
    (r'^imprint/(?P<imprint_id>\d+)/$',
     'apps.gcd.views.details.imprint'),

    # Series
    (r'^series/(?P<series_id>\d+)/$', 'apps.gcd.views.details.series'),
    (r'^series/name/(?P<series_name>.+)/sort/(?P<sort>.+)/$',
     'apps.gcd.views.search.series_by_name'),
    # Series and Issue
    (r'^series/name/(?P<series_name>.+)/issue/(?P<issue_nr>.+)/$',
     'apps.gcd.views.search.series_and_issue'),
    (r'^series/name/(?P<series_name>.+)/$',
     'apps.gcd.views.search.series_by_name'),

    # Series index and cover status / gallery
    (r'^series/(?P<series_id>\d+)/status/$',
     'apps.gcd.views.details.status'),

    (r'^series/(?P<series_id>\d+)/covers/$',
     'apps.gcd.views.details.covers'),

    (r'^series/(?P<series_id>\d+)/scans/$',
     'apps.gcd.views.details.scans'),

    # Issue
    (r'^issue/(?P<issue_id>\d+)/$', 'apps.gcd.views.details.issue'),
    (r'^issue/$', 'apps.gcd.views.details.issue_form'),

    # Single Cover
    (r'^issue/(?P<issue_id>\d+)/cover/(?P<size>\d+)/$',
     'apps.gcd.views.details.cover'),

    # Attribute searches
    (r'^character/name/(?P<character_name>.+)/sort/(?P<sort>.+)/$',
     'apps.gcd.views.search.character_by_name'),
    (r'^character/name/(?P<character_name>.+)/$',
     'apps.gcd.views.search.character_by_name'),

    (r'^writer/name/(?P<writer>.+)/sort/(?P<sort>.+)/$',
     'apps.gcd.views.search.writer_by_name'),
    (r'^writer/name/(?P<writer>.+)/$',
     'apps.gcd.views.search.writer_by_name'),

    (r'^penciller/name/(?P<penciller>.+)/sort/(?P<sort>.+)/$',
     'apps.gcd.views.search.penciller_by_name'),
    (r'^penciller/name/(?P<penciller>.+)/$',
     'apps.gcd.views.search.penciller_by_name'),

    (r'^inker/name/(?P<inker>.+)/sort/(?P<sort>.+)/$',
     'apps.gcd.views.search.inker_by_name'),
    (r'^inker/name/(?P<inker>.+)/$',
     'apps.gcd.views.search.inker_by_name'),

    (r'^colorist/name/(?P<colorist>.+)/sort/(?P<sort>.+)/$',
     'apps.gcd.views.search.colorist_by_name'),
    (r'^colorist/name/(?P<colorist>.+)/$',
     'apps.gcd.views.search.colorist_by_name'),

    (r'^letterer/name/(?P<letterer>.+)/sort/(?P<sort>.+)/$',
     'apps.gcd.views.search.letterer_by_name'),
    (r'^letterer/name/(?P<letterer>.+)/$',
     'apps.gcd.views.search.letterer_by_name'),

    (r'^editor/name/(?P<editor>.+)/sort/(?P<sort>.+)/$',
     'apps.gcd.views.search.editor_by_name'),
    (r'^editor/name/(?P<editor>.+)/$',
     'apps.gcd.views.search.editor_by_name'),

    (r'^story/name/(?P<title>.+)/sort/(?P<sort>.+)/$',
     'apps.gcd.views.search.story_by_title'),
    (r'^story/name/(?P<title>.+)/$',
     'apps.gcd.views.search.story_by_title'),

    (r'^feature/name/(?P<feature>.+)/sort/(?P<sort>.+)/$',
     'apps.gcd.views.search.story_by_feature'),
    (r'^feature/name/(?P<feature>.+)/$',
     'apps.gcd.views.search.story_by_feature'),

    (r'^credit/name/(?P<name>.+)/sort/(?P<sort>.+)/$',
     'apps.gcd.views.search.story_by_credit'),
    (r'^credit/name/(?P<name>.+)/$',
     'apps.gcd.views.search.story_by_credit'),

    # Note that Jobs don't have 'name' in the path, but otherwise work the same.
    (r'^job_number/name/(?P<number>.+)/sort/(?P<sort>.+)/$',
     'apps.gcd.views.search.story_by_job_number_name'),
    (r'^job_number/name/(?P<number>.+)/$',
     'apps.gcd.views.search.story_by_job_number_name'),
    (r'^job_number/(?P<number>.+)/sort/(?P<sort>.+)/$',
     'apps.gcd.views.search.story_by_job_number'),
    (r'^job_number/(?P<number>.+)/$',
     'apps.gcd.views.search.story_by_job_number'),

    # show covers uploaded on a particular date
    url(r'^daily_covers/$',
     'apps.gcd.views.details.daily_covers', name='covers_today'),
    url(r'^daily_covers/(?P<show_date>.+)/$',
     'apps.gcd.views.details.daily_covers', name='covers_by_date'),

    # upload of covers
    (r'^cover_upload/(?P<issue_id>.+)/$', 'apps.gcd.views.covers.cover_upload'),
    (r'^variant_upload/(?P<issue_id>.+)/$',
      'apps.gcd.views.covers.variant_upload'),

    # list covers marked for replacement
    (r'^covers_to_replace/$',
     'apps.gcd.views.details.covers_to_replace'),    
    (r'^covers_to_replace/with/(?P<starts_with>.+)/$',
     'apps.gcd.views.details.covers_to_replace'),    

    # Reprints
    (r'^reprint/(?P<reprints>.+)/sort/(?P<sort>.+)/$',
     'apps.gcd.views.search.story_by_reprint'),
    (r'^reprint/(?P<reprints>.+)/$',
     'apps.gcd.views.search.story_by_reprint'),
    (r'^settings/$',
     'apps.gcd.views.settings.settings'),    
)
