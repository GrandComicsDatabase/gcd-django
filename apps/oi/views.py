# -*- coding: utf-8 -*-


import re
import sys
import glob
import PIL.Image as pyImage
from urllib.parse import unquote

from django.core import urlresolvers
from django.conf import settings
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.db import transaction, IntegrityError
from django.db.models import Min, Max, Count, F
from django.utils.html import mark_safe, conditional_escape as esc

from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.contenttypes.models import ContentType

from apps.stddata.models import Country

from apps.indexer.views import ViewTerminationError, render_error

from apps.gcd.models import (
    Brand, BrandGroup, BrandUse, Cover, Image, IndiciaPublisher, Issue,
    IssueReprint, Publisher, Reprint, ReprintFromIssue, ReprintToIssue,
    Series, SeriesBond, Story, StoryType, Award, ReceivedAward, Creator,
    CreatorMembership, CreatorArtInfluence, CreatorDegree, CreatorNonComicWork,
    CreatorRelation, CreatorSchool, NameType, SourceType, STORY_TYPES,
    BiblioEntry, Feature, FeatureLogo, FeatureRelation)
from apps.gcd.views import paginate_response
# need this for preview-call
from apps.gcd.views.details import show_publisher, show_indicia_publisher, \
    show_brand_group, show_brand, show_series, show_issue, show_creator, \
    show_creator_membership, show_received_award, show_creator_art_influence, \
    show_creator_non_comic_work, show_creator_school, show_creator_degree, \
    show_award

from apps.gcd.views.covers import get_image_tag, get_image_tags_per_issue
from apps.gcd.views.search import do_advanced_search, used_search
from apps.gcd.models.cover import ZOOM_LARGE, ZOOM_MEDIUM
from apps.oi.templatetags.editing import show_revision_short
from apps.select.views import store_select_data

from apps.oi.models import (
    Changeset, BrandGroupRevision, BrandRevision, BrandUseRevision,
    CoverRevision, ImageRevision, IndiciaPublisherRevision, IssueRevision,
    PublisherRevision, ReprintRevision, SeriesBondRevision, SeriesRevision,
    StoryRevision, OngoingReservation, RevisionLock, _get_revision_lock,
    _free_revision_lock, CTYPES, get_issue_field_list, set_series_first_last,
    BiblioEntryRevision, DataSourceRevision, AwardRevision, CreatorRevision,
    CreatorNameDetailRevision, CreatorMembershipRevision, ReceivedAwardRevision,
    CreatorArtInfluenceRevision, CreatorNonComicWorkRevision, FeatureRevision,
    CreatorSchoolRevision, CreatorDegreeRevision, FeatureLogoRevision,
    CreatorRelationRevision, PreviewBrand, PreviewIssue, PreviewStory,
    PreviewReceivedAward, PreviewCreator, PreviewCreatorArtInfluence,
    PreviewCreatorDegree, PreviewCreatorMembership, PreviewCreatorNonComicWork,
    PreviewCreatorSchool, _get_creator_sourced_fields, on_sale_date_as_string,
    FeatureRelationRevision, process_data_source)

from apps.oi.forms import (get_brand_group_revision_form,
                           get_brand_revision_form,
                           get_brand_use_revision_form,
                           get_bulk_issue_revision_form,
                           get_award_revision_form,
                           get_received_award_revision_form,
                           get_creator_revision_form,
                           get_indicia_publisher_revision_form,
                           get_publisher_revision_form,
                           get_revision_form,
                           get_series_revision_form,
                           get_story_revision_form,
                           StoryRevisionFormSet,
                           get_feature_logo_revision_form,
                           get_feature_relation_revision_form,
                           get_date_revision_form,
                           OngoingReservationForm,
                           CreatorRevisionFormSet,
                           CreatorArtInfluenceRevisionForm,
                           CreatorMembershipRevisionForm,
                           ReceivedAwardRevisionForm,
                           CreatorNonComicWorkRevisionForm,
                           CreatorRelationRevisionForm,
                           CreatorSchoolRevisionForm,
                           CreatorDegreeRevisionForm,
                           DateRevisionForm)
from apps.oi.forms.support import CREATOR_HELP_LINKS

from apps.oi.covers import get_preview_image_tag, \
                           get_preview_generic_image_tag, \
                           get_preview_image_tags_per_page, UPLOAD_WIDTH
from apps.oi import states
from apps.oi.templatetags.editing import is_locked

REVISION_CLASSES = {
    'publisher': PublisherRevision,
    'indicia_publisher': IndiciaPublisherRevision,
    'brand_group': BrandGroupRevision,
    'brand': BrandRevision,
    'brand_use': BrandUseRevision,
    'series': SeriesRevision,
    'series_bond': SeriesBondRevision,
    'issue': IssueRevision,
    'story': StoryRevision,
    'biblio_entry': BiblioEntryRevision,
    'feature': FeatureRevision,
    'feature_logo': FeatureLogoRevision,
    'feature_relation': FeatureRelationRevision,
    'cover': CoverRevision,
    'reprint': ReprintRevision,
    'image': ImageRevision,
    'award': AwardRevision,
    'received_award': ReceivedAwardRevision,
    'creator': CreatorRevision,
    'creator_art_influence': CreatorArtInfluenceRevision,
    'creator_degree': CreatorDegreeRevision,
    'creator_membership': CreatorMembershipRevision,
    'creator_non_comic_work': CreatorNonComicWorkRevision,
    'creator_relation': CreatorRelationRevision,
    'creator_school': CreatorSchoolRevision,
}

