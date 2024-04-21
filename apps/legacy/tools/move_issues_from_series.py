import sys

import django
from apps.gcd.models import Issue, Series

from apps.legacy.tools import migrate_reserve, do_auto_approve


def move_issues(issues, series, reserve_text, approve_text):
    changes = []
    for issue in issues:
        if issue.reserved is False:
            changeset = migrate_reserve(issue, 'issue', reserve_text)
            if changeset:
                issue_revision = changeset.issuerevisions.get()
                if issue_revision.series.publisher != series.publisher:
                    if issue_revision.brand:
                        new_brand = series.publisher.active_brands()\
                            .filter(name=issue_revision.brand.name)
                        if new_brand.count() == 1:
                            issue_revision.brand = new_brand[0]
                        else:
                            issue_revision.brand = None
                    if issue_revision.indicia_publisher:
                        name = issue_revision.indicia_publisher.name
                        new_indicia_publisher = \
                            series.publisher.active_indicia_publishers() \
                                  .filter(name=name)
                        if new_indicia_publisher.count() == 1:
                            issue_revision.indicia_publisher = \
                                new_indicia_publisher[0]
                        else:
                            issue_revision.indicia_publisher = None
                            issue_revision.no_indicia_publisher = False
                issue_revision.series = series
                issue_revision.save()
                changes.append((changeset, True))
            else:
                print("Issue %s could not be reserved" % issue)
        else:
            print("Issue %s is reserved" % issue)

        if len(changes) > 100:
            do_auto_approve(changes, approve_text)
            changes = []
    if len(changes):
        do_auto_approve(changes, approve_text)


def main():
    print(sys.argv, len(sys.argv))

    old_series_id = int(sys.argv[1])
    old_series = Series.objects.get(id=old_series_id)

    new_series_id = int(sys.argv[2])
    new_series = Series.objects.get(id=new_series_id)

    issue_list = Issue.objects.filter(series=old_series,
                                      deleted=False, reserved=False)

    if len(sys.argv) >= 4:
        num_range = list(range(int(sys.argv[3]), int(sys.argv[4])+1))
        issue_list = issue_list.filter(number__in=num_range)

    # issue_list = issue_list[:10]

    answer = input(
        'Move the %d (of %d total) issues from series %s to series %s (y/n):' %
        (issue_list.count(), old_series.issue_count, old_series, new_series))
    if answer.startswith('y'):
        reserve_text = 'for the move of an issue.'
        approve_text = 'move of an issue'

        move_issues(issue_list, new_series, reserve_text, approve_text)


if __name__ == '__main__':
    django.setup()
    main()
