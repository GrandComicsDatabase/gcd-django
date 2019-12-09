# -*- coding: utf-8 -*-
import PIL.Image as pyImage
import os
import shutil
import glob

from django.core import urlresolvers
from django.conf import settings
from django.shortcuts import render, get_object_or_404
from django.core.files import File
from django.utils.safestring import mark_safe
from django.utils.html import conditional_escape as esc
from django.http import HttpResponseRedirect
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.contenttypes.models import ContentType
from apps.indexer.views import render_error

from apps.gcd.models import Cover, Issue, Image
from apps.gcd.views.covers import get_image_tag, get_image_tags_per_issue, \
                                  get_generic_image_tag

from apps.oi.models import (
  Changeset, CoverRevision, ImageRevision, IssueRevision, StoryRevision,
  StoryType, ImageType, CTYPES, states,
  _get_revision_lock, _free_revision_lock)
from apps.oi.forms import UploadScanForm, UploadVariantScanForm, \
                          GatefoldScanForm, UploadImageForm
from apps.oi.templatetags.editing import is_locked

from apps.gcd.models.cover import ZOOM_SMALL, ZOOM_MEDIUM, ZOOM_LARGE

# table width for displaying the medium sized current and active covers
UPLOAD_WIDTH = 3

SHOW_GATEFOLD_WIDTH = 1000

# where to put our covers,
LOCAL_NEW_SCANS = settings.NEW_COVERS_DIR

NEW_COVERS_LOCATION = settings.IMAGE_SERVER_URL + settings.NEW_COVERS_DIR
# only while testing:
NEW_COVERS_LOCATION = settings.MEDIA_URL + LOCAL_NEW_SCANS


def get_preview_generic_image_tag(revision, alt_text):
    img_class = 'cover_img'
    if revision.image_file:
        width = min(revision.image_file.width, 400)
        return mark_safe('<img src="' + revision.scaled_image.url + '" alt="' + esc(alt_text) \
                + '" ' + ' class="' + img_class + '" width="' + str(width) + '"/>')
    elif revision.deleted:
        return get_generic_image_tag(revision.image, esc(alt_text))
    else:
        last_revision = ImageRevision.objects.filter(image=revision.image,
          changeset__change_type=CTYPES['image'],
          changeset__state=states.APPROVED).order_by('-created')[0]
        if revision==last_revision:
            # Current cover is the one from this revision, show it.
            return get_generic_image_tag(revision.image, esc(alt_text))
        else:
            if settings.BETA:
                return 'no old images on BETA'

def get_preview_image_tag(revision, alt_text, zoom_level, request=None):
    if revision is None:
        return mark_safe('<img class="no_cover" src="' + settings.STATIC_URL + \
               'img/nocover.gif" alt="No image yet" class="cover_img"/>')

    img_class = 'cover_img'
    if zoom_level == ZOOM_SMALL:
        width = 100
        size = 'small'
        if revision.is_wraparound:
            img_class = 'wraparound_cover_img'
    elif zoom_level == ZOOM_MEDIUM:
        width = 200
        size = 'medium'
        if revision.is_wraparound:
            img_class = 'wraparound_cover_img'
    elif zoom_level == ZOOM_LARGE:
        width = 400
        size = 'large'

    if revision.changeset.state == states.APPROVED:
        current_cover = CoverRevision.objects.filter(cover=revision.cover,
          changeset__change_type=CTYPES['cover'],
          changeset__state=states.APPROVED).order_by('-created')[0]
        if revision==current_cover:
            # Current cover is the one from this revision, show it.
            return get_image_tag(revision.cover, esc(alt_text), zoom_level)
        else:
            if request and request.user.has_perm('indexer.can_approve') \
              and not settings.BETA:
                # The cover was replaced by now, show original uploaded file,
                # scaled in the browser.
                # It is the real uploaded file for uploads on the new server, and
                # the large scan for older uploads, copied on replacement.
                suffix = "/uploads/%d_%s" % (revision.cover.id,
                        revision.changeset.created.strftime('%Y%m%d_%H%M%S'))
                if revision.created > settings.NEW_SITE_COVER_CREATION_DATE:
                    filename = glob.glob(revision.cover.base_dir() + suffix + '*')[0]
                    file_extension = os.path.splitext(filename)[1]
                else:
                    file_extension = ".jpg"
                # TODO:
                suffix = "%d/uploads/%d_%s" % (int(revision.cover.id/1000),
                        revision.cover.id,
                        revision.changeset.created.strftime('%Y%m%d_%H%M%S'))
                img_url = settings.IMAGE_SERVER_URL + settings.COVERS_DIR +\
                        suffix + file_extension
                # for old covers do manual scaling, since it is the uploaded file
                return mark_safe('<img src="' + img_url + '" alt="' + \
                esc(alt_text) + '" width="' + str(width) + \
                '" class="' + img_class + '"/>')
            elif settings.BETA:
                return 'no old covers on BETA'
            else:
                return 'only editors can view covers which were replaced'
    elif revision.deleted:
        return get_image_tag(revision.cover, esc(alt_text), zoom_level)
    else:
        suffix = "w%d/%d.jpg" % (width, revision.id)
        img_url = NEW_COVERS_LOCATION + \
          revision.changeset.created.strftime('%B_%Y/').lower() + suffix
        return mark_safe('<img src="' + img_url + '" alt="' + esc(alt_text) \
               + '" ' + ' class="' + img_class + '"/>')


