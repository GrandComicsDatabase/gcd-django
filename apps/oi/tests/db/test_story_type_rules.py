# -*- coding: utf-8 -*-
"""Sequence type rules from the wiki in StoryRevisionForm.clean()."""

import mock
import pytest

from django import forms

from apps.gcd.models import Feature, FeatureLogo, FeatureNameDetail, \
                            FeatureType, Story, StoryType
from apps.oi.forms.story import StoryCreditRevisionForm, StoryRevisionForm
from apps.oi.models import StoryCreditRevision, StoryRevision
from apps.oi.templatetags.compare import show_type_notes
from apps.oi.views import _cover_order_error, _covers_out_of_order
from apps.select.views import FeatureLogoAutocomplete, \
                              FeatureNameAutocomplete, StoryArcAutocomplete

LETTERS_PAGE = 'letters page'
BLANK_PAGE = 'blank page(s)'
INSERT = 'insert or dust jacket'


def _clean(user, type_name, instance=None, data=None,
           form_class=StoryRevisionForm, **values):
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
    form = form_class(form_data, user=user,
                      instance=instance or StoryRevision())
    form._errors = {}
    form.cleaned_data = cleaned_data
    return form.clean()


def _edit_rev(story, changeset, type_name, **values):
    """Approve the story with these values and open an edit revision."""
    Story.objects.filter(pk=story.pk).update(
        type=StoryType.objects.get(name=type_name), **values)
    return StoryRevision.clone(data_object=Story.objects.get(pk=story.pk),
                               changeset=changeset)


def _rejected(user, type_name, wiki_page, **kwargs):
    """Assert clean() rejects the sequence citing the wiki page."""
    with pytest.raises(forms.ValidationError) as error:
        _clean(user, type_name, **kwargs)
    assert wiki_page in str(error.value)


@pytest.mark.django_db
def test_letters_page_needs_script_or_no_script(any_indexer):
    """A new letters page needs a script entry or No Script."""
    _rejected(any_indexer, LETTERS_PAGE, 'Letters and Fan Art')
    assert _clean(any_indexer, LETTERS_PAGE, no_script=True)
    assert _clean(any_indexer, LETTERS_PAGE,
                  script='Julius Schwartz (response)')
    assert _clean(any_indexer, LETTERS_PAGE, data={
      'story_credit_revisions-TOTAL_FORMS': '1',
      'story_credit_revisions-0-credit_type': '1'})


@pytest.mark.django_db
def test_letters_page_without_script_stays_editable(any_added_story,
                                                    any_editing_changeset,
                                                    any_indexer):
    """An approved letters page without script can still be corrected."""
    rev = _edit_rev(any_added_story, any_editing_changeset, LETTERS_PAGE,
                    script='', no_script=False)
    assert _clean(any_indexer, LETTERS_PAGE, instance=rev,
                  notes='corrected elsewhere')


@pytest.mark.django_db
def test_letters_page_script_cannot_be_removed(any_added_story,
                                               any_editing_changeset,
                                               any_indexer):
    """The script entry of an approved letters page cannot be dropped."""
    rev = _edit_rev(any_added_story, any_editing_changeset, LETTERS_PAGE,
                    script='Julius Schwartz', no_script=False)
    _rejected(any_indexer, LETTERS_PAGE, 'Letters and Fan Art',
              instance=rev)


@pytest.mark.django_db
def test_type_changed_to_letters_page_needs_script(any_added_story,
                                                   any_editing_changeset,
                                                   any_indexer):
    """A sequence becoming a letters page needs a script entry."""
    rev = _edit_rev(any_added_story, any_editing_changeset, 'comic story',
                    script='', no_script=True)
    _rejected(any_indexer, LETTERS_PAGE, 'Letters and Fan Art',
              instance=rev)


@pytest.mark.django_db
def test_blank_page_has_no_content(any_indexer):
    """A new blank page has no credits, characters or synopsis."""
    assert _clean(any_indexer, BLANK_PAGE, no_pencils=True)
    _rejected(any_indexer, BLANK_PAGE, 'Empty page with no content',
              pencils='?')
    _rejected(any_indexer, BLANK_PAGE, 'Empty page with no content', data={
      'story_credit_revisions-TOTAL_FORMS': '1',
      'story_credit_revisions-0-credit_type': '2'})
    _rejected(any_indexer, BLANK_PAGE, 'Empty page with no content',
              characters='Superman')
    _rejected(any_indexer, BLANK_PAGE, 'Empty page with no content', data={
      'story_character_revisions-TOTAL_FORMS': '1',
      'story_character_revisions-0-character': '1'})
    _rejected(any_indexer, BLANK_PAGE, 'Empty page with no content',
              synopsis='Nothing happens.')


