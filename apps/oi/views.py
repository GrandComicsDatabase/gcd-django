# -*- coding: utf-8 -*-
import re
import sys
import os
import os.path
import stat
from datetime import datetime, timedelta

from django.core import urlresolvers
from django.core.files import File
from django.conf import settings
from django.http import HttpResponse, HttpResponseRedirect
from django.template import RequestContext
from django.shortcuts import render_to_response, get_object_or_404
from django.db import transaction
from django.db.models import Min, Max
from django.core.exceptions import *

from django.contrib.auth.views import login
from django.contrib.auth.decorators import login_required, permission_required

from apps.gcd.models import *
from apps.gcd.views import ViewTerminationError, render_error, paginate_response
from apps.gcd.views.details import show_indicia_publisher, show_brand, \
                                   show_series, show_issue
from apps.gcd.views.covers import get_image_tag
from apps.gcd.views.search import do_advanced_search, used_search
from apps.gcd.models.cover import ZOOM_LARGE, ZOOM_MEDIUM, ZOOM_SMALL
from apps.gcd.templatetags.display import show_revision_short
from apps.oi.models import *
from apps.oi.forms import *
from apps.oi.covers import get_preview_image_tag, \
                           get_preview_image_tags_per_page, copy_approved_cover

REVISION_CLASSES = {
    'publisher': PublisherRevision,
    'indicia_publisher': IndiciaPublisherRevision,
    'brand': BrandRevision,
    'series': SeriesRevision,
    'issue': IssueRevision,
    'story': StoryRevision,
    'cover': CoverRevision,
}

DISPLAY_CLASSES = {
    'publisher': Publisher,
    'indicia_publisher': IndiciaPublisher,
    'brand': Brand,
    'series': Series,
    'issue': Issue,
    'story': Story,
    'cover': Cover,
}

##############################################################################
# Helper functions
##############################################################################

def _cant_get(request):
    return render_error(request,
      'This page may only be accessed through the proper form.',
       redirect=False)

##############################################################################
# Generic view functions
##############################################################################

@permission_required('gcd.can_reserve')
def delete(request, id, model_name):
    display_obj = get_object_or_404(DISPLAY_CLASSES[model_name], id=id)
    if request.method == 'GET':

        # These can only be reached if people try to paste in URLs directly,
        # but as we know, some people do that sort of thing.
        if display_obj.reserved:
            return render_error(request,
              u'Cannot delete "%s" as it is curently reserved.' % display_obj)
        if display_obj.deleted:
            return render_error(request,
              u'Cannot delete "%s" as it is already deleted.' % display_obj)

        return render_to_response('oi/edit/deletion_comment.html',
        {
            'model_name' : model_name,
            'id' : id,
            'object' : display_obj,
            'no_comment' : False
        },
        context_instance=RequestContext(request))

    if 'cancel' in request.POST:
        if model_name == 'cover':
            return HttpResponseRedirect(urlresolvers.reverse('edit_covers',
                     kwargs={'issue_id' : display_obj.issue.id}))
        return HttpResponseRedirect(urlresolvers.reverse('show_%s' % model_name,
                 kwargs={'%s_id' % model_name : id}))

    if not request.POST.__contains__('comments') or \
       request.POST['comments'].strip() == '':
        return render_to_response('oi/edit/deletion_comment.html',
        {
            'model_name' : model_name,
            'id' : id,
            'object' : display_obj,
            'no_comment' : True
        },
        context_instance=RequestContext(request))

    return reserve(request, id, model_name, True)

@transaction.autocommit
def _is_reservable(model_name, id):
    # returns number of objects which got reserved, so 1 if successful
    # with django 1.3 we can do this in reserve() using a with statement
    return DISPLAY_CLASSES[model_name].objects.filter(id=id,
                    reserved=False).update(reserved=True)

@transaction.autocommit
def _unreserve(display_obj):
    display_obj.reserved = False
    display_obj.save()

@permission_required('gcd.can_reserve')
def reserve(request, id, model_name, delete=False):
    display_obj = get_object_or_404(DISPLAY_CLASSES[model_name], id=id)
    if request.method != 'POST':
        return _cant_get(request)

    if display_obj.deleted:
        if model_name == 'cover':
            return HttpResponseRedirect(urlresolvers.reverse('show_issue',
              kwargs={'issue_id': display_obj.issue.id}))
        return HttpResponseRedirect(urlresolvers.reverse('change_history',
          kwargs={'model_name': model_name, 'id': id}))

    is_reservable = _is_reservable(model_name, id)

    if is_reservable == 0:
        return render_error(request,
          u'Cannot edit "%s" as it is already reserved.' %
          display_obj)

    try: # if something goes wrong we unreserve
        if delete:
            # In case someone else deleted while page was open or if it is not
            # deletable because of other actions in the interim (adding to an
            # issue for brand/ind_pub, modifying covers for issue, etc.)
            if not display_obj.deletable():
                # Technically nothing to roll back, but keep this here in case
                # someone adds more code later.
                transaction.rollback()
                _unreserve(display_obj)
                return render_error(request,
                       'This object fails the requirements for deletion.')

            changeset = _do_reserve(request.user, display_obj, model_name, True)
            changeset.submit(notes=request.POST['comments'], delete=True)
        else:
            changeset = _do_reserve(request.user, display_obj, model_name)

        if changeset is None:
            _unreserve(display_obj)
            return render_error(request,
              'You have reached your limit of open changes.  You must '
              'submit or discard some changes from your edit queue before you '
              'can edit any more.  If you are a new user this number is very low '
              'but will be increased as your first changes are approved.')

        if delete:
            if model_name == 'cover':
                return HttpResponseRedirect(urlresolvers.reverse('edit_covers',
                         kwargs={'issue_id' : display_obj.issue.id}))
            return HttpResponseRedirect(urlresolvers.reverse(
                     'show_%s' % model_name,
                     kwargs={str('%s_id' % model_name): id}))
        else:
            return HttpResponseRedirect(urlresolvers.reverse('edit',
              kwargs={ 'id': changeset.id }))

    except:
        transaction.rollback()
        _unreserve(display_obj)
        raise

def _do_reserve(indexer, display_obj, model_name, delete=False):
    if model_name != 'cover' and indexer.indexer.can_reserve_another() is False:
        return None

    if delete:
        # Deletions are submitted immediately which will set the correct state.
        new_state = states.UNRESERVED
    else:
        comment = 'Editing'
        new_state = states.OPEN
    changeset = Changeset(indexer=indexer, state=new_state,
                          change_type=CTYPES[model_name])
    changeset.save()

    if not delete:
        # Deletions are immediately submitted, which will add the appropriate
        # initial comment- no need to add two.
        changeset.comments.create(commenter=indexer,
                                  text=comment,
                                  old_state=states.UNRESERVED,
                                  new_state=changeset.state)

    revision = REVISION_CLASSES[model_name].objects.clone_revision(
      display_obj, changeset=changeset)

    if delete:
        revision.deleted = True
        revision.save()

    if model_name == 'issue':
        for story in revision.issue.active_stories():
            story_revision = StoryRevision.objects.clone_revision(
              story=story, changeset=changeset)
            if delete:
                story_revision.toggle_deleted()
        if delete:
            for cover in revision.issue.active_covers():
                cover_revision = CoverRevision(changeset=changeset,
                                               issue=cover.issue,
                                               cover=cover, deleted=True)
                cover_revision.save()
    elif model_name == 'publisher' and delete:
        for brand in revision.publisher.active_brands():
            brand_revision = BrandRevision.objects.clone_revision(brand=brand,
              changeset=changeset)
            brand_revision.deleted = True
            brand_revision.save()
        for indicia_publisher in revision.publisher.active_indicia_publishers():
            indicia_publisher_revision = \
              IndiciaPublisherRevision.objects.clone_revision(
                indicia_publisher=indicia_publisher, changeset=changeset)
            indicia_publisher_revision.deleted = True
            indicia_publisher_revision.save()
        for imprint in revision.publisher.imprint_set.all():
            imprint_revision = PublisherRevision.objects.clone_revision(
              publisher=imprint, changeset=changeset)
            imprint_revision.deleted = True
            imprint_revision.save()

    return changeset

@permission_required('gcd.can_reserve')
def edit_revision(request, id, model_name):
    revision = get_object_or_404(REVISION_CLASSES[model_name], id=id)
    form_class = get_revision_form(revision)
    form = form_class(instance=revision)
    return _display_edit_form(request, revision.changeset, form, revision)

@permission_required('gcd.can_reserve')
def edit(request, id):
    changeset = get_object_or_404(Changeset, id=id)
    form = None
    revision = None
    if changeset.inline():
        revision = changeset.inline_revision()
        form_class = get_revision_form(revision)
        form = form_class(instance=revision)

    # Note that for non-inline changesets, no form is expected so it may be None.
    return _display_edit_form(request, changeset, form, revision)

def _display_edit_form(request, changeset, form, revision=None):
    if revision is None or changeset.inline():
        template = 'oi/edit/changeset.html'
        if revision is None:
            revision = changeset.inline_revision()
    else:
        template = 'oi/edit/revision.html'

    response = render_to_response(
      template,
      {
        'changeset': changeset,
        'revision': revision,
        'form': form,
        'states': states,
      },
      context_instance=RequestContext(request))
    response['Cache-Control'] = "no-cache, no-store, max-age=0, must-revalidate"
    return response