def get_preview_image_tags_per_page(page, series=None):
    """
    Produces a list of cover tags for the pending covers in a page.
    Intended for use as a callback with paginate_response().
    """

    cover_tags = []
    for change in page.object_list:
        # TODO if we ever do bulk uploads of covers this might need to change,
        # although we might generate one changeset for each cover there as well
        cover = change.coverrevisions.select_related('changeset__indexer',
                                     'issue__series__publisher').all()[0]
        issue = cover.issue
        alt_string = issue.series.name + ' #' + issue.number
        cover_tags.append([cover, issue, get_preview_image_tag(cover,
                                                               alt_string,
                                                               ZOOM_SMALL)])
    return cover_tags


def _create_cover_dir(scan_dir):
    # server error if something goes wrong here needs to checked by caller
    if not os.path.isdir(scan_dir):
        os.mkdir(scan_dir)
        return True
    return False

def check_cover_dir(scan_dir):
    """
    Checks if the necessary cover directories exist and creates
    them if necessary.
    """
    # assuming here that the creation of the subdirs worked
    if _create_cover_dir(scan_dir):
        _create_cover_dir(scan_dir + "/uploads")
        for width in [100, 200, 400]:
            _create_cover_dir(scan_dir + "/w" + str(width))

def copy_approved_cover(cover_revision):
    cover = cover_revision.cover
    # here we want a server error to get notice to the admins
    # that the file transfer did not take place
    check_cover_dir(cover.base_dir())

    # replacement cover
    if cover_revision.is_replacement:
        # get current cover
        old_cover = CoverRevision.objects.filter(cover=cover,
          changeset__change_type=CTYPES['cover'],
          changeset__state=states.APPROVED).order_by('-created')[0]
        if old_cover.created <= settings.NEW_SITE_COVER_CREATION_DATE:
            # uploaded file too old, not stored, copy large file
            suffix = "/uploads/%d_%s.jpg" % (cover.id,
                     old_cover.changeset.created.strftime('%Y%m%d_%H%M%S'))
            target_name = cover.base_dir() + suffix
            source_name = cover.base_dir() + "/w400/%d.jpg" % cover.id
            shutil.move(source_name, target_name)

    source_name = glob.glob(cover_revision.base_dir() + \
                            str(cover_revision.id) + '*')[0]

    target_name = "%s/uploads/%d_%s%s" % (cover.base_dir(), cover.id,
                    cover_revision.changeset.created.strftime('%Y%m%d_%H%M%S'),
                    os.path.splitext(source_name)[1])
    shutil.move(source_name, target_name)

    for width in [100, 200, 400]:
        source_name = "%s/w%d/%d.jpg" % (cover_revision.base_dir(), width,
                                         cover_revision.id)
        target_name = "%s/w%d/%d.jpg" % (cover.base_dir(), width, cover.id)
        shutil.move(source_name, target_name)


def generate_sizes(cover, im):
    base_dir = cover.base_dir()
    if im.mode != "RGB":
        im = im.convert("RGB")

    if cover.is_wraparound:
        # coordinates in PIL are measured from the top/left corner
        front_part = im.crop((cover.front_left, cover.front_top,
                              cover.front_right, cover.front_bottom))
        full_cover = im
        im = front_part

    for width in [100, 200, 400]:
        scaled_name = "%s/w%d/%d.jpg" % (base_dir, width, cover.id)
        if cover.is_wraparound and width == 400:
            # ratio between widths of full cover and its front part times 400
            width = float(full_cover.size[0]) / \
                    float(cover.front_right - cover.front_left)*400.
            size = int(width), \
                   int(width / full_cover.size[0] * full_cover.size[1])
            if size[1] < 400:
                size = int(full_cover.size[0]*400./full_cover.size[1]), 400
            scaled = full_cover.resize(size, pyImage.ANTIALIAS)
        else:
            if width == 400 and im.size[0] > im.size[1]:
                # for landscape covers use height as base size
                size = int(float(width)/im.size[1]*im.size[0]), width
            else:
                size = width, int(float(width)/im.size[0]*im.size[1])
            scaled = im.resize(size, pyImage.ANTIALIAS)
        scaled.save(scaled_name, subsampling='4:4:4')


