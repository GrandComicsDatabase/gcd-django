# -*- coding: utf-8 -*-
import re
import sys
import os
import os.path
import glob
import Image
import stat
import errno
import hashlib
from random import random
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
from django.utils.html import conditional_escape as esc
from django.utils.datastructures import MultiValueDictKeyError

from django.contrib.auth.views import login
from django.contrib.auth.decorators import login_required, permission_required

from apps.gcd.models import *
from apps.gcd.views import ViewTerminationError, render_error, paginate_response
from apps.gcd.views.details import show_indicia_publisher, show_brand, \
                                   show_series, show_issue
from apps.gcd.views.covers import get_image_tag, get_image_tags_per_issue
from apps.gcd.views.search import do_advanced_search, used_search
from apps.gcd.models.cover import ZOOM_LARGE, ZOOM_MEDIUM, ZOOM_SMALL
from apps.gcd.templatetags.display import show_revision_short
from apps.oi.models import *
from apps.oi.forms import *
from apps.oi.covers import get_preview_image_tag, \
                           get_preview_image_tags_per_page, UPLOAD_WIDTH

REVISION_CLASSES = {
    'publisher': PublisherRevision,
    'indicia_publisher': IndiciaPublisherRevision,
    'brand': BrandRevision,
    'series': SeriesRevision,
    'issue': IssueRevision,
    'story': StoryRevision,
    'cover': CoverRevision,
    'reprint': ReprintRevision,
}

DISPLAY_CLASSES = {
    'publisher': Publisher,
    'indicia_publisher': IndiciaPublisher,
    'brand': Brand,
    'series': Series,
    'issue': Issue,
    'story': Story,
    'cover': Cover,
    'reprint': Reprint,
    'reprint_to_issue': ReprintToIssue,
    'reprint_from_issue': ReprintFromIssue,
    'issue_reprint': IssueReprint
}

REACHED_CHANGE_LIMIT = 'You have reached your limit of open changes.  You ' \
  'must submit or discard some changes from your edit queue before you ' \
  'can edit any more.  If you are a new user this number is very low ' \
  'but will be increased as your first changes are approved. ' \
  'If you are an experienced indexer and frequently hit ' \
  'your reservation limit please contact us.'

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
              u'Cannot delete "%s" as it is curently reserved.' % display_obj,
              redirect=False)
        if display_obj.deleted:
            return render_error(request,
              u'Cannot delete "%s" as it is already deleted.' % display_obj,
              redirect=False)
        if not display_obj.deletable():
            return render_error(request,
              u'"%s" cannot be deleted.' % display_obj, redirect=False)

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
def reserve(request, id, model_name, delete=False, callback=None, callback_args=None):
    if request.method != 'POST':
        return _cant_get(request)
    display_obj = get_object_or_404(DISPLAY_CLASSES[model_name], id=id)

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
        else:
            changeset = _do_reserve(request.user, display_obj, model_name)

        if changeset is None:
            _unreserve(display_obj)
            return render_error(request, REACHED_CHANGE_LIMIT)

        if delete:
            changeset.submit(notes=request.POST['comments'], delete=True)
            if model_name == 'cover':
                return HttpResponseRedirect(urlresolvers.reverse('edit_covers',
                         kwargs={'issue_id' : display_obj.issue.id}))
            return HttpResponseRedirect(urlresolvers.reverse(
                     'show_%s' % model_name,
                     kwargs={str('%s_id' % model_name): id}))
        else:
            if callback:
                if not callback(changeset, display_obj, **callback_args):
                    transaction.rollback()
                    # the callback can result in a db save of the changeset
                    # so delete it. This does not fail if no save happened
                    changeset.delete()
                    _unreserve(display_obj)
                    return render_error(request,
                      'Not all objects could be reserved.')
            return HttpResponseRedirect(urlresolvers.reverse('edit',
              kwargs={ 'id': changeset.id }))

    except:
        transaction.rollback()
        _unreserve(display_obj)
        raise

def _do_reserve(indexer, display_obj, model_name, delete=False, changeset=None):
    if model_name != 'cover' and (delete is False or indexer.indexer.is_new)\
       and indexer.indexer.can_reserve_another() is False:
        return None

    if delete:
        # Deletions are submitted immediately which will set the correct state.
        new_state = states.UNRESERVED
    else:
        comment = 'Editing'
        new_state = states.OPEN

    if not changeset:
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
        for imprint in revision.publisher.active_imprints().all():
            imprint_revision = PublisherRevision.objects.clone_revision(
              publisher=imprint, changeset=changeset)
            imprint_revision.deleted = True
            imprint_revision.save()

    return changeset
    
@permission_required('gcd.can_reserve')
def edit_two_issues(request, issue_id):
    issue = get_object_or_404(Issue, id=issue_id, deleted=False)
    if issue.reserved:
        return render_error(request, 'Issue %s is reserved.' % issue,
                            redirect=False)
    data = {'issue_id': issue_id,
            'issue': True,
            'heading': mark_safe('<h2>Select issue to edit with %s</h2>' \
                                    % esc(issue.full_name())),
            'target': 'an issue',
            'return': confirm_two_edits,
            'cancel': HttpResponseRedirect(urlresolvers.reverse('show_issue',
                        kwargs={'issue_id': issue_id}))}
    select_key = store_select_data(request, None, data)
    return HttpResponseRedirect(urlresolvers.reverse('select_object',
          kwargs={'select_key': select_key}))
    
@permission_required('gcd.can_reserve')
def confirm_two_edits(request, data, object_type, issue_two_id):
    if object_type != 'issue':
        raise ValueError
    issue_one = get_object_or_404(Issue, id=data['issue_id'], deleted=False)
    if issue_one.reserved:
        return render_error(request, 'Issue %s is reserved.' % issue_one,
                            redirect=False)

    issue_two = get_object_or_404(Issue, id=issue_two_id, deleted=False)
    if issue_two.reserved:
        return render_error(request, 'Issue %s is reserved.' % issue_two,
                            redirect=False)
    return render_to_response('oi/edit/confirm_two_edits.html',
        {'issue_one': issue_one, 'issue_two': issue_two},
        context_instance=RequestContext(request))

@permission_required('gcd.can_reserve')
# in case of variants: issue_one = variant, issue_two = base
def reserve_two_issues(request, issue_one_id, issue_two_id):
    if request.method != 'POST':
        return _cant_get(request)
    if 'cancel' in request.POST:
        return HttpResponseRedirect(urlresolvers.reverse('show_issue',
          kwargs={'issue_id': issue_one_id}))
    issue_one = get_object_or_404(Issue, id=issue_one_id, deleted=False)
    issue_two = get_object_or_404(Issue, id=issue_two_id, deleted=False)

    kwargs = {'issue_one': issue_one}
    return reserve(request, issue_two_id, 'issue',
                   callback=reserve_other_issue,
                   callback_args=kwargs)

def reserve_other_issue(changeset, revision, issue_one):
    is_reservable = _is_reservable('issue', issue_one.id)

    if is_reservable == 0:
        return False

    if not _do_reserve(changeset.indexer, issue_one, 'issue',
                       changeset=changeset):
        _unreserve(issue_one)
        return False
    changeset.change_type=CTYPES['two_issues']
    changeset.save()
    return True

@permission_required('gcd.can_reserve')
def edit_revision(request, id, model_name):
    revision = get_object_or_404(REVISION_CLASSES[model_name], id=id)
    form_class = get_revision_form(revision, user=request.user)
    form = form_class(instance=revision)
    return _display_edit_form(request, revision.changeset, form, revision)

@permission_required('gcd.can_reserve')
def edit(request, id):
    changeset = get_object_or_404(Changeset, id=id)
    form = None
    revision = None
    if changeset.inline():
        revision = changeset.inline_revision()
        form_class = get_revision_form(revision, user=request.user)
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
        'CTYPES': CTYPES
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
    comment_text = request.POST['comments'].strip()
    changeset.submit(notes=comment_text)
    if changeset.approver is not None:
        if comment_text:
            comment = u'The submission includes the comment:\n"%s"' % \
                      comment_text
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
          
    if comment_text:
        send_comment_observer(request, changeset, comment_text)

    return HttpResponseRedirect(urlresolvers.reverse('editing'))

def show_error_with_return(request, text, changeset):
    return render_error(request, '%s <a href="%s">Return to changeset.</a>' \
        % (esc(text), urlresolvers.reverse('edit',
                                           kwargs={ 'id': changeset.id })),
        is_safe=True)

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
        if revision.changeset.change_type == CTYPES['series'] and \
          'move_to_publisher_with_id' in form.cleaned_data and \
          request.user.has_perm('gcd.can_approve') and \
          form.cleaned_data['move_to_publisher_with_id']:
            try:
                publisher_id = form.cleaned_data['move_to_publisher_with_id']
                publisher = Publisher.objects.get(id=publisher_id,
                                                  deleted=False, is_master=True)
            except Publisher.DoesNotExist:
                return show_error_with_return(request,
                  'No publisher with id %d.' % publisher_id, changeset)
            if publisher.pending_deletion():
                return show_error_with_return(request, 'Publisher %s is '
                  'pending deletion' % unicode(publisher), changeset)
            if revision.changeset.issuerevisions.count() == 0:
                if revision.series.active_issues().filter(reserved=True):
                    return show_error_with_return(request, 'Some issues for series'
                    ' %s are reserved. No move possible.' % revision.series,
                    changeset)
            return HttpResponseRedirect(urlresolvers.reverse('move_series',
                kwargs={'series_revision_id': revision.id,
                        'publisher_id': publisher_id}))

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
    comment_text = request.POST['comments'].strip()
    changeset.retract(notes=comment_text)
    
    if comment_text:
        send_comment_observer(request, changeset, comment_text)

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
            comment_text = changeset.comments.latest('created').text
            comment = u'The discard includes the comment:\n"%s"' % comment_text
        else:
            comment = ''
            comment_text = ''
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
        if comment_text:
            send_comment_observer(request, changeset, comment_text)
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

    comment_text = request.POST['comments'].strip()
    if request.user != changeset.indexer and not comment_text:
        return render_error(request,
                            'You must explain why you are rejecting this '
                            'change.  Please press the "back" button and use '
                            'the comments field for the explanation.' )

    # get a confirmation to avoid unwanted discards
    if request.user == changeset.indexer:
        if comment_text:
            changeset.comments.create(commenter=request.user,
                                      text=comment_text,
                                      old_state=changeset.state,
                                      new_state=changeset.state)
            has_comment = 1
        else:
            has_comment = 0
        return HttpResponseRedirect(urlresolvers.reverse('confirm_discard',
                                    kwargs={'id': changeset.id,
                                            'has_comment': has_comment}))

    changeset.discard(discarder=request.user, notes=comment_text)

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
           comment_text,
           settings.SITE_URL.rstrip('/') +
             urlresolvers.reverse('compare', kwargs={'id': changeset.id }),
           changeset.approver.email,
           settings.SITE_NAME,
           settings.SITE_URL)

        changeset.indexer.email_user('GCD change rejected', email_body,
          settings.EMAIL_INDEXING)
        if comment_text:
            send_comment_observer(request, changeset, comment_text)
        if request.user.approved_changeset.filter(state=states.REVIEWING).count():
            return HttpResponseRedirect(urlresolvers.reverse('reviewing'))
        else:
            if changeset.change_type is CTYPES['cover']:
                return HttpResponseRedirect(urlresolvers.reverse('pending_covers'))
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

    comment_text = request.POST['comments'].strip()
    # TODO: rework error checking strategy.  This is a hack for the most
    # common case but we probably shouldn't be doing this check in the
    # model layer in the first place.  See tech bug #199.
    try:
        changeset.assign(approver=request.user, notes=comment_text)
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
       changeset.change_type is not CTYPES['cover']:

        changeset.indexer.indexer.mentor = request.user
        changeset.indexer.indexer.save()

        for pending in changeset.indexer.changesets.filter(state=states.PENDING):
            try:
              pending.assign(approver=request.user, notes='')
            except ValueError:
                # Someone is already reviewing this.  Unlikely, and just let it go.
                pass

    if comment_text:
        email_body = u"""
Hello from the %s!


  %s became editor of the change "%s" with the comment:
"%s"

You can view the full change at %s.

thanks,
-the %s team
%s
""" % (settings.SITE_NAME,
           unicode(request.user.indexer),
           unicode(changeset),
           comment_text,
           settings.SITE_URL.rstrip('/') +
             urlresolvers.reverse('compare', kwargs={'id': changeset.id }),
           settings.SITE_NAME,
           settings.SITE_URL)
        changeset.indexer.email_user('GCD comment', email_body,
            settings.EMAIL_INDEXING)
        
        send_comment_observer(request, changeset, comment_text)
        
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
          
    comment_text = request.POST['comments'].strip()
    changeset.release(notes=comment_text)
    if comment_text:
        email_body = u"""
Hello from the %s!


  editor %s released the change "%s" with the comment:
"%s"

You can view the full change at %s.

thanks,
-the %s team
%s
""" % (settings.SITE_NAME,
           unicode(request.user.indexer),
           unicode(changeset),
           comment_text,
           settings.SITE_URL.rstrip('/') +
             urlresolvers.reverse('compare', kwargs={'id': changeset.id }),
           settings.SITE_NAME,
           settings.SITE_URL)
        changeset.indexer.email_user('GCD comment', email_body,
            settings.EMAIL_INDEXING)
            
        send_comment_observer(request, changeset, comment_text)

    if request.user.approved_changeset.filter(state=states.REVIEWING).count():
        return HttpResponseRedirect(urlresolvers.reverse('reviewing'))
    else:
        return HttpResponseRedirect(urlresolvers.reverse('pending'))

