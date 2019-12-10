# -*- coding: utf-8 -*-
"""
Contains views related to account management, login and logout.
Should probably be refactored into a separate app rather than the gcd app.

The urls for these views are in the top-level urls.py file instead of
the gcd app's urls.py, which was the start of an effort to split this
out of the gcd app.
"""


import re
import hashlib
from random import random
from datetime import date, timedelta

from django.db import IntegrityError
from django.core import urlresolvers
from django.core.mail import send_mail
from django.conf import settings
from django.http import HttpResponseRedirect
from django.shortcuts import render, get_object_or_404
from django.template.loader import get_template
from django.contrib.auth.models import User, Group
from django.contrib.auth.views import login as standard_login
from django.contrib.auth.views import logout as standard_logout
from django.contrib.auth.decorators import login_required
from django.utils.safestring import mark_safe
from django.utils.html import conditional_escape as esc
from django.utils.translation import ugettext as _

from contact_form.views import ContactFormView

from apps.indexer.models import Indexer, Error
from apps.indexer.forms import ProfileForm, RegistrationForm, \
                               LongUsernameAuthenticationForm

from apps.oi import states
from apps.mycomics.models import Collector

from .forms import UserContactForm


class ViewTerminationError(Exception):
    """
    Used to end a view from within a helper function.  Takes a Django response
    object in place of a message.  View functions should catch these exceptions
    and simply return the included response.
    """

    def __init__(self, response):
        self.response = response

    def __str__(self):
        return repr(self.response)

    def get_response(self, request):
        return self.response


class ErrorWithMessage(ViewTerminationError):
    def __init__(self, message):
        self.message = message

    def get_response(self, request):
        return render_error(request, _(self.message), redirect=False)


def render_error(request, error_text, redirect=True, is_safe=False):
    """
    Utility function to render an error page as a response.  Can be
    called to return the page directly as a response or used to
    set up a redirect for which the error message is stored in our
    custom errors table.

    See apps.indexer.models.Error for more details.
    """
    if redirect:
        if error_text != '':
            salt = hashlib.sha1(str(random())).hexdigest()[:5]
            key = hashlib.sha1(salt + error_text.encode('utf-8')).hexdigest()
            Error.objects.create(error_key=key, is_safe=is_safe,
                                 error_text=error_text,)
            return HttpResponseRedirect(
              urlresolvers.reverse('error') +
              '?error_key=' + key)

        else:
            return HttpResponseRedirect(urlresolvers.reverse('error'))
    else:
        if is_safe:
            error_text = mark_safe(error_text)
        return error_view(request, error_text)


def error_view(request, error_text=''):
    """
    Looks up a specified error in the GCD's custom errors table,
    and renders a generic error page using that error's text.
    Can be used through a redirect or can be called directly from another view.

    See apps.indexer.models.Error for more details.
    """
    if error_text == '':
        if 'error_key' not in request.GET:
            error_text = 'Unknown error.'
        else:
            key = request.GET['error_key']
            errors = Error.objects.filter(error_key=key)
            if errors.count() == 1:
                error_text = errors[0]
                if errors[0].is_safe:
                    error_text = mark_safe(error_text)
                errors[0].delete()
            else:
                error_text = 'Unknown error.'
    return render(request, 'indexer/error.html', {'error_text': error_text})


