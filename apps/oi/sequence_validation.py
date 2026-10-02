"""Sequence-type rules shared by the full editor and inline workbench."""
from django import forms

from apps.gcd.models.story import NO_FEATURE_TYPES, NO_GENRE_TYPES, STORY_TYPES


def validate_sequence_page_count(cd):
    if (cd['page_count'] is None and not cd['page_count_uncertain'] and
            cd['type'].id != STORY_TYPES['insert']):
        raise forms.ValidationError(
            ['Page count uncertain must be checked if the page count '
             'is not filled in.'])


def validate_sequence_type_fields(cd):
    """Validate type-specific feature, logo, genre and story-arc constraints."""
    if (cd['feature'] or cd['feature_name'] or cd['feature_logo']) and \
       cd['type'].id in NO_FEATURE_TYPES:
        raise forms.ValidationError(
            ['The sequence type cannot have a feature.'])

    if cd['story_arc'] and cd['type'].id != STORY_TYPES['comic story']:
        raise forms.ValidationError(
            ['The sequence type cannot have a story arc.'])

    if cd['genre'] and cd['type'].id in NO_GENRE_TYPES:
        raise forms.ValidationError(
            ['The sequence type cannot have a genre.'])

    if cd['feature'] and (cd['feature_name'] or cd['feature_logo']):
        raise forms.ValidationError(
            ['Either use the text feature field or the database objects.'])

    if cd['feature_name']:
        for feature_name in cd['feature_name']:
            if cd['type'].id == STORY_TYPES['letters_page']:
                if not feature_name.feature.feature_type.id == 2:
                    raise forms.ValidationError(
                      ['Select the correct feature for a letters page.'])
            elif cd['type'].id == STORY_TYPES['in-house column']:
                if not feature_name.feature.feature_type.id == 4:
                    raise forms.ValidationError(
                      ['Select the correct feature for an in-house '
                       'column.'])
            elif feature_name.feature.feature_type.id == 3:
                if not cd['type'].id in [STORY_TYPES['ad'],
                                         STORY_TYPES['comics-form ad']]:
                    raise forms.ValidationError(
                      ['Incorrect feature for this sequence.'])
            elif feature_name.feature.feature_type.id in [2, 4]:
                raise forms.ValidationError(
                  ['Incorrect feature for this sequence.'])

    if cd['feature_logo']:
        if cd['type'].id == STORY_TYPES['cover']:
            raise forms.ValidationError(
              ['No feature logos for cover sequences.'])
        for feature_logo in cd['feature_logo']:
            if cd['type'].id == STORY_TYPES['letters_page']:
                if not feature_logo.feature_name\
                                   .filter(feature__feature_type__id=2)\
                                   .exists():
                    raise forms.ValidationError(
                      ['Select the correct feature logo for a '
                       'letters page.'])
            elif cd['type'].id == STORY_TYPES['in-house column']:
                if not feature_logo.feature_name\
                                   .filter(feature__feature_type__id=4)\
                                   .exists():
                    raise forms.ValidationError(
                      ['Select the correct feature logo for an '
                       'in-house column.'])
            elif feature_logo.feature_name\
                             .filter(feature__feature_type__id=3).exists():
                if not cd['type'].id in [STORY_TYPES['ad'],
                                         STORY_TYPES['comics-form ad']]:
                    raise forms.ValidationError(
                      ['Incorrect feature logo for this sequence.'])
            elif feature_logo.feature_name\
                             .filter(feature__feature_type_id__in=[2, 4])\
                             .exists():
                raise forms.ValidationError(
                  ['Incorrect feature logo for this sequence.'])
