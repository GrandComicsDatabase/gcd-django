import re
import sys
import os
import os.path
import stat

from django.core import urlresolvers
from django.core.files import File
from django.conf import settings
from django.http import HttpResponse, HttpResponseRedirect
from django.template import RequestContext
from django.shortcuts import render_to_response, get_object_or_404
from django.db.models import Min, Max
from django.core.exceptions import *

from django.contrib.auth.views import login
from django.contrib.auth.decorators import login_required, permission_required

from apps.gcd.models import *
from apps.gcd.views import render_error, paginate_response
from apps.gcd.views.details import show_indicia_publisher, show_brand, \
                                   show_series, show_issue
from apps.gcd.views.covers import get_image_tag
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
}

DISPLAY_CLASSES = {
    'publisher': Publisher,
    'indicia_publisher': IndiciaPublisher,
    'brand': Brand,
    'series': Series,
    'issue': Issue,
    'story': Story,
}

##############################################################################
# Helper functions
##############################################################################

def _cant_get(request):
    return render_error(request,
      'This page may only be accessed through the proper form',
       redirect=False)

##############################################################################
# Generic view functions
##############################################################################

@permission_required('gcd.can_reserve')
def reserve(request, id, model_name):
    display_obj = get_object_or_404(DISPLAY_CLASSES[model_name], id=id)
    if request.method != 'POST':
        return _cant_get(request)

    if display_obj.reserved:
        return render_error(request,
          'Cannot create a new revision for "%s" as it is already reserved.' %
          display_obj)

    changeset = _do_reserve(request.user, display_obj, model_name)
    if changeset is None:
        return render_error(request,
          'You have reached your limit of open changes.  You must '
          'submit or discard some changes from your edit queue before you '
          'can edit any more.  If you are a new user this number is very low '
          'but will be increased as your first changes are approved.')

    return HttpResponseRedirect(urlresolvers.reverse('edit',
      kwargs={ 'id': changeset.id }))

def _do_reserve(indexer, display_obj, model_name):
    if indexer.indexer.can_reserve_another() is False:
        return None

    changeset = Changeset(indexer=indexer, state=states.OPEN,
                          change_type=CTYPES[model_name])
    changeset.save()
    changeset.comments.create(commenter=indexer,
                              text='Editing',
                              old_state=states.UNRESERVED,
                              new_state=changeset.state)

    revision = REVISION_CLASSES[model_name].objects.clone_revision(
      display_obj, changeset=changeset)

    if model_name == 'issue':
        for story in revision.issue.active_stories():
           StoryRevision.objects.clone_revision(story=story, changeset=changeset)
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
        source_name = revision.source_name
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
          {'error_message': 'A change may only be submitted by its author.'},
          context_instance=RequestContext(request))

    changeset.submit(notes=request.POST['comments'])
    if changeset.approver is not None:
        if request.POST['comments']:
            comment = u'The submission includes the comment:\n"%s"' % request.POST['comments'] 
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
          {'error_message': 'A change may only be retracted by its author.'},
          context_instance=RequestContext(request))
    changeset.retract(notes=request.POST['comments'])

    return HttpResponseRedirect(urlresolvers.reverse('edit', kwargs={'id': changeset.id }))

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
          { 'error_message':
            'Only the author or the assigned editor can discard a change.' },
          context_instance=RequestContext(request))

    if request.user != changeset.indexer and not request.POST['comments']:
        return render_error(request,
                            'You must explain why you are rejecting this '
                            'change.  Please press the "back" button and use '
                            'the comments field for the explanation.' )

    notes = request.POST['comments']
    changeset.discard(discarder=request.user, notes=notes)

    if request.user != changeset.indexer:
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
    else:
        if changeset.approver:
            if request.POST['comments']:
                comment = u'The discard includes the comment:\n"%s"' % \
                          request.POST['comments'] 
            else:
                comment = ''   
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

    return HttpResponseRedirect(urlresolvers.reverse('compare', 
                                             kwargs={'id': changeset.id }))

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
          {'error_message': 'A change may only be released by its approver.'},
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

    if notes.strip():
        email_body = u"""
Hello from the %s!


  Your change for "%s" was approved by GCD editor %s with the comment:
"%s"

You can view the full change at %s.

thanks,
-the %s team
%s
""" % (settings.SITE_NAME,
           unicode(changeset),
           unicode(changeset.approver.indexer),
           notes,
           settings.SITE_URL.rstrip('/') +
             urlresolvers.reverse('compare', kwargs={'id': changeset.id }),
           settings.SITE_NAME,
           settings.SITE_URL)

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


