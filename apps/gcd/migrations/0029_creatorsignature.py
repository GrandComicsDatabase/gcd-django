# Generated by Django 2.2.12 on 2020-05-29 20:50

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('gcd', '0028_add_printer'),
    ]

    operations = [
        migrations.CreateModel(
            name='CreatorSignature',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('modified', models.DateTimeField(auto_now=True, db_index=True)),
                ('deleted', models.BooleanField(db_index=True, default=False)),
                ('name', models.CharField(db_index=True, max_length=255)),
                ('notes', models.TextField()),
                ('generic', models.BooleanField(default=False)),
                ('creator', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='signatures', to='gcd.Creator')),
                ('data_source', models.ManyToManyField(to='gcd.DataSource')),
            ],
            options={
                'verbose_name_plural': 'Creator Signatures',
                'db_table': 'gcd_creator_signature',
                'ordering': ['name', '-creator__sort_name', '-creator__birth_date__year'],
            },
        ),
    ]