@login_required
def edit_covers(request, issue_id):
    """
    Overview of covers for an issue and possible actions
    """

    issue = get_object_or_404(Issue, id=issue_id)
    if issue.has_covers():
        covers = get_image_tags_per_issue(issue, "current covers", ZOOM_MEDIUM,
                                          as_list=True, variants=True)
        return render(
          request,
          'oi/edit/edit_covers.html',
          {'issue': issue,
           'covers': covers,
           'table_width': UPLOAD_WIDTH
          })
    else:
        return upload_cover(request, issue_id=issue_id)


def needed_issue_list(objects, issue, cover=False):
    num_show_issues = 14
    if cover:
        earlier = objects.filter(issue__sort_code__lt=issue.sort_code) \
                         .order_by('-issue__sort_code')
        later = objects.filter(issue__sort_code__gt=issue.sort_code) \
                       .order_by('issue__sort_code')
    else:
        earlier = objects.filter(sort_code__lt=issue.sort_code) \
                         .order_by('-sort_code')
        later = objects.filter(sort_code__gt=issue.sort_code) \
                       .order_by('sort_code')
    if earlier.count() + later.count() > num_show_issues:
        if earlier.count() < num_show_issues/2:
            later = later[:num_show_issues - earlier.count()]
        elif later.count() < num_show_issues/2:
            earlier = earlier[:num_show_issues - later.count()]
        else:
            later = later[:7]
            earlier = earlier[:7]
    earlier = list(earlier)
    earlier.reverse()
    return earlier + list(later)

@login_required
def uploaded_cover(request, revision_id):
    """
    On successful upload display the cover and show further possibilities
    """
    uploaded_template = 'oi/edit/upload_cover_complete.html'

    # what other covers do we need
    # TODO change this code
    # - add discard button for undo of wrong upload
    # - ...
    revision = get_object_or_404(CoverRevision, id=revision_id)
    issue = revision.issue

    blank_issues = needed_issue_list(issue.series.active_issues() \
                                          .exclude(cover__isnull=False,
                                                   cover__deleted=False),
                                     issue)
    marked_covers = needed_issue_list(Cover.objects \
                                      .filter(issue__series=issue.series,
                                              deleted=False,
                                              marked=True),
                                      issue, cover=True)
    tag = get_preview_image_tag(revision, "uploaded cover", ZOOM_MEDIUM)
    return render(request, uploaded_template,
                  {'marked_covers' : marked_covers,
                   'blank_issues' : blank_issues,
                   'revision': revision,
                   'issue' : issue,
                   'tag'   : tag})

def process_edited_gatefold_cover(request):
    ''' process the edited gatefold cover and generate CoverRevision '''

    if request.method != 'POST':
        return render_error(request,
            'This page may only be accessed through the proper form',
            redirect=False)

    form = GatefoldScanForm(request.POST)
    if not form.is_valid():
        error_text = 'Error: Something went wrong in the file upload.'
        return render_error(request, error_text, redirect=False)
    cd = form.cleaned_data

    tmpdir = settings.MEDIA_ROOT + LOCAL_NEW_SCANS + 'tmp'
    scan_name = cd['scan_name']
    tmp_name = os.path.join(tmpdir, scan_name)

    if 'discard' in request.POST:
        os.remove(tmp_name)
        return HttpResponseRedirect(urlresolvers.reverse('edit_covers',
                kwargs={'issue_id': cd['issue_id']} ))

    # create OI records
    changeset = Changeset(indexer=request.user, state=states.OPEN,
                            change_type=CTYPES['cover'])

    if cd['cover_id']:
        cover = get_object_or_404(Cover, id=cd['cover_id'])
        issue = cover.issue
        # check if there is a pending change for the cover
        revision_lock = _get_revision_lock(cover)
        if not revision_lock:
            return render_error(
              request,
              'Cannot replace %s as it is already reserved.' %
              cover.issue)
        changeset.save()
        revision_lock.changeset = changeset
        revision_lock.save()

        revision = CoverRevision(changeset=changeset, issue=issue,
            cover=cover, file_source=cd['source'], marked=cd['marked'],
            is_replacement = True)
    # no cover_id, therefore upload a cover to an issue (first or variant)
    else:
        changeset.save()
        issue = get_object_or_404(Issue, id=cd['issue_id'])
        cover = None
        revision = CoverRevision(changeset=changeset, issue=issue,
            file_source=cd['source'], marked=cd['marked'])
    revision.save()

    scan_name = str(revision.id) + os.path.splitext(tmp_name)[1]
    upload_dir = settings.MEDIA_ROOT + LOCAL_NEW_SCANS + \
                   changeset.created.strftime('%B_%Y').lower()
    destination_name = os.path.join(upload_dir, scan_name)
    try: # essentially only needed at beginning of the month
        check_cover_dir(upload_dir)
    except IOError:
        changeset.delete()
        error_text = "Problem with file storage for uploaded " + \
                        "cover, please report an error."
        return render_error(request, error_text, redirect=False)

    shutil.move(tmp_name, destination_name)

    im = pyImage.open(destination_name)
    revision.is_wraparound = True
    # convert from scaled to real values
    width = cd['width']
    height = cd['height']
    left = cd['left']
    top = cd['top']
    revision.front_left = left
    revision.front_right = left + width
    revision.front_top = top
    revision.front_bottom = top + height
    revision.save()
    generate_sizes(revision, im)

    return finish_cover_revision(request, revision, cd)


