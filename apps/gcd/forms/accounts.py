# -*- coding: utf-8 -*-
"""
Forms related to account and profile management.  As with the other account
pieces, this should probably be moved out of the gcd app.
"""

import re
from datetime import date, timedelta

from django import forms
from django.forms.utils import ErrorList
from django.contrib.auth.models import User
from django.contrib.auth.forms import AuthenticationForm, SetPasswordForm
from django.conf import settings

from apps.gcd.models import Indexer, Country, Language, Reservation, IndexCredit

MIN_PASSWORD_LENGTH = 6
MAX_PASSWORD_LENGTH = 20

class LongUsernameAuthenticationForm(AuthenticationForm):
    """
    Exists purely to make the username input field wider since we
    support email addresses up to 75 characters rather than the traditional
    auth app's 30 character usernames.
    """
    username = forms.CharField(max_length=75, label='Username or email address',
      widget=forms.TextInput(attrs={'class': 'medium'}))

class AccountForm(forms.Form):
    """
    Base class for account creation and editing forms.
    Works with fields from both the stock auth object and our profile
    object (currently apps.gcd.models.Indexer).
    """
    # For some reason, importing urlresolvers in this module causes an error
    # where django thinks our urls conf is empty.
    # TODO: use reverse_lazy() now that we're on Django 1.4.
    email = forms.EmailField(max_length=75, help_text=(
      u'Your email address is your login name.  It will not be '
      u'publicly displayed on the site.  Please see our '
      u'<a target="_blank" href="%s">Privacy Policy</a> '
      u'for more information.' % '/privacy/'))
    
    _name_help =(u'You must provide at least one name (first, last or both). ' 
                 u'We prefer real names, but you do not have to use them. '
                 u'If you choose a different name please do not take someone '
                 u"else's real name and use common sense when choosing one. "
                 u'Your contributions will be credited under the name(s) you '
                 u'provide.')
    first_name = forms.CharField(max_length=30, required=False,
                                 help_text=_name_help)
    last_name = forms.CharField(max_length=30, required=False,
                                help_text=_name_help)
    country = forms.ModelChoiceField(
        queryset=Country.objects.exclude(name='-- FIX ME --').order_by('name'),
        empty_label='--- Please Select a Country ---')

    languages = forms.ModelMultipleChoiceField(
      queryset=Language.objects.exclude(code='zxx').order_by('name'),
      required=False,
      widget=forms.SelectMultiple(attrs={'size' : '6'}),
      help_text=(u'Please let us know what languages you read so we know what '
                 u'language(s) to use when contacting you.  Hold down your '
                 u'Control (ctrl) key to select multiple languages (Command '
                 u'key on the Macintosh).'))

    interests = forms.CharField(widget=forms.Textarea, required=False,
      help_text=(u'Please tell us a bit about your comic book interests. '
                 u'This helps us connect you with an Editor knowledgeable in '
                 u'your area to help you learn our indexing system.'))


    from_where = forms.CharField(widget=forms.Textarea, required=False,
      label='Where did you hear about us',
      help_text=(u'Please tell us where you heard about the GCD. For example '
                 u'a website, a blog, a search, a convention,...'))

    opt_in_email = forms.BooleanField(label="Opt in for emails",
                                           initial=False,
                                           required=False,
      help_text=(u'If checked, you indicate an interest in receiving '
                 u'communication from GCD members, e.g. newsletters. You will '
                 u'receive emails related to your data entries in any case.'))

    issue_detail = forms.ChoiceField(choices=[['0', 'core view'],
                                        ['1', 'edititorial content'],
                                        ['2', 'all content (including ads)']],
                               initial='1',
                               label='Displayed content for issues',
      help_text=(u'Select how detailed an issue is displayed. Core view '
                 u'consists of story and cover sequences, edititorial content '
                 u'(default) has all content besides promos and ads.'))

    notify_on_approve = forms.BooleanField(label="Approval emails",
                                           initial=True,
                                           required=False,
      help_text=(u'If checked, the system will also email you when a change that '
                 u'you submitted is approved without a comment.  You will '
                 u'always receive an email if the approver comments.'))
    collapse_compare_view = forms.BooleanField(
      label="Collapse compare view by default", required=False,
      help_text=(u'If checked, the change comparison page for an issue will show '
                 u'a shortened version of the unchanged values, with the full '
                 u'view accessible via a link.'))
    show_wiki_links = forms.BooleanField(label="Wiki Links in OI",
                                           initial=True,
                                           required=False,
      help_text=(u'If checked, the links to the documentation show in the OI'))

    def clean(self):
        cd = self.cleaned_data

        if ('email' in cd):
            for blocked_domain in settings.BLOCKED_DOMAINS:
                if (blocked_domain in cd['email']):
                    raise forms.ValidationError(
                      ['You may not use a disposable email address service. '
                       'E-mail addresses are strictly confidential and are only ' 
                       'used to contact you when there are questions about '
                       'your submissions to the database. Please contact %s '
                       'if you believe this message is in error.' %
                       settings.EMAIL_CONTACT])

        if ('email' in cd and
            User.objects.filter(username=cd['email']).count()):
            user = User.objects.get(username=cd['email'])
            if user.indexer.registration_key is not None:
                if date.today() > (user.indexer.registration_expires +
                                   timedelta(1)):
                    legacy_reservations = Reservation.objects.filter( 
                        indexer=user.indexer)
                    index_credits = IndexCredit.objects.filter(indexer=\
                                                        user.indexer)
                    if legacy_reservations.count() == 0 and \
                        index_credits.count() == 0:
                        user.delete()
                    else:
                        raise forms.ValidationError(
                          ['A registration with email %s was never confirmed, ' 
                           'has expired, but has data attached. Please '
                           'contact %s if this is your email.'
                           % (cd['email'], settings.EMAIL_CONTACT)])
                else:
                    raise forms.ValidationError(
                      [('The account with email %s has not yet been confirmed. '
                       'You should receive an email that gives you a URL to '
                       'visit to confirm your account.  After you have visited '
                       'that URL you will be able to log in and use your '
                       'account.  Please email %s if you do not receive the '
                       'email within a few hours.') %
                       (cd['email'], settings.EMAIL_CONTACT)])
            else:
                raise forms.ValidationError(
                  ['An account with email address "%s" as its login name '
                   'is already in use.' % cd['email']])

        if ('first_name' in cd and 'last_name' in cd and
            not cd['first_name'] and not cd['last_name']):
            error_msg = (
              'Please fill in either family name or given name, or '
              'both. You may use an alias if you do not wish your '
              'real name to appear on the site.')
            self._errors['first_name'] = ErrorList([error_msg])
            self._errors['last_name'] = ErrorList([error_msg])
        return cd

