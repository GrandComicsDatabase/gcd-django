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
    url(r'^search/advanced/$', 'apps.gcd.views.search.advanced_search',
      name='advanced_search'),
    url(r'^search/advanced/process/$',
     'apps.gcd.views.search.process_advanced',
      name='process_advanced_search'),

    url(r'^(?P<model_name>\w+)/(?P<id>\d+)/history/$',
     'apps.gcd.views.details.change_history', name='change_history'),

    # Publisher
    (r'^publisher/(?P<publisher_id>\d+)/$',
     'apps.gcd.views.details.publisher'),
    (r'^publisher/name/(?P<publisher_name>.+)/sort/(?P<sort>.+)/$',
     'apps.gcd.views.search.publishers_by_name'),
    (r'^publisher/name/(?P<publisher_name>.+)/$',
     'apps.gcd.views.search.publishers_by_name'),
    (r'^publisher/(?P<publisher_id>\d+)/indicia_publishers/$',
     'apps.gcd.views.details.indicia_publishers'),
    (r'^publisher/(?P<publisher_id>\d+)/brands/$',
     'apps.gcd.views.details.brands'),
    (r'^publisher/(?P<publisher_id>\d+)/imprints/$',
     'apps.gcd.views.details.imprints'),

    url(r'^brand/(?P<brand_id>\d+)/$',
     'apps.gcd.views.details.brand', name='show_brand'),
    url(r'^indicia_publisher/(?P<indicia_publisher_id>\d+)/$',
     'apps.gcd.views.details.indicia_publisher', name='show_indicia_publisher'),
    (r'^imprint/(?P<imprint_id>\d+)/$',
     'apps.gcd.views.details.imprint'),

    # Series
    (r'^series/(?P<series_id>\d+)/$', 'apps.gcd.views.details.series'),
    (r'^series/name/(?P<series_name>.+)/sort/(?P<sort>.+)/$',
     'apps.gcd.views.search.series_by_name'),
    url(r'^series/(?P<series_id>\d+)/details/$',
      'apps.gcd.views.details.series_details',
      name='series_details'),
    url(r'^series/(?P<series_id>\d+)/details/timeline/$',
      'apps.gcd.views.details.series_details',
      {'by_date': True },
      name='series_timeline'),
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
    url(r'^issue/(?P<issue_id>\d+)/cover/(?P<size>\d+)/$',
     'apps.gcd.views.details.cover', name='issue_cover_view'),

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

    # show covers/changes from a particular date
    url(r'^daily_covers/$',
     'apps.gcd.views.details.daily_covers', name='covers_today'),
    url(r'^daily_covers/(?P<show_date>.+)/$',
     'apps.gcd.views.details.daily_covers', name='covers_by_date'),
    url(r'^daily_changes/$',
     'apps.gcd.views.details.daily_changes', name='changes_today'),
    url(r'^daily_changes/(?P<show_date>.+)/$',
     'apps.gcd.views.details.daily_changes', name='changes_by_date'),
    url(r'^international_stats/$',
      'apps.gcd.views.details.int_stats', name='international_stats'),

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

    # admin tools
    (r'^countries/$','apps.gcd.views.details.countries_in_use'),

    # redirects of old lasso pages
    (r'^publisher_details.lasso/$', 'apps.gcd.views.redirect.publisher'),
    (r'^series.lasso/$', 'apps.gcd.views.redirect.series'),
    (r'^indexstatus.lasso/$', 'apps.gcd.views.redirect.series_status'),
    (r'^scans.lasso/$', 'apps.gcd.views.redirect.series_scans'),
    (r'^covers.lasso/$', 'apps.gcd.views.redirect.series_covers'),
    (r'^details.lasso/$', 'apps.gcd.views.redirect.issue'),
    (r'^coverview.lasso/$', 'apps.gcd.views.redirect.issue_cover'),
    (r'^daily_covers.lasso/$','apps.gcd.views.redirect.daily_covers'),
    (r'^search.lasso/$','apps.gcd.views.redirect.search'),
)


urlpatterns += patterns('django.views.generic.simple',
    ('^covers_for_replacement.lasso/$', 'redirect_to', 
     {'url' : '/covers_to_replace/' }),
    ('^index.lasso/$', 'redirect_to', {'url' : '/' }),
    ('^donate.lasso/$', 'redirect_to', {'url' : '/donate/' }),
    (r'^graphics/covers/', 'redirect_to', {'url' : None}),
    ('^coversubmit/index.lasso/$', 'redirect_to', {'url' : None})
)
