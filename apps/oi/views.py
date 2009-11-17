import re

from django.core import urlresolvers
from django.conf import settings
from django.http import HttpResponseRedirect
from django.template import RequestContext
from django.shortcuts import render_to_response, get_object_or_404
from django.core.exceptions import *

from django.contrib.auth.views import login
from django.contrib.auth.decorators import login_required, permission_required

from apps.gcd.models import *
from apps.gcd.views import render_error, paginate_response
from apps.gcd.views.details import show_series, show_issue
from apps.oi.models import *
from apps.oi.forms import *

REVISION_CLASSES = {
    'publisher': PublisherRevision,
    'series': SeriesRevision,
    'issue': IssueRevision,
    'story': StoryRevision,
}

DISPLAY_CLASSES = {
    'publisher': Publisher,
    'series': Series,
    'issue': Issue,
    'story': Story,
}

FORM_CLASSES = {
    'publisher': PublisherRevisionForm,
    'series': SeriesRevisionForm,
    'issue': IssueRevisionForm,
    'story': StoryRevisionForm,
}

##############################################################################
# Helper functions
##############################################################################

def _cant_get(request):
    redirect = False
    if request.method == "POST":
        redirect = True
    return render_error(request,
      'This page may only be accessed through the proper form',
       redirect=redirect)

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

    revision = REVISION_CLASSES[model_name].objects.clone_revision(
      display_obj, indexer=request.user)
    if model_name == 'issue':
        for story in revision.issue.story_set.all():
           StoryRevision.objects.clone_revision(story=story,
                                                indexer=request.user,
                                                issue_revision=revision)

    return HttpResponseRedirect(urlresolvers.reverse('edit_revision',
      kwargs={ 'model_name': model_name, 'id': revision.id }))

# TODO: What is the point of this method?  I can't remember...
@permission_required('gcd.can_reserve')
def direct_edit(request, id, model_name):
    # Since I can't remember what this is, let's see if I can find out:
    raise Exception, "Henry can't remember why this function exists"

    display_obj = get_object_or_404(DISPLAY_CLASSES[model_name], id=id)
    if display_obj.revisions.count() > 0:
        return HttpResponseRedirect(
          urlresolvers.reverse('edit_revision',
                               kwargs={
                                 'model_name': model_name,
                                 'id': display_obj.revisions.all()[0].id,
                               }))
    return render_to_response(
      'gcd/error.html',
      { 'error_text': 'Please reserve this %s in order to edit it.' },
      context_instance=RequestContext(request))

@permission_required('gcd.can_reserve')
def edit(request, id, model_name):
    revision = get_object_or_404(REVISION_CLASSES[model_name], id=id)
    form = FORM_CLASSES[model_name](instance=revision)
    return _display_edit_form(request, revision, model_name, form)

def _display_edit_form(request, revision, model_name, form):
    url = urlresolvers.reverse('process_revision',
                               kwargs={
                                 'model_name': model_name,
                                 'id': revision.id,
                               })
    template = 'oi/edit/%s_form.html' % model_name
    object_name = model_name.capitalize()
    if 'Publisher' == object_name and revision.parent is not None:
        object_name = 'Imprint'

    response= render_to_response('oi/edit/frame.html',
                             {
                               'revision': revision,
                               'object': getattr(revision, model_name),
                               'object_name': object_name,
                               'object_class': model_name,
                               'object_url': url,
                               'object_form_template': template,
                               'form': form,
                               'states': states,
                              },
                              context_instance=RequestContext(request))
    response['Cache-Control'] = "no-cache, no-store, max-age=0, must-revalidate"
    return response

@permission_required('gcd.can_reserve')
def submit(request, id, model_name):
    """
    Submit a change and go to the reservations queue.
    """
    if request.method != 'POST':
        return _cant_get(request)

    revision = get_object_or_404(REVISION_CLASSES[model_name], id=id)
    if (request.user != revision.indexer):
        return render_to_response('gcd/error.html',
          {'error_message': 'A change may only be submitted by its author.'},
          context_instance=RequestContext(request))

    form = FORM_CLASSES[model_name](request.POST, instance=revision)

    if form.is_valid():
        revision = form.save()
        revision.submit(notes=form.cleaned_data['comments'])
        if model_name == 'issue':
            for story_revision in revision.story_revisions.all():
                story_revision.submit()

        return HttpResponseRedirect(
          urlresolvers.reverse('editing'))
    else:
        return _display_edit_form(request, revision, model_name, form)
        

