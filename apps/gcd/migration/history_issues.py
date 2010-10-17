from django.db import models
from django.contrib.auth.models import User
from apps.gcd.models.issue import Issue
from apps.gcd.models.indexer import Indexer
from apps.oi.models import *
from datetime import time

class LogIssues(models.Model):
    class Meta:
        db_table = 'log_issues2'
        app_label = 'gcd'

    ID = models.BigIntegerField(primary_key=True)
    VolumeNum = models.IntegerField()
    SeriesID = models.IntegerField()
    Pub_Date = models.CharField(max_length=255)
    Price = models.CharField(max_length=25)
    Modified = models.DateField()
    ModTime = models.TimeField()
    Key_Date = models.CharField(max_length=10)
    Issue = models.CharField(max_length=25)
    IssueID = models.BigIntegerField()
    UserID = models.IntegerField()


def create_issue_revision(old_change, anon):
    # create changeset
    indexer = Indexer.objects.get(id=old_change.UserID)
    changeset = Changeset(indexer=indexer.user, approver=anon,
                          state=states.APPROVED, change_type=CTYPES['issue'])
    changeset.save()

    # all dates and times guaranteed to be valid
    changeset.created = datetime.combine(old_change.Modified, old_change.ModTime)
    changeset.save()

    changeset.comments.create(commenter=indexer.user,
                              text='This change history was migrated from the old site.',
                              old_state=states.APPROVED, new_state=states.APPROVED)
    comment = changeset.comments.all()[0]
    comment.created = changeset.created
    comment.save()

    issue = Issue.objects.get(id=old_change.IssueID)
    series = Series.objects.get(id=old_change.SeriesID)
    revision = IssueRevision(changeset=changeset, issue=issue,
                             number=old_change.Issue,
                             volume=old_change.VolumeNum,
                             publication_date=old_change.Pub_Date,
                             key_date=old_change.Key_Date,
                             price=old_change.Price, series=series)
    revision.save()
    revision.created = changeset.created
    revision.save()

def add_times(no_time_issues):
    issue_id = no_time_issues[0].IssueID
    issue_date = no_time_issues[0].Modified
    seconds = 0

    # reset the seconds between issues as well as between dates inside that issue
    for change in no_time_issues:
        if issue_id != change.IssueID:
            seconds = 0
            issue_id = change.IssueID
            issue_date = change.Modified
        elif issue_date != change.Modified:
            seconds = 0
            issue_date = change.Modified
        new_time = time(0, 0, seconds)

        if change.ModTime is None:
            change.ModTime = new_time
            change.save()
            seconds += 1

def import_issue_history():
    issue_history = LogIssues.objects.order_by('ID')

    add_times(issue_history.filter(ModTime__isnull=True).order_by('IssueID', 'ID'))

    anon = User.objects.get(id=381)
    for change in issue_history:
        create_issue_revision(change, anon)

import_issue_history()