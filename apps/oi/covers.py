# -*- coding: utf-8 -*-
import re
from urllib import urlopen, urlretrieve, quote
import Image
import os, shutil, glob
import codecs
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
from apps.oi.forms import UploadScanForm

ZOOM_SMALL = 1
ZOOM_MEDIUM = 2
ZOOM_LARGE = 4

# table width for displaying the medium sized current and active covers
UPLOAD_WIDTH = 3

# where to put our covers,
LOCAL_NEW_SCANS = settings.NEW_COVERS_DIR

NEW_COVERS_LOCATION = settings.IMAGE_SERVER_URL + settings.NEW_COVERS_DIR
# only while testing:
NEW_COVERS_LOCATION = settings.MEDIA_URL + LOCAL_NEW_SCANS

def get_preview_image_tag(revision, alt_text, zoom_level):
    if revision is None:
        return mark_safe('<img class="no_cover" src="' + settings.MEDIA_URL + \
               'img/nocover.gif" alt="No image yet" class="cover_img"/>')

    if zoom_level == ZOOM_SMALL:
        width = 100
        size = 'small'
    elif zoom_level == ZOOM_MEDIUM:
        width = 200
        size = 'medium'
    elif zoom_level == ZOOM_LARGE:
        width = 400
        size = 'large'
    width_string = 'width="' + str(width) + '"'

    if revision.changeset.state == states.APPROVED:
        current_cover = CoverRevision.objects.filter(cover=revision.cover, 
          changeset__state=states.APPROVED).order_by('-created')[0]
        if revision==current_cover: 
            # Current cover is the one from this revision, show it.
            return get_image_tag(revision.cover, "uploaded cover", zoom_level)  
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
            return mark_safe('<img src="' + img_url + '" alt="' + \
              esc(alt_text) + '" ' + width_string + ' class="cover_img"/>')
    else:
        suffix = "w%d/%d.jpg" % (width, revision.id)
        img_url = NEW_COVERS_LOCATION + \
          revision.changeset.created.strftime('%B_%Y/').lower() + suffix
        return mark_safe('<img src="' + img_url + '" alt="' + esc(alt_text) \
               + '" ' + width_string + ' class="cover_img"/>')


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

    for width in [100, 200, 400]:
        scaled_name = "%s/w%d/%d.jpg" % (base_dir, width, cover.id)
        size = width, int(float(width)/im.size[0]*im.size[1])
        scaled = im.resize(size,Image.ANTIALIAS)
        scaled.save(scaled_name)


@login_required
def edit_covers(request, issue_id):
    """
    Overview of covers for an issue and possible actions
    """

    issue = get_object_or_404(Issue, id=issue_id)
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