@permission_required('gcd.can_reserve')
def retract(request, id, model_name):
    """
    Retract a pendint change back into your reserved queue.
    """
    if request.method != 'POST':
        return _cant_get(request)
    revision = get_object_or_404(REVISION_CLASSES[model_name], id=id)

    if request.user != revision.indexer:
        return render_to_response('gcd/error.html',
          {'error_message': 'A change may only be retracted by its author.'},
          context_instance=RequestContext(request))
    revision.retract(notes=request.POST['comments'])
    if model_name == 'issue':
        for story_revision in revision.story_revisions.all():
            story_revision.retract()

    return HttpResponseRedirect(
      urlresolvers.reverse('editing'))

@permission_required('gcd.can_reserve')
def discard(request, id, model_name):
    """
    Discard a change and go to the reservations queue.
    """
    if request.method != 'POST':
        return _cant_get(request)
    revision = get_object_or_404(REVISION_CLASSES[model_name], id=id)

    if (request.user != revision.indexer and
        not request.user.has_perm('gcd.can_approve')):
        return render_to_response('gcd/error.html',
          { 'error_message':
            'Only the author or an Editor can discard a change.' },
          context_instance=RequestContext(request))

    if request.user != revision.indexer and not request.POST['comments']:
        return render_to_response('gcd/error.html',
          {'error_message': 'You must explain why you are discarding this '
                            'change.  Please press the "back" button and use '
                            'the comments field for the explanation.' },
          context_instance=RequestContext(request))

    revision.discard(discarder=request.user, notes=request.POST['comments'])
    if model_name == 'issue':
        for story_revision in revision.story_revisions.all():
            story_revision.discard(discarder=request.user)

    return HttpResponseRedirect(
      urlresolvers.reverse('editing'))

@permission_required('gcd.can_approve')
def assign(request, id, model_name):
    """
    Move a change into your approvals queue, and go to the queue.
    """
    if request.method != 'POST':
        return _cant_get(request)

    revision = get_object_or_404(REVISION_CLASSES[model_name], id=id)
    revision.assign(approver=request.user, notes=request.POST['comments'])
    if model_name == 'issue':
        for story_revision in revision.story_revisions.all():
            story_revision.assign(approver=request.user)

    return HttpResponseRedirect(
      urlresolvers.reverse('reviewing'))

@permission_required('gcd.can_approve')
def release(request, id, model_name):
    """
    Move a change out of your approvals queue, and go back to your queue.
    """
    if request.method != 'POST':
        return _cant_get(request)

    revision = get_object_or_404(REVISION_CLASSES[model_name], id=id)
    if request.user != revision.approver:
        return render_to_response('gcd/error.html',
          {'error_message': 'A change may only be released by its approver.'},
          context_instance=RequestContext(request))
        
    revision.release(notes=request.POST['comments'])
    if model_name == 'issue':
        for story_revision in revision.story_revisions.all():
            story_revision.release()

    return HttpResponseRedirect(
      urlresolvers.reverse('reviewing'))

@permission_required('gcd.can_approve')
def approve(request, id, model_name):
    """
    Approve a change and return to your approvals queue.
    """
    if request.method != 'POST':
        return _cant_get(request)

    revision = get_object_or_404(REVISION_CLASSES[model_name], id=id)
    if request.user != revision.approver:
        return render_error(request,
          'A change may only be approved by its approver.')

    revision.approve(notes=request.POST['comments'])
    if model_name == 'issue':
        for story_revision in revision.story_revisions.all():
            story_revision.approve()

    return HttpResponseRedirect(
      urlresolvers.reverse('reviewing'))

@permission_required('gcd.can_approve')
def disapprove(request, id, model_name):
    """
    Disapprove a change and return to your approvals queue.
    """
    if request.method != 'POST':
        return _cant_get(request)

    revision = get_object_or_404(REVISION_CLASSES[model_name], id=id)
    if request.user != revision.approver:
        return render_error(request,
          'A change may only be rejected by its approver.')

    if not request.POST['comments']:
        return render_error(request,
                            'You must explain why you are disapproving this '
                            'change.  Please press the "back" button and use '
                            'the comments field for the explanation.')

    revision.disapprove(notes=request.POST['comments'])
    if model_name == 'issue':
        for story_revision in revision.story_revisions.all():
            story_revision.disapprove()

    return HttpResponseRedirect(
      urlresolvers.reverse('reviewing'))

@permission_required('gcd.can_reserve')
def delete(request, id, model_name):
    """
    Delete and submit a change, returning to the reservations queue.
    """
    if request.method != 'POST':
        return _cant_get(request)

    revision = get_object_or_404(REVISION_CLASSES[model_name], id=id)
    if request.user != revision.indexer:
        return render_to_response('gcd/error.html',
          {'error_message': 'Only the reservation holder may delete a record.'},
          context_instance=RequestContext(request))
    if model_name == 'issue':
        # For now, refuse to delete stories with issues.  TODO: Revisit.
        if revision.story_revisions.count():
            return render_error(request,
              "Cannot delete issue while stories are still attached.")
    revision.mark_deleted()

    return HttpResponseRedirect(
      urlresolvers.reverse('editing'))