@pytest.mark.django_db
def test_blank_page_deleted_credit_row_is_ignored(any_indexer):
    """A credit row marked for deletion does not count."""
    assert _clean(any_indexer, BLANK_PAGE, data={
      'story_credit_revisions-TOTAL_FORMS': '1',
      'story_credit_revisions-0-credit_type': '2',
      'story_credit_revisions-0-DELETE': 'on'})


@pytest.mark.django_db
def test_blank_page_with_old_content_stays_editable(any_added_story,
                                                    any_editing_changeset,
                                                    any_indexer):
    """An approved blank page keeps its content, but cannot get more."""
    rev = _edit_rev(any_added_story, any_editing_changeset, BLANK_PAGE,
                    pencils='? (logo)', synopsis='', characters='',
                    feature='', genre='')
    assert _clean(any_indexer, BLANK_PAGE, instance=rev, pencils='? (logo)',
                  notes='corrected elsewhere')
    _rejected(any_indexer, BLANK_PAGE, 'Empty page with no content',
              instance=rev, pencils='? (logo)', synopsis='Nothing happens.')


@pytest.mark.django_db
def test_type_changed_to_blank_page_drops_content(any_added_story,
                                                  any_editing_changeset,
                                                  any_indexer):
    """A sequence becoming a blank page must drop its credits."""
    rev = _edit_rev(any_added_story, any_editing_changeset, 'comic story')
    _rejected(any_indexer, BLANK_PAGE, 'Empty page with no content',
              instance=rev, pencils='Test Person Two')


@pytest.mark.django_db
def test_insert_needs_page_count_or_uncertain(any_indexer):
    """A new insert needs a page count or Page count uncertain."""
    _rejected(any_indexer, INSERT, 'Page Count', page_count=None)
    assert _clean(any_indexer, INSERT, page_count=None,
                  page_count_uncertain=True)
    assert _clean(any_indexer, INSERT, page_count=4)


@pytest.mark.django_db
def test_insert_without_page_count_stays_editable(any_added_story,
                                                  any_editing_changeset,
                                                  any_indexer):
    """An approved insert without page count can still be corrected."""
    rev = _edit_rev(any_added_story, any_editing_changeset, INSERT,
                    page_count=None, page_count_uncertain=False)
    assert _clean(any_indexer, INSERT, instance=rev, page_count=None,
                  notes='corrected elsewhere')


@pytest.mark.django_db
def test_type_changed_to_insert_needs_page_count(any_added_story,
                                                 any_editing_changeset,
                                                 any_indexer):
    """A sequence becoming an insert keeps the page count rule."""
    rev = _edit_rev(any_added_story, any_editing_changeset, 'comic story')
    _rejected(any_indexer, INSERT, 'Page Count', instance=rev,
              page_count=None)


TEXT_STORY = 'text story'


@pytest.mark.django_db
@pytest.mark.parametrize('field, value, wiki', [
    ('script', 'n/a', 'Credits'),
    ('pencils', 'Joe Kubert; none', 'Credits'),
    ('inks', 'Joe Kubert;Dick Giordano', 'Credits'),
    ('colors', 'Joe Kubert?', 'Credits'),
    ('letters', 'Typeset', 'Style Guide'),
    ('editing', 'Julius Schwartz, Jr.', 'Style Guide'),
    ('characters', 'Martin Luther King Jr', 'Style Guide'),
    ('title', 'Wait . . . what', 'Style Guide'),
    ('title', 'When Titans Clash...the End', 'Style Guide')])
def test_format_rules_refuse_new_values(any_indexer, field, value, wiki):
    """Values breaking a format rule of the wiki are refused."""
    _rejected(any_indexer, TEXT_STORY, 'Wiki "%s"' % wiki, **{field: value})


@pytest.mark.django_db
@pytest.mark.parametrize('field, value', [
    ('script', '?'), ('script', 'Nonesuch Smith'),
    ('pencils', 'Joe Kubert; Dick Giordano'), ('colors', 'Joe Kubert ?'),
    ('letters', 'typeset'), ('editing', 'Julius Schwartz Jr.'),
    ('characters', 'Martin Luther King Jr.'),
    ('title', 'It was a dark and stormy night...'),
    ('title', '...And Then There Were None'), ('title', 'Wait... What')])