def handle_gatefold_cover(request, cover, issue, form):
    ''' process the uploaded file in case of a gatefold cover '''

    cd = form.cleaned_data
    scan = cd['scan']
    source = cd['source']
    remember_source = cd['remember_source']
    marked = cd['marked']
    comments = cd['comments']
    # we cannot use the system tmp directory due to apache security settings
    # use media/img/gcd/new_covers/tmp and accept that it could fill up with
    # abandoned files
    tmpdir = settings.MEDIA_ROOT + LOCAL_NEW_SCANS + 'tmp'
    if cover: # upload_type is 'replacement':
        scan_name = "%d_%d_%d" % (request.user.id, issue.id, cover.id)
    else:
        scan_name = "%d_%d" % (request.user.id, issue.id)
    scan_name += os.path.splitext(scan.name)[1]
    destination_name = os.path.join(tmpdir, scan_name)
    # write uploaded file to tmp-dir
    destination = open(destination_name, 'wb')
    for chunk in scan.chunks():
        destination.write(chunk)
    destination.close()
    im = pyImage.open(destination.name)
    if min(im.size) <= 400:
        os.remove(destination.name)
        info_text = "Image is too small, only " + str(im.size) + \
                    " in size."
        return _display_cover_upload_form(request, form, cover, issue,
            info_text=info_text)

    vars = {'issue_id': issue.id, 'marked': marked, 'scan_name': scan_name,
            'source': source, 'remember_source': remember_source,
            'comments': comments, 'real_width': im.size[0]}
    if cover:
        vars['cover_id'] = cover.id
        #  gatefold cover replacement might not be done till the end
        _free_revision_lock(cover)

    form = GatefoldScanForm(initial=vars)

    return render(request, 'oi/edit/upload_gatefold_cover.html',
                  {'remember_source': remember_source,
                   'scan_name': scan_name,
                   'form': form,
                   'issue': issue,
                   'width': min(SHOW_GATEFOLD_WIDTH, im.size[0])})


