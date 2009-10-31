from django.conf.urls.defaults import *
from django.conf import settings
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.views.generic.simple import direct_to_template

from apps.gcd.views import accounts as account_views
from apps.gcd.views import error_view
from apps.gcd.forms.accounts import PasswordResetForm

urlpatterns = patterns('',
    (r'^admin/', include(admin.site.urls)),

    # Account management

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
        direct_to_template,
        { 'template': 'gcd/accounts/welcome.html' },
        name='welcome'),
    url(r'^accounts/confirm/$',
        direct_to_template,
        { 'template': 'gcd/accounts/confirm_instructions.html' },
        name='confirm_instructions'),
    url(r'^accounts/confirm/(?P<key>[0-9a-f]+)/$',
        account_views.confirm_account,
        name='confirm'),
    url(r'^accounts/mentor/(?P<indexer_id>\d+)/$',
        account_views.mentor,
        name='mentor'),
    url(r'^accounts/forgot/$',
        auth_views.password_reset, 
        { 'post_reset_redirect': 'done',
          'template_name': 'gcd/accounts/password_reset_form.html',
          'email_template_name' : 'gcd/accounts/password_reset_email.html'},
        name='forgot_password'),
    url(r'^accounts/forgot/done/$', auth_views.password_reset_done,
        { 'template_name': 'gcd/accounts/password_reset_done.html'}),
    url(r'^accounts/reset/(?P<uidb36>[0-9A-Za-z]+)-(?P<token>.+)/$', 
	auth_views.password_reset_confirm,
        { 'template_name': 'gcd/accounts/password_reset_confirm.html',
          'set_password_form': PasswordResetForm,
          'post_reset_redirect': '/accounts/reset/done' }),
    url(r'^accounts/reset/done/$', 
        auth_views.password_reset_complete,
        { 'template_name': 'gcd/accounts/password_reset_complete.html'}),

    url(r'gcd-error/$', error_view, name='error'),

    url(r'^donate/$', direct_to_template,
        { 'template': 'gcd/donate/donate.html' }, name='donate'),
    url(r'^donate/thanks/$', direct_to_template,
        { 'template': 'gcd/donate/thanks.html' }, name='donate_thanks'),

    (r'^', include('apps.gcd.urls')),
    (r'^', include('apps.oi.urls')),
)

if settings.DEBUG:
    urlpatterns += patterns('',
        (r'site_media/(?P<path>.*)$', 'django.views.static.serve',
         { 'document_root' : settings.MEDIA_ROOT }))
