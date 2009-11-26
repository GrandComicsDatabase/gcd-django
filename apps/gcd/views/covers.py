# -*- coding: utf-8 -*-
import re
from urllib import urlopen, urlretrieve, quote
import Image
import os, shutil
import codecs
from datetime import datetime

from django import forms
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

from apps.gcd.models import Cover, Series, Issue
from apps.gcd.views import render_error

ZOOM_SMALL = 1
ZOOM_MEDIUM = 2
ZOOM_LARGE = 4

# where to put our covers,
_local_new_scans = '/img/gcd/new_covers/'
_local_scans_by_id = '/img/gcd/covers_by_id/'

# Entries in this tuple match the server_version column of the covers table.
# Note that there is no sever version 0 recorded.
_server_prefixes = ['',
                    'http://images.comics.org/img/gcd/covers/',
                    'http://www.gcdcovers.com/graphics/covers/',
                    settings.MEDIA_URL + _local_scans_by_id]

def get_image_tag(cover, alt_text, zoom_level, no_cache = False):
    if cover is None:
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

    if not (cover.has_image):
        return mark_safe('<img class="no_cover" src="' + settings.MEDIA_URL + \
               'img/nocover_' + size +'.png" alt="No image yet"' + \
               width_string + 'class="cover_img">')

    if settings.FAKE_COVER_IMAGES:
        return mark_safe('<img src="' +settings.MEDIA_URL + \
               'img/placeholder_' + size + '.jpg"' + width_string + 'class="cover_img">')

    suffix = "%d/w%d/%d.jpg" % (int(cover.id/1000), width, cover.id)

    # For replacement and variant cover uploads we should make sure that no 
    # cached cover is displayed. Adding a changing query string seems the
    # prefered solution found on the net.
    # if no_cache:
    suffix = suffix + '?' + quote(str(cover.modified))

    # For now use only the covers from images.comics.org.
    # gcdcovers.com does not have all the covers the db says it should have.
    img_url = _server_prefixes[1] + suffix

    return mark_safe('<img src="' + img_url + '" alt="' + esc(alt_text) + \
           '" ' + width_string + ' class="cover_img"/>')


def get_image_tags_per_issue(issue, alt_text, zoom_level):
    covers = issue.cover_set.all()
    tag = ''
    for cover in covers:
        tag += get_image_tag(cover=cover, zoom_level=zoom_level, 
                             alt_text=alt_text)
    return mark_safe(tag)


def get_image_tags_per_page(page, series=None):
    """
    Produces a list of cover tags for the covers in a page.
    Intended for use as a callback with paginate_response().
    """

    cover_tags = []
    cover_series=series
    for cover in page.object_list:
        if series is None:
            cover_series = cover.series
        issue = cover.issue
        alt_string = cover_series.name + ' #' + issue.number
        cover_tags.append([cover, issue, get_image_tag(cover,
                                                       alt_string,
                                                       ZOOM_SMALL)])
    return cover_tags


def _create_cover_dir(scan_dir):
    if not os.path.isdir(scan_dir):
        if os.path.exists(scan_dir):
            return False
        else:
            os.mkdir(scan_dir)
    return True

def check_cover_dir(cover):
    """
    Checks if the necessary cover directories exist and creates
    them if necessary.
    """

    scan_dir = settings.MEDIA_ROOT + _local_scans_by_id + str(int(cover.id/1000))
    if not _create_cover_dir(scan_dir):
        return False
    if not _create_cover_dir(scan_dir + "/uploads"):
        return False
    if not _create_cover_dir(scan_dir + "/w100"):
        return False
    if not _create_cover_dir(scan_dir + "/w200"):
        return False
    if not _create_cover_dir(scan_dir + "/w400"):
        return False
    return True


