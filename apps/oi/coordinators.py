from datetime import datetime, timedelta

from django.core import urlresolvers
from django.shortcuts import render_to_response
from django.template import RequestContext
from django.contrib.auth.decorators import permission_required

from apps.oi import states
from apps.oi.models import *

SCRIPT_DEBUG = True

@permission_required('oi.change_ongoingreservation')
def clear_reservations_nine_weeks(request=None):
    clearing_date = datetime.today()-timedelta(weeks=9)
    changes = Changeset.objects.filter(created__lt=clearing_date,
                                       state=states.OPEN)
    return clear_reservations(request, changes)

@permission_required('oi.change_ongoingreservation')
def clear_reservations_one_week(request=None):
    clearing_date = datetime.today()-timedelta(weeks=1)
    changes = Changeset.objects.filter(created__lt=clearing_date,
      state=states.OPEN).filter(change_type__in=[CTYPES['publisher'],
                                                 CTYPES['brand'],
                                                 CTYPES['indicia_publisher'],
                                                 CTYPES['series']])
    return clear_reservations(request, changes)

@permission_required('oi.change_ongoingreservation')
def clear_reservations(request=None, changes=None):
    submitted_list = []
    discarded_list = []
    for changeset in changes:
        changed = False
        if changeset.inline():
            revision = changeset.inline_revision()
        elif changeset.issuerevisions.count() > 0:
            revision = changeset.issuerevisions.all()[0]
        else:
            raise NotImplementedError

        # old (forgotten) cover uploads stay unchanged and get discarded
        if changeset.change_type != CTYPES['cover']:
            revision.compare_changes()
            if revision.is_changed:
                changed = True

        if not changed and changeset.storyrevisions.count():
            for story in changeset.storyrevisions.all():
                story.compare_changes()
                if story.is_changed:
                     changed = True

        info_text = 'Created: %s <a href="%s%s">Change: %s</a> Indexer: %s' % \
          (str(changeset.created), settings.SITE_URL,
           urlresolvers.reverse('compare', kwargs={'id': changeset.id }),
           str(changeset),
           str(changeset.indexer.indexer))
        if changed:
            if not SCRIPT_DEBUG:
                changeset.submit(notes='This is an automatic submit for an '
                    'old reservation. If the change contains useful information '
                    'but needs correction please reserve and edit after approval.')
            submitted_list.append(mark_safe(info_text))
        else:
            if not SCRIPT_DEBUG:
                changeset.discard(changeset.indexer,notes='This is an automatic discard of '
                    'an unchanged edit which was reserved for 9 weeks')
            discarded_list.append(mark_safe(info_text))
    return render_to_response('oi/edit/clear_reservations.html',
      {
        'submitted_list': submitted_list,
        'discarded_list': discarded_list
      },
      context_instance=RequestContext(request))