def login(request, template_name, landing_view='default_profile'):
    """
    Do some pre-checking before handing off to the standard login view.
    If anything goes wrong just let the standard login handle it.
    """

    if request.user.is_authenticated():
        return HttpResponseRedirect(urlresolvers.reverse(landing_view))

    try:
        if request.method == "POST":
            try:
                user = User.objects.get(email=request.POST['username'])
            except (User.DoesNotExist, User.MultipleObjectsReturned):
                user = User.objects.get(username=request.POST['username'])

            if user.indexer.registration_expires is not None:
                if date.today() > (user.indexer.registration_expires +
                                   timedelta(1)):
                    return render_error(
                      request,
                      ('The account with the email "%s" was never confirmed '
                       'and has expired.  You may <a href="' +
                       urlresolvers.reverse('register') +
                       '">re-register</a>.  ') % esc(user.email), is_safe=True)
                return render_error(
                  request,
                  ('The account with email "%s" has not yet been confirmed. '
                   'You should receive an email that gives you a URL to visit '
                   'to confirm your account.  After you have visited that URL '
                   'you will be able to log in and use your account.  Please '
                   '<a href="mailto:%s">contact us</a> if you do not receive '
                   'the email within a few hours.') %
                  (esc(user.email), settings.EMAIL_CONTACT), is_safe=True)

    except User.DoesNotExist:
        pass

    if 'next' in request.POST:
        next = request.POST['next']
        if re.match(r'/accounts/confirm/', next, flags=re.I):
            post = request.POST.copy()
            post['next'] = urlresolvers.reverse('welcome')
            request.POST = post
        if re.match(r'/gcd-error/', next, flags=re.I):
            post = request.POST.copy()
            post['next'] = urlresolvers.reverse('home')
            request.POST = post

    return standard_login(request, template_name=template_name,
                          authentication_form=LongUsernameAuthenticationForm)


def logout(request):
    """
    Handle logout.  Prevent GET requests from having side effects (such as
    logging the user out).  Don't leave the site on a user's error message
    after the user logs out.
    """
    if request.method == 'POST':
        next_page = request.POST['next']
        if re.match(urlresolvers.reverse('error'), next_page):
            next_page = '/'
        return standard_logout(request, next_page=next_page)

    elif request.user.is_authenticated():
        return render_error(request,
                            'Please use the logout button to log out.')
    return render_error(request,
                        'Cannot logout because you are not logged in.')


def register(request):
    """
    Handle the registration form.

    On a GET, display the form.
    On a POST, register the new user, set up their profile, and log them in
    (logging the current user out if necessary).
    """

    if request.method == 'GET':
        form = RegistrationForm(auto_id=True)
        return render(request, 'indexer/register.html', {'form': form})

    form = RegistrationForm(request.POST)
    if not form.is_valid():
        return render(request, 'indexer/register.html', {'form': form})

    cd = form.cleaned_data
    email_users = User.objects.filter(email=cd['email'])
    if email_users.count():
        return handle_existing_account(request, email_users)

    # To make a unique username, take the first 20 characters before the "@"
    # in the email address, and tack on a number if that username is already
    # in use.  These usernames will not ever be shown except by accident
    # or possibly in corners of the admin UI that insist on displaying them,
    # but only admins and possibly editors will have access to that if we
    # use it at all.  20 characters just to give plenty of room in 30-character
    # username field for a disambiguating number, and maybe some other stuff
    # if we ever need to change this algorithm.

    # NOTE: We just go ahead and attempt to insert the user and then catch
    # the integrity error because any other strategy involves race conditions
    # so we'd have to catch it anyway.  We limit this to 10 tries to prevent
    # some other condition that raises the exception from trapping us in
    # an infinite loop.

    username_base = re.sub('@.*$', '', cd['email'])[:20]
    user_count = User.objects.count()
    new_user = None
    last_delta = 10
    for delta in range(1, last_delta):
        username = '%s_%d' % (username_base, user_count + delta)
        try:
            new_user = User.objects.create_user(username,
                                                cd['email'],
                                                cd['password'])
            break
        except IntegrityError:
            if delta == last_delta:
                raise

    if new_user is None:
        return render_error(
          request,
          ('Could not create unique internal account name.  This is a very '
           'unlikely error, and it will probably go away if you try to '
           'register again.  We apologize for the inconvenience.  If it '
           'does not go away, please email <a href="mailto:%s">%s</a>.') %
          (settings.EMAIL_CONTACT, settings.EMAIL_CONTACT), is_safe=True)

    new_user.first_name = cd['first_name']
    new_user.last_name = cd['last_name']
    new_user.is_active = False
    new_user.save()

    new_user.groups.add(*Group.objects.filter(name='indexer'))

    salt = hashlib.sha1(str(random())).hexdigest()[:5]
    key = hashlib.sha1(salt + new_user.email).hexdigest()
    expires = date.today() + timedelta(settings.REGISTRATION_EXPIRATION_DELTA)
    indexer = Indexer(is_new=True,
                      max_reservations=settings.RESERVE_MAX_INITIAL,
                      max_ongoing=settings.RESERVE_MAX_ONGOING_INITIAL,
                      country=cd['country'],
                      interests=cd['interests'],
                      from_where=cd['from_where'],
                      registration_key=key,
                      registration_expires=expires,
                      notify_on_approve=cd['notify_on_approve'],
                      collapse_compare_view=cd['collapse_compare_view'],
                      show_wiki_links=cd['show_wiki_links'],
                      seen_privacy_policy=cd['seen_privacy_policy'],
                      opt_in_email=cd['opt_in_email'],
                      issue_detail=cd['issue_detail'],
                      user=new_user)
    indexer.save()

    if cd['languages']:
        indexer.languages.add(*cd['languages'])

    email_body = """
Hello from the %s!

  We've received a request for an account using this email
address.  If you did indeed register an account with us,
please confirm your account by going to:

%s

within the next %d days.

  If you did not register for an account, then someone else is trying to
use your email address.  In that case, simply do not confirm the account.

thanks,
-the %s team
%s
""" % (settings.SITE_NAME,
       settings.SITE_URL.rstrip('/') +
       urlresolvers.reverse('confirm', kwargs={'key': key}),
       settings.REGISTRATION_EXPIRATION_DELTA,
       settings.SITE_NAME,
       settings.SITE_URL)

    send_mail(from_email=settings.EMAIL_NEW_ACCOUNTS_FROM,
              recipient_list=[new_user.email],
              subject='GCD new account confirmation',
              message=email_body,
              fail_silently=(not settings.BETA))

    return HttpResponseRedirect(urlresolvers.reverse('confirm_instructions'))