def test_format_rules_accept_correct_values(any_indexer, field, value):
    """Values following the format rules are accepted."""
    assert _clean(any_indexer, TEXT_STORY, **{field: value})


@pytest.mark.django_db
def test_format_rules_skip_old_values(any_added_story, any_editing_changeset,
                                      any_indexer):
    """Approved values stay editable, new values are checked."""
    rev = _edit_rev(any_added_story, any_editing_changeset, TEXT_STORY,
                    script='n/a', title='Wait . . . what')
    assert _clean(any_indexer, TEXT_STORY, instance=rev, script='n/a',
                  title='Wait . . . what', notes='corrected elsewhere')
    _rejected(any_indexer, TEXT_STORY, 'Wiki "Credits"', instance=rev,
              script='n/a', pencils='none')


def _clean_credit(instance=None, changed=True, **values):
    """Run clean() of the credit form on these cleaned values."""
    form = StoryCreditRevisionForm({},
                                   instance=instance or StoryCreditRevision())
    form.has_changed = lambda: changed
    form.cleaned_data = {
        'credited_as': '', 'is_credited': False, 'signed_as': '',
        'is_signed': False, 'signature': None, 'credit_name': '',
        'sourced_by': '', 'is_sourced': False}
    form.cleaned_data.update(values)
    form.clean()


@pytest.mark.django_db
def test_sourced_credit_needs_sourced_by():
    """A new or changed sourced credit needs its source, an old one not."""
    with pytest.raises(forms.ValidationError) as error:
        _clean_credit(is_sourced=True)
    assert 'Wiki "Credits", Sourced' in str(error.value)
    _clean_credit(is_sourced=True, sourced_by='Who\'s Who #3')
    _clean_credit(instance=StoryCreditRevision(pk=1), changed=False,
                  is_sourced=True)


LONG_SYNOPSIS = 'Things happen. ' * 41


@pytest.mark.django_db
def test_long_synopsis_refused_also_when_copied(any_added_story,
                                                any_editing_changeset,
                                                any_indexer):
    """A long synopsis already in a new revision (a copy) is refused."""
    copy = StoryRevision(synopsis=LONG_SYNOPSIS)
    with pytest.raises(forms.ValidationError) as error:
        _clean(any_indexer, TEXT_STORY, instance=copy,
               synopsis=LONG_SYNOPSIS.strip())
    assert '600 characters' in str(error.value)
    rev = _edit_rev(any_added_story, any_editing_changeset, TEXT_STORY,
                    synopsis=LONG_SYNOPSIS)
    assert _clean(any_indexer, TEXT_STORY, instance=rev,
                  synopsis=LONG_SYNOPSIS.strip())


@pytest.mark.django_db
def test_new_filler_refused(any_added_story, any_editing_changeset,
                            any_indexer):
    """A new filler is refused, an approved one stays editable."""
    _rejected(any_indexer, 'filler', 'Filler (types no longer used)')
    rev = _edit_rev(any_added_story, any_editing_changeset, 'filler')
    assert _clean(any_indexer, 'filler', instance=rev)


class NoAboutComicsForm(StoryRevisionForm):
    series_has_about_comics = False


class AboutComicsForm(StoryRevisionForm):
    series_has_about_comics = True


@pytest.mark.django_db
def test_new_about_comics_needs_series_flag(any_added_story, any_indexer):
    """About comics needs "has about comics", unless already approved."""
    _rejected(any_indexer, 'about comics', 'Wiki "About Comics"',
              form_class=NoAboutComicsForm)
    assert _clean(any_indexer, 'about comics', form_class=AboutComicsForm)
    # a revision of an approved about comics sequence (cloning one needs its
    # bibliographic entry, which the clean() check does not use)
    Story.objects.filter(pk=any_added_story.pk).update(
        type=StoryType.objects.get(name='about comics'))
    rev = StoryRevision(story=Story.objects.get(pk=any_added_story.pk))
    assert _clean(any_indexer, 'about comics', instance=rev,
                  form_class=NoAboutComicsForm)


COVER, STORY = 6, 19


@pytest.mark.parametrize('types', [
    [], [STORY, STORY], [COVER], [COVER, STORY, STORY],
    [COVER, COVER, STORY], [COVER, STORY, COVER]])
def test_covers_in_wiki_order(types):
    """First cover, then a dust jacket cover or a final flip book cover."""
    assert not _covers_out_of_order(types)


