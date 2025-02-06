# -*- coding: utf-8 -*-
from django.urls import include, path
from django.conf import settings
from django.urls import path, re_path
from django.contrib import admin
from django.views.generic import base as bv
from django.shortcuts import redirect
from django.views.generic.base import TemplateView
from django.views.i18n import JavaScriptCatalog
from django.contrib.staticfiles.urls import staticfiles_urlpatterns

from django_contact_form.views import ContactFormView

from apps.indexer.views import error_view
from apps.gcd.views import read_only
from apps.api.urls import router as api_router


from apps.gcd.forms.contact import CustomContactForm

admin.autodiscover()


# Note that the structure of the various pattern lists is to facilitate
# future implementation of a read-only mode for the site.  Such a mode
# would use the basic_patterns variable and include the gcd app, but not
# use the account views from the indexer app or include the other apps.

js_info_dict = {
    'packages': ['apps.gcd',],
}

basic_patterns = [
    # Read-only URLS: basic messages and the gcd display pages.
    path('privacy/',
        bv.TemplateView.as_view(template_name='gcd/privacy.html'),
        name='privacy'),

    path('gcd-error/', error_view, name='error'),

    path('donate/',
        bv.TemplateView.as_view(template_name='gcd/donate/donate.html'),
        name='donate'),
    path('donate/thanks/',
        bv.TemplateView.as_view(template_name='gcd/donate/thanks.html'),
        name='donate_thanks'),
    path('jsi18n/', JavaScriptCatalog.as_view(**js_info_dict),
        name='javascript-catalog'),
    path('contact/',
        ContactFormView.as_view(
            form_class=CustomContactForm
        ),
        name='contact_form'),
    path('contact/sent/',
        TemplateView.as_view(
            template_name='django_contact_form/contact_form_sent.html'
        ),
        name='contact_form_sent'),
    path('api/', include(api_router.urls)),
]

read_only_patterns = [
    path('queues/editing/', read_only.dummy,
        name='editing'),
    path('upload_cover/<int:issue_id>/', read_only.dummy,
        name='upload_cover'),
    path('edit_covers/<int:issue_id>/', read_only.dummy,
        name='edit_covers'),
    re_path(r'^(?P<model_name>\w+)/(?P<id>\d+)/upload_image/(?P<image_type>\w+)/$', 
        read_only.dummy, name='upload_image'),
    re_path(r'^(?P<model_name>\w+)/(?P<id>\d+)/replace_image/(?P<image_id>\d+)/$', 
        read_only.dummy, name='replace_image'),
    re_path(r'^(?P<model_name>\w+)/(?P<id>\d+)/delete/$', read_only.dummy,
        name='delete_revision'),
    path('changeset/<int:id>/compare/', read_only.dummy, name='compare'),
]

if settings.SITE_DOWN:
    class SiteDownTemplateView(TemplateView):
        def get_context_data(self, **kwargs):
            context = super(SiteDownTemplateView, self).get_context_data(**kwargs)
            context.update({'settings': settings})
            return context

    urlpatterns = [
        path('site-down/',  SiteDownTemplateView.as_view(
            template_name= 'site_down.html')),
        re_path(r'^.*$', lambda request: redirect('/site-down/')),
    ]

elif settings.NO_OI:
    urlpatterns = basic_patterns + \
                    [path('', include('apps.gcd.urls'))] + \
                    [path('', include('apps.stats.urls'))] + \
                    [path('', include('apps.indexer.urls'))] + \
                    read_only_patterns
elif settings.MYCOMICS:
    urlpatterns = basic_patterns + \
                    [path('', include('apps.mycomics.urls'))] + \
                    [path('', include('apps.gcd.urls'))] + \
                    [path('', include('apps.stats.urls'))] + \
                    [path('', include('apps.indexer.urls'))] + \
                    [path('', include('apps.select.urls'))] + \
                    read_only_patterns
else:
    urlpatterns = basic_patterns + \
                    [path('', include('apps.gcd.urls'))] + \
                    [path('', include('apps.stats.urls'))] + \
                    [path('', include('apps.indexer.urls'))] + \
                    [path('', include('apps.select.urls'))] + \
                    [path('', include('apps.oi.urls'))] + \
                    [path('api/', include('apps.api.urls'))] + \
                    [path('voting/', include('apps.voting.urls'))] + \
                    [path('admin/templatesadmin/', include('templatesadmin.urls'))] + \
                    [path('admin/', admin.site.urls)] + \
                    [path('projects/', include('apps.projects.urls'))]

if 'django_rq' in settings.INSTALLED_APPS:
    urlpatterns += [path('django-rq/', include('django_rq.urls'))]

if 'rosetta' in settings.INSTALLED_APPS:
    urlpatterns += [path('rosetta/', include('rosetta.urls'))]

if 'drf_spectacular' in settings.INSTALLED_APPS:
    from drf_spectacular.views import SpectacularAPIView, \
                                      SpectacularRedocView, \
                                      SpectacularSwaggerView

    urlpatterns += [path('api/schema/', SpectacularAPIView.as_view(),
                         name='schema'),
                    path('api/schema/swagger-ui/',
                         SpectacularSwaggerView.as_view(url_name='schema'),
                         name='swagger-ui'),
                    path('api/schema/redoc/',
                         SpectacularRedocView.as_view(url_name='schema'),
                         name='redoc'),
                    ]

if settings.DEBUG and 'debug_toolbar' in settings.INSTALLED_APPS:
    import debug_toolbar
    urlpatterns += [
        path('__debug__/', include(debug_toolbar.urls)),
    ]

# This only has any effect when DEBUG is True.
urlpatterns += staticfiles_urlpatterns()
