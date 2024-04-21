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
from apps.gcd.models import Creator, Publisher, Series
from apps.indexer.models import Indexer
from apps.stddata.models import Country

@login_required
def download(request):

    if request.method == 'POST':
        form = DownloadForm(request.POST)
        if form.is_valid():
            cd = form.cleaned_data

            # Note that the submit input is never present in the cleaned data.
            file = settings.MYSQL_DUMP
            if ('name-value' in request.POST):
                file = settings.NAME_VALUE_DUMP
            if ('sqlite' in request.POST):
                file = settings.SQLITE_DUMP
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
    nv_path = os.path.join(settings.MEDIA_ROOT, settings.DUMP_DIR,
                           settings.NAME_VALUE_DUMP)
    sqlite_path = os.path.join(settings.MEDIA_ROOT, settings.DUMP_DIR,
                               settings.SQLITE_DUMP)

    # Use a list of tuples because we want the MySQL dump (our primary format)
    # to be first.
    timestamps = []
    for dump_info in (('MySQL', m_path), ('Name-Value', nv_path), ('SQLite', sqlite_path), ):
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


def countries_in_use(request):
    """
    Show list of countries with name and flag.
    Main use is to find missing names and flags.
    """

    if request.user.is_authenticated and \
       request.user.groups.filter(name='admin'):
        countries_from_series = set(
                Series.objects.exclude(deleted=True).
                values_list('country', flat=True))
        countries_from_indexers = set(
                Indexer.objects.filter(user__is_active=True).
                values_list('country', flat=True))
        countries_from_publishers = set(
                Publisher.objects.exclude(deleted=True).
                values_list('country', flat=True))
        countries_from_creators = set(
                country for tuple in
                Creator.objects.exclude(deleted=True).
                values_list('birth_country', 'death_country')
                for country in tuple)
        used_ids = list(countries_from_indexers |
                        countries_from_series |
                        countries_from_publishers |
                        countries_from_creators)
        used_countries = Country.objects.filter(id__in=used_ids)

        return render(request, 'gcd/admin/countries.html',
                      {'countries': used_countries})
    else:
        return render(request, 'indexer/error.html',
                      {'error_text':
                       'You are not allowed to access this page.'})
