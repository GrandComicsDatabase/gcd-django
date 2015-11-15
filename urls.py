# -*- coding: utf-8 -*-
from django.conf.urls import patterns, url, include
from django.conf import settings
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.views.generic import base as bv
from django.shortcuts import redirect
from django.views.generic.base import TemplateView

from apps.gcd.views import accounts as account_views
from apps.gcd.views import error_view
from apps.gcd.forms.accounts import PasswordResetForm
from apps.gcd.views import read_only

admin.autodiscover()

# Note that the structure of the various pattern lists is to facilitate
# future implementation of a read-only mode for the site.  Such a mode
# would use the basic_patterns variable and include the gcd app, but not
# use the account_patterns or include the other apps.

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
)

account_patterns = patterns('',
    # Logout will only look for a 'next_page' parameter in GET, but
    # GET requests should not have side effects so use a wrapper to
    # pull from POST.
    url(r'^accounts/logout/$',
        account_views.logout,
        name='logout'),
    url(r'^accounts/login/$', account_views.login, 
        {'template_name': 'gcd/accounts/login.html'},
        name='login'),
    url(r'^accounts/register/$', account_views.register,
        name='register'),
    url(r'^accounts/profile/$', account_views.profile,
        name='default_profile'),
    url(r'^accounts/profile/(?P<user_id>\d+)/$',
        account_views.profile,
        name='view_profile'),
    url(r'^accounts/profile/(?P<user_id>\d+)/edit/$',
        account_views.profile,
        { 'edit': True },
        name='edit_profile'),
    url(r'^accounts/welcome/$',
        bv.TemplateView.as_view(template_name='gcd/accounts/welcome.html'),
        name='welcome'),
    url(r'^accounts/confirm/$',
        bv.TemplateView.as_view(
          template_name='gcd/accounts/confirm_instructions.html'),
        name='confirm_instructions'),
    url(r'^accounts/resend/$',
        bv.TemplateView.as_view(
          template_name='gcd/accounts/resend_instructions.html'),
        name='resend_instructions'),
    url(r'^accounts/confirm/(?P<key>[0-9a-f]+)/$',
        account_views.confirm_account,
        name='confirm'),
    url(r'^accounts/mentor/(?P<indexer_id>\d+)/$',
        account_views.mentor,
        name='mentor'),
    url(r'^accounts/mentor/(?P<indexer_id>\d+)/not_new/$',
        account_views.mentor_not_new,
        name='mentor_not_new'),
    url(r'^accounts/mentor/(?P<indexer_id>\d+)/unmentor/$',
        account_views.unmentor,
        name='unmentor'),
    url(r'^accounts/forgot/$',
        auth_views.password_reset, 
        { 'post_reset_redirect': 'done',
          'template_name': 'gcd/accounts/password_reset_form.html',
          'email_template_name' : 'gcd/accounts/password_reset_email.html'},
        name='forgot_password'),
    url(r'^accounts/forgot/done/$', auth_views.password_reset_done,
        { 'template_name': 'gcd/accounts/password_reset_done.html'}),
    url(r'^accounts/reset/(?P<uidb64>[0-9A-Za-z]+)-(?P<token>.+)/$', 
	auth_views.password_reset_confirm,
        { 'template_name': 'gcd/accounts/password_reset_confirm.html',
          'set_password_form': PasswordResetForm,
          'post_reset_redirect': '/accounts/reset/done' }),
    url(r'^accounts/reset/done/$', 
        auth_views.password_reset_complete,
        { 'template_name': 'gcd/accounts/password_reset_complete.html'}),
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
        (r'^site-down/$',  SiteDownTemplateView.as_view(
            template_name= 'site_down.html')),
        (r'^.*$', lambda request: redirect('/site-down/')),
    )

elif settings.NO_OI:
    urlpatterns = (basic_patterns +
                   patterns('', (r'^', include('apps.gcd.urls'))) +
                   account_patterns +
                   read_only_patterns
                  )
elif settings.MYCOMICS:
    urlpatterns = (basic_patterns +
                   patterns('', (r'^', include('apps.mycomics.urls'))) +
                   patterns('', (r'^', include('apps.gcd.urls'))) +
                   patterns('', (r'^', include('apps.select.urls'))) +
                   account_patterns +
                   read_only_patterns
                   )
else:
    urlpatterns = (basic_patterns +
                   patterns('', (r'^', include('apps.gcd.urls'))) +
                   account_patterns +
                   patterns('', (r'^', include('apps.select.urls'))) +
                   patterns('', (r'^', include('apps.oi.urls')),
                                (r'^voting/', include('apps.voting.urls')),
                                (r'^admin/templatesadmin/', include('templatesadmin.urls')),
                                (r'^admin/', include(admin.site.urls)),
                                (r'^projects/', include('apps.projects.urls')),
                           )
                  )

if settings.DEBUG:
    urlpatterns += patterns('',
        (r'site_media/(?P<path>.*)$', 'django.views.static.serve',
         { 'document_root' : settings.MEDIA_ROOT }))
