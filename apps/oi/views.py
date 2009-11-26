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
from apps.gcd.views.details import show_indicia_publisher, show_brand, \
                                   show_series, show_issue
from apps.oi.models import *
from apps.oi.forms import *

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

    # TODO: Create changeset, add "Editing." states.UNRESERVED => states.OPEN
    # comments.

    changeset = Changeset(indexer=request.user, state=states.OPEN)
    changeset.save()
    changeset.comments.create(commenter=request.user,
                              text='Editing',
                              old_state=states.UNRESERVED,
                              new_state=changeset.state)

    revision = REVISION_CLASSES[model_name].objects.clone_revision(
      display_obj, changeset=changeset)

    if model_name == 'issue':
        for story in revision.issue.story_set.all():
           StoryRevision.objects.clone_revision(story=story, changeset=changeset)

    return HttpResponseRedirect(urlresolvers.reverse('edit',
                                                     kwargs={ 'id': changeset.id }))

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
    return HttpResponseRedirect(urlresolvers.reverse('editing'))

# TODO: changeset ID or revision ID?
def _save(request, form, changeset_id=None, revision_id=None, model_name=None):
    if form.is_valid():
        revision = form.save(commit=False)
        changeset = revision.changeset
        if 'comments' in form.cleaned_data:
            comments = form.cleaned_data['comments']
            if comments is not None and comments != '':
                changeset.comments.create(commenter=request.user,
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
    Retract a pendint change back into your reserved queue.
    """
    if request.method != 'POST':
        return _cant_get(request)
    changeset = get_object_or_404(Changeset, id=id)

    if request.user != changeset.indexer:
        return render_to_response('gcd/error.html',
          {'error_message': 'A change may only be retracted by its author.'},
          context_instance=RequestContext(request))
    changeset.retract(notes=request.POST['comments'])

    return HttpResponseRedirect(urlresolvers.reverse('editing'))

@permission_required('gcd.can_reserve')
def discard(request, id):
    """
    Discard a change and go to the reservations queue.
    """
    if request.method != 'POST':
        return _cant_get(request)
    changeset = get_object_or_404(Changeset, id=id)

    if (request.user != changeset.indexer and
        not request.user.has_perm('gcd.can_approve')):
        return render_to_response('gcd/error.html',
          { 'error_message':
            'Only the author or an Editor can discard a change.' },
          context_instance=RequestContext(request))

    if request.user != changeset.indexer and not request.POST['comments']:
        return render_to_response('gcd/error.html',
          {'error_message': 'You must explain why you are discarding this '
                            'change.  Please press the "back" button and use '
                            'the comments field for the explanation.' },
          context_instance=RequestContext(request))

    changeset.discard(discarder=request.user, notes=request.POST['comments'])

    return HttpResponseRedirect(urlresolvers.reverse('editing'))

@permission_required('gcd.can_approve')
def assign(request, id):
    """
    Move a change into your approvals queue, and go to the queue.
    """
    if request.method != 'POST':
        return _cant_get(request)

    changeset = get_object_or_404(Changeset, id=id)
    changeset.assign(approver=request.user, notes=request.POST['comments'])

    return HttpResponseRedirect(urlresolvers.reverse('reviewing'))

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

    return HttpResponseRedirect(urlresolvers.reverse('reviewing'))

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

    changeset.approve(notes=request.POST['comments'])

    return HttpResponseRedirect(urlresolvers.reverse('reviewing'))

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

    changeset.disapprove(notes=request.POST['comments'])

    return HttpResponseRedirect(urlresolvers.reverse('reviewing'))

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

    This handles saving (with no state change) directly, and routes
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
        changeset = get_object_or_404(Changeset, id=id)
        comments = request.POST['comments']
        if comments is not None and comments != '':
            changeset.comments.create(commenter=request.user,
                                      text=comments,
                                      old_state=changeset.state,
                                      new_state=changeset.state)
            return HttpResponseRedirect(urlresolvers.reverse(compare,
                                                             kwargs={ 'id': id }))
        
    return render_error(request, 'Unknown action requested!  Please try again. '
      'If this error message persists, please contact an Editor.')

@permission_required('gcd.can_reserve')
def process_revision(request, id, model_name):
    if 'cancel_return' in request.POST:
        revision = get_object_or_404(REVISION_CLASSES[model_name], id=id)
        return HttpResponseRedirect(urlresolvers.reverse('edit',
          kwargs={ 'id': revision.changeset.id }))

    if 'save' in request.POST or 'save_return' in request.POST:
        revision = get_object_or_404(REVISION_CLASSES[model_name], id=id)
        form = get_revision_form(revision)(request.POST, instance=revision)
        return _save(request, form=form, revision_id=id, model_name=model_name)

##############################################################################
# Adding Items
##############################################################################

@permission_required('gcd.can_reserve')
def add_publisher(request):
    if request.method != 'POST':
        form = get_publisher_revision_form()()
        return _display_add_publisher_form(request, form)

    form = get_publisher_revision_form()(request.POST)
    if not form.is_valid():
        return _display_add_publisher_form(request, form)

    changeset = Changeset(indexer=request.user, state=states.OPEN)
    changeset.save()
    changeset.comments.create(commenter=request.user,
                              text=form.cleaned_data['comments'],
                              old_state=states.UNRESERVED,
                              new_state=changeset.state)
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
    try:
        parent = Publisher.objects.get(id=parent_id, is_master=True)

        if request.method != 'POST':
            form = get_indicia_publisher_revision_form()()
            return _display_add_indicia_publisher_form(request, parent, form)

        form = get_indicia_publisher_revision_form()(request.POST)
        if not form.is_valid():
            return _display_add_indicia_publisher_form(request, parent, form)

        changeset = Changeset(indexer=request.user, state=states.OPEN)
        changeset.save()
        changeset.comments.create(commenter=request.user,
                                  text=form.cleaned_data['comments'],
                                  old_state=states.UNRESERVED,
                                  new_state=changeset.state)
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
    try:
        parent = Publisher.objects.get(id=parent_id, is_master=True)

        if request.method != 'POST':
            form = get_brand_revision_form()()
            return _display_add_brand_form(request, parent, form)

        form = get_brand_revision_form()(request.POST)
        if not form.is_valid():
            return _display_add_brand_form(request, parent, form)

        changeset = Changeset(indexer=request.user, state=states.OPEN)
        changeset.save()
        changeset.comments.create(commenter=request.user,
                                  text=form.cleaned_data['comments'],
                                  old_state=states.UNRESERVED,
                                  new_state=changeset.state)
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

    # Process add form if this is a POST.
    try:
        publisher = Publisher.objects.get(id=publisher_id)
        imprint = None
        if publisher.parent is not None:
            return render_error(request, 'Series may no longer be added to '
              'imprints.  Add the series to the master publisher, and then set '
              'the indicia publisher(s) and/or brand(s) at the issue level.')

        if request.method != 'POST':
            form = get_series_revision_form(publisher)()
            return _display_add_series_form(request, publisher, imprint, form)

        form = get_series_revision_form(publisher)(request.POST)
        if not form.is_valid():
            return _display_add_series_form(request, publisher, imprint, form)

        changeset = Changeset(indexer=request.user, state=states.OPEN)
        changeset.save()
        changeset.comments.create(commenter=request.user,
                                  text=form.cleaned_data['comments'],
                                  old_state=states.UNRESERVED,
                                  new_state=changeset.state)
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
def add_issues(request, series_id):
    return render_error(request, 'Adding issues is not yet implemented.')

@permission_required('gcd.can_reserve')
def add_story(request, issue_id, changeset_id):
    changeset = get_object_or_404(Changeset, id=changeset_id)
    # Process add form if this is a POST.
    try:
        issue = Issue.objects.get(id=issue_id)
        if request.method != 'POST':
            seq = request.GET['added_sequence_number']
            if seq != '':
                try:
                    seq_num = int(seq)
                    initial = {'sequence_number': seq_num }
                    if seq_num == 0:
                        # Do not default other sequences, because if we do we
                        # will get a lot of people leaving the default values
                        # by accident.  Only sequence zero is predictable.
                        initial['type'] = StoryType.objects.get(name='cover').id
                        initial['no_script'] = True
                    form = get_story_revision_form()(initial=initial)
                except ValueError:
                    return render_error("Sequence number must be a whole number.")
            else:
                form = get_story_revision_form()()
            return _display_add_story_form(request, issue, form, changeset_id)

        if 'cancel_return' in request.POST:
            return HttpResponseRedirect(urlresolvers.reverse('edit',
              kwargs={ 'id': changeset_id }))

        form = get_story_revision_form()(request.POST)
        if not form.is_valid():
            return _display_add_story_form(request, issue, form, changeset_id)

        changeset.comments.create(commenter=request.user,
                                  text=form.cleaned_data['comments'],
                                  old_state=states.UNRESERVED,
                                  new_state=changeset.state)
        revision = form.save(commit=False)
        revision.save_added_revision(changeset=changeset,
                                     issue=issue)
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

    publishers = Changeset.objects.annotate(
      publisher_revision_count=Count('publisherrevisions')).filter(
      publisher_revision_count=1, **kwargs)

    indicia_publishers = Changeset.objects.annotate(
      indicia_publisher_revision_count=Count('indiciapublisherrevisions')).filter(
      indicia_publisher_revision_count=1, **kwargs)

    brands = Changeset.objects.annotate(
      brand_revision_count=Count('brandrevisions')).filter(
      brand_revision_count=1, **kwargs)

    series = Changeset.objects.annotate(
      series_revision_count=Count('seriesrevisions')).filter(
      series_revision_count=1, **kwargs)

    issue_annotated = Changeset.objects.annotate(
      issue_revision_count=Count('issuerevisions'))
    bulk_issue_adds = issue_annotated.filter(issue_revision_count__gt=1, **kwargs)
    issues = issue_annotated.filter(issue_revision_count=1, **kwargs)

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
            'changesets': bulk_issue_adds.order_by('modified'),
          },
          {
            'object_name': 'Issues',
            'object_type': 'issue',
            'changesets': issues, # TODO: hack! issues.order_by('modified'),
          },
        ],
      },
      context_instance=RequestContext(request)
    )

@login_required
def compare(request, id):
    changeset = get_object_or_404(Changeset, id=id)
    if changeset.inline():
        revision = changeset.inline_revision()
    else:
        if changeset.issuerevisions.count() == 1:
            revision = changeset.issuerevisions.all()[0]
        else:
            # TODO: What does compare look like for bulk skeleton adds?
            raise NotImplementedError

    revision.compare_changes()

    model_name = revision.source_name
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

