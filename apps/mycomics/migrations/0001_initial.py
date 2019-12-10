# -*- coding: utf-8 -*-


from django.db import models, migrations
import django.db.models.deletion
from django.conf import settings
import taggit.managers


class Migration(migrations.Migration):

    dependencies = [
        ('taggit', '0002_auto_20150616_2121'),
        ('stddata', '0001_initial'),
        ('gcd', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Collection',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(max_length=255, db_index=True)),
                ('description', models.TextField(blank=True)),
                ('public', models.BooleanField(default=False, verbose_name=b'collection is public and can be viewed by all')),
                ('condition_used', models.BooleanField(default=False, verbose_name=b'show condition')),
                ('acquisition_date_used', models.BooleanField(default=False, verbose_name=b'show acquisition date')),
                ('sell_date_used', models.BooleanField(default=False, verbose_name=b'show sell data')),
                ('location_used', models.BooleanField(default=False, verbose_name=b'show location')),
                ('purchase_location_used', models.BooleanField(default=False, verbose_name=b'show purchase location')),
                ('own_used', models.BooleanField(default=False, verbose_name=b'show own/want status')),
                ('own_default', models.NullBooleanField(default=None, verbose_name=b'default ownership status when adding items to this collection')),
                ('was_read_used', models.BooleanField(default=False, verbose_name=b'show read status')),
                ('for_sale_used', models.BooleanField(default=False, verbose_name=b'show for sale status')),
                ('signed_used', models.BooleanField(default=False, verbose_name=b'show signed status')),
                ('price_paid_used', models.BooleanField(default=False, verbose_name=b'show price paid')),
                ('market_value_used', models.BooleanField(default=False, verbose_name=b'show entered market value')),
                ('sell_price_used', models.BooleanField(default=False, verbose_name=b'show sell price')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='CollectionItem',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('notes', models.TextField(blank=True)),
                ('own', models.NullBooleanField(default=None, verbose_name=b'ownership')),
                ('was_read', models.NullBooleanField(default=None)),
                ('for_sale', models.BooleanField(default=False)),
                ('signed', models.BooleanField(default=False)),
                ('price_paid', models.DecimalField(null=True, max_digits=10, decimal_places=2, blank=True)),
                ('market_value', models.DecimalField(null=True, max_digits=10, decimal_places=2, blank=True)),
                ('sell_price', models.DecimalField(null=True, max_digits=10, decimal_places=2, blank=True)),
                ('acquisition_date', models.ForeignKey(related_name='+', blank=True, to='stddata.Date', null=True)),
                ('collections', models.ManyToManyField(related_name='items', db_table=b'mycomics_collection_item_collections', to='mycomics.Collection')),
            ],
            options={
                'ordering': ['issue__series__sort_name', 'issue__series__year_began', 'issue__sort_code', 'id'],
                'db_table': 'mycomics_collection_item',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Collector',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('default_currency', models.ForeignKey(related_name='+', blank=True, to='stddata.Currency', null=True)),
                ('default_have_collection', models.ForeignKey(related_name='+', to='mycomics.Collection', null=True)),
                ('default_language', models.ForeignKey(related_name='+', to='stddata.Language')),
                ('default_want_collection', models.ForeignKey(related_name='+', to='mycomics.Collection', null=True)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='ConditionGrade',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('code', models.CharField(max_length=20)),
                ('name', models.CharField(max_length=255)),
                ('value', models.FloatField()),
            ],
            options={
                'db_table': 'mycomics_condition_grade',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='ConditionGradeScale',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(max_length=255)),
                ('description', models.CharField(max_length=2000, blank=True)),
            ],
            options={
                'db_table': 'mycomics_condition_grade_scale',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Location',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(max_length=255, blank=True)),
                ('description', models.TextField(blank=True)),
                ('user', models.ForeignKey(to='mycomics.Collector')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='PurchaseLocation',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(max_length=255, blank=True)),
                ('description', models.TextField(blank=True)),
                ('user', models.ForeignKey(to='mycomics.Collector')),
            ],
            options={
                'db_table': 'mycomics_purchase_location',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Subscription',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('last_pulled', models.DateTimeField()),
                ('collection', models.ForeignKey(related_name='subscriptions', to='mycomics.Collection')),
                ('series', models.ForeignKey(to='gcd.Series')),
            ],
            options={
                'db_table': 'mycomics_subscription',
            },
            bases=(models.Model,),
        ),
        migrations.AddField(
            model_name='conditiongrade',
            name='scale',
            field=models.ForeignKey(related_name='grades', to='mycomics.ConditionGradeScale'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='collector',
            name='grade_system',
            field=models.ForeignKey(related_name='+', to='mycomics.ConditionGradeScale'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='collector',
            name='user',
            field=models.OneToOneField(to=settings.AUTH_USER_MODEL),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='collectionitem',
            name='grade',
            field=models.ForeignKey(related_name='+', blank=True, to='mycomics.ConditionGrade', null=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='collectionitem',
            name='issue',
            field=models.ForeignKey(to='gcd.Issue'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='collectionitem',
            name='keywords',
            field=taggit.managers.TaggableManager(to='taggit.Tag', through='taggit.TaggedItem', blank=True, help_text='A comma-separated list of tags.', verbose_name='Tags'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='collectionitem',
            name='location',
            field=models.ForeignKey(related_name='items', on_delete=django.db.models.deletion.SET_NULL, blank=True, to='mycomics.Location', null=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='collectionitem',
            name='market_value_currency',
            field=models.ForeignKey(related_name='+', blank=True, to='stddata.Currency', null=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='collectionitem',
            name='price_paid_currency',
            field=models.ForeignKey(related_name='+', blank=True, to='stddata.Currency', null=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='collectionitem',
            name='purchase_location',
            field=models.ForeignKey(related_name='items', on_delete=django.db.models.deletion.SET_NULL, blank=True, to='mycomics.PurchaseLocation', null=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='collectionitem',
            name='sell_date',
            field=models.ForeignKey(related_name='+', blank=True, to='stddata.Date', null=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='collectionitem',
            name='sell_price_currency',
            field=models.ForeignKey(related_name='+', blank=True, to='stddata.Currency', null=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='collection',
            name='collector',
            field=models.ForeignKey(related_name='collections', to='mycomics.Collector'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='collection',
            name='keywords',
            field=taggit.managers.TaggableManager(to='taggit.Tag', through='taggit.TaggedItem', blank=True, help_text='A comma-separated list of tags.', verbose_name='Tags'),
            preserve_default=True,
        ),
    ]
