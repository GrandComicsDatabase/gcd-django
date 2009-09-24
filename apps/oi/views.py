import re

from django.core import urlresolvers
from django.http import HttpResponseRedirect
from django.template import RequestContext
from django.shortcuts import render_to_response, get_object_or_404
from django.core.exceptions import *

from django.contrib.auth.views import login
from django.contrib.auth.decorators import login_required, permission_required

from apps.gcd.models import *
from apps.oi.models import *
from apps.oi.forms import *

REVISION_CLASSES = {
    'publisher': PublisherRevision,
    'series': SeriesRevision,
}

DISPLAY_CLASSES = {
    'publisher': Publisher,
    'series': Series,
}

FORM_CLASSES = {
    'publisher': PublisherRevisionForm,
}

##############################################################################
# Helper functions
##############################################################################

# TODO: Raising an exception is not the right way to handle user checks.
# This function needs to be replaced with something else that properly
# returns an evaluate error template.
def _check_user(actual, expected=None, role=None):
    """
    Assert several conditions on the user who wants to perform an action.
    We may want to do something specific later to produce a more friendly
    error result.

    This is in addition to the basic @permission_required check.
    """
    if not actual.indexer.active:
        raise ValueError, 'User "%s" is inactive.' % actual

    if expected is not None and actual != expected:
        raise ValueError, \
             'User mismatch, got "%s" for role "%s", expected "%s"' % \
             (actual, role, expected)

def _cant_get(request):
    return render_to_response(
      'gcd/error.html',
      { 'error_text':
        'This page may only be accessed through the proper form' },
      context_instance=RequestContext(request))

##############################################################################
# Generic view functions
##############################################################################

@permission_required('oi.can_reserve')
def reserve(request, id, model_name):
    target_view = 'edit_%s' % model_name

    display_obj = get_object_or_404(DISPLAY_CLASSES[model_name], id=id)
    if request.method != 'POST':
        return _cant_get(request)

    revision = REVISION_CLASSES[model_name].objects.clone_revision(
      display_obj, indexer=request.user)
    return HttpResponseRedirect(urlresolvers.reverse(target_view,
                                             kwargs={ 'id': revision.id }))

@permission_required('oi.can_reserve')
def direct_edit(request, id, model_name):
    display_obj = get_object_or_404(DISPLAY_CLASSES[model_name], id=id)
    if display_obj.revisions.count() > 0:
        return HttpResponseRedirect(
          urlresolvers.reverse('edit_%s' % model_name,
                               kwargs={
                                 'id': display_obj.revisions.all()[0].id,
                               }))
    return render_to_response(
      'gcd/error.html',
      { 'error_text': 'Please reserve this %s in order to edit it.' },
      context_instance=RequestContext(request))

@permission_required('oi.can_reserve')
def edit(request, id, model_name):
    edit_template = 'oi/edit/%s.html' % model_name
    revision = get_object_or_404(REVISION_CLASSES[model_name], id=id)

    form = FORM_CLASSES[model_name](instance=revision)
    return render_to_response(edit_template,
                             {
                               'revision': revision,
                               'form': form,
                               'states': states,
                              },
                              context_instance=RequestContext(request))

@permission_required('oi.can_reserve')
def submit(request, id, model_name):
    """
    Submit a change and go to the reservations queue.
    """
    if request.method != 'POST':
        return _cant_get(request)

    form = FORM_CLASSES[model_name](
      request.POST,
      instance=REVISION_CLASSES[model_name].objects.get(id=id))

    if form.is_valid():
        revision = form.save()
        revision.submit(notes=form.cleaned_data['comments'])
        return HttpResponseRedirect(
          urlresolvers.reverse('apps.oi.views.show_reserved'))
    else:
        revision = get_object_or_404(REVISION_CLASSES[model_name], id=id)
        return render_to_response('oi/edit/%s.html' % model_name,
                                  {
                                    'revision': revision,
                                    'form': form,
                                    'states': states
                                  },
                                  context_instance=RequestContext(request))
        

# TODO: discard has complicated permissions checking as in theory
# an editor should be able to discard a change under review, and
# an indexer should be able to discard their own open change.
# But indexers should not be allowed to discard changes other than their own.
# _check_user can't handle this but it's getting replaced anyway.
@permission_required('oi.can_reserve')
def discard(request, id, model_name):
    """
    Discard a change and go to the reservations queue.
    """
    if request.method != 'POST':
        return _cant_get(request)
    revision = get_object_or_404(REVISION_CLASSES[model_name], id=id)

    # TODO: If an editor is discarding, notes are required.
    revision.discard(discarder=request.user, notes=request.POST['comments'])
    return HttpResponseRedirect(
      urlresolvers.reverse('apps.oi.views.show_reserved'))

@permission_required('oi.can_approve')
def examine(request, id, model_name):
    """
    Move a change into your approvals queue, and go to the queue.
    """
    if request.method != 'POST':
        return _cant_get(request)

    revision = get_object_or_404(REVISION_CLASSES[model_name], id=id)
    revision.examine(approver=request.user, notes=request.POST['comments'])

    return HttpResponseRedirect(
      urlresolvers.reverse('apps.oi.views.show_reviews'))