@permission_required('gcd.can_reserve')
def submit(request, id):
    """
    Submit a change and go to the reservations queue.
    """
    if request.method != 'POST':
        return _cant_get(request)

    changeset = get_object_or_404(Changeset, id=id)
    if (request.user != changeset.indexer):
        return render_to_response('gcd/error.html',
          {'error_text': 'A change may only be submitted by its author.'},
          context_instance=RequestContext(request))

    changeset.submit(notes=request.POST['comments'])
    if changeset.approver is not None:
        if request.POST['comments']:
            comment = u'The submission includes the comment:\n"%s"' % \
                      request.POST['comments'] 
        else:
            comment = ''   
        email_body = u"""
Hello from the %s!


  You have a change for "%s" by %s to review. %s

Please go to %s to compare the changes.

thanks,
-the %s team
%s
""" % (settings.SITE_NAME,
           unicode(changeset),
           unicode(changeset.indexer.indexer),
           comment,
           settings.SITE_URL.rstrip('/') +
             urlresolvers.reverse('compare', kwargs={'id': changeset.id }),
           settings.SITE_NAME,
           settings.SITE_URL)

        changeset.approver.email_user('GCD change to review', email_body, 
          settings.EMAIL_INDEXING)
        
    return HttpResponseRedirect(urlresolvers.reverse('editing'))

def _save(request, form, changeset_id=None, revision_id=None, model_name=None):
    if form.is_valid():
        revision = form.save(commit=False)
        changeset = revision.changeset
        if 'comments' in form.cleaned_data and 'submit' not in request.POST:
            comments = form.cleaned_data['comments']
            if comments is not None and comments != '':
                revision.comments.create(commenter=request.user,
                                         changeset=changeset,
                                         text=comments,
                                         old_state=changeset.state,
                                         new_state=changeset.state)

        revision.save()
        if hasattr(revision, 'save_m2m'):
            revision.save_m2m()
        if 'submit' in request.POST:
            return submit(request, revision.changeset.id)
        if 'queue' in request.POST:
            return HttpResponseRedirect(urlresolvers.reverse('editing'))
        if 'save' in request.POST:
            return HttpResponseRedirect(urlresolvers.reverse('edit_revision',
              kwargs={ 'model_name': model_name, 'id': revision_id }))
        if 'save_return' in request.POST:
            return HttpResponseRedirect(urlresolvers.reverse('edit',
              kwargs={ 'id': revision.changeset.id }))
        return render_error(request, 'Revision saved but cannot determine which '
          'page to load now.  Contact an editor if this error persists.')

    revision = None
    if revision_id is not None:
        revision = get_object_or_404(REVISION_CLASSES[model_name], id=revision_id)
        changeset = revision.changeset
    else:
        changeset = get_object_or_404(Changeset, id=changeset_id)
    return _display_edit_form(request, changeset, form, revision)

@permission_required('gcd.can_reserve')
def retract(request, id):
    """
    Retract a pending change back into your reserved queue.
    """
    if request.method != 'POST':
        return _cant_get(request)
    changeset = get_object_or_404(Changeset, id=id)

    if request.user != changeset.indexer:
        return render_to_response('gcd/error.html',
          {'error_text': 'A change may only be retracted by its author.'},
          context_instance=RequestContext(request))
    changeset.retract(notes=request.POST['comments'])

    return HttpResponseRedirect(urlresolvers.reverse('edit',
                                                     kwargs={'id': changeset.id }))

@permission_required('gcd.can_reserve')
def confirm_discard(request, id, has_comment=0):
    """
    Indexer has to confirm the discard of a change.
    """
    changeset = get_object_or_404(Changeset, id=id)
    if request.user != changeset.indexer:
        return render_error(request,
          'Only the author of the changeset can access this page.',
          redirect=False)

    if not changeset.state in states.ACTIVE:
        return render_error(request,
          'Only ACTIVE changes can be discarded.')

    if request.method != 'POST':
        return render_to_response('oi/edit/confirm_discard.html', 
                                  {'changeset': changeset },
                                  context_instance=RequestContext(request))

    if 'discard' in request.POST:
        if has_comment == '1' and changeset.approver:
            text = changeset.comments.latest('created').text
            comment = u'The discard includes the comment:\n"%s"' % text
        else:
            comment = ''   
        changeset.discard(discarder=request.user)
        if changeset.approver:
            email_body = u"""
Hello from the %s!


  The change for "%s" by %s which you were reviewing was discarded. %s

You can view the full change at %s.

thanks,
-the %s team
%s
""" % (settings.SITE_NAME,
               unicode(changeset),
               unicode(changeset.indexer.indexer),
               comment,
               settings.SITE_URL.rstrip('/') +
                 urlresolvers.reverse('compare', kwargs={'id': changeset.id }),
               settings.SITE_NAME,
               settings.SITE_URL)

            changeset.approver.email_user('Reviewed GCD change discarded', 
              email_body, settings.EMAIL_INDEXING)
        return HttpResponseRedirect(urlresolvers.reverse('editing'))
    else:
        # it would be nice if we would be able to go back the page
        # from where the 'discard' originated, but due to the
        # redirect we don't have this information here.
        return HttpResponseRedirect(urlresolvers.reverse('edit', 
                                    kwargs={'id': changeset.id }))
    
@permission_required('gcd.can_reserve')
def discard(request, id):
    """
    Discard a change and go to the reservations queue.
    """
    if request.method != 'POST':
        return _cant_get(request)
    changeset = get_object_or_404(Changeset, id=id)

    if (request.user != changeset.indexer and
        request.user != changeset.approver):
        return render_to_response('gcd/error.html',
          { 'error_text':
            'Only the author or the assigned editor can discard a change.' },
          context_instance=RequestContext(request))

    if request.user != changeset.indexer and not request.POST['comments']:
        return render_error(request,
                            'You must explain why you are rejecting this '
                            'change.  Please press the "back" button and use '
                            'the comments field for the explanation.' )

    # get a confirmation to avoid unwanted discards
    if request.user == changeset.indexer:
        if request.POST['comments']:
            notes = request.POST['comments']
            changeset.comments.create(commenter=request.user,
                                      text=notes,
                                      old_state=changeset.state,
                                      new_state=changeset.state)
            has_comment = 1
        else:
            has_comment = 0
        return HttpResponseRedirect(urlresolvers.reverse('confirm_discard',
                                    kwargs={'id': changeset.id,
                                            'has_comment': has_comment}))

    notes = request.POST['comments']
    changeset.discard(discarder=request.user, notes=notes)

    if request.user == changeset.approver:
        email_body = u"""
Hello from the %s!


  Your change for "%s" was rejected by GCD editor %s with the comment:
"%s"

You can view the full change at %s.

If you disagree please either contact the editor directly via the e-mail 
%s or post a message on the main mailing-list 
which is also reachable via http://groups.google.com/group/gcd-main.

thanks,
-the %s team
%s
""" % (settings.SITE_NAME,
           unicode(changeset),
           unicode(changeset.approver.indexer),
           notes,
           settings.SITE_URL.rstrip('/') +
             urlresolvers.reverse('compare', kwargs={'id': changeset.id }),
           changeset.approver.email,
           settings.SITE_NAME,
           settings.SITE_URL)

        changeset.indexer.email_user('GCD change rejected', email_body, 
          settings.EMAIL_INDEXING)

        if request.user.approved_changeset.filter(state=states.REVIEWING).count():
            return HttpResponseRedirect(urlresolvers.reverse('reviewing'))
        else:
            return HttpResponseRedirect(urlresolvers.reverse('pending'))

@permission_required('gcd.can_approve')
def assign(request, id):
    """
    Move a change into your approvals queue, and go to the queue.
    """
    if request.method != 'POST':
        return _cant_get(request)

    changeset = get_object_or_404(Changeset, id=id)
    if request.user == changeset.indexer:
        return render_error(request, 'You may not approve your own changes.')

    # TODO: rework error checking strategy.  This is a hack for the most
    # common case but we probably shouldn't be doing this check in the
    # model layer in the first place.  See tech bug #199.
    try:
        changeset.assign(approver=request.user, notes=request.POST['comments'])
    except ValueError:
        if changeset.approver is None:
            return render_error(request,
              'This change has been retracted by the indexer after you loaded '
              'the previous page. This results in you seeing an "Assign" '
              'button. Please use the back button to return to the Pending queue.',
              redirect=False)
        else:
            return render_error(request,
              ('This change is already being reviewed by %s who may have assigned it '
               'after you loaded the previous page.  This results in you seeing an '
               '"Assign" button even though the change is under review. '
               'Please use the back button to return to the Pending queue.') %
              changeset.approver.indexer,
              redirect=False)

    if changeset.indexer.indexer.is_new and \
       changeset.indexer.indexer.mentor is None and\
       changeset.coverrevisions.count() != 1:

        changeset.indexer.indexer.mentor = request.user
        changeset.indexer.indexer.save()

        for pending in changeset.indexer.changesets.filter(state=states.PENDING):
            try:
              pending.assign(approver=request.user, notes='')
            except ValueError:
                # Someone is already reviewing this.  Unlikely, and just let it go.
                pass

    if changeset.approver.indexer.collapse_compare_view:
        option = '?collapse=1'
    else:
        option = ''
    return HttpResponseRedirect(urlresolvers.reverse('compare', 
                                             kwargs={'id': changeset.id }) \
                                + option)

@permission_required('gcd.can_approve')
def release(request, id):
    """
    Move a change out of your approvals queue, and go back to your queue.
    """
    if request.method != 'POST':
        return _cant_get(request)

    changeset = get_object_or_404(Changeset, id=id)
    if request.user != changeset.approver:
        return render_to_response('gcd/error.html',
          {'error_text': 'A change may only be released by its approver.'},
          context_instance=RequestContext(request))
        
    changeset.release(notes=request.POST['comments'])

    if request.user.approved_changeset.filter(state=states.REVIEWING).count():
        return HttpResponseRedirect(urlresolvers.reverse('reviewing'))
    else:
        return HttpResponseRedirect(urlresolvers.reverse('pending'))

