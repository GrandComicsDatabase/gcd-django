# -*- coding: utf-8 -*-


from django.db import models, migrations
from apps.oi import states

def actual_move(apps, stories):
    if stories.count():
        StoryRevision = apps.get_model('oi', 'StoryRevision')
        ContentType = apps.get_model('contenttypes', 'ContentType')
        RevisionLock = apps.get_model('oi', 'RevisionLock')

        ct = ContentType.objects.get(app_label='gcd',
                                    model='story')
        for story in stories:
            if not RevisionLock.objects.filter(object_id=story.id,
                                              content_type=ct).first():
                story.first_line = story.title[1:-1]
                story.title = ''
                story.title_inferred = False
                story.save()
                revision = story.revisions.filter(committed=True).latest('created')
                revision.first_line = story.first_line
                revision.title = story.title
                revision.title_inferred = False
                revision.save()
            else:
                revision = story.revisions.get(changeset__state__in=states.ACTIVE)
                revision.first_line = story.title[1:-1]
                revision.title = ''
                revision.title_inferred = False
                revision.save()

def move_first_line_from_title(apps, schema_editor):
    Story = apps.get_model('gcd', 'Story')

    stories=Story.objects.filter(title_inferred=True,
                                 title__startswith='"',
                                 title__endswith='"',
                                 deleted=False)
    actual_move(apps, stories)

    stories=Story.objects.filter(title_inferred=True,
                                 title__startswith='"',
                                 title__endswith="'",
                                 deleted=False)
    actual_move(apps, stories)

    stories=Story.objects.filter(title_inferred=True,
                                 title__startswith="'",
                                 title__endswith='"',
                                 deleted=False)
    actual_move(apps, stories)

    stories=Story.objects.filter(title_inferred=True,
                                 title__startswith="'",
                                 title__endswith="'",
                                 deleted=False)
    actual_move(apps, stories)

    stories=Story.objects.filter(title_inferred=True,
                                 title__startswith='“',
                                 title__endswith='”',
                                 deleted=False)
    actual_move(apps, stories)

    stories=Story.objects.filter(title_inferred=True,
                                 title__startswith='"',
                                 title__endswith='\u201d',
                                 deleted=False)
    actual_move(apps, stories)

class Migration(migrations.Migration):

    dependencies = [
        ('gcd', '0007_story_first_line'),
        ('oi', '0009_storyrevision_first_line'),
    ]

    operations = [
        migrations.RunPython(move_first_line_from_title)
    ]