class RegistrationForm(AccountForm):
    """
    Form for creating an account.  Adds password creation/confirmation fields.
    """
    password = forms.CharField(widget=forms.PasswordInput,
                               min_length=MIN_PASSWORD_LENGTH,
                               max_length=MAX_PASSWORD_LENGTH)
    confirm_password = forms.CharField(widget=forms.PasswordInput,
                                       min_length=MIN_PASSWORD_LENGTH,
                                       max_length=MAX_PASSWORD_LENGTH)
    def __init__(self, *args, **kwargs):
        AccountForm.__init__(self, *args, **kwargs)
        
    def clean(self):
        AccountForm.clean(self)

        cd = self.cleaned_data
        if ('password' in cd and 'confirm_password' in cd and
            cd['password'] != cd['confirm_password']):
            self._errors['password'] = ErrorList(
              ['Password and confirm password do not match.'])
            del cd['password']
            del cd['confirm_password']

        return cd

class ProfileForm(AccountForm):
    """
    Profile (auth + apps.gcd.models.Indexer) editing form.

    Add password reset handling to the regular account form.
    Do not try to clean these fields as it depends on the request's user
    and is therefore done in the view function.

    TODO: Use PasswordResetForm class instead and set separately?
    """
    old_password = forms.CharField(widget=forms.PasswordInput,
                                   min_length=MIN_PASSWORD_LENGTH,
                                   max_length=MAX_PASSWORD_LENGTH,
                                   required=False)
    new_password = forms.CharField(widget=forms.PasswordInput,
                                   min_length=MIN_PASSWORD_LENGTH,
                                   max_length=MAX_PASSWORD_LENGTH,
                                   required=False)
    confirm_new_password = forms.CharField(widget=forms.PasswordInput,
                                           min_length=MIN_PASSWORD_LENGTH,
                                           max_length=MAX_PASSWORD_LENGTH,
                                           required=False)

class PasswordResetForm(SetPasswordForm):
    """
    Passed to auth.views.password_reset_confirm() in the top-level urls.py
    """
    def clean(self):
        cleaned_data = SetPasswordForm.clean(self)
        if 'new_password1' in cleaned_data:
            if (len(cleaned_data['new_password1']) < MIN_PASSWORD_LENGTH or
                len(cleaned_data['new_password1']) > MAX_PASSWORD_LENGTH):

                self._errors['new_password1'] = ErrorList(
                  ['New password must be between %d and %d characters long.' %
                   (MIN_PASSWORD_LENGTH, MAX_PASSWORD_LENGTH)])
                del cleaned_data['new_password1']
                if 'new_password2' in cleaned_data:
                    del cleaned_data['new_password2']

        return cleaned_data

