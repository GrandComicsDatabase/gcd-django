# -*- coding: utf-8 -*-
import re
from urllib import urlopen, urlretrieve, quote
import Image
import os, shutil, glob
import codecs
import tempfile
from datetime import datetime

from django import forms
from django.core import urlresolvers
from django.conf import settings
from django.shortcuts import get_list_or_404, \
                             get_object_or_404, \
                             render_to_response
from django.template import RequestContext
from django.utils.encoding import smart_unicode as uni
from django.core.files import temp as tempfile
from django.utils.safestring import mark_safe
from django.utils.html import conditional_escape as esc
from django.http import HttpResponseRedirect
from django.contrib.auth.decorators import login_required, permission_required

from apps.gcd.models import Cover, Series, Issue, CountStats
from apps.gcd.views import render_error, paginate_response
from apps.gcd.views.covers import get_image_tag, get_image_tags_per_issue

from apps.oi.models import *
from apps.oi.forms import UploadScanForm, GatefoldScanForm

from apps.gcd.models.cover import ZOOM_SMALL, ZOOM_MEDIUM, ZOOM_LARGE

# table width for displaying the medium sized current and active covers
UPLOAD_WIDTH = 3

SHOW_GATEFOLD_WIDTH = 1000

# where to put our covers,
LOCAL_NEW_SCANS = settings.NEW_COVERS_DIR

NEW_COVERS_LOCATION = settings.IMAGE_SERVER_URL + settings.NEW_COVERS_DIR
# only while testing:
NEW_COVERS_LOCATION = settings.MEDIA_URL + LOCAL_NEW_SCANS

def get_preview_image_tag(revision, alt_text, zoom_level):
    if revision is None:
        return mark_safe('<img class="no_cover" src="' + settings.MEDIA_URL + \
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
          changeset__state=states.APPROVED).order_by('-created')[0]
        if revision==current_cover: 
            # Current cover is the one from this revision, show it.
            return get_image_tag(revision.cover, esc(alt_text), zoom_level)  
        else: 
            # The cover was replaced by now, show original uploaded file,
            # scaled in the browser.
            # It is the real uploaded file for uploads on the new server, and
            # the large scan for older uploads, copied on replacement.
            suffix = "/uploads/%d_%s" % (revision.cover.id, 
                     revision.changeset.created.strftime('%Y%m%d_%H%M%S'))
            if revision.created > datetime(2009,10,2,14,0,0):
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
        old_cover = CoverRevision.objects.filter(cover=cover, 
          changeset__state=states.APPROVED).order_by('-created')[1]
        if old_cover.created <= datetime(2009,10,2,14,0,0):
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
            scaled = full_cover.resize(size, Image.ANTIALIAS)
        else:
            if width == 400 and im.size[0] > im.size[1]:
                # for landscape covers use height as base size
                size = int(float(width)/im.size[1]*im.size[0]), width
            else:
                size = width, int(float(width)/im.size[0]*im.size[1])
            scaled = im.resize(size, Image.ANTIALIAS)
        scaled.save(scaled_name, subsampling='4:4:4')


@login_required
def edit_covers(request, issue_id):
    """
    Overview of covers for an issue and possible actions
    """

    issue = get_object_or_404(Issue, id=issue_id)
    if issue.has_covers():
        covers = get_image_tags_per_issue(issue, "current covers", ZOOM_MEDIUM,
                                          as_list=True)
        return render_to_response(
        'oi/edit/edit_covers.html',
        {
            'issue': issue,
            'covers': covers,
            'table_width': UPLOAD_WIDTH
        },
        context_instance=RequestContext(request)
        )
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
    return render_to_response(uploaded_template, {
              'marked_covers' : marked_covers,
              'blank_issues' : blank_issues,
              'revision': revision,
              'issue' : issue,
              'tag'   : tag},
              context_instance=RequestContext(request))

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

    tmpdir = tempfile.gettempdir()
    scan_name = cd['scan_name']
    tmp_name = os.path.join(tmpdir, scan_name)

    if 'discard' in request.POST:
        os.remove(tmp_name)
        return HttpResponseRedirect(urlresolvers.reverse('edit_covers',
                kwargs={'issue_id': cd['issue_id']} ))

    # create OI records
    changeset = Changeset(indexer=request.user, state=states.OPEN,
                            change_type=CTYPES['cover'])
    changeset.save()

    if cd['cover_id']:
        cover = get_object_or_404(Cover, id=cd['cover_id'])
        issue = cover.issue
        # check if there is a pending change for the cover
        if CoverRevision.objects.filter(cover=cover, 
                                 changeset__state__in=states.ACTIVE):
            revision = CoverRevision.objects.get(cover=cover, 
                                     changeset__state__in=states.ACTIVE)
            changeset.delete()
            return render_error(request,
              ('There currently is a <a href="%s">pending replacement</a> '
               'for this cover of %s.') % (urlresolvers.reverse('compare',
                kwargs={'id': revision.changeset.id}), esc(cover.issue)),
            redirect=False, is_safe=True)
        revision = CoverRevision(changeset=changeset, issue=issue,
            cover=cover, file_source=cd['source'], marked=cd['marked'],
            is_replacement = True)
    # no cover_id, therefore upload a cover to an issue (first or variant)
    else: 
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

    im = Image.open(destination_name)
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
    # either we use the system tmp directory and do a symlink from there
    # to the media/img/gcd/new_covers/tmp directory, or we actually use
    # media/img/gcd/new_covers/tmp and accept that it could fill up with
    # abandoned files
    tmpdir = tempfile.gettempdir()
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
    im = Image.open(destination.name)
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
    form = GatefoldScanForm(initial=vars)

    return render_to_response('oi/edit/upload_gatefold_cover.html', {
                                'remember_source': remember_source,
                                'scan_name': scan_name, 
                                'form': form,
                                'issue': issue,
                                'width': min(SHOW_GATEFOLD_WIDTH, im.size[0])},
                              context_instance=RequestContext(request))