def confirm_account(request, key):
    """
    The registration process involves emailing prospective users a link
    with a key, which they must use to confirm their account before they
    can log in.

    This view function handles the confirmation step, which is expected
    to be a GET.

    TODO: Should we check the HTTP method here?  Technically, this does
    something other than retrieve data, and therefore should not be a GET,
    but it is idempotent and we want to keep the number of clicks required
    to activate an account to a minimum.  This sort of confirmation by GET
    is common.
    """
    try:
        indexer = Indexer.objects.get(registration_key=key)
        if indexer.registration_expires is None:
            if indexer.user.is_active:
                # The indexer already confirmed his or her account.
                return render_error(
                  request,
                  'You have already successfully confirmed your account.  '
                  'Please use the login button in the bar at the top of the '
                  'screen to log in to your account.')
            return render_error(
              request,
              ('Your account has already been confirmed, but it is marked '
               'as inactive.  Please <a href="mailto:%s">contact us</a> if '
               'you would like to re-activate it.') % settings.EMAIL_CONTACT,
              is_safe=True)

        if date.today() > indexer.registration_expires:
            return render_error(
              request, 'Your confirmation key has expired. '
              'You may <a href="' + urlresolvers.reverse('register') +
              '">re-register</a>.  ', is_safe=True)

        indexer.user.is_active = True
        indexer.user.save()

        # Clear the expiration date so that we can tell that the account has
        # been confirmed even if it's later marked as inactive, but leave
        # the key in place so that we can find the account again and give
        # a friendly message if the user tries to confirm a second time.
        indexer.registration_expires = None
        indexer.save()
        Collector.objects.create_collector(indexer.user)

        email_body = """
We have a new Indexer!

Name: %s
Country: %s
Languages: %s
Interests:
   %s

Where heard about us: %s
Mentor this indexer: %s
        """ % (indexer,
               indexer.country.name,
               ', '.join([lang.name for lang in indexer.languages.all()]),
               indexer.interests,
               indexer.from_where,
               'http://' + request.get_host() +
               urlresolvers.reverse('mentor',
                                    kwargs={'indexer_id': indexer.id}))

        if settings.BETA:
            email_subject = 'New BETA Indexer: %s' % indexer
        else:
            email_subject = 'New Indexer: %s' % indexer

        send_mail(from_email=settings.EMAIL_NEW_ACCOUNTS_FROM,
                  recipient_list=[settings.EMAIL_EDITORS,
                                  settings.EMAIL_PRTEAM],
                  subject=email_subject,
                  message=email_body,
                  fail_silently=(not settings.BETA))

        send_mail(from_email=settings.EMAIL_NEW_ACCOUNTS_FROM,
                  recipient_list=[indexer.user.email],
                  subject='GCD successfull registration',
                  message=get_template('indexer/welcome_mail.html').render(),
                  fail_silently=(not settings.BETA))

        return HttpResponseRedirect(urlresolvers.reverse('welcome'))

    except Indexer.DoesNotExist:
        return render_error(
          request,
          ('Invalid confirmation URL.  Please make certain that you copied '
           'the URL from the email correctly.  If it has been more than %d '
           'days, the confirmation code has expired and the account may have '
           'been deleted due to lack of confirmation.') %
          (settings.REGISTRATION_EXPIRATION_DELTA + 1))

    except Indexer.MultipleObjectsReturned:
        return render_error(
          request,
          ('There is a problem with your confirmation key.  Please email %s '
           'for assistance.') % settings.EMAIL_CONTACT)


