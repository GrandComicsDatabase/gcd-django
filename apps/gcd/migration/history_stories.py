from django.db import models
from django.contrib.auth.models import User
from apps.gcd.models.story import Story
from apps.gcd.models.indexer import Indexer
from apps.oi.models import *
from datetime import time

class LogStories(models.Model):
    class Meta:
        db_table = 'log_stories2'
        app_label = 'gcd'

    ID = models.BigIntegerField(primary_key=True)
    Char_App = models.CharField(max_length=255)
    Colors = models.CharField(max_length=255)
    Editing = models.CharField(max_length=255)
    Feature = models.CharField(max_length=255)
    Genre = models.CharField(max_length=255)
    Inks = models.CharField(max_length=255)
    IssueID = models.IntegerField()
    Letters = models.CharField(max_length=255)
    Modified = models.DateField()
    ModTime = models.TimeField()
    Notes = models.TextField(blank=True)
    Pencils = models.CharField(max_length=255)
    Pg_Cnt = models.IntegerField()
    Reprints = models.TextField(blank=True)
    Script = models.CharField(max_length=255)
    Seq_No = models.IntegerField()
    StoryID = models.BigIntegerField()
    Synopsis = models.TextField(blank=True)
    Title = models.CharField(max_length=255)
    Type = models.CharField(max_length=255)
    UserID = models.IntegerField()
    JobNo = models.CharField(max_length=25)


def create_story_revision(old_change, anon):
    # create changeset
    indexer = Indexer.objects.get(id=old_change.UserID)
    changeset = Changeset(indexer=indexer.user, approver=anon,
                          state=states.APPROVED, change_type=CTYPES['story'])
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

    story = Story.objects.get(id=old_change.StoryID)
    issue = Issue.objects.get(id=old_change.IssueID)
    type = StoryType.objects.get(id=old_change.Type)
    revision = StoryRevision(changeset=changeset, story=story,
                             title=old_change.Title, feature=old_change.Feature,
                             type=type, sequence_number=old_change.Seq_No,
                             page_count=old_change.Pg_Cnt,
                             script=old_change.Script,
                             pencils=old_change.Pencils, inks=old_change.Inks,
                             colors=old_change.Colors,
                             letters=old_change.Letters,
                             editing=old_change.Editing,
                             job_number=old_change.JobNo,
                             genre=old_change.Genre,
                             characters=old_change.Char_App,
                             synopsis=old_change.Synopsis,
                             reprint_notes=old_change.Reprints,
                             notes=old_change.Notes, issue=issue)
    revision.save()
    revision.created = changeset.created
    revision.save()

def add_times(no_time_stories):
    story_id = no_time_stories[0].StoryID
    story_date = no_time_stories[0].Modified
    seconds = 0

    # reset the seconds between stories as well as between dates inside that story
    for change in no_time_stories:
        if story_id != change.StoryID:
            seconds = 0
            story_id = change.StoryID
            story_date = change.Modified
        elif story_date != change.Modified:
            seconds = 0
            story_date = change.Modified
        new_time = time(0, 0, seconds)

        if change.ModTime is None:
            change.ModTime = new_time
#            change.save()
            seconds += 1

def import_story_history():
    story_history = LogStories.objects.order_by('ID')
    # replace with below and rerun if MemoryError happens.
    # clean up oi_changeset, oi_changeset_comment, and oi_issue_revision
    # tables if it stopped in the middle of processing one.
    # story_history = LogStories.objects.filter(ID__gt=156796).order_by('ID')
    print story_history.count()

    # comment out if MemoryError happens
    print story_history.filter(ModTime__isnull=True).count()
    add_times(story_history.filter(ModTime__isnull=True).order_by('StoryID', 'ID'))

    # 2010-10-17 - I think when I stopped, I had it to the point of adding the
    # modified dates / times, but was not yet at the point of creating the
    # changesets and revisions. That method above is probably just a skeleton
    # based on the publisher/series/issue import scripts and does not reflect
    # the complexities of importing story records.
    #
    # Each story changeset would need the next oldest issue revision added
    # to it. Each subsequent changeset for that issue would need the story
    # revision copied to it unless it contained a newer one of the same
    # sequence id.
    #
    # A special case needing consideration is if the earliest changeset for
    # an issue is a story revision only. It shouldn't be possible, which
    # means it is almost certainly there.

#    anon = User.objects.get(id=381)
#    for change in story_history:
#        create_story_revision(change, anon)

import_story_history()