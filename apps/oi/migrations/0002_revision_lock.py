# -*- coding: utf-8 -*-


from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('contenttypes', '0001_initial'),
        ('oi', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='RevisionLock',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('object_id', models.IntegerField(db_index=True)),
                ('changeset', models.ForeignKey(related_name='revision_locks', to='oi.Changeset', null=True)),
                ('content_type', models.ForeignKey(to='contenttypes.ContentType')),
            ],
            options={
                'db_table': 'oi_revision_lock',
            },
            bases=(models.Model,),
        ),
        migrations.AlterUniqueTogether(
            name='revisionlock',
            unique_together=set([('content_type', 'object_id')]),
        ),
    ]
