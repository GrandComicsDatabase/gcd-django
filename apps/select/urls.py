from django.urls import path
from apps.select import views as select_views

urlpatterns = [
    path('issue/<int:issue_id>/cache/', select_views.cache_content,
        name='cache_issue'),
    path('story/<int:story_id>/cache/', select_views.cache_content,
        name='cache_story'),
    path('cover/<int:cover_story_id>/cache/', select_views.cache_content,
        name='cache_cover'),

    path('select_object/<path:select_key>/search/',
      select_views.process_select_search, name='select_object_search'),
    path('select_object/<path:select_key>/search_haystack/',
      select_views.process_select_search_haystack, name='select_object_search_haystack'),
    path('select_object/<path:select_key>/', select_views.select_object,
      name='select_object'),

    path('select_objects/<path:select_key>/',
      select_views.process_multiple_selects, name='process_multiple_selects'),

    path(
        'select/creator/by_detail/',
        select_views.creator_for_detail,
        name='select_creator_for_detail',
    ),

    path(
        'autocomplete/creator/',
        select_views.CreatorAutocomplete.as_view(),
        name='creator_autocomplete',
    ),
    path(
        'autocomplete/creator_name/',
        select_views.CreatorNameAutocomplete.as_view(),
        name='creator_name_autocomplete',
    ),
    path(
        'autocomplete/creator_name_4_relation/',
        select_views.CreatorName4RelationAutocomplete.as_view(),
        name='creator_name_4_relation_autocomplete',
    ),
    path(
        'autocomplete/creator_signature/',
        select_views.CreatorSignatureAutocomplete.as_view(),
        name='creator_signature_autocomplete',
    ),
    path(
        'autocomplete/feature/',
        select_views.FeatureAutocomplete.as_view(),
        name='feature_autocomplete',
    ),
    path(
        'autocomplete/feature_logo/',
        select_views.FeatureLogoAutocomplete.as_view(),
        name='feature_logo_autocomplete',
    ),
    path(
        'autocomplete/story_arc/',
        select_views.StoryArcAutocomplete.as_view(),
        name='story_arc_autocomplete',
    ),
    path(
        'autocomplete/character/',
        select_views.CharacterAutocomplete.as_view(),
        name='character_autocomplete',
    ),
    path(
        'autocomplete/character_name/',
        select_views.CharacterNameAutocomplete.as_view(),
        name='character_name_autocomplete',
    ),
    path(
        'autocomplete/group/',
        select_views.GroupAutocomplete.as_view(),
        name='group_autocomplete',
    ),
    path(
        'autocomplete/group_name/',
        select_views.GroupNameAutocomplete.as_view(),
        name='group_name_autocomplete',
    ),
    path(
        'autocomplete/universe/',
        select_views.UniverseAutocomplete.as_view(),
        name='universe_autocomplete',
    ),
    path(
        'autocomplete/brand_group/',
        select_views.BrandGroupAutocomplete.as_view(),
        name='brand_group_autocomplete',
    ),
    path(
        'autocomplete/brand_emblem/',
        select_views.BrandEmblemAutocomplete.as_view(),
        name='brand_emblem_autocomplete',
    ),
    path(
        'autocomplete/indicia_printer/',
        select_views.IndiciaPrinterAutocomplete.as_view(),
        name='indicia_printer_autocomplete',
    ),
    path(
        'autocomplete/keyword/',
        select_views.KeywordAutocomplete.as_view(create_field='name',
                                                 validate_create=True),
        name='keyword_autocomplete',
    ),
    path(
        'autocomplete/school/',
        select_views.SchoolAutocomplete.as_view(),
        name='school_autocomplete',
    ),
]