# naming convention: xxx_yyy_zzz <-> XxxYyyZzz
DISPLAY_CLASSES = {
    'publisher': Publisher,
    'indicia_publisher': IndiciaPublisher,
    'brand_group': BrandGroup,
    'brand': Brand,
    'brand_use': BrandUse,
    'series': Series,
    'series_bond': SeriesBond,
    'issue': Issue,
    'story': Story,
    'biblio_entry': BiblioEntry,
    'feature': Feature,
    'feature_logo': FeatureLogo,
    'feature_relation': FeatureRelation,
    'cover': Cover,
    'reprint': Reprint,
    'reprint_to_issue': ReprintToIssue,
    'reprint_from_issue': ReprintFromIssue,
    'issue_reprint': IssueReprint,
    'image': Image,
    'award': Award,
    'received_award': ReceivedAward,
    'creator': Creator,
    'creator_art_influence': CreatorArtInfluence,
    'creator_degree': CreatorDegree,
    'creator_membership': CreatorMembership,
    'creator_non_comic_work': CreatorNonComicWork,
    'creator_relation': CreatorRelation,
    'creator_school': CreatorSchool,
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
    return render_error(
      request,
      'This page may only be accessed through the proper form.',
      redirect=False)


def oi_render(request, template_name, context={}):
    context['EDITING'] = True
    return render(request, template_name, context)

##############################################################################
# Generic view functions
##############################################################################


@permission_required('indexer.can_reserve')
def delete(request, id, model_name):
    display_obj = get_object_or_404(DISPLAY_CLASSES[model_name], id=id)
    if request.method == 'GET':

        # These can only be reached if people try to paste in URLs directly,
        # but as we know, some people do that sort of thing.
        if display_obj.deleted:
            return render_error(
              request,
              'Cannot delete "%s" as it is already deleted.' % display_obj,
              redirect=False)
        if not display_obj.deletable():
            return render_error(
              request,
              '"%s" cannot be deleted.' % display_obj, redirect=False)

        return oi_render(
          request,
          'oi/edit/deletion_comment.html',
          {
            'model_name': model_name,
            'id': id,
            'object': display_obj,
            'no_comment': False
          })

    if 'cancel' in request.POST:
        if model_name == 'cover':
            return HttpResponseRedirect(urlresolvers.reverse('edit_covers',
                                        kwargs={'issue_id':
                                                display_obj.issue.id}))
        return HttpResponseRedirect(urlresolvers.reverse('show_%s' % model_name,
                                    kwargs={'%s_id' % model_name: id}))

    if not request.POST.__contains__('comments') or \
       request.POST['comments'].strip() == '':
        return oi_render(
          request,
          'oi/edit/deletion_comment.html',
          {
            'model_name': model_name,
            'id': id,
            'object': display_obj,
            'no_comment': True
          })

    return reserve(request, id, model_name, delete=True)


@permission_required('indexer.can_reserve')
def reserve(request, id, model_name, delete=False,
            callback=None, callback_args=None):
    if request.method != 'POST':
        return _cant_get(request)
    display_obj = get_object_or_404(DISPLAY_CLASSES[model_name], id=id)

    if display_obj.deleted:
        if model_name == 'cover':
            return HttpResponseRedirect(urlresolvers.reverse('show_issue',
              kwargs={'issue_id': display_obj.issue.id}))
        return HttpResponseRedirect(urlresolvers.reverse('change_history',
          kwargs={'model_name': model_name, 'id': id}))

    try: # if something goes wrong we unreserve
        if delete:
            # TODO, this likely should not be needed anymore with the new
            # transaction handling ?
            # In case someone else deleted while page was open or if it is not
            # deletable because of other actions in the interim (adding to an
            # issue for brand/ind_pub, modifying covers for issue, etc.)
            if not display_obj.deletable():
                # Technically nothing to roll back, but keep this here in case
                # someone adds more code later.
                return render_error(request,
                       'This object fails the requirements for deletion.')

            changeset = _do_reserve(request.user, display_obj, model_name,
                                    delete=True)
        else:
            changeset = _do_reserve(request.user, display_obj, model_name)

        if changeset is False:
            return render_error(request, REACHED_CHANGE_LIMIT)
        if changeset is None:
            return render_error(
              request,
              'Cannot edit "%s" as it is reserved, or data objects required'
               ' for its editing are reserved.' % display_obj)

        if delete:
            changeset.submit(notes=request.POST['comments'], delete=True)
            if model_name in ['image', 'series_bond']:
                return HttpResponseRedirect(urlresolvers.reverse('editing'))
            if model_name == 'cover':
                return HttpResponseRedirect(urlresolvers.reverse('edit_covers',
                         kwargs={'issue_id' : display_obj.issue.id}))
            if model_name == 'brand_use':
                return HttpResponseRedirect(urlresolvers.reverse(
                     'show_brand',
                     kwargs={str('brand_id'): display_obj.emblem.id}))
            return HttpResponseRedirect(urlresolvers.reverse(
                     'show_%s' % model_name,
                     kwargs={str('%s_id' % model_name): id}))
        else:
            if callback:
                if not callback(changeset, display_obj, **callback_args):
                    _free_revision_lock(display_obj)
                    changeset.delete()
                    return render_error(request,
                      'Not all objects could be reserved.')
            return HttpResponseRedirect(urlresolvers.reverse(
              'edit', kwargs={ 'id': changeset.id }))

    except:
        #_free_revision_lock(display_obj)
        raise


def _do_reserve(indexer, display_obj, model_name, delete=False,
                changeset=None):
    """
    The creation of the revision and if needed changeset happens here.
    Returns either the changeset, False (when indexer cannot reserve more)
    or None (when something goes wrong). The revision_lock is deleted for
    both False and None as return values.
    """
    if model_name != 'cover' and (delete is False or indexer.indexer.is_new)\
       and indexer.indexer.can_reserve_another() is False:
        return False

    revision_lock = _get_revision_lock(display_obj)
    if not revision_lock:
        return None

    if delete:
        # Deletions are submitted immediately which will set the correct state.
        new_state = states.UNRESERVED
    else:
        comment = 'Editing'
        new_state = states.OPEN

    if not changeset:
        changeset_created = True
        changeset = Changeset(indexer=indexer, state=new_state,
                              change_type=CTYPES[model_name])
        changeset.save()

        if not delete:
            # Deletions are immediately submitted, which will add the
            # appropriate initial comment- no need to add two.
            changeset.comments.create(commenter=indexer,
                                      text=comment,
                                      old_state=states.UNRESERVED,
                                      new_state=changeset.state)
    else:
        changeset_created = False

    revision_lock.changeset = changeset
    revision_lock.save()

    revision = REVISION_CLASSES[model_name].objects.clone_revision(
      display_obj, changeset=changeset)

    if delete:
        revision.deleted = True
        revision.save()

    try:
        with transaction.atomic():
            revision._create_dependent_revisions(delete=delete)
    except IntegrityError:
        _free_revision_lock(revision.source)
        if changeset_created:
            changeset.delete()
        return None

    return changeset


@permission_required('indexer.can_reserve')
def edit_two_issues(request, issue_id):
    issue = get_object_or_404(Issue, id=issue_id, deleted=False)
    if is_locked(issue):
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
    return HttpResponseRedirect(urlresolvers.reverse(
      'select_object', kwargs={'select_key': select_key}))


@permission_required('indexer.can_reserve')
def confirm_two_edits(request, data, object_type, issue_two_id):
    if object_type != 'issue':
        raise ValueError
    issue_one = get_object_or_404(Issue, id=data['issue_id'], deleted=False)
    if is_locked(issue_one):
        return render_error(request, 'Issue %s is reserved.' % issue_one,
                            redirect=False)

    issue_two = get_object_or_404(Issue, id=issue_two_id, deleted=False)
    if is_locked(issue_two):
        return render_error(request, 'Issue %s is reserved.' % issue_two,
                            redirect=False)
    return oi_render(request, 'oi/edit/confirm_two_edits.html',
        {'issue_one': issue_one, 'issue_two': issue_two})


@permission_required('indexer.can_reserve')
# in case of variants: issue_one = variant, issue_two = base
def reserve_two_issues(request, issue_one_id, issue_two_id):
    if request.method != 'POST':
        return _cant_get(request)
    if 'cancel' in request.POST:
        return HttpResponseRedirect(urlresolvers.reverse(
          'show_issue', kwargs={'issue_id': issue_one_id}))
    issue_one = get_object_or_404(Issue, id=issue_one_id, deleted=False)
    issue_two = get_object_or_404(Issue, id=issue_two_id, deleted=False)

    kwargs = {'issue_one': issue_one}
    return reserve(request, issue_two_id, 'issue',
                   callback=reserve_other_issue,
                   callback_args=kwargs)


def reserve_other_issue(changeset, revision, issue_one):
    if not _do_reserve(changeset.indexer, issue_one, 'issue',
                       changeset=changeset):
        return False
    changeset.change_type=CTYPES['two_issues']
    changeset.save()
    return True


def extract_creator_names(request):
    total_creator_names = int(request.POST.get('total_names'))
    creator_names = []
    for i in range(1, total_creator_names + 1):
        if 'name_' + str(i) in request.POST:
            name_data = {}
            name_data['id'] = i
            name_data['name'] = request.POST.get('name_' + str(i))
            name_data['sort_name'] = request.POST.get('sort_name_' + str(i))
            name_data['type_id'] = int(request.POST.get('name_type_' + str(i)))
            name_data['revision_id'] = request.POST.get('name_revision_id_' + str(i))
            name_data['relation_type_id'] = int(request.POST.get(
                'relation_type_' + str(i))) if request.POST.get(
                'relation_type_' + str(i)) else None
            creator_names.append(name_data)
    return creator_names


@permission_required('indexer.can_reserve')
def edit_revision(request, id, model_name):
    revision = get_object_or_404(REVISION_CLASSES[model_name], id=id)
    form_class = get_revision_form(revision, user=request.user)
    form = form_class(instance=revision)
    extra_forms = revision.extra_forms(request)
    return _display_edit_form(request, revision.changeset, form, revision, extra_forms)


@permission_required('indexer.can_reserve')
def edit(request, id):
    changeset = get_object_or_404(Changeset, id=id)

    if changeset.inline():
        revision = changeset.inline_revision()
        form_class = get_revision_form(revision, user=request.user)
        form = form_class(instance=revision)
        extra_forms = revision.extra_forms(request)
    else:
        form = None
        revision = None
        extra_forms = None
    # Note that for non-inline changesets, no form is expected so
    # it may be None.
    return _display_edit_form(request, changeset, form, revision, extra_forms)


def _display_edit_form(request, changeset, form, revision=None, extra_forms=None):
    if revision is None or changeset.inline():
        template = 'oi/edit/changeset.html'
        if revision is None:
            revision = changeset.inline_revision()
    else:
        template = 'oi/edit/revision.html'

    context_vars = {
        'changeset': changeset,
        'revision': revision,
        'form': form,
        'states': states,
        'settings': settings,
        'CTYPES': CTYPES
    }
    if extra_forms:
        context_vars.update(extra_forms)
    response = oi_render(request, template, context_vars)
    response['Cache-Control'] = "no-cache, no-store, max-age=0, must-revalidate"
    return response


@permission_required('indexer.can_reserve')
def submit(request, id):
    """
    Submit a change and go to the reservations queue.
    """
    if request.method != 'POST':
        return _cant_get(request)

    changeset = get_object_or_404(Changeset, id=id)
    if (request.user != changeset.indexer):
        return oi_render(request, 'indexer/error.html',
          {'error_text': 'A change may only be submitted by its author.'})
    comment_text = request.POST['comments'].strip()
    changeset.submit(notes=comment_text)
    if changeset.approver is not None:
        if comment_text:
            comment = 'The submission includes the comment:\n"%s"' % \
                      comment_text
        else:
            comment = ''
        email_body = """
Hello from the %s!


  You have a change for "%s" by %s to review. %s

Please go to %s to compare the changes.

thanks,
-the %s team
%s
""" % (settings.SITE_NAME,
           str(changeset),
           str(changeset.indexer.indexer),
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


def _save_data_source_revision(form, revision, field):
    data_source_revision = revision.changeset\
        .datasourcerevisions.filter(field=field)
    if data_source_revision:
        # TODO support more than one revision
        data_source_revision = data_source_revision[0]
    process_data_source(form, field, revision.changeset,
                        revision=data_source_revision,
                        sourced_revision=revision)


def _extra_forms_valid(request, extra_forms):
    is_valid = True
    for form in extra_forms:
        is_valid = is_valid and extra_forms[form].is_valid()
    return is_valid


def _save(request, form, revision, changeset=None, model_name=None):
    extra_forms = revision.extra_forms(request)
    if form.is_valid() and _extra_forms_valid(request, extra_forms):
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
        revision.process_extra_forms(request, extra_forms)
        if revision.changeset.change_type == CTYPES['series'] and \
          'move_to_publisher_with_id' in form.cleaned_data and \
          request.user.has_perm('indexer.can_approve') and \
          form.cleaned_data['move_to_publisher_with_id']:
            try:
                publisher_id = form.cleaned_data['move_to_publisher_with_id']
                publisher = Publisher.objects.get(id=publisher_id,
                                                  deleted=False)
            except Publisher.DoesNotExist:
                return show_error_with_return(request,
                  'No publisher with id %d.' % publisher_id, changeset)
            if publisher.pending_deletion():
                return show_error_with_return(request, 'Publisher %s is '
                  'pending deletion' % str(publisher), changeset)
            if revision.changeset.issuerevisions.count() == 0:
                revision.series.active_issues()
                if RevisionLock.objects.filter(
                  object_id__in=revision.series.active_issues() \
                                               .values_list('id', flat=True)) \
                                               .exists():
                    return show_error_with_return(request,
                      ('Some issues for series %s are reserved. '
                       'No move possible.') % revision.series,
                      changeset)
            return HttpResponseRedirect(urlresolvers.reverse(
              'move_series', kwargs={'series_revision_id': revision.id,
                                     'publisher_id': publisher_id}))

        if hasattr(form, 'save_m2m'):
            # TODO handle sources in standard workflow
            # I don't quite understand what is going on here, but for image
            # and cover revision form.save_m2m() fails with a comment.
            # But we don't need form.save_m2m() for these anyway. I suspect
            # problems since relation to ChangesetComment is called 'comments'
            # and the text 'field' is called that as well.
            if not (len(form.cleaned_data) == 1 and \
                                'comments' in form.cleaned_data):
                if revision.changeset.change_type in [
                                        CTYPES['received_award'],
                                        CTYPES['creator_art_influence'],
                                        CTYPES['creator_degree'],
                                        CTYPES['creator_membership'],
                                        CTYPES['creator_non_comic_work'],
                                        CTYPES['creator_relation'],
                                        CTYPES['creator_school']]:
                    _save_data_source_revision(form, revision, '')
                    if revision.changeset.change_type == \
                      CTYPES['creator_relation']:
                        form.save_m2m()
                else:
                    form.save_m2m()

        # TODO re-factor into model routine
        if revision.source_name == 'story':
            if revision.feature_logo.count():
                # stories for variants in variant-add next to issue have issue
                if revision.issue:
                    language = revision.issue.series.language
                else:
                    language = revision.my_issue_revision.\
                                        other_issue_revision.series.language
                for feature_logo in revision.feature_logo.all():
                    if feature_logo.feature.get(language=language) not in \
                       revision.feature_object.all():
                        revision.feature_object.add(feature_logo.feature.
                                                    get(language=language))

        if 'submit' in request.POST:
            return submit(request, revision.changeset.id)
        if 'queue' in request.POST:
            return HttpResponseRedirect(urlresolvers.reverse('editing'))
        if 'save' in request.POST:
            return HttpResponseRedirect(urlresolvers.reverse('edit_revision',
              kwargs={ 'model_name': model_name, 'id': revision.id }))
        if 'save_return' in request.POST:
            # BiblioEntry needs second form for specific fields
            if revision.source_class == Story \
              and revision.type.id == STORY_TYPES['about comics']:
                if hasattr(revision, 'biblioentryrevision'):
                    biblio_revision = revision.biblioentryrevision
                else:
                    biblio_revision = BiblioEntryRevision(storyrevision_ptr=
                                                          revision)
                    biblio_revision.__dict__.update(revision.__dict__)
                    biblio_revision.save()
                return HttpResponseRedirect(
                  urlresolvers.reverse('edit_revision',
                                       kwargs={'model_name': 'biblio_entry',
                                               'id': biblio_revision.id }))
            return HttpResponseRedirect(urlresolvers.reverse('edit',
              kwargs={ 'id': revision.changeset.id }))
        return render_error(request,
          'Revision saved but cannot determine which '
          'page to load now.  Contact an editor if this error persists.')

    if changeset == None:
        changeset = revision.changeset
    return _display_edit_form(request, changeset, form, revision,
                              extra_forms=extra_forms)


@permission_required('indexer.can_reserve')
def retract(request, id):
    """
    Retract a pending change back into your reserved queue.
    """
    if request.method != 'POST':
        return _cant_get(request)
    changeset = get_object_or_404(Changeset, id=id)

    if request.user != changeset.indexer:
        return oi_render(request, 'indexer/error.html',
          {'error_text': 'A change may only be retracted by its author.'})
    comment_text = request.POST['comments'].strip()
    changeset.retract(notes=comment_text)

    if comment_text:
        send_comment_observer(request, changeset, comment_text)

    return HttpResponseRedirect(
      urlresolvers.reverse('edit', kwargs={'id': changeset.id }))


@permission_required('indexer.can_reserve')
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
        return oi_render(request, 'oi/edit/confirm_discard.html',
                         {'changeset': changeset })

    if 'discard' in request.POST:
        if has_comment == '1' and changeset.approver:
            comment_text = changeset.comments.latest('created').text
            comment = 'The discard includes the comment:\n"%s"' % comment_text
        else:
            comment = ''
            comment_text = ''
        changeset.discard(discarder=request.user)
        if changeset.approver:
            email_body = """
Hello from the %s!


  The change for "%s" by %s which you were reviewing was discarded. %s

You can view the full change at %s.

thanks,
-the %s team
%s
""" % (settings.SITE_NAME,
               str(changeset),
               str(changeset.indexer.indexer),
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


@permission_required('indexer.can_reserve')
def discard(request, id):
    """
    Discard a change and go to the reservations queue.
    """
    if request.method != 'POST':
        return _cant_get(request)
    changeset = get_object_or_404(Changeset, id=id)

    if (request.user != changeset.indexer and
        request.user != changeset.approver):
        return oi_render(request, 'indexer/error.html',
                         {'error_text': 'Only the author or the assigned '
                                        'editor can discard a change.' })

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
        email_body = """
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
           str(changeset),
           str(changeset.approver.indexer),
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
        if request.user.approved_changeset.filter(state=states.REVIEWING)\
                                          .count():
            return HttpResponseRedirect(urlresolvers.reverse('reviewing'))
        else:
            if changeset.change_type is CTYPES['cover']:
                return HttpResponseRedirect(
                  urlresolvers.reverse('pending_covers'))
            else:
                return HttpResponseRedirect(urlresolvers.reverse('pending'))


@permission_required('indexer.can_approve')
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
    except ViewTerminationError:
        if changeset.approver is None:
            return render_error(request,
              'This change has been retracted by the indexer after you loaded '
              'the previous page. This results in you seeing an "Assign" '
              'button. Please use the back button to return to the '
              'Pending queue.',
              redirect=False)
        else:
            return render_error(request,
              ('This change is already being reviewed by %s who may have '
               'assigned it after you loaded the previous page.  '
               'This results in you seeing an '
               '"Assign" button even though the change is under review. '
               'Please use the back button to return to the Pending queue.') %
              changeset.approver.indexer,
              redirect=False)

    if changeset.indexer.indexer.is_new and \
       changeset.indexer.indexer.mentor is None and\
       changeset.change_type is not CTYPES['cover']:

        changeset.indexer.indexer.mentor = request.user
        changeset.indexer.indexer.save()

        for pending in changeset.indexer.changesets\
                                        .filter(state=states.PENDING):
            try:
              pending.assign(approver=request.user, notes='')
            except ValueError:
                # Someone is already reviewing this.
                # Unlikely, and just let it go.
                pass

    if comment_text:
        email_body = """
Hello from the %s!


  %s became editor of the change "%s" with the comment:
"%s"

You can view the full change at %s.

thanks,
-the %s team
%s
""" % (settings.SITE_NAME,
           str(request.user.indexer),
           str(changeset),
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


@permission_required('indexer.can_approve')
def release(request, id):
    """
    Move a change out of your approvals queue, and go back to your queue.
    """
    if request.method != 'POST':
        return _cant_get(request)

    changeset = get_object_or_404(Changeset, id=id)
    if request.user != changeset.approver:
        return oi_render(request, 'indexer/error.html',
          {'error_text': 'A change may only be released by its approver.'})

    comment_text = request.POST['comments'].strip()
    changeset.release(notes=comment_text)
    if comment_text:
        email_body = """
Hello from the %s!


  editor %s released the change "%s" with the comment:
"%s"

You can view the full change at %s.

thanks,
-the %s team
%s
""" % (settings.SITE_NAME,
           str(request.user.indexer),
           str(changeset),
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
        if changeset.change_type is CTYPES['cover']:
            return HttpResponseRedirect(urlresolvers.reverse('pending_covers'))
        else:
            return HttpResponseRedirect(urlresolvers.reverse('pending'))


@permission_required('indexer.can_approve')
def discuss(request, id):
    """
    Move a change into the discussion state and go back to your queue.
    """
    if request.method != 'POST':
        return _cant_get(request)

    changeset = get_object_or_404(Changeset, id=id)
    if request.user != changeset.approver and \
      request.user != changeset.indexer:
        return oi_render(request, 'indexer/error.html',
          {'error_text': 'A change may only be put into discussion by its ' \
                         'indexer or approver.'})
    if request.user == changeset.approver and \
      changeset.state != states.REVIEWING:
        return render_error(request,
          'Only REVIEWING changes can be put into discussion.')
    if request.user == changeset.indexer and \
      changeset.state not in [states.OPEN, states.REVIEWING]:
        return render_error(request,
          'Only EDITING OR REVIEWING changes can be put into discussion.')

    comment_text = request.POST['comments'].strip()
    changeset.discuss(commenter=request.user, notes=comment_text)

    if comment_text:
        email_comments = ' with the comment:\n"%s"' % comment_text
    else:
        email_comments = '.'

    if request.user == changeset.indexer:
        action_by = 'indexer %s' % str(changeset.indexer.indexer)
        start_comment = 'The reviewed'
    else:
        action_by = 'editor %s' % str(changeset.approver.indexer)
        start_comment = 'Your'

    email_body = """
Hello from the %s!


  %s change for "%s" was put into the discussion state by GCD %s%s

You can view the full change at %s.

thanks,
-the %s team

%s
""" % (settings.SITE_NAME,
       start_comment,
       str(changeset),
       action_by,
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

    if request.user == changeset.indexer:
        changeset.approver.email_user(subject, email_body, settings.EMAIL_INDEXING)
        return HttpResponseRedirect(urlresolvers.reverse('editing'))
    else:
        changeset.indexer.email_user(subject, email_body, settings.EMAIL_INDEXING)

        if request.user.approved_changeset.filter(state=states.REVIEWING).count():
            return HttpResponseRedirect(urlresolvers.reverse('reviewing'))
        else:
            if changeset.change_type is CTYPES['cover']:
                return HttpResponseRedirect(urlresolvers.reverse('pending_covers'))
            else:
                return HttpResponseRedirect(urlresolvers.reverse('pending'))


def _reserve_newly_created_issue(issue, changeset, indexer):
    new_change = _do_reserve(indexer, issue, 'issue')
    # TODO maybe check for False vs. None here ?
    if not new_change:
        _send_declined_reservation_email(indexer, issue)


@permission_required('indexer.can_approve')
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
    #try:
    changeset.approve(notes=comment_text)
    #except ValueError as detail:
        #if len(detail.args) > 0:
            #return render_error(request, detail.args[0])
        #else:
            #raise detail
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
        email_body = """
Hello from the %s!


  Your change for "%s" was approved by GCD editor %s%s

You can view the full change at %s.

thanks,
-the %s team

%s
%s
""" % (settings.SITE_NAME,
       str(changeset),
       str(changeset.approver.indexer),
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
    # TODO does this belong into model.py ?
    for series_revision in \
        changeset.seriesrevisions.filter(deleted=False,
                                         reservation_requested=True,
                                         series__created__gt=F('created'),
                                         series__is_current=True,
                                         series__ongoing_reservation=None,
                                         is_singleton=False):
        if (changeset.indexer.ongoing_reservations.count() >=
           changeset.indexer.indexer.max_ongoing):
            _send_declined_ongoing_email(changeset.indexer,
                                         series_revision.series)

        ongoing = OngoingReservation(indexer=changeset.indexer,
                                     series=series_revision.series)
        ongoing.save()

    # here created_gte needed for singleton issues freshly created
    for issue_revision in \
        changeset.issuerevisions.filter(deleted=False,
                                        reservation_requested=True,
                                        issue__created__gte=F('created'),
                                        series__ongoing_reservation=None):
        _reserve_newly_created_issue(issue_revision.issue, changeset,
                                     changeset.indexer)

    for issue_revision in \
        changeset.issuerevisions.filter(
                                 deleted=False,
                                 reservation_requested=True,
                                 issue__created__gt=F('created'),
                                 series__ongoing_reservation__isnull=False,
                                 issue__variant_of__isnull=False):
        _reserve_newly_created_issue(issue_revision.issue, changeset,
                                     changeset.indexer)

    # here created_gt since for issues reserved by an ongoing reservation the
    # timestamps can be the same
    for issue_revision in \
        changeset.issuerevisions.filter(
                                 deleted=False,
                                 issue__created__gt=F('created'),
                                 series__ongoing_reservation__isnull=False,
                                 issue__variant_of=None):
        _reserve_newly_created_issue(
          issue_revision.issue, changeset,
          issue_revision.series.ongoing_reservation.indexer)

    # Move brand new indexers to probationary status on first approval.
    if changeset.change_type is not CTYPES['cover'] and \
       changeset.indexer.indexer.max_reservations == \
       settings.RESERVE_MAX_INITIAL:
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
    email_body = """
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
    email_body = """
Hello from the %s!


  Your requested ongoing reservation of series "%s" was declined because
you have reached your maximum number of ongoing reservations.  %s

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


@permission_required('indexer.can_approve')
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

    email_body = """
Hello from the %s!


  Your change for "%s" was sent back by GCD editor %s with the comment:
"%s"

Please go to %s to re-edit or reply.

thanks,
-the %s team
%s
""" % (settings.SITE_NAME,
       str(changeset),
       str(changeset.approver.indexer),
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
        if changeset.change_type is CTYPES['cover']:
            return HttpResponseRedirect(
                urlresolvers.reverse('pending_covers'))
        else:
            return HttpResponseRedirect(urlresolvers.reverse('pending'))


def send_comment_observer(request, changeset, comments):
    email_body = """
Hello from the %s!


  %s added a comment to the change "%s" to which you added a comment before:
"%s"

You can view the full change at %s.

thanks,
-the %s team
%s
""" % (settings.SITE_NAME,
           str(request.user.indexer),
           str(changeset),
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


@permission_required('indexer.can_reserve')
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

        email_body = """
Hello from the %s!


  %s added a comment to the change "%s":
"%s"

You can view the full change at %s.

thanks,
-the %s team
%s
""" % (settings.SITE_NAME,
           str(request.user.indexer),
           str(changeset),
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

    if 'HTTP_REFERER' in request.META:
        return HttpResponseRedirect(request.META['HTTP_REFERER'])

    return HttpResponseRedirect(urlresolvers.reverse(compare,
                                                     kwargs={ 'id': id }))


@permission_required('indexer.can_reserve')
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
            form = form_class(request.POST, request.FILES, instance=revision)
            return _save(request, form, revision, changeset=changeset)
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


@permission_required('indexer.can_reserve')
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
        return _save(request, form, revision, model_name=model_name)

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


@permission_required('indexer.can_reserve')
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
    nr_items_reserved = RevisionLock.objects.filter(
      object_id__in=items.values_list('id', flat=True),
      content_type=ContentType.objects.get_for_model(items[0])).count()
    nr_items_unreserved = nr_items - nr_items_reserved
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
            raise ValueError('not more than 100 issues if more than one series')
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
                remove_fields.append(i)
                # some fields belong together, both are either in or out
                if i in ['volume', 'brand', 'editing', 'indicia_frequency',
                         'rating']:
                    if 'no_' + i not in remove_fields:
                        remove_fields.append('no_' + i)
                elif i in ['no_volume', 'no_brand', 'no_editing',
                           'no_indicia_frequency', 'no_rating']:
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

    for i in ['no_barcode', 'no_isbn']:
        if i not in remove_fields:
            values_list = list(set(items.values_list(i[3:], flat=True)))
            if len(values_list) > 1:
                remove_fields.append(i)

    for i in fields:
        if i not in remove_fields:
            values_list = list(set(items.values_list(i, flat=True)))
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
        comment += '%s : %s\n' % (search[0], search[1])
    comment += 'method : %s\n' % method
    comment += 'behavior : %s\n' % logic
    # cannot use urlencode since urlize needs plain text
    # and urlencode would encode non-ASCII characters
    query_string = ''
    for entry in request.GET.items():
        if query_string == '':
            query_string += '?%s=%s' % entry
        else:
            query_string += '&%s=%s' % entry
    comment += 'Search results: %s%s%s' % (settings.SITE_URL.rstrip('/'),
                 urlresolvers.reverse('process_advanced_search'),
                 query_string.replace(' ', '+'))

    changeset.comments.create(commenter=request.user,
                              text=comment,
                              old_state=changeset.state,
                              new_state=changeset.state)

    cd = form.cleaned_data
    for issue in items:
        revision_lock = _get_revision_lock(issue, changeset)
        if revision_lock:
            revision = IssueRevision.objects.clone_revision(
                                             issue,
                                             changeset=changeset)
            for field in initial:
                if field in ['brand', 'indicia_publisher'] and \
                   cd[field] is not None:
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
    return oi_render(
      request, 'oi/edit/bulk_frame.html',
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
      })

##############################################################################
# Adding Items
##############################################################################


@permission_required('indexer.can_reserve')
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
    revision.save_added_revision(changeset=changeset)
    return submit(request, changeset.id)


def _display_add_publisher_form(request, form):
    object_name = 'Publisher'
    object_url = urlresolvers.reverse('add_publisher')

    return oi_render(
      request, 'oi/edit/add_frame.html',
      {
        'object_name': object_name,
        'object_url': object_url,
        'action_label': 'Submit new',
        'form': form,
      })


@permission_required('indexer.can_reserve')
def add_indicia_publisher(request, parent_id):
    if not request.user.indexer.can_reserve_another():
        return render_error(request, REACHED_CHANGE_LIMIT)

    try:
        parent = Publisher.objects.get(id=parent_id)
        if parent.deleted or parent.pending_deletion():
            return render_error(request, 'Cannot add indicia / colophon '
              'publishers since "%s" is deleted or pending deletion.' % parent)

        if request.method != 'POST':
            form = get_indicia_publisher_revision_form(user=request.user)()
            return _display_add_indicia_publisher_form(request, parent, form)

        if 'cancel' in request.POST:
            return HttpResponseRedirect(urlresolvers.reverse(
              'show_publisher',
              kwargs={ 'publisher_id': parent_id }))

        form = \
          get_indicia_publisher_revision_form(user=request.user)(request.POST)
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
          'Could not find publisher for id ' + parent_id)


def _display_add_indicia_publisher_form(request, parent, form):
    object_name = 'Indicia / Colophon Publisher'
    object_url = urlresolvers.reverse('add_indicia_publisher',
                                          kwargs={ 'parent_id': parent.id })

    return oi_render(
      request, 'oi/edit/add_frame.html',
      {
        'object_name': object_name,
        'object_url': object_url,
        'action_label': 'Submit new',
        'form': form,
      })


@permission_required('indexer.can_reserve')
def add_brand_group(request, parent_id):
    if not request.user.indexer.can_reserve_another():
        return render_error(request, REACHED_CHANGE_LIMIT)

    try:
        parent = Publisher.objects.get(id=parent_id)
        if parent.deleted or parent.pending_deletion():
            return render_error(request, 'Cannot add brands '
              'since "%s" is deleted or pending deletion.' % parent)

        if request.method != 'POST':
            form = get_brand_group_revision_form(user=request.user)()
            return _display_add_brand_group_form(request, parent, form)

        if 'cancel' in request.POST:
            return HttpResponseRedirect(urlresolvers.reverse(
              'show_publisher',
              kwargs={ 'publisher_id': parent_id }))

        form = get_brand_group_revision_form(user=request.user)(request.POST)
        if not form.is_valid():
            return _display_add_brand_group_form(request, parent, form)

        changeset = Changeset(indexer=request.user, state=states.OPEN,
                              change_type=CTYPES['brand_group'])
        changeset.save()
        revision = form.save(commit=False)
        revision.save_added_revision(changeset=changeset,
                                     parent=parent)
        return submit(request, changeset.id)

    except (Publisher.DoesNotExist, Publisher.MultipleObjectsReturned):
        return render_error(request,
          'Could not find publisher for id ' + parent_id)


def _display_add_brand_group_form(request, parent, form):
    object_name = 'BrandGroup'
    object_url = urlresolvers.reverse('add_brand_group',
                                      kwargs={ 'parent_id': parent.id })

    return oi_render(
      request, 'oi/edit/add_frame.html',
      {
        'object_name': object_name,
        'object_url': object_url,
        'action_label': 'Submit new',
        'form': form,
      })


@permission_required('indexer.can_reserve')
def add_brand(request, brand_group_id=None, publisher_id=None):
    if not request.user.indexer.can_reserve_another():
        return render_error(request, REACHED_CHANGE_LIMIT)

    if brand_group_id:
        try:
            brand_group = BrandGroup.objects.get(id=brand_group_id)
            if brand_group.deleted or brand_group.pending_deletion():
                return render_error(request, 'Cannot add brands '
                'since "%s" is deleted or pending deletion.' % brand_group)
        except (BrandGroup.DoesNotExist, BrandGroup.MultipleObjectsReturned):
            return render_error(request,
            'Could not find Brand Group for id ' + brand_group_id)
        publisher = None
    else:
        try:
            publisher = Publisher.objects.get(id=publisher_id)
            if publisher.deleted or publisher.pending_deletion():
                return render_error(request, 'Cannot add brands '
                'since "%s" is deleted or pending deletion.' % publisher)
        except (Publisher.DoesNotExist, Publisher.MultipleObjectsReturned):
            return render_error(request,
            'Could not find Publisher for id ' + publisher_id)
        brand_group = None
            
    if request.method != 'POST':
        form = get_brand_revision_form(user=request.user, publisher=publisher,
                                       brand_group=brand_group)()
        return _display_add_brand_form(request, form, brand_group, publisher)

    if 'cancel' in request.POST:
        if brand_group_id:
            return HttpResponseRedirect(urlresolvers.reverse(
                'show_brand_group',
                kwargs={ 'brand_group_id': brand_group_id }))
        else:
            return HttpResponseRedirect(urlresolvers.reverse(
                'show_publisher',
                kwargs={ 'publisher_id': publisher_id }))

    form = get_brand_revision_form(user=request.user, publisher=publisher,
                                   brand_group=brand_group)(request.POST)
    if not form.is_valid():
        return _display_add_brand_form(request, form, brand_group, publisher)
    
    changeset = Changeset(indexer=request.user, state=states.OPEN,
                            change_type=CTYPES['brand'])
    changeset.save()
    revision = form.save(commit=False)
    revision.save_added_revision(changeset=changeset)
    form.save_m2m()
    return submit(request, changeset.id)


def _display_add_brand_form(request, form, brand_group=None, publisher=None):
    object_name = 'Brand Emblem'
    if brand_group:
        object_url = urlresolvers.reverse('add_brand_via_group',
                                        kwargs={ 'brand_group_id': brand_group.id })
    else:
        object_url = urlresolvers.reverse('add_brand_via_publisher',
                                        kwargs={ 'publisher_id': publisher.id })

    return oi_render(
      request, 'oi/edit/add_frame.html',
      {
        'object_name': object_name,
        'object_url': object_url,
        'action_label': 'Submit new',
        'form': form,
      })


@permission_required('indexer.can_reserve')
def add_brand_use(request, brand_id, publisher_id=None):
    brand = get_object_or_404(Brand, id=brand_id, deleted=False)
    if brand.pending_deletion():
        return render_error(request, 'Cannot add a brand use '
          'since "%s" is pending deletion.' % brand)
    if publisher_id:
        publisher = get_object_or_404(Publisher, id=publisher_id, deleted=False)
        if publisher.pending_deletion():
            return render_error(request, 'Cannot add a brand use '
              'since "%s" is pending deletion.' % publisher)
        if request.method != 'POST':
            # we should only get here by a POST
            raise NotImplementedError

        if 'cancel' in request.POST:
            return HttpResponseRedirect(urlresolvers.reverse(
                'show_brand',
                kwargs={ 'brand_id': brand_id }))

        form = get_brand_use_revision_form(user=request.user)(request.POST)
        if not form.is_valid:
            return _display_add_brand_use_form(request, form, brand, publisher)

        changeset = Changeset(indexer=request.user, state=states.OPEN,
                              change_type=CTYPES['brand_use'])
        changeset.save()
        revision = form.save(commit=False)
        revision.save_added_revision(changeset=changeset, emblem=brand,
                                     publisher=publisher)
        return submit(request, changeset.id)
    else:
        data = {'heading': mark_safe('<h2>Select Publisher where the Brand %s was '
                                    'in use</h2>' % esc(brand.name)),
                'target': 'a publisher',
                'brand_id': brand_id,
                'publisher': True,
                'return': process_add_brand_use,
                'cancel': HttpResponseRedirect(urlresolvers.reverse('show_brand',
                            kwargs={'brand_id': brand_id}))}
        select_key = store_select_data(request, None, data)
        return HttpResponseRedirect(urlresolvers.reverse('select_object',
            kwargs={'select_key': select_key}))


@permission_required('indexer.can_reserve')
def process_add_brand_use(request, data, object_type, publisher_id):
    if object_type != 'publisher':
        raise ValueError
    brand = get_object_or_404(Brand, id=data['brand_id'], deleted=False)

    publisher = get_object_or_404(Publisher, id=publisher_id, deleted=False)

    form = get_brand_use_revision_form(user=request.user)
    return _display_add_brand_use_form(request, form, brand, publisher)


def _display_add_brand_use_form(request, form, brand, publisher):
    object_name = 'BrandUse for %s at %s' % (brand, publisher)
    object_url = urlresolvers.reverse('add_brand_use',
                                      kwargs={ 'brand_id': brand.id,
                                               'publisher_id': publisher.id})

    return oi_render(
      request, 'oi/edit/add_frame.html',
      {
        'object_name': object_name,
        'object_url': object_url,
        'action_label': 'Submit new',
        'form': form,
      })


@permission_required('indexer.can_reserve')
def add_series(request, publisher_id):
    if not request.user.indexer.can_reserve_another():
        return render_error(request, REACHED_CHANGE_LIMIT)

    # Process add form if this is a POST.
    try:
        publisher = Publisher.objects.get(id=publisher_id)
        if publisher.deleted or publisher.pending_deletion():
            return render_error(request, 'Cannot add series '
              'since "%s" is deleted or pending deletion.' % publisher)

        if request.method != 'POST':
            initial = {}
            initial['country'] = publisher.country.id
            # TODO: make these using same code as get_blank_values
            initial['has_barcode'] = True
            initial['has_isbn'] = True
            initial['is_comics_publication'] = True
            form = get_series_revision_form(publisher,
                                            user=request.user)(initial=initial)
            return _display_add_series_form(request, publisher, form)

        if 'cancel' in request.POST:
            return HttpResponseRedirect(urlresolvers.reverse(
              'show_publisher',
              kwargs={ 'publisher_id': publisher_id }))

        form = get_series_revision_form(publisher,
                                        user=request.user)(request.POST)
        if not form.is_valid():
            return _display_add_series_form(request, publisher, form)

        changeset = Changeset(indexer=request.user, state=states.OPEN,
                              change_type=CTYPES['series'])
        changeset.save()
        revision = form.save(commit=False)
        revision.save_added_revision(changeset=changeset,
                                     publisher=publisher)
        return submit(request, changeset.id)

    except (Publisher.DoesNotExist, Publisher.MultipleObjectsReturned):
        return render_error(request,
          'Could not find publisher for id ' + publisher_id)


def _display_add_series_form(request, publisher, form):
    kwargs = {
        'publisher_id': publisher.id,
    }
    url = urlresolvers.reverse('add_series', kwargs=kwargs)
    return oi_render(
      request, 'oi/edit/add_frame.html',
      {
        'object_name': 'Series',
        'object_url': url,
        'action_label': 'Submit new',
        'form': form,
      })


def init_added_variant(form_class, initial, issue, revision=False):
    for key in list(initial):
        if key.startswith('_'):
            initial.pop(key)
    if issue.brand:
        initial['brand'] = issue.brand.id
    if issue.indicia_publisher:
        initial['indicia_publisher'] = issue.indicia_publisher.id
    initial['variant_name'] = ''
    if revision:
        issue = issue.issue
    if issue.variant_set.filter(deleted=False).count():
        initial['after'] = issue.variant_set.filter(deleted=False)\
                                            .latest('sort_code').id
    form = form_class(initial=initial)
    return form


@permission_required('indexer.can_reserve')
def add_issue(request, series_id, sort_after=None, variant_of=None,
              variant_cover=None, edit_with_base=False):
    if not request.user.indexer.can_reserve_another():
        return render_error(request, REACHED_CHANGE_LIMIT)

    series = get_object_or_404(Series, id=series_id)
    if series.deleted or series.pending_deletion():
        return render_error(request, 'Cannot add an issue '
          'since "%s" is deleted or pending deletion.' % series)

    form_class = get_revision_form(model_name='issue',
                                   series=series,
                                   publisher=series.publisher,
                                   variant_of=variant_of,
                                   user=request.user,
                                   edit_with_base=edit_with_base)

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
              'show_issue',
              kwargs={ 'issue_id': variant_of.id }))
        else:
            return HttpResponseRedirect(urlresolvers.reverse(
              'show_series',
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
    series = issue_revision.series

    form_class = get_revision_form(model_name='issue',
                                   series=series,
                                   publisher=issue_revision.series.publisher,
                                   variant_of=issue_revision.issue,
                                   user=request.user)

    if request.method != 'POST':
        initial = dict(issue_revision.__dict__)
        form = init_added_variant(form_class, initial, issue_revision,
                                  revision=True)
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
        # via create variant for cover
        issue = revision.issue

        # create issue revision for the issue of the cover
        if not _do_reserve(changeset.indexer, issue, 'issue',
                           changeset=changeset):
            return False

    changeset.change_type=CTYPES['variant_add']
    changeset.save()

    # save issue revision for the new variant record
    issuerevision.save_added_revision(changeset=changeset,
                                      series=variant_of.series,
                                      variant_of=variant_of)
    return True


@permission_required('indexer.can_reserve')
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
            object_name = 'Variant Issue'
            extra_adding_info = 'of %s and edit both' % variant_of
        else:
            alternative_action = 'edit_with_base'
            alternative_label = 'Save new Variant Issue for %s and edit both' \
                                % variant_of
            object_name = 'Variant Issue'
            extra_adding_info = 'of %s' % variant_of

        url = urlresolvers.reverse('add_variant_issue', kwargs=kwargs)
    elif issue_revision:
        kwargs = {
            'issue_revision_id': issue_revision.id,
            'changeset_id': issue_revision.changeset.id,
        }
        action_label = 'Save new'
        url = urlresolvers.reverse('add_variant_to_issue_revision',
                                   kwargs=kwargs)
        object_name = 'Variant Issue'
        extra_adding_info = 'of %s' % issue_revision
    else:
        kwargs = {
            'series_id': series.id,
        }
        url = urlresolvers.reverse('add_issue', kwargs=kwargs)
        object_name = 'Issue'
        extra_adding_info = 'to %s' % series

    return oi_render(
      request, 'oi/edit/add_frame.html',
      {
        'object_name': object_name,
        'object_url': url,
        'extra_adding_info': extra_adding_info,
        'action_label': action_label,
        'form': form,
        'alternative_action': alternative_action,
        'alternative_label': alternative_label,
      })


@permission_required('indexer.can_reserve')
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
        return render_error(request, 'Cannot add issues '
          'since "%s" is deleted or pending deletion.' % series)

    if method is None:
        return oi_render(request, 'oi/edit/add_issues.html',
                         { 'series': series,
                           'issue_adds' : issue_adds })

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
          'show_series',
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


def _display_bulk_issue_form(request, series, form, method=None):
    kwargs = {
        'series_id': series.id,
    }
    url_name = 'add_issues'
    if method is not None:
        kwargs['method'] = method
        url_name = 'add_multiple_issues'
    url = urlresolvers.reverse(url_name, kwargs=kwargs)
    extra_adding_info = 'to %s' % series
    return oi_render(
      request, 'oi/edit/add_frame.html',
      {
        'object_name': 'Issues',
        'object_url': url,
        'extra_adding_info': extra_adding_info,
        'action_label': 'Submit new',
        'form': form,
      })


@permission_required('indexer.can_reserve')
def add_generic(request, model_name):
    if not request.user.indexer.can_reserve_another():
        return render_error(request, REACHED_CHANGE_LIMIT)

    if request.method == 'POST' and 'cancel' in request.POST:
        return HttpResponseRedirect(urlresolvers.reverse('add'))

    form = get_revision_form(model_name=model_name,
                             user=request.user)(request.POST or None)
    if form.is_valid():
        changeset = Changeset(indexer=request.user, state=states.OPEN,
                              change_type=CTYPES[model_name])
        changeset.save()
        revision = form.save(commit=False)
        revision.save_added_revision(changeset=changeset)
        return submit(request, changeset.id)
    else:
        object_name = DISPLAY_CLASSES[model_name].__name__
        object_url = urlresolvers.reverse('add_%s' % model_name)

        return oi_render(
          request, 'oi/edit/add_frame.html',
          {
            'object_name': object_name,
            'object_url': object_url,
            'action_label': 'Submit new',
            'form': form,
          })


def add_feature(request):
    return add_generic(request, 'feature')


@permission_required('indexer.can_reserve')
def add_feature_logo(request, feature_id):
    if not request.user.indexer.can_reserve_another():
        return render_error(request, REACHED_CHANGE_LIMIT)

    feature = get_object_or_404(Feature, id=feature_id, deleted=False)

    if feature.pending_deletion():
        return render_error(request, 'Cannot add a feature logo '
          'since "%s" is pending deletion.' % feature)

    if request.method == 'POST' and 'cancel' in request.POST:
        return HttpResponseRedirect(urlresolvers.reverse(
          'show_feature', kwargs={ 'feature_id': feature_id }))

    initial = {'feature': feature}
    form = get_feature_logo_revision_form(user=request.user)\
                                         (request.POST or None,
                                          initial=initial)

    if form.is_valid():
        changeset = Changeset(indexer=request.user, state=states.OPEN,
                              change_type=CTYPES['feature_logo'])
        changeset.save()
        revision = form.save(commit=False)
        revision.save_added_revision(changeset=changeset)
        form.save_m2m()
        return submit(request, changeset.id)

    object_name = 'Feature Logo'
    object_url = urlresolvers.reverse('add_feature_logo',
                                      kwargs={ 'feature_id': feature.id })

    return oi_render(
      request, 'oi/edit/add_frame.html',
      {
        'object_name': object_name,
        'object_url': object_url,
        'action_label': 'Submit new',
        'form': form,
      })


@permission_required('indexer.can_reserve')
def add_feature_relation(request, feature_id):
    if not request.user.indexer.can_reserve_another():
        return render_error(request, REACHED_CHANGE_LIMIT)

    feature = get_object_or_404(Feature, id=feature_id, deleted=False)

    if feature.pending_deletion():
        return render_error(request, 'Cannot add Relation for '
                                     'feature "%s" since the record is '
                                     'pending deletion.' % feature)

    if request.method == 'POST' and 'cancel' in request.POST:
        return HttpResponseRedirect(urlresolvers.reverse(
                'show_feature', kwargs={'feature_id': feature_id}))

    initial = {}
    initial['from_feature'] = feature
    relation_form = get_feature_relation_revision_form(user=request.user)\
                                                      (request.POST or None,
                                                       initial=initial)

    if relation_form.is_valid():
        changeset = Changeset(indexer=request.user, state=states.OPEN,
                              change_type=CTYPES['feature_relation'])
        changeset.save()

        revision = relation_form.save(commit=False)
        revision.save_added_revision(changeset=changeset, feature=feature)
        revision.save()

        return submit(request, changeset.id)

    context = {'form': relation_form,
               'object_name': 'Relation with Feature',
               'object_url': urlresolvers.reverse('add_feature_relation',
                                                  kwargs={'feature_id': feature_id}),
               'action_label': 'Submit new',
               'settings': settings}
    return oi_render(request, 'oi/edit/add_frame.html', context)


@permission_required('indexer.can_reserve')
def add_story(request, issue_revision_id, changeset_id):
    changeset = get_object_or_404(Changeset, id=changeset_id)
    if request.user != changeset.indexer:
        return render_error(request,
          'Only the reservation holder may add stories.')
    # check if this is a request to add a copy of a sequence
    if 'copy' in request.GET:
        issue_revision = changeset.issuerevisions.get(id=issue_revision_id)
        if issue_revision.issue:
            issue_id = issue_revision.issue_id
        else:
            raise NotImplementedError
        seq = request.GET.get('added_sequence_number')
        initial = _get_initial_add_story_data(request, issue_revision, seq)
        return copy_sequence(request, changeset_id, issue_id,
                             sequence_number=initial['sequence_number'])

    if request.method == 'POST' and 'cancel_return' in request.POST:
        return HttpResponseRedirect(urlresolvers.reverse(
          'edit', kwargs={'id': changeset_id}))

    # Process add form if this is a POST.
    try:
        issue_revision = changeset.issuerevisions.get(id=issue_revision_id)
        issue = issue_revision.issue
        if issue_revision.variant_of and \
          issue_revision.active_stories().count():
            return render_error(request,
                  'You cannot add more than one story to a variant issue.',
                  redirect=False)

        initial = {}
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
        form = get_story_revision_form(user=request.user,
                                       series=issue_revision.series)\
                                      (request.POST or None,
                                       initial=initial)
        credits_formset = StoryRevisionFormSet(request.POST or None)

        if not form.is_valid() or not credits_formset.is_valid():
            kwargs = {
                'issue_revision_id': issue_revision_id,
                'changeset_id': changeset_id,
            }
            url = urlresolvers.reverse('add_story', kwargs=kwargs)

            return oi_render(
                request, 'oi/edit/add_frame.html',
                {
                    'object_name': 'Story',
                    'object_url': url,
                    'action_label': 'Save',
                    'form': form,
                    'settings': settings,
                    'credits_formset': credits_formset,
                })

        revision = form.save(commit=False)
        stories = issue_revision.active_stories()
        _reorder_children(request, issue_revision, stories, 'sequence_number',
                          stories, commit=True, unique=False, skip=revision)

        revision.save_added_revision(changeset=changeset,
                                     issue=issue)
        revision.save()
        if form.cleaned_data['comments']:
            revision.comments.create(commenter=request.user,
                                     changeset=changeset,
                                     text=form.cleaned_data['comments'],
                                     old_state=changeset.state,
                                     new_state=changeset.state)

        extra_forms = {'credits_formset': credits_formset, }
        revision.process_extra_forms(request, extra_forms)
        form.save_m2m()
        if revision.feature_logo.count():
            # stories for variants in variant-add next to issue have issue
            if revision.issue:
                language = revision.issue.series.language
            else:
                language = revision.my_issue_revision. \
                    other_issue_revision.series.language
            for feature_logo in revision.feature_logo.all():
                if feature_logo.feature.get(language=language) not in \
                  revision.feature_object.all():
                    revision.feature_object.add(feature_logo.feature.
                                                get(language=language))

        if revision.source_class == Story \
          and revision.type.id == STORY_TYPES['about comics']:
            biblio_revision = BiblioEntryRevision(storyrevision_ptr=
                                                  revision)
            biblio_revision.__dict__.update(revision.__dict__)
            biblio_revision.save()
            return HttpResponseRedirect(
              urlresolvers.reverse('edit_revision',
                                    kwargs={'model_name': 'biblio_entry',
                                            'id': biblio_revision.id }))

        return HttpResponseRedirect(urlresolvers.reverse('edit',
          kwargs={ 'id': changeset.id }))

    except ViewTerminationError as vte:
        return vte.response

    except (IssueRevision.DoesNotExist, IssueRevision.MultipleObjectsReturned):
        return render_error(request,
          'Could not find issue revision for id ' + issue_revision_id)


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


##############################################################################
# Series Bond Editing
##############################################################################


@permission_required('indexer.can_reserve')
def edit_series_bonds(request, series_id):
    series = get_object_or_404(Series, id=series_id)
    return oi_render(request, 'oi/edit/list_series_bonds.html',
      {
        'series': series,
      })


@permission_required('indexer.can_reserve')
def save_selected_series_bond(request, data, object_type, selected_id):
    if request.method != 'POST':
        return _cant_get(request)
    series_bond_revision = get_object_or_404(SeriesBondRevision,
                           id=data['series_bond_revision_id'])
    if object_type == 'series':
        series = get_object_or_404(Series, id=selected_id)
        if data['which_side'] == 'origin':
            series_bond_revision.origin = series
            series_bond_revision.origin_issue = None
        else:
            series_bond_revision.target = series
            series_bond_revision.target_issue = None
    else:
        issue = get_object_or_404(Issue, id=selected_id)
        if data['which_side'] == 'origin':
            series_bond_revision.origin = issue.series
            series_bond_revision.origin_issue = issue
        else:
            series_bond_revision.target = issue.series
            series_bond_revision.target_issue = issue
    series_bond_revision.save()
    return HttpResponseRedirect(urlresolvers.reverse('edit',
        kwargs={'id': series_bond_revision.changeset.id}))


@permission_required('indexer.can_reserve')
def edit_series_bond(request, id):
    if request.method != 'POST':
        return _cant_get(request)
    series_bond_revision = get_object_or_404(SeriesBondRevision, id=id)
    number = ''
    if 'edit_origin' in request.POST:
        which_side = 'origin'
        series = series_bond_revision.origin
        if series_bond_revision.origin_issue:
            number = series_bond_revision.origin_issue.number
    elif 'edit_target' in request.POST:
        which_side = 'target'
        series = series_bond_revision.target
        if series_bond_revision.target_issue:
            number = series_bond_revision.target_issue.number
    elif 'flip_direction' in request.POST:
        series = series_bond_revision.target
        issue = series_bond_revision.target_issue
        series_bond_revision.target = series_bond_revision.origin
        series_bond_revision.target_issue = series_bond_revision.origin_issue
        series_bond_revision.origin = series
        series_bond_revision.origin_issue = issue
        series_bond_revision.save()
        return HttpResponseRedirect(urlresolvers.reverse('edit',
            kwargs={'id': series_bond_revision.changeset.id}))
    else:
        raise NotImplementedError
    initial = {'series': series.name,
            'publisher': series.publisher,
            'year': series.year_began,
            'number': number}
    data = {'series_bond_revision_id': id,
            'initial': initial,
            'series': True,
            'issue': True,
            'heading': mark_safe('<h2>Select %s of the bond %s</h2>' % \
                                 (which_side, series_bond_revision)),
            'target': 'a series or issue',
            'return': save_selected_series_bond,
            'which_side': which_side,
            'cancel': HttpResponseRedirect(urlresolvers.reverse('edit',
                        kwargs={'id': series_bond_revision.changeset.id}))}
    select_key = store_select_data(request, None, data)
    return HttpResponseRedirect(urlresolvers.reverse('select_object',
        kwargs={'select_key': select_key}))


def save_added_series_bond(request, data, object_type, selected_id):
    if request.method != 'POST':
        return _cant_get(request)
    changeset = Changeset(indexer=request.user, state=states.OPEN,
                        change_type=CTYPES['series_bond'])
    changeset.save()
    series = get_object_or_404(Series, id=data['series_id'])
    if object_type == 'series':
        target = get_object_or_404(Series, id=selected_id)
        series_bond_revision = SeriesBondRevision(target=target)
    else:
        target_issue = get_object_or_404(Issue, id=selected_id)
        series_bond_revision = SeriesBondRevision(target=target_issue.series,
                                                  target_issue=target_issue)
    series_bond_revision.origin = series
    series_bond_revision.changeset = changeset
    series_bond_revision.save()
    return HttpResponseRedirect(urlresolvers.reverse('edit',
        kwargs={'id': series_bond_revision.changeset.id}))


@permission_required('indexer.can_reserve')
def add_series_bond(request, id):
    series = get_object_or_404(Series, id=id)
    data = {'series_id': id,
            'series': True,
            'issue': True,
            'heading': mark_safe('<h2>Select other side of the bond</h2>'),
            'target': 'a series or issue',
            'return': save_added_series_bond,
            'cancel': HttpResponseRedirect(urlresolvers.reverse('show_series',
                        kwargs={'series_id': series.id}))}
    select_key = store_select_data(request, None, data)
    return HttpResponseRedirect(urlresolvers.reverse('select_object',
        kwargs={'select_key': select_key}))


##############################################################################
# Reprint Link Editing
##############################################################################


def parse_reprint(reprints):
    """ parse a reprint entry for exactly our standard """
    reprint_direction_from = ["from", "da", "di", "de", "uit", "från", "aus"]
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

            # italian and spanish from/in
            if from_to in ['da ', 'in ', 'de ', 'en ']:
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
                    if hyphen > 0 and string[:hyphen].isdigit() and \
                       not string[hyphen+2:].strip()[0].isdigit():
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


@permission_required('indexer.can_reserve')
def list_issue_reprints(request, id):
    issue_revision = get_object_or_404(IssueRevision, id=id)
    changeset = issue_revision.changeset
    if request.user != changeset.indexer:
        return render_error(request,
          'Only the reservation holder may access this page.')
    response = oi_render(request, 'oi/edit/list_issue_reprints.html',
      { 'issue_revision': issue_revision, 'changeset': changeset })
    response['Cache-Control'] = "no-cache, no-store, max-age=0, must-revalidate"
    return response


@permission_required('indexer.can_reserve')
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
    revision_lock = _get_revision_lock(display_obj, changeset)
    if not revision_lock:
        return render_error(request,
          'Cannot edit "%s" as it is already reserved.' % display_obj)

    revision = ReprintRevision.objects.clone_revision(display_obj,
                                                      changeset=changeset)

    return HttpResponseRedirect(urlresolvers.reverse('edit_reprint',
        kwargs={'id': revision.id, 'which_side': which_side }))


@permission_required('indexer.can_reserve')
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
            return HttpResponseRedirect(
                urlresolvers.reverse('list_issue_reprints',
                                     kwargs={ 'id': changeset_issue.id }))
        else:
            return _cant_get(request)
    elif which_side == 'remove':
        return HttpResponseRedirect(
          urlresolvers.reverse('remove_reprint_revision', kwargs={ 'id': id }))
    elif which_side == 'matching_sequence':
        if reprint_revision.origin_story:
            story = reprint_revision.origin_story
            issue = reprint_revision.target_issue
        else:
            story = reprint_revision.target_story
            issue = reprint_revision.origin_issue
        if issue != changeset_issue.issue:
            return _cant_get(request)
        return HttpResponseRedirect(
          urlresolvers.reverse('create_matching_sequence',
                               kwargs={ 'reprint_revision_id': id,
                                        'story_id': story.id,
                                        'issue_id': issue.id }))
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
                story = PreviewStory.init(reprint_revision.origin_revision)
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
                story = PreviewStory.init(reprint_revision.target_revision)
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

        return oi_render(request, 'oi/edit/confirm_reprint.html',
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
            })

    else:
        raise NotImplementedError

    if which_side.endswith('internal'):
        issue_revision  = select_issue.revisions.get(changeset=changeset)
        return oi_render(request, 'oi/edit/select_internal_object.html',
            { 'issue_revision': issue_revision, 'changeset': changeset,
              'reprint_revision': reprint_revision,
              'which_side': which_side[:6] })

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


@permission_required('indexer.can_reserve')
def add_reprint(request, changeset_id,
                story_id=None, issue_id=None, reprint_note=''):
    if story_id:
        story = get_object_or_404(StoryRevision, id=story_id,
                                    changeset__id=changeset_id)
    else:
        issue = get_object_or_404(IssueRevision, id=issue_id,
                                  changeset__id=changeset_id)
    if reprint_note:
        publisher, series, year, number, volume = \
            parse_reprint(unquote(reprint_note).split(';')[0])
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


@permission_required('indexer.can_reserve')
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
        this_story = PreviewStory.init(this_story)
        this_issue = None

    return oi_render(request, 'oi/edit/confirm_internal.html',
        { 'this_issue': this_issue, 'this_story': this_story,
          'other_issue': other_issue, 'other_story': other_story,
          'changeset': changeset, 'reprint_revision_id': reprint_revision.id,
          'reprint_revision': reprint_revision, 'which_side': which_side })


def _selected_copy_sequence(request, data, object_type, selected_id):
    if request.method != 'POST':
        return _cant_get(request)
    if 'cancel' in request.POST:
        return HttpResponseRedirect(urlresolvers.reverse('edit',
          kwargs={ 'id': data['changeset_id'] }))

    return copy_sequence(request, data['changeset_id'], data['issue_id'],
                         story_id=selected_id,
                         sequence_number=data['sequence_number'])


@permission_required('indexer.can_reserve')
def copy_sequence(request, changeset_id, issue_id, story_id=None,
                  sequence_number=None):
    changeset = get_object_or_404(Changeset, id=changeset_id)
    if request.user != changeset.indexer:
        return render_error(request,
          'Only the reservation holder may access this page.')

    issue = get_object_or_404(Issue, id=issue_id)
    if issue_id not in changeset.issuerevisions.values_list('issue_id', flat=True):
        return _cant_get(request)

    if request.method != 'POST':
        heading = 'Select story to copy into %s' % (esc(issue))
        data = {'issue_id': issue_id,
                'changeset_id': changeset_id,
                'story': True,
                'initial': {},
                'heading': mark_safe('<h2>%s</h2>' % heading),
                'target': 'a story',
                'return': _selected_copy_sequence,
                'sequence_number': sequence_number,
                'cancel': HttpResponseRedirect(urlresolvers.reverse('edit',
                                               kwargs={'id': changeset_id}))}
        select_key = store_select_data(request, None, data)
        return HttpResponseRedirect(urlresolvers.reverse('select_object',
                                    kwargs={'select_key': select_key}))
    else:
        story = get_object_or_404(Story, id=story_id)
        story_revision = StoryRevision.copied_revision(story, changeset,
                                                       issue=issue)
        # sequence number should be determined in add_story
        # but this routine could be called differently as well
        if sequence_number:
            story_revision.sequence_number = sequence_number
            story_revision.save()
            issue_revision = changeset.issuerevisions.get(issue_id=issue_id)
            stories = issue_revision.active_stories().exclude(id=story_revision.id)
            _reorder_children(request, issue_revision, stories, 'sequence_number',
                              stories, commit=True, unique=False,
                              skip=story_revision)
        return HttpResponseRedirect(urlresolvers.reverse('edit_revision',
                                    kwargs={'model_name': 'story',
                                            'id': story_revision.id }))


@permission_required('indexer.can_reserve')
def create_matching_sequence(request, reprint_revision_id, story_id, issue_id, edit=False):
    story = get_object_or_404(Story, id=story_id)
    issue = get_object_or_404(Issue, id=issue_id)
    reprint_revision = get_object_or_404(ReprintRevision,
                                         id=reprint_revision_id)
    changeset = reprint_revision.changeset
    changeset_issue = changeset.issuerevisions.get()
    if request.user != changeset.indexer:
        return render_error(request,
          'Only the reservation holder may access this page.')
    if issue != changeset_issue.issue:
        return _cant_get(request)
    if request.method != 'POST' and not edit:
        if story == reprint_revision.origin_story:
            direction = 'from'
        else:
            direction = 'in'
        return oi_render(request, 'oi/edit/create_matching_sequence.html',
            { 'issue': issue, 'story': story,
              'reprint_revision': reprint_revision, 'direction': direction })
    else:
        story_revision = StoryRevision.copied_revision(story, changeset,
                                                       issue=issue)
        if reprint_revision.origin_story:
            reprint_revision.target_revision = story_revision
            reprint_revision.target_issue = None
        else:
            reprint_revision.origin_revision = story_revision
            reprint_revision.origin_issue = None
        reprint_revision.save()
        return HttpResponseRedirect(urlresolvers.reverse('edit_revision',
              kwargs={ 'model_name': 'story', 'id': story_revision.id }))


@permission_required('indexer.can_reserve')
def confirm_reprint(request, data, object_type, selected_id):
    if request.method != 'POST':
        return _cant_get(request)
    if 'cancel' in request.POST:
        return HttpResponseRedirect(urlresolvers.reverse('edit',
          kwargs={ 'id': data['changeset_id'] }))

    if 'story_id' in data and data['story_id']:
        story = get_object_or_404(Story, id=data['story_id'])
        story_revision = False
        story_story = True
        current_issue = None
    elif 'story_revision_id' in data and data['story_revision_id']:
        story_story = False
        story_revision = True
        story_revision = get_object_or_404(StoryRevision,
                                   id=data['story_revision_id'],
                                   changeset__id=data['changeset_id'])
        story = PreviewStory.init(story_revision)
        current_issue = None
    elif 'issue_id' in data and data['issue_id']:
        story_story = False
        story_revision = False
        story = None
        current_issue = get_object_or_404(Issue, id=data['issue_id'])
    elif 'issue_revision_id' in data and data['issue_revision_id']:
        story_story = False
        story_revision = False
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
    elif 'which_side' in request.session:
        which_side = request.session['which_side']
    else:
        which_side = None

    return oi_render(request, 'oi/edit/confirm_reprint.html',
        {
        'story': story,
        'issue': current_issue,
        'story_story': story_story,
        'story_revision': story_revision,
        'selected_story': selected_story,
        'selected_issue': selected_issue,
        'reprint_revision': reprint_revision,
        'reprint_revision_id': reprint_revision_id,
        'changeset': changeset,
        'which_side': which_side
        })


@permission_required('indexer.can_reserve')
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
        if request.POST['direction'] == 'from':
            request.session['which_side'] = 'origin'
        else:
            request.session['which_side'] = 'target'

    if request.POST['comments'].strip():
        revision.comments.create(commenter=request.user,
                                 changeset=changeset,
                                 text=request.POST['comments'],
                                 old_state=changeset.state,
                                 new_state=changeset.state)
    if 'add_reprint_view' in request.POST:
        return HttpResponseRedirect(urlresolvers.reverse('list_issue_reprints',
            kwargs={ 'id': changeset.issuerevisions.get().id }))
    if 'matching_sequence' in request.POST:
        if revision.origin_story:
            story = revision.origin_story
            issue = revision.target_issue
        else:
            story = revision.target_story
            issue = revision.origin_issue
        if issue != changeset.issuerevisions.get().issue:
            return _cant_get(request)
        return HttpResponseRedirect(
          urlresolvers.reverse('create_edit_matching_sequence',
                               kwargs={ 'reprint_revision_id': revision.id,
                                        'story_id': story.id,
                                        'issue_id': issue.id }))
    else:
        return HttpResponseRedirect(urlresolvers.reverse('edit',
            kwargs={ 'id': changeset_id }))


@permission_required('indexer.can_reserve')
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
        return oi_render(request, 'oi/edit/confirm_remove_reprint.html',
        {
            'origin': origin,
            'origin_issue': origin_issue,
            'target': target,
            'target_issue': target_issue,
            'reprint': reprint
        })

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


@permission_required('indexer.can_reserve')
def move_series(request, series_revision_id, publisher_id):
    series_revision = get_object_or_404(SeriesRevision, id=series_revision_id,
                                        deleted=False)
    if request.user != series_revision.changeset.indexer:
        return render_error(request,
          'Only the reservation holder may move series.')

    publisher = Publisher.objects.filter(id=publisher_id, deleted=False)
    if not publisher:
        return render_error(request, 'No publisher with id %s.' \
                            % publisher_id, redirect=False)
    publisher = publisher[0]

    if request.method != 'POST':
        header_text = 'Do you want to move %s to <a href="%s">%s</a> ?' % \
          (esc(series_revision.series.full_name()),
           publisher.get_absolute_url(),
           esc(publisher))
        url = urlresolvers.reverse('move_series',
          kwargs={'series_revision_id': series_revision_id,
                  'publisher_id': publisher_id})
        cancel_button = "Cancel"
        confirm_button = "move of series %s to publisher %s" % \
          (series_revision.series, publisher)
        return oi_render(request, 'oi/edit/confirm.html',
                          {
                              'type': 'Series Move',
                              'header_text': mark_safe(header_text),
                              'url': url,
                              'cancel_button': cancel_button,
                              'confirm_button': confirm_button,
                          })
    else:
        if 'cancel' in request.POST:
            return HttpResponseRedirect(urlresolvers.reverse('edit',
              kwargs={'id': series_revision.changeset.id}))
        else:
            if series_revision.changeset.issuerevisions.count() == 0:
                for issue in series_revision.series.active_issues():
                    if not _do_reserve(series_revision.changeset.indexer,
                                       issue, 'issue',
                                       changeset=series_revision.changeset):
                        for issue_rev in series_revision.changeset\
                                                        .issuerevisions.all():
                            _free_revision_lock(issue_rev.issue)
                            issue_rev.delete()
                        for story_rev in series_revision.changeset\
                                                        .storyrevisions.all():
                            _free_revision_lock(story_rev.story)
                            story_rev.delete()
                        return show_error_with_return(
                          request, 'Error while reserving issues.',
                          series_revision.changeset)
                for issue_revision in series_revision.changeset.issuerevisions.all():
                    if issue_revision.brand:
                        new_brand = publisher.active_brand_emblems()\
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


@permission_required('indexer.can_reserve')
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
        return oi_render(request, 'oi/edit/confirm.html',
                                {
                                    'type': 'Issue Move',
                                    'header_text': header_text,
                                    'url': url,
                                    'cancel_button': cancel_button,
                                    'confirm_button': confirm_button,
                                })
    else:
        if 'cancel' not in request.POST:
            if issue_revision.series.publisher != series.publisher:
                if issue_revision.brand:
                    new_brand = series.publisher.active_brand_emblems()\
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


@permission_required('indexer.can_reserve')
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


@permission_required('indexer.can_reserve')
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
        return oi_render(
          request,
          'oi/edit/move_covers.html',
          {
              'changeset': changeset,
              'covers': covers,
              'table_width': UPLOAD_WIDTH
          })

    cover = get_object_or_404(Cover, id=cover_id)
    issue = changeset.issuerevisions.filter(issue=cover.issue)
    if not issue:
        return render_error(request,
          'Cover does not belong to an issue of this changeset.')

    revision_lock = _get_revision_lock(cover, changeset)
    if not revision_lock:
        return render_error(request,
            'Cannot move the cover as it is already reserved.')

    # create cover revision
    revision = CoverRevision.objects.clone_revision(cover, changeset=changeset)

    return HttpResponseRedirect(urlresolvers.reverse('edit',
      kwargs={ 'id': changeset.id }))


@permission_required('indexer.can_reserve')
def undo_move_cover(request, id, cover_id):
    changeset = get_object_or_404(Changeset, id=id)
    if request.user != changeset.indexer:
        return render_error(request,
          'Only the reservation holder may undo cover moves in a changeset.')

    if request.method != 'POST':
        return _cant_get(request)
    # TODO FIXME
    cover_revision = get_object_or_404(CoverRevision, id=cover_id, changeset=changeset)
    _free_revision_lock(cover_revision.cover)
    cover_revision.delete()

    return HttpResponseRedirect(urlresolvers.reverse('edit',
      kwargs={ 'id': changeset.id }))

##############################################################################
# Removing Items from a Changeset
##############################################################################


@permission_required('indexer.can_reserve')
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
        preview_story = PreviewStory.init(story)
        return oi_render(
          request, 'oi/edit/remove_story_revision.html',
          {
            'story' : preview_story,
            'issue' : story.issue
          })

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


@permission_required('indexer.can_reserve')
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


@permission_required('indexer.can_reserve')
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
        return render_error(request, 'Cannot reserve issues '
          'since "%s" is deleted or pending deletion.' % series)

    # TODO no need for the form, since different workflow as originally intended
    form = OngoingReservationForm()
    if request.method == 'POST':
        form = OngoingReservationForm(request.POST)
        if form.is_valid():
            reservation = form.save(commit=False)
            reservation.indexer = request.user
            reservation.save()
            return HttpResponseRedirect(urlresolvers.reverse(
              'show_series', kwargs={ 'series_id': reservation.series.id }))
        else:
            return render_error(request, 'Something went wrong while reserving'
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
      'show_series', kwargs={ 'series_id': series.id }))

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


@permission_required('indexer.can_approve')
def reorder_series(request, series_id):
    series = get_object_or_404(Series, id=series_id)
    if request.method != 'POST':
        return oi_render(
          request, 'oi/edit/reorder_series.html',
          { 'series': series,
            'issue_list': [ (i, None) for i in series.active_issues() ] })

    try:
        issues = _process_reorder_form(request, series, 'sort_code',
                                       'issue', Issue)
        return _reorder_series(request, series, issues)
    except ViewTerminationError as vte:
        return vte.response


@permission_required('indexer.can_approve')
def reorder_series_by_key_date(request, series_id):
    if request.method != 'POST':
        return _cant_get(request)
    series = get_object_or_404(Series, id=series_id)

    issues = series.active_issues().order_by('key_date')
    return _reorder_series(request, series, issues)


@permission_required('indexer.can_approve')
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
                                       series.issue_set.all(),
                                       'commit' in request.POST,
                                       extras=series.issue_set.filter(
                                         deleted=True))
    except ViewTerminationError as vte:
        return vte.response

    if 'commit' in request.POST:
        set_series_first_last(series)
        return HttpResponseRedirect(urlresolvers.reverse(
          'show_series', kwargs={ 'series_id': series.id }))

    return oi_render(request, 'oi/edit/reorder_series.html',
      { 'series': series,
        'issue_list': issue_list })


@permission_required('indexer.can_reserve')
def reorder_stories(request, issue_id, changeset_id):
    changeset = get_object_or_404(Changeset, id=changeset_id)
    if request.user != changeset.indexer:
        return render_error(request,
          'Only the reservation holder may reorder stories.')

    # At this time, only existing issues can have their stories reordered.
    # This is analagous to issues needing to exist before stories can be added.
    issue_revision = changeset.issuerevisions.get(issue=issue_id)
    if request.method != 'POST':
        return oi_render(request, 'oi/edit/reorder_stories.html',
          { 'issue': issue_revision, 'changeset': changeset })

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
                      commit, unique=True, skip=None, extras=None):
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
        elif num_children <= sys.maxsize - max:
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

    if commit and extras:
        for child in extras:
            setattr(child, sort_field, current_code)
            child.save()
            current_code += 1

    return child_list


##############################################################################
# Queue Views
##############################################################################


@permission_required('indexer.can_reserve')
def show_queue(request, queue_name, state):
    kwargs = {}
    if 'editing' == queue_name:
        kwargs['indexer'] = request.user
        kwargs['state__in'] = states.ACTIVE
    elif 'pending' == queue_name:
        kwargs['state__in'] = (states.PENDING, states.DISCUSSED,
                               states.REVIEWING)
    elif 'reviews' == queue_name:
        kwargs['approver'] = request.user
        kwargs['state__in'] = (states.OPEN, states.DISCUSSED,
                               states.REVIEWING)
    elif 'covers' == queue_name:
        return show_cover_queue(request)
    elif 'approved' == queue_name:
        return show_approved(request)
    elif 'editor_log' == queue_name:
        return show_editor_log(request)

    changes = Changeset.objects.filter(**kwargs).select_related(
      'indexer__indexer', 'approver__indexer')

    awards = changes.filter(change_type=CTYPES['award'])
    creators = changes.filter(change_type=CTYPES['creator'])
    creator_art_influences = changes.filter(change_type=CTYPES['creator_art_influence'])
    received_awards = changes.filter(change_type=CTYPES['received_award'])
    creator_memberships = changes.filter(change_type=CTYPES['creator_membership'])
    creator_non_comic_works = changes.filter(change_type=CTYPES['creator_non_comic_work'])
    creator_relations = changes.filter(change_type=CTYPES['creator_relation'])
    creator_schools = changes.filter(change_type=CTYPES['creator_school'])
    creator_degres = changes.filter(change_type=CTYPES['creator_degree'])
    publishers = changes.filter(change_type=CTYPES['publisher'])
    indicia_publishers = changes.filter(change_type=CTYPES['indicia_publisher'])
    brand_groups = changes.filter(change_type=CTYPES['brand_group'])
    brands = changes.filter(change_type=CTYPES['brand'])
    brand_uses = changes.filter(change_type=CTYPES['brand_use'])
    series = changes.filter(change_type=CTYPES['series'])\
                    .prefetch_related('seriesrevisions__series')
    series_bonds = changes.filter(change_type=CTYPES['series_bond'])
    issue_adds = changes.filter(change_type=CTYPES['issue_add'])
    issues = changes.filter(change_type__in=[CTYPES['issue'],
                                             CTYPES['variant_add'],
                                             CTYPES['two_issues']])\
                    .prefetch_related('issuerevisions__issue',
                                      'issuerevisions__series')
    issue_bulks = changes.filter(change_type=CTYPES['issue_bulk'])
    covers = changes.filter(change_type=CTYPES['cover'])\
                    .prefetch_related('coverrevisions__issue__series')
    features = changes.filter(change_type=CTYPES['feature'])
    feature_logos = changes.filter(change_type=CTYPES['feature_logo'])
    feature_relations = changes.filter(change_type=CTYPES['feature_relation'])
    images = changes.filter(change_type=CTYPES['image'])
    countries = dict(Country.objects.values_list('id', 'code'))
    country_names = dict(Country.objects.values_list('id', 'name'))
    response = oi_render(
      request,
      'oi/queues/%s.html' % queue_name,
      {
        'queue_name': queue_name,
        'indexer': request.user,
        'states': states,
        'countries': countries,
        'country_names': country_names,
        'data': [
          {
            'object_name': 'Awards',
            'object_type': 'award',
            'changesets': awards.order_by('modified', 'id')
          },
          {
            'object_name': 'Received Awards',
            'object_type': 'received_award',
            'changesets': received_awards.order_by('modified', 'id')
          },
          {
            'object_name': 'Creators',
            'object_type': 'creator',
            'changesets': creators.order_by('modified', 'id') \
                .annotate(
                country=Max('creatorrevisions__birth_country__id'))
          },
          {
            'object_name': 'Memberships',
            'object_type': 'creator_membership',
            'changesets': creator_memberships.order_by('modified', 'id') \
                .annotate(country=Max(
                'creatormembershiprevisions__creator__birth_country__id'))
          },
          {
            'object_name': 'Art Influences',
            'object_type': 'creator_art_influence',
            'changesets': creator_art_influences.order_by('modified',
                                                          'id') \
                .annotate(country=Max(
                'creatorartinfluencerevisions__creator__birth_country__id'))
          },
          {
            'object_name': 'Non Comic Works',
            'object_type': 'creator_non_comic_work',
            'changesets': creator_non_comic_works.order_by('modified', 'id') \
                .annotate(country=Max(
                'creatornoncomicworkrevisions__creator__birth_country__id'))
          },
          {
            'object_name': 'Creator Relations',
            'object_type': 'creator_relation',
            'changesets': creator_relations.order_by('modified', 'id') \
                .annotate(country=Max(
                'creatorrelationrevisions__from_creator__birth_country__id'))
          },
          {
            'object_name': 'Creator Schools',
            'object_type': 'creator_school',
            'changesets': creator_schools.order_by('modified', 'id') \
                .annotate(country=Max(
                'creatorschoolrevisions__creator__birth_country__id'))
          },
          {
            'object_name': 'Creator Degrees',
            'object_type': 'creator_degree',
            'changesets': creator_degres.order_by('modified', 'id') \
                .annotate(country=Max(
                'creatordegreerevisions__creator__birth_country__id'))
          },
          {
            'object_name': 'Publishers',
            'object_type': 'publisher',
            'changesets': publishers.order_by('modified', 'id')\
              .annotate(country=Max('publisherrevisions__country__id')),
          },
          {
            'object_name': 'Indicia / Colophon Publishers',
            'object_type': 'indicia_publisher',
            'changesets': indicia_publishers.order_by('modified', 'id')\
              .annotate(country=Max('indiciapublisherrevisions__country__id')),
          },
          {
            'object_name': 'Brand Groups',
            'object_type': 'brand_groups',
            'changesets': brand_groups.order_by('modified', 'id')\
              .annotate(country=Max('brandgrouprevisions__parent__country__id')),
          },
          {
            'object_name': 'Brand Emblems',
            'object_type': 'brands',
            'changesets': brands.order_by('modified', 'id')\
              .annotate(country=Max('brandrevisions__group__parent__country__id')),
          },
          {
            'object_name': 'Brand Uses',
            'object_type': 'brand_uses',
            'changesets': brand_uses.order_by('modified', 'id')\
              .annotate(country=Max('branduserevisions__publisher__country__id')),
          },
          {
            'object_name': 'Series',
            'object_type': 'series',
            'changesets': series.order_by('modified', 'id')\
              .annotate(country=Max('seriesrevisions__country__id')),
          },
          {
            'object_name': 'Series Bonds',
            'object_type': 'series_bond',
            'changesets': series_bonds.order_by('modified', 'id')\
              .annotate(country=Max('seriesbondrevisions__origin__country__id')),
          },
          {
            'object_name': 'Features',
            'object_type': 'feature',
            'changesets': features.order_by('modified', 'id')
          },
          {
            'object_name': 'Feature Logos',
            'object_type': 'feature_logo',
            'changesets': feature_logos.order_by('modified', 'id')
          },
          {
            'object_name': 'Feature Relations',
            'object_type': 'feature_relations',
            'changesets': feature_relations.order_by('modified', 'id')
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
          {
            'object_name': 'Images',
            'object_type': 'image',
            'changesets': images.order_by('state', 'modified', 'id'),
          },
        ],
      }
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
      {'CTYPES': CTYPES, 'EDITING': True},
      per_page=50)


@login_required
def show_editor_log(request):
    changed_states = set(states.CLOSED+states.ACTIVE)
    changed_states.remove(states.REVIEWING)
    changes = Changeset.objects.order_by('-modified')\
                .filter(comments__old_state=states.REVIEWING,
                        comments__new_state__in=changed_states,
                        comments__commenter=request.user)\
                .exclude(indexer=request.user).distinct()
    return paginate_response(
      request,
      changes,
      'oi/queues/editor_log.html',
      {'CTYPES': CTYPES, 'EDITING': True},
      per_page=50)


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
      {'table_width' : table_width, 'EDITING': True},
      per_page=50,
      callback_key='tags',
      callback=get_preview_image_tags_per_page)


def compare(request, id):
    changeset = get_object_or_404(Changeset.objects\
                                  .prefetch_related('comments__commenter'),
                                  id=id)

    if changeset.inline():
        revision = changeset.inline_revision()
    elif changeset.change_type in [CTYPES['issue'], CTYPES['issue_add'],
                                   CTYPES['issue_bulk'], CTYPES['variant_add'],
                                   CTYPES['two_issues']]:
        revision = changeset.issuerevisions.all()[0]
    elif changeset.change_type == CTYPES['series_bond']:
        revision = changeset.seriesbondrevisions.all()[0]
    else:
        # never reached at the moment
        raise NotImplementedError

    model_name = revision.source_name
    if model_name == 'cover':
        return cover_compare(request, changeset, revision)
    if model_name == 'image':
        return image_compare(request, changeset, revision)

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
    sourced_fields = None
    group_sourced_fields = None
    revisions_before = []
    revisions_after = []
    # eliminate fields that shouldn't appear in the compare
    if model_name == 'series':
        if not revision.imprint and \
          (prev_rev is None or prev_rev.imprint is None):
            field_list.remove('imprint')
        if not revision.format and \
          (prev_rev is None or not prev_rev.format):
            field_list.remove('format')
        if not (revision.publication_notes or prev_rev and \
          prev_rev.publication_notes):
            field_list.remove('publication_notes')
    elif model_name in ['indicia_publisher']:
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
    elif changeset.change_type == CTYPES['creator']:
        sourced_fields = _get_creator_sourced_fields()
        sourced_fields['birth_date'] = 'birth_date'
        sourced_fields['death_date'] = 'death_date'
        group_sourced_fields = {'birth_city_uncertain': 'birth_place',
                                'death_city_uncertain': 'death_place'}
        creator_name_revisions = changeset.creatornamedetailrevisions.all()
        for creator_name_revision in creator_name_revisions:
            revisions_before.append(creator_name_revision)
            #if creator_name_revision.cr_to_name.count():
                #revisions_before.append(creator_name_revision\
                                        #.cr_to_name.get())
    elif changeset.change_type == CTYPES['creator_membership']:
        sourced_fields = {'': 'membership_year_ended_uncertain'}
    elif changeset.change_type == CTYPES['received_award']:
        sourced_fields = {'': 'award_year_uncertain'}
    elif changeset.change_type in [CTYPES['creator_art_influence'],
                                   CTYPES['creator_degree'],
                                   CTYPES['creator_non_comic_work'],
                                   CTYPES['creator_relation'],
                                   CTYPES['creator_school']]:
        sourced_fields = {'': 'notes'}
        
    for revision_before in revisions_before:
        revision_before.compare_changes()
    for revision_after in revisions_after:
        revision_after.compare_changes()

    response = oi_render(request, template,
                         {'changeset': changeset,
                          'revision': revision,
                          'revisions_before': revisions_before,
                          'revisions_after': revisions_after,
                          'prev_rev': prev_rev,
                          'post_rev': post_rev,
                          'changeset_type' : model_name.replace('_',' '),
                          'model_name': model_name,
                          'states': states,
                          'field_list': field_list,
                          'sourced_fields': sourced_fields,
                          'group_sourced_fields': group_sourced_fields,
                          'source_fields': ['source_description', 'source_type'],
                          'CTYPES': CTYPES},
                        )
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
    im = pyImage.open(source_name)
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

    response = oi_render(request, 'oi/edit/compare_cover.html', kwargs)
    response['Cache-Control'] = "no-cache, no-store, max-age=0, must-revalidate"
    return response


@login_required
def image_compare(request, changeset, revision):
    '''
    Compare page for images.
    - show uploaded image
    - for replacement show former image
    '''
    image_tag = get_preview_generic_image_tag(revision, "uploaded image")
    kwargs = {'changeset': changeset,
            'revision': revision,
            'image_tag' : image_tag,
            'states': states,
            'settings': settings}

    if changeset.state != states.APPROVED and revision.type.unique:
        if Image.objects.filter(content_type=\
                ContentType.objects.get_for_model(revision.object),
            object_id=revision.object.id, type=revision.type, deleted=False).count():
                kwargs['double_upload'] = '%s has an %s. Additional images ' \
                'cannot be uploaded, only replacements are possible.' \
                % (revision.object, revision.type.description)

    if revision.is_replacement:
        replaced_image = revision.previous()
        kwargs['replaced_image'] = replaced_image
        kwargs['replaced_image_tag'] = get_preview_generic_image_tag( \
                                        replaced_image, "replaced image")
        if changeset.state != states.APPROVED:
            kwargs['replaced_image_marked'] = revision.image.marked
            kwargs['replaced_image_file'] = revision.image.image_file
        else:
            kwargs['replaced_image_file'] = replaced_image.image_file

    response = oi_render(request, 'oi/edit/compare_image.html', kwargs)
    response['Cache-Control'] = "no-cache, no-store, max-age=0, must-revalidate"
    return response


@login_required
def preview(request, id, model_name):
    revision = get_object_or_404(REVISION_CLASSES[model_name], id=id)
    template = 'gcd/details/%s.html' % model_name

    if model_name in ['publisher', 'indicia_publisher', 'brand_group',
                      'brand', 'series', 'issue', 'award', 'creator',
                      'received_award', 'creator_art_influence',
                      'creator_degree', 'creator_membership',
                      'creator_non_comic_work', 'creator_school']:
        # TODO the model specific settings very likely should be methods
        #      on the revision
        if model_name == 'brand':
            # fake for brand emblems the group_set
            if revision.source:
                model_object = PreviewBrand(revision.source)
                for field in revision._get_irregular_fields():
                    setattr(model_object, field,
                            getattr(revision.source, field))
            else:
                model_object = PreviewBrand()
            model_object._group  = revision.group
        elif model_name == 'issue':
            # TODO add and use PreviewIssue.init
            if revision.source:
                model_object = PreviewIssue(revision.source)
                model_object.sort_code = revision.source.sort_code
            else:
                model_object = PreviewIssue()
                model_object.after = revision.after
            model_object.issuerevisions = revision.changeset.issuerevisions
            model_object.storyrevisions = revision.changeset.storyrevisions
            model_object.series = revision.series
            model_object.revision = revision
            model_object.on_sale_date = on_sale_date_as_string(revision)
            # on preview show all story types
            request.GET = request.GET.copy()
            request.GET['issue_detail'] = 2
        elif model_name == 'creator':
            model_object = PreviewCreator()
            model_object.revision = revision
        elif model_name == 'received_award':
            model_object = PreviewReceivedAward()
            model_object.revision = revision
        elif model_name == 'creator_art_influence':
            model_object = PreviewCreatorArtInfluence()
            model_object.revision = revision
        elif model_name == 'creator_degree':
            model_object = PreviewCreatorDegree()
            model_object.revision = revision
        elif model_name == 'creator_membership':
            model_object = PreviewCreatorMembership()
            model_object.revision = revision
        elif model_name == 'creator_non_comic_work':
            model_object = PreviewCreatorNonComicWork()
            model_object.revision = revision
        elif model_name == 'creator_school':
            model_object = PreviewCreatorSchool()
            model_object.revision = revision
        else:
            if revision.source:
                model_object = revision.source
            else:
                model_object = revision.source_class()
        if not revision.source:
            # this of course depends on there being no valid data with id 0
            model_object.id = 0
        else:
            model_object.id = revision.source.id
        revision._copy_fields_to(model_object)
        # keywords are a TextField for the revision, but a M2M-relation
        # for the model, overwrite for preview.
        # TODO should all have keywords ?
        if not model_name in ['award', 'creator', 'received_award',
                              'creator_art_influence', 'creator_degree',
                              'creator_membership', 'creator_non_comic_work',
                              'creator_school']:
            model_object.keywords = revision.keywords
        return globals()['show_%s' % (model_name)](request, model_object, True)
    return render_error(request,
      'No preview for "%s" revisions.' % model_name)

##############################################################################
# Mentoring
##############################################################################


@permission_required('indexer.can_contact')
def contacting(request):
    users = User.objects.filter(indexer__opt_in_email=True) \
                           .filter(is_active=True) \
                           .order_by('-date_joined') \
                           .select_related('indexer__country')

    return oi_render(
      request, 'oi/queues/contacting.html',
      {
        'users': users,
      })


@permission_required('indexer.can_mentor')
def mentoring(request):
    max_show_new = 50
    new_indexers = User.objects.filter(indexer__mentor=None) \
                               .filter(indexer__is_new=True) \
                               .filter(is_active=True) \
                               .order_by('-date_joined') \
                               .select_related('indexer__country')[:max_show_new]
    my_mentees = User.objects.filter(indexer__mentor=request.user) \
                             .filter(indexer__is_new=True) \
                             .select_related('indexer__country')
    mentees = User.objects.exclude(indexer__mentor=None) \
                          .filter(indexer__is_new=True) \
                          .exclude(indexer__mentor=request.user) \
                          .order_by('date_joined') \
                          .select_related('indexer__mentor__indexer',
                                          'indexer__country')

    return oi_render(
      request, 'oi/queues/mentoring.html',
      {
        'new_indexers': new_indexers,
        'my_mentees': my_mentees,
        'mentees': mentees,
        'max_show_new': max_show_new
      })


@permission_required('indexer.can_reserve')
def add_award(request):
    return add_generic(request, 'award')


@permission_required('indexer.can_reserve')
def add_creator_award(request, creator_id):
    if not request.user.indexer.can_reserve_another():
        return render_error(request, REACHED_CHANGE_LIMIT)

    creator = get_object_or_404(Creator, id=creator_id, deleted=False)

    if creator.pending_deletion():
        return render_error(request, 'Cannot add Award for '
                                     'creator "%s" since the record is '
                                     'pending deletion.' % creator)

    if request.method == 'GET':
        award_form = ReceivedAwardRevisionForm()

    elif request.method == 'POST':
        if 'cancel' in request.POST:
            return HttpResponseRedirect(urlresolvers.reverse(
                    'show_creator', kwargs={'creator_id': creator_id}))

        award_form = ReceivedAwardRevisionForm(
                request.POST or None,
                request.FILES or None,
        )
        if award_form.is_valid():
            changeset = Changeset(indexer=request.user, state=states.OPEN,
                                    change_type=CTYPES['received_award'])
            changeset.save()
            revision = award_form.save(commit=False)
            revision.save_added_revision(changeset=changeset,
                                         recipient=creator,
                                         award=award_form.cleaned_data['award'])
            revision.save()

            process_data_source(award_form, '', changeset,
                                sourced_revision=revision)

            return submit(request, changeset.id)

    context = {'form': award_form,
               'object_name': 'Award of a Creator',
               'object_url': urlresolvers.reverse('add_creator_award',
                                                  kwargs={'creator_id':
                                                          creator_id}),
               'action_label': 'Submit new',
               'settings': settings}
    return oi_render(request, 'oi/edit/add_frame.html', context)


@permission_required('indexer.can_reserve')
def add_received_award(request, award_id, model_name, id):
    award = get_object_or_404(Award, id=award_id)

    if award.pending_deletion():
        return render_error(request, 'Cannot add to Award "%s" since the '
                                     'record is pending deletion.' % award)

    if request.method == 'POST' and 'cancel' in request.POST:
        return HttpResponseRedirect(urlresolvers.reverse('show_award',
          kwargs={ 'id': data['award_id'] }))

    form = get_received_award_revision_form(user=request.user)(request.POST 
                                                               or None)

    if model_name == 'story':
        selected_object = get_object_or_404(Story, id=id)
    elif model_name == 'issue':
        selected_object = get_object_or_404(Issue, id=id)
    elif model_name == 'series':
        selected_object = get_object_or_404(Series, id=id)
    else:
        raise NotImplementedError

    if form.is_valid():
        changeset = Changeset(indexer=request.user, state=states.OPEN,
                                change_type=CTYPES['received_award'])
        changeset.save()
        revision = form.save(commit=False)
        revision.save_added_revision(changeset=changeset,
                                      recipient=selected_object,
                                      award=award)
        revision.save()

        process_data_source(form, '', changeset,
                            sourced_revision=revision)

        return submit(request, changeset.id)

    extra_adding_info = 'the Award: %s for %s: %s' % (award,
                                                      model_name.capitalize(),
                                                      selected_object)

    return oi_render(request, 'oi/edit/add_frame.html',
        {'action_label': 'Submit new received award',
         'form': form,
         'extra_adding_info': extra_adding_info,
         'object_url': urlresolvers.reverse('add_received_award',
                                            kwargs={'award_id': award.id,
                                                    'model_name': model_name,
                                                    'id': selected_object.id}),
        })


@permission_required('indexer.can_reserve')
def process_award_recipient(request, data, object_type, selected_id):
    if request.method != 'POST':
        return _cant_get(request)
    if 'cancel' in request.POST:
        return HttpResponseRedirect(urlresolvers.reverse('show_award',
          kwargs={ 'id': data['award_id'] }))

    return HttpResponseRedirect(urlresolvers.reverse('add_received_award',
                                            kwargs={'award_id': data['award_id'],
                                                    'model_name': object_type,
                                                    'id': selected_id}))


@permission_required('indexer.can_reserve')
def select_award_recipient(request, award_id):
    if not request.user.indexer.can_reserve_another():
        return render_error(request, REACHED_CHANGE_LIMIT)

    award = get_object_or_404(Award, id=award_id)
    heading = 'Select recipient for an %s award' % (esc(award))

    data = {'award_id': award_id,
            'story': True,
            'issue': True,
            'series': True,
            'heading': mark_safe('<h2>%s</h2>' % heading),
            'target': 'a story, issue, or series',
            'return': process_award_recipient,
            'cancel': HttpResponseRedirect(urlresolvers.reverse('show_award',
                        kwargs={'award_id': award_id}))}
    select_key = store_select_data(request, None, data)
    return HttpResponseRedirect(urlresolvers.reverse('select_object',
          kwargs={'select_key': select_key}))


@permission_required('indexer.can_reserve')
def add_creator(request):
    if not request.user.indexer.can_reserve_another():
        return render_error(request, REACHED_CHANGE_LIMIT)

    if request.method == 'POST' and 'cancel' in request.POST:
        return HttpResponseRedirect(reverse('add'))

    creator_form = get_creator_revision_form(user=request.user)(request.POST or None)
    form_class = get_date_revision_form(user=request.user,
                                        date_help_links=CREATOR_HELP_LINKS)
    birth_date_form = form_class(request.POST or None, prefix='birth_date')
    death_date_form = form_class(request.POST or None, prefix='death_date')

    creator_names_formset = CreatorRevisionFormSet(request.POST or None)

    if not creator_form.is_valid() or not creator_names_formset.is_valid()\
      or not birth_date_form.is_valid() or not death_date_form.is_valid():
        birth_date_form.fields['date'].label = 'Birth date'
        death_date_form.fields['date'].label = 'Death date'

        context = {'form': creator_form,
                   'creator_names_formset': creator_names_formset,
                   'birth_date_form': birth_date_form,
                   'death_date_form': death_date_form,
                   'object_name': 'Creator',
                   'object_url': urlresolvers.reverse('add_creator'),
                   'action_label': 'Submit new',
                   'mode': 'new',
                   'settings': settings}
        return oi_render(request, 'oi/edit/add_frame.html', context)

    changeset = Changeset(indexer=request.user, state=states.OPEN,
                          change_type=CTYPES['creator'])
    changeset.save()
    revision = creator_form.save(commit=False)
    revision.save_added_revision(changeset=changeset)
    revision.gcd_official_name = "Dummy"
    extra_forms = {'creator_names_formset': creator_names_formset,
                   'birth_date_form': birth_date_form,
                   'death_date_form': death_date_form
                   }
    revision.process_extra_forms(request, extra_forms)

    for field in _get_creator_sourced_fields():
        process_data_source(creator_form, field, revision.changeset,
                            sourced_revision=revision)
    return submit(request, changeset.id)


@permission_required('indexer.can_reserve')
def add_creator_relation(request, creator_id):
    if not request.user.indexer.can_reserve_another():
        return render_error(request, REACHED_CHANGE_LIMIT)
    
    creator = get_object_or_404(Creator, id=creator_id, deleted=False)

    if creator.pending_deletion():
        return render_error(request, 'Cannot add Relation for '
                                     'creator "%s" since the record is '
                                     'pending deletion.' % creator)

    if request.method == 'POST' and 'cancel' in request.POST:
        return HttpResponseRedirect(urlresolvers.reverse(
                'show_creator', kwargs={'creator_id': creator_id}))

    initial = {}
    initial['from_creator'] = creator
    relation_form = CreatorRelationRevisionForm(request.POST or None,
                                                initial=initial)


    if relation_form.is_valid():
        changeset = Changeset(indexer=request.user, state=states.OPEN,
                              change_type=CTYPES['creator_relation'])
        changeset.save()

        revision = relation_form.save(commit=False)
        revision.save_added_revision(changeset=changeset, creator=creator)
        revision.save()

        process_data_source(relation_form, '', changeset,
                            sourced_revision=revision)

        return submit(request, changeset.id)

    context = {'form': relation_form,
               'object_name': 'Relation with Creator',
               'object_url': urlresolvers.reverse('add_creator_relation',
                                                  kwargs={'creator_id': creator_id}),
               'action_label': 'Submit new',
               'settings': settings}
    return oi_render(request, 'oi/edit/add_frame.html', context)


@permission_required('indexer.can_reserve')
def add_creator_school(request, creator_id):
    if not request.user.indexer.can_reserve_another():
        return render_error(request, REACHED_CHANGE_LIMIT)
    
    creator = get_object_or_404(Creator, id=creator_id, deleted=False)

    if creator.pending_deletion():
        return render_error(request, 'Cannot add School for '
                                     'creator "%s" since the record is '
                                     'pending deletion.' % creator)

    if request.method == 'POST' and 'cancel' in request.POST:
        return HttpResponseRedirect(urlresolvers.reverse(
                'show_creator', kwargs={'creator_id': creator_id}))

    school_form = CreatorSchoolRevisionForm(request.POST or None)

    if school_form.is_valid():
        changeset = Changeset(indexer=request.user, state=states.OPEN,
                                change_type=CTYPES['creator_school'])
        changeset.save()

        revision = school_form.save(commit=False)
        revision.save_added_revision(changeset=changeset, creator=creator)
        revision.save()

        process_data_source(school_form, '', changeset,
                            sourced_revision=revision)

        return submit(request, changeset.id)

    context = {'form': school_form,
               'object_name': 'School of a Creator',
               'object_url': urlresolvers.reverse('add_creator_school',
                                                  kwargs={'creator_id': creator_id}),
               'action_label': 'Submit new',
               'settings': settings}
    return oi_render(request, 'oi/edit/add_frame.html', context)


@permission_required('indexer.can_reserve')
def add_creator_degree(request, creator_id):
    if not request.user.indexer.can_reserve_another():
        return render_error(request, REACHED_CHANGE_LIMIT)
    
    creator = get_object_or_404(Creator, id=creator_id, deleted=False)

    if creator.pending_deletion():
        return render_error(request, 'Cannot add School Degree for '
                                     'creator "%s" since the record is '
                                     'pending deletion.' % creator)

    if request.method == 'POST' and 'cancel' in request.POST:
        return HttpResponseRedirect(urlresolvers.reverse(
                'show_creator', kwargs={'creator_id': creator_id}))

    degree_form = CreatorDegreeRevisionForm(request.POST or None)

    if degree_form.is_valid():
        changeset = Changeset(indexer=request.user, state=states.OPEN,
                              change_type=CTYPES['creator_degree'])
        changeset.save()

        revision = degree_form.save(commit=False)
        revision.save_added_revision(changeset=changeset, creator=creator)
        revision.save()

        process_data_source(degree_form, '', changeset,
                            sourced_revision=revision)

        return submit(request, changeset.id)

    context = {'form': degree_form,
               'object_name': 'School Degree of a Creator',
               'object_url': urlresolvers.reverse('add_creator_degree',
                                                  kwargs={'creator_id': creator_id}),
               'action_label': 'Submit new',
               'settings': settings}
    return oi_render(request, 'oi/edit/add_frame.html', context)


@permission_required('indexer.can_reserve')
def add_creator_membership(request, creator_id):
    if not request.user.indexer.can_reserve_another():
        return render_error(request, REACHED_CHANGE_LIMIT)

    creator = get_object_or_404(Creator, id=creator_id, deleted=False)

    if creator.pending_deletion():
        return render_error(request, 'Cannot add Membership '
                                        'creators since "%s" is deleted or '
                                        'pending deletion.' % creator)

    if request.method == 'GET':
        membership_form = CreatorMembershipRevisionForm()

    elif request.method == 'POST':
        if 'cancel' in request.POST:
            return HttpResponseRedirect(urlresolvers.reverse(
                    'show_creator', kwargs={'creator_id': creator_id}))

        membership_form = CreatorMembershipRevisionForm(
                request.POST or None,
                request.FILES or None,
        )
        if membership_form.is_valid():
            changeset = Changeset(indexer=request.user, state=states.OPEN,
                                    change_type=CTYPES['creator_membership'])
            changeset.save()

            revision = membership_form.save(commit=False)

            revision.save_added_revision(changeset=changeset, creator=creator)
            revision.save()

            process_data_source(membership_form, '', changeset,
                                sourced_revision=revision)

            return submit(request, changeset.id)


    context = {'form': membership_form,
               'object_name': 'Membership of a Creator',
               'object_url': urlresolvers.reverse('add_creator_membership',
                                                  kwargs={'creator_id': creator_id}),
               'action_label': 'Submit new',
               'settings': settings}
    return oi_render(request, 'oi/edit/add_frame.html', context)


@permission_required('indexer.can_reserve')
def add_creator_art_influence(request, creator_id):
    if not request.user.indexer.can_reserve_another():
        return render_error(request, REACHED_CHANGE_LIMIT)

    creator = get_object_or_404(Creator, id=creator_id, deleted=False)

    if creator.pending_deletion():
        return render_error(request, 'Cannot add Art Influence for '
                                     'creator "%s" since the record is '
                                     'pending deletion.' % creator)

    if request.method == 'GET':
        artinfluence_form = CreatorArtInfluenceRevisionForm()

    elif request.method == 'POST':
        if 'cancel' in request.POST:
            return HttpResponseRedirect(urlresolvers.reverse(
                    'show_creator', kwargs={'creator_id': creator_id}))

        artinfluence_form = CreatorArtInfluenceRevisionForm(
                request.POST or None,
                request.FILES or None,
        )
        if artinfluence_form.is_valid():
            changeset = Changeset(indexer=request.user, state=states.OPEN,
                                    change_type=CTYPES[
                                        'creator_art_influence'])
            changeset.save()

            revision = artinfluence_form.save(commit=False)

            revision.save_added_revision(changeset=changeset, creator=creator)
            revision.save()

            process_data_source(artinfluence_form, '', changeset,
                                sourced_revision=revision)
            return submit(request, changeset.id)

    context = {'form': artinfluence_form,
               'object_name': 'Art Influence of a Creator',
               'object_url': urlresolvers.reverse('add_creator_art_influence',
                                                  kwargs={'creator_id': creator_id}),
               'action_label': 'Submit new',
               'settings': settings}
    return oi_render(request, 'oi/edit/add_frame.html', context)


@permission_required('indexer.can_reserve')
def add_creator_non_comic_work(request, creator_id):
    if not request.user.indexer.can_reserve_another():
        return render_error(request, REACHED_CHANGE_LIMIT)

    creator = get_object_or_404(Creator, id=creator_id, deleted=False)

    creator = Creator.objects.get(id=creator_id)
    if creator.deleted or creator.pending_deletion():
        return render_error(request, 'Cannot add NonComicWork '
                                        'creators since "%s" is deleted or '
                                        'pending deletion.' % creator)

    if request.method == 'GET':
        noncomicwork_form = CreatorNonComicWorkRevisionForm()

    elif request.method == 'POST':
        if 'cancel' in request.POST:
            return HttpResponseRedirect(urlresolvers.reverse(
                    'show_creator',
                    kwargs={'creator_id': creator_id}))

        noncomicwork_form = CreatorNonComicWorkRevisionForm(
                request.POST or None,
                request.FILES or None,
        )
        if noncomicwork_form.is_valid():
            changeset = Changeset(indexer=request.user, state=states.OPEN,
                                    change_type=CTYPES[
                                        'creator_non_comic_work'])
            changeset.save()

            revision = noncomicwork_form.save(commit=False)

            revision.save_added_revision(changeset=changeset, creator=creator)
            revision.save()

            process_data_source(noncomicwork_form, '', changeset,
                                sourced_revision=revision)
            return submit(request, changeset.id)

    context = {'form': noncomicwork_form,
               'object_name': 'Non Comic Work of a Creator',
               'object_url': urlresolvers.reverse('add_creator_non_comic_work',
                                                  kwargs={'creator_id': creator_id}),
               'action_label': 'Submit new',
               'settings': settings}
    return oi_render(request, 'oi/edit/add_frame.html', context)