def handle_uploaded_cover(request, cover, issue, variant=False,
                          revision_lock=None):
    ''' process the uploaded file and generate CoverRevision '''

    try:
        if variant:
            form = UploadVariantScanForm(request.POST, request.FILES)
        else:
            form = UploadScanForm(request.POST, request.FILES)
    except IOError: # sometimes uploads misbehave. connection dropped ?
        error_text = 'Something went wrong with the upload. ' + \
                        'Please <a href="' + request.path + '">try again</a>.'
        return render_error(request, error_text, redirect=False,
            is_safe=True)

    if not form.is_valid():
        return _display_cover_upload_form(request, form, cover, issue,
                                          variant=variant)

    # process form
    if form.cleaned_data['is_gatefold']:
        return handle_gatefold_cover(request, cover, issue, form)
    scan = form.cleaned_data['scan']
    file_source = form.cleaned_data['source']
    marked = form.cleaned_data['marked']

    # create OI records
    changeset = Changeset(indexer=request.user, state=states.OPEN,
                            change_type=CTYPES['cover'])
    changeset.save()

    if cover: # upload_type is 'replacement':
        revision = CoverRevision(changeset=changeset, issue=issue,
            cover=cover, file_source=file_source, marked=marked,
            is_replacement = True)
        revision_lock.changeset = changeset
        revision_lock.save()
        revision.previous_revision = cover.revisions.get(
                                           next_revision=None,
                                           changeset__state=states.APPROVED,
                                           committed=True)
    else:
        revision = CoverRevision(changeset=changeset, issue=issue,
            file_source=file_source, marked=marked)
    revision.save()

    # if uploading a variant, generate an issue_revision for
    # the variant issue and copy the values which would not change
    # TODO are these reasonable assumptions below ?
    if variant:
        current_variants = issue.variant_set.all().order_by('-sort_code')
        if current_variants:
            add_after = current_variants[0]
        else:
            add_after = issue
        issue_revision = IssueRevision(changeset=changeset,
          after=add_after,
          number=issue.number,
          title=issue.title,
          no_title=issue.no_title,
          volume=issue.volume,
          no_volume=issue.no_volume,
          display_volume_with_number=issue.display_volume_with_number,
          variant_of=issue,
          variant_name=form.cleaned_data['variant_name'],
          page_count=issue.page_count,
          page_count_uncertain=issue.page_count_uncertain,
          series=issue.series,
          editing=issue.editing,
          no_editing=issue.no_editing,
          reservation_requested=form.cleaned_data['reservation_requested']
          )
        issue_revision.save()
        if form.cleaned_data['variant_artwork']:
            story_revision = StoryRevision(changeset=changeset,
              type=StoryType.objects.get(name='cover'),
              no_script=True,
              pencils='?',
              inks='?',
              colors='?',
              no_letters=True,
              no_editing=True,
              sequence_number=0,
              page_count=2 if form.cleaned_data['is_wraparound'] else 1,
              )
            story_revision.save()
    # put new uploaded covers into
    # media/<LOCAL_NEW_SCANS>/<monthname>_<year>/
    # with name
    # <revision_id>_<date>_<time>.<ext>
    scan_name = str(revision.id) + os.path.splitext(scan.name)[1]
    upload_dir = settings.MEDIA_ROOT + LOCAL_NEW_SCANS + \
                   changeset.created.strftime('%B_%Y').lower()
    destination_name = os.path.join(upload_dir, scan_name)
    try: # essentially only needed at beginning of the month
        check_cover_dir(upload_dir)
    except IOError:
        changeset.delete()
        error_text = "Problem with file storage for uploaded " + \
                        "cover, please report an error."
        return render_error(request, error_text, redirect=False)

    # write uploaded file
    destination = open(destination_name, 'wb')
    for chunk in scan.chunks():
        destination.write(chunk)
    destination.close()

    try:
        # generate different sizes we are using
        im = pyImage.open(destination.name)
        large_enough = False
        if form.cleaned_data['is_wraparound']:
            # wraparounds need to have twice the width
            if im.size[0] >= 800 and im.size[1] >= 400:
                large_enough = True
        elif min(im.size) >= 400:
            large_enough = True
        if large_enough:
            if form.cleaned_data['is_wraparound']:
                revision.is_wraparound = True
                revision.front_left = im.size[0]/2
                revision.front_right = im.size[0]
                revision.front_bottom = im.size[1]
                revision.front_top = 0
                revision.save()
            generate_sizes(revision, im)
        else:
            changeset.delete()
            os.remove(destination.name)
            info_text = "Image is too small, only " + str(im.size) + \
                        " in size."
            return _display_cover_upload_form(request, form, cover, issue,
                info_text=info_text, variant=variant)
    except IOError as e:
        # just in case, django *should* have taken care of file type
        changeset.delete()
        os.remove(destination.name)
        info_text = 'Error: File \"' + scan.name + \
                    '" is not a valid picture.'
        return _display_cover_upload_form(request, form, cover, issue,
            info_text=info_text, variant=variant)

    # all done, we can save the state
    return finish_cover_revision(request, revision, form.cleaned_data)

def finish_cover_revision(request, revision, cd):
    if cd['remember_source']:
        request.session['oi_file_source'] = cd['source']
    else:
        request.session.pop('oi_file_source','')

    revision.changeset.submit(cd['comments'])

    return HttpResponseRedirect(urlresolvers.reverse('upload_cover_complete',
        kwargs={'revision_id': revision.id} ))

@login_required
def upload_variant(request, issue_id):
    """
    Handles uploading of variant covers
    """
    issue = get_object_or_404(Issue, id=issue_id)

    if issue.variant_of:
        return render_error(request,
          'Variants can only be uploaded to the base issue.')

    # check if there is a pending issue deletion
    if IssueRevision.objects.filter(issue=issue, deleted=True,
                                    changeset__state__in=states.ACTIVE):
        revision = IssueRevision.objects.get(issue=issue,
          changeset__state__in=states.ACTIVE)
        return render_error(request,
          ('%s is <a href="%s">pending deletion</a>. Covers '
          'cannot be added or modified.') % (esc(issue),
          urlresolvers.reverse('compare', kwargs={'id': revision.changeset.id})),
          redirect=False, is_safe=True)

    # current request is an upload
    if request.method == 'POST':
        return handle_uploaded_cover(request, None, issue, variant=True)
    # request is a GET for the form
    else:
        if 'oi_file_source' in request.session:
            vars = {'source' : request.session['oi_file_source'],
                    'remember_source' : True}
        else:
            vars = None
        form = UploadVariantScanForm(initial=vars)
        kwargs={'pending_variant_adds': Changeset.objects\
          .filter(issuerevisions__variant_of=issue,
                  #state__in=states.ACTIVE,
                  state__in=[states.PENDING,states.REVIEWING],
                  change_type__in=[CTYPES['issue_add'],
                                   CTYPES['variant_add']])}
        # display the form
        return _display_cover_upload_form(request, form, None, issue,
                                          variant=True, kwargs=kwargs)

