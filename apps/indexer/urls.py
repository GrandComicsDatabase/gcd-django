# -*- coding: utf-8 -*-


from django.urls import path, re_path
from django.contrib.auth import views as auth_views
from django.views.generic import base as bv
from django.views.generic.base import TemplateView

from apps.indexer import views as account_views
from apps.indexer.forms import PasswordResetForm, UserContactForm

urlpatterns = [
    # Logout will only look for a 'next_page' parameter in GET, but
    # GET requests should not have side effects so use a wrapper to
    # pull from POST.
    path('accounts/logout/',
        account_views.logout,
        name='logout'),
    path('accounts/login/', account_views.login,
        {'template_name': 'indexer/login.html'},
        name='login'),
    path('accounts/register/', account_views.register,
        name='register'),
    path('accounts/profile/', account_views.profile,
        name='default_profile'),
    path('accounts/profile/<int:user_id>/',
        account_views.profile,
        name='view_profile'),
    path('accounts/profile/<int:user_id>/edit/',
        account_views.profile,
        {'edit': True},
        name='edit_profile'),
    path('accounts/welcome/',
        bv.TemplateView.as_view(template_name='indexer/welcome.html'),
        name='welcome'),
    path('accounts/confirm/',
        bv.TemplateView.as_view(
            template_name='indexer/confirm_instructions.html'),
        name='confirm_instructions'),
    path('accounts/resend/',
        bv.TemplateView.as_view(
            template_name='indexer/resend_instructions.html'),
        name='resend_instructions'),
    re_path(r'^accounts/confirm/(?P<key>[0-9a-f]+)/$',
        account_views.confirm_account,
        name='confirm'),
    path('accounts/mentor/<int:indexer_id>/',
        account_views.mentor,
        name='mentor'),
    path('accounts/mentor/<int:indexer_id>/not_new/',
        account_views.mentor_not_new,
        name='mentor_not_new'),
    path('accounts/mentor/<int:indexer_id>/unmentor/',
        account_views.unmentor,
        name='unmentor'),
    path('accounts/forgot/',
        auth_views.PasswordResetView.as_view(
            template_name='indexer/password_reset_form.html',
            email_template_name='indexer/password_reset_email.html'),
        name='forgot_password'),
    path('accounts/forgot/done/', auth_views.PasswordResetDoneView.as_view(
        template_name='indexer/password_reset_done.html'),
        name='password_reset_done'),
    re_path(r'^accounts/reset/(?P<uidb64>[0-9A-Za-z]+)-(?P<token>.+)/$',
        auth_views.PasswordResetConfirmView.as_view(
            template_name='indexer/password_reset_confirm.html',
            form_class=PasswordResetForm),
        name='password_reset_confirm'),
    path('accounts/reset/done/',
        auth_views.PasswordResetCompleteView.as_view(
            template_name='indexer/password_reset_complete.html'),
        name='password_reset_complete'),
    path('accounts/contact/<int:user_id>/',
        account_views.CustomContactFormView.as_view(
            form_class=UserContactForm,
            template_name='indexer/user_contact_form.html',
        ),
        name='django_contact_form'),
    path('accounts/contact/sent/',
        TemplateView.as_view(
            template_name='indexer/user_contact_form_sent.html'
        ),
        name='django_contact_form_sent'),
]
