# Generated by Django 3.2.11 on 2022-01-22 09:47

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('contenttypes', '0002_remove_content_type_name'),
        ('gcd', '0043_external_link'),
        ('oi', '0039_one_reprint_data_table'),
    ]

    operations = [
        migrations.CreateModel(
            name='ExternalLinkRevision',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('deleted', models.BooleanField(db_index=True, default=False)),
                ('committed', models.NullBooleanField(db_index=True, default=None)),
                ('created', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('modified', models.DateTimeField(auto_now=True, db_index=True)),
                ('object_id', models.IntegerField(db_index=True, null=True)),
                ('link', models.URLField(max_length=2000)),
                ('changeset', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='externallinkrevisions', to='oi.changeset')),
                ('content_type', models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='contenttypes.contenttype')),
                ('external_link', models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='revisions', to='gcd.externallink')),
                ('previous_revision', models.OneToOneField(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='next_revision', to='oi.externallinkrevision')),
                ('site', models.ForeignKey(help_text='External site, links to its pages that are directly related to this record can be added.', on_delete=django.db.models.deletion.CASCADE, to='gcd.externalsite')),
            ],
            options={
                'verbose_name_plural': 'External Link Revisions',
                'db_table': 'oi_external_link_revision',
                'ordering': ['created', '-id'],
            },
        ),
    ]
