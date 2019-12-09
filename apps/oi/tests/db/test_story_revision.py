# -*- coding: utf-8 -*-


import mock
import pytest

from apps.gcd.models import Publisher, Series, Issue, Story, INDEXED
from apps.oi.models import StoryRevision
from apps.stddata.models import Country, Language
from apps.stats.models import CountStats

UPDATE_ALL = 'apps.stats.models.CountStats.objects.update_all_counts'

# Needed for various set_indexed_status() patch replacements
def _get_indexed_delta(was_indexed, is_indexed, is_comics):
    if is_comics:
        if not was_indexed and is_indexed:
            return 1
        if was_indexed and not is_indexed:
            return -1
    return 0


@pytest.mark.django_db
def test_create_add_revision(any_added_story_rev, story_add_values,
                             any_adding_changeset):
    rev = any_added_story_rev
    for k, v in story_add_values.items():
        assert getattr(rev, k) == v

    assert rev.story is None
    assert rev.previous_revision is None
    assert rev.changeset == any_adding_changeset
    assert rev.date_inferred is False

    assert rev.source is None
    assert rev.source_name == 'story'
    assert rev.source_class is Story


@pytest.mark.parametrize('is_comics', (True, False))
@pytest.mark.parametrize('new_status', [INDEXED[i] for i in INDEXED])
@pytest.mark.django_db
def test_commit_added_revision(any_added_story_rev, story_add_values,
                               any_adding_changeset, keywords,
                               is_comics, new_status):
    rev = any_added_story_rev
    rev.issue.series.is_comics_publication = is_comics
    rev.issue.series.save()

    def set_indexed_status(self):
        delta = _get_indexed_delta(self.is_indexed, new_status, is_comics)
        self.is_indexed = new_status
        self.save()
        return delta

    with mock.patch(UPDATE_ALL) \
            as updater_mock, \
            mock.patch('apps.gcd.models.issue.Issue.set_indexed_status',
                       set_indexed_status):
        rev.commit_to_display()

    expected_calls = [
      mock.call({}, language=None, country=None, negate=True),
      mock.call({'stories': 1}, language=rev.issue.series.language,
                country=rev.issue.series.country)]
    if is_comics and new_status != INDEXED['skeleton']:
        expected_calls.append(mock.call({'issue indexes': 1},
                                        language=rev.issue.series.language,
                                        country=rev.issue.series.country))

    assert is_comics is rev.issue.series.is_comics_publication
    updater_mock.assert_has_calls(expected_calls)
    assert updater_mock.call_count == len(expected_calls)

    assert rev.story is not None
    assert rev.source is rev.story
    assert rev.date_inferred is False

    for k, v in story_add_values.items():
        if k == 'keywords':
            kws = [k for k in rev.story.keywords.names()]
            kws.sort()
            assert kws == keywords['list']
        else:
            assert getattr(rev.story, k) == v


# Changing the story type can change the index status, but this is measured
# in the Issue class, so we just mock it and set the status directly rather
# than dealing with story types.  The code only checks skeleton vs
# not-skeleton, so don't bother with every possible not-skeleton in the
# interest of shorter test runs.
@pytest.mark.parametrize('is_comics', (True, False))
@pytest.mark.parametrize('old_status', (INDEXED['skeleton'], INDEXED['full']))
@pytest.mark.parametrize('new_status', (INDEXED['skeleton'], INDEXED['full']))
@pytest.mark.django_db
def test_create_edit_revision(any_edit_story_rev, story_add_values,
                              any_editing_changeset, keywords, is_comics,
                              old_status, new_status):
    rev = any_edit_story_rev
    rev.issue.is_indexed = old_status
    rev.issue.series.is_comics_publication = is_comics
    rev.issue.series.save()

    # Change a few fields, but don't try to be comprehensive as the
    # field copying code is tested elsewhere.  This is just to catch
    # some sort of egregious regression.
    story_edit_values = story_add_values.copy()
    story_edit_values['no_colors'] = False
    story_edit_values['colors'] = 'Diverse Hands'
    story_edit_values['page_count'] = rev.page_count + 1
    rev.no_colors = story_edit_values['no_colors']
    rev.colors = story_edit_values['colors']
    rev.page_count = story_edit_values['page_count']
    rev.save()

    def set_indexed_status(self):
        delta = _get_indexed_delta(self.is_indexed, new_status, is_comics)
        self.is_indexed = new_status
        self.save()
        return delta

    with mock.patch(UPDATE_ALL) as updater_mock, \
            mock.patch('apps.gcd.models.issue.Issue.set_indexed_status',
                       set_indexed_status):
        rev.commit_to_display()

    if old_status == new_status or not is_comics:
        assert not updater_mock.called
    elif is_comics:
        delta = 1 if old_status == INDEXED['skeleton'] else -1
        updater_mock.assert_called_once_with(
            {'issue indexes': delta},
            country=rev.issue.series.country,
            language=rev.issue.series.language)

    for k, v in story_edit_values.items():
        if k == 'keywords':
            kws = [k for k in rev.story.keywords.names()]
            kws.sort()
            assert kws == keywords['list']
        else:
            assert getattr(rev.story, k) == v


