# -*- coding: utf-8 -*-
import re
import sha
from random import random
from datetime import date, timedelta

from django.db import IntegrityError
from django.core import urlresolvers
from django.core.mail import send_mail
from django.conf import settings
from django.http import HttpResponseRedirect
from django.shortcuts import render_to_response, get_object_or_404
from django.template import RequestContext
from django.contrib.auth import authenticate
from django.contrib.auth.models import User, Group
from django.contrib.auth.views import login as standard_login
from django.contrib.auth.views import logout as standard_logout
from django.contrib.auth.decorators import login_required
from django.utils.safestring import mark_safe
from django.utils.html import conditional_escape as esc

from apps.gcd.views import render_error
from apps.gcd.models import Indexer, Language, Country, Reservation, IndexCredit
from apps.gcd.forms.accounts import ProfileForm, RegistrationForm

def login(request, template_name):
    """
    Do some pre-checking before handing off to the standard login view.
    If anything goes wrong just let the standard login handle it.
    """

    if request.user.is_authenticated():
        return HttpResponseRedirect(urlresolvers.reverse('default_profile'))

    try:
        if request.method == "POST":
            user = User.objects.get(username=request.POST['username'])
            if user.indexer.registration_key is not None:
                if date.today() > (user.indexer.registration_expires +
                                   timedelta(1)):
                    return render_error(request,
                      ('The account with the email "%s" was never confirmed '
                       'and has expired.  You may <a href="' + \
                       urlresolvers.reverse('register') + \
                       '">re-register</a>.  ') % esc(user.email), is_safe=True )
                return render_error(request,
                  ('The account with email "%s" has not yet been confirmed. '
                   'You should receive an email that gives you a URL to visit '
                   'to confirm your account.  After you have visited that URL '
                   'you will be able to log in and use your account.  Please '
                   '<a href="mailto:%s">contact us</a> if you do not receive '
                   'the email within a few hours.') %
                  (esc(user.email), settings.EMAIL_CONTACT), is_safe=True)

            if 'next' in request.POST:
                next = request.POST['next']
                if re.match(r'/accounts/confirm/', next, flags=re.I):
                    post = request.POST.copy()
                    post['next'] = urlresolvers.reverse('welcome')
                    request.POST = post
    except Exception:
        pass
    return standard_login(request, template_name=template_name)

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
        return render_to_response('gcd/accounts/register.html',
          { 'form' : form },
          context_instance=RequestContext(request))
        
    errors = []
    form = RegistrationForm(request.POST)
    if not form.is_valid():
        return render_to_response('gcd/accounts/register.html',
                                  { 'form': form },
                                  context_instance=RequestContext(request))

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
        return render_error(request, 
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

    salt = sha.new(str(random())).hexdigest()[:5]
    key = sha.new(salt + new_user.email).hexdigest()
    expires = date.today() + timedelta(settings.REGISTRATION_EXPIRATION_DELTA)
    indexer = Indexer(is_new=True,
                      max_reservations=settings.RESERVE_MAX_INITIAL,
                      max_ongoing=settings.RESERVE_MAX_ONGOING_INITIAL,
                      country=cd['country'],
                      interests=cd['interests'],
                      registration_key=key,
                      registration_expires=expires,
                      user=new_user)
    indexer.save()

    if cd['languages']:
        indexer.languages.add(*cd['languages'])

    email_body = u"""
Hello from the %s!

  We've received a request for an account using this email
address.  If you did indeed register an account with us,
please confirm your account by going to:

%s

within the next %d days.

  If you did not register for an account, then someone else is trying to
use your email address.  In that case, simply do not confirm the account
and it will expire after %d days.

thanks,
-the %s team
%s
""" % (settings.SITE_NAME,
       settings.SITE_URL.rstrip('/') +
         urlresolvers.reverse('confirm', kwargs={ 'key': key }),
       settings.REGISTRATION_EXPIRATION_DELTA,
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
    try:
        indexer = Indexer.objects.get(registration_key=key)
        if date.today() > indexer.registration_expires:
            return render_error(request, 'Your confirmation key has expired. '
                     'You may <a href="' + urlresolvers.reverse('register') + \
                     '">re-register</a>.  ', is_safe=True )

        indexer.user.is_active = True
        indexer.user.save()
        indexer.registration_key = None
        indexer.registration_expires = None
        indexer.save()

        email_body = u"""
We have a new Indexer!

Name: %s
Email: %s
Country: %s
Languages: %s
Interests:
   %s

Mentor this indexer: %s
        """ % (indexer,
               indexer.user.email,
               indexer.country.name,
               ', '.join([lang.name for lang in indexer.languages.all()]),
               indexer.interests,
               'http://' + request.get_host() +
               urlresolvers.reverse('mentor',
                                    kwargs={ 'indexer_id': indexer.id }))

        send_mail(from_email=settings.EMAIL_NEW_ACCOUNTS_FROM,
                  recipient_list=[settings.EMAIL_EDITORS],
                  subject='New Indexer: %s' % indexer,
                  message=email_body,
                  fail_silently=(not settings.BETA))

        return HttpResponseRedirect(urlresolvers.reverse('welcome'))

    except Indexer.DoesNotExist:
        return render_error(request,
          ('Invalid confirmation URL.  Please make certain that you copied '
           'the URL from the email correctly.  If it has been more than %d '
           'days, the confirmation code has expired and the account may have '
           'been deleted due to lack of confirmation.') %
          (settings.REGISTRATION_EXPIRATION_DELTA + 1))

    except Indexer.MultipleObjectsReturned:
        return render_error(request,
          ('There is a problem with your confirmation key.  Please email %s '
           'for assistance.') % settings.EMAIL_CONTACT)

def handle_existing_account(request, users):
    if users.count() > 1:
        # There are only a few people in this situation, all of whom are
        # either editors themselves or definitely know how to easily get
        # in touch with an editor.
        return render_error(request,
          ('You already have multiple accounts with this email '
           'address.  Please contact an editor to get your '
           'personal and/or shared accounts sorted out before '
           'adding a new one.'))

    user = users[0]
    if user.is_active:
        return render_error(request, 
          'You already have an active account with this email address.  If '
          'you have forgotten your password, you may <a href="' +
           urlresolvers.reverse('forgot_password') + '">reset '
          'it</a>.  If you feel you need a second account with this email, '
          'please <a href="mailto:%s">contact us</a>.' %
          settings.EMAIL_CONTACT, is_safe=True)

    elif not user.indexer.is_banned:
        # TODO: automatic reactivation, but have to merge fields?  Complicated.
        return render_error(request, 
          ('An account with this email address already exists, '
           'but is deactivated.  Please '
           '<a href="mailto:%s">contact us</a> '
           'if you would like to reactivate it.') % settings.EMAIL_CONTACT,
           is_safe=True)
    else:
        return render_error(request,
          'A prior account with this email address has been '
          'shut down.  Please contact an Editor if you believe '
          'this was done in error.')

def profile(request, user_id=None, edit=False):
    if request.method == 'POST':
        return update_profile(request, user_id)

    if user_id is None:
        if request.user.is_authenticated():
            return HttpResponseRedirect(
              urlresolvers.reverse('view_profile',
                                   kwargs={'user_id': request.user.id}))
        else:
            return HttpResponseRedirect(
              urlresolvers.reverse('login'))
        profile_user = request.user
    else:
        profile_user = get_object_or_404(User, id=user_id)

    context = { 'profile_user': profile_user }
    if edit is True:
        if profile_user == request.user:
            form = ProfileForm(auto_id=True, initial={
              'email': profile_user.email,
              'first_name': profile_user.first_name,
              'last_name': profile_user.last_name,
              'country': profile_user.indexer.country.id,
              'languages':
                [ lang.id for lang in profile_user.indexer.languages.all() ],
              'interests': profile_user.indexer.interests,
            })
            context['form'] = form
        else:
            return render_error(request,
              "You may not edit other users' profiles")

    return render_to_response('gcd/accounts/profile.html',
                              context,
                              context_instance=RequestContext(request))

def update_profile(request, user_id=None):
    if request.user.id != int(user_id):
        return render_error(request, 'You may only edit your own profile.')

    errors = []
    form = ProfileForm(request.POST)
    if not form.is_valid():
        return render_to_response('gcd/accounts/profile.html',
                                  { 'form': form },
                                  context_instance=RequestContext(request))
    set_password = False
    old = form.cleaned_data['old_password']
    new = form.cleaned_data['new_password']
    confirm = form.cleaned_data['confirm_new_password']
    if (new or confirm) and not old:
        errors.append(
          u'You must supply your old password in order to change it.')
    elif old and (new or confirm):
        if not request.user.check_password(old):
            errors.append(u'Old password incorrect, please try again.')
        elif new != confirm:
            errors.append(
              u'New password and confirm new password do not match.')
        else:
            set_password = True

    if errors:
        return render_to_response('gcd/accounts/profile.html',
                                  { 'form': form, 'error_list': errors },
                                  context_instance=RequestContext(request))

    request.user.first_name = form.cleaned_data['first_name']
    request.user.last_name = form.cleaned_data['last_name']
    request.user.email = form.cleaned_data['email']
    if set_password is True:
        request.user.set_password(new)
    request.user.save()

    indexer = request.user.indexer
    indexer.country = form.cleaned_data['country']
    indexer.languages = form.cleaned_data['languages']
    indexer.interests = form.cleaned_data['interests']
    indexer.save()

    return HttpResponseRedirect(
      urlresolvers.reverse('view_profile',
                           kwargs={'user_id': request.user.id}))

@login_required
def mentor(request, indexer_id):
    if not request.user.has_perm('gcd.can_mentor'):
        return render_error(request,
          'You are not allowed to mentor new Indexers', redirect=False)

    indexer = get_object_or_404(Indexer, id=indexer_id)
    if request.method == 'POST' and indexer.mentor is None:
        indexer.mentor = request.user
        indexer.save()
        # I kinda assume the HTTP_REFERER is always present, but just in case
        if request.META.has_key('HTTP_REFERER'):
            return HttpResponseRedirect(request.META['HTTP_REFERER'])

    return render_to_response('gcd/accounts/mentor.html',
                              { 'indexer' : indexer },
                              context_instance=RequestContext(request))

@login_required
def mentor_not_new(request, indexer_id):
    if not request.user.has_perm('gcd.can_mentor'):
        return render_error(request,
          'You are not allowed to mentor new Indexers', redirect=False)

    indexer = get_object_or_404(Indexer, id=indexer_id)
    if indexer.mentor != request.user:
        return render_error(request,
          'You are not allowed to change the state of this new Indexer', 
          redirect=False)
    else:
        if request.method == 'POST':
            indexer.is_new = False
            indexer.max_reservations = settings.RESERVE_MAX_DEFAULT
            indexer.max_ongoing = settings.RESERVE_MAX_ONGOING_DEFAULT
            indexer.save()
    
    return HttpResponseRedirect(urlresolvers.reverse('mentoring'))