@permission_required('gcd.can_approve')
def discuss(request, id):
    """
    Move a change into the discussion state and go back to your queue.
    """
    if request.method != 'POST':
        return _cant_get(request)

    changeset = get_object_or_404(Changeset, id=id)
    if request.user != changeset.approver:
        return render_to_response('gcd/error.html',
          {'error_text': 'A change may only be put into discussion by its ' \
                         'approver.'},
          context_instance=RequestContext(request))
    if changeset.state != states.REVIEWING:
        return render_error(request,
          'Only REVIEWING changes can be put into discussion.')

    comment_text = request.POST['comments'].strip()
    changeset.discuss(notes=comment_text)

    if comment_text:
        email_comments = ' with the comment:\n"%s"' % comment_text
    else:
        email_comments = '.'
        
    email_body = u"""
Hello from the %s!


  Your change for "%s" was put into the discussion state by GCD editor %s%s

You can view the full change at %s.

thanks,
-the %s team

%s
""" % (settings.SITE_NAME,
       unicode(changeset),
       unicode(changeset.approver.indexer),
       email_comments,
       settings.SITE_URL.rstrip('/') +
         urlresolvers.reverse('compare', kwargs={'id': changeset.id }),
       settings.SITE_NAME,
       settings.SITE_URL)

    if comment_text:
        subject = 'GCD change put into discussion with a comment'
        send_comment_observer(request, changeset, comment_text)
    else:
        subject = 'GCD change put into discussion'
            
    changeset.indexer.email_user(subject, email_body, settings.EMAIL_INDEXING)
          
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

    if changeset.state not in [states.DISCUSSED, states.REVIEWING] \
      or changeset.approver is None:
        return render_error(request,
          'Only REVIEWING changes with an approver can be approved.')

    comment_text = request.POST['comments'].strip()
    changeset.approve(notes=comment_text)

    email_comments = '.'
    postscript = ''
    if comment_text:
        email_comments = ' with the comment:\n"%s"' % comment_text
    else:
        postscript = """
PS: You can change your email settings on your profile page:
%s
Currently, your profile is set to receive emails about change approvals even
if the approver did not comment.  To turn these off, just edit your profile
and uncheck the "Approval emails" box.
""" % (settings.SITE_URL.rstrip('/') + urlresolvers.reverse('default_profile'))

    if changeset.indexer.indexer.notify_on_approve or comment_text:
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

        if comment_text:
            subject = 'GCD change approved with a comment'
            send_comment_observer(request, changeset, comment_text)
        else:
            subject = 'GCD change approved'
        changeset.indexer.email_user(subject, email_body,
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
                                        reservation_requested=True,
                                        issue__created__gt=F('created'),
                                        series__ongoing_reservation__isnull=False,
                                        issue__variant_of__isnull=False):
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
                                        series__ongoing_reservation__isnull=False,
                                        issue__variant_of=None):
        new_change = _do_reserve(issue_revision.series.ongoing_reservation.indexer,
                                 issue_revision.issue, 'issue')
        if new_change is None:
            _send_declined_reservation_email(issue_revision.series.\
                                             ongoing_reservation.indexer,
                                             issue_revision.issue)
        else:
            issue_revision.issue.reserved = True
            issue_revision.issue.save()

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

    comment_text = request.POST['comments'].strip()
    if not comment_text:
        return render_error(request,
                            'You must explain why you are disapproving this '
                            'change.  Please press the "back" button and use '
                            'the comments field for the explanation.')

    changeset.disapprove(notes=comment_text)

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
       comment_text,
       settings.SITE_URL.rstrip('/') +
         urlresolvers.reverse('edit', kwargs={'id': changeset.id }),
       settings.SITE_NAME,
       settings.SITE_URL)

    changeset.indexer.email_user('GCD change sent back', email_body,
      settings.EMAIL_INDEXING)
      
    send_comment_observer(request, changeset, comment_text)

    if request.user.approved_changeset.filter(state=states.REVIEWING).count():
        return HttpResponseRedirect(urlresolvers.reverse('reviewing'))
    else:
        return HttpResponseRedirect(urlresolvers.reverse('pending'))