@login_required
def upload_cover(request, cover_id=None, issue_id=None):
    """
    Handles uploading of covers be it
    - first upload
    - replacement upload
    - variant upload
    """

    # this cannot actually happen
    if cover_id and issue_id:
        raise ValueError

    # if cover_id is present it is a replacement upload
    if cover_id:
        cover = get_object_or_404(Cover, id=cover_id)
        issue = cover.issue
    # no cover_id, therefore upload a cover to an issue (first or variant)
    else:
        issue = get_object_or_404(Issue, id=issue_id)
        if not issue.can_have_cover():
            return render_error(request,
              'No covers for non-comics publications if the issue has less'
              ' than 10% indexed comics content.', redirect=False)
        cover = None

    # check if there is a pending issue deletion
    if IssueRevision.objects.filter(issue=issue, deleted=True,
                                    changeset__state__in=states.ACTIVE):
        revision = IssueRevision.objects.get(issue=issue,
          changeset__state__in=states.ACTIVE)
        return render_error(request,
          ('%s is <a href="%s">pending deletion</a>. Covers '
          'cannot be added or modified.') % (esc(issue),
          urlresolvers.reverse('compare', kwargs={'id': revision.changeset.id})),
          redirect=False, is_safe=True)

    # check if there is a pending change for the cover
    # if POST, get a lock
    if cover_id and request.method == 'POST':
        revision_lock = _get_revision_lock(cover)
        if not revision_lock:
            return render_error(
              request,
              'Cannot replace %s as it is already reserved.' %
              cover.issue)
    # if GET, check for a lock
    elif cover_id and is_locked(cover):
        return render_error(
          request,
          ('There currently is a pending replacement for this cover of %s.')
          % (cover.issue), redirect=False, is_safe=True)
    else:
        revision_lock = None

    # current request is an upload
    if request.method == 'POST':
        return handle_uploaded_cover(request, cover, issue,
                                     revision_lock=revision_lock)
    # request is a GET for the form
    else:
        if 'oi_file_source' in request.session:
            vars = {'source' : request.session['oi_file_source'],
                    'remember_source' : True}
        else:
            vars = None
        form = UploadScanForm(initial=vars)

        # display the form
        return _display_cover_upload_form(request, form, cover, issue)

def _display_cover_upload_form(request, form, cover, issue, info_text='',
                               variant=False, kwargs=None):
    if kwargs == None:
        kwargs = {}
    upload_template = 'oi/edit/upload_cover.html'
    kwargs['upload_type'] = ''

    if cover:
        kwargs['upload_type'] = 'replacement'
        kwargs['replace_cover'] = get_image_tag(cover, "cover to replace", ZOOM_MEDIUM)
    else:
        if issue.has_covers():
            kwargs['current_covers'] = get_image_tags_per_issue(issue, "current covers",
                                              ZOOM_MEDIUM, as_list=True,
                                              variants=True)
            kwargs['upload_type'] = 'additional'
        if variant:
            kwargs['upload_type'] = 'variant'

    # generate tags for cover uploads for this issue currently in the queue
    active_covers_tags = []
    if issue.variant_of:
        active_covers = CoverRevision.objects\
                        .filter(issue=issue.variant_of,
                        changeset__state__in=states.ACTIVE,
                        deleted=False).order_by('created')
        active_covers = active_covers | CoverRevision.objects\
                        .filter(issue__variant_of=issue.variant_of,
                        changeset__state__in=states.ACTIVE,
                        deleted=False).order_by('created')
        if issue.variant_of.has_covers():
            covers_list = get_image_tags_per_issue(issue.variant_of,
                                                   "current covers",
                                                   ZOOM_MEDIUM, as_list=True,
                                                   variants=True)
            if 'current_covers' in kwargs:
                kwargs['current_covers'].extend(covers_list)
            else:
                kwargs['current_covers'] = covers_list
    else:
        active_covers = CoverRevision.objects.filter(issue=issue,
                        changeset__state__in=states.ACTIVE,
                        deleted=False).order_by('created')
        active_covers = active_covers | CoverRevision.objects\
                        .filter(issue__variant_of=issue,
                        changeset__state__in=states.ACTIVE,
                        deleted=False).order_by('created')
    active_covers = active_covers.exclude(changeset__change_type=CTYPES['variant_add'])
    for active_cover in active_covers:
        active_covers_tags.append([active_cover,
                                   get_preview_image_tag(active_cover,
                                     "pending cover", ZOOM_MEDIUM)])
    kwargs['form'] = form
    kwargs['info'] = info_text
    kwargs['cover'] = cover
    kwargs['issue'] = issue
    kwargs['active_covers'] = active_covers_tags
    kwargs['table_width'] = UPLOAD_WIDTH
    return render(request, upload_template, kwargs)