@pytest.mark.parametrize('types', [
    [STORY, COVER], [COVER, STORY, COVER, STORY],
    [COVER, COVER, STORY, COVER]])
def test_covers_out_of_wiki_order(types):
    """Cover not first, second cover in the middle, three covers."""
    assert _covers_out_of_order(types)


def _issue_revision(types, approved_types=None):
    """An issue revision mock with sequence types, and the approved ones."""
    revision = mock.MagicMock()
    stories = revision.active_stories.return_value.order_by.return_value
    stories.values_list.return_value = types
    if approved_types is None:
        revision.issue = None
    else:
        approved = revision.issue.active_stories.return_value\
                           .order_by.return_value
        approved.values_list.return_value = approved_types
    return revision


def test_cover_order_error_cites_wiki():
    """A new issue or a correct approved one gets the cover order error."""
    assert 'Wiki "Type"' in _cover_order_error(
      _issue_revision([STORY, COVER]))
    assert 'Wiki "Type"' in _cover_order_error(
      _issue_revision([STORY, COVER], [COVER, STORY]))
    assert _cover_order_error(_issue_revision([COVER, STORY])) is None


def test_cover_order_of_approved_issue_stays_editable():
    """An approved issue with covers out of order can still be corrected."""
    assert _cover_order_error(
      _issue_revision([STORY, COVER], [STORY, COVER])) is None


def _notes(type_id, synopsis='', reprint_notes='', has_links=False,
           deleted=False):
    """The type notes of a story revision mock."""
    story = mock.MagicMock(type_id=type_id, synopsis=synopsis,
                           reprint_notes=reprint_notes, deleted=deleted)
    story.from_all_reprints.exists.return_value = has_links
    return show_type_notes(story)


def test_synopsis_note_on_types_without_plot():
    """A synopsis on a promo gets a note, on a comic story not."""
    assert 'Synopsis' in _notes(16, synopsis='Buy this!')
    assert _notes(STORY, synopsis='Things happen.') == ''
    assert _notes(16) == ''


def test_cover_reprint_link_note():
    """A cover reprint without reprint link or reprint notes gets a note."""
    assert 'reprint link' in _notes(7)
    assert _notes(7, has_links=True) == ''
    assert _notes(7, reprint_notes='from Batman (DC, 1940 series) #1') == ''


def test_no_type_notes_on_deleted_sequences():
    """Deleted sequences get no notes."""
    assert _notes(16, synopsis='Buy this!', deleted=True) == ''


def _choices(view_class, type_id):
    """The queryset an autocomplete offers in a sequence of the type."""
    view = view_class()
    view.forwarded = {'type': str(type_id)}
    view.q = ''
    return view.get_queryset()


def _feature_logo(name, feature_type_id, language):
    """A feature logo of a new feature with the given feature type."""
    feature_type, _ = FeatureType.objects.get_or_create(
      id=feature_type_id, defaults={'name': name})
    feature = Feature.objects.create(
      name=name, sort_name=name, genre='', language=language,
      feature_type=feature_type, notes='')
    feature_name = FeatureNameDetail.objects.create(
      feature=feature, name=name, sort_name=name, is_official_name=True)
    logo = FeatureLogo.objects.create(name=name, sort_name=name, notes='')
    logo.feature.add(feature)
    logo.feature_name.add(feature_name)
    return logo


@pytest.mark.django_db
def test_no_features_offered_for_types_without_feature():
    """No feature names or logos are offered for a blank page."""
    assert _choices(FeatureNameAutocomplete, 24).query.is_empty()
    assert _choices(FeatureLogoAutocomplete, 24).query.is_empty()
    assert not _choices(FeatureNameAutocomplete, STORY).query.is_empty()


@pytest.mark.django_db
def test_in_house_logos_only_for_in_house_columns(any_language):
    """In-house column logos are offered only for in-house columns."""
    story_logo = _feature_logo('Batman', 1, any_language)
    in_house_logo = _feature_logo('DC Nation', 4, any_language)
    assert list(_choices(FeatureLogoAutocomplete, 29)) == [in_house_logo]
    assert list(_choices(FeatureLogoAutocomplete, STORY)) == [story_logo]


@pytest.mark.django_db
def test_story_arcs_offered_only_for_comic_stories():
    """Story arcs are offered only for comic stories."""
    assert _choices(StoryArcAutocomplete, 21).query.is_empty()
    assert not _choices(StoryArcAutocomplete, STORY).query.is_empty()
