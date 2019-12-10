# -*- coding: utf-8 -*-


from django.conf.urls import url
from django.contrib.auth import views as auth_views
from django.views.generic import base as bv
from django.views.generic.base import TemplateView

from apps.indexer import views as account_views
from apps.indexer.forms import PasswordResetForm, UserContactForm

urlpatterns = [
    # Logout will only look for a 'next_page' parameter in GET, but
    # GET requests should not have side effects so use a wrapper to
    # pull from POST.
    url(r'^accounts/logout/$',
        account_views.logout,
        name='logout'),
    url(r'^accounts/login/$', account_views.login,
        {'template_name': 'indexer/login.html'},
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
        {'edit': True},
        name='edit_profile'),
    url(r'^accounts/welcome/$',
        bv.TemplateView.as_view(template_name='indexer/welcome.html'),
        name='welcome'),
    url(r'^accounts/confirm/$',
        bv.TemplateView.as_view(
            template_name='indexer/confirm_instructions.html'),
        name='confirm_instructions'),
    url(r'^accounts/resend/$',
        bv.TemplateView.as_view(
            template_name='indexer/resend_instructions.html'),
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
        {'post_reset_redirect': 'done',
         'template_name': 'indexer/password_reset_form.html',
         'email_template_name': 'indexer/password_reset_email.html'},
        name='forgot_password'),
    url(r'^accounts/forgot/done/$', auth_views.password_reset_done,
        {'template_name': 'indexer/password_reset_done.html'},
        name='done'),
    url(r'^accounts/reset/(?P<uidb64>[0-9A-Za-z]+)-(?P<token>.+)/$',
        auth_views.password_reset_confirm,
        {'template_name': 'indexer/password_reset_confirm.html',
         'set_password_form': PasswordResetForm,
         'post_reset_redirect': '/accounts/reset/done'},
        name='password_reset_confirm'),
    url(r'^accounts/reset/done/$',
        auth_views.password_reset_complete,
        {'template_name': 'indexer/password_reset_complete.html'}),
    url(r'^accounts/contact/(?P<user_id>\d+)/$',
        account_views.CustomContactFormView.as_view(
            form_class=UserContactForm,
            template_name='indexer/user_contact_form.html',
        ),
        name='user_contact_form'),
    url(r'^accounts/contact/sent/$',
        TemplateView.as_view(
            template_name='indexer/user_contact_form_sent.html'
        ),
        name='user_contact_form_sent'),
]