@permission_required('indexer.can_approve')
def flip_artwork_flag(request, revision_id=None):
    """
    flips the status in regard to variants with different cover artwork
    """

    cover = get_object_or_404(CoverRevision, id=revision_id)
    changeset = cover.changeset
    if request.user != changeset.approver:
        return render_error(request,
          'The variant artwork status may only be changed by the approver.')
    story = list(changeset.storyrevisions.all())
    if len(story) == 1:
        for s in story:
            s.delete()
    elif len(story) == 0:
        story_revision = StoryRevision(
          changeset=changeset,
          type=StoryType.objects.get(name='cover'),
          pencils='?',
          inks='?',
          colors='?',
          sequence_number=0,
          page_count=2 if cover.is_wraparound else 1,
          )
        story_revision.save()
    else:
        # this should never happen
        raise ValueError("More than one story sequence in a cover revision.")

    return HttpResponseRedirect(urlresolvers.reverse('compare',
                                kwargs={'id': cover.changeset.id}))


@permission_required('indexer.can_approve')
def mark_cover(request, marked, cover_id=None, revision_id=None):
    """
    sets or removes the replacement mark from the the cover
    """

    if cover_id:
        cover = get_object_or_404(Cover, id=cover_id)
    else:
        cover = get_object_or_404(CoverRevision, id=revision_id)
    cover.marked = marked
    cover.save()

    # Typically present, but not for direct URLs
    if 'HTTP_REFERER' in request.META:
        return HttpResponseRedirect(request.META['HTTP_REFERER'])
    elif revision_id:
        return HttpResponseRedirect(urlresolvers.reverse('compare',
                                    kwargs={'id': cover.changeset.id}))
    else:
        return HttpResponseRedirect(urlresolvers.reverse('edit_covers',
                                    kwargs={'issue_id': cover.issue.id}))


def handle_uploaded_image(request, display_obj, model_name, image_type,
                          current_image=None):
    ''' process the uploaded file and generate ImageRevision '''

    try:
        form = UploadImageForm(request.POST, request.FILES)
    except IOError:  # sometimes uploads misbehave. connection dropped ?
        error_text = 'Something went wrong with the upload. ' + \
                        'Please <a href="' + request.path + '">try again</a>.'
        return render_error(request, error_text, redirect=False, is_safe=True)

    if not form.is_valid():
        return _display_image_upload_form(request, form, display_obj,
                                          model_name, image_type)

    # process form
    image = form.cleaned_data['image']

    if current_image:
        revision_lock = _get_revision_lock(current_image)
        if not revision_lock:
            return render_error(
              request,
              'Cannot replace %s as it is already reserved.' %
              current_image.description())

    # create OI records
    changeset = Changeset(indexer=request.user, state=states.OPEN,
                          change_type=CTYPES['image'])
    changeset.save()
    if current_image:
        revision_lock.changeset = changeset
        revision_lock.save()

    revision = ImageRevision(
      changeset=changeset,
      content_type=ContentType.objects.get_for_model(display_obj),
      object_id=display_obj.id, type=ImageType.objects.get(name=image_type),
      marked=form.cleaned_data['marked'])
    if current_image:
        revision.image = current_image
        revision.is_replacement = True
        revision.previous_revision = current_image.revisions.get(
                                     next_revision=None,
                                     changeset__state=states.APPROVED,
                                     committed=True)
    revision.save()
    revision.image_file.save(str(revision.id) + '.jpg', content=File(image))
    revision.changeset.submit(form.cleaned_data['comments'])
    return HttpResponseRedirect(urlresolvers.reverse('editing'))


@login_required
def replace_image(request, model_name, id, image_id):
    image = get_object_or_404(Image, id=image_id, deleted=False)
    if is_locked(image):
        return render_error(
          request,
          ('%s is reserved.') % (image.description()),
          redirect=False, is_safe=True)
    return upload_image(request, model_name, id, image.type.name, image=image)