def handle_existing_account(request, users):
    """
    Helper function to handle people trying to open multiple accounts.
    Called from view functions, but not directly used as a view.
    """
    if users.count() > 1:
        # There are only a few people in this situation, all of whom are
        # either editors themselves or definitely know how to easily get
        # in touch with an editor.
        return render_error(
          request,
          ('You already have multiple accounts with this email '
           'address.  Please contact an editor to get your '
           'personal and/or shared accounts sorted out before '
           'adding a new one.'))

    user = users[0]
    if user.is_active:
        return render_error(
          request,
          'You already have an active account with this email address.  If '
          'you have forgotten your password, you may <a href="' +
          urlresolvers.reverse('forgot_password') + '">reset '
          'it</a>.  If you feel you need a second account with this email, '
          'please <a href="mailto:%s">contact us</a>.' %
          settings.EMAIL_CONTACT, is_safe=True)

    elif not user.indexer.is_banned:
        if user.indexer.registration_expires is not None:
            user.indexer.registration_expires = date.today() + \
              timedelta(settings.REGISTRATION_EXPIRATION_DELTA)
            user.indexer.save()

            email_body = """
Hello from the %s!

  We've received a request for resending the confirmation information
for an account using this email address.  If you did indeed register
an account with us, please confirm your account by going to:

%s

within the next %d days.

  If you did not register for an account, then someone else is trying to
use your email address.  In that case, simply do not confirm the account.

thanks,
-the %s team
%s
            """ % (settings.SITE_NAME,
                   settings.SITE_URL.rstrip('/') + urlresolvers.reverse(
                     'confirm', kwargs={'key': user.indexer.registration_key}),
                   settings.REGISTRATION_EXPIRATION_DELTA,
                   settings.SITE_NAME,
                   settings.SITE_URL)

            send_mail(from_email=settings.EMAIL_NEW_ACCOUNTS_FROM,
                      recipient_list=[user.email],
                      subject='GCD new account confirmation - resend',
                      message=email_body,
                      fail_silently=(not settings.BETA))

            return HttpResponseRedirect(urlresolvers
                                        .reverse('resend_instructions'))
        else:
            return render_error(
              request,
              ('An account with this email address already exists, '
               'but is deactivated.  Please '
               '<a href="mailto:%s">contact us</a> '
               'if you would like to reactivate it.') % settings.EMAIL_CONTACT,
              is_safe=True)
    else:
        return render_error(
          request,
          'A prior account with this email address has been '
          'shut down.  Please contact an Editor if you believe '
          'this was done in error.')


