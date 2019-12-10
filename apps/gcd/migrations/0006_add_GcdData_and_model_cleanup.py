# -*- coding: utf-8 -*-


from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('gcd', '0006_award_editable'),
        ('oi', '0003_migrate_reservations_to_locks'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='brand',
            name='parent',
        ),
        migrations.RemoveField(
            model_name='brand',
            name='reserved',
        ),
        migrations.RemoveField(
            model_name='brandgroup',
            name='reserved',
        ),
        migrations.RemoveField(
            model_name='creator',
            name='reserved',
        ),
        migrations.RemoveField(
            model_name='creatorartinfluence',
            name='reserved',
        ),
        migrations.RemoveField(
            model_name='creatoraward',
            name='reserved',
        ),
        migrations.RemoveField(
            model_name='creatordegree',
            name='reserved',
        ),
        migrations.RemoveField(
            model_name='creatormembership',
            name='reserved',
        ),
        migrations.RemoveField(
            model_name='creatornamedetail',
            name='reserved',
        ),
        migrations.RemoveField(
            model_name='creatornoncomicwork',
            name='reserved',
        ),
        migrations.RemoveField(
            model_name='creatorrelation',
            name='reserved',
        ),
        migrations.RemoveField(
            model_name='creatorschool',
            name='reserved',
        ),
        migrations.RemoveField(
            model_name='datasource',
            name='reserved',
        ),
        migrations.RemoveField(
            model_name='indiciapublisher',
            name='reserved',
        ),
        migrations.RemoveField(
            model_name='issue',
            name='reserved',
        ),
        migrations.RemoveField(
            model_name='publisher',
            name='imprint_count',
        ),
        migrations.RemoveField(
            model_name='publisher',
            name='is_master',
        ),
        migrations.RemoveField(
            model_name='publisher',
            name='parent',
        ),
        migrations.RemoveField(
            model_name='publisher',
            name='reserved',
        ),
        migrations.RemoveField(
            model_name='series',
            name='open_reserve',
        ),
        migrations.RemoveField(
            model_name='series',
            name='publication_notes',
        ),
        migrations.RemoveField(
            model_name='series',
            name='reserved',
        ),
        migrations.RemoveField(
            model_name='story',
            name='reserved',
        ),
        migrations.AlterField(
            model_name='brand',
            name='modified',
            field=models.DateTimeField(auto_now=True, db_index=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='brandgroup',
            name='modified',
            field=models.DateTimeField(auto_now=True, db_index=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='creator',
            name='modified',
            field=models.DateTimeField(auto_now=True, db_index=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='creatorartinfluence',
            name='modified',
            field=models.DateTimeField(auto_now=True, db_index=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='creatoraward',
            name='modified',
            field=models.DateTimeField(auto_now=True, db_index=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='creatordegree',
            name='modified',
            field=models.DateTimeField(auto_now=True, db_index=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='creatormembership',
            name='modified',
            field=models.DateTimeField(auto_now=True, db_index=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='creatornamedetail',
            name='modified',
            field=models.DateTimeField(auto_now=True, db_index=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='creatornoncomicwork',
            name='modified',
            field=models.DateTimeField(auto_now=True, db_index=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='creatorrelation',
            name='modified',
            field=models.DateTimeField(auto_now=True, db_index=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='creatorschool',
            name='modified',
            field=models.DateTimeField(auto_now=True, db_index=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='datasource',
            name='modified',
            field=models.DateTimeField(auto_now=True, db_index=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='indiciapublisher',
            name='modified',
            field=models.DateTimeField(auto_now=True, db_index=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='publisher',
            name='modified',
            field=models.DateTimeField(auto_now=True, db_index=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='series',
            name='modified',
            field=models.DateTimeField(auto_now=True, db_index=True),
            preserve_default=True,
        ),
    ]