@permission_required('gcd.can_approve')
def approve(request, id):
    """
    Approve a change and return to your approvals queue.
    """
    if request.method != 'POST':
        return _cant_get(request)

    changeset = get_object_or_404(Changeset, id=id)
    if request.user != changeset.approver:
        return render_error(request,
          'A change may only be approved by its approver.')

    if changeset.state != states.REVIEWING or changeset.approver is None:
        return render_error(request,
          'Only REVIEWING changes with an approver can be approved.')

    notes = request.POST['comments']
    changeset.approve(notes=notes)

    email_comments = '.'
    postscript = ''
    if notes:
        email_comments = ' with the comment:\n"%s"' % notes
    else:
        postscript = """
PS: You can change your email settings on your profile page:
%s
Currently, your profile is set to receive emails about change approvals even
if the approver did not comment.  To turn these off, just edit your profile
and uncheck the "Approval emails" box.
""" % (settings.SITE_URL.rstrip('/') + urlresolvers.reverse('default_profile'))

    if changeset.indexer.indexer.notify_on_approve or notes.strip():
        email_body = u"""
Hello from the %s!


  Your change for "%s" was approved by GCD editor %s%s

You can view the full change at %s.

thanks,
-the %s team

%s
%s
""" % (settings.SITE_NAME,
       unicode(changeset),
       unicode(changeset.approver.indexer),
       email_comments,
       settings.SITE_URL.rstrip('/') +
         urlresolvers.reverse('compare', kwargs={'id': changeset.id }),
       settings.SITE_NAME,
       settings.SITE_URL,
       postscript)


        changeset.indexer.email_user('GCD change approved', email_body, 
          settings.EMAIL_INDEXING)


    # Note that series ongoing reservations must be processed first, as
    # they could potentially apply to the issue reservations if we ever
    # implement complex changesets.
    for series_revision in \
        changeset.seriesrevisions.filter(deleted=False,
                                         reservation_requested=True,
                                         series__created__gt=F('created'),
                                         series__is_current=True,
                                         series__ongoing_reservation=None):
        if (changeset.indexer.ongoing_reservations.count() >=
            changeset.indexer.indexer.max_ongoing):
            _send_declined_ongoing_email(changeset.indexer, series_revision.series)

        ongoing = OngoingReservation(indexer=changeset.indexer,
                                     series=series_revision.series)
        ongoing.save()

    for issue_revision in \
        changeset.issuerevisions.filter(deleted=False,
                                        reservation_requested=True,
                                        issue__created__gt=F('created'),
                                        series__ongoing_reservation=None):
        new_change = _do_reserve(changeset.indexer, issue_revision.issue, 'issue')
        if new_change is None:
            _send_declined_reservation_email(changeset.indexer,
                                             issue_revision.issue)
        else:
            issue_revision.issue.reserved = True
            issue_revision.issue.save()

    for issue_revision in \
        changeset.issuerevisions.filter(deleted=False,
                                        issue__created__gt=F('created'),
                                        series__ongoing_reservation__isnull=False):
        new_change = _do_reserve(issue_revision.series.ongoing_reservation.indexer,
                                 issue_revision.issue, 'issue')
        if new_change is None:
            _send_declined_reservation_email(issue_revision.series.\
                                             ongoing_reservation.indexer,
                                             issue_revision.issue)
        else:
            issue_revision.issue.reserved = True
            issue_revision.issue.save()

    for cover_revision in changeset.coverrevisions.filter(deleted=False):
        copy_approved_cover(cover_revision)

    # Move brand new indexers to probationary status on first approval.
    if changeset.change_type is not CTYPES['cover'] and \
      changeset.indexer.indexer.max_reservations == settings.RESERVE_MAX_INITIAL:
        i = changeset.indexer.indexer
        i.max_reservations = settings.RESERVE_MAX_PROBATION
        i.max_ongoing = settings.RESERVE_MAX_ONGOING_PROBATION
        i.save()

    if request.user.approved_changeset.filter(state=states.REVIEWING).count():
        return HttpResponseRedirect(urlresolvers.reverse('reviewing'))
    else:
        # to avoid counting assume for now that cover queue is never empty
        if changeset.change_type is CTYPES['cover']:
            return HttpResponseRedirect(urlresolvers.reverse('pending_covers'))
        else:
            return HttpResponseRedirect(urlresolvers.reverse('pending'))

def _send_declined_reservation_email(indexer, issue):
    email_body = u"""
Hello from the %s!


  Your requested reservation of issue "%s" was declined because you have
reached your maximum number of open changes.  Please visit your editing
queue at %s%s and submit or discard some changes and then
try your edit again.

  Your maximum change limit starts low as a new user but is increased as
more of your changes are approved.

thanks,
-the %s team
%s
""" % (settings.SITE_NAME,
       issue,
       settings.SITE_URL,
       urlresolvers.reverse('editing'),
       settings.SITE_NAME, settings.SITE_URL)

    indexer.email_user('GCD automatic reservation declined',
      email_body, 
      settings.EMAIL_INDEXING)

def _send_declined_ongoing_email(indexer, series):
    course_of_action = ("Please contact a GCD Editor on the gcd_main group "
                        "(http://groups.google.com/group/gcd-main/) "
                        "if you would like to request a limit increase.")
    if indexer.indexer.is_new:
        course_of_action = ("As a new user you will gain the ability to hold "
                            "series revisions as your initial changes get "
                            "approved.")
    email_body = u"""
Hello from the %s!


  Your requested ongoing reservation of series "%s" was declined because you have
reached your maximum number of ongoing reservations.  %s

thanks,
-the %s team
%s
""" % (settings.SITE_NAME,
       series,
       course_of_action,
       settings.SITE_NAME, settings.SITE_URL)

    indexer.email_user('GCD automatic reservation declined',
      email_body, 
      settings.EMAIL_INDEXING)

@permission_required('gcd.can_approve')
def disapprove(request, id):
    """
    Disapprove a change and return to your approvals queue.
    """
    if request.method != 'POST':
        return _cant_get(request)

    changeset = get_object_or_404(Changeset, id=id)
    if request.user != changeset.approver:
        return render_error(request,
          'A change may only be rejected by its approver.')

    if not request.POST['comments']:
        return render_error(request,
                            'You must explain why you are disapproving this '
                            'change.  Please press the "back" button and use '
                            'the comments field for the explanation.')

    notes = request.POST['comments']
    changeset.disapprove(notes=notes)

    email_body = u"""
Hello from the %s!


  Your change for "%s" was sent back by GCD editor %s with the comment:
"%s"

Please go to %s to re-edit or reply.

thanks,
-the %s team
%s
""" % (settings.SITE_NAME,
       unicode(changeset),
       unicode(changeset.approver.indexer),
       notes,
       settings.SITE_URL.rstrip('/') +
         urlresolvers.reverse('edit', kwargs={'id': changeset.id }),
       settings.SITE_NAME,
       settings.SITE_URL)

    changeset.indexer.email_user('GCD change sent back', email_body, 
      settings.EMAIL_INDEXING)

    if request.user.approved_changeset.filter(state=states.REVIEWING).count():
        return HttpResponseRedirect(urlresolvers.reverse('reviewing'))
    else:
        return HttpResponseRedirect(urlresolvers.reverse('pending'))


@permission_required('gcd.can_reserve')
def add_comments(request, id):
    """
    Comment on a change and return to the compare page.
    """
    if request.method != 'POST':
        return _cant_get(request)

    changeset = get_object_or_404(Changeset, id=id)
    comments = request.POST['comments']
    if comments is not None and comments != '':
        changeset.comments.create(commenter=request.user,
                                  text=comments,
                                  old_state=changeset.state,
                                  new_state=changeset.state)

        email_body = u"""
Hello from the %s!


  %s added a comment to the change "%s":
"%s"

You can view the full change at %s.

thanks,
-the %s team
%s
""" % (settings.SITE_NAME,
           unicode(request.user.indexer),
           unicode(changeset),
           comments,
           settings.SITE_URL.rstrip('/') +
             urlresolvers.reverse('compare', kwargs={'id': changeset.id }),
           settings.SITE_NAME,
           settings.SITE_URL)

        if request.user != changeset.indexer:
            changeset.indexer.email_user('GCD comment', email_body, 
              settings.EMAIL_INDEXING)
        if changeset.approver and request.user != changeset.approver:
            changeset.approver.email_user('GCD comment', email_body, 
              settings.EMAIL_INDEXING)

    return HttpResponseRedirect(urlresolvers.reverse(compare,
                                                     kwargs={ 'id': id }))

@permission_required('gcd.can_reserve')
def process(request, id):
    """
    Entry point for forms with multiple actions.

    This handles adding comments (with no state change) directly, and routes
    the request to other views for all other cases.
    """
    if request.method != 'POST':
        return _cant_get(request)

    if 'submit' in request.POST:
        changeset = get_object_or_404(Changeset, id=id)
        if changeset.inline():
            revision = changeset.inline_revision()
            form_class = get_revision_form(revision)
            form = form_class(request.POST, instance=revision)
            return _save(request, form, changeset_id=id)
        else:
            return submit(request, id)

    if 'retract' in request.POST:
        return retract(request, id)

    if 'discard' in request.POST or 'cancel' in request.POST:
        return discard(request, id)

    if 'assign' in request.POST:
        return assign(request, id)

    if 'release' in request.POST:
        return release(request, id)

    if 'approve' in request.POST:
        return approve(request, id)

    if 'disapprove' in request.POST:
        return disapprove(request, id)

    if 'add_comment' in request.POST:
        return add_comments(request, id)
        
    return render_error(request, 'Unknown action requested!  Please try again. '
      'If this error message persists, please contact an Editor.')

@permission_required('gcd.can_reserve')
def process_revision(request, id, model_name):
    if request.method != 'POST':
        return _cant_get(request)

    if 'cancel_return' in request.POST:
        revision = get_object_or_404(REVISION_CLASSES[model_name], id=id)
        return HttpResponseRedirect(urlresolvers.reverse('edit',
          kwargs={ 'id': revision.changeset.id }))

    if 'save' in request.POST or 'save_return' in request.POST:
        revision = get_object_or_404(REVISION_CLASSES[model_name], id=id)
        form = get_revision_form(revision)(request.POST, instance=revision)
        return _save(request, form=form, revision_id=id, model_name=model_name)

    return render_error(request,
      'Unknown action requested!  Please try again.  If this error message '
      'persists, please contact an Editor.')


