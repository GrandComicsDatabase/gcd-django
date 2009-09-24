from django.conf.urls.defaults import *
from django.conf import settings
from django.contrib import admin
from django.contrib.auth import views as auth_views

urlpatterns = patterns('',
    (r'^admin/', include(admin.site.urls)),

    # Account management
    (r'^accounts/logout/', auth_views.logout),
    (r'^accounts/login/$', auth_views.login, 
     {'template_name': 'gcd/accounts/login.html'}),
    (r'^accounts/profile/$', 'apps.gcd.views.accounts.profile'),

    (r'^', include('apps.gcd.urls')),
    (r'^', include('apps.oi.urls')),
    # (r'^inducks/', include('apps.inducks.urls')),
)

if settings.DEBUG:
    urlpatterns += patterns('',
        (r'site_media/(?P<path>.*)$', 'django.views.static.serve',
         { 'document_root' : settings.MEDIA_ROOT }))
