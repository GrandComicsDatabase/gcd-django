from django.conf.urls.defaults import *
from django.conf import settings

urlpatterns = patterns('',
    (r'^gcd/', include('apps.gcd.urls')),
    (r'^inducks/', include('apps.inducks.urls')),
)

if settings.DEBUG:
    urlpatterns += patterns('',
        (r'site_media/(?P<path>.*)$', 'django.views.static.serve',
         { 'document_root' : settings.MEDIA_ROOT }))