@login_required
def uploaded_cover(request, revision_id):
    """
    On successful upload display the cover and show further possibilities
    """
    uploaded_template = 'oi/edit/upload_cover_complete.html'
 
    # what other covers do we need
    # TODO change this code
    # - show different selection
    # - links to next issue
    # - upload another variant
    # - add discard button for undo of wrong upload
    # - ...
    revision = get_object_or_404(CoverRevision, id=revision_id)
    if revision.cover:
        issue = revision.cover.issue
    else:
        issue = revision.issue

    covers_needed = Cover.objects.filter(issue__series=issue.series).\
                      exclude(marked=False, has_image=True)[:15]
    tag = get_preview_image_tag(revision, "uploaded cover", ZOOM_MEDIUM)
    return render_to_response(uploaded_template, {
              'covers_needed' :  covers_needed,
              'revision': revision,
              'issue' : issue,
              'tag'   : tag},
              context_instance=RequestContext(request))


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

    upload_template = 'oi/edit/upload_cover.html'
    style = 'default'

    # set cover, issue, covers, replace_cover, upload_type
    covers = []
    replace_cover = None
    # if cover_id is present it is a replacement upload
    if cover_id:
        cover = get_object_or_404(Cover, id=cover_id)
        issue = cover.issue
        if not cover.has_image: 
            # nothing to replace, empty cover slot, redirect to issue upload
            return HttpResponseRedirect(urlresolvers.reverse('upload_cover',
                kwargs={'issue_id': issue.id} ))


        # check if there is a pending change for the cover
        if CoverRevision.objects.filter(cover=cover, 
                                 changeset__state__in=states.ACTIVE):
            revision = CoverRevision.objects.get(cover=cover, 
                                     changeset__state__in=states.ACTIVE)
            return render_error(request,
              ('There currently is a <a href="%s">pending replacement</a> '
               'for this cover of %s.') % (urlresolvers.reverse('compare',
                kwargs={'id': revision.changeset.id}), esc(cover.issue)),
            redirect=False, is_safe=True)

        upload_type = 'replacement'
        replace_cover = get_image_tag(cover, "cover to replace", ZOOM_MEDIUM)
    # no cover_id, therefore upload a cover to an issue (first or variant)
    else: 
        issue = get_object_or_404(Issue, id=issue_id)
        cover = issue.cover_set.latest() # latest can be the empty first one
        if cover.has_image:
            covers = get_image_tags_per_issue(issue, "current covers", 
                                              ZOOM_MEDIUM, as_list=True)
            upload_type = 'variant'
        else:
            upload_type = ''

    # generate tags for cover uploads for this issue currently in the queue
    active_covers_tags = []
    active_covers = CoverRevision.objects.filter(issue=issue, 
                    changeset__state__in=states.ACTIVE).order_by('created')
    for active_cover in active_covers:
        active_covers_tags.append([active_cover, 
                                   get_preview_image_tag(active_cover, 
                                   "pending cover", ZOOM_MEDIUM)])

    # current request is an upload
    if request.method == 'POST':
        try:
            form = UploadScanForm(request.POST,request.FILES)
        except IOError: # sometimes uploads misbehave. connection dropped ?
            error_text = 'Something went wrong with the upload. ' + \
                         'Please <a href="' + request.path + '">try again</a>.'
            return render_error(request, error_text, redirect=False, 
                is_safe=True)

        if not form.is_valid():
            return render_to_response(upload_template, {
                                      'form': form,
                                      'cover' : cover,
                                      'issue' : issue,
                                      'style' : style,
                                      'replace_cover' : replace_cover,
                                      'current_covers' : covers,
                                      'upload_type' : upload_type,
                                      'table_width': UPLOAD_WIDTH
                                      },
                                      context_instance=RequestContext(request))
        # if scan is actually in the form handle it
        if 'scan' in request.FILES:
            # process form
            scan = request.FILES['scan']
            file_source = request.POST['source']
            marked = 'marked' in request.POST

            # create OI records
            changeset = Changeset(indexer=request.user, state=states.PENDING)
            changeset.save()

            if upload_type == 'replacement':
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
                         changeset.created.strftime('%B_%Y/').lower()
            destination_name = upload_dir + scan_name
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
                if im.size[0] >= 400:
                    generate_sizes(revision, im)
                else:
                    changeset.delete()
                    os.remove(destination.name)
                    info_text = "Image is too small, only " + str(im.size) + \
                                " in size."
                    return render_to_response(upload_template, {
                      'form': form,
                      'info' : info_text,
                      'cover' : cover,
                      'current_covers' : covers,
                      'replace_cover' : replace_cover,
                      'upload_type' : upload_type,
                      'table_width': UPLOAD_WIDTH,
                      'issue' : issue
                      },
                      context_instance=RequestContext(request))
            except IOError: 
                # just in case, django *should* have taken care of file type
                changeset.delete()
                os.remove(destination.name)
                return render_to_response(upload_template, {
                  'form': form,
                  'info' : 'Error: File \"' + scan.name + \
                           '" is not a valid picture.',
                  'cover' : cover,
                  'issue' : issue,
                  'current_covers' : covers,
                  'replace_cover' : replace_cover,
                  'upload_type' : upload_type,
                  'table_width': UPLOAD_WIDTH
                  },
                  context_instance=RequestContext(request))

            # all done, we can save the state
            changeset.comments.create(commenter=request.user,
                                      text=form.cleaned_data['comments'],
                                      old_state=states.UNRESERVED,
                                      new_state=changeset.state)

            if 'remember_source' in request.POST:
                request.session['oi_file_source'] = request.POST['source']
            else:
                request.session.pop('oi_file_source','')

            return HttpResponseRedirect(urlresolvers.reverse('upload_cover_complete',
                kwargs={'revision_id': revision.id} ))

    # request is a GET for the form
    else:
        if 'oi_file_source' in request.session:
            vars = {'source' : request.session['oi_file_source'],
                    'remember_source' : True}
        else:
            vars = None
        form = UploadScanForm(initial=vars)

        # display the form
        return render_to_response(upload_template, {
                                  'form': form, 
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
        if cover.has_image:
            cover.marked = marked
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