def profile(request, user_id=None, edit=False):
    """
    View method to display (with this method) or edit (using the
    update_profile method) the user's profile data.
    """
    if request.method == 'POST':
        return update_profile(request, user_id)

    if not request.user.is_authenticated():
        return HttpResponseRedirect(urlresolvers.reverse('login'))

    if user_id is None:
        return HttpResponseRedirect(
          urlresolvers.reverse('view_profile',
                               kwargs={'user_id': request.user.id}))
    else:
        profile_user = get_object_or_404(User, id=user_id)

    context = {'profile_user': profile_user, 'settings': settings}
    if edit is True:
        if profile_user == request.user:
            form = ProfileForm(auto_id=True, initial={
              'email': profile_user.email,
              'first_name': profile_user.first_name,
              'last_name': profile_user.last_name,
              'country': profile_user.indexer.country.id,
              'languages':
              [lang.id for lang in profile_user.indexer.languages.all()],
              'interests': profile_user.indexer.interests,
              'from_where': profile_user.indexer.from_where,
              'seen_privacy_policy': profile_user.indexer.seen_privacy_policy,
              'opt_in_email': profile_user.indexer.opt_in_email,
              'issue_detail': profile_user.indexer.issue_detail,
              'notify_on_approve': profile_user.indexer.notify_on_approve,
              'collapse_compare_view':
              profile_user.indexer.collapse_compare_view,
              'show_wiki_links': profile_user.indexer.show_wiki_links,
            })
            context['form'] = form
        else:
            return render_error(
              request,
              "You may not edit other users' profiles")

    if profile_user == request.user:
        context['ranking'] = ranking(profile_user.indexer)

    return render(request, 'indexer/profile.html', context)


def update_profile(request, user_id=None):
    """
    Helper method to perform the update if the main profile view
    detects a POST request.
    """
    if request.user.id != int(user_id):
        return render_error(request, 'You may only edit your own profile.')

    errors = []
    form = ProfileForm(request.POST)
    if not form.is_valid():
        return render(request, 'indexer/profile.html', {'form': form})

    set_password = False
    old = form.cleaned_data['old_password']
    new = form.cleaned_data['new_password']
    confirm = form.cleaned_data['confirm_new_password']
    if (new or confirm) and not old:
        errors.append(
          'You must supply your old password in order to change it.')
    elif old and (new or confirm):
        if not request.user.check_password(old):
            errors.append('Old password incorrect, please try again.')
        elif new != confirm:
            errors.append(
              'New password and confirm new password do not match.')
        else:
            set_password = True

    if errors:
        return render(request, 'indexer/profile.html', {'form': form,
                                                        'error_list': errors})

    request.user.first_name = form.cleaned_data['first_name']
    request.user.last_name = form.cleaned_data['last_name']
    request.user.email = form.cleaned_data['email']
    if set_password is True:
        request.user.set_password(new)
    request.user.save()

    indexer = request.user.indexer
    indexer.notify_on_approve = form.cleaned_data['notify_on_approve']
    indexer.collapse_compare_view = form.cleaned_data['collapse_compare_view']
    indexer.show_wiki_links = form.cleaned_data['show_wiki_links']
    indexer.country = form.cleaned_data['country']
    indexer.languages = form.cleaned_data['languages']
    indexer.interests = form.cleaned_data['interests']
    indexer.from_where = form.cleaned_data['from_where']
    indexer.seen_privacy_policy = form.cleaned_data['seen_privacy_policy']
    indexer.opt_in_email = form.cleaned_data['opt_in_email']
    indexer.issue_detail = form.cleaned_data['issue_detail']
    indexer.save()

    return HttpResponseRedirect(
      urlresolvers.reverse('view_profile',
                           kwargs={'user_id': request.user.id}))


@login_required
def mentor(request, indexer_id):
    """
    View for an approver to use to mentor a new user.
    GET: Displays whether the user needs a mentor or not, or who it is.
    POST: Takes on the user as a mentee.
    """
    if not request.user.has_perm('indexer.can_mentor'):
        return render_error(
          request,
          'You are not allowed to mentor new Indexers', redirect=False)

    indexer = get_object_or_404(Indexer, id=indexer_id)
    if request.method == 'POST' and indexer.mentor is None:
        indexer.mentor = request.user
        indexer.save()
        pending = indexer.user.changesets.filter(state=states.PENDING)
        for changeset in pending.all():
            try:
                changeset.assign(approver=request.user, notes='')
            except ValueError:
                # Someone is already mentoring. Unlikely, and just let it go.
                pass

        if pending.count():
            return HttpResponseRedirect(urlresolvers.reverse('reviewing'))

        # I kinda assume the HTTP_REFERER is always present, but just in case
        if 'HTTP_REFERER' in request.META:
            return HttpResponseRedirect(request.META['HTTP_REFERER'])

    return render(request, 'indexer/mentor.html', {'indexer': indexer})