@login_required
def upload_image(request, model_name, id, image_type, image=None):
    from apps.oi.views import DISPLAY_CLASSES, REVISION_CLASSES
    """
    Handles uploading of supporting images
    """

    display_obj = get_object_or_404(DISPLAY_CLASSES[model_name], id=id,
                                    deleted=False)

    kwargs = None
    # replacement
    if image:
        if image.object != display_obj:
            return render_error(
              request, 'Image and object id do not match.',
              redirect=False, is_safe=True)
        kwargs = {
          'upload_type': 'replacement', 'current_image': image,
          'current_image_tag': get_generic_image_tag(image, 'current image')}
    # check if there is an image if image_type.unique is set
    else:
        img_type = get_object_or_404(ImageType, name=image_type)
        if img_type.unique:
            if Image.objects.filter(
              content_type=ContentType.objects.get_for_model(display_obj),
              object_id=display_obj.id, type=img_type, deleted=False).count():
                return render_error(
                  request,
                  ('%s has an image. Further images cannot be added, '
                   'only replaced.') % (esc(display_obj)),
                  redirect=False, is_safe=True)

    # check if there is a pending object deletion
    filter_dict = {model_name: display_obj, 'deleted': True,
                   'changeset__state__in': states.ACTIVE}
    revision = REVISION_CLASSES[model_name].objects.filter(**filter_dict)
    if revision:
        revision = revision.get()
        return render_error(
          request,
          ('%s is <a href="%s">pending deletion</a>. Images '
           'cannot be added or modified.') % (
            esc(display_obj), urlresolvers.reverse(
              'compare', kwargs={'id': revision.changeset.id})),
          redirect=False, is_safe=True)

    # current request is an upload
    if request.method == 'POST':
        if image:
            return handle_uploaded_image(request, display_obj, model_name,
                                         image_type, current_image=image)
        else:
            return handle_uploaded_image(request, display_obj, model_name,
                                         image_type)
    # request is a GET for the form
    else:
        form = UploadImageForm()
        # display the form
        return _display_image_upload_form(request, form, display_obj,
                                          model_name, image_type,
                                          kwargs=kwargs)


def general_guidelines(type_name):
    return ['The uploaded scan needs to be a readable scan of the %s.' %
            type_name,
            'Please use large images scanned with at least 150 DPI, where '
            '300 DPI is preferred.',
            'Upload only the %s and not a scan of the full page, i.e. without'
            ' any artwork.' % type_name]


def _display_image_upload_form(request, form, display_obj, model_name,
                               image_type, kwargs=None):
    if kwargs is None:
        kwargs = {'upload_type': ''}
    upload_template = 'oi/edit/upload_image.html'

    kwargs['form'] = form
    if image_type == 'IndiciaScan':
        kwargs['header'] = 'Upload a %s scan of the indicia for' \
                           % kwargs['upload_type']
        kwargs['guidelines'] = general_guidelines('indicia')
    if image_type == 'SoOScan':
        kwargs['header'] = 'Upload a %s scan of the statement of ownership' \
                           % kwargs['upload_type']
        kwargs['guidelines'] = general_guidelines('statement of ownership')
    if image_type == 'BrandScan':
        kwargs['header'] = 'Upload a %s scan of the brand emblem' \
                           % kwargs['upload_type']
        kwargs['guidelines'] = ['Please only upload an image of the brand '
                                'emblem.']
    if image_type == 'CreatorPortrait':
        kwargs['header'] = 'Upload a %s portrait of the creator' \
                           % kwargs['upload_type']
        kwargs['guidelines'] = ['Please only upload an image of the creator']
    if image_type == 'SampleScan':
        kwargs['header'] = 'Upload a %s scan of a sample for the work of ' \
                           'creator' % kwargs['upload_type']
        kwargs['guidelines'] = ['Please upload a representative example for '
                                'the work of the creator']
    kwargs['display_obj'] = display_obj
    kwargs['model_name'] = model_name
    kwargs['image_type'] = image_type
    return render(request, upload_template, kwargs)


@permission_required('indexer.can_approve')
def mark_image(request, marked, image_id=None, revision_id=None):
    """
    sets or removes the replacement mark from the the cover
    """

    if image_id:
        image = get_object_or_404(Image, id=image_id, deleted=False)
    else:
        image = get_object_or_404(ImageRevision, id=revision_id)
    image.marked = marked
    image.save()

    # Typically present, but not for direct URLs
    if 'HTTP_REFERER' in request.META:
        return HttpResponseRedirect(request.META['HTTP_REFERER'])
    else:
        return HttpResponseRedirect(urlresolvers.reverse('reviewing'))
