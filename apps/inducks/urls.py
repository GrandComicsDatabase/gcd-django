from django.conf.urls.defaults import *
from django.conf import settings
# Uncomment the next two lines to enable the admin:
from django.contrib import admin
admin.autodiscover()

urlpatterns = patterns('',
    # Example:
    # (r'^gcd/', include('gcd.foo.urls')),

    # Uncomment this for admin:
    (r'^admin/(.*)', admin.site.root),

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
    (r'^$', 'apps.inducks.views.index'),

    # Issue
    (r'^issue/(?P<issue_id>.+)/$', 'apps.inducks.views.details.issue'),
    # Series
    (r'^series/(?P<series_id>.+)/$', 'apps.inducks.views.details.series'),

)
