# -*- coding: utf-8 -*-
"""
Forms related to account and profile management.  As with the other account
pieces, this should probably be moved out of the gcd app.
"""

from datetime import date, timedelta

from django import forms
from django.forms.utils import ErrorList
from django.contrib.auth.models import User
from django.contrib.auth.forms import AuthenticationForm, SetPasswordForm
from django.conf import settings
from django.core.mail import EmailMessage
from django.core.urlresolvers import reverse

from contact_form.forms import ContactForm

from apps.stddata.models import Country, Language
from apps.legacy.models import Reservation, IndexCredit

MIN_PASSWORD_LENGTH = 6
MAX_PASSWORD_LENGTH = 20


class LongUsernameAuthenticationForm(AuthenticationForm):
    """
    Exists purely to make the username input field wider since we
    support email addresses up to 75 characters rather than the traditional
    auth app's 30 character usernames.
    """
    username = forms.CharField(
      max_length=75, label='Username or email address',
      widget=forms.TextInput(attrs={'class': 'medium'}))


class AccountForm(forms.Form):
    """
    Base class for account creation and editing forms.
    Works with fields from both the stock auth object and our profile
    object (currently apps.gcd.models.Indexer).
    """
    def __init__(self, *args, **kwargs):
        super(AccountForm, self).__init__(*args, **kwargs)
        self.fields['email'].help_text = 'Your email address is your login' \
          ' name.  It will not be publicly displayed on the site.  Please ' \
          'see our <a target="_blank" href="%s">Privacy Policy</a> ' \
          'for more information.' % reverse('privacy')
        self.fields['seen_privacy_policy'].help_text = 'Please confirm that' \
          ' you have seen and agree with our <a target="_blank" href="%s">' \
          'Privacy Policy</a>.' % reverse('privacy')

    email = forms.EmailField(max_length=75)

    _name_help = (
      "You must provide at least one name (first, last or both). "
      "We prefer real names, but you do not have to use them. "
      "While you can choose any user name, the name of people entering data "
      "into the GCD is displayed publicly and should be consistent with the "
      "GCD's objective of reputable research about comics.  We recommend "
      "using your real name or a name similar to your real name. Please do "
      "not choose a name which is likely to be considered offensive, copies "
      "the name of a comics character, or impersonates another person.")

    first_name = forms.CharField(max_length=30, required=False,
                                 help_text=_name_help)
    last_name = forms.CharField(max_length=30, required=False)
    country = forms.ModelChoiceField(
        queryset=Country.objects.exclude(name='-- FIX ME --').order_by('name'),
        empty_label='--- Please Select a Country ---')

    languages = forms.ModelMultipleChoiceField(
      queryset=Language.objects.exclude(code='zxx').order_by('name'),
      required=False,
      widget=forms.SelectMultiple(attrs={'size': '6'}),
      help_text=('Please let us know what languages you read so we know what '
                 'language(s) to use when contacting you.  Hold down your '
                 'Control (ctrl) key to select multiple languages (Command '
                 'key for some systems).'))

    interests = forms.CharField(
      widget=forms.Textarea, required=False,
      help_text=('Please tell us a bit about your comic book interests. '
                 'This helps us connect you with an editor knowledgeable in '
                 'your area to help you learn our indexing system. We might '
                 'also contact you in response to your given interests.'))

    from_where = forms.CharField(
      widget=forms.Textarea, required=False,
      label='Where did you hear about us',
      help_text=('Please tell us where you heard about the GCD. For example '
                 'a website, a blog, a search, a convention,...'))

    seen_privacy_policy = forms.BooleanField(label="Privacy policy",
                                             initial=False,
                                             required=True)

    opt_in_email = forms.BooleanField(
      label="Opt in for emails", initial=False, required=False,
      help_text=('If checked, you indicate an interest in receiving '
                 'communication from the GCD, e.g. newsletters. You will '
                 'receive emails related to your data entries in any case.'))

    issue_detail = forms.ChoiceField(
      choices=[['0', 'core view'],
               ['1', 'edititorial content'],
               ['2', 'all content (including ads)']],
      initial='1',
      label='Displayed content for issues',
      help_text=('Select how detailed an issue is displayed. Core view '
                 'consists of story and cover sequences, editorial content '
                 '(default) has all content besides promos and ads. The other'
                 ' issue content is accessible by a click.'))

    notify_on_approve = forms.BooleanField(
      label="All approval emails", initial=True, required=False,
      help_text=('If checked, the system will email you when a change that '
                 'you submitted is approved.  You will always receive an'
                 ' email if the editor comments on approval.'))

    collapse_compare_view = forms.BooleanField(
      label="Collapse issue compare view", required=False,
      help_text=('If checked, the change comparison page for an issue will '
                 'show stories with no edits in a shortened version, with '
                 'a view of the full change accessible by a click.'))

    show_wiki_links = forms.BooleanField(
      label="Wiki Links in OI", initial=True, required=False,
      help_text=('If checked, the links to the documentation show in the OI'))

    def clean(self):
        cd = self.cleaned_data

        if ('email' in cd):
            for blocked_domain in settings.BLOCKED_DOMAINS:
                if (blocked_domain in cd['email']):
                    raise forms.ValidationError(
                      ['You may not use a disposable email address service. '
                       'E-mail addresses are strictly confidential and are '
                       'only used to contact you when questions arise about '
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
                    index_credits = IndexCredit.objects.filter(indexer=
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
                      [('The account with email %s has not yet been confirmed.'
                        ' You should receive an email that gives you a URL to'
                        ' visit to confirm your account.  After you have '
                        'visited that URL you will be able to log in and use '
                        'your account.  Please email %s if you do not receive '
                        'the email within a few hours.') %
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


class UserContactForm(ContactForm):
    from_email = 'do-not-reply@comics.org'
    name = forms.CharField(widget=forms.HiddenInput, required=False)
    email = forms.CharField(widget=forms.HiddenInput, required=False)
    template_name = 'indexer/user_contact_form.txt'

    def __init__(self, data=None, files=None, request=None,
                 user_id=None, *args, **kwargs):
        super(UserContactForm, self).__init__(data=data, files=files,
                                              request=request,
                                              *args, **kwargs)
        if user_id:
            self.fields['user_id'] = forms.IntegerField(
              widget=forms.HiddenInput, initial=user_id)
            self.target_user = User.objects.get(id=int(user_id))
        else:
            self.fields['user_id'] = forms.IntegerField(
              widget=forms.HiddenInput)

    def save(self, fail_silently=False):
        """
        Build and send the email message.
        """
        target_user = User.objects.get(id=int(self.cleaned_data['user_id']))

        user = self.request.user
        self.cleaned_data['email'] = user.email
        self.cleaned_data['name'] = user.get_full_name()

        message_dict = self.get_message_dict()
        message_dict['to'] = [target_user.email, ]
        message_dict['reply_to'] = [user.email, ]
        message_dict['body'] = self.message()
        message_dict['subject'] = 'Message from %s via the GCD' % \
                                  (user.get_full_name())
        message_dict.pop('message')
        message_dict.pop('recipient_list')

        email = EmailMessage(**message_dict)
        email.send(fail_silently=fail_silently)