##############################################################################
# Bulk Changes
##############################################################################
def _clean_bulk_issue_change_form(form, remove_fields, items,
                                  number_of_issues=True):
    form.fields.pop('after')
    form.fields.pop('first_number')
    if number_of_issues:
        form.fields.pop('number_of_issues')
    for i in remove_fields:
        form.fields.pop(i)
    return form

@permission_required('gcd.can_reserve')
def edit_issues_in_bulk(request):
    if not request.user.indexer.can_reserve_another():
        return render_error(request,
          'You have reached your limit of open changes.  You must '
          'submit or discard some changes from your edit queue before you '
          'can edit any more.  If you are a new user this number is very low '
          'but will be increased as your first changes are approved.')

    if request.method == 'GET' and request.GET['target'] != 'issue':
        return HttpResponseRedirect(urlresolvers.reverse \
                 ('process_advanced_search') + '?' + request.GET.urlencode())

    if request.method == 'POST' and 'cancel' in request.POST:
        return HttpResponseRedirect(urlresolvers.reverse \
                 ('process_advanced_search') + '?' + request.GET.urlencode())

    search_values = request.GET.copy()
    context = {}
    target, method, logic, used_search_terms = used_search(search_values)

    try:
        items, target_name = do_advanced_search(request)
    except ViewTerminationError:
        return render_error(request, 
            'The search underlying the bulk change was not successful. '
            'This should not happen. Please try again. If this error message '
            'persists, please contact an Editor.')

    nr_items = items.count()
    items = items.filter(reserved=False)
    nr_items_unreserved = items.count()
    if nr_items_unreserved == 0:
        if nr_items == 0: # shouldn't really happen
            return HttpResponseRedirect(urlresolvers.reverse \
                     ('process_advanced_search') + '?' + \
                     request.GET.urlencode())
        else:
            return render_error(request, 
              'All issues fulfilling the search criteria for the bulk change'
              ' are currently reserved.')

    series_list = list(set(items.values_list('series', flat=True)))
    ignore_publisher = False
    if len(series_list) == 1:
        series = Series.objects.get(id=series_list[0])
    else:
        if len(items) > 100: # shouldn't happen, just in case
            raise ValueError, 'not more than 100 issues if more than one series'
        series = Series.objects.exclude(deleted=True).filter(id__in=series_list)
        publisher_list = Publisher.objects.exclude(deleted=True) \
          .filter(series__in=series).distinct()
        series = series[0]
        if len(publisher_list) > 1:
            ignore_publisher = True

    form_class = get_bulk_issue_revision_form(series, 'number')

    # We should be able to access the fields without a dummy revision, or ?
    fields = IssueRevision._field_list(IssueRevision.objects.get(id=1))
    fields.remove('after')
    fields.remove('number')
    fields.remove('publication_date')
    fields.remove('key_date')
    fields.remove('isbn')
    fields.remove('notes')

    # look at values for the issue fields
    # if only one it gives the initial value
    # if several, the field is not editable
    initial = {} # init value is the common value for all issues
    remove_fields = [] # field to take out of the form
    if ignore_publisher:
        remove_fields.append('brand')
        remove_fields.append('no_brand')
        remove_fields.append('indicia_publisher')
        remove_fields.append('indicia_pub_not_printed')
    for i in fields:
        if i not in remove_fields: 
            values_list = list(set(items.values_list(i, flat=True)))
            if len(values_list) > 1:
                if i not in remove_fields: 
                    remove_fields.append(i)
                    # some fields belong together, both are either in or out
                    if i in ['volume', 'brand', 'editing']:
                        remove_fields.append('no_' + i)
                    elif i in ['no_volume', 'no_brand', 'no_indicia_publisher',
                            'no_editing']:
                        if i[3:] not in remove_fields:
                            remove_fields.append(i[3:])
                    elif i == 'indicia_publisher':
                        remove_fields.append('indicia_pub_not_printed')
                    elif i == 'indicia_pub_not_printed':
                        remove_fields.append('indicia_publisher')
                    elif i == 'page_count':
                        remove_fields.append('page_count_uncertain')
                    elif i == 'page_count_uncertain':
                        remove_fields.append('page_count')
            elif i not in remove_fields:
                initial[i] = values_list[0]

    if request.method != 'POST':
        form = _clean_bulk_issue_change_form(form_class(initial=initial), 
                                             remove_fields, items)
        return _display_bulk_issue_change_form(request, form,
                nr_items, nr_items_unreserved, 
                request.GET.urlencode(), target, method, logic,
                used_search_terms)

    form = form_class(request.POST)
    form.fields.pop('number_of_issues')

    if not form.is_valid():
        form = _clean_bulk_issue_change_form(form, remove_fields, items,
                                             number_of_issues=False)
        return _display_bulk_issue_change_form(request, form,
                nr_items, nr_items_unreserved, 
                request.GET.urlencode(), target, method, logic,
                used_search_terms)

    changeset = Changeset(indexer=request.user, state=states.OPEN,
                          change_type=CTYPES['issue_bulk'])
    changeset.save()
    comment = 'Used search terms:\n'
    for search in used_search_terms:
        comment += "%s : %s\n" % (search[0], search[1])
    comment += "method : %s\n" % method
    comment += "behavior : %s\n" % logic

    changeset.comments.create(commenter=request.user,
                              text=comment,
                              old_state=changeset.state,
                              new_state=changeset.state)

    cd = form.cleaned_data
    for issue in items:
        is_reservable = _is_reservable('issue', issue.id)
        if is_reservable:
            revision = IssueRevision.objects.clone_revision(issue,
                                                            changeset=changeset)
            for field in initial:
                if field in ['brand', 'indicia_publisher'] and cd[field] is not None:
                    setattr(revision, field + '_id', cd[field].id)
                else:
                    setattr(revision, field, cd[field])
            revision.save()

    return submit(request, changeset.id)

def _display_bulk_issue_change_form(request, form, 
                                    nr_items, nr_items_unreserved,
                                    search_option, 
                                    target, method, logic, used_search_terms):
    url_name = 'edit_issues_in_bulk'
    url = urlresolvers.reverse(url_name) + '?' + search_option
    return render_to_response('oi/edit/bulk_frame.html',
      {
        'object_name': 'Issues',
        'object_url': url,
        'action_label': 'Submit bulk change',
        'form': form,
        'nr_items': nr_items,
        'nr_items_unreserved': nr_items_unreserved,
        'target': target,
        'method': method,
        'logic': logic,
        'used_search_terms': used_search_terms,
      },
      context_instance=RequestContext(request))

##############################################################################
# Adding Items
##############################################################################

@permission_required('gcd.can_reserve')
def add_publisher(request):
    if not request.user.indexer.can_reserve_another():
        return render_error(request,
          'You have reached your limit of open changes.  You must '
          'submit or discard some changes from your edit queue before you '
          'can edit any more.  If you are a new user this number is very low '
          'but will be increased as your first changes are approved.')

    if request.method != 'POST':
        form = get_publisher_revision_form()()
        return _display_add_publisher_form(request, form)

    if 'cancel' in request.POST:
        return HttpResponseRedirect(urlresolvers.reverse('add'))

    form = get_publisher_revision_form()(request.POST)
    if not form.is_valid():
        return _display_add_publisher_form(request, form)

    changeset = Changeset(indexer=request.user, state=states.OPEN,
                          change_type=CTYPES['publisher'])
    changeset.save()
    revision = form.save(commit=False)
    revision.save_added_revision(changeset=changeset,
                                 parent=None)
    return submit(request, changeset.id)

def _display_add_publisher_form(request, form):
    object_name = 'Publisher'
    object_url = urlresolvers.reverse('add_publisher')

    return render_to_response('oi/edit/add_frame.html',
      {
        'object_name': object_name,
        'object_url': object_url,
        'action_label': 'Submit new',
        'form': form,
      },
      context_instance=RequestContext(request))

@permission_required('gcd.can_reserve')
def add_indicia_publisher(request, parent_id):
    if not request.user.indexer.can_reserve_another():
        return render_error(request,
          'You have reached your limit of open changes.  You must '
          'submit or discard some changes from your edit queue before you '
          'can edit any more.  If you are a new user this number is very low '
          'but will be increased as your first changes are approved.')

    try:
        parent = Publisher.objects.get(id=parent_id, is_master=True)
        if parent.deleted or parent.pending_deletion():
            return render_error(request, u'Cannot add indicia publishers '
              u'since "%s" is deleted or pending deletion.' % parent)

        if request.method != 'POST':
            form = get_indicia_publisher_revision_form()()
            return _display_add_indicia_publisher_form(request, parent, form)

        if 'cancel' in request.POST:
            return HttpResponseRedirect(urlresolvers.reverse(
              'apps.gcd.views.details.publisher',
              kwargs={ 'publisher_id': parent_id }))

        form = get_indicia_publisher_revision_form()(request.POST)
        if not form.is_valid():
            return _display_add_indicia_publisher_form(request, parent, form)

        changeset = Changeset(indexer=request.user, state=states.OPEN,
                              change_type=CTYPES['indicia_publisher'])
        changeset.save()
        revision = form.save(commit=False)
        revision.save_added_revision(changeset=changeset,
                                     parent=parent)
        return submit(request, changeset.id)

    except (Publisher.DoesNotExist, Publisher.MultipleObjectsReturned):
        return render_error(request,
          'Could not find publisher for id ' + publisher_id)

def _display_add_indicia_publisher_form(request, parent, form):
    object_name = 'Indicia Publisher'
    object_url = urlresolvers.reverse('add_indicia_publisher',
                                          kwargs={ 'parent_id': parent.id })

    return render_to_response('oi/edit/add_frame.html',
      {
        'object_name': object_name,
        'object_url': object_url,
        'action_label': 'Submit new',
        'form': form,
      },
      context_instance=RequestContext(request))

