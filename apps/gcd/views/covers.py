# -*- coding: utf-8 -*-
import re
from urllib import urlopen, urlretrieve
import Image
import os
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

from apps.gcd.models import Cover, Series, Issue

ZOOM_SMALL = 1
ZOOM_MEDIUM = 2
ZOOM_LARGE = 4

# where to put our covers,
_local_new_scans = '/img/gcd/new_covers/'
_local_scans = '/img/gcd/covers/'

# Entries in this tuple match the server_version column of the covers table.
# Note that there is no sever version 0 recorded.
_server_prefixes = ['',
                    'http://www.comics.org/graphics/covers/',
                    'http://www.gcdcovers.com/graphics/covers/',
                    settings.MEDIA_URL + _local_scans]
                    #'http://imagesgcd.everycomic.net/img/gcd/covers/']

def get_image_tag(series_id, cover, alt_text, zoom_level):
    if cover is None:
        return mark_safe('<img class="no_cover" src="' + _server_prefixes[2] + \
               'nocover.gif" alt="No image yet" class="cover_img"/>')

    if settings.FAKE_COVER_IMAGES:
        if zoom_level == ZOOM_SMALL:
            return mark_safe('<img src="' +settings.MEDIA_URL + \
                   'img/placeholder_small.jpg" width="100" class="cover_img"/>')
        if zoom_level == ZOOM_MEDIUM:
            return mark_safe('<img src="' + settings.MEDIA_URL + \
                   'img/placeholder_medium.jpg" width="200" class="cover_img"/>')
        if zoom_level == ZOOM_LARGE:
            return mark_safe('<img src="' + settings.MEDIA_URL + \
                   'img/placeholder_large.jpg" width="400" class="cover_img"/>')

    width = ''
    if zoom_level == ZOOM_SMALL:
        width = 'width="100"'
    elif zoom_level == ZOOM_MEDIUM:
        width = 'width="200"'
    elif zoom_level == ZOOM_LARGE:
        width = 'width="400"'

    # I don't think this is used ?
    img_url = ('<img src="" alt="' +
               esc(alt_text) +
               '" ' +
               width +
               ' class="cover_img"/>')

    if (zoom_level == ZOOM_SMALL):
        if not (cover.has_image):
            return mark_safe('<img class="no_cover" src="' + _server_prefixes[2] + \
                   'nocover.gif" alt="No image yet" class="cover_img"/>')
        suffix = "%d/%d_%s.jpg" % (series_id, series_id, cover.code)
    else:
        suffix = "%d/" % series_id
        suffix = suffix + "%d00/" % zoom_level
        suffix = suffix + "%d_%d_%s.jpg" % (series_id, zoom_level, cover.code)

    # For now trust the DB on the graphics server.  This will sometimes
    # be wrong but is *MUCH* faster.
    img_url = _server_prefixes[cover.server_version] + suffix
    # try:
        # img_url = _server_prefixes[cover.server_version] + suffix
        # img = urlopen(img_url)
    # except:
        # TODO: Figure out specific recoverable error.
        # TODO: Don't hardcode the number 2.
        # cover.server_version = 2
        # cover.save()
        # img_url = _server_prefixes[cover.server_version] + suffix

    return mark_safe('<img src="' + img_url + '" alt="' + esc(alt_text) + \
           '" ' + width + ' class="cover_img"/>')

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
        cover_tags.append([cover, issue, get_image_tag(cover_series.id,
                                                       cover,
                                                       alt_string,
                                                       ZOOM_SMALL)])
    return cover_tags


def check_series_cover_dir(series):
    """
    Checks if the necessary cover directories exist and creates
    them if necessary.
    """

    scan_dir = settings.MEDIA_ROOT + _local_scans + str(series.id)
    if not os.path.isdir(scan_dir):
        if os.path.exists(scan_dir):
            return False
        else:
            os.mkdir(scan_dir)
    if not os.path.isdir(scan_dir + "/200"):
        if os.path.exists(scan_dir + "/200"):
            return False
        else:
            os.mkdir(scan_dir + "/200")
    if not os.path.isdir(scan_dir + "/400"):
        if os.path.exists(scan_dir + "/400"): 
            return False
        else:
            os.mkdir(scan_dir + "/400")
    return True