@permission_required('gcd.can_reserve')
def process(request, id, model_name):
    """
    Entry point for forms with multiple actions.

    This handles saving (with no state change) directly, and routes
    the request to other views for all other cases.
    """
    if request.method != 'POST':
        return _cant_get(request)

    # Stories go through most state transitions with their issue, so don't
    # allow them to get moved separately here.
    if model_name != 'story':
        # Deleting stories should work, but haven't set up the rest of the
        # necessary code yet so stuff it in here for now.
        if 'delete' in request.POST:
            return delete(request, id, model_name)

        if 'submit' in request.POST:
            return submit(request, id, model_name)

        if 'retract' in request.POST:
            return retract(request, id, model_name)

        if 'discard' in request.POST or 'cancel' in request.POST:
            return discard(request, id, model_name)

        if 'assign' in request.POST:
            return assign(request, id, model_name)

        if 'release' in request.POST:
            return release(request, id, model_name)

        if 'approve' in request.POST:
            return approve(request, id, model_name)

        if 'disapprove' in request.POST:
            return disapprove(request, id, model_name)

    elif 'cancel_return' in request.POST:
        # Story forms can navigate back to issues without saving.
        revision = get_object_or_404(REVISION_CLASSES[model_name], id=id)
        return HttpResponseRedirect(urlresolvers.reverse('edit_revision',
          kwargs={ 'model_name': 'issue', 'id': revision.issue_revision.id }))


    if 'add_comment' in request.POST:
        revision = get_object_or_404(REVISION_CLASSES[model_name], id=id)
        comments = request.POST['comments']
        if comments is not None and comments != '':
            revision.comments.create(commenter=request.user,
                                     text=comments,
                                     old_state=revision.state,
                                     new_state=revision.state)
            # Just add comments, don't touch other fields.
            return HttpResponseRedirect(urlresolvers.reverse(compare,
              kwargs={ 'model_name': model_name, 'id': id }))
        
    if 'save' not in request.POST and 'save_return' not in request.POST and \
       'queue' not in request.POST:
        return render_error(request, 'Unknown action requested!  Please try again. '
          'If this error message persists, please contact an Editor.')

    form = FORM_CLASSES[model_name](request.POST,
      instance=REVISION_CLASSES[model_name].objects.get(id=id))

    if form.is_valid():
        revision = form.save(commit=False)
        comments = form.cleaned_data['comments']
        if comments is not None and comments != '':
            revision.comments.create(commenter=request.user,
                                     text=comments,
                                     old_state=revision.state,
                                     new_state=revision.state)

        revision.save()
        if hasattr(revision, 'save_m2m'):
            revision.save_m2m()
        if 'queue' in request.POST:
            return HttpResponseRedirect(urlresolvers.reverse('editing'))
        if 'save' in request.POST:
            return HttpResponseRedirect(urlresolvers.reverse('edit_revision',
              kwargs={ 'model_name': model_name, 'id': id }))
        if 'save_return' in request.POST:
            return HttpResponseRedirect(urlresolvers.reverse('edit_revision',
              kwargs={ 'model_name': 'issue', 'id': revision.issue_revision.id }))

    else:
        revision = get_object_or_404(REVISION_CLASSES[model_name], id=id)
        return _display_edit_form(request, revision, model_name, form)

##############################################################################
# Adding Items
##############################################################################

@permission_required('gcd.can_reserve')
def add_publisher(request, parent_id=None):
    try:
        parent = None
        if parent_id is not None:
            parent = Publisher.objects.get(id=parent_id, is_master=True)

        if request.method != 'POST':
            form = PublisherRevisionForm()
            return _display_add_publisher_form(request, parent, form)

        form = PublisherRevisionForm(request.POST)
        if not form.is_valid():
            return _display_add_publisher_form(request, parent, form)

        revision = form.save(commit=False)
        revision.save_added_revision(indexer=request.user,
                                     parent=parent,
                                     comments=form.cleaned_data['comments'])

        return HttpResponseRedirect(
          urlresolvers.reverse('edit_publisher', kwargs={ 'id': revision.id }))

    except (Publisher.DoesNotExist, Publisher.MultipleObjectsReturned):
        return render_error(request,
          'Could not find publisher or imprint for id ' + publisher_id)

