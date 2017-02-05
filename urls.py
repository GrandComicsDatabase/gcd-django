# -*- coding: utf-8 -*-
from django.conf.urls import patterns, url, include
from django.conf import settings
from django.contrib import admin
from django.views.generic import base as bv
from django.shortcuts import redirect
from django.views.generic.base import TemplateView
from django.contrib.staticfiles.urls import staticfiles_urlpatterns

from apps.indexer.views import error_view
from apps.gcd.views import read_only
from apps.api.urls import router as api_router


admin.autodiscover()


# Note that the structure of the various pattern lists is to facilitate
# future implementation of a read-only mode for the site.  Such a mode
# would use the basic_patterns variable and include the gcd app, but not
# use the account views from the indexer app or include the other apps.

js_info_dict = {
    'packages': ('apps.gcd',),
}

basic_patterns = patterns('',
    # Read-only URLS: basic messages and the gcd display pages.
    url(r'^privacy/$',
        bv.TemplateView.as_view(template_name='gcd/privacy.html'),
        name='privacy'),

    url(r'gcd-error/$', error_view, name='error'),

    url(r'^donate/$',
        bv.TemplateView.as_view(template_name='gcd/donate/donate.html'),
        name='donate'),
    url(r'^donate/thanks/$',
        bv.TemplateView.as_view(template_name='gcd/donate/thanks.html'),
        name='donate_thanks'),
    url(r'^jsi18n/$', 'django.views.i18n.javascript_catalog', js_info_dict),
    url(r'^api/', include(api_router.urls)),
)

read_only_patterns = patterns('',
    url(r'^queues/editing/$', read_only.dummy,
        name='editing'),
    url(r'^upload_cover/(?P<issue_id>\d+)/$', read_only.dummy,
        name='upload_cover'),
    url(r'^edit_covers/(?P<issue_id>\d+)/$', read_only.dummy,
        name='edit_covers'),
    url(r'^(?P<model_name>\w+)/(?P<id>\d+)/upload_image/(?P<image_type>\w+)/$',
        read_only.dummy, name='upload_image'),
    url(r'^(?P<model_name>\w+)/(?P<id>\d+)/replace_image/(?P<image_id>\d+)/$', 
        read_only.dummy, name='replace_image'),
    url(r'^(?P<model_name>\w+)/(?P<id>\d+)/delete/$', read_only.dummy,
        name='delete_revision'),
    url(r'^changeset/(?P<id>\d+)/compare/$', read_only.dummy, name='compare'),
)

if settings.SITE_DOWN:
    class SiteDownTemplateView(TemplateView):
        def get_context_data(self, **kwargs):
            context = super(SiteDownTemplateView, self).get_context_data(**kwargs)
            context.update({'settings': settings})
            return context

    urlpatterns = patterns('',
        (r'^site-down/$', SiteDownTemplateView.as_view(
            template_name='site_down.html')),
        (r'^.*$', lambda request: redirect('/site-down/')),
    )

elif settings.NO_OI:
    urlpatterns = (basic_patterns +
                   patterns('', (r'^', include('apps.gcd.urls'))) +
                   patterns('', (r'^', include('apps.stats.urls'))) +
                   patterns('', (r'^', include('apps.indexer.urls'))) +
                   read_only_patterns
                   )
elif settings.MYCOMICS:
    urlpatterns = (basic_patterns +
                   patterns('', (r'^', include('apps.mycomics.urls'))) +
                   patterns('', (r'^', include('apps.gcd.urls'))) +
                   patterns('', (r'^', include('apps.stats.urls'))) +
                   patterns('', (r'^', include('apps.select.urls'))) +
                   patterns('', (r'^', include('apps.indexer.urls'))) +
                   read_only_patterns
                   )
else:
    urlpatterns = (basic_patterns +
                   patterns('', (r'^', include('apps.gcd.urls'))) +
                   patterns('', (r'^', include('apps.stats.urls'))) +
                   patterns('', (r'^', include('apps.indexer.urls'))) +
                   patterns('', (r'^', include('apps.select.urls'))) +
                   patterns('', (r'^', include('apps.oi.urls')),
                                (r'^voting/', include('apps.voting.urls')),
                                (r'^admin/templatesadmin/',
                                    include('templatesadmin.urls')),
                                (r'^admin/', include(admin.site.urls)),
                                (r'^projects/', include('apps.projects.urls')),
                            )
                   )

if 'django_rq' in settings.INSTALLED_APPS:
    urlpatterns += patterns('',
                            (r'^django-rq/', include('django_rq.urls')),
                            )

# This only has any effect when DEBUG is True.
urlpatterns += staticfiles_urlpatterns()
