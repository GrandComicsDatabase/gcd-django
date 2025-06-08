# -*- coding: utf-8 -*-
from django.urls import path, re_path
from django.conf import settings
from apps.indexer import views as account_views
from apps.mycomics import views as mycomics_views

if settings.MYCOMICS:

    urlpatterns = [
        path('', mycomics_views.index, name='home'),
        path('accounts/login/', account_views.login,
            {'template_name': 'mycomics/index.html',
            'landing_view': 'collections_list'},
            name='my_login'),
        path('collection/list/',
            mycomics_views.collections_list,
            name='collections_list'),
        re_path(r'^collection/(?P<collection_id>\d+)/series/',
            mycomics_views.view_collection_series,
            name='view_collection_series'),
        re_path(r'^collection/(?P<collection_id>\d+)/edit_items/',
            mycomics_views.edit_collection_items,
            name='edit_collection_items'),
        re_path(r'^collection/(?P<collection_id>\d+)/',
            mycomics_views.view_collection,
            name='view_collection'),
        path('collection/add/',
            mycomics_views.edit_collection,
            name='add_collection'),
        re_path(r'^collection/delete/(?:(?P<collection_id>\d+)?)$',
            mycomics_views.delete_collection,
            name='delete_collection'),
        path('collection/edit/<int:collection_id>/',
            mycomics_views.edit_collection,
            name='edit_collection'),
        path('collection/export/<int:collection_id>/',
            mycomics_views.export_collection,
            name='export_collection'),
        re_path(r'^collection/pull/(?:(?P<collection_id>\d+)?)$',
            mycomics_views.subscribed_into_collection,
            name='subscribed_into_collection'),
        path('collection/subscriptions/<int:collection_id>/',
            mycomics_views.subscriptions_collection,
            name='subscriptions_collection'),

        path('item/<int:item_id>/collection/<int:collection_id>/view/',
            mycomics_views.view_item, name='view_item'),
        path('item/<int:item_id>/collection/<int:collection_id>/save/',
            mycomics_views.save_item, name='save_item'),
        path('item/<int:item_id>/collection/<int:collection_id>/move/',
            mycomics_views.move_item, name='move_item'),
        path('item/<int:item_id>/collection/<int:collection_id>/delete/',
            mycomics_views.delete_item, name='delete_item'),

        path('series/<int:series_id>/add_to_collection/',
        mycomics_views.add_series_issues_to_collection, name='my_series_issues'),
        path('issue/<int:issue_id>/add_to_collection/',
        mycomics_views.add_single_issue_to_collection, name='my_issue'),
        path('on_sale_weekly/',
        mycomics_views.select_from_on_sale_weekly, name='on_sale_this_week'),
        re_path(r'^on_sale_weekly/(?P<year>\d{4})/week/(?P<week>\d{1,2})/$',
        mycomics_views.select_from_on_sale_weekly, name='on_sale_weekly'),

        path('series/<int:series_id>/subscribe/',
        mycomics_views.subscribe_series, name='series_subscribe'),
        re_path(r'^subscription/unsubscribe/(?:(?P<subscription_id>\d+)?)$',
        mycomics_views.unsubscribe_series, name='unsubscribe'),

        path('mycomics_search/',
        mycomics_views.mycomics_search, name='mycomics_search'),

        path('message/', mycomics_views.display_message, name='display_message'),

        path('settings/', mycomics_views.mycomics_settings, name='mycomics_settings'),

        path('location/edit/<int:id>', mycomics_views.edit_location,
            name='edit_location'),
        path('location/edit/', mycomics_views.edit_location,
            name='edit_location'),
        path('purchase_location/edit/', mycomics_views.edit_purchase_location,
            name='edit_purchase_location'),
        path('purchase_location/edit/<int:id>',
            mycomics_views.edit_purchase_location, name='edit_purchase_location'),
        re_path(r'^location/delete/(?:(?P<location_id>\d+)?)$',
            mycomics_views.delete_location, name='delete_location'),
        re_path(r'^purchase_location/delete/(?:(?P<location_id>\d+)?)$',
            mycomics_views.delete_purchase_location,
            name='delete_purchase_location'),

        path('import_items/', mycomics_views.import_items, name='import_items'),
    ]

else:
    urlpatterns = [
        path('series/<int:series_id>/add_to_collection/',
            mycomics_views.add_series_issues_to_collection, name='my_series_issues'),
        path('series/<int:series_id>/subscribe/',
            mycomics_views.subscribe_series, name='series_subscribe'),
        re_path(r'^subscription/unsubscribe/(?:(?P<subscription_id>\d+)?)$',
            mycomics_views.unsubscribe_series, name='unsubscribe'),
        path('issue/<int:issue_id>/add_to_collection/',
            mycomics_views.add_single_issue_to_collection, name='my_issue'),
        path('item/<int:item_id>/collection/<int:collection_id>/view/',
            mycomics_views.view_item, name='view_item'),
        re_path(r'^collection/(?P<collection_id>\d+)/',
            mycomics_views.view_collection,
            name='view_collection'),
        path('collection/subscriptions/<int:collection_id>/',
            mycomics_views.subscriptions_collection,
            name='subscriptions_collection'),
    ]
