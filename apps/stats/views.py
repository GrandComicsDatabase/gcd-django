# -*- coding: utf-8 -*-


import os
import os.path
import stat
import errno
from datetime import datetime, timedelta

from django.conf import settings
from django.http import FileResponse
from django.shortcuts import render
from django.contrib.auth.decorators import login_required

from apps.indexer.views import render_error
from apps.stats.models import Download
from apps.stats.forms import DownloadForm


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
                return render_error(
                    request,
                    ("You have started a download of this file within the "
                     "last %d minutes.  Please check your download window.  "
                     "If you need to start a new download, please wait at "
                     "least %d minutes in order to avoid consuming excess "
                     "bandwidth.") % (delta, delta))

            desc = {'file': file, 'accepted license': True}
            if 'purpose' in cd and cd['purpose']:
                desc['purpose'] = cd['purpose']
            if 'usage' in cd and cd['usage']:
                desc['usage'] = cd['usage']

            record = Download(user=request.user, description=repr(desc))
            record.save()

            response = FileResponse(open(path, 'rb'),
                                    content_type='application/zip')
            response['Content-Disposition'] = \
                'attachment; filename=current.zip'
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
                 datetime.utcfromtimestamp(
                    os.stat(dump_info[1])[stat.ST_MTIME])))
        except OSError as ose:
            if ose.errno == errno.ENOENT:
                timestamps.append((dump_info[0], 'never'))
            else:
                raise

    return render(request, 'stats/download.html',
                  {'method': request.method,
                   'timestamps': timestamps,
                   'form': form, })
