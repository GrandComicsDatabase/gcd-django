# -*- coding: utf-8 -*-
"""Letters page and blank page rules of StoryRevisionForm.clean()."""

import pytest

from django import forms

from apps.gcd.models import Story, StoryType
from apps.oi.forms.story import StoryRevisionForm
from apps.oi.models import StoryRevision

LETTERS_PAGE = 'letters page'
LETTERS_RULE = 'If there is no response, then the NO script check-box'
BLANK_PAGE = 'blank page(s)'
BLANK_RULE = 'Empty page with no content.'


def _clean(user, type_name, instance=None, data=None, **values):
    """Run clean() on cleaned data of an empty sequence of the type."""
    cleaned_data = {
        'type': StoryType.objects.get(name=type_name),
        'title': '', 'title_inferred': False, 'feature': '',
        'feature_name': [], 'feature_logo': [], 'story_arc': [],
        'genre': [], 'keywords': '', 'keyword_objects': [],
        'script': '', 'pencils': '', 'inks': '', 'colors': '',
        'letters': '', 'editing': '',
        'no_script': False, 'no_pencils': False, 'no_inks': False,
        'no_colors': False, 'no_letters': False, 'no_editing': False,
        'characters': '', 'appearing_characters': [], 'group_name': None,
        'group_members': [], 'job_number': '', 'reprint_notes': '',
        'synopsis': '', 'notes': '', 'comments': '',
        'page_count': 1, 'page_count_uncertain': False,
    }
    cleaned_data.update(values)
    form_data = {'story_credit_revisions-TOTAL_FORMS': '0'}
    form_data.update(data or {})
    form = StoryRevisionForm(form_data, user=user,
                             instance=instance or StoryRevision())
    form._errors = {}
    form.cleaned_data = cleaned_data
    return form.clean()


def _rejected(user, type_name, rule, **kwargs):
    """Assert clean() rejects the sequence quoting the wiki rule."""
    with pytest.raises(forms.ValidationError) as error:
        _clean(user, type_name, **kwargs)
    assert rule in str(error.value)


def _edit_rev(story, changeset, type_name, **values):
    """Approve the story with these values and open an edit revision."""
    Story.objects.filter(pk=story.pk).update(
        type=StoryType.objects.get(name=type_name), **values)
    return StoryRevision.clone(data_object=Story.objects.get(pk=story.pk),
                               changeset=changeset)


def _row(prefix, field, value, deleted=False):
    """Posted data of a formset with one row."""
    data = {'%s-TOTAL_FORMS' % prefix: '1',
            '%s-0-%s' % (prefix, field): value}
    if deleted:
        data['%s-0-DELETE' % prefix] = 'on'
    return data


@pytest.mark.django_db
def test_letters_page_needs_script_or_no_script(any_indexer):
    """A new letters page needs a script entry or No Script."""
    _rejected(any_indexer, LETTERS_PAGE, LETTERS_RULE)
    assert _clean(any_indexer, LETTERS_PAGE, no_script=True)
    assert _clean(any_indexer, LETTERS_PAGE, script='Some Editor (response)')
    assert _clean(any_indexer, LETTERS_PAGE,
                  data=_row('story_credit_revisions', 'credit_type', '1'))
    # a script credit marked for deletion does not count
    _rejected(any_indexer, LETTERS_PAGE, LETTERS_RULE,
              data=_row('story_credit_revisions', 'credit_type', '1',
                        deleted=True))


@pytest.mark.django_db
def test_letters_page_without_script_stays_editable(any_added_story,
                                                    any_editing_changeset,
                                                    any_indexer):
    """An approved letters page without script can still be corrected."""
    rev = _edit_rev(any_added_story, any_editing_changeset, LETTERS_PAGE,
                    script='', no_script=False)
    assert _clean(any_indexer, LETTERS_PAGE, instance=rev,
                  notes='Corrected elsewhere.')
    # the same values on an added letters page are refused
    _rejected(any_indexer, LETTERS_PAGE, LETTERS_RULE,
              notes='Corrected elsewhere.')