@permission_required('gcd.can_reserve')
def add_brand(request, parent_id):
    if not request.user.indexer.can_reserve_another():
        return render_error(request,
          'You have reached your limit of open changes.  You must '
          'submit or discard some changes from your edit queue before you '
          'can edit any more.  If you are a new user this number is very low '
          'but will be increased as your first changes are approved.')

    try:
        parent = Publisher.objects.get(id=parent_id, is_master=True)
        if parent.deleted or parent.pending_deletion():
            return render_error(request, u'Cannot add brands '
              u'since "%s" is deleted or pending deletion.' % parent)

        if request.method != 'POST':
            form = get_brand_revision_form()()
            return _display_add_brand_form(request, parent, form)

        if 'cancel' in request.POST:
            return HttpResponseRedirect(urlresolvers.reverse(
              'apps.gcd.views.details.publisher',
              kwargs={ 'publisher_id': parent_id }))

        form = get_brand_revision_form()(request.POST)
        if not form.is_valid():
            return _display_add_brand_form(request, parent, form)

        changeset = Changeset(indexer=request.user, state=states.OPEN,
                              change_type=CTYPES['brand'])
        changeset.save()
        revision = form.save(commit=False)
        revision.save_added_revision(changeset=changeset,
                                     parent=parent)
        return submit(request, changeset.id)

    except (Publisher.DoesNotExist, Publisher.MultipleObjectsReturned):
        return render_error(request,
          'Could not find publisher for id ' + publisher_id)

def _display_add_brand_form(request, parent, form):
    object_name = 'Brand'
    object_url = urlresolvers.reverse('add_brand',
                                      kwargs={ 'parent_id': parent.id })

    return render_to_response('oi/edit/add_frame.html',
      {
        'object_name': object_name,
        'object_url': object_url,
        'action_label': 'Submit new',
        'form': form,
      },
      context_instance=RequestContext(request))

@permission_required('gcd.can_reserve')
def add_series(request, publisher_id):
    if not request.user.indexer.can_reserve_another():
        return render_error(request,
          'You have reached your limit of open changes.  You must '
          'submit or discard some changes from your edit queue before you '
          'can edit any more.  If you are a new user this number is very low '
          'but will be increased as your first changes are approved.')

    # Process add form if this is a POST.
    try:
        publisher = Publisher.objects.get(id=publisher_id)
        if publisher.deleted or publisher.pending_deletion():
            return render_error(request, u'Cannot add series '
              u'since "%s" is deleted or pending deletion.' % publisher)

        imprint = None
        if publisher.parent is not None:
            return render_error(request, 'Series may no longer be added to '
              'imprints.  Add the series to the master publisher, and then set '
              'the indicia publisher(s) and/or brand(s) at the issue level.')

        if request.method != 'POST':
            initial = {}
            initial['country'] = publisher.country.id
            form = get_series_revision_form(publisher,
                                            indexer=request.user)(initial=initial)
            return _display_add_series_form(request, publisher, imprint, form)

        if 'cancel' in request.POST:
            return HttpResponseRedirect(urlresolvers.reverse(
              'apps.gcd.views.details.publisher',
              kwargs={ 'publisher_id': publisher_id }))

        form = get_series_revision_form(publisher,
                                        indexer=request.user)(request.POST)
        if not form.is_valid():
            return _display_add_series_form(request, publisher, imprint, form)

        changeset = Changeset(indexer=request.user, state=states.OPEN,
                              change_type=CTYPES['series'])
        changeset.save()
        revision = form.save(commit=False)
        revision.save_added_revision(changeset=changeset,
                                     publisher=publisher,
                                     imprint=imprint)
        return submit(request, changeset.id)

    except (Publisher.DoesNotExist, Publisher.MultipleObjectsReturned):
        return render_error(request,
          'Could not find publisher or imprint for id ' + publisher_id)

def _display_add_series_form(request, publisher, imprint, form):
    kwargs = {
        'publisher_id': publisher.id,
    }
    url = urlresolvers.reverse('add_series', kwargs=kwargs)
    return render_to_response('oi/edit/add_frame.html',
      {
        'object_name': 'Series',
        'object_url': url,
        'action_label': 'Submit new',
        'form': form,
      },
      context_instance=RequestContext(request))

@permission_required('gcd.can_reserve')
def add_issue(request, series_id, sort_after=None):
    if not request.user.indexer.can_reserve_another():
        return render_error(request,
          'You have reached your limit of open changes.  You must '
          'submit or discard some changes from your edit queue before you '
          'can edit any more.  If you are a new user this number is very low '
          'but will be increased as your first changes are approved.')

    series = get_object_or_404(Series, id=series_id)
    if series.deleted or series.pending_deletion():
        return render_error(request, u'Cannot add an issue '
          u'since "%s" is deleted or pending deletion.' % series)

    form_class = get_revision_form(model_name='issue',
                                   series=series,
                                   publisher=series.publisher)

    if request.method != 'POST':
        reversed_issues = series.active_issues().order_by('-sort_code')
        initial = {}
        if reversed_issues.count():
            initial['after'] = reversed_issues[0].id
        form = form_class(initial=initial)
        return _display_add_issue_form(request, series, form)

    if 'cancel' in request.POST:
        return HttpResponseRedirect(urlresolvers.reverse(
          'apps.gcd.views.details.series',
          kwargs={ 'series_id': series_id }))

    form = form_class(request.POST)
    if not form.is_valid():
        return _display_add_issue_form(request, series, form)

    changeset = Changeset(indexer=request.user, state=states.OPEN,
                          change_type=CTYPES['issue_add'])
    changeset.save()
    revision = form.save(commit=False)
    revision.save_added_revision(changeset=changeset,
                                 series=series)
    return submit(request, changeset.id)

def _display_add_issue_form(request, series, form):
    kwargs = {
        'series_id': series.id,
    }
    url = urlresolvers.reverse('add_issue', kwargs=kwargs)
    return render_to_response('oi/edit/add_frame.html',
      {
        'object_name': 'Issue',
        'object_url': url,
        'action_label': 'Submit new',
        'form': form,
      },
      context_instance=RequestContext(request))

@permission_required('gcd.can_reserve')
def add_issues(request, series_id, method=None):
    if not request.user.indexer.can_reserve_another():
        return render_error(request,
          'You have reached your limit of open changes.  You must '
          'submit or discard some changes from your edit queue before you '
          'can edit any more.  If you are a new user this number is very low '
          'but will be increased as your first changes are approved.')

    issue_annotated = Changeset.objects.annotate(
      issue_revision_count=Count('issuerevisions'))
    issue_adds = issue_annotated.filter(issue_revision_count__gte=1) \
                                .filter(issuerevisions__issue=None) \
                                .filter(issuerevisions__series__id=series_id) \
                                .filter(state__in=states.ACTIVE)
    series = get_object_or_404(Series, id=series_id)
    if series.deleted or series.pending_deletion():
        return render_error(request, u'Cannot add issues '
          u'since "%s" is deleted or pending deletion.' % series)

    if method is None:
        return render_to_response('oi/edit/add_issues.html',
                                  { 'series': series, 
                                    'issue_adds' : issue_adds },
                                  context_instance=RequestContext(request))

    form_class = get_bulk_issue_revision_form(series=series, method=method)

    if request.method != 'POST':
        reversed_issues = series.active_issues().order_by('-sort_code')
        initial = {}
        if reversed_issues.count():
            initial['after'] = reversed_issues[0].id
        form = form_class(initial=initial)
        return _display_bulk_issue_form(request, series, form, method)

    if 'cancel' in request.POST:
        return HttpResponseRedirect(urlresolvers.reverse(
          'apps.gcd.views.details.series',
          kwargs={ 'series_id': series_id }))

    form = form_class(request.POST)
    if not form.is_valid():
        return _display_bulk_issue_form(request, series, form, method)

    changeset = Changeset(indexer=request.user, state=states.OPEN,
                          change_type=CTYPES['issue_add'])
    changeset.save()
    if method == 'number':
        new_issues = _build_whole_numbered_issues(series, form, changeset)
    elif method == 'volume':
        new_issues = _build_per_volume_issues(series, form, changeset)
    elif method == 'year':
        new_issues = _build_per_year_issues(series, form, changeset)
    elif method == 'year_volume':
        new_issues = _build_per_year_volume_issues(series, form, changeset)
    else:
        return render_error(request,
          'Unknown method for generating issues: %s' % method)

    # "after" for the rest of the issues gets set when they are all
    # committed to display.
    new_issues[0].after = form.cleaned_data['after']
    for revision in new_issues:
        revision.save_added_revision(changeset=changeset, series=series)

    return submit(request, changeset.id)

def _build_whole_numbered_issues(series, form, changeset):
    issue_revisions = []
    cd = form.cleaned_data
    first_number = cd['first_number']
    increment = 0
    for number in range(first_number, first_number + cd['number_of_issues']):
        issue_revisions.append(_build_issue(form, revision_sort_code=increment,
          number=number,
          volume=cd['volume'],
          no_volume=cd['no_volume'],
          display_volume_with_number=cd['display_volume_with_number']))
        increment += 1
    return issue_revisions

def _build_per_volume_issues(series, form, changeset):
    issue_revisions = []
    cd = form.cleaned_data
    first_number = cd['first_number']
    num_issues = cd['number_of_issues']
    per_volume = cd['issues_per_volume']
    current_volume = cd['first_volume']
    for increment in range(0, num_issues):
        current_number = (first_number + increment) % per_volume
        if current_number == 0:
            current_number = per_volume
        elif increment > 0 and current_number == 1:
            current_volume += 1
        issue_revisions.append(_build_issue(form, revision_sort_code=increment,
          number=current_number,
          volume=current_volume,
          no_volume=False,
          display_volume_with_number=True))
    return issue_revisions