def handle_uploaded_cover(request, cover, issue):
    ''' process the uploaded file and generate CoverRevision '''

    try:
        form = UploadScanForm(request.POST, request.FILES)
    except IOError: # sometimes uploads misbehave. connection dropped ?
        error_text = 'Something went wrong with the upload. ' + \
                        'Please <a href="' + request.path + '">try again</a>.'
        return render_error(request, error_text, redirect=False, 
            is_safe=True)

    if not form.is_valid():
        return _display_cover_upload_form(request, form, cover, issue)

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
    else:
        revision = CoverRevision(changeset=changeset, issue=issue,
            file_source=file_source, marked=marked)
    revision.save()

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
        im = Image.open(destination.name)
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
                info_text=info_text)
    except IOError: 
        # just in case, django *should* have taken care of file type
        changeset.delete()
        os.remove(destination.name)
        info_text = 'Error: File \"' + scan.name + \
                    '" is not a valid picture.'
        return _display_cover_upload_form(request, form, cover, issue,
            info_text=info_text)

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
    if cover_id and CoverRevision.objects.filter(cover=cover, 
                    changeset__state__in=states.ACTIVE):
        revision = CoverRevision.objects.get(cover=cover, 
          changeset__state__in=states.ACTIVE)
        return render_error(request,
          ('There currently is a <a href="%s">pending replacement</a> '
          'for this cover of %s.') % (urlresolvers.reverse('compare',
          kwargs={'id': revision.changeset.id}), esc(cover.issue)),
          redirect=False, is_safe=True)

    # current request is an upload
    if request.method == 'POST':
        return handle_uploaded_cover(request, cover, issue)
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

def _display_cover_upload_form(request, form, cover, issue, info_text=''):
    upload_template = 'oi/edit/upload_cover.html'

    # set covers, replace_cover, upload_type
    covers = []
    replace_cover = None
    if cover:
        upload_type = 'replacement'
        replace_cover = get_image_tag(cover, "cover to replace", ZOOM_MEDIUM)
    else:
        if issue.has_covers():
            covers = get_image_tags_per_issue(issue, "current covers", 
                                              ZOOM_MEDIUM, as_list=True)
            upload_type = 'variant'
        else:
            upload_type = ''

    # generate tags for cover uploads for this issue currently in the queue
    active_covers_tags = []
    active_covers = CoverRevision.objects.filter(issue=issue, 
                    changeset__state__in=states.ACTIVE,
                    deleted=False).order_by('created')
    for active_cover in active_covers:
        active_covers_tags.append([active_cover, 
                                   get_preview_image_tag(active_cover, 
                                     "pending cover", ZOOM_MEDIUM)])

    return render_to_response(upload_template, {
                                'form': form, 
                                'info' : info_text,
                                'cover' : cover,
                                'issue' : issue,
                                'current_covers' : covers,
                                'replace_cover' : replace_cover,
                                'active_covers' : active_covers_tags,
                                'upload_type' : upload_type,
                                'table_width': UPLOAD_WIDTH},
                              context_instance=RequestContext(request))

@permission_required('gcd.can_approve')
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
    if request.META.has_key('HTTP_REFERER'):
        return HttpResponseRedirect(request.META['HTTP_REFERER'])
    elif revision_id:
        return HttpResponseRedirect(urlresolvers.reverse('compare',
                kwargs={'id': cover.changeset.id} ))
    else:
        return HttpResponseRedirect(urlresolvers.reverse('edit_covers',
                kwargs={'issue_id': cover.issue.id} ))