# Since index status is always just compared against 'skeleton', we only
# test skeleton and full here.  The entire matrix of possible pre and post
# statuses for the old and new issues would actually add noticeable run time
# to the test suite, without adding much value.
#
# Some of the transitions would involve editing the story type as the story
# is moved so that it goes from counting towards being indexed to not counting,
# or the other way around.  Since the code examining this is in the Issue
# class, we do not try to simulate this by actually changing story types, and
# instead just handle this by setting the index status directly.  This makes
# the test for the Story-level functionality more clear.
@pytest.mark.parametrize('old_is_comics', (True, False))
@pytest.mark.parametrize('new_is_comics', (True, False))
@pytest.mark.parametrize('old_pre_status, old_post_status',
                         [(INDEXED['skeleton'], INDEXED['skeleton']),
                          (INDEXED['full'], INDEXED['skeleton']),
                          (INDEXED['full'], INDEXED['full'])])
@pytest.mark.parametrize('new_pre_status, new_post_status',
                         [(INDEXED['skeleton'], INDEXED['skeleton']),
                          (INDEXED['skeleton'], INDEXED['full']),
                          (INDEXED['full'], INDEXED['full'])])
@pytest.mark.django_db
def test_create_move_revision(any_edit_story_rev, story_add_values,
                              any_editing_changeset, keywords,
                              old_is_comics, new_is_comics,
                              old_pre_status, old_post_status,
                              new_pre_status, new_post_status):

    rev = any_edit_story_rev
    rev.issue.is_indexed = old_pre_status
    rev.issue.series.is_comics_publication = old_is_comics
    rev.issue.series.save()

    # Changing country and language ensures that the stats are updated
    # (we are not interested in the path where they are not, as it is a
    # decision made in common code post-refactor).
    old_country = rev.issue.series.country
    old_language = rev.issue.series.language

    new_country = Country.objects.get_or_create(code='XZX',
                                                name='Other Country')[0]
    new_language = Language.objects.get_or_create(code='XZX',
                                                  name='Other Language')[0]
    # Ensure we already have stats for new country and language or else
    # we get different calls in the tests due to init logic.
    CountStats.objects.init_stats(country=new_country)
    CountStats.objects.init_stats(language=new_language)

    new_publisher = Publisher.objects.create(name='Other Test Publisher',
                                             country=new_country,
                                             year_began=1990,
                                             series_count=1,
                                             issue_count=1)
    new_series = Series.objects.create(name='New Test Series',
                                       publisher=new_publisher,
                                       country=new_country,
                                       language=new_language,
                                       year_began=2000,
                                       is_comics_publication=new_is_comics,
                                       issue_count=1)
    new_issue = Issue(number='[nn]',
                      series=new_series,
                      publication_date='January 2000',
                      key_date='2000-01-00',
                      sort_code=0,
                      is_indexed=new_pre_status)
    new_issue.save()
    rev.issue = new_issue
    rev.save()

    def set_indexed_status(self):
        if self.series.name == 'New Test Series':
            # Destination series always ends up indexed.
            delta = _get_indexed_delta(self.is_indexed, new_post_status,
                                       new_is_comics)
            self.is_indexed = new_post_status
        else:
            delta = _get_indexed_delta(self.is_indexed, old_post_status,
                                       old_is_comics)
            self.is_indexed = old_post_status
        self.save()
        return delta

    with mock.patch(UPDATE_ALL) as updater_mock, \
      mock.patch('apps.gcd.models.issue.Issue.set_indexed_status',
                  set_indexed_status):
        rev.commit_to_display()

    # TODO: Verify that reprint links still have story/issue fields agreeing.

    expected_calls = [mock.call({'stories': 1},
                                language=new_language,
                                country=new_country),
                      mock.call({'stories': 1},
                                language=old_language,
                                country=old_country,
                                negate=True)]
    if old_is_comics and (old_pre_status != INDEXED['skeleton'] and
                          old_post_status == INDEXED['skeleton']):
        expected_calls.append(mock.call({'issue indexes': -1},
                                        language=old_language,
                                        country=old_country))
    if new_is_comics and (new_pre_status == INDEXED['skeleton'] and
                          new_post_status != INDEXED['skeleton']):
        expected_calls.append(mock.call({'issue indexes': 1},
                                        language=new_language,
                                        country=new_country))
    elif new_is_comics and (new_pre_status != INDEXED['skeleton'] and
                            new_post_status == INDEXED['skeleton']):
        expected_calls.append(mock.call({'issue indexes': 1},
                                        language=new_language,
                                        country=new_country))

    updater_mock.assert_has_calls(expected_calls, any_order=True)
    assert updater_mock.call_count == len(expected_calls)


@pytest.mark.parametrize('is_comics', (True, False))
@pytest.mark.parametrize('old_status, new_status',
                         [(INDEXED['skeleton'], INDEXED['skeleton']),
                          (INDEXED['full'], INDEXED['skeleton']),
                          (INDEXED['full'], INDEXED['full'])])
@pytest.mark.django_db
def test_delete_story(any_edit_story_rev, any_added_story, is_comics, old_status, new_status, any_country, any_language, ):
    #rev = StoryRevision.clone(data_object=any_added_story,
                              #changeset=any_deleting_changeset)
    rev = any_edit_story_rev
    rev.issue.series.is_comics_publication = is_comics
    rev.issue.series.save()
    rev.issue.is_indexed = old_status
    rev.story.issue.is_indexed = old_status
    rev.issue.save()
    rev.story.issue.save()
    rev.deleted = True
    rev.save()

    def set_indexed_status(self):
        delta = _get_indexed_delta(self.is_indexed, new_status, is_comics)
        self.is_indexed = new_status
        self.save()
        return delta

    CountStats.objects.init_stats(country=any_country)
    CountStats.objects.init_stats(language=any_language)

    with mock.patch(UPDATE_ALL) as updater_mock, \
            mock.patch('apps.gcd.models.issue.Issue.set_indexed_status',
                       set_indexed_status), \
            mock.patch('apps.oi.models.StoryRevision._reset_values'):

        rev.commit_to_display()

        # We don't need to actually see how _reset_values works as it
        # will be tested separately post-refactor.  Just make sure that
        # it gets called.
        rev._reset_values.assert_called_once_with()
    
    assert rev.deleted is True
    assert rev.story == any_added_story
    assert rev.story.deleted is True
    assert rev.issue.deleted is False

    expected_calls = [
      mock.call({'stories': 1}, country=rev.issue.series.country,
                language=rev.issue.series.language, negate=True),
      mock.call({}, country=None,
                language=None)]
    if is_comics and old_status != new_status:
        expected_calls.insert(0,
                              mock.call({'issue indexes': -1},
                                        country=rev.issue.series.country,
                                        language=rev.issue.series.language))
    updater_mock.assert_has_calls(expected_calls, any_order=True)
    assert updater_mock.call_count == len(expected_calls)