def _build_per_year_issues(series, form, changeset):
    issue_revisions = []
    cd = form.cleaned_data
    first_number = cd['first_number']
    num_issues = cd['number_of_issues']
    per_year = cd['issues_per_year']
    current_year = cd['first_year']
    for increment in range(0, num_issues):
        current_number = (first_number + increment) % per_year
        if current_number == 0:
            current_number = per_year
        elif increment > 0 and current_number == 1:
            current_year +=1
        issue_revisions.append(_build_issue(form, revision_sort_code=increment,
          number='%d/%d' % (current_number, current_year),
          volume=cd['volume'],
          no_volume=cd['no_volume'],
          display_volume_with_number=cd['display_volume_with_number']))
    return issue_revisions

def _build_per_year_volume_issues(series, form, changeset):
    issue_revisions = []
    cd = form.cleaned_data
    first_number = cd['first_number']
    num_issues = cd['number_of_issues']
    per_cycle = cd['issues_per_cycle']
    current_year = cd['first_year']
    current_volume = cd['first_volume']
    for increment in range(0, num_issues):
        current_number = (first_number + increment) % per_cycle
        if current_number == 0:
            current_number = per_cycle
        elif increment > 0 and current_number == 1:
            current_year +=1
            current_volume +=1
        issue_revisions.append(_build_issue(form, revision_sort_code=increment,
          number='%d/%d' % (current_number, current_year),
          volume=current_volume,
          no_volume=False,
          display_volume_with_number=cd['display_volume_with_number']))
    return issue_revisions

def _build_issue(form, revision_sort_code, number,
                 volume, no_volume, display_volume_with_number):
    cd = form.cleaned_data
    # Don't specify series and changeset as save_added_revision handles that.
    return IssueRevision(
      number=number,
      volume=volume,
      no_volume=no_volume,
      display_volume_with_number=display_volume_with_number,
      indicia_publisher=cd['indicia_publisher'],
      brand=cd['brand'],
      indicia_frequency=cd['indicia_frequency'],
      price=cd['price'],
      page_count=cd['page_count'],
      page_count_uncertain=cd['page_count_uncertain'],
      editing=cd['editing'],
      no_editing=cd['no_editing'],
      revision_sort_code=revision_sort_code)
    issue_revisions.append(revision)
    return issue_revisons

def _display_bulk_issue_form(request, series, form, method=None):
    kwargs = {
        'series_id': series.id,
    }
    url_name = 'add_issues'
    if method is not None:
        kwargs['method'] = method
        url_name = 'add_multiple_issues'
    url = urlresolvers.reverse(url_name, kwargs=kwargs)
    return render_to_response('oi/edit/add_frame.html',
      {
        'object_name': 'Issues',
        'object_url': url,
        'action_label': 'Submit new',
        'form': form,
      },
      context_instance=RequestContext(request))


@permission_required('gcd.can_reserve')
def add_story(request, issue_id, changeset_id):
    changeset = get_object_or_404(Changeset, id=changeset_id)
    if request.user != changeset.indexer:
        return render_error(request,
          'Only the reservation holder may add stories.')
    # Process add form if this is a POST.
    try:
        # If we're adding stories we're guaranteed to only have one issue rev.
        issue_revision = changeset.issuerevisions.all()[0]
        issue = Issue.objects.get(id=issue_id)
        if request.method != 'POST':
            seq = request.GET['added_sequence_number']
            if seq == '':
                return render_error(request,
                  'You must supply a sequence number for the new story.',
                  redirect=False)
            else:
                initial = _get_initial_add_story_data(request, issue_revision, seq)
                form = get_story_revision_form()(initial=initial)
            return _display_add_story_form(request, issue, form, changeset_id)

        if 'cancel_return' in request.POST:
            return HttpResponseRedirect(urlresolvers.reverse('edit',
              kwargs={ 'id': changeset_id }))

        form = get_story_revision_form()(request.POST)
        if not form.is_valid():
            return _display_add_story_form(request, issue, form, changeset_id)


        revision = form.save(commit=False)
        stories = issue_revision.active_stories()
        _reorder_children(request, issue_revision, stories, 'sequence_number',
                          stories, commit=True, unique=False, skip=revision)

        revision.save_added_revision(changeset=changeset,
                                     issue=issue)
        if form.cleaned_data['comments']:
            revision.comments.create(commenter=request.user,
                                     changeset=changeset,
                                     text=form.cleaned_data['comments'],
                                     old_state=changeset.state,
                                     new_state=changeset.state)
        return HttpResponseRedirect(urlresolvers.reverse('edit',
          kwargs={ 'id': changeset.id }))

    except ViewTerminationError as vte:
        return vte.response

    except (Issue.DoesNotExist, Issue.MultipleObjectsReturned):
        return render_error(request,
          'Could not find issue for id ' + issue_id)

def _get_initial_add_story_data(request, issue_revision, seq):
    # First, if we have an integer sequence number, make certain it's
    # not a duplicate as we can't tell if they meant above or below.
    # Since all sequence numbers in the database are integers,
    # if we have a non-int then we know it's not a dupe.
    try:
        seq_num = int(seq)
        if issue_revision.story_set.filter(sequence_number=seq_num)\
                                   .count():
            raise ViewTerminationError(render_error(request,
              "New stories must be added with a sequence number that "
              "is not already in use.  You may use a decimal number "
              "to insert a sequence between two existing sequences, "
              "or a negative number to insert before sequence zero.",
              redirect=False))

    except ValueError:
        try:
            float_num = float(seq)
        except ValueError:
            raise ViewTerminationError(render_error(request,
              "Sequence number must be a number.", redirect=False))

        # Now convert to the next int above the float.  If this
        # is a duplicate that's OK because we know that the user
        # intended the new sequence to go *before* the existing one.
        # int(float) truncates towards zero, hence adding 1 to positive
        # float values.
        if float_num > 0:
            float_num += 1
        seq_num = int(float_num)

    initial = {'no_editing' : True }
    if seq_num == 0:
        # Do not default other sequences, because if we do we
        # will get a lot of people leaving the default values
        # by accident.  Only sequence zero is predictable.
        initial['type'] = StoryType.objects.get(name='cover').id
        initial['no_script'] = True

    initial['sequence_number'] = seq_num 
    return initial

def _display_add_story_form(request, issue, form, changeset_id):
    kwargs = {
        'issue_id': issue.id,
        'changeset_id': changeset_id,
    }
    url = urlresolvers.reverse('add_story', kwargs=kwargs)
    return render_to_response('oi/edit/add_frame.html',
      {
        'object_name': 'Story',
        'object_url': url,
        'action_label': 'Save',
        'form': form,
      },
      context_instance=RequestContext(request))

##############################################################################
# Removing Items from a Changeset
##############################################################################

@permission_required('gcd.can_reserve')
def remove_story_revision(request, id):
    story = get_object_or_404(StoryRevision, id=id)
    if request.user != story.changeset.indexer:
        return render_error(request,
          'Only the reservation holder may remove stories.')

    # if user manually tries to permanently remove a sequence revision
    # that came from a pre-existing sequence, toggle the deleted flag
    # instead
    if story.source:
        return toggle_delete_story_revision(request, id)

    if request.method != 'POST':
        return render_to_response('oi/edit/remove_story_revision.html',
        {
            'story' : story,
            'issue' : story.issue
        },
        context_instance=RequestContext(request))
    
    # we fully delete the freshly added sequence, but first check if a 
    # comment is attached.
    if story.comments.count():
        comment = story.comments.latest('created')
        # might be set anyway. But if we don't set it we would get <span ... 
        # in the response and we cannot mark a comment as safe.
        if not story.page_count:
            story.page_count_uncertain = True
        comment.text += '\nThe StoryRevision "%s" for which this comment was'\
                        ' entered was removed.' % show_revision_short(story)
        comment.revision_id = None
        comment.save()
    elif story.changeset.approver:
        # changeset already was submitted once since it has an approver
        # TODO not quite sure if we actually should add this comment
        story.changeset.comments.create(commenter=story.changeset.indexer,
                          text='The StoryRevision "%s" was removed.'\
                            % show_revision_short(story),
                          old_state=story.changeset.state,
                          new_state=story.changeset.state)
    story.delete()
    return HttpResponseRedirect(urlresolvers.reverse('edit',
      kwargs={ 'id': story.changeset.id }))

@permission_required('gcd.can_reserve')
def toggle_delete_story_revision(request, id):
    story = get_object_or_404(StoryRevision, id=id)
    if request.user != story.changeset.indexer:
        return render_error(request,
          'Only the reservation holder may delete or restore stories.')
    
    story.toggle_deleted()
    return HttpResponseRedirect(urlresolvers.reverse('edit',
      kwargs={ 'id': story.changeset.id }))

##############################################################################
# Ongoing Reservations
##############################################################################

@permission_required('gcd.can_reserve')
def ongoing(request, user_id=None):
    """
    Handle the ongoing reservatin page.  Display on GET.  On POST, process
    the form and re-display with error or success message as appropriate.
    """
    if (request.user.ongoing_reservations.count() >=
        request.user.indexer.max_ongoing):
        return render_error(request, 'You have reached the maximum number of '
          'ongoing reservations you can hold at this time.  If you are a new '
          'user this number is very low or even zero, but will increase as your '
          'first few changes are approved.',
          redirect=False)

    series = get_object_or_404(Series, id=request.POST['series'])
    if series.deleted or series.pending_deletion():
        return render_error(request, u'Cannot reserve issues '
          u'since "%s" is deleted or pending deletion.' % series)

    form = OngoingReservationForm()
    message = ''
    if request.method == 'POST':
        form = OngoingReservationForm(request.POST)
        if form.is_valid():
            reservation = form.save(commit=False)
            reservation.indexer = request.user
            reservation.save()
            message = 'Series %s reserved' % form.cleaned_data['series']
            return HttpResponseRedirect(urlresolvers.reverse(
              'apps.gcd.views.details.series',
               kwargs={ 'series_id': reservation.series.id }))

    return render_to_response('oi/edit/ongoing.html',
                              {
                                'form': form,
                                'message': message,
                              },
                              context_instance=RequestContext(request))

