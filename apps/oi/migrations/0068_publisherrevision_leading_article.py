from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('oi', '0067_changeset_comment_utf8mb4'),
    ]

    operations = [
        migrations.AddField(
            model_name='publisherrevision',
            name='leading_article',
            field=models.BooleanField(default=False),
        ),
    ]