@pytest.mark.django_db
def test_letters_page_script_cannot_be_removed(any_added_story,
                                               any_editing_changeset,
                                               any_indexer):
    """The script entry of an approved letters page cannot be dropped."""
    rev = _edit_rev(any_added_story, any_editing_changeset, LETTERS_PAGE,
                    script='Some Editor', no_script=False)
    assert _clean(any_indexer, LETTERS_PAGE, instance=rev,
                  script='Some Editor')
    _rejected(any_indexer, LETTERS_PAGE, LETTERS_RULE, instance=rev)


@pytest.mark.django_db
def test_type_changed_to_letters_page_needs_script(any_added_story,
                                                   any_editing_changeset,
                                                   any_indexer):
    """A sequence becoming a letters page needs a script entry."""
    rev = _edit_rev(any_added_story, any_editing_changeset, 'comic story',
                    script='', no_script=True)
    _rejected(any_indexer, LETTERS_PAGE, LETTERS_RULE, instance=rev)
    assert _clean(any_indexer, LETTERS_PAGE, instance=rev, no_script=True)


@pytest.mark.django_db
def test_blank_page_has_no_content(any_indexer):
    """A new blank page has no credits, characters or synopsis."""
    assert _clean(any_indexer, BLANK_PAGE)
    _rejected(any_indexer, BLANK_PAGE, 'cannot have credits', pencils='?')
    _rejected(any_indexer, BLANK_PAGE, BLANK_RULE,
              data=_row('story_credit_revisions', 'credit_type', '2'))
    _rejected(any_indexer, BLANK_PAGE, 'cannot have characters',
              characters='Test Character')
    _rejected(any_indexer, BLANK_PAGE, BLANK_RULE,
              data=_row('story_character_revisions', 'character', '1'))
    _rejected(any_indexer, BLANK_PAGE, BLANK_RULE,
              data=_row('story_group_revisions', 'group_name', '1'))
    _rejected(any_indexer, BLANK_PAGE, 'cannot have a synopsis',
              synopsis='Nothing happens.')


@pytest.mark.django_db
def test_blank_page_deleted_rows_are_ignored(any_indexer):
    """Credit and character rows marked for deletion do not count."""
    data = _row('story_credit_revisions', 'credit_type', '2', deleted=True)
    data.update(_row('story_character_revisions', 'character', '1',
                     deleted=True))
    assert _clean(any_indexer, BLANK_PAGE, data=data)
    _rejected(any_indexer, BLANK_PAGE, BLANK_RULE,
              data=_row('story_credit_revisions', 'credit_type', '2'))


@pytest.mark.django_db
def test_blank_page_with_old_content_stays_editable(any_added_story,
                                                    any_editing_changeset,
                                                    any_indexer):
    """An approved blank page keeps its content, but cannot get more."""
    rev = _edit_rev(any_added_story, any_editing_changeset, BLANK_PAGE,
                    pencils='? (logo)', synopsis='', characters='',
                    feature='', genre='')
    assert _clean(any_indexer, BLANK_PAGE, instance=rev, pencils='? (logo)',
                  notes='Corrected elsewhere.')
    _rejected(any_indexer, BLANK_PAGE, 'cannot have a synopsis',
              instance=rev, pencils='? (logo)', synopsis='Nothing happens.')


@pytest.mark.django_db
def test_type_changed_to_blank_page_drops_content(any_added_story,
                                                  any_editing_changeset,
                                                  any_indexer):
    """A sequence becoming a blank page must drop its content."""
    rev = _edit_rev(any_added_story, any_editing_changeset, 'comic story')
    _rejected(any_indexer, BLANK_PAGE, BLANK_RULE, instance=rev,
              pencils='Test Person Two')
    assert _clean(any_indexer, BLANK_PAGE, instance=rev)
