from django.db import migrations, models
from django.db.models import F


def fill_sort_name(apps, schema_editor):
    """Sort every publisher by its name, as before."""
    Publisher = apps.get_model('gcd', 'Publisher')
    Publisher.objects.update(sort_name=F('name'))


class Migration(migrations.Migration):

    dependencies = [
        ('gcd', '0071_feature_description'),
    ]

    operations = [
        migrations.AddField(
            model_name='publisher',
            name='sort_name',
            field=models.CharField(db_index=True, default='', max_length=255,
                                   serialize=False),
        ),
        migrations.RunPython(fill_sort_name, migrations.RunPython.noop),
    ]
