# -*- coding: utf-8 -*-
from django.conf.urls import url
from django.conf import settings
from django.views.generic import base as bv
from haystack.forms import FacetedSearchForm
from haystack.views import search_view_factory
from apps.gcd.views.search_haystack import PaginatedFacetedSearchView, \
    GcdSearchQuerySet

from apps.gcd import views as gcd_views
import apps.gcd.views.details
import apps.gcd.views.search
import apps.gcd.views.redirect

urlpatterns = [
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

    url(r'^$', gcd_views.index, name='home'),
    url(r'^search/$', gcd_views.search.search, name='basic_search'),
    url(r'^search/advanced/$', gcd_views.search.advanced_search,
      name='advanced_search'),
    url(r'^search/advanced/process/csv/$', gcd_views.search.process_advanced,
      {'export_csv': True}, name='process_advanced_search_csv'),
    url(r'^search/advanced/process/$', gcd_views.search.process_advanced,
      name='process_advanced_search'),

    url(r'^(?P<model_name>\w+)/(?P<id>\d+)/history/$',
     gcd_views.details.change_history, name='change_history'),

    # Publisher
    url(r'^publisher/(?P<publisher_id>\d+)/$',
      gcd_views.details.publisher, name='show_publisher'),
    url(r'^publisher/name/(?P<publisher_name>.+)/sort/(?P<sort>.+)/$',
     gcd_views.search.publisher_by_name, name='publisher_by_name'),
    url(r'^publisher/name/(?P<publisher_name>.+)/$',
     gcd_views.search.publisher_by_name, name='publisher_by_name'),
    url(r'^publisher/(?P<publisher_id>\d+)/indicia_publishers/$',
     gcd_views.details.indicia_publishers),
    url(r'^publisher/(?P<publisher_id>\d+)/brands/$',
      gcd_views.details.brands),
    url(r'^publisher/(?P<publisher_id>\d+)/brand_uses/$',
      gcd_views.details.brand_uses),
    url(r'^publisher/(?P<publisher_id>\d+)/monthly_covers_on_sale/$',
      gcd_views.details.publisher_monthly_covers,
      {'use_on_sale': True }, name='publisher_monthly_covers_on_sale'),
    url(r'^publisher/(?P<publisher_id>\d+)/monthly_covers_on_sale/year/(?P<year>\d{4})/month/(?P<month>\d{1,2})/$',
      gcd_views.details.publisher_monthly_covers,
      {'use_on_sale': True }, name='publisher_monthly_covers_on_sale'),
    url(r'^publisher/(?P<publisher_id>\d+)/monthly_covers_pub_date/$',
      gcd_views.details.publisher_monthly_covers,
      {'use_on_sale': False }, name='publisher_monthly_covers_pub_date'),
    url(r'^publisher/(?P<publisher_id>\d+)/monthly_covers_pub_date/year/(?P<year>\d{4})/month/(?P<month>\d{1,2})/$',
      gcd_views.details.publisher_monthly_covers,
      {'use_on_sale': False }, name='publisher_monthly_covers_pub_date'),

    url(r'^brand_group/(?P<brand_group_id>\d+)/$',
      gcd_views.details.brand_group, name='show_brand_group'),
    url(r'^brand_group/name/(?P<brand_group_name>.+)/sort/(?P<sort>.+)/$',
      gcd_views.search.brand_group_by_name,
      name='brand_group_by_name'),
    url(r'^brand_group/name/(?P<brand_group_name>.+)/$',
      gcd_views.search.brand_group_by_name,
      name='brand_group_by_name'),

    url(r'^brand/(?P<brand_id>\d+)/$',
      gcd_views.details.brand, name='show_brand'),
    url(r'^brand/name/(?P<brand_name>.+)/sort/(?P<sort>.+)/$',
      gcd_views.search.brand_by_name, name='brand_by_name'),
    url(r'^brand/name/(?P<brand_name>.+)/$',
      gcd_views.search.brand_by_name, name='brand_by_name'),

    url(r'^indicia_publisher/(?P<indicia_publisher_id>\d+)/$',
      gcd_views.details.indicia_publisher, name='show_indicia_publisher'),
    url(r'^indicia_publisher/name/(?P<ind_pub_name>.+)/sort/(?P<sort>.+)/$',
      gcd_views.search.indicia_publisher_by_name,
      name='indicia_publisher_by_name'),
    url(r'^indicia_publisher/name/(?P<ind_pub_name>.+)/$',
      gcd_views.search.indicia_publisher_by_name,
      name='indicia_publisher_by_name'),

    url(r'^award/(?P<award_id>\d+)/$',
      gcd_views.details.award, name='show_award'),
    url(r'^award/name/(?P<award_name>.+)/sort/(?P<sort>.+)/$',
      gcd_views.search.award_by_name, name='award_by_name'),
    url(r'^award/name/(?P<award_name>.+)/$',
      gcd_views.search.award_by_name, name='award_by_name'),

    url(r'^creator/(?P<creator_id>\d+)/$',
      gcd_views.details.creator, name='show_creator'),
    url(r'^creator/name/(?P<creator_name>.+)/sort/(?P<sort>.+)/$',
      gcd_views.search.creator_by_name,
      name='creator_by_name'),
    url(r'^creator/name/(?P<creator_name>.+)/$',
      gcd_views.search.creator_by_name,
      name='creator_by_name'),

    url(r'^creator_membership/(?P<creator_membership_id>\d+)/$',
      gcd_views.details.creator_membership, name='show_creator_membership'),
    url(r'^creator_membership/name/(?P<creator_membership_name>.+)/sort/(?P<sort>.+)/$',
      gcd_views.search.creator_membership_by_name,
      name='creator_membership_by_name'),
    url(r'^creator_membership/name/(?P<creator_membership_name>.+)/$',
      gcd_views.search.creator_membership_by_name,
      name='creator_membership_by_name'),

    url(r'^creator_award/(?P<creator_award_id>\d+)/$',
      gcd_views.details.creator_award, name='show_creator_award'),
    url(r'^creator_award/name/(?P<creator_award_name>.+)/sort/(?P<sort>.+)/$',
      gcd_views.search.creator_award_by_name,
      name='creator_award_by_name'),
    url(r'^creator_award/name/(?P<creator_award_name>.+)/$',
      gcd_views.search.creator_award_by_name,
      name='creator_award_by_name'),

    url(r'^creator_art_influence/(?P<creator_art_influence_id>\d+)/$',
      gcd_views.details.creator_art_influence, name='show_creator_art_influence'),
    url(r'^creator_art_influence/name/(?P<creator_art_influence_name>.+)/sort/(?P<sort>.+)/$',
      gcd_views.search.creator_art_influence_by_name,
      name='creator_art_influence_by_name'),
    url(r'^creator_art_influence/name/(?P<creator_art_influence_name>.+)/$',
      gcd_views.search.creator_art_influence_by_name,
      name='creator_art_influence_by_name'),

    url(r'^creator_non_comic_work/(?P<creator_non_comic_work_id>\d+)/$',
      gcd_views.details.creator_non_comic_work, name='show_creator_non_comic_work'),
    url(r'^creator_non_comic_work/name/(?P<creator_non_comic_work_name>.+)/sort/(?P<sort>.+)/$',
      gcd_views.search.creator_non_comic_work_by_name,
      name='creator_non_comic_work_by_name'),
    url(r'^creator_non_comic_work/name/(?P<creator_non_comic_work_name>.+)/$',
      gcd_views.search.creator_non_comic_work_by_name,
      name='creator_non_comic_work_by_name'),

    url(r'^creator_relation/(?P<creator_relation_id>\d+)/$',
      gcd_views.details.creator_relation, name='show_creator_relation'),

    url(r'^creator_school/(?P<creator_school_id>\d+)/$',
      gcd_views.details.creator_school, name='show_creator_school'),
    url(r'^creator_degree/(?P<creator_degree_id>\d+)/$',
      gcd_views.details.creator_degree, name='show_creator_degree'),

    url(r'^imprint/(?P<imprint_id>\d+)/$', gcd_views.details.imprint,
      name='show_imprint'),

    # Series
    url(r'^series/(?P<series_id>\d+)/$',
      gcd_views.details.series, name='show_series'),
    url(r'^series/name/(?P<series_name>.+)/sort/(?P<sort>.+)/$',
      gcd_views.search.series_by_name, name='series_by_name'),
    url(r'^series/(?P<series_id>\d+)/details/$',
      gcd_views.details.series_details,
      name='series_details'),
    url(r'^series/(?P<series_id>\d+)/details/timeline/$',
      gcd_views.details.series_details,
      {'by_date': True },
      name='series_timeline'),
    # Series and Issue
    url(r'^series/name/(?P<series_name>.+)/issue/(?P<issue_nr>.+)/$',
      gcd_views.search.series_and_issue),
    url(r'^series/name/(?P<series_name>.+)/$',
      gcd_views.search.series_by_name, name='series_by_name'),

    # Series index and cover status / gallery
    url(r'^series/(?P<series_id>\d+)/status/$',
      gcd_views.details.status, name='series_status'),

    url(r'^series/(?P<series_id>\d+)/covers/$',
      gcd_views.details.covers, name='series_covers'),

    url(r'^series/(?P<series_id>\d+)/scans/$',
      gcd_views.details.scans, name='series_scan_table'),

    # Issue
    url(r'^issue/(?P<issue_id>\d+)/$',
      gcd_views.details.issue, name='show_issue'),
    url(r'^issue/$', gcd_views.details.issue_form, name='issue_select_form'),
    # ISBNs don't have 'name' in the path, but otherwise work the same
    url(r'^isbn/name/(?P<isbn>.+)/sort/(?P<sort>.+)/$',
      gcd_views.search.issue_by_isbn_name),
    url(r'^isbn/name/(?P<isbn>.+)/$',
      gcd_views.search.issue_by_isbn_name),
    url(r'^isbn/(?P<isbn>.+)/sort/(?P<sort>.+)/$',
      gcd_views.search.issue_by_isbn),
    url(r'^isbn/(?P<isbn>.+)/$',
      gcd_views.search.issue_by_isbn),
    # barcodes don't have 'name' in the path, but otherwise work the same
    url(r'^barcode/name/(?P<barcode>.+)/sort/(?P<sort>.+)/$',
      gcd_views.search.issue_by_barcode_name),
    url(r'^barcode/name/(?P<barcode>.+)/$',
      gcd_views.search.issue_by_barcode_name),
    url(r'^barcode/(?P<barcode>.+)/sort/(?P<sort>.+)/$',
      gcd_views.search.issue_by_barcode),
    url(r'^barcode/(?P<barcode>.+)/$',
      gcd_views.search.issue_by_barcode),

    # Single Cover
    url(r'^issue/(?P<issue_id>\d+)/cover/(?P<size>\d+)/$',
      gcd_views.details.cover, name='issue_cover_view'),

    # Images for Issue
    url(r'^issue/(?P<issue_id>\d+)/image/$',
      gcd_views.details.issue_images, name='issue_images'),

    # Attribute searches
    url(r'^character/name/(?P<character_name>.+)/sort/(?P<sort>.+)/$',
      gcd_views.search.character_by_name, name='character_by_name'),
    url(r'^character/name/(?P<character_name>.+)/$',
      gcd_views.search.character_by_name, name='character_by_name'),

    url(r'^writer/name/(?P<writer>.+)/sort/(?P<sort>.+)/$',
      gcd_views.search.writer_by_name, name='writer_by_name'),
    url(r'^writer/name/(?P<writer>.+)/$',
      gcd_views.search.writer_by_name, name='writer_by_name'),

    url(r'^penciller/name/(?P<penciller>.+)/sort/(?P<sort>.+)/$',
      gcd_views.search.penciller_by_name, name='penciller_by_name'),
    url(r'^penciller/name/(?P<penciller>.+)/$',
      gcd_views.search.penciller_by_name, name='penciller_by_name'),

    url(r'^inker/name/(?P<inker>.+)/sort/(?P<sort>.+)/$',
      gcd_views.search.inker_by_name, name='inker_by_name'),
    url(r'^inker/name/(?P<inker>.+)/$',
      gcd_views.search.inker_by_name, name='inker_by_name'),

    url(r'^colorist/name/(?P<colorist>.+)/sort/(?P<sort>.+)/$',
      gcd_views.search.colorist_by_name, name='colorist_by_name'),
    url(r'^colorist/name/(?P<colorist>.+)/$',
      gcd_views.search.colorist_by_name, name='colorist_by_name'),

    url(r'^letterer/name/(?P<letterer>.+)/sort/(?P<sort>.+)/$',
      gcd_views.search.letterer_by_name, name='letterer_by_name'),
    url(r'^letterer/name/(?P<letterer>.+)/$',
      gcd_views.search.letterer_by_name, name='letterer_by_name'),

    url(r'^editor/name/(?P<editor>.+)/sort/(?P<sort>.+)/$',
      gcd_views.search.editor_by_name, name='editor_by_name'),
    url(r'^editor/name/(?P<editor>.+)/$',
      gcd_views.search.editor_by_name, name='editor_by_name'),

    url(r'^story/name/(?P<title>.+)/sort/(?P<sort>.+)/$',
      gcd_views.search.story_by_title),
    url(r'^story/name/(?P<title>.+)/$',
      gcd_views.search.story_by_title),

    url(r'^feature/name/(?P<feature>.+)/sort/(?P<sort>.+)/$',
      gcd_views.search.story_by_feature),
    url(r'^feature/name/(?P<feature>.+)/$',
      gcd_views.search.story_by_feature),

    url(r'^credit/name/(?P<name>.+)/sort/(?P<sort>.+)/$',
      gcd_views.search.story_by_credit),
    url(r'^credit/name/(?P<name>.+)/$',
      gcd_views.search.story_by_credit),

    # Special display pages
    url(r'^checklist/name/(?P<creator>.+)/country/(?P<country>.+)/$',
      gcd_views.search.checklist_by_name, name='checklist_by_name'),
    url(r'^checklist/name/(?P<creator>.+)/language/(?P<language>.+)/$',
      gcd_views.search.checklist_by_name, name='checklist_by_name'),
    url(r'^checklist/name/(?P<creator>.+)/$',
      gcd_views.search.checklist_by_name, name='checklist_by_name'),

    # Note that Jobs don't have 'name' in the path, but otherwise work the same.
    url(r'^job_number/name/(?P<number>.+)/sort/(?P<sort>.+)/$',
      gcd_views.search.story_by_job_number_name),
    url(r'^job_number/name/(?P<number>.+)/$',
      gcd_views.search.story_by_job_number_name),
    url(r'^job_number/(?P<number>.+)/sort/(?P<sort>.+)/$',
      gcd_views.search.story_by_job_number),
    url(r'^job_number/(?P<number>.+)/$',
      gcd_views.search.story_by_job_number),

    # show covers/changes from a particular date
    url(r'^daily_covers/$',
      gcd_views.details.daily_covers, name='covers_today'),
    url(r'^daily_covers/(?P<show_date>.+)/$',
      gcd_views.details.daily_covers, name='covers_by_date'),
    url(r'^daily_changes/$',
      gcd_views.details.daily_changes, name='changes_today'),
    url(r'^daily_changes/(?P<show_date>.+)/$',
      gcd_views.details.daily_changes, name='changes_by_date'),
    url(r'^on_sale_weekly/$',
      gcd_views.details.on_sale_weekly, name='on_sale_this_week'),
    url(r'^on_sale_weekly/(?P<year>\d{4})/week/(?P<week>\d{1,2})/$',
      gcd_views.details.on_sale_weekly, name='on_sale_weekly'),

    url(r'^international_stats_language/$',
      gcd_views.details.int_stats_language,
      name='international_stats_language'),
    url(r'^international_stats_country/$',
      gcd_views.details.int_stats_country,
      name='international_stats_country'),

    # list covers marked for replacement
    url(r'^covers_to_replace/$',
      gcd_views.details.covers_to_replace),
    url(r'^covers_to_replace/with/(?P<starts_with>.+)/$',
     gcd_views.details.covers_to_replace),

    # Reprints
    url(r'^reprint/name/(?P<reprints>.+)/sort/(?P<sort>.+)/$',
      gcd_views.search.story_by_reprint),
    url(r'^reprint/name/(?P<reprints>.+)/$',
      gcd_views.search.story_by_reprint),

    # calendar
    url(r'^agenda/(?P<language>.+)/$',gcd_views.details.agenda),
    url(r'^agenda/',gcd_views.details.agenda, {'language' : 'en'}),
    url(r'^calendar/$',
     bv.TemplateView.as_view(template_name='gcd/status/calendar.html')),

    # admin tools
    url(r'^countries/$',gcd_views.details.countries_in_use),

    # redirects of old lasso pages
    url(r'^publisher_details.lasso/$', gcd_views.redirect.publisher),
    url(r'^series.lasso/$', gcd_views.redirect.series),
    url(r'^indexstatus.lasso/$', gcd_views.redirect.series_status),
    url(r'^scans.lasso/$', gcd_views.redirect.series_scans),
    url(r'^covers.lasso/$', gcd_views.redirect.series_covers),
    url(r'^details.lasso/$', gcd_views.redirect.issue),
    url(r'^coverview.lasso/$', gcd_views.redirect.issue_cover),
    url(r'^daily_covers.lasso/$',gcd_views.redirect.daily_covers),
    url(r'^search.lasso/$',gcd_views.redirect.search),
]

