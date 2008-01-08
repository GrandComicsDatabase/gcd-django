from django.conf.urls.defaults import *
from django.conf import settings

urlpatterns = patterns('',
    # Example:
    # (r'^gcd/', include('gcd.foo.urls')),

    # Uncomment this for admin:
    (r'^admin/', include('django.contrib.admin.urls')),

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

    (r'^gcd/$', 'gcd.views.index'),
    (r'^gcd/search/$', 'gcd.views.search.search'),
    (r'^gcd/search/advanced/$', 'gcd.views.search.advanced_search'),

    (r'^gcd/publisher/(?P<publisher_id>\d+)/$', 'gcd.views.details.publisher'),
    (r'^gcd/publisher/name/(?P<publisher_name>.+)/sort/(?P<sort>.+)/$',
     'gcd.views.search.publishers_by_name'),
    (r'^gcd/publisher/name/(?P<publisher_name>.+)/$',
     'gcd.views.search.publishers_by_name'),
    (r'^gcd/publisher/(?P<publisher_id>\d+)/imprints/$',
     'gcd.views.search.imprints_by_publisher'),

    (r'^gcd/series/(?P<series_id>\d+)/$', 'gcd.views.details.series'),
    (r'^gcd/series/name/(?P<series_name>.+)/sort/(?P<sort>.+)/$',
     'gcd.views.search.series_by_name'),
    (r'^gcd/series/name/(?P<series_name>.+)/$',
     'gcd.views.search.series_by_name'),

    (r'^gcd/issue/(?P<issue_id>\d+)/$', 'gcd.views.details.issue'),
    (r'^gcd/issue/$', 'gcd.views.details.issue_form'),

    (r'^gcd/character/name/(?P<character_name>.+)/sort/(?P<sort>.+)/$',
     'gcd.views.search.character_appearances'),
    (r'^gcd/character/name/(?P<character_name>.+)/$',
     'gcd.views.search.character_appearances'),

    (r'^gcd/writer/name/(?P<writer>.+)/sort/(?P<sort>.+)/$',
     'gcd.views.search.writer_by_name'),
    (r'^gcd/writer/name/(?P<writer>.+)/$',
     'gcd.views.search.writer_by_name'),

    (r'^gcd/penciller/name/(?P<penciller>.+)/sort/(?P<sort>.+)/$',
     'gcd.views.search.penciller_by_name'),
    (r'^gcd/penciller/name/(?P<penciller>.+)/$',
     'gcd.views.search.penciller_by_name'),

    (r'^gcd/inker/name/(?P<inker_name>.+)/sort/(?P<sort>.+)/$',
     'gcd.views.search.inker_by_name'),
    (r'^gcd/inker/name/(?P<inker_name>.+)/$',
     'gcd.views.search.inker_by_name'),

    (r'^gcd/colorist/name/(?P<colorist_name>.+)/sort/(?P<sort>.+)/$',
     'gcd.views.search.colorist_by_name'),
    (r'^gcd/colorist/name/(?P<colorist_name>.+)/$',
     'gcd.views.search.colorist_by_name'),

    (r'^gcd/letterer/name/(?P<letterer_name>.+)/sort/(?P<sort>.+)/$',
     'gcd.views.search.letterer_by_name'),
    (r'^gcd/letterer/name/(?P<letterer_name>.+)/$',
     'gcd.views.search.letterer_by_name'),

    (r'^gcd/editor/name/(?P<editor_name>.+)/sort/(?P<sort>.+)/$',
     'gcd.views.search.editor_by_name'),
    (r'^gcd/editor/name/(?P<editor_name>.+)/$',
     'gcd.views.search.editor_by_name'),

    (r'^gcd/story/name/(?P<title>.+)/sort/(?P<sort>.+)/$',
     'gcd.views.search.story_by_title'),
    (r'^gcd/story/name/(?P<title>.+)/$',
     'gcd.views.search.story_by_title'),

    (r'^gcd/credit/name/(?P<name>.+)/sort/(?P<sort>.+)/$',
     'gcd.views.search.story_by_credit'),
    (r'^gcd/credit/name/(?P<name>.+)/$',
     'gcd.views.search.story_by_credit'),

    # Odd to list job numbers by 'name' but makes forms consistent.
    # TODO: Fix this, it's weird.
    (r'^gcd/job/name/(?P<number>.+)/sort/(?P<sort>.+)/$',
     'gcd.views.search.story_by_job'),
    (r'^gcd/job/name/(?P<number>.+)/$', 'gcd.views.search.story_by_job'),
)

if settings.DEBUG:
    urlpatterns += patterns('',
        (r'site_media/(?P<path>.*)$', 'django.views.static.serve',
         { 'document_root' : '/Users/handrews/staging/gcd/media' }))