class UploadScanForm(forms.Form):
    """ Form for cover uploads. """

    scan = forms.ImageField(widget=forms.FileInput)
    name = forms.CharField(label='Submitter')
    email = forms.EmailField(label='Submitter email')
    remember_me = forms.BooleanField(label="Remember my name & email", 
                                     required=False)


def cover_upload(request, issue_id, add_variant=False):
    """
    Handles uploading of covers be it
    - first upload
    - replacement upload
    - variant upload
    """

    upload_template = 'gcd/details/cover_upload.html'
    uploaded_template = 'gcd/details/cover_uploaded.html'
    error_template = 'gcd/error.html'
    style = 'default'

    # check for issue and cover
    # TODO might do get_object_or_404 instead of own error check
    issue = Issue.objects.filter(id=int(issue_id))
    if len(issue) == 0:
        return render_to_response(error_template, {
          'error_text' : 'Issue ID #' + issue_id  + ' does not exist.',
          'media_url' : settings.MEDIA_URL
          })    
    else:
        issue = issue[0]

    cover = Cover.objects.filter(issue=issue)
    if len(cover) == 0:
        return render_to_response(error_template, {
          'error_text' : 'Something wrong with issue ID #' + issue_id  + \
                        ' and its cover table, please contact the admins.',
          'media_url' : settings.MEDIA_URL
          })    
    else:
        cover = cover[0]

    # check that we are actually allowed to upload
    if cover.has_image and not cover.marked and not add_variant:
        tag = get_image_tag(issue.series.id, cover, "existing cover", 2)
        covers_needed = Cover.objects.filter(issue__series=issue.series)
        covers_needed = covers_needed.exclude(marked=False, 
                                              has_large=True)
        # TODO: make the 15 an option
        covers_needed = covers_needed.exclude(marked=None, 
                                              has_large=True)[:15]
        return render_to_response(uploaded_template, {
                                  'cover' : cover,
                                  'covers_needed' :  covers_needed,
                                  'issue' : issue,
                                  'tag'   : tag,
                                  'already' : "is already",
                                  'style' : style},
                                  context_instance=RequestContext(request))

    # check what kind of upload
    if cover.has_image and cover.marked:
        display_cover = get_image_tag(issue.series.id, cover,
                                      "cover to replace", 2)
        upload_type = 'replacement'
    elif add_variant:
        display_cover = get_image_tag(issue.series.id, cover,
                                      "first cover", 2)
        upload_type = 'variant'
    else:
        display_cover = None
        upload_type = ''

    # current request is an upload
    if request.method == 'POST':
        # user has to change defaults and enter something valid
        if request.POST['email'] == 'your@email.adress':
            request.POST['email'] = ''
        if request.POST['name'] == 'Your name':
            request.POST['name'] = ''
        form = UploadScanForm(request.POST,request.FILES)
        # TODO: even if the file is a valid image it does not survive into
        #       the next form if name/email is not valid, Django issue ?
        if not form.is_valid():
            return render_to_response(upload_template, {
                                      'form': form.as_ul(),
                                      'issue' : issue,
                                      'style' : style,
                                      'display_cover' : display_cover,
                                      'upload_type' : upload_type,
                                      },
                                      context_instance=RequestContext(request))
        # if file is in form handle it
        if 'scan' in request.FILES:
            scan = request.FILES['scan']
            contributor = '%s (%s)' % (request.POST['name'],
                                       request.POST['email'])
            # put new covers into media/_local_new_scans/monthname_year/
            # name <issue_id>_<series_name>_#<issue_number>_<date>_<time>.<ext>
            scan_name = str(issue.id) + "_" + \
                        uni(issue).replace(' ','_').replace('/','-') + \
                        "_" + datetime.today().strftime('%Y%m%d_%H%M%S')
            upload_dir = settings.MEDIA_ROOT + _local_new_scans + \
                         datetime.today().strftime('%B_%Y/').lower()
            destination_name = upload_dir + scan_name + \
                               os.path.splitext(scan.name)[1]
            if not os.path.isdir(upload_dir):
                try:
                    os.mkdir(upload_dir)
                except IOError:
                    info_text = "Problem with file storage for uploaded " + \
                                "cover please contact GCD-admins." 
                    return render_to_response(error_template, {
                        'error_text' : info_text,
                        'media_url' : settings.MEDIA_URL
                        })

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
                    if check_series_cover_dir(issue.series) == False:
                        info_text = "Problem with file storage for series " + \
                          "'%s', id #%d, please contact webmaster." \
                          % (issue.series, issue.id)
                        return render_to_response(error_template, {
                            'error_text' : info_text,
                            'media_url' : settings.MEDIA_URL
                            })

                    if add_variant:
                        # we need current scan in 400 width
                        temp = tempfile.NamedTemporaryFile(suffix='.jpg')
                        size = 400,int(400./im.size[0]*im.size[1])
                        scaled = im.resize(size,Image.ANTIALIAS)
                        suffix = "%d/400/" % issue.series_id
                        suffix = suffix + "%d_4_%s.jpg" % (issue.series.id,
                                                           cover.code)
                        current_im_name = settings.MEDIA_ROOT + \
                                            _local_scans + suffix
                        # check for existence, otherwise get from server
                        if not os.path.exists(current_im_name):
                            img_url = _server_prefixes[cover.server_version] \
                                      + suffix
                            urlretrieve(img_url,current_im_name)
                        im_old = Image.open(current_im_name)

                        # backup current scan
                        backup_name = os.path.splitext(current_im_name)[0] + \
                          "_" + datetime.today().strftime('%Y%m%d_%H%M%S') + \
                          "_backup.jpg"
                        im_old.save(backup_name)

                        # and do the stacking
                        h = im_old.size[1]+scaled.size[1]
                        stacked = Image.new('RGBA',(400,h))
                        stacked.paste(im_old,(0,0))
                        stacked.paste(scaled,(0,im_old.size[1]))
                        im = stacked
                        variants = codecs.open( settings.MEDIA_ROOT + \
                                   _local_new_scans + "variant_covers", 
                                   "a", "utf-8" )
                        save_text = "series: " + str(issue.series.id) + \
                                    " issue: " + str(issue.id) + "\n"
                        save_text = uni(save_text) + "--old: " + \
                                    uni(backup_name) + "\n--add: " + \
                                    uni(destination_name) + "\n"
                        variants.write(save_text)
                        variants.close()

                    # generate different sizes
                    scaled_name = settings.MEDIA_ROOT + _local_scans + \
                      str(issue.series.id) + "/" + str(issue.series.id) + \
                      "_" + cover.code + ".jpg"
                    size = 100,int(100./im.size[0]*im.size[1])
                    scaled = im.resize(size,Image.ANTIALIAS)
                    scaled.save(scaled_name)

                    scaled_name = settings.MEDIA_ROOT + _local_scans + \
                      str(issue.series.id) + "/200/" + str(issue.series.id) + \
                      "_2_" + cover.code + ".jpg"
                    size = 200,int(200./im.size[0]*im.size[1])
                    scaled = im.resize(size,Image.ANTIALIAS)
                    scaled.save(scaled_name)

                    scaled_name = settings.MEDIA_ROOT + _local_scans + \
                      str(issue.series.id) + "/400/" + str(issue.series.id) + \
                      "_4_" + cover.code + ".jpg"
                    size = 400,int(400./im.size[0]*im.size[1])
                    scaled = im.resize(size,Image.ANTIALIAS)
                    scaled.save(scaled_name)

                    # set cover table values
                    cover.server_version = 3
                    cover.has_small = True
                    cover.has_medium = True
                    cover.has_large = True
                    cover.has_image = True
                    cover.marked = False
                    cover.contributor = contributor
                    if not cover.series.gallery_present == True:
                        series = cover.series
                        series.gallery_present = True
                        series.save()
                    cover.modified = datetime.today()                    
                    cover.modification_time = datetime.today().time()
                    cover.save()

                    if 'remember_me' in request.POST:
                        request.session['gcd_uploader_name'] = \
                          request.POST['name']
                        request.session['gcd_uploader_email'] = \
                          request.POST['email']
                    else:
                        request.session.pop('gcd_uploader_name','')
                        request.session.pop('gcd_uploader_email','')

                    tag = get_image_tag(issue.series.id, cover, 
                                        "uploaded cover", 2)
                else:
                    os.remove(destination.name)
                    info_text = "Image is too small, only " + str(im.size) + \
                                " in size."
                    return render_to_response(upload_template, {
                        'form': form.as_table(),
                        'info' : info_text,
                        'display_cover' : display_cover,
                        'upload_type' : upload_type,
                        'issue' : issue,
                        'media_url' : settings.MEDIA_URL
                        })

                # what else do we need
                covers_needed = Cover.objects.filter(issue__series = \
                  issue.series).exclude(marked = False, has_large = True)
                covers_needed = covers_needed.exclude(marked = None,
                                                      has_large = True)[:15]

                return render_to_response(uploaded_template, {
                  'cover' : cover,
                  'covers_needed' :  covers_needed,
                  'issue' : issue,
                  'tag'   : tag,
                  'style' : style},
                  context_instance=RequestContext(request))

            except IOError:
                os.remove(destination.name)
                return render_to_response(upload_template, {
                  'form': form.as_table(),
                  'info' : 'Error: File \"' + scan.name + \
                           '" is not a valid picture.',
                  'issue' : issue,
                  'display_cover' : display_cover,
                  'upload_type' : upload_type,
                  'media_url' : settings.MEDIA_URL
                  })
        else:
            return render_to_response(upload_template, { 
              'form': form.as_table(), 
              'issue' : issue,
              'style' : style},
              context_instance=RequestContext(request))

    else:
        # do we have email/name cached
        if 'gcd_uploader_email' in request.session:
            var = {'name' : request.session['gcd_uploader_name'],
                   'email' : request.session['gcd_uploader_email'],
                   'remember_me' : True}
        else:
            var = {'name' : 'Your name', 'email' : 'your@email.adress'}

        form = UploadScanForm(initial=var)
        # display the form
        return render_to_response(upload_template, {
                                  'form': form.as_ul(), 
                                  'issue' : issue,
                                  'display_cover' : display_cover,
                                  'upload_type' : upload_type,
                                  'style' : style},
                                  context_instance=RequestContext(request))