# TODO: Figure out how to handle deletions.
# @permission_required('gcd.can_reserve')
# def delete(request, id, model_name):
#     """
#     Delete and submit a change, returning to the reservations queue.
#     """
#     if request.method != 'POST':
#         return _cant_get(request)
# 
#     revision = get_object_or_404(REVISION_CLASSES[model_name], id=id)
#     if request.user != revision.indexer:
#         return render_to_response('gcd/error.html',
#           {'error_message': 'Only the reservation holder may delete a record.'},
#           context_instance=RequestContext(request))
#     if model_name == 'issue':
#         # For now, refuse to delete stories with issues.  TODO: Revisit.
#         if revision.story_revisions.count():
#             return render_error(request,
#               "Cannot delete issue while stories are still attached.")
#     revision.mark_deleted()
# 
#     return HttpResponseRedirect(
#       urlresolvers.reverse('editing'))

@permission_required('gcd.can_reserve')
def process(request, id):
    """
    Entry point for forms with multiple actions.

    This handles adding comments (with no state change) directly, and routes
    the request to other views for all other cases.
    """
    if request.method != 'POST':
        return _cant_get(request)

    # TODO: Figure out delete.
    # if 'delete' in request.POST:
        # return delete(request, id, model_name)

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
    form_class = get_revision_form(model_name='issue',
                                   series=series,
                                   publisher=series.publisher)

    if request.method != 'POST':
        reversed_issues = series.issue_set.order_by('-sort_code')
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
    if method is None:
        return render_to_response('oi/edit/add_issues.html',
                                  { 'series_id': series_id, 
                                    'issue_adds' : issue_adds },
                                  context_instance=RequestContext(request))

    series = get_object_or_404(Series, id=series_id)
    form_class = get_bulk_issue_revision_form(series=series, method=method)

    if request.method != 'POST':
        reversed_issues = series.issue_set.order_by('-sort_code')
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
        issue = Issue.objects.get(id=issue_id)
        if request.method != 'POST':
            seq = request.GET['added_sequence_number']
            if seq != '':
                try:
                    seq_num = int(seq)
                    initial = {'sequence_number': seq_num, 'no_editing' : True }
                    if seq_num == 0:
                        # Do not default other sequences, because if we do we
                        # will get a lot of people leaving the default values
                        # by accident.  Only sequence zero is predictable.
                        initial['type'] = StoryType.objects.get(name='cover').id
                        initial['no_script'] = True
                    form = get_story_revision_form()(initial=initial)
                except ValueError:
                    return render_error(request,
                                        "Sequence number must be a whole number.")
            else:
                form = get_story_revision_form()()
            return _display_add_story_form(request, issue, form, changeset_id)

        if 'cancel_return' in request.POST:
            return HttpResponseRedirect(urlresolvers.reverse('edit',
              kwargs={ 'id': changeset_id }))

        form = get_story_revision_form()(request.POST)
        if not form.is_valid():
            return _display_add_story_form(request, issue, form, changeset_id)

        revision = form.save(commit=False)
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

    except (Issue.DoesNotExist, Issue.MultipleObjectsReturned):
        return render_error(request,
          'Could not find issue for id ' + issue_id)

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

@permission_required('gcd.can_approve')
def reorder_series(request, series_id):
    series = get_object_or_404(Series, id=series_id)
    if request.method != 'POST':
        return render_to_response('oi/edit/reorder_series.html', 
          { 'series': series,
            'issue_list': [ (i, None) for i in series.issue_set.all() ] },
          context_instance=RequestContext(request))

    reorder_map = {}
    reorder_list = []
    sort_code_set = set()
    for input in request.POST:
        m = re.match(r'sort_code_(?P<issue_id>\d+)$', input)
        if m:
            issue_id = int(m.group('issue_id'))
            sort_code =  float(request.POST[input])
            if sort_code in sort_code_set:
                return render_error(request,
                  "Cannot have duplicate sort codes: %f" % sort_code,
                  redirect=False)
            sort_code_set.add(sort_code)

            reorder_map[issue_id] = sort_code
            reorder_list.append(issue_id)

    def _compare_sort_input(a, b):
        diff = reorder_map[a] - reorder_map[b]
        if diff > 0:
            return 1
        if diff < 0:
            return -1
        return 0

    reorder_list.sort(_compare_sort_input)

    # Use in_bulk to ensure the specific issue order
    issue_map = Issue.objects.in_bulk(reorder_list)
    issues = [issue_map[issue_id] for issue_id in reorder_list]
    return _reorder_series(request, series, issues)