def generate_sizes(cover, im):
    if im.mode != "RGB":
        im = im.convert("RGB")
    scaled_name = settings.MEDIA_ROOT + _local_scans_by_id + \
      str(int(cover.id/1000)) + "/w100/" + str(cover.id) + ".jpg"
    size = 100,int(100./im.size[0]*im.size[1])
    scaled = im.resize(size,Image.ANTIALIAS)
    scaled.save(scaled_name)

    scaled_name = settings.MEDIA_ROOT + _local_scans_by_id + \
      str(int(cover.id/1000)) + "/w200/" + str(cover.id) + ".jpg"
    size = 200,int(200./im.size[0]*im.size[1])
    scaled = im.resize(size,Image.ANTIALIAS)
    scaled.save(scaled_name)

    scaled_name = settings.MEDIA_ROOT + _local_scans_by_id + \
      str(int(cover.id/1000)) + "/w400/" + str(cover.id) + ".jpg"
    size = 400,int(400./im.size[0]*im.size[1])
    scaled = im.resize(size,Image.ANTIALIAS)
    scaled.save(scaled_name)


class UploadScanForm(forms.Form):
    """ Form for cover uploads. """

    scan = forms.ImageField(widget=forms.FileInput)
    name = forms.CharField(label='Submitter')
    email = forms.EmailField(label='Submitter email')
    remember_me = forms.BooleanField(label="Remember my name & email", 
                                     required=False)