def variant_upload(request, issue_id):
    """ handle uploads of variant covers"""

    return cover_upload(request, issue_id, add_variant=True)


def mark_cover(request, issue_id):
    """
    marks the cover of the issue for replacement
    """

    # TODO: once we have permissions 'can_mark' should be one
    if request.user.is_authenticated() and \
      request.user.groups.filter(name='editor'):
        # check for issue and cover
        # TODO might do get_object_or_404 instead of own error check
        issue = Issue.objects.filter(id=int(issue_id))
        if len(issue) == 0:
            return render_to_response(error_template, {
              'error_text' : 'Issue ID #' + issue_id  + ' does not exist.',
              'media_url' : settings.MEDIA_URL
              })    
        else:
            issue = issue[0]

        cover = Cover.objects.filter(issue=issue)
        if len(cover) == 0:
            return render_to_response(error_template, {
              'error_text' : 'Something wrong with issue ID #' + issue_id  + \
                            ' and its cover table, please contact the admins.',
              'media_url' : settings.MEDIA_URL
              })    
        else:
            cover = cover[0]
        
        cover.marked = True
        cover.save()
        cover_tag = get_image_tag(issue.series_id, cover,
                                  "Cover Image", 2)
        return render_to_response(
          'gcd/details/cover_marked.html',
          {
            'issue': issue,
            'cover_tag': cover_tag,
            'error_subject': '%s cover' % issue,
            'style': 'default',
          },
          context_instance=RequestContext(request)
        )        
    else:
        return render_to_response('gcd/error.html', {
          'error_text' : 'You are not allowed to mark covers for replacement.',
          'media_url' : settings.MEDIA_URL
          })