@permission_required('gcd.can_approve')
def reorder_series_by_key_date(request, series_id):
    if request.method != 'POST':
        return _cant_get(request)
    series = get_object_or_404(Series, id=series_id)

    issues = series.issue_set.order_by('key_date')
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
        for issue in series.issue_set.all():
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

    # There's a "unique together" constraint on series_id and sort_code in
    # the issue table, which is great for avoiding nonsensical sort_code
    # situations that we had in the old system, but annoying when updating
    # the codes.  Get around it by shifing the numbers down to starting
    # at one if they'll fit, or up above the current range if not.  Given that
    # the numbers were all set to consecutive ranges when we migrated to this
    # system, and this code always produces consecutive ranges, the chances that
    # we won't have room at one end or the other are very slight.
    min = series.issue_set.aggregate(Min('sort_code'))['sort_code__min']
    max = series.issue_set.aggregate(Max('sort_code'))['sort_code__max']
    num_issues = series.issue_set.count() 

    if num_issues < min:
        current_code = 1
    elif num_issues <= sys.maxint - max:
        current_code = max + 1
    else:
        # This should be extremely rare, so let's not bother to code our way out.
        return render_error(request,
          "Cannot find room for rearranged sort codes, please contact an admin",
          redirect=False)

    issue_list = []
    for issue in issues:
        if 'commit' in request.POST:
            issue.sort_code = current_code
            issue.save()
        else:
            issue_list.append((issue, current_code))
        current_code +=1

    if 'commit' in request.POST:
        return HttpResponseRedirect(urlresolvers.reverse(
          'apps.gcd.views.details.series',
          kwargs={ 'series_id': series.id }))

    return render_to_response('oi/edit/reorder_series.html', 
      { 'series': series,
        'issue_list': issue_list },
      context_instance=RequestContext(request))


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
        kwargs['state'] = states.REVIEWING
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
            'changesets': publishers.order_by('modified'),
          },
          {
            'object_name': 'Indicia Publishers',
            'object_type': 'indicia_publisher',
            'changesets': indicia_publishers.order_by('modified'),
          },
          {
            'object_name': 'Brands',
            'object_type': 'brands',
            'changesets': brands.order_by('modified'),
          },
          {
            'object_name': 'Series',
            'object_type': 'series',
            'changesets': series.order_by('modified'),
          },
          {
            'object_name': 'Issue Skeletons',
            'object_type': 'issue',
            'changesets': issue_adds.order_by('modified'),
          },
          {
            'object_name': 'Issues',
            'object_type': 'issue',
            'changesets': issues.order_by('state', 'modified'),
          },
          {
            'object_name': 'Covers',
            'object_type': 'cover',
            'changesets': covers.order_by('state', 'modified'),
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
      {},
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

@login_required
def compare(request, id):
    changeset = get_object_or_404(Changeset, id=id)
    if changeset.coverrevisions.count() == 1:
        return cover_compare(request, changeset, 
                             changeset.coverrevisions.all()[0])
    if changeset.inline():
        revision = changeset.inline_revision()
    elif changeset.issuerevisions.count() > 0:
        revision = changeset.issuerevisions.all()[0]
    else:
        raise NotImplementedError

    revision.compare_changes()

    model_name = revision.source_name
    if changeset.issuerevisions.count() > 1:
        template = 'oi/edit/compare_issue_skeletons.html'
    else:
        template = 'oi/edit/compare_%s.html' % model_name

    response = render_to_response(template,
                                  { 'changeset': changeset,
                                    'revision': revision,
                                    'model_name': model_name,
                                    'states': states },
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

    current_covers = []
    pending_covers = []
    if revision.is_replacement:
        old_cover = CoverRevision.objects.filter(cover=revision.cover, 
                      created__lt=revision.created,
                      changeset__state=states.APPROVED).order_by('-created')[0]
        current_covers.append([old_cover, get_preview_image_tag(
                                            old_cover, "replaced cover", 
                                            ZOOM_LARGE)])
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
                                    'cover_tag' : cover_tag,
                                    'current_covers' : current_covers,
                                    'pending_covers' : pending_covers,
                                    'revision': revision,
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
            queryset = revision.series_set.order_by('name')
        else:
            queryset = revision.imprint_series_set.order_by('name')
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
    new_indexers = User.objects.filter(indexer__mentor=None) \
                               .filter(indexer__is_new=True) \
                               .filter(is_active=True)
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

