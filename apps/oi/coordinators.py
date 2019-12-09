from datetime import datetime, timedelta

from django.conf import settings
from django.core import urlresolvers
from django.shortcuts import render
from django.contrib.auth.decorators import permission_required
from django.utils.safestring import mark_safe

from apps.oi import states
from apps.oi.models import Changeset, CTYPES

SCRIPT_DEBUG = False


def issue_untouched(c, clearing_date):
    modified = issue_revision_modified(c)
    if modified > datetime.today() - timedelta(weeks=1):
        # at max three weeks extensions
        if c.created > datetime.today() - timedelta(weeks=clearing_date + 3):
            return False
    return True


def issue_revision_modified(changeset):
    # was there an edit to the issue changeset in the last week
    modified = changeset.issuerevisions.latest('modified').modified
    if changeset.storyrevisions.exists():
        modified_story = changeset.storyrevisions.latest('modified')
        if modified < modified_story.modified:
            modified = modified_story.modified
    return modified


@permission_required('oi.change_ongoingreservation')
def clear_reservations_three_weeks(request=None):
    clearing_date = datetime.today() - \
                    timedelta(weeks=settings.RESERVE_ISSUE_WEEKS)
    final_clearing_date = datetime.today() - \
                          timedelta(weeks=settings.RESERVE_ISSUE_INITIAL_WEEKS)
    changes = Changeset.objects.filter(created__lt=clearing_date,
                                       state=states.OPEN)
    changes_issue = changes.filter(change_type__in=[CTYPES['issue'],
                                                    CTYPES['two_issues'],
                                                    CTYPES['variant_add']])
    changes_overdue = list(changes.exclude(change_type__in=
                                           [CTYPES['issue'],
                                            CTYPES['two_issues'],
                                            CTYPES['variant_add']]))
    for c in changes_issue:
        # issue edits with more than two existing revisions cannot be
        # changes due to ongoing reservations (which have more time)
        # Revision 0:  Initial add of the issue
        # Revision 1:  Potentially an automatic edit due to ongoing reservation
        # Revision 2:  Definitely not the result of an ongoing reservation.
        if c.issuerevisions.earliest('created').issue.revisions.count() > 2:
            if issue_untouched(c, settings.RESERVE_ISSUE_WEEKS):
                changes_overdue.append(c)
        elif c.created <= final_clearing_date and \
          issue_untouched(c, settings.RESERVE_ISSUE_INITIAL_WEEKS):
            changes_overdue.append(c)
    return clear_reservations(request, changes_overdue)


@permission_required('oi.change_ongoingreservation')
def clear_reservations_one_week(request=None):
    clearing_date = datetime.today() - \
                    timedelta(days=settings.RESERVE_NON_ISSUE_DAYS)
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
           urlresolvers.reverse('compare', kwargs={'id': changeset.id}),
           str(changeset),
           str(changeset.indexer.indexer))
        if changed:
            if not SCRIPT_DEBUG:
                changeset.submit(notes='This is an automatic submit for an '
                                 'old reservation. If the change contains '
                                 'useful information but needs correction '
                                 'please reserve and edit after approval.')
            submitted_list.append(mark_safe(info_text))
        else:
            if not SCRIPT_DEBUG:
                changeset.discard(changeset.indexer, notes='This is an '
                                  'automatic discard of an unchanged edit '
                                  'which was reserved for 9 weeks')
            discarded_list.append(mark_safe(info_text))
    return render(request, 'oi/edit/clear_reservations.html',
                  {'submitted_list': submitted_list,
                   'discarded_list': discarded_list})