@permission_required('oi.can_approve')
def release(request, id, model_name):
    """
    Move a change out of your approvals queue, and go back to your queue.
    """
    if request.method != 'POST':
        return _cant_get(request)

    revision = get_object_or_404(REVISION_CLASSES[model_name], id=id)
    _check_user(request.user, revision.indexer, None)

    revision.release() # get notes from POST data

    return HttpResponseRedirect(
      urlresolvers.reverse('apps.oi.views.show_reviews'))

@permission_required('oi.can_approve')
def approve(request, id, model_name):
    """
    Approve a change and return to your approvals queue.
    """
    if request.method != 'POST':
        return _cant_get(request)

    revision = get_object_or_404(REVISION_CLASSES[model_name], id=id)
    _check_user(request.user, revision.approver, None)

    revision.approve(notes=request.POST['comments'])

    return HttpResponseRedirect(
      urlresolvers.reverse('apps.oi.views.show_reviews'))

@permission_required('oi.can_approve')
def disapprove(request, id, model_name):
    """
    Disapprove a change and return to your approvals queue.
    """
    if request.method != 'POST':
        return _cant_get(request)

    revision = get_object_or_404(REVISION_CLASSES[model_name], id=id)
    _check_user(request.user, revision.approver, None)

    if not request.POST['comments']:
        return render_to_response('gcd/error.html',
          {'error_message': 'You must explain why you are disapproving this '
                            'change.  Please press the "back" button and use '
                            'the comments field for the explanation.' },
          context_instance=RequestContext(request))

    revision.disapprove(notes=request.POST['comments'])

    return HttpResponseRedirect(
      urlresolvers.reverse('apps.oi.views.show_reviews'))

@permission_required('oi.can_reserve')
def delete(request, id, model_name):
    """
    Delete and submit a change, returning to the reservations queue.
    """
    if request.method != 'POST':
        return _cant_get(request)

    revision = get_object_or_404(REVISION_CLASSES[model_name], id=id)
    revision.mark_deleted()

    return HttpResponseRedirect(
      urlresolvers.reverse('apps.oi.views.show_reserved'))

@permission_required('oi.can_reserve')
def process(request, id, model_name):
    """
    Entry point for forms with multiple actions.

    This handles saving (with no state change) directly, and routes
    the request to other views for all other cases.
    """
    if request.method != 'POST':
        return _cant_get(request)

    action = request.POST['submit']
    if re.match(r'save', action, re.I):
        form = FORM_CLASSES[model_name](
        request.POST,
        instance=REVISION_CLASSES[model_name].objects.get(id=id))

        if form.is_valid():
            revision = form.save(commit=False)
            revision.comments.create(commenter=request.user,
                                     text=form.cleaned_data['comments'],
                                     old_state=revision.state,
                                     new_state=revision.state)
            revision.save()
            if hasattr(revision, 'save_m2m'):
                revision.save_m2m()
            return HttpResponseRedirect(
              urlresolvers.reverse('edit_%s' % model_name, kwargs={ 'id': id }))
        else:
            revision = get_object_or_404(REVISION_CLASSES[model_name], id=id)
            return render_to_response('oi/edit/%s.html' % model_name,
                                      {
                                        'revision': revision,
                                        'form': form,
                                        'states': states
                                      },
                                      context_instance=RequestContext(request))

    if re.match(r'delete', action, re.I):
        return delete(request, id, model_name)

    if re.match(r'submit', action, re.I):
        return submit(request, id, model_name)

    if re.match(r'retract', action, re.I):
        return retract(request, id, model_name)

    if re.match(r'discard|cancel', action, re.I):
        return discard(request, id, model_name)

    if re.match(r'examine', action, re.I):
        return examine(request, id, model_name)

    if re.match(r'release', action, re.I):
        return release(request, id, model_name)

    if re.match(r'approve', action, re.I):
        return approve(request, id, model_name)

    if re.match(r'disapprove', action, re.I):
        return disapprove(request, id, model_name)

    raise Exception, "Unknown action!"

##############################################################################
# Queue Views
##############################################################################

@permission_required('oi.can_reserve')
def show_reserved(request):
    return render_to_response(
      'oi/queues/reserved.html',
      {
        'indexer': request.user,
        'publishers': PublisherRevision.objects.filter(
          indexer=request.user,
          state=states.OPEN,
          is_master=True).order_by('modified'),
        'imprints': PublisherRevision.objects.filter(
          indexer=request.user,
          state=states.OPEN,
          parent__isnull=False).order_by('modified'),
      },
      context_instance=RequestContext(request)
    )

@permission_required('oi.can_approve')
def show_pending(request):
    return render_to_response(
      'oi/queues/pending.html',
      {
        'publishers': PublisherRevision.objects.filter(
          state=states.PENDING,
          is_master=True).order_by('modified'),
        'imprints': PublisherRevision.objects.filter(
          state=states.PENDING,
          parent__isnull=False).order_by('modified'),
      },
      context_instance=RequestContext(request)
    )

@permission_required('oi.can_approve')
def show_reviews(request):
    return render_to_response(
      'oi/queues/reviews.html',
      {
        'approver': request.user,
        'publishers': PublisherRevision.objects.filter(
          approver=request.user,
          state=states.REVIEWING,
          is_master=True).order_by('modified'),
        'imprints': PublisherRevision.objects.filter(
          approver=request.user,
          state=states.REVIEWING,
          parent__isnull=False).order_by('modified'),
      },
      context_instance=RequestContext(request)
    )