def cover_upload(request, cover_id, add_variant=False):
    """
    Handles uploading of covers be it
    - first upload
    - replacement upload
    - variant upload
    """

    upload_template = 'gcd/details/cover_upload.html'
    uploaded_template = 'gcd/details/cover_uploaded.html'
    style = 'default'

    # check for issue and cover
    cover = get_object_or_404(Cover, id=cover_id)
    issue = cover.issue

    if add_variant and not cover.has_image:
        error_text = "No cover present for %s. You cannot upload a variant." \
                     % cover.issue
        return render_error(request, error_text, redirect=False)

    # check that we are actually allowed to upload
    if cover.has_image and not cover.marked and not add_variant:
        tag = get_image_tag(cover, "existing cover", 2)
        covers_needed = Cover.objects.filter(issue__series=issue.series)
        covers_needed = covers_needed.exclude(marked=False, 
                                              has_image=True)
        # TODO: make the 15 an option
        covers_needed = covers_needed.exclude(marked=None, 
                                              has_image=True)[:15]
        return render_to_response(uploaded_template, {
                                  'cover' : cover,
                                  'covers_needed' :  covers_needed,
                                  'issue' : issue,
                                  'tag'   : tag,
                                  'already' : "is already",
                                  'style' : style},
                                  context_instance=RequestContext(request))

    # check what kind of upload
    if cover.has_image and cover.marked and not add_variant:
        display_cover = get_image_tag(cover, "cover to replace", 2, 
                                      no_cache = True)
        upload_type = 'replacement'
    elif add_variant:
        display_cover = get_image_tag(cover, "first cover", 2, 
                                      no_cache = True)
        upload_type = 'variant'
    else:
        display_cover = None
        upload_type = ''

    # current request is an upload
    if request.method == 'POST':
        try:
            form = UploadScanForm(request.POST,request.FILES)
        except IOError: # sometimes uploads misbehave. connection dropped ?
            error_text = 'Something went wrong with the upload. ' + \
                         'Please <a href="' + request.path + '">try again</a>.'
            return render_error(request, error_text, redirect=False, 
                is_safe=True)

        if form.is_valid():
            # user has to change defaults and enter something valid
            if request.POST['email'] == 'your@email.address':
                request.POST['email'] = ''
            if request.POST['name'] == 'Your name':
                request.POST['name'] = ''
            form = UploadScanForm(request.POST,request.FILES)
        # TODO: even if the file is a valid image it does not survive into
        #       the next form if name/email is not valid, Django issue ?
        if not form.is_valid():
            return render_to_response(upload_template, {
                                      'form': form.as_ul(),
                                      'cover' : cover,
                                      'issue' : issue,
                                      'style' : style,
                                      'display_cover' : display_cover,
                                      'upload_type' : upload_type,
                                      },
                                      context_instance=RequestContext(request))
        # if file is in form handle it
        if 'scan' in request.FILES:
            upload_datetime = datetime.today()
            scan = request.FILES['scan']
            contributor = '%s (%s)' % (request.POST['name'],
                                       request.POST['email'])
            # at first (in case something goes wrong) put new covers into 
            # media/<_local_new_scans>/<monthname>_<year>/ 
            # with name 
            # <cover_id>_<date>_<time>.<ext>
            scan_name = str(cover.id) + "_" + \
                        upload_datetime.strftime('%Y%m%d_%H%M%S')
            upload_dir = settings.MEDIA_ROOT + _local_new_scans + \
                         upload_datetime.strftime('%B_%Y/').lower()
            destination_name = upload_dir + scan_name + \
                               os.path.splitext(scan.name)[1]
            if not os.path.isdir(upload_dir):
                try:
                    os.mkdir(upload_dir)
                except IOError:
                    error_text = "Problem with file storage for uploaded " + \
                                 "cover, please report an error." 
                    return render_error(request, error_text, redirect=False)

            # arguably a bit unlikely to happen with the current naming scheme
            if os.path.exists(destination_name):
                destination_name = os.path.splitext(destination_name)[0] + \
                                   "_a" + os.path.splitext(scan.name)[1]
            # write uploaded file
            destination = open(destination_name, 'wb')
            for chunk in scan.chunks():
                destination.write(chunk)
            destination.close()

            try:
                # generate different sizes we are using
                im = Image.open(destination.name)
                if im.size[0] >= 400:
                    # generate the sizes we are using
                    if check_cover_dir(cover) == False:
                        error_text = "Problem with file storage for cover " + \
                          "with id %d for %s, please report an error." \
                          % (cover.id, uni(issue))
                        return render_error(request, error_text, redirect=False)

                    base_dir = str(int(cover.id/1000))
                    if upload_type == 'replacement':
                        # if we don't have the original file copy it from w400
                        # otherwise do nothing, old cover file stays due to
                        # datetime string in the filename
                        if not cover.file_extension: 
                            sub_dir = "/w400/"
                            extension = ".jpg"
                            current_im_name = settings.MEDIA_ROOT + \
                                              _local_scans_by_id + base_dir + \
                                              sub_dir + str(cover.id) + extension
                            # check for existence
                            if not os.path.exists(current_im_name):
                                error_text = "Problem with existing file for cover " + \
                                  "with id %d for %s, please report an error." \
                                  % (cover.id, uni(issue))
                                return render_error(request, error_text, 
                                                    redirect=False)
                                # use this for debugging locally
                                # img_url = _server_prefixes[cover.server_version] \
                                #          + suffix
                                # urlretrieve(img_url,current_im_name)

                            backup_name = settings.MEDIA_ROOT + \
                              _local_scans_by_id + base_dir + \
                              "/uploads/" + str(cover.id) + \
                              cover.modified.strftime('_%Y%m%d_%H%M%S') + \
                              extension
                            shutil.copy(current_im_name, backup_name)
        
                    if add_variant:
                        return render_error(request, 
                          'Adding variant covers is not yet implemented.',
                          redirect=False)

                    # generate different sizes
                    generate_sizes(cover, im)

                    # set cover table values
                    cover.server_version = 1
                    cover.has_image = True
                    cover.marked = False
                    cover.contributor = contributor
                    if not cover.series.has_gallery == True:
                        series = cover.series
                        series.has_gallery = True
                        series.save()
                    cover.modified = upload_datetime    
                    cover.extension = os.path.splitext(destination_name)[1]
                    im_name = settings.MEDIA_ROOT + \
                              _local_scans_by_id + base_dir + "/uploads/" + \
                              str(cover.id) + upload_datetime. \
                              strftime('_%Y%m%d_%H%M%S') + cover.extension

                    shutil.move(destination_name, im_name)
                    cover.save()

                    store_count = codecs.open(settings.MEDIA_ROOT + \
                                  _local_new_scans + "cover_count", "w", "utf-8")
                    store_count.write(str(Cover.objects.filter(has_image=True)\
                                                               .count()))
                    store_count.close()

                    if 'remember_me' in request.POST:
                        request.session['gcd_uploader_name'] = \
                          request.POST['name']
                        request.session['gcd_uploader_email'] = \
                          request.POST['email']
                    else:
                        request.session.pop('gcd_uploader_name','')
                        request.session.pop('gcd_uploader_email','')

                    tag = get_image_tag(cover, "uploaded cover", 2)
                else:
                    os.remove(destination.name)
                    info_text = "Image is too small, only " + str(im.size) + \
                                " in size."
                    return render_to_response(upload_template, {
                      'form': form.as_ul(),
                      'info' : info_text,
                      'cover' : cover,
                      'display_cover' : display_cover,
                      'upload_type' : upload_type,
                      'issue' : issue,
                      'style' : style,
                      },
                      context_instance=RequestContext(request))

                # what else do we need
                covers_needed = Cover.objects.filter(issue__series = \
                  issue.series).exclude(marked = False, has_image = True)
                covers_needed = covers_needed.exclude(marked = None,
                                                      has_image = True)[:15]

                return render_to_response(uploaded_template, {
                  'cover' : cover,
                  'covers_needed' :  covers_needed,
                  'issue' : issue,
                  'tag'   : tag,
                  'style' : style},
                  context_instance=RequestContext(request))

            except IOError: # file type *should* be taken care of by django
                os.remove(destination.name)
                return render_to_response(upload_template, {
                  'form': form.as_ul(),
                  'info' : 'Error: File \"' + scan.name + \
                           '" is not a valid picture.',
                  'cover' : cover,
                  'issue' : issue,
                  'display_cover' : display_cover,
                  'upload_type' : upload_type,
                  'style' : style,
                  },
                  context_instance=RequestContext(request))
        else: # there is a pretty good chance we never end up here
            return render_to_response(upload_template, { 
              'form': form.as_ul(), 
              'cover' : cover,
              'issue' : issue,
              'style' : style},
              context_instance=RequestContext(request))

    else:
        # do we have email/name cached
        if 'gcd_uploader_email' in request.session:
            vars = {'name' : request.session['gcd_uploader_name'],
                   'email' : request.session['gcd_uploader_email'],
                   'remember_me' : True}
        elif request.user.is_authenticated():
            vars = {'name' : unicode(request.user.indexer),
                   'email' : request.user.email,
                   'remember_me' : True}            
        else:
            vars = {'name' : 'Your name', 'email' : 'your@email.address'}

        form = UploadScanForm(initial=vars)
        # display the form
        return render_to_response(upload_template, {
                                  'form': form.as_ul(), 
                                  'cover' : cover,
                                  'issue' : issue,
                                  'display_cover' : display_cover,
                                  'upload_type' : upload_type,
                                  'style' : style},
                                  context_instance=RequestContext(request))


def variant_upload(request, cover_id):
    """ handle uploads of variant covers"""

    return cover_upload(request, cover_id, add_variant=True)


def mark_cover(request, cover_id):
    """
    marks the cover of the issue for replacement
    """

    # TODO: once we have permissions 'can_mark' should be one
    if request.user.is_authenticated() and \
      request.user.groups.filter(name='editor'):
        # check for issue and cover
        cover = get_object_or_404(Cover, id=cover_id)
        
        cover.marked = True
        cover.save()

        # I kinda assume the HTTP_REFERER is always present, but just in case
        if request.META.has_key('HTTP_REFERER'):
            return HttpResponseRedirect(request.META['HTTP_REFERER'])
        else:
            cover_tag = get_image_tag(cover, "Cover Image", 2)
            return render_to_response(
              'gcd/details/cover_marked.html',
              {
                'issue': cover.issue,
                'cover_tag': cover_tag,
                'error_subject': '%s cover' % cover.issue,
                'style': 'default',
              },
              context_instance=RequestContext(request)
            )        
    else:
        return render_error(request,
          'You are not allowed to mark covers for replacement.', 
          redirect=False)


