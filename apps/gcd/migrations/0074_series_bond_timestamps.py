from django.db import migrations, models
from django.db.models import OuterRef, Subquery, Value
from django.db.models.functions import Coalesce
from django.utils import timezone


APPROVED = 5


def backfill_series_bond_timestamps(apps, schema_editor):
    """Backfill known revision dates or a shared tracking baseline."""
    series_bond = apps.get_model('gcd', 'SeriesBond')
    series_bond_revision = apps.get_model('oi', 'SeriesBondRevision')
    database = schema_editor.connection.alias
    baseline = timezone.now()
    approved_revisions = series_bond_revision.objects.using(database).filter(
        series_bond_id=OuterRef('pk'),
        changeset__state=APPROVED,
    )
    earliest_created = approved_revisions.order_by(
        'created',
        'id',
    ).values('created')[:1]
    latest_modified = approved_revisions.order_by(
        '-created',
        '-id',
    ).values('modified')[:1]
    baseline_value = Value(
        baseline,
        output_field=models.DateTimeField(),
    )

    series_bond.objects.using(database).update(
        created=Coalesce(Subquery(earliest_created), baseline_value),
        modified=Coalesce(Subquery(latest_modified), baseline_value),
    )


class Migration(migrations.Migration):

    dependencies = [
        ('gcd', '0073_merge_api_v2_beta'),
        ('oi', '0062_add_character_order'),
    ]

    operations = [
        migrations.AddField(
            model_name='seriesbond',
            name='created',
            field=models.DateTimeField(null=True),
        ),
        migrations.AddField(
            model_name='seriesbond',
            name='modified',
            field=models.DateTimeField(db_index=True, null=True),
        ),
        migrations.RunPython(
            backfill_series_bond_timestamps,
            migrations.RunPython.noop,
        ),
        migrations.AlterField(
            model_name='seriesbond',
            name='created',
            field=models.DateTimeField(auto_now_add=True),
        ),
        migrations.AlterField(
            model_name='seriesbond',
            name='modified',
            field=models.DateTimeField(auto_now=True, db_index=True),
        ),
    ]