def _display_add_publisher_form(request, parent, form):
    if parent is not None:
        # Use imprint instead and publisher will be calculated from it.
        object_name = 'Imprint'
        object_url = urlresolvers.reverse('add_imprint',
                                          kwargs={ 'parent_id': parent.id })
    else:
        object_name = 'Publisher'
        object_url = urlresolvers.reverse('add_publisher')

    return render_to_response('oi/edit/add_frame.html',
      {
        'object_name': object_name,
        'object_url': object_url,
        'object_form_template': 'oi/edit/publisher_form.html',
        'form': form,
      },
      context_instance=RequestContext(request))


@permission_required('gcd.can_reserve')
def add_series(request, publisher_id):

    # Process add form if this is a POST.
    try:
        publisher = Publisher.objects.get(id=publisher_id)
        imprint = None
        if publisher.parent is not None:
            imprint = publisher
            publisher = imprint.parent

        if request.method != 'POST':
            form = SeriesRevisionForm()
            return _display_add_series_form(request, publisher, imprint, form)

        form = SeriesRevisionForm(request.POST)
        if not form.is_valid():
            return _display_add_series_form(request, publisher, imprint, form)

        revision = form.save(commit=False)
        revision.save_added_revision(indexer=request.user,
                                     publisher=publisher,
                                     imprint=imprint,
                                     comments=form.cleaned_data['comments'])
        return HttpResponseRedirect(
          urlresolvers.reverse('edit_series', kwargs={ 'id': revision.id }))

    except (Publisher.DoesNotExist, Publisher.MultipleObjectsReturned):
        return render_error(request,
          'Could not find publisher or imprint for id ' + publisher_id)

def _display_add_series_form(request, publisher, imprint, form):
    kwargs = {
        'publisher_id': publisher.id,
    }
    if imprint is not None:
        # Use imprint instead and publisher will be calculated from it.
        kwargs['publisher_id'] = imprint.id

    url = urlresolvers.reverse('add_series', kwargs=kwargs)
    return render_to_response('oi/edit/add_frame.html',
      {
        'object_name': 'Series',
        'object_url': url,
        'object_form_template': 'oi/edit/series_form.html',
        'form': form,
      },
      context_instance=RequestContext(request))

def add_issues(request, series_id):
    return render_error(request, 'Adding issues is not yet implemented.')

##############################################################################
# Ongoing Reservations
##############################################################################

@permission_required('gcd.can_reserve')
def ongoing(request, user_id=None):
    """
    Handle the ongoing reservatin page.  Display on GET.  On POST, process
    the form and re-display with error or success message as appropriate.
    """
    form = OngoingReservationForm()
    message = ''
    if request.method == 'POST':
        post_form = OngoingReservationForm(request.POST)
        if post_form.is_valid():
            reservation = post_form.save(commit=False)
            reservation.indexer = request.user
            reservation.save()
            message = 'Series %s reserved' % post_form.cleaned_data['series']
        else:
            form = post_form

    return render_to_response('oi/edit/ongoing.html',
                              {
                                'form': form,
                                'message': message,
                              },
                              context_instance=RequestContext(request))

##############################################################################
# Queue Views
##############################################################################

@permission_required('gcd.can_reserve')
def show_queue(request, queue_name, state):
    kwargs = {}
    if 'editing' == queue_name:
        kwargs['indexer'] = request.user
        kwargs['state__in'] = (states.OPEN, states.PENDING, states.REVIEWING)
    else:
        kwargs['state'] = state

    if 'reviews' == queue_name:
        kwargs['approver'] = request.user

    publishers = PublisherRevision.objects.filter(is_master=True,
                                                  **kwargs)
    imprints = PublisherRevision.objects.filter(parent__isnull=False,
                                                **kwargs)
    series = SeriesRevision.objects.filter(**kwargs)
    issues = IssueRevision.objects.filter(**kwargs)

    return render_to_response(
      'oi/queues/%s.html' % queue_name,
      {
        'queue_name': queue_name,
        'indexer': request.user,
        'states': states,
        'data': [
          {
            'object_name': 'Publishers',
            'object_type': 'publisher',
            'objects': publishers.order_by('modified'),
          },
          {
            'object_name': 'Imprints',
            'object_type': 'publisher',
            'objects': imprints.order_by('modified'),
          },
          {
            'object_name': 'Series',
            'object_type': 'series',
            'objects': series.order_by('modified'),
          },
          {
            'object_name': 'Issues',
            'object_type': 'issue',
            'objects': issues.order_by('modified'),
          },
        ],
      },
      context_instance=RequestContext(request)
    )

@login_required
def compare(request, id, model_name):
    revision = get_object_or_404(REVISION_CLASSES[model_name], id=id)
    revision.compare_changes()

    template = 'oi/edit/compare_%s.html' % model_name

    response = render_to_response(template,
                                  { 'revision': revision,
                                    'model_name': model_name,
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
    if 'series' == model_name:
        return show_series(request, revision, True)
    if 'issue' == model_name:
        return show_issue(request, revision, True)