# haystack search
sqs = GcdSearchQuerySet().facet('facet_model_name').facet('country') \
                         .facet('language').facet('publisher').facet('feature')

urlpatterns += [url(r'^searchNew/',
                search_view_factory(
                  view_class=PaginatedFacetedSearchView,
                  form_class=FacetedSearchForm, searchqueryset=sqs),
                name='haystack_search'),
]

urlpatterns += [
    url(r'^international_stats/$',
     bv.RedirectView.as_view(url='/international_stats_language/',
                             permanent=True)),
    url('^covers_for_replacement.lasso/$',
      bv.RedirectView.as_view(url='/covers_to_replace/',
                              permanent=True)),
    url('^index.lasso/$', bv.RedirectView.as_view(url='/', permanent=True)),
    url('^donate.lasso/$', bv.RedirectView.as_view(url='/donate/',
                                                permanent=True)),
    url(r'^graphics/covers/', bv.RedirectView.as_view(url=None, permanent=True)),
    url('^coversubmit/index.lasso/$', bv.RedirectView.as_view(url=None,
                                                           permanent=True)),
    url(r'^creator_checklist/name/(?P<creator>.+)/country/(?P<country>.+)/$',
      bv.RedirectView.as_view(
        url='/checklist/name/%(creator)s/country/%(country)s/',
        permanent=True)),
    url(r'^creator_checklist/name/(?P<creator>.+)/language/(?P<language>.+)/$',
      bv.RedirectView.as_view(
        url='/checklist/name/%(creator)s/language/%(language)s/',
        permanent=True)),
    url(r'^creator_checklist/name/(?P<creator>.+)/$',
      bv.RedirectView.as_view(url='/checklist/name/%(creator)s/',
                              permanent=True))
]