@login_required
def unmentor(request, indexer_id):
    """
    Releases a user from being mentored.  POST only.
    This is NOT for "graduating" a user into not needing a mentor.
    It is for releasing the new user to find another mentor.
    """
    indexer = get_object_or_404(Indexer, id=indexer_id)
    if indexer.mentor is None:
        return render_error(request, "This indexer does not have a mentor.")
    if request.user != indexer.mentor:
        return render_error(
          request,
          "You are not this indexer's mentor, so you may not un-mentor them.")
    if request.method == 'POST':
        indexer.mentor = None
        indexer.save()
        return HttpResponseRedirect(urlresolvers.reverse('mentoring'))

    return render_error(request,
                        'Please access this page through the proper form.')


@login_required
def mentor_not_new(request, indexer_id):
    """
    Marks a user as no longer needing a mentor and adjusts their limits
    accordingly.
    POST only, although a GET will redirect to the basic mentoring view.
    """
    if not request.user.has_perm('indexer.can_mentor'):
        return render_error(
          request,
          'You are not allowed to mentor new Indexers', redirect=False)

    indexer = get_object_or_404(Indexer, id=indexer_id)
    if indexer.mentor != request.user:
        return render_error(
          request,
          'You are not allowed to change the state of this new Indexer',
          redirect=False)
    else:
        if request.method == 'POST':
            indexer.is_new = False
            indexer.max_reservations = max(settings.RESERVE_MAX_DEFAULT,
                                           indexer.max_reservations)
            indexer.max_ongoing = max(settings.RESERVE_MAX_ONGOING_DEFAULT,
                                      indexer.max_ongoing)
            indexer.save()

    return HttpResponseRedirect(urlresolvers.reverse('mentoring'))


def ranking(indexer):
    """
    Returns a dictionary of indexer ranking information (by IMPs).
    """
    # Query for list of indexers with more imps than this indexer (with gt and
    # not gte because indexers with equal imps are tied). When ordered by imps,
    # the first in the list is the one to beat to rise to next level.
    worldwide = Indexer.objects.order_by('imps')\
        .exclude(user__username=settings.ANON_USER_NAME) \
        .filter(imps__gt=indexer.imps)
    national = worldwide.filter(country=indexer.country)

    # first in the list is the next one who can get in front
    worldwide_down = Indexer.objects.order_by('-imps')\
        .exclude(user__username=settings.ANON_USER_NAME) \
        .exclude(user=indexer.user) \
        .filter(imps__lte=indexer.imps)
    national_down = worldwide_down.filter(country=indexer.country)

    return {
        'national': national.count() + 1,
        'global': worldwide.count() + 1,
        'national_levelup':
            (national[0].imps - indexer.imps + 1) if national else None,
        'global_levelup':
            (worldwide[0].imps - indexer.imps + 1) if worldwide else None,
        'national_leveldown':
            (indexer.imps - national_down[0].imps) if national_down else None,
        'global_leveldown':
            (indexer.imps - worldwide_down[0].imps) if worldwide_down else None
            }


class CustomContactFormView(ContactFormView):
    form_class = UserContactForm

    def get_form_kwargs(self):
        kwargs = super(CustomContactFormView, self).get_form_kwargs()
        if hasattr(self, 'user_id'):
            kwargs['user_id'] = self.user_id
        return kwargs

    def get(self, request, user_id):
        self.user_id = user_id
        return super(CustomContactFormView, self).get(request=request)

    def get_success_url(self):
        return urlresolvers.reverse('user_contact_form_sent')