def delete_ongoing(request, series_id):
    if request.method != 'POST':
        return render_error(request,
          'You must access this page through the proper form.')
    reservation = get_object_or_404(OngoingReservation, series=series_id)
    if request.user != reservation.indexer:
        return render_error(request,
          'Only the reservation holder may delete the reservation.')
    series = reservation.series
    reservation.delete()
    return HttpResponseRedirect(urlresolvers.reverse(
      'apps.gcd.views.details.series',
      kwargs={ 'series_id': series.id }))

##############################################################################
# Reordering
##############################################################################

def _process_reorder_form(request, parent, sort_field, child_name, child_class):
    """
    Pull out the order fields and process the child objects in a generic way.
    """

    reorder_map = {}
    reorder_list = []
    sort_code_set = set()
    input_regexp = re.compile(r'%s_(?P<%s_id>\d+)$' % (sort_field, child_name))
    child_group = '%s_id' % child_name

    for input in request.POST:
        m = input_regexp.match(input)
        if m:
            child_id = int(m.group(child_group))
            try:
                sort_code =  float(request.POST[input])
            except ValueError:
                raise ViewTerminationError(render_error(request,
                  "%s must be a number", redirect=False))

            if sort_code in sort_code_set:
                raise ViewTerminationError(render_error(request,
                  "Cannot have duplicate %ss: %f" % (sort_field, sort_code),
                  redirect=False))

            sort_code_set.add(sort_code)

            reorder_map[child_id] = sort_code
            reorder_list.append(child_id)

    def _compare_sort_input(a, b):
        diff = reorder_map[a] - reorder_map[b]
        if diff > 0:
            return 1
        if diff < 0:
            return -1
        return 0

    reorder_list.sort(_compare_sort_input)

    # Use in_bulk to ensure the specific issue order
    child_map = child_class.objects.in_bulk(reorder_list)
    return [child_map[child_id] for child_id in reorder_list]

@permission_required('gcd.can_approve')
def reorder_series(request, series_id):
    series = get_object_or_404(Series, id=series_id)
    if request.method != 'POST':
        return render_to_response('oi/edit/reorder_series.html', 
          { 'series': series,
            'issue_list': [ (i, None) for i in series.active_issues() ] },
          context_instance=RequestContext(request))

    try:
        issues = _process_reorder_form(request, series, 'sort_code',
                                       'issue', Issue)
        return _reorder_series(request, series, issues)
    except ViewTerminationError as vte:
        return vte.response

@permission_required('gcd.can_approve')
def reorder_series_by_key_date(request, series_id):
    if request.method != 'POST':
        return _cant_get(request)
    series = get_object_or_404(Series, id=series_id)

    issues = series.active_issues().order_by('key_date')
    return _reorder_series(request, series, issues)

@permission_required('gcd.can_approve')
def reorder_series_by_issue_number(request, series_id):
    if request.method != 'POST':
        return _cant_get(request)
    series = get_object_or_404(Series, id=series_id)

    reorder_map = {}
    reorder_list = []
    number_set = set()
    try:
        for issue in series.active_issues():
            number = int(issue.number)
            if number in number_set:
                return render_error(request,
                  "Cannot sort by issue with duplicate issue numbers: %i" % number,
                  redirect=False)
            reorder_map[number] = issue
            reorder_list.append(number)

        reorder_list.sort()
        issues = [reorder_map[n] for n in reorder_list]
        return _reorder_series(request, series, issues)

    except ValueError:
        return render_error(request,
          "Cannot sort by issue numbers because they are not all whole numbers",
          redirect=False)

def _reorder_series(request, series, issues):
    """
    Internal method for actually changing the sort codes.
    Note that the 'issues' parameter may be either an ordered queryset
    or a plain list of issue objects.
    """

    # Note that _reorder_children actually performs the reordering, so it
    # is necessary even if we do not use the issue_list that it returns.
    # Do not move the call further down in this method.
    try:
        issue_list = _reorder_children(request, series, issues, 'sort_code',
                                       series.active_issues(), 'commit' in request.POST)
    except ViewTerminationError as vte:
        return vte.response

    if 'commit' in request.POST:
        set_series_first_last(series)
        return HttpResponseRedirect(urlresolvers.reverse(
          'apps.gcd.views.details.series',
          kwargs={ 'series_id': series.id }))

    return render_to_response('oi/edit/reorder_series.html', 
      { 'series': series,
        'issue_list': issue_list },
      context_instance=RequestContext(request))

@permission_required('gcd.can_reserve')
def reorder_stories(request, issue_id, changeset_id):
    changeset = get_object_or_404(Changeset, id=changeset_id)
    if request.user != changeset.indexer:
        return render_error(request,
          'Only the reservation holder may reorder stories.')

    # At this time, only existing issues can have their stories reordered.
    # This is analagous to issues needing to exist before stories can be added.
    issue_revision = changeset.issuerevisions.get(issue=issue_id)
    if request.method != 'POST':
        return render_to_response('oi/edit/reorder_stories.html',
          { 'issue': issue_revision, 'changeset': changeset },
          context_instance=RequestContext(request))

    if 'cancel' in request.POST:
        return HttpResponseRedirect(urlresolvers.reverse(
          'edit', kwargs={ 'id': changeset_id }))

    try:
        stories = _process_reorder_form(request, issue_revision, 'sequence_number',
                                       'story', StoryRevision)
        _reorder_children(request, issue_revision, stories,
                         'sequence_number', issue_revision.active_stories(),
                         commit=True, unique=False)

        return HttpResponseRedirect(urlresolvers.reverse(
          'edit', kwargs={ 'id': changeset_id }))

    except ViewTerminationError as vte:
        return vte.response

def _reorder_children(request, parent, children, sort_field, child_set,
                      commit, unique=True, skip=None):
    """
    Internal function implementing reordering in a generic way.
    Note that "children" may be a list or a query_set, while "child_set"
    must be the query set as accessed through the parent object.
    This may be accessed in a non-standard way, which is why it must be
    passed separately.

    The "skip" parameter is new revision for which a gap should be left.
    If there is already a revision with this sequence number, then the gap
    must go before that revision.  The new revision's sort code should
    be updated if necessary for it to fit into the gap properly.
    """

    # TODO:  Ideally we would have a mixin class, reorderable, that would
    #        implement this, and all reorderables could be assumed to have
    #        a sort_code field and a get_children method instead of all of
    #        this getattr/setattr madness.  This is something we should look
    #        into once the more urgent features are complete.  Our design
    #        is far too procedural in this area.

    if unique:
        # There's a "unique together" constraint on series_id and sort_code in
        # the issue table, which is great for avoiding nonsensical sort_code
        # situations that we had in the old system, but annoying when updating
        # the codes.  Get around it by shifing the numbers down to starting
        # at one if they'll fit, or up above the current range if not.  Given that
        # the numbers were all set to consecutive ranges when we migrated to this
        # system, and this code always produces consecutive ranges, the chances
        # that we won't have room at one end or the other are very slight.

        # Use child_set because children may be a list, not a query set.
        min = child_set.aggregate(Min(sort_field))['%s__min' % sort_field]
        max = child_set.aggregate(Max(sort_field))['%s__max' % sort_field]
        num_children = child_set.count() 

        if num_children < min:
            current_code = 1
        elif num_children <= sys.maxint - max:
            current_code = max + 1
        else:
            # This should be extremely rare, so let's not bother to
            # code our way out.
            raise ViewTerminationError(render_error(request,
              "Can't find room for rearranged sort codes, please contact an admin",
              redirect=False))
    else:
        # If there's no uniqueness constraints, always sort starting with zero.
        current_code = 0

    child_list = []
    found_skip = False
    for child in children:
        if skip is not None:
            current_sort_code = getattr(child, sort_field)
            skip_code = getattr(skip, sort_field)
            if not found_skip and current_code >= skip_code:
                found_skip = True
                setattr(skip, sort_field, current_code)
                current_code += 1
        if commit:
            setattr(child, sort_field, current_code)
            child.save()
        else:
            child_list.append((child, current_code))
        current_code += 1

    # Special case if there were no children and therefore for loop did nothing.
    if not children and skip is not None:
        setattr(skip, sort_field, current_code)

    return child_list


##############################################################################
# Queue Views
##############################################################################

@permission_required('gcd.can_reserve')
def show_queue(request, queue_name, state):
    kwargs = {}
    if 'editing' == queue_name:
        kwargs['indexer'] = request.user
        kwargs['state__in'] = states.ACTIVE
    if 'pending' == queue_name:
        kwargs['state__in'] = (states.PENDING, states.REVIEWING)
    if 'reviews' == queue_name:
        kwargs['approver'] = request.user
        kwargs['state__in'] = (states.OPEN, states.REVIEWING)
    if 'covers' == queue_name:
        return show_cover_queue(request)
    if 'approved' == queue_name:
        return show_approved(request)

    changes = Changeset.objects.filter(**kwargs).select_related(
      'indexer__indexer', 'approver__indexer')

    publishers = changes.filter(change_type=CTYPES['publisher'])
    indicia_publishers = changes.filter(change_type=CTYPES['indicia_publisher'])
    brands = changes.filter(change_type=CTYPES['brand'])
    series = changes.filter(change_type=CTYPES['series'])
    issue_adds = changes.filter(change_type=CTYPES['issue_add'])
    issues = changes.filter(change_type=CTYPES['issue'])
    issue_bulks = changes.filter(change_type=CTYPES['issue_bulk'])
    covers = changes.filter(change_type=CTYPES['cover'])

    response = render_to_response(
      'oi/queues/%s.html' % queue_name,
      {
        'queue_name': queue_name,
        'indexer': request.user,
        'states': states,
        'data': [
          {
            'object_name': 'Publishers',
            'object_type': 'publisher',
            'changesets': publishers.order_by('modified', 'id'),
          },
          {
            'object_name': 'Indicia Publishers',
            'object_type': 'indicia_publisher',
            'changesets': indicia_publishers.order_by('modified', 'id'),
          },
          {
            'object_name': 'Brands',
            'object_type': 'brands',
            'changesets': brands.order_by('modified', 'id'),
          },
          {
            'object_name': 'Series',
            'object_type': 'series',
            'changesets': series.order_by('modified', 'id'),
          },
          {
            'object_name': 'Issue Skeletons',
            'object_type': 'issue',
            'changesets': issue_adds.order_by('modified', 'id'),
          },
          {
            'object_name': 'Issue Bulk Changes',
            'object_type': 'issue',
            'changesets': issue_bulks.order_by('state', 'modified', 'id'),
          },
          {
            'object_name': 'Issues',
            'object_type': 'issue',
            'changesets': issues.order_by('state', 'modified', 'id'),
          },
          {
            'object_name': 'Covers',
            'object_type': 'cover',
            'changesets': covers.order_by('state', 'modified', 'id'),
          },
        ],
      },
      context_instance=RequestContext(request)
    )
    response['Cache-Control'] = "no-cache, no-store, max-age=0, must-revalidate"
    return response