def send_comment_observer(request, changeset, comments):
    email_body = u"""
Hello from the %s!


  %s added a comment to the change "%s" to which you added a comment before:
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
           
    if changeset.approver:
        excluding = [changeset.indexer, changeset.approver, request.user]
    else:
        excluding = [changeset.indexer, request.user]
    commenters = set(changeset.comments.exclude(text='')\
                     .exclude(commenter__in=excluding)\
                     .values_list('commenter', flat=True))
    for commenter in commenters:
        User.objects.get(id=commenter).email_user('GCD comment',
            email_body, settings.EMAIL_INDEXING)

@permission_required('gcd.can_reserve')
def add_comments(request, id):
    """
    Comment on a change and return to the compare page.
    """
    if request.method != 'POST':
        return _cant_get(request)

    changeset = get_object_or_404(Changeset, id=id)
    comment_text = request.POST['comments'].strip()
    if comment_text:
        changeset.comments.create(commenter=request.user,
                                  text=comment_text,
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
           comment_text,
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
              
        send_comment_observer(request, changeset, comment_text)

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
            form_class = get_revision_form(revision, user=request.user)
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

    if 'discuss' in request.POST:
        return discuss(request, id)

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
    for i in remove_fields:
        form.fields.pop(i)
    return form

@permission_required('gcd.can_reserve')
def edit_issues_in_bulk(request):
    if not request.user.indexer.can_reserve_another():
        return render_error(request, REACHED_CHANGE_LIMIT)

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

    form_class = get_bulk_issue_revision_form(series, 'bulk_edit',
                                              user=request.user)

    fields = get_issue_field_list()
    fields.remove('number')
    fields.remove('publication_date')
    fields.remove('key_date')
    fields.remove('year_on_sale')
    fields.remove('month_on_sale')
    fields.remove('day_on_sale')
    fields.remove('on_sale_date_uncertain')
    fields.remove('isbn')
    fields.remove('notes')
    fields.remove('barcode')
    fields.remove('title')
    fields.remove('keywords')

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
        comment += u'%s : %s\n' % (search[0], search[1])
    comment += u'method : %s\n' % method
    comment += u'behavior : %s\n' % logic
    # cannot use urlencode since urlize needs plain text
    # and urlencode would encode non-ASCII characters
    query_string = ''
    for entry in request.GET.iteritems():
        if query_string == '':
            query_string += u'?%s=%s' % entry
        else:
            query_string += u'&%s=%s' % entry
    comment += u'Search results: %s%s%s' % (settings.SITE_URL.rstrip('/'),
                 urlresolvers.reverse('process_advanced_search'),
                 query_string.replace(' ', '+'))

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
        return render_error(request, REACHED_CHANGE_LIMIT)

    if request.method != 'POST':
        form = get_publisher_revision_form(user=request.user)()
        return _display_add_publisher_form(request, form)

    if 'cancel' in request.POST:
        return HttpResponseRedirect(urlresolvers.reverse('add'))

    form = get_publisher_revision_form(user=request.user)(request.POST)
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
        return render_error(request, REACHED_CHANGE_LIMIT)

    try:
        parent = Publisher.objects.get(id=parent_id, is_master=True)
        if parent.deleted or parent.pending_deletion():
            return render_error(request, u'Cannot add indicia publishers '
              u'since "%s" is deleted or pending deletion.' % parent)

        if request.method != 'POST':
            form = get_indicia_publisher_revision_form(user=request.user)()
            return _display_add_indicia_publisher_form(request, parent, form)

        if 'cancel' in request.POST:
            return HttpResponseRedirect(urlresolvers.reverse(
              'apps.gcd.views.details.publisher',
              kwargs={ 'publisher_id': parent_id }))

        form = get_indicia_publisher_revision_form(user=request.user)(request.POST)
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
        return render_error(request, REACHED_CHANGE_LIMIT)

    try:
        parent = Publisher.objects.get(id=parent_id, is_master=True)
        if parent.deleted or parent.pending_deletion():
            return render_error(request, u'Cannot add brands '
              u'since "%s" is deleted or pending deletion.' % parent)

        if request.method != 'POST':
            form = get_brand_revision_form(user=request.user)()
            return _display_add_brand_form(request, parent, form)

        if 'cancel' in request.POST:
            return HttpResponseRedirect(urlresolvers.reverse(
              'apps.gcd.views.details.publisher',
              kwargs={ 'publisher_id': parent_id }))

        form = get_brand_revision_form(user=request.user)(request.POST)
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
        return render_error(request, REACHED_CHANGE_LIMIT)

    # Process add form if this is a POST.
    try:
        publisher = Publisher.objects.get(id=publisher_id, is_master=True)
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
            # TODO: make these using same code as get_blank_values
            initial['has_barcode'] = True
            initial['has_indicia_frequency'] = True
            initial['has_isbn'] = True
            initial['has_volume'] = True
            initial['is_comics_publication'] = True
            form = get_series_revision_form(publisher,
                                            user=request.user)(initial=initial)
            return _display_add_series_form(request, publisher, imprint, form)

        if 'cancel' in request.POST:
            return HttpResponseRedirect(urlresolvers.reverse(
              'apps.gcd.views.details.publisher',
              kwargs={ 'publisher_id': publisher_id }))

        form = get_series_revision_form(publisher,
                                        user=request.user)(request.POST)
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

def init_added_variant(form_class, initial, issue):
    for key in initial.keys():
        if key.startswith('_'):
            initial.pop(key)
    if issue.brand:
        initial['brand'] = issue.brand.id
    if issue.indicia_publisher:
        initial['indicia_publisher'] = issue.indicia_publisher.id
    initial['variant_name'] = u''
    if issue.variant_set.filter(deleted=False).count():
        initial['after'] = issue.variant_set.filter(deleted=False).latest('sort_code').id
    form = form_class(initial=initial)
    return form

@permission_required('gcd.can_reserve')
def add_issue(request, series_id, sort_after=None, variant_of=None,
              variant_cover=None, edit_with_base=False):
    if not request.user.indexer.can_reserve_another():
        return render_error(request, REACHED_CHANGE_LIMIT)

    series = get_object_or_404(Series, id=series_id)
    if series.deleted or series.pending_deletion():
        return render_error(request, u'Cannot add an issue '
          u'since "%s" is deleted or pending deletion.' % series)

    form_class = get_revision_form(model_name='issue',
                                   series=series,
                                   publisher=series.publisher,
                                   variant_of=variant_of,
                                   user=request.user)

    if request.method != 'POST':
        if variant_of:
            initial = dict(variant_of.__dict__)
            form = init_added_variant(form_class, initial, variant_of)
        else:
            initial = {}
            reversed_issues = series.active_issues().order_by('-sort_code')
            if reversed_issues.count():
                initial['after'] = reversed_issues[0].id
            form = form_class(initial=initial)
        return _display_add_issue_form(request, series, form, variant_of,
                                       variant_cover)

    if 'cancel' in request.POST:
        if variant_of:
            return HttpResponseRedirect(urlresolvers.reverse(
              'apps.gcd.views.details.issue',
              kwargs={ 'issue_id': variant_of.id }))
        else:
            return HttpResponseRedirect(urlresolvers.reverse(
              'apps.gcd.views.details.series',
              kwargs={ 'series_id': series_id }))

    form = form_class(request.POST)
    if not form.is_valid():
        return _display_add_issue_form(request, series, form, variant_of,
                                       variant_cover)

    if variant_of and edit_with_base:
        kwargs = {'variant_of': variant_of,
                  'issuerevision': form.save(commit=False)}
        if variant_cover:
            return reserve(request, variant_cover.id, 'cover',
                           callback=add_variant_issuerevision,
                           callback_args=kwargs)
        return reserve(request, variant_of.id, 'issue',
                       callback=add_variant_issuerevision,
                       callback_args=kwargs)

    changeset = Changeset(indexer=request.user, state=states.OPEN,
                          change_type=CTYPES['issue_add'])
    changeset.save()
    revision = form.save(commit=False)
    revision.save_added_revision(changeset=changeset,
                                 series=series,
                                 variant_of=variant_of)
    return submit(request, changeset.id)

def add_variant_to_issue_revision(request, changeset_id, issue_revision_id):
    changeset = get_object_or_404(Changeset, id=changeset_id)
    if request.user != changeset.indexer:
        return render_error(request,
          'Only the reservation holder may add variants.')
    if changeset.change_type in [CTYPES['variant_add'], CTYPES['two_issues']]:
        return render_error(request,
          'You cannot add a variant to this changeset.')
    issue_revision = changeset.issuerevisions.get(id=issue_revision_id)

    form_class = get_revision_form(model_name='issue',
                                   series=issue_revision.series,
                                   publisher=issue_revision.series.publisher,
                                   variant_of=issue_revision.issue,
                                   user=request.user)

    if request.method != 'POST':
        initial = dict(issue_revision.__dict__)
        form = init_added_variant(form_class, initial, issue_revision)
        return _display_add_issue_form(request, series, form, None, None,
                                       issue_revision=issue_revision)

    if 'cancel' in request.POST:
        return HttpResponseRedirect(urlresolvers.reverse(
          'edit',
          kwargs={ 'id': changeset_id }))

    form = form_class(request.POST)
    if not form.is_valid():
        return _display_add_issue_form(request, series, form, None, None,
                                       issue_revision=issue_revision)

    variant_revision = form.save(commit=False)
    variant_revision.save_added_revision(changeset=changeset,
                                         series=issue_revision.series,
                                         variant_of=issue_revision.issue)
    changeset.change_type=CTYPES['variant_add']
    changeset.save()

    return HttpResponseRedirect(urlresolvers.reverse(
      'edit',
      kwargs={ 'id': changeset_id }))

def add_variant_issuerevision(changeset, revision, variant_of, issuerevision):
    if changeset.change_type == CTYPES['cover']:
        issue = revision.issue
        if _is_reservable('issue', issue.id) == 0:
            return False

        # create issue revision for the issue of the cover
        if not _do_reserve(changeset.indexer, issue, 'issue', changeset=changeset):
            _unreserve(issue)
            return False
    changeset.change_type=CTYPES['variant_add']
    changeset.save()

    # save issue revision for the new variant record
    issuerevision.save_added_revision(changeset=changeset,
                                      series=variant_of.series,
                                      variant_of=variant_of)
    return True

@permission_required('gcd.can_reserve')
def add_variant_issue(request, issue_id, cover_id=None, edit_with_base=False):
    if cover_id:
        cover = get_object_or_404(Cover, id=cover_id)
        if cover.issue.id != int(issue_id):
            return render_error(request,
                'Selected cover does not correspond to selected issue.')
    else:
        cover = None
    issue = get_object_or_404(Issue, id=issue_id)

    if 'edit_with_base' in request.POST or edit_with_base:
        return add_issue(request, issue.series.id, variant_of=issue,
                        variant_cover=cover, edit_with_base=True)
    else:
        return add_issue(request, issue.series.id, variant_of=issue,
                         variant_cover=cover)

def _display_add_issue_form(request, series, form, variant_of, variant_cover,
                            issue_revision=None):
    action_label = 'Submit new'
    alternative_action = None
    alternative_label = None
    if variant_of:
        kwargs = {
            'issue_id': variant_of.id,
        }
        if variant_cover:
            kwargs['cover_id'] = variant_cover.id
            action_label = 'Save new'
            object_name = 'Variant Issue for %s and edit both' % variant_of
        else:
            alternative_action = 'edit_with_base'
            alternative_label = 'Save new Variant Issue for %s and edit both' \
                                % variant_of
            object_name = 'Variant Issue for %s' % variant_of

        url = urlresolvers.reverse('add_variant_issue', kwargs=kwargs)
    elif issue_revision:
        kwargs = {
            'issue_revision_id': issue_revision.id,
            'changeset_id': issue_revision.changeset.id,
        }
        action_label = 'Save new'
        url = urlresolvers.reverse('add_variant_to_issue_revision', kwargs=kwargs)
        object_name = 'Variant Issue for %s' % issue_revision
    else:
        kwargs = {
            'series_id': series.id,
        }
        url = urlresolvers.reverse('add_issue', kwargs=kwargs)
        object_name = 'Issue'

    return render_to_response('oi/edit/add_frame.html',
      {
        'object_name': object_name,
        'object_url': url,
        'action_label': action_label,
        'form': form,
        'alternative_action': alternative_action,
        'alternative_label': alternative_label
      },
      context_instance=RequestContext(request))

@permission_required('gcd.can_reserve')
def add_issues(request, series_id, method=None):
    if not request.user.indexer.can_reserve_another():
        return render_error(request, REACHED_CHANGE_LIMIT)

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

    form_class = get_bulk_issue_revision_form(series=series, method=method,
                                              user=request.user)

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
      indicia_pub_not_printed=cd['indicia_pub_not_printed'],
      brand=cd['brand'],
      no_brand=cd['no_brand'],
      indicia_frequency=cd['indicia_frequency'],
      no_indicia_frequency=cd['no_indicia_frequency'],
      price=cd['price'],
      page_count=cd['page_count'],
      page_count_uncertain=cd['page_count_uncertain'],
      editing=cd['editing'],
      no_editing=cd['no_editing'],
      no_isbn=cd['no_isbn'],
      no_barcode=cd['no_barcode'],
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
def add_story(request, issue_revision_id, changeset_id):
    changeset = get_object_or_404(Changeset, id=changeset_id)
    if request.user != changeset.indexer:
        return render_error(request,
          'Only the reservation holder may add stories.')
    # Process add form if this is a POST.
    try:
        issue_revision = changeset.issuerevisions.get(id=issue_revision_id)
        issue = issue_revision.issue
        if issue_revision.variant_of and \
          issue_revision.active_stories().count():
            return render_error(request,
                  'You cannot add more than one story to a variant issue.',
                  redirect=False)

        if request.method != 'POST':
            seq = ''
            if 'added_sequence_number' in request.GET:
                seq = request.GET['added_sequence_number']
            if seq == '':
                return render_error(request,
                  'You must supply a sequence number for the new story.',
                  redirect=False)
            else:
                initial = _get_initial_add_story_data(request, issue_revision,
                                                      seq)
                if issue:
                    is_comics_publication = issue.series.is_comics_publication
                else: # for variants added with base issue the issue is not set
                    is_comics_publication = True
                form = get_story_revision_form(user=request.user,
                  is_comics_publication=is_comics_publication)\
                  (initial=initial)
            return _display_add_story_form(request, issue_revision, form,
                                           changeset_id)

        if 'cancel_return' in request.POST:
            return HttpResponseRedirect(urlresolvers.reverse('edit',
              kwargs={ 'id': changeset_id }))

        form = get_story_revision_form(user=request.user)(request.POST)
        if not form.is_valid():
            return _display_add_story_form(request, issue_revision, form,
                                           changeset_id)

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
    if seq_num == 0 and issue_revision.series.is_comics_publication:
        # Do not default other sequences, because if we do we
        # will get a lot of people leaving the default values
        # by accident.  Only sequence zero is predictable.
        initial['type'] = StoryType.objects.get(name='cover').id
        initial['no_script'] = True

    initial['sequence_number'] = seq_num
    return initial

def _display_add_story_form(request, issue, form, changeset_id):
    kwargs = {
        'issue_revision_id': issue.id,
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
# Reprint Link Editing
##############################################################################

def confirm_reprint_migration(request, id, changeset_id):
    changeset = get_object_or_404(Changeset, id=changeset_id)
    if request.user != changeset.indexer:
        return render_error(request,
          'Only the reservation holder may confirm the reprint migration.')
    migration_status = get_object_or_404(MigrationStoryStatus, story__id=id)
    if request.method == 'GET':
        story = changeset.storyrevisions.get(story__id=id)
        return render_to_response('oi/edit/confirm_reprint_migration.html',
          {
              'story': story,
              'changeset': changeset,
          },
          context_instance=RequestContext(request))
    else:
        if 'confirm' in request.POST:
            migration_status.reprint_confirmed = True
            migration_status.reprint_needs_inspection = False
            migration_status.save()
        return HttpResponseRedirect(urlresolvers.reverse('edit',
          kwargs={ 'id': changeset_id }))

def parse_reprint(reprints):
    """ parse a reprint entry for exactly our standard """
    reprint_direction_from = ["from", "da", "di", "de", "uit", u"från", "aus"]
    reprint_direction_to = ["in", "i"]
    from_to = reprints.split(' ')[0].lower()
    if from_to in reprint_direction_from + reprint_direction_to:
        try:# our format: seriesname (publisher, year <series>) #nr
            position = reprints.find(' (')
            series = reprints[len(from_to) + 1:position]
            string = reprints[position + 2:]
            after_series = string
            end_bracket = string.find(')')
            position = string[:end_bracket].rfind(', ')
            if position < 0:
                series_pos = string.lower().find('series)')
                if series_pos > 0:
                    position = string[:series_pos].rfind(', ')
            publisher = string[:position].strip()
            position += 2
            string = string[position:]
            year = string[:4]
            if from_to in ['da ', 'in ', 'de ', 'en ']: #italian and spanish from/in
                if year.isdigit() != True:
                    position = string.find(')')
                    year = string[position-4:position]
            string = string[4:]
            position = string.find(' #')
            if position > 0 and len(string[position+2:]):
                
                string = string[position + 2:]
                position = string.find(' [') #check for notes
                if position > 0:
                    position_end = string.find(']')
                    if position_end > position:
                        notes = string[position+2:position_end]
                    date_pos = string.find(' (') #check for (date)
                    if date_pos > 0 and date_pos < position:
                        position = date_pos
                else:
                    position = string.find(' (') #check for (date)
                    if position > 0: #if found ignore later
                        pass
                volume = None
                if string.isdigit(): #in this case we are fine
                    number = string
                elif string[0].lower() == 'v' and string.find('#') > 0:
                    n_pos = string.find('#')
                    volume = string[1:n_pos]
                    if position > 0:
                        number = string[n_pos+1:position]
                    else:
                        number = string[n_pos+1:]
                else:
                    hyphen = string.find(' -')
                    # following issue title after number
                    if hyphen > 0 and string[:hyphen].isdigit() and not string[hyphen+2:].strip()[0].isdigit():
                        number = string[:hyphen]
                    else:
                        if position > 0:
                            number = string[:position].strip('., ')
                        else:
                            number = string.strip('., ')
                if number == 'nn':
                    number = '[nn]'
                if number == '?':
                    number = None
            else:
                number = None
                volume = None
            return publisher, series, year, number, volume
        except:
            pass
    return None, None, None, None, None

@permission_required('gcd.can_reserve')
def list_issue_reprints(request, id):
    issue_revision = get_object_or_404(IssueRevision, id=id)
    changeset = issue_revision.changeset
    if request.user != changeset.indexer:
        return render_error(request,
          'Only the reservation holder may access this page.')
    response = render_to_response('oi/edit/list_issue_reprints.html',
      { 'issue_revision': issue_revision, 'changeset': changeset },
      context_instance=RequestContext(request))
    response['Cache-Control'] = "no-cache, no-store, max-age=0, must-revalidate"
    return response

@permission_required('gcd.can_reserve')
def reserve_reprint(request, changeset_id, reprint_id, reprint_type):
    changeset = get_object_or_404(Changeset, id=changeset_id)
    if request.user != changeset.indexer:
        return render_error(request,
          'Only the reservation holder may access this page.')
    if 'edit_origin' in request.POST:
        which_side = 'origin'
    elif 'edit_origin_internal' in request.POST:
        which_side = 'origin_internal'
    elif 'edit_target' in request.POST:
        which_side = 'target'
    elif 'edit_target_internal' in request.POST:
        which_side = 'target_internal'
    elif 'flip_direction' in request.POST:
        which_side = 'flip_direction'
    elif 'delete' in request.POST:
        which_side = 'delete'
    elif 'matching_sequence' in request.POST:
        which_side = 'matching_sequence'
    elif 'edit_note_origin' in request.POST:
        which_side = 'edit_note_origin'
    elif 'edit_note_target' in request.POST:
        which_side = 'edit_note_target'
    else:
        return _cant_get(request)
    display_obj = get_object_or_404(DISPLAY_CLASSES[reprint_type],
                                    id=reprint_id)
    if _is_reservable(reprint_type, reprint_id) == 0:
        return render_error(request,
          u'Cannot edit "%s" as it is already reserved.' % display_obj)

    revision = ReprintRevision.objects.clone_revision(display_obj,
                                                      changeset=changeset)
    return HttpResponseRedirect(urlresolvers.reverse('edit_reprint',
        kwargs={'id': revision.id, 'which_side': which_side }))

        
@permission_required('gcd.can_reserve')
def edit_reprint(request, id, which_side=None):
    reprint_revision = get_object_or_404(ReprintRevision, id=id)
    changeset = reprint_revision.changeset
    if request.user != changeset.indexer:
        return render_error(request,
          'Only the reservation holder may access this page.')

    if not which_side:
        if 'edit_origin' in request.POST:
            which_side = 'origin'
        elif 'edit_origin_internal' in request.POST:
            which_side = 'origin_internal'
        elif 'edit_target' in request.POST:
            which_side = 'target'
        elif 'edit_target_internal' in request.POST:
            which_side = 'target_internal'
        elif 'flip_direction' in request.POST:
            which_side = 'flip_direction'
        elif 'delete' in request.POST:
            which_side = 'delete'
        elif 'restore' in request.POST:
            which_side = 'restore'
        elif 'remove' in request.POST:
            which_side = 'remove'
        elif 'matching_sequence' in request.POST:
            which_side = 'matching_sequence'
        elif 'edit_note_origin' in request.POST:
            which_side = 'edit_note_origin'
        elif 'edit_note_target' in request.POST:
            which_side = 'edit_note_target'
        else:
            return _cant_get(request)

    changeset_issue = changeset.issuerevisions.get()

    issue = None
    story = None
    story_revision = None
    if which_side.startswith('origin'):
        if reprint_revision.origin_story:
            select_issue = reprint_revision.origin_story.issue
            sequence_number = reprint_revision.origin_story.sequence_number
        elif reprint_revision.origin_issue:
            select_issue = reprint_revision.origin_issue
            sequence_number = None
        elif which_side == 'origin_internal':
            select_issue = reprint_revision.origin_revision.issue
        else: # for newly added stories problematic otherwise
            raise NotImplementedError
        if reprint_revision.target_issue:
            issue = reprint_revision.target_issue
        elif reprint_revision.target_story:
            story = reprint_revision.target_story
        else:
            story_revision = reprint_revision.target_revision
    elif which_side.startswith('target'):
        if reprint_revision.target_story:
            select_issue = reprint_revision.target_story.issue
            sequence_number = reprint_revision.target_story.sequence_number
        elif reprint_revision.target_issue:
            select_issue = reprint_revision.target_issue
            sequence_number = None
        elif which_side == 'target_internal':
            select_issue = reprint_revision.target_revision.issue
        else: # for newly added stories problematic otherwise
            raise NotImplementedError
        if reprint_revision.origin_issue:
            issue = reprint_revision.origin_issue
        elif reprint_revision.origin_story:
            story = reprint_revision.origin_story
        else:
            story_revision = reprint_revision.origin_revision
    elif which_side == 'flip_direction':
        origin_story = reprint_revision.target_story
        origin_revision = reprint_revision.target_revision
        origin_issue = reprint_revision.target_issue
        reprint_revision.target_story = reprint_revision.origin_story
        reprint_revision.target_revision = reprint_revision.origin_revision
        reprint_revision.target_issue = reprint_revision.origin_issue
        reprint_revision.origin_story = origin_story
        reprint_revision.origin_revision = origin_revision
        reprint_revision.origin_issue = origin_issue
        reprint_revision.save()
        return HttpResponseRedirect(urlresolvers.reverse('list_issue_reprints',
            kwargs={ 'id': changeset_issue.id }))
    elif which_side == 'delete':
        reprint_revision.deleted = True
        reprint_revision.save()
        return HttpResponseRedirect(urlresolvers.reverse('list_issue_reprints',
            kwargs={ 'id': changeset_issue.id }))
    elif which_side == 'restore':
        if reprint_revision.deleted:
            reprint_revision.deleted = False
            reprint_revision.save()
            return HttpResponseRedirect(urlresolvers.reverse('list_issue_reprints',
                kwargs={ 'id': changeset_issue.id }))
        else:
            return _cant_get(request)            
    elif which_side == 'remove':
        return HttpResponseRedirect(urlresolvers.reverse('remove_reprint_revision',
            kwargs={ 'id': id }))
    elif which_side == 'matching_sequence':
        if reprint_revision.origin_story:
            story = reprint_revision.origin_story
            issue = reprint_revision.target_issue
        else:
            story = reprint_revision.target_story
            issue = reprint_revision.origin_issue
        if issue != changeset_issue.issue:
            return _cant_get(request)
        return HttpResponseRedirect(urlresolvers.reverse('create_matching_sequence',
            kwargs={ 'reprint_revision_id': id, 'story_id': story.id, 'issue_id': issue.id }))
        raise ValueError
    elif which_side.startswith('edit_note'):
        if which_side == 'edit_note_origin':
            which_side = 'target'
            if reprint_revision.origin_story:
                story = reprint_revision.origin_story
                story_story = True
                story_revision = False
                issue = None
            elif reprint_revision.origin_revision:
                story = reprint_revision.origin_revision
                story_story = False
                story_revision = True
                issue = None
            else:
                story = None 
                story_story = False
                story_revision = False
                issue = reprint_revision.origin_issue
            if reprint_revision.target_story:
                selected_story = reprint_revision.target_story
                selected_issue = None
            else:
                selected_story = None
                selected_issue = reprint_revision.target_issue
        else:
            which_side = 'origin'
            if reprint_revision.target_story:
                story = reprint_revision.target_story
                story_story = True
                story_revision = False
                issue = None
            elif reprint_revision.target_revision:
                story = reprint_revision.target_revision
                story_story = False
                story_revision = True
                issue = None
            else:
                story = None 
                story_story = False
                story_revision = False
                issue = reprint_revision.target_issue
            if reprint_revision.origin_story:
                selected_story = reprint_revision.origin_story
                selected_issue = None
            else:
                selected_story = None
                selected_issue = reprint_revision.origin_issue
            
        return render_to_response('oi/edit/confirm_reprint.html',
            {
            'story': story,
            'issue': issue,
            'story_story': story_story,
            'story_revision': story_revision,
            'selected_story': selected_story,
            'selected_issue': selected_issue,
            'reprint_revision': reprint_revision,
            'reprint_revision_id': reprint_revision.id,
            'changeset': changeset,
            'which_side': which_side
            },
            context_instance=RequestContext(request))
                
    else:
        raise NotImplementedError

    if which_side.endswith('internal'):
        issue_revision  = select_issue.revisions.get(changeset=changeset)
        return render_to_response('oi/edit/select_internal_object.html',
            { 'issue_revision': issue_revision, 'changeset': changeset,
              'reprint_revision': reprint_revision, 'which_side': which_side[:6]},
        context_instance=RequestContext(request))
        
    initial = {'series': select_issue.series.name,
               'publisher': select_issue.series.publisher,
               'year': select_issue.series.year_began,
               'number': select_issue.number,
               'sequence_number': sequence_number}
    if story or story_revision:
        if story:
            story_id = story.id
            story_revision_id = None
        else:
            story_id = None
            story_revision_id = story_revision.id
            story = story_revision
        issue_id = None
        heading = 'Select story/issue for the reprint link with %s of %s' \
                                    % (esc(story), esc(story.issue))
    else:
        story_id = None
        issue_id = issue.id
        story_revision_id = None
        heading = 'Select story/issue for the reprint link with %s' \
                                    % (esc(issue))
    data = {'story_id': story_id,
            'story_revision_id': story_revision_id,
            'issue_id': issue_id,
            'reprint_revision_id': reprint_revision.id,
            'changeset_id': changeset.id,
            'story': True,
            'issue': True,
            'initial': initial,
            'heading': mark_safe('<h2>%s</h2>' % heading),
            'target': 'a story or issue',
            'return': confirm_reprint,
            'which_side': which_side,
            'cancel': HttpResponseRedirect(urlresolvers.reverse('edit',
                        kwargs={'id': changeset.id}))}
    select_key = store_select_data(request, None, data)
    return HttpResponseRedirect(urlresolvers.reverse('select_object',
        kwargs={'select_key': select_key}))

@permission_required('gcd.can_reserve')
def add_reprint(request, changeset_id, story_id=None, issue_id=None, reprint_note=''):
    if story_id:
        story = get_object_or_404(StoryRevision, id=story_id,
                                    changeset__id=changeset_id)
    else:
        issue = get_object_or_404(IssueRevision, id=issue_id,
                                  changeset__id=changeset_id)
    if reprint_note:
        publisher, series, year, number, volume = \
            parse_reprint(reprint_note)
        initial = { 'series': series, 'publisher': publisher,
                    'year': year, 'number': number }
    else:
        initial = {}
    if story_id:
        heading = 'Select story/issue for the reprint link with %s of %s' \
                                    % (esc(story), esc(story.issue))
    else:
        heading = 'Select story/issue for the reprint link with %s' \
                                    % (esc(issue))
    data = {'story_revision_id': story_id,
            'issue_revision_id': issue_id,
            'changeset_id': changeset_id,
            'story': True,
            'issue': True,
            'initial': initial,
            'heading': mark_safe('<h2>%s</h2>' % heading),
            'target': 'a story or issue',
            'return': confirm_reprint,
            'cancel': HttpResponseRedirect(urlresolvers.reverse('edit',
                        kwargs={'id': changeset_id}))}
    select_key = store_select_data(request, None, data)
    return HttpResponseRedirect(urlresolvers.reverse('select_object',
          kwargs={'select_key': select_key}))

@permission_required('gcd.can_reserve')
def select_internal_object(request, id, changeset_id, which_side,
                           issue_id=None, story_id=None):
    reprint_revision = get_object_or_404(ReprintRevision, id=id)
    if reprint_revision.changeset.id != int(changeset_id):
        return _cant_get(request)
    changeset = reprint_revision.changeset
    if request.user != changeset.indexer:
        return render_error(request,
          'Only the reservation holder may access this page.')
    if which_side == 'origin':
        if reprint_revision.target_story:
            other_story = reprint_revision.target_story
            other_issue = None
        elif reprint_revision.target_issue:
            other_issue = reprint_revision.target_issue
            other_story = None
        else:
            raise NotImplementedError
    elif which_side == 'target':
        if reprint_revision.origin_story:
            other_story = reprint_revision.origin_story
            other_issue = None
        elif reprint_revision.origin_issue:
            other_issue = reprint_revision.origin_issue
            other_story = None
        else:
            raise NotImplementedError
    else:
        return _cant_get(request)

    if issue_id:
        this_issue = get_object_or_404(IssueRevision, id=issue_id)
        this_story = None
    else:
        this_story = get_object_or_404(StoryRevision, id=story_id)
        this_issue = None

    return render_to_response('oi/edit/confirm_internal.html',
        { 'this_issue': this_issue, 'this_story': this_story,
          'other_issue': other_issue, 'other_story': other_story,
          'changeset': changeset, 'reprint_revision_id': reprint_revision.id,
          'reprint_revision': reprint_revision, 'which_side': which_side },
        context_instance=RequestContext(request))
          
@permission_required('gcd.can_reserve')
def create_matching_sequence(request, reprint_revision_id, story_id, issue_id):
    story = get_object_or_404(Story, id=story_id)
    issue = get_object_or_404(Issue, id=issue_id)
    reprint_revision = get_object_or_404(ReprintRevision, id=reprint_revision_id)
    changeset = reprint_revision.changeset
    changeset_issue = changeset.issuerevisions.get()
    if request.user != changeset.indexer:
        return render_error(request,
          'Only the reservation holder may access this page.')
    if issue != changeset_issue.issue:
        return _cant_get(request)
    if request.method != 'POST':
        if story == reprint_revision.origin_story:
            direction = 'from'
        else:
            direction = 'in'
        return render_to_response('oi/edit/create_matching_sequence.html',
            { 'issue': issue, 'story': story, 'reprint_revision': reprint_revision, 'direction': direction },
            context_instance=RequestContext(request))
    else:
        story_revision = StoryRevision.objects.clone_revision(story=story,
                                               changeset=changeset)
        story_revision.story = None
        story_revision.issue = changeset_issue.issue
        story_revision.sequence_number = changeset_issue.next_sequence_number()
        if story_revision.issue.series.language != story.issue.series.language:
            if story_revision.letters:
                story_revision.letters = u'?'
            story_revision.title = u''
            story_revision.title_inferred = False
        story_revision.save()
        if reprint_revision.origin_story:
            reprint_revision.target_revision = story_revision
            reprint_revision.target_issue = None
        else:
            reprint_revision.origin_revision = story_revision
            reprint_revision.origin_issue = None
        reprint_revision.save()
        return HttpResponseRedirect(urlresolvers.reverse('edit_revision',
              kwargs={ 'model_name': 'story', 'id': story_revision.id }))
              
@permission_required('gcd.can_reserve')
def confirm_reprint(request, data, object_type, selected_id):
    if request.method != 'POST':
        return _cant_get(request)
    if 'cancel' in request.POST:
        return HttpResponseRedirect(urlresolvers.reverse('edit',
          kwargs={ 'id': changeset_id }))

    if 'story_id' in data and data['story_id']:
        current_story = get_object_or_404(Story, id=data['story_id'])        
        current_story_revision = None
        story = current_story
        current_issue = None
    elif 'story_revision_id' in data and data['story_revision_id']:
        current_story = None
        current_story_revision = get_object_or_404(StoryRevision,
                                   id=data['story_revision_id'],
                                   changeset__id=data['changeset_id'])
        story = current_story_revision
        current_issue = None
    elif 'issue_id' in data and data['issue_id']:
        current_story = None
        current_story_revision = None
        story = None
        current_issue = get_object_or_404(Issue, id=data['issue_id'])
    elif 'issue_revision_id' in data and data['issue_revision_id']:
        current_story = None
        current_story_revision =None
        story = None
        current_issue = get_object_or_404(IssueRevision,
                                          id=data['issue_revision_id'])
        current_issue = current_issue.issue
    else:
        raise NotImplementedError
        
    changeset = get_object_or_404(Changeset, id=data['changeset_id'])
    
    if object_type == 'story':
        selected_story = get_object_or_404(Story, id=selected_id)
        selected_issue = None
    else:
        selected_story = None
        selected_issue = get_object_or_404(Issue, id=selected_id)
        
    if 'reprint_revision_id' in data:
        reprint_revision = get_object_or_404(ReprintRevision, 
                                             id=data['reprint_revision_id'])
        reprint_revision_id = data['reprint_revision_id']
    else:
        reprint_revision_id = None
        reprint_revision = None

    if 'which_side' in data:
        which_side = data['which_side']
    else:
        which_side = None
    return render_to_response('oi/edit/confirm_reprint.html',
        {
        'story': story,
        'issue': current_issue,
        'story_story': current_story,
        'story_revision': current_story_revision,
        'selected_story': selected_story,
        'selected_issue': selected_issue,
        'reprint_revision': reprint_revision,
        'reprint_revision_id': reprint_revision_id,
        'changeset': changeset,
        'which_side': which_side
        },
        context_instance=RequestContext(request))

@permission_required('gcd.can_reserve')
def save_reprint(request, reprint_revision_id, changeset_id,
                 story_one_id=None, story_revision_id=None, issue_one_id=None,
                 story_two_id=None, issue_two_id=None):
    if request.method != 'POST':
        return _cant_get(request)
    if 'cancel' in request.POST:
        return HttpResponseRedirect(urlresolvers.reverse('edit',
          kwargs={ 'id': changeset_id }))
    if story_one_id and (story_revision_id or issue_one_id):
        return _cant_get(request)
    if story_two_id and issue_two_id:
        return _cant_get(request)
    if reprint_revision_id.isdigit():
        revision = get_object_or_404(ReprintRevision, id=reprint_revision_id)
        if revision.changeset.id != int(changeset_id):
            return _cant_get(request)
    else:
        revision = None
        
    changeset = get_object_or_404(Changeset, id=changeset_id)
        
    origin_story = None
    origin_revision = None
    origin_issue = None
    target_story = None
    target_revision = None
    target_issue = None

    if story_revision_id:
        story_revision = StoryRevision.objects.get(id=story_revision_id)
        if 'reprint_notes' in request.POST:
            story_revision.reprint_notes = request.POST['reprint_notes']
        story_revision.save()
        if story_revision.story:
            story_one_id = story_revision.story.id
            story_revision_id = None

    if request.POST['direction'] == 'from':
        if story_one_id:
            target_story = Story.objects.get(id=story_one_id)
        elif story_revision_id:
            target_revision = story_revision            
        else:
            target_issue = Issue.objects.get(id=issue_one_id)
        if story_two_id:
            origin_story = Story.objects.get(id=story_two_id)
        else:
            origin_issue = Issue.objects.get(id=issue_two_id)
    else:
        if story_one_id:
            origin_story = Story.objects.get(id=story_one_id)
        elif story_revision_id:
            origin_revision = story_revision
        else:
            origin_issue = Issue.objects.get(id=issue_one_id)
        if story_two_id:
            target_story = Story.objects.get(id=story_two_id)
        else:
            target_issue = Issue.objects.get(id=issue_two_id)
            
    notes = request.POST['reprint_link_notes']
    if revision:
        revision.origin_story = origin_story
        revision.origin_revision=origin_revision
        revision.origin_issue=origin_issue
        revision.target_story=target_story
        revision.target_revision=target_revision
        revision.target_issue=target_issue
        revision.notes=notes
        revision.save()
    else:
        revision = ReprintRevision(origin_story=origin_story,
                                   origin_revision=origin_revision,
                                   origin_issue=origin_issue,
                                   target_story=target_story,
                                   target_revision=target_revision,
                                   target_issue=target_issue,
                                   notes=notes)
        revision.save_added_revision(changeset=changeset)
    if request.POST['comments'].strip():
        revision.comments.create(commenter=request.user,
                                 changeset=changeset,
                                 text=request.POST['comments'],
                                 old_state=changeset.state,
                                 new_state=changeset.state)
    if 'add_reprint_view' in request.POST:
        return HttpResponseRedirect(urlresolvers.reverse('list_issue_reprints',
            kwargs={ 'id': changeset.issuerevisions.get().id }))
    else:
        return HttpResponseRedirect(urlresolvers.reverse('edit',
            kwargs={ 'id': changeset_id }))
          

@permission_required('gcd.can_reserve')
def remove_reprint_revision(request, id):
    reprint = get_object_or_404(ReprintRevision, id=id)
    if request.user != reprint.changeset.indexer:
        return render_error(request,
          'Only the reservation holder may remove stories.')

    if reprint.source:
        return _cant_get(request)

    if hasattr(reprint, "origin"):
        origin = reprint.origin
        origin_issue = None
    else:
        origin = None
        origin_issue = reprint.origin_issue
    if hasattr(reprint, "target"):
        target = reprint.target
        target_issue = None
    else:
        target = None
        target_issue = reprint.target_issue
    
    if request.method != 'POST':
        return render_to_response('oi/edit/confirm_remove_reprint.html',
        {
            'origin': origin,
            'origin_issue': origin_issue,
            'target': target,
            'target_issue': target_issue,
            'reprint': reprint
        },
        context_instance=RequestContext(request))

    # we fully delete the freshly added link, but first check if a
    # comment is attached.
    if reprint.comments.count():
        comment = reprint.comments.latest('created')
        comment.text += '\nThe ReprintRevision "%s" for which this comment was'\
                        ' entered was removed.' % reprint
        comment.revision_id = None
        comment.save()
    elif reprint.changeset.approver:
        # changeset already was submitted once since it has an approver
        # TODO not quite sure if we actually should add this comment
        reprint.changeset.comments.create(commenter=reprint.changeset.indexer,
                          text='The ReprintRevision "%s" was removed.'\
                            % reprint,
                          old_state=reprint.changeset.state,
                          new_state=reprint.changeset.state)
    reprint.delete()
    return HttpResponseRedirect(urlresolvers.reverse('list_issue_reprints',
        kwargs={ 'id': reprint.changeset.issuerevisions.get().id }))
    
##############################################################################
# Moving Items
##############################################################################

@permission_required('gcd.can_reserve')
def move_series(request, series_revision_id, publisher_id):
    series_revision = get_object_or_404(SeriesRevision, id=series_revision_id,
                                        deleted=False)
    if request.user != series_revision.changeset.indexer:
        return render_error(request,
          'Only the reservation holder may move series.')

    publisher = Publisher.objects.filter(id=publisher_id, is_master=True,
                                         deleted=False)
    if not publisher:
        return render_error(request, 'No publisher with id %s.' \
                            % publisher_id, redirect=False)
    publisher = publisher[0]

    if request.method != 'POST':
        header_text = 'Do you want to move %s to <a href="%s">%s</a> ?' % \
          (esc(series_revision.series.full_name()), publisher.get_absolute_url(),
           esc(publisher))
        url = urlresolvers.reverse('move_series',
          kwargs={'series_revision_id': series_revision_id,
                  'publisher_id': publisher_id})
        cancel_button = "Cancel"
        confirm_button = "move of series %s to publisher %s" % \
          (series_revision.series, publisher)
        return render_to_response('oi/edit/confirm.html',
                                {
                                    'type': 'Series Move',
                                    'header_text': mark_safe(header_text),
                                    'url': url,
                                    'cancel_button': cancel_button,
                                    'confirm_button': confirm_button,
                                },
                                context_instance=RequestContext(request))
    else:
        if 'cancel' in request.POST:
            return HttpResponseRedirect(urlresolvers.reverse('edit',
              kwargs={'id': series_revision.changeset.id}))
        else:
            if series_revision.changeset.issuerevisions.count() == 0:
                for issue in series_revision.series.active_issues():
                    is_reservable = _is_reservable('issue', issue.id)

                    if is_reservable == 0:
                        for issue_rev in series_revision.changeset\
                                                        .issuerevisions.all():
                            _unreserve(issue_rev.issue)
                        return show_error_with_return(request, 'Error while'
                        ' reserving issues.', series_revision.changeset)

                    if not _do_reserve(series_revision.changeset.indexer, issue,
                                    'issue', changeset=series_revision.changeset):
                        _unreserve(issue)
                        for issue_rev in series_revision.changeset\
                                                        .issuerevisions.all():
                            _unreserve(issue_rev.issue)
                        return show_error_with_return(request, 'Error while'
                        ' reserving issues.', series_revision.changeset)
                for issue_revision in series_revision.changeset.issuerevisions.all():
                    if issue_revision.brand:
                        new_brand = publisher.active_brands()\
                          .filter(name=issue_revision.brand.name)
                        if new_brand.count() == 1:
                            issue_revision.brand = new_brand[0]
                        else:
                            issue_revision.brand = None
                    if issue_revision.indicia_publisher:
                        new_indicia_publisher = publisher.active_indicia_publishers()\
                          .filter(name=issue_revision.indicia_publisher.name)
                        if new_indicia_publisher.count() == 1:
                            issue_revision.indicia_publisher = \
                              new_indicia_publisher[0]
                        else:
                            issue_revision.indicia_publisher = None
                            issue_revision.no_indicia_publisher = False
                    issue_revision.save()
            series_revision.publisher = publisher
            series_revision.imprint = None
            series_revision.save()
            return submit(request, series_revision.changeset.id)

@permission_required('gcd.can_reserve')
def move_issue(request, issue_revision_id, series_id):
    """ move issue to series """
    issue_revision = get_object_or_404(IssueRevision, id=issue_revision_id,
                                       deleted=False)
    if request.user != issue_revision.changeset.indexer:
        return render_error(request,
          'Only the reservation holder may move issues.')

    if series_id == '0':
        if 'series_id' in request.GET:
            try:
                series_id = int(request.GET['series_id'])
            except ValueError:
                return render_error(request,
                                    'Series id must be an integer number.',
                                    redirect=False)
        else:
            return render_error(request,
                                'No series id given.',
                                redirect=False)
    series = Series.objects.filter(id=series_id, deleted=False)
    if not series:
        return render_error(request, 'No series with id %s.' \
                            % series_id, redirect=False)
    series = series[0]

    if request.method != 'POST':
        header_text = "Do you want to move %s to %s ?" % \
          (issue_revision.issue.full_name(), series.full_name())
        url = urlresolvers.reverse('move_issue',
                                   kwargs={'issue_revision_id': issue_revision_id,
                                           'series_id': series_id})
        cancel_button = "Cancel"
        confirm_button = "move of issue %s to series %s" % (issue_revision.issue,
                                                            series)
        return render_to_response('oi/edit/confirm.html',
                                {
                                    'type': 'Issue Move',
                                    'header_text': header_text,
                                    'url': url,
                                    'cancel_button': cancel_button,
                                    'confirm_button': confirm_button,
                                },
                                context_instance=RequestContext(request))
    else:
        if 'cancel' not in request.POST:
            if issue_revision.series.publisher != series.publisher:
                if issue_revision.brand:
                    new_brand = series.publisher.active_brands()\
                        .filter(name=issue_revision.brand.name)
                    if new_brand.count() == 1:
                        issue_revision.brand = new_brand[0]
                    else:
                        issue_revision.brand = None
                if issue_revision.indicia_publisher:
                    new_indicia_publisher = series.publisher\
                                                  .active_indicia_publishers()\
                        .filter(name=issue_revision.indicia_publisher.name)
                    if new_indicia_publisher.count() == 1:
                        issue_revision.indicia_publisher = \
                            new_indicia_publisher[0]
                    else:
                        issue_revision.indicia_publisher = None
                        issue_revision.no_indicia_publisher = False
            issue_revision.series = series
            issue_revision.save()
        return HttpResponseRedirect(urlresolvers.reverse('edit',
            kwargs={'id': issue_revision.changeset.id}))

@permission_required('gcd.can_reserve')
def move_story_revision(request, id):
    """ move story revision between two issue revisions """
    story = get_object_or_404(StoryRevision, id=id)
    if request.user != story.changeset.indexer:
        return render_error(request,
          'Only the reservation holder may move stories.')

    if story.changeset.issuerevisions.count() != 2:
        return render_error(request,
          'Stories can only be moved between two issues.')

    if request.method != 'POST':
        return _cant_get(request)

    new_issue = story.changeset.issuerevisions.exclude(issue=story.issue).get()
    story.issue = new_issue.issue
    story.sequence_number = new_issue.next_sequence_number()
    story.save()
    old_issue = story.changeset.issuerevisions.exclude(id=new_issue.id).get()

    _reorder_children(request, old_issue, old_issue.active_stories(),
                      'sequence_number', old_issue.active_stories(),
                      commit=True, unique=False)

    return HttpResponseRedirect(urlresolvers.reverse('edit',
      kwargs={ 'id': story.changeset.id }))

@permission_required('gcd.can_reserve')
def move_cover(request, id, cover_id=None):
    """ move cover between two issue revisions """
    changeset = get_object_or_404(Changeset, id=id)
    if request.user != changeset.indexer:
        return render_error(request,
          'Only the reservation holder may move covers in a changeset.')

    if changeset.issuerevisions.count() != 2:
        return render_error(request,
          'Covers can only be moved between two issues.')

    if request.method != 'POST':
        covers = []
        for revision in changeset.issuerevisions.all():
            if revision.issue and revision.issue.has_covers():
                for image in get_image_tags_per_issue(revision.issue,
                  "current covers", ZOOM_MEDIUM, as_list=True):
                  image.append(revision)
                  covers.append(image)
        return render_to_response(
          'oi/edit/move_covers.html',
          {
              'changeset': changeset,
              'covers': covers,
              'table_width': UPLOAD_WIDTH
          },
          context_instance=RequestContext(request)
          )

    cover = get_object_or_404(Cover, id=cover_id)
    issue = changeset.issuerevisions.filter(issue=cover.issue)
    if not issue:
        return render_error(request,
          'Cover does not belong to an issue of this changeset.')

    if _is_reservable('cover', cover_id) == 0:
        return render_error(request,
            u'Cannot move the cover as it is already reserved.')

    # create cover revision
    revision = CoverRevision.objects.clone_revision(cover, changeset=changeset)

    return HttpResponseRedirect(urlresolvers.reverse('edit',
      kwargs={ 'id': changeset.id }))

@permission_required('gcd.can_reserve')
def undo_move_cover(request, id, cover_id):
    changeset = get_object_or_404(Changeset, id=id)
    if request.user != changeset.indexer:
        return render_error(request,
          'Only the reservation holder may undo cover moves in a changeset.')

    if request.method != 'POST':
        return _cant_get(request)

    cover_revision = get_object_or_404(CoverRevision, id=cover_id, changeset=changeset)
    cover_revision.cover.reserved=False
    cover_revision.cover.save()
    cover_revision.delete()

    return HttpResponseRedirect(urlresolvers.reverse('edit',
      kwargs={ 'id': changeset.id }))

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
                        ' entered was removed.' % show_revision_short(story, 
                                                                markup=False)
        comment.revision_id = None
        comment.save()
    elif story.changeset.approver:
        # changeset already was submitted once since it has an approver
        # TODO not quite sure if we actually should add this comment
        story.changeset.comments.create(commenter=story.changeset.indexer,
                          text='The StoryRevision "%s" was removed.'\
                            % show_revision_short(story, markup=False),
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
    Handle the ongoing reservation, process the request and form and
    return with error or success message as appropriate.
    """
    if request.method != 'POST':
        return _cant_get(request)

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

    # TODO no need for the form, since different workflow as originally intended
    form = OngoingReservationForm()
    if request.method == 'POST':
        form = OngoingReservationForm(request.POST)
        if form.is_valid():
            reservation = form.save(commit=False)
            reservation.indexer = request.user
            reservation.save()
            return HttpResponseRedirect(urlresolvers.reverse(
              'apps.gcd.views.details.series',
               kwargs={ 'series_id': reservation.series.id }))
        else:
            return render_error(request, u'Something went wrong while reserving'
              ' the series. Please contact us if this error persists.')

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
    variant_counts = {}

    try:
        for issue in series.active_issues():
            number = int(issue.number)
            if number in reorder_list:
                if issue.variant_of:
                    if number in variant_counts:
                        variant_counts[number] += 1
                    else:
                        variant_counts[number] = 1
                    # there won't be more than 9999 variants...
                    number = float("%d.%04d" % (number, variant_counts[number]))
                else:
                    return render_error(request,
                      "Cannot sort by issue with duplicate issue numbers: %i" \
                      % number,
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
        kwargs['state__in'] = (states.PENDING, states.DISCUSSED,
                               states.REVIEWING)
    if 'reviews' == queue_name:
        kwargs['approver'] = request.user
        kwargs['state__in'] = (states.OPEN, states.DISCUSSED,
                               states.REVIEWING)
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
    issues = changes.filter(change_type__in=[CTYPES['issue'],
                                             CTYPES['variant_add'],
                                             CTYPES['two_issues']])
    issue_bulks = changes.filter(change_type=CTYPES['issue_bulk'])
    covers = changes.filter(change_type=CTYPES['cover'])
    countries=dict(Country.objects.values_list('id','code'))
    
    response = render_to_response(
      'oi/queues/%s.html' % queue_name,
      {
        'queue_name': queue_name,
        'indexer': request.user,
        'states': states,
        'countries': countries,
        'data': [
          {
            'object_name': 'Publishers',
            'object_type': 'publisher',
            'changesets': publishers.order_by('modified', 'id')\
              .annotate(country=Max('publisherrevisions__country__id')),
          },
          {
            'object_name': 'Indicia Publishers',
            'object_type': 'indicia_publisher',
            'changesets': indicia_publishers.order_by('modified', 'id')\
              .annotate(country=Max('indiciapublisherrevisions__country__id')),
          },
          {
            'object_name': 'Brands',
            'object_type': 'brands',
            'changesets': brands.order_by('modified', 'id')\
              .annotate(country=Max('brandrevisions__parent__country__id')),
          },
          {
            'object_name': 'Series',
            'object_type': 'series',
            'changesets': series.order_by('modified', 'id')\
              .annotate(country=Max('seriesrevisions__country__id')),
          },
          {
            'object_name': 'Issue Skeletons',
            'object_type': 'issue',
            'changesets': issue_adds.order_by('modified', 'id')\
              .annotate(country=Max('issuerevisions__series__country__id')),
          },
          {
            'object_name': 'Issue Bulk Changes',
            'object_type': 'issue',
            'changesets': issue_bulks.order_by('state', 'modified', 'id')\
              .annotate(country=Max('issuerevisions__series__country__id')),
          },
          {
            'object_name': 'Issues',
            'object_type': 'issue',
            'changesets': issues.order_by('state', 'modified', 'id')\
              .annotate(country=Max('issuerevisions__series__country__id')),
          },
          {
            'object_name': 'Covers',
            'object_type': 'cover',
            'changesets': covers.order_by('state', 'modified', 'id')\
              .annotate(country=Max('coverrevisions__issue__series__country__id')),
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
      state__in=(states.PENDING, states.DISCUSSED, states.REVIEWING),
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
                                   CTYPES['issue_bulk'], CTYPES['variant_add'],
                                   CTYPES['two_issues']]:
        revision = changeset.issuerevisions.all()[0]
    else:
        # never reached at the moment
        raise NotImplementedError

    model_name = revision.source_name
    if model_name == 'cover':
        return cover_compare(request, changeset, revision)

    revision.compare_changes()

    if changeset.change_type == CTYPES['issue_add']:
        template = 'oi/edit/compare_issue_skeletons.html'
    elif changeset.change_type == CTYPES['issue_bulk']:
        template = 'oi/edit/compare_bulk_issue.html'
    else:
        template = 'oi/edit/compare.html'

    prev_rev = revision.previous()
    post_rev = revision.posterior()
    field_list = revision.field_list()
    # eliminate fields that shouldn't appear in the compare
    if model_name == 'series':
        if not revision.imprint and \
          (prev_rev is None or prev_rev.imprint is None):
            field_list.remove('imprint')
        if not (revision.publication_notes or prev_rev and \
          prev_rev.publication_notes):
            field_list.remove('publication_notes')
    elif model_name == 'publisher':
        field_list.remove('is_master')
        field_list.remove('parent')
    elif model_name in ['brand', 'indicia_publisher']:
        field_list.remove('parent')
    elif model_name == 'issue':
        if changeset.change_type == CTYPES['issue_bulk'] or \
          changeset.change_type == CTYPES['issue_add'] and \
          changeset.issuerevisions.count() > 1:
            field_list.remove('number')
            field_list.remove('publication_date')
            field_list.remove('key_date')
            field_list.remove('notes')
            field_list.remove('year_on_sale')
            field_list.remove('month_on_sale')
            field_list.remove('day_on_sale')
            field_list.remove('on_sale_date_uncertain')
            if changeset.change_type == CTYPES['issue_bulk']:
                field_list.remove('title')
                field_list.remove('isbn')
                field_list.remove('barcode')
            else:
                field_list.remove('after')

    response = render_to_response(template,
                                  {'changeset': changeset,
                                   'revision': revision,
                                   'prev_rev': prev_rev,
                                   'post_rev': post_rev,
                                   'changeset_type' : model_name.replace('_',' '),
                                   'model_name': model_name,
                                   'states': states,
                                   'field_list': field_list,
                                   'CTYPES': CTYPES},
                                  context_instance=RequestContext(request))
    response['Cache-Control'] = "no-cache, no-store, max-age=0, must-revalidate"
    return response

def get_cover_width(name):
    try:
        source_name = glob.glob(name)[0]
    except:
        if settings.BETA:
            return "'none given'"
        else:
            raise
    im = Image.open(source_name)
    cover_width = im.size[0]
    return cover_width

@login_required
def cover_compare(request, changeset, revision):
    '''
    Compare page for covers.
    - show uploaded cover
    - for replacement show former cover
    - for other active uploads show other existing and active covers
    '''
    if revision.deleted or revision.cover and revision.cover.deleted==True:
        cover_tag = get_image_tag(revision.cover, "deleted cover", ZOOM_LARGE)
    else:
        cover_tag = get_preview_image_tag(revision, "uploaded cover",
                                          ZOOM_LARGE, request=request)
    kwargs = {'changeset': changeset,
              'revision': revision,
              'cover_tag' : cover_tag,
              'table_width': 5,
              'states': states,
              'settings': settings}
    if revision.is_wraparound:
        kwargs['cover_front_tag'] = get_preview_image_tag(revision, "uploaded cover",
                                                ZOOM_MEDIUM, request=request)
    if revision.is_replacement:
        # change this to use cover.previous() once we are using
        # cover.reserved = True for cover replacements and
        # cleared out cover uploads from editing limbo
        # possible problem scenario:
        # replacement a) is retracted/sent back
        # replacement b) is submitted and approved
        # replacement a) is submitted and approved
        # then the order would be wrong
        old_cover = CoverRevision.objects.filter(cover=revision.cover,
                      created__lt=revision.created,
                      changeset__change_type=CTYPES['cover'],
                      changeset__state=states.APPROVED).order_by('-created')[0]
        kwargs['old_cover'] = old_cover
        kwargs['old_cover_tag'] = get_preview_image_tag(old_cover, "replaced cover",
                                              ZOOM_LARGE, request=request)
        if old_cover.is_wraparound:
            kwargs['old_cover_front_tag'] = get_preview_image_tag(old_cover,
                                    "replaced cover", ZOOM_MEDIUM, request=request)

        if old_cover.created <= settings.NEW_SITE_COVER_CREATION_DATE:
            # uploaded file too old, not stored, we have width 400
            kwargs['old_cover_width'] = 400
        else:
            kwargs['old_cover_width'] = get_cover_width("%s/uploads/%d_%s*" % (
              old_cover.cover.base_dir(),
              old_cover.cover.id,
              old_cover.changeset.created.strftime('%Y%m%d_%H%M%S')))

    if revision.deleted:
        kwargs['old_cover'] = CoverRevision.objects.filter(cover=revision.cover,
                      created__lt=revision.created,
                      changeset__state=states.APPROVED).order_by('-created')[0]

    if revision.changeset.state in states.ACTIVE:
        if revision.issue.has_covers() or revision.issue.variant_covers() or \
          (revision.issue.variant_of and revision.issue.variant_of.has_covers()):
            # no issuesrevision, so no variant upload, but covers exist for issue
            if revision.issue.has_covers() and not \
              revision.changeset.issuerevisions.count():
                kwargs['additional'] = True
            current_covers = []
            current_cover_set = revision.issue.active_covers() \
              | revision.issue.variant_covers()
            if revision.is_replacement or revision.deleted:
                current_cover_set = current_cover_set.exclude(id=revision.cover.id)
            for cover in current_cover_set:
                current_covers.append([cover, get_image_tag(cover,
                                       "current cover", ZOOM_MEDIUM)])
            kwargs['current_covers'] = current_covers
        cover_revisions = CoverRevision.objects.filter(issue=revision.issue) | \
          CoverRevision.objects.filter(issue=revision.issue.variant_of) | \
          CoverRevision.objects.filter(issue__in=revision.issue.variant_set.all())
        cover_revisions = cover_revisions.exclude(id=revision.id)\
                                         .filter(cover=None)\
                                         .filter(changeset__state__in=states.ACTIVE) \
                                         .order_by('created')
        if len(cover_revisions):
            pending_covers = []
            for cover in cover_revisions:
                pending_covers.append([cover, get_preview_image_tag(cover,
                                       "pending cover", ZOOM_MEDIUM)])
            kwargs['pending_covers'] = pending_covers
        kwargs['pending_variant_adds'] = Changeset.objects\
          .filter(issuerevisions__variant_of=revision.issue,
                  #state__in=states.ACTIVE,
                  state__in=[states.PENDING,states.REVIEWING],
                  change_type__in=[CTYPES['issue_add'],
                                   CTYPES['variant_add']])
        # TODO This doesn't include the case of a variant with a
        # deleted cover scan.
        kwargs['variants_without_covers'] = revision.issue.variant_set\
                                                    .filter(cover=None)

        if revision.deleted == False:
            kwargs['cover_width'] = get_cover_width(revision.base_dir() + \
                                          str(revision.id) + '*')
    else:
        if revision.created <= settings.NEW_SITE_COVER_CREATION_DATE:
            # uploaded file too old, not stored, we have width 400
            kwargs['cover_width'] = 400
        elif revision.deleted == False:
            if revision.changeset.state == states.DISCARDED:
                kwargs['cover_width'] = get_cover_width(revision.base_dir() + \
                                              str(revision.id) + '*')
            else:
                kwargs['cover_width'] = get_cover_width("%s/uploads/%d_%s*" % (
                  revision.cover.base_dir(),
                  revision.cover.id,
                  revision.changeset.created.strftime('%Y%m%d_%H%M%S')))

    response = render_to_response('oi/edit/compare_cover.html',
                                  kwargs,
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
    return render_error(request,
      u'No preview for "%s" revisions.' % model_name)

##############################################################################
# Cache and select objects
##############################################################################

def store_select_data(request, select_key, data):
    if not select_key:
        salt = hashlib.sha1(str(random())).hexdigest()[:5]
        select_key = hashlib.sha1(salt + unicode(request.user)).hexdigest()
    for item in data:
        request.session['%s_%s' % (select_key, item)] = data[item]
    request.session['%s_items' % select_key] = data.keys() 
    return select_key

def get_select_data(request, select_key):
    keys = request.session['%s_items' % select_key]
    data = {}
    for item in keys:
        data[item] = request.session['%s_%s' % (select_key, item)]
    return data

def get_select_forms(request, initial, data, series=False, issue=False, story=False):
    if issue or story:
        cached_issue = get_cached_issue(request)
    else:
        cached_issue = None
    if story:
        cached_story = get_cached_story(request)
        cached_cover = get_cached_cover(request)
    else:
        cached_story = None
        cached_cover = None
    
    if data:
        search_form = get_select_search_form(series, issue, story)(data)
    else:
        search_form = get_select_search_form(series, issue, story)(initial=initial)

    cache_form = get_select_cache_form(cached_issue=cached_issue,
        cached_story=cached_story, cached_cover=cached_cover)()

    return search_form, cache_form

@permission_required('gcd.can_reserve')
def process_select_search(request, select_key):
    try:
        data = get_select_data(request, select_key)
    except KeyError:
        return _cant_get(request)
    series = data.get('series', False)
    issue =  data.get('issue', False)
    story =  data.get('story', False)    
    
    search_form = get_select_search_form(series=series, issue=issue, story=story)(request.GET)
    if not search_form.is_valid():
        return HttpResponseRedirect(urlresolvers.reverse('select_object',
                                      kwargs={'select_key': select_key}) \
                                    + '?' + request.META['QUERY_STRING'])
    cd = search_form.cleaned_data

    if 'search_story' in request.GET or 'search_cover' in request.GET:
        search = Story.objects.filter(issue__number=cd['number'], deleted=False,
                    issue__series__name__icontains=cd['series'],
                    issue__series__publisher__name__icontains=cd['publisher'])
        publisher = cd['publisher'] if cd['publisher'] else '?'
        if cd['year']:
            search = search.filter(issue__series__year_began=cd['year'])
            heading = '%s (%s, %d series) #%s' % (cd['series'],
                                                  publisher,
                                                  cd['year'],
                                                  cd['number'])
        else:
            heading = '%s (%s, ? series) #%s' % (cd['series'], publisher, 
                                       cd['number'])
        if cd['sequence_number']:
            search = search.filter(sequence_number=cd['sequence_number'])
            heading += ', seq.# ' + str(cd['sequence_number'])
        if 'search_cover' in request.GET:
                # ? make StoryType.objects.get(name='cover').id a CONSTANT ?
            search = search.filter(type=StoryType.objects.get(name='cover'))
            base_name = 'cover'
            plural_suffix = 's'
        else:
            base_name = 'stor'
            plural_suffix = 'y,ies'
        template='gcd/search/content_list.html'
        heading = 'Search for: ' + heading
        search = search.order_by("issue__series__name",
                                 "issue__series__year_began",
                                 "issue__key_date",
                                 "sequence_number")
    elif 'search_issue' in request.GET:
        search = Issue.objects.filter(number=cd['number'], deleted=False,
                    series__name__icontains=cd['series'],
                    series__publisher__name__icontains=cd['publisher'])
        publisher = cd['publisher'] if cd['publisher'] else '?'
        if cd['year']:
            search = search.filter(series__year_began=cd['year'])
            heading = '%s (%s, %d series) #%s' % (cd['series'], publisher,
                                                  cd['year'], cd['number'])
        else:
            heading = '%s (%s, ? series) #%s' % (cd['series'], publisher,
                                                 cd['number'])
        heading = 'Issue search for: ' + heading
        template='gcd/search/issue_list.html'
        base_name = 'issue'
        plural_suffix = 's'
        search = search.order_by("series__name", "series__year_began",
                                 "key_date")
        
    context = { 'item_name': base_name,
        'plural_suffix': plural_suffix,
        'items' : search,
        'heading' : heading,
        'select_key': select_key,
        'query_string': request.META['QUERY_STRING'],
        'publisher': cd['publisher'] if cd['publisher'] else '',
        'series': cd['series'] if cd['series'] else '',
        'year': cd['year'] if cd['year'] else '',
        'number': cd['number'] if cd['number'] else ''
    }
    return paginate_response(request, search, template, context)

@permission_required('gcd.can_reserve')
def select_object(request, select_key):
    try:
        data = get_select_data(request, select_key)
    except KeyError:
        return _cant_get(request)
    if request.method == 'GET':
        if 'refine_search' in request.GET or 'search_issue' in request.GET:
            request_data = request.GET
        else:
            request_data = None
        initial = data.get('initial', {})
        initial['select_key'] = select_key
        series = data.get('series', False)
        issue =  data.get('issue', False)
        story =  data.get('story', False)
        search_form, cache_form = get_select_forms(request, 
                                    initial, request_data, 
                                    series=series, issue=issue, story=story)
        return render_to_response('oi/edit/select_object.html',
        {
            'heading': data['heading'],
            'select_key': select_key,
            'cache_form': cache_form,
            'search_form': search_form,
            'series': series,
            'issue': issue,
            'story': story,
            'target': data['target']
        },
        context_instance=RequestContext(request))
    
    if 'cancel' in request.POST: 
        return data['cancel']
    elif 'select_object' in request.POST:
        try:
            choice = request.POST['object_choice']
            object_type, selected_id = choice.split('_')
            if object_type == 'cover':
                object_type = 'story'
        except MultiValueDictKeyError:
            return render_error(request,
                                'You did not select a cached object. '
                                'Please use the back button to return.',
                                redirect=False)
    elif 'search_select' in request.POST:
        choice = request.POST['object_choice']
        object_type, selected_id = choice.split('_')
    elif 'entered_issue_id' in request.POST:
        object_type = 'issue'
        try:
            selected_id = int(request.POST['entered_issue_id'])
        except ValueError:
            return render_error(request,
                                'Entered Id must be an integer number. '
                                'Please use the back button to return.',
                                redirect=False)
    elif 'entered_story_id' in request.POST:
        object_type = 'story'
        try:
            selected_id = int(request.POST['entered_story_id'])
        except ValueError:
            return render_error(request,
                                'Entered Id must be an integer number. '
                                'Please use the back button to return.',
                                redirect=False)
    else:
        raise ValueError
    return data['return'](request, data, object_type, selected_id)

def get_cached_issue(request):
    cached_issue = request.session.get('cached_issue', None)
    if cached_issue:
        try:
            cached_issue = Issue.objects.get(id=cached_issue)
        except Issue.DoesNotExist:
            cached_issue = None
            del request.session['cached_issue']
    return cached_issue


def get_cached_story(request):
    cached_story = request.session.get('cached_story', None)
    if cached_story:
        try:
            cached_story = Story.objects.get(id=cached_story)
        except Story.DoesNotExist:
            cached_story = None
            del request.session['cached_story']
    return cached_story


def get_cached_cover(request):
    cached_cover = request.session.get('cached_cover', None)
    if cached_cover:
        try:
            cached_cover = Story.objects.get(id=cached_cover)
        except Story.DoesNotExist:
            cached_cover = None
            del request.session['cached_cover']
    return cached_cover


@permission_required('gcd.can_reserve')
def cache_content(request, issue_id=None, story_id=None, cover_story_id=None):
    """
    Store an issue_id or story_id in the session.
    Only one of each can be stored at a time.
    """
    if issue_id:
        request.session['cached_issue'] = issue_id
    if story_id:
        request.session['cached_story'] = story_id
    if cover_story_id:
        request.session['cached_cover'] = cover_story_id
    return HttpResponseRedirect(request.META['HTTP_REFERER'])

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
def download(request):

    if request.method == 'POST':
        form = DownloadForm(request.POST)
        if form.is_valid():
            cd = form.cleaned_data

            # Note that the submit input is never present in the cleaned data.
            file = settings.MYSQL_DUMP
            if ('postgres' in request.POST):
                file = settings.POSTGRES_DUMP
            path = os.path.join(settings.MEDIA_ROOT, settings.DUMP_DIR, file)

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

    m_path = os.path.join(settings.MEDIA_ROOT, settings.DUMP_DIR,
                          settings.MYSQL_DUMP)
    p_path = os.path.join(settings.MEDIA_ROOT, settings.DUMP_DIR,
                          settings.POSTGRES_DUMP)

    # Use a list of tuples because we want the MySQL dump (our primary format)
    # to be first.
    timestamps = []
    for dump_info in (('MySQL', m_path), ('PostgreSQL-compatible', p_path)):
        try:
            timestamps.append(
              (dump_info[0],
               datetime.utcfromtimestamp(os.stat(dump_info[1])[stat.ST_MTIME])))
        except OSError, ose:
            if ose.errno == errno.ENOENT:
                timestamps.append((dump_info[0], 'never'))
            else:
                raise

    return render_to_response('oi/download.html',
      {
        'method': request.method,
        'timestamps': timestamps,
        'form': form,
      },
      context_instance=RequestContext(request))

