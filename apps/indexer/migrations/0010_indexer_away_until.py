from django.db import migrations, models


class Migration(migrations.Migration):
    """Add the date until which an editor is away."""

    dependencies = [
        ('indexer', '0009_indexer_items_per_page'),
    ]

    operations = [
        migrations.AddField(
            model_name='indexer',
            name='away_until',
            field=models.DateField(
              blank=True, null=True,
              help_text='Up to and including this day, changes that would '
                        'go to this editor go to the general queue.'),
        ),
    ]