@login_required
def show_approved(request):
    changes = Changeset.objects.order_by('-modified')\
                .filter(state=(states.APPROVED), indexer=request.user)

    return paginate_response(
      request,
      changes,
      'oi/queues/approved.html',
      {'CTYPES': CTYPES},
      page_size=50)


@login_required
def show_cover_queue(request):
    covers = Changeset.objects.filter(
      state__in=(states.PENDING, states.REVIEWING),
      change_type=CTYPES['cover']).select_related('indexer__indexer',
                                                  'approver__indexer')

    # TODO: Figure out optimal table width and/or make it user controllable.
    table_width = 5

    return paginate_response(
      request,
      covers,
      'oi/queues/covers.html',
      {
        'table_width' : table_width,
      },
      page_size=50,
      callback_key='tags',
      callback=get_preview_image_tags_per_page)

def compare(request, id):
    changeset = get_object_or_404(Changeset, id=id)

    if changeset.inline():
        revision = changeset.inline_revision()
    elif changeset.change_type in [CTYPES['issue'], CTYPES['issue_add'],
                                   CTYPES['issue_bulk']]:
        revision = changeset.issuerevisions.all()[0]
    else:
        # never reached at the moment
        raise NotImplementedError

    model_name = revision.source_name
    if model_name == 'cover':
        return cover_compare(request, changeset, revision)

    revision.compare_changes()

    if changeset.change_type == CTYPES['issue_add'] and \
      changeset.issuerevisions.count() > 1:
        template = 'oi/edit/compare_issue_skeletons.html'
    elif changeset.change_type == CTYPES['issue_bulk']:
        template = 'oi/edit/compare_bulk_issue.html'
    else:
        template = 'oi/edit/compare.html'

    prev_rev = revision.previous()
    field_list = revision.field_list()
    # eliminate fields that shouldn't appear in the compare
    if model_name == 'series':
        if prev_rev is None or prev_rev.imprint is None:
            field_list.remove('imprint')
    elif model_name == 'publisher':
        field_list.remove('is_master')
        field_list.remove('parent')
    elif model_name in ['brand', 'indicia_publisher']:
        field_list.remove('parent')
    elif model_name == 'issue':
        if prev_rev:
            field_list.remove('after')
        if changeset.change_type == CTYPES['issue_bulk']:
            field_list.remove('number')
            field_list.remove('publication_date')
            field_list.remove('key_date')
            field_list.remove('notes')

            
    response = render_to_response(template,
                                  {'changeset': changeset,
                                   'revision': revision,
                                   'prev_rev': prev_rev,
                                   'changeset_type' : model_name.replace('_',' '),
                                   'model_name': model_name,
                                   'states': states,
                                   'field_list': field_list},
                                  context_instance=RequestContext(request))
    response['Cache-Control'] = "no-cache, no-store, max-age=0, must-revalidate"
    return response

@login_required
def cover_compare(request, changeset, revision):
    ''' 
    Compare page for covers.
    - show uploaded cover
    - for replacement show former cover
    - for other active uploads show other existing and active covers
    '''
    if revision.deleted:
        cover_tag = get_image_tag(revision.cover, "deleted cover", ZOOM_LARGE)
    else:
        cover_tag = get_preview_image_tag(revision, "uploaded cover", ZOOM_LARGE)
    if revision.is_wraparound:
        cover_front_tag = get_preview_image_tag(revision, "uploaded cover",
                                                ZOOM_MEDIUM)
    else:
        cover_front_tag = ''

    current_covers = []
    pending_covers = []
    old_cover = None
    old_cover_tag = ''
    old_cover_front_tag = ''
    if revision.is_replacement:
        old_cover = CoverRevision.objects.filter(cover=revision.cover, 
                      created__lt=revision.created,
                      changeset__state=states.APPROVED).order_by('-created')[0]
        old_cover_tag = get_preview_image_tag(old_cover, "replaced cover", 
                                              ZOOM_LARGE)
        if old_cover.is_wraparound:
            old_cover_front_tag = get_preview_image_tag(old_cover, 
                                    "replaced cover", ZOOM_MEDIUM)
        else:
            old_cover_front_tag = ''
    elif revision.changeset.state in states.ACTIVE:
        if revision.issue.has_covers():
            for cover in revision.issue.active_covers():
                current_covers.append([cover, get_image_tag(cover, 
                                       "current cover", ZOOM_MEDIUM)])
        if CoverRevision.objects.filter(issue=revision.issue).count() > 1:
            covers = CoverRevision.objects.filter(issue=revision.issue)
            covers = covers.exclude(id=revision.id).filter(cover=None)
            covers = covers.filter(changeset__state__in=states.ACTIVE)
            covers = covers.order_by('created')
            for cover in covers:
                pending_covers.append([cover, get_preview_image_tag(cover, 
                                       "pending cover", ZOOM_MEDIUM)])

    response = render_to_response('oi/edit/compare_cover.html',
                                  { 'changeset': changeset,
                                    'revision': revision,
                                    'cover_tag' : cover_tag,
                                    'cover_front_tag': cover_front_tag,
                                    'current_covers' : current_covers,
                                    'pending_covers' : pending_covers,
                                    'old_cover': old_cover,
                                    'old_cover_tag': old_cover_tag,
                                    'old_cover_front_tag': old_cover_front_tag,
                                    'table_width': 5,
                                    'states': states },
                                  context_instance=RequestContext(request))
    response['Cache-Control'] = "no-cache, no-store, max-age=0, must-revalidate"
    return response


@login_required
def preview(request, id, model_name):
    revision = get_object_or_404(REVISION_CLASSES[model_name], id=id)
    template = 'gcd/details/%s.html' % model_name

    if 'publisher' == model_name:
        if revision.parent is None:
            queryset = revision.active_series().order_by('name')
        else:
            queryset = revision.imprint_series_set.exclude(deleted=True) \
              .order_by('name')
        return paginate_response(request,
          queryset,
          template,
          {
            model_name: revision,
            'error_subject': revision,
            'preview': True,
          },
        )
    if 'indicia_publisher' == model_name:
        return show_indicia_publisher(request, revision, True)
    if 'brand' == model_name:
        return show_brand(request, revision, True)
    if 'series' == model_name:
        return show_series(request, revision, True)
    if 'issue' == model_name:
        return show_issue(request, revision, True)

##############################################################################
# Mentoring 
##############################################################################

@permission_required('gcd.can_mentor')
def mentoring(request):
    max_show_new = 50
    new_indexers = User.objects.filter(indexer__mentor=None) \
                               .filter(indexer__is_new=True) \
                               .filter(is_active=True) \
                               .order_by('-date_joined')[:max_show_new]
    my_mentees = User.objects.filter(indexer__mentor=request.user) \
                             .filter(indexer__is_new=True)
    mentees = User.objects.exclude(indexer__mentor=None) \
                          .filter(indexer__is_new=True) \
                          .exclude(indexer__mentor=request.user)
    
    return render_to_response('oi/queues/mentoring.html',
      {
        'new_indexers': new_indexers,
        'my_mentees': my_mentees,
        'mentees': mentees,
        'max_show_new': max_show_new
      },
      context_instance=RequestContext(request))


##############################################################################
# Downloads
##############################################################################

@login_required
def download(request, file='current.zip'):
    path = os.path.join(settings.MEDIA_ROOT, settings.DUMP_DIR, 'current.zip')

    if request.method == 'POST':
        form = DownloadForm(request.POST)
        if form.is_valid():
            cd = form.cleaned_data

            delta = settings.DOWNLOAD_DELTA
            recently = datetime.now() - timedelta(minutes=delta)
            if Download.objects.filter(user=request.user,
                                       description__contains=file,
                                       timestamp__gt=recently).count():
                return render_error(request,
                  ("You have started a download of this file within the last %d "
                   "minutes.  Please check your download window.  If you need to "
                   "start a new download, please wait at least %d minutes in "
                   "order to avoid consuming excess bandwidth.") % (delta, delta))

            desc = {'file': file, 'accepted license': True}
            if 'purpose' in cd and cd['purpose']:
                desc['purpose'] = cd['purpose']
            if 'usage' in cd and cd['usage']:
                desc['usage'] = cd['usage']

            record = Download(user=request.user, description=repr(desc))
            record.save()
            dump = File(open(path))
    
            response = HttpResponse(dump.chunks(), mimetype='application/zip')
            response['Content-Disposition'] = 'attachment; filename=current.zip'
            return response
    else:
        form = DownloadForm()

    return render_to_response('oi/download.html',
      {
        'method': request.method,
        'timestamp': datetime.utcfromtimestamp(os.stat(path)[stat.ST_MTIME]),
        'form': form,
      },
      context_instance=RequestContext(request))

