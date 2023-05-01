from django.conf.urls import url
from apps.select import views as select_views

urlpatterns = [
    url(r'^issue/(?P<issue_id>\d+)/cache/$', select_views.cache_content,
        name='cache_issue'),
    url(r'^story/(?P<story_id>\d+)/cache/$', select_views.cache_content,
        name='cache_story'),
    url(r'^cover/(?P<cover_story_id>\d+)/cache/$', select_views.cache_content,
        name='cache_cover'),

    url(r'^select_object/(?P<select_key>.+)/search/$',
      select_views.process_select_search, name='select_object_search'),
    url(r'^select_object/(?P<select_key>.+)/search_haystack/$',
      select_views.process_select_search_haystack, name='select_object_search_haystack'),
    url(r'^select_object/(?P<select_key>.+)/$', select_views.select_object,
      name='select_object'),

    url(r'^select_objects/(?P<select_key>.+)/$',
      select_views.process_multiple_selects, name='process_multiple_selects'),

    url(
        r'^select/creator/by_detail/$',
        select_views.creator_for_detail,
        name='select_creator_for_detail',
    ),

    url(
        r'^autocomplete/creator/$',
        select_views.CreatorAutocomplete.as_view(),
        name='creator_autocomplete',
    ),
    url(
        r'^autocomplete/creator_name/$',
        select_views.CreatorNameAutocomplete.as_view(),
        name='creator_name_autocomplete',
    ),
    url(
        r'^autocomplete/creator_name_4_relation/$',
        select_views.CreatorName4RelationAutocomplete.as_view(),
        name='creator_name_4_relation_autocomplete',
    ),
    url(
        r'^autocomplete/creator_signature/$',
        select_views.CreatorSignatureAutocomplete.as_view(),
        name='creator_signature_autocomplete',
    ),
    url(
        r'^autocomplete/feature/$',
        select_views.FeatureAutocomplete.as_view(),
        name='feature_autocomplete',
    ),
    url(
        r'^autocomplete/feature_logo/$',
        select_views.FeatureLogoAutocomplete.as_view(),
        name='feature_logo_autocomplete',
    ),
    url(
        r'^autocomplete/character/$',
        select_views.CharacterAutocomplete.as_view(),
        name='character_autocomplete',
    ),
    url(
        r'^autocomplete/character_name/$',
        select_views.CharacterNameAutocomplete.as_view(),
        name='character_name_autocomplete',
    ),
    url(
        r'^autocomplete/group/$',
        select_views.GroupAutocomplete.as_view(),
        name='group_autocomplete',
    ),
    url(
        r'^autocomplete/indicia_printer/$',
        select_views.IndiciaPrinterAutocomplete.as_view(),
        name='indicia_printer_autocomplete',
    ),
    url(
        r'^autocomplete/school/$',
        select_views.SchoolAutocomplete.as_view(),
        name='school_autocomplete',
    ),
]
