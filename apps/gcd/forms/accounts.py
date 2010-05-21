import re
from datetime import date, timedelta

from django import forms
from django.forms.util import ErrorList
from django.contrib.auth.models import User
from django.contrib.auth.forms import SetPasswordForm
from django.conf import settings

from apps.gcd.models import Indexer, Country, Language, Reservation, IndexCredit

MIN_PASSWORD_LENGTH = 6
MAX_PASSWORD_LENGTH = 20

class AccountForm(forms.Form):
    email = forms.EmailField(max_length=75, help_text=(
      u'Your email address is your login name.  It will not be '
      u'publicly displayed on the site.'))
    
    _name_help =(u'You must provide at least one name (first, last or both). ' 
                 u'You do not have to give your real name, but please do '
                 u'not use someone else\'s real name. '
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

    def clean(self):
        cd = self.cleaned_data

        if ('email' in cd):
            for blocked_domain in settings.BLOCKED_DOMAINS:
                if (blocked_domain in cd['email']):
                    raise forms.ValidationError(
                      ['You may not use a disposable e-mail address service. '
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

    def clean(self):
        AccountForm.clean(self)

        cd = self.cleaned_data
        return cd

        set_password = False
        if ('old_password' not in cd or 'new_password' not in cd or
            'confirm_new_password' not in cd):
            return cd

        old = cd['old_password']
        new = cd['new_password']
        confirm = cd['confirm_new_password']
        if (new or confirm) and not old:
            self._errors['old_password'] = ErrorList(
              ['You must supply your old password in order to change it.'])
            cd = self._del_passwords(cd)

        elif old and (new or confirm):
            if not request.user.check_password(old):
                self._errors['old_password'] = ErrorList(
                  ['Old password incorrect, please try again.'])
                cd = self._del_passwords(cd)
            elif new != confirm:
                self._errors['new_password'] = ErrorList(
                  ['New password and confirm new password do not match.'])
                cd = self._del_passwords(cd)

        return cd

    def _del_passwords(self, cd):
        del cd['old_password']
        del cd['new_password']
        del cd['confirm_new_password']
        return cd

class PasswordResetForm(SetPasswordForm):
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

