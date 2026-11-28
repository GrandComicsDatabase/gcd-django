# -*- coding: utf-8 -*-
"""
Tests of the page marking the characters of a cover sequence on a cover.
"""
import re
from datetime import timedelta
from html.parser import HTMLParser

import mock
import pytest

from django.contrib.auth.models import Permission, User
from django.core.exceptions import ValidationError
from django.test import RequestFactory
from django.urls import reverse
from django.utils import timezone

from apps.gcd.models import (
    Character, CharacterNameDetail, Cover, CoverCharacterBox, Issue,
    Publisher, Series, Story, StoryCharacter, StoryType, STORY_TYPES)
from apps.indexer.models import Error, Indexer
from apps.oi import states
from apps.oi.forms import get_story_revision_form
from apps.oi.forms.cover_character_box import CoverCharacterBoxForm
from apps.oi.models import (
    Changeset, CoverCharacterBoxRevision, CoverRevision, IssueRevision,
    StoryCharacterRevision, StoryRevision, CTYPES)
from apps.oi.views import process_revision, _save
from apps.gcd.tests.page_ids import assert_valid_ids


pytestmark = pytest.mark.django_db

# An upright rectangle 3000 wide and 4500 high in affine coordinates of the
# front, drawn on a scan of 400 x 615 pixels.
UPRIGHT = {
    'top_left_x': 1000, 'top_left_y': 2000,
    'top_right_x': 4000, 'top_right_y': 2000,
    'bottom_left_x': 1000, 'bottom_left_y': 6500,
    'scan_aspect': 15375,
}

# A rectangle turned a quarter counterclockwise, on a scan of 400 x 600.
TURNED = {
    'top_left_x': 5000, 'top_left_y': 9000,
    'top_right_x': 5000, 'top_right_y': 4000,
    'bottom_left_x': 8000, 'bottom_left_y': 9000,
    'scan_aspect': 15000,
}


class _FormParser(HTMLParser):
    """
    Collects what a browser submits from the box form of the page:
    the values of the inputs other than buttons, checked boxes only.
    """
    def __init__(self):
        """
        Starts outside of any form.
        """
        super().__init__()
        self.data = {}
        self.rows = 0
        self._in_form = False

    def handle_starttag(self, tag, attrs):
        """
        Keeps the inputs of the form and counts the box rows.
        """
        attrs = dict(attrs)
        if tag == 'form':
            self._in_form = True
        elif tag == 'tr' and 'data-box-row' in attrs:
            self.rows += 1
        elif tag == 'input' and self._in_form and attrs.get('name'):
            kind = attrs.get('type', 'text')
            if kind in ('submit', 'reset'):
                return
            if kind in ('checkbox', 'radio') and 'checked' not in attrs:
                return
            self.data[attrs['name']] = attrs.get('value', 'on' if kind in (
              'checkbox', 'radio') else '')

    def handle_endtag(self, tag):
        """
        Stops at the end of the form.
        """
        if tag == 'form':
            self._in_form = False


def _parse(response):
    """
    The form data and the number of box rows of a rendered page.
    """
    parser = _FormParser()
    parser.feed(response.content.decode())
    return parser


def _add_appearance(name, story, language, approved_story_revision):
    """
    An approved appearance of a new character in the story.
    """
    character = Character.objects.create(
        name=name, sort_name=name, disambiguation='', language=language,
        description='', notes='')
    name_detail = CharacterNameDetail.objects.create(
        name=name, sort_name=name, character=character,
        is_official_name=True)
    appearance = StoryCharacter.objects.create(
        character=name_detail, story=story, notes='')
    StoryCharacterRevision.objects.create(
        changeset=approved_story_revision.changeset, committed=True,
        story_character=appearance, character=name_detail,
        story_revision=approved_story_revision, notes='')
    return appearance


@pytest.fixture
def world(any_indexer, any_country, any_language):
    """
    An approved cover sequence with the characters Alpha and Beta, a cover
    scan of the issue with a box of Alpha drawn on an older scan, and an
    open changeset of the indexer editing the sequence, with the box
    cloned.
    """
    any_indexer.user_permissions.add(Permission.objects.get(
        codename='can_reserve', content_type__app_label='indexer'))
    publisher = Publisher.objects.create(
        name='Test Publisher', country=any_country, year_began=1965)
    series = Series.objects.create(
        name='Test Series', sort_name='Test Series', year_began=1965,
        country=any_country, language=any_language, publisher=publisher,
        is_comics_publication=True, has_gallery=True,
        publication_dates='1965')
    issue = Issue.objects.create(
        number='1', series=series, sort_code=0, publication_date='1965',
        key_date='1965-01-00')
    cover_type = StoryType.objects.get_or_create(
        id=STORY_TYPES['cover'],
        defaults={'name': 'cover', 'sort_code': 99011})[0]
    story = Story.objects.create(issue=issue, type=cover_type,
                                 sequence_number=0)
    approved = Changeset.objects.create(
        state=states.APPROVED, indexer=any_indexer,
        change_type=CTYPES['issue'])
    approved_story_revision = StoryRevision.objects.create(
        changeset=approved, committed=True, story=story, issue=issue,
        type=cover_type, sequence_number=0)
    alpha = _add_appearance('Alpha', story, any_language,
                            approved_story_revision)
    beta = _add_appearance('Beta', story, any_language,
                           approved_story_revision)
    last_upload = timezone.now()
    cover = Cover.objects.create(issue=issue, last_upload=last_upload)
    box = CoverCharacterBox.objects.create(
        story_character=alpha, cover=cover,
        scan_date=last_upload - timedelta(days=30), **UPRIGHT)
    CoverCharacterBoxRevision.objects.create(
        changeset=approved, committed=True, cover_character_box=box,
        story_character_revision=alpha.revisions.get(), cover=cover,
        scan_date=box.scan_date, **UPRIGHT)

    changeset = Changeset.objects.create(
        state=states.OPEN, indexer=any_indexer, change_type=CTYPES['issue'])
    story_revision = StoryRevision.objects.create(
        changeset=changeset, story=story, issue=issue, type=cover_type,
        sequence_number=0)
    alpha_revision = StoryCharacterRevision.objects.create(
        changeset=changeset, story_character=alpha,
        character=alpha.character, story_revision=story_revision, notes='')
    beta_revision = StoryCharacterRevision.objects.create(
        changeset=changeset, story_character=beta,
        character=beta.character, story_revision=story_revision, notes='')
    box_revision = CoverCharacterBoxRevision.clone(
        box, changeset=changeset,
        story_character_revision=alpha_revision)
    return {
        'user': any_indexer,
        'issue': issue,
        'cover': cover,
        'changeset': changeset,
        'story_revision': story_revision,
        'alpha_revision': alpha_revision,
        'beta_revision': beta_revision,
        'box_revision': box_revision,
        'url': reverse('mark_cover_characters',
                       kwargs={'story_revision_id': story_revision.id}),
    }


def _variant_cover(issue, status):
    """
    The cover of a new variant of the issue with the variant cover status.
    """
    variant = Issue.objects.create(
        number='1', series=issue.series, sort_code=status,
        publication_date='1965', key_date='1965-01-00', variant_of=issue,
        variant_name='Variant %d' % status, variant_cover_status=status)
    return Cover.objects.create(issue=variant, last_upload=timezone.now())


def _page_data(client, world, query=''):
    """
    What the browser submits from the page as loaded, before any drawing.
    """
    response = client.get(world['url'] + query)
    assert response.status_code == 200
    return _parse(response).data


def _is_error(response):
    """
    Whether the response sends to the error page.
    """
    return response.status_code == 302 and \
        response.url.startswith(reverse('error'))


def _boxes(world):
    """
    The box revisions of the changeset by appearance revision id.
    """
    return {box.story_character_revision_id: box
            for box in CoverCharacterBoxRevision.objects.filter(
              changeset=world['changeset'])}


def test_page_lists_appearances_with_their_boxes(client, world):
    """
    One row per appearance with its box, and the scan.  The box was drawn
    on an older scan, so it shows no cut-out.
    """
    client.force_login(world['user'])

    response = client.get(world['url'])

    assert response.status_code == 200
    content = response.content.decode()
    parsed = _parse(response)
    assert parsed.rows == 2
    assert 'img/placeholder_large.jpg' in content
    assert 'Drawn on an older scan: draw it again' in content
    assert '<span data-box-status aria-live="polite">not marked</span>' \
        in content
    assert 'data-box-cut-out' not in content
    assert '<th class="text-left">Remove</th>' in content
    assert 'Mark a character only where it is clearly seen' in content
    assert 'data-box-clear' in content
    assert 'sticky-action-bar' in content
    assert 'js/oi/cover_character_box.js' in content
    data = parsed.data
    assert data['box-0-appearance'] == str(world['alpha_revision'].id)
    assert data['box-0-top_right_x'] == '4000'
    assert data['box-0-scan_aspect'] == '15375'
    assert data['box-1-appearance'] == str(world['beta_revision'].id)
    assert data['box-1-top_left_x'] == ''
    assert data['box-0-scan_date'] == \
        world['cover'].last_upload.isoformat()
    # The first character without a box is chosen for marking.
    assert data['mark'] == '2'
    # A single cover needs no choice.
    assert '?cover=' not in content
    assert 'can be marked on each of these covers' not in content


def test_page_uses_w400_scan_and_w200_for_wraparound(client, world,
                                                     settings):
    """The scan is the w400 one, the w200 one for a wraparound cover."""
    settings.FAKE_IMAGES = False
    client.force_login(world['user'])
    cover = world['cover']

    content = client.get(world['url']).content.decode()
    assert '/w400/%d.jpg' % cover.id in content

    cover.is_wraparound = True
    cover.save()
    content = client.get(world['url']).content.decode()
    assert '/w200/%d.jpg' % cover.id in content


def test_page_ignores_a_row_number_too_long_for_an_integer(client, world):
    """A row number of thousands of digits chooses the first free row."""
    client.force_login(world['user'])

    response = client.get(world['url'], {'mark': '1' * 5000})

    assert response.status_code == 200
    assert response.context['selected'] == 2


def test_page_only_for_reservation_holder(client, world, any_country):
    """Another indexer can neither see nor save the boxes."""
    other = User.objects.create_user('other_indexer', password='other')
    Indexer.objects.create(user=other, country=any_country)
    other.user_permissions.add(Permission.objects.get(
        codename='can_reserve', content_type__app_label='indexer'))
    client.force_login(world['user'])
    data = _page_data(client, world)
    client.force_login(other)

    assert _is_error(client.get(world['url']))
    data['box-1-top_left_x'] = '6000'
    response = client.post(world['url'], data)

    assert _is_error(response)
    assert Error.objects.filter(
        error_text__contains='Only the reservation holder').exists()
    assert len(_boxes(world)) == 1


def test_page_needs_permission_to_reserve(client, world):
    """A user who may not index is sent to the login page."""
    world['user'].user_permissions.clear()
    client.force_login(world['user'])

    response = client.get(world['url'])

    assert response.status_code == 302
    assert 'login' in response.url


def test_page_needs_login(client, world):
    """A visitor who is not logged in is sent to the login page."""
    client.force_login(world['user'])
    data = _page_data(client, world)
    data.update({'box-1-%s' % name: value
                 for name, value in UPRIGHT.items()})
    client.logout()

    for response in (client.get(world['url']),
                     client.post(world['url'], data)):
        assert response.status_code == 302
        assert 'login' in response.url
    assert len(_boxes(world)) == 1


@pytest.mark.parametrize('state', [states.PENDING, states.REVIEWING,
                                   states.APPROVED, states.DISCARDED])
def test_page_needs_open_changeset(client, world, state):
    """
    Boxes are only edited while the change is being edited, not in the
    queue, after approval or after the change was discarded.
    """
    client.force_login(world['user'])
    data = _page_data(client, world)
    data.update({'box-1-%s' % name: value
                 for name, value in UPRIGHT.items()})
    changeset = world['changeset']
    changeset.state = state
    changeset.save()

    assert _is_error(client.get(world['url']))
    assert _is_error(client.post(world['url'], data))
    assert len(_boxes(world)) == 1


def test_page_refuses_a_deleted_sequence(client, world):
    """A cover sequence deleted in the change has no boxes to mark."""
    story_revision = world['story_revision']
    story_revision.deleted = True
    story_revision.save()
    client.force_login(world['user'])

    assert _is_error(client.get(world['url']))


def test_page_needs_an_existing_issue(client, world):
    """
    The sequence of an issue still being added, a variant with its own
    cover sequence, has no cover scan yet: no button, and the page refuses
    it.
    """
    # The added variant has a revision without an issue, as its sequences.
    changeset = world['changeset']
    changeset.change_type = CTYPES['issue_add']
    changeset.save()
    IssueRevision.objects.create(
        changeset=changeset, series=world['issue'].series, number='1',
        variant_of=world['issue'])
    story_revision = world['story_revision']
    story_revision.issue = None
    story_revision.save()
    client.force_login(world['user'])

    assert not _has_mark_button(story_revision, world['user'])
    assert _is_error(client.get(world['url']))
    assert Error.objects.filter(
        error_text__contains='of an existing issue').exists()


@pytest.mark.parametrize('scan', ['deleted', 'none'])
def test_page_without_a_cover_scan(client, world, scan):
    """
    An issue whose only cover scan was deleted, or with no scan inserted
    at all, has nothing to mark the characters on: no button, and the page
    says so.  A scan waiting in the queue is not a cover yet either.
    """
    cover = world['cover']
    if scan == 'deleted':
        cover.deleted = True
        cover.save()
    else:
        cover.delete()
    CoverRevision.objects.create(changeset=Changeset.objects.create(
        state=states.PENDING, indexer=world['user'],
        change_type=CTYPES['cover']), issue=world['issue'])
    client.force_login(world['user'])

    assert not _has_mark_button(world['story_revision'], world['user'])
    assert _is_error(client.get(world['url']))
    assert Error.objects.filter(
        error_text__contains='There is no cover scan of this issue').exists()


def test_page_only_for_cover_sequence(client, world):
    """A sequence of another type has no boxes."""
    story_revision = world['story_revision']
    story_revision.type = StoryType.objects.get_or_create(
        id=STORY_TYPES['comic story'],
        defaults={'name': 'comic story', 'sort_code': 19})[0]
    story_revision.save()
    client.force_login(world['user'])

    assert _is_error(client.get(world['url']))


def _layout_html(layout):
    """
    The HTML pieces of a crispy layout, also those inside tabs.
    """
    html = []
    for item in getattr(layout, 'fields', []):
        if hasattr(item, 'html'):
            html.append(item.html)
        html.extend(_layout_html(item))
    return html


def _has_mark_button(story_revision, user):
    """
    Whether the sequence form shows the button to mark the characters.
    """
    form_class = get_story_revision_form(story_revision, user=user)
    form = form_class(instance=story_revision)
    return any('name="mark_cover_characters"' in html
               for html in _layout_html(form.helper.layout))


@pytest.mark.parametrize('use_tabs', [False, True])
def test_button_only_for_cover_sequence_with_characters(world, use_tabs):
    """
    The sequence form has the button for a cover sequence with characters,
    not for one without or for another type of sequence.
    """
    user = world['user']
    user.indexer.use_tabs = use_tabs
    user.indexer.save()
    story_revision = world['story_revision']

    assert _has_mark_button(story_revision, user)

    for revision in story_revision.story_character_revisions.all():
        revision.deleted = True
        revision.save()
    assert not _has_mark_button(story_revision, user)

    story_revision.story_character_revisions.update(deleted=False)
    story_revision.type = StoryType.objects.get_or_create(
        id=STORY_TYPES['comic story'],
        defaults={'name': 'comic story', 'sort_code': 19})[0]
    story_revision.save()
    assert not _has_mark_button(story_revision, user)


def test_button_only_with_a_cover_to_mark_on(world):
    """
    The sequence form has no button when the issue has no cover scan to
    mark the characters on.
    """
    user = world['user']
    story_revision = world['story_revision']
    cover = world['cover']
    cover.deleted = True
    cover.save()
    assert not _has_mark_button(story_revision, user)

    cover.deleted = False
    cover.save()
    assert _has_mark_button(story_revision, user)


def test_button_saves_sequence_and_opens_page(world):
    """The button saves the sequence form as the other save buttons."""
    request = RequestFactory().post('/', {'mark_cover_characters': 'Mark'})
    request.user = world['user']
    story_revision = world['story_revision']

    with mock.patch('apps.oi.views._save', return_value='saved') as save:
        response = process_revision.__wrapped__(
            request, story_revision.id, 'story')

    assert response == 'saved'
    assert save.call_args.kwargs['model_name'] == 'story'


def test_saving_with_the_button_goes_to_the_page(world):
    """After saving the sequence, the button leads to the marking page."""
    request = RequestFactory().post('/', {'mark_cover_characters': 'Mark'})
    request.user = world['user']
    story_revision = world['story_revision']
    form = mock.Mock(cleaned_data={})
    form.is_valid.return_value = True
    form.save.return_value = story_revision

    with mock.patch.object(StoryRevision, 'extra_forms', return_value={}), \
            mock.patch.object(StoryRevision, 'process_extra_forms'):
        response = _save(request, form, story_revision, model_name='story')

    assert response.status_code == 302
    assert response.url == world['url']


def test_covers_follow_the_rule_of_box_covers(client, world):
    """
    A variant with only a scan difference can be chosen and marked, a
    variant with other art cannot.
    """
    scan_variant = _variant_cover(world['issue'], 2)
    art_variant = _variant_cover(world['issue'], 3)
    client.force_login(world['user'])

    # The cover of the issue itself comes first.
    assert _page_data(client, world)['cover'] == str(world['cover'].id)
    content = client.get(world['url']).content.decode()
    assert '?cover=%d"' % scan_variant.id in content
    assert '?cover=%d"' % art_variant.id not in content
    assert _is_error(client.get(world['url'] + '?cover=%d' % art_variant.id))

    data = _page_data(client, world, '?cover=%d' % scan_variant.id)
    assert data['cover'] == str(scan_variant.id)
    # No box of Alpha on this cover yet.
    assert data['box-0-top_left_x'] == ''
    data.update({'box-0-%s' % name: value
                 for name, value in UPRIGHT.items()})
    response = client.post(world['url'], data)
    assert response.status_code == 302
    assert CoverCharacterBoxRevision.objects.filter(
        changeset=world['changeset'], cover=scan_variant).count() == 1

    data['cover'] = str(art_variant.id)
    data['box-0-scan_date'] = art_variant.last_upload.isoformat()
    response = client.post(world['url'], data)
    assert _is_error(response)
    assert not CoverCharacterBoxRevision.objects.filter(
        cover=art_variant).exists()


@pytest.mark.parametrize('corners, message', [
    # The centre at x 12500, beyond the right edge.
    ({'top_left_x': 11000, 'top_right_x': 14000, 'bottom_left_x': 11000},
     'The centre of the box is not on the cover'),
    # The centre at y 13250, below the bottom edge.
    ({'top_left_y': 11000, 'top_right_y': 11000, 'bottom_left_y': 15500},
     'The centre of the box is not on the cover'),
    # The top side has length 0.
    ({'top_right_x': 1000},
     'A side of the box is shorter than 1'),
    # The left side has length 0.
    ({'bottom_left_y': 2000},
     'A side of the box is shorter than 1'),
    # One y unit is 0.6 x units on a wide scan.
    ({'bottom_left_y': 2001, 'scan_aspect': 6000},
     'A side of the box is shorter than 1'),
    # Beyond a SmallIntegerField.
    ({'top_left_x': 40000},
     'A corner of the box is too far from the cover'),
    ({'top_left_y': -32769},
     'A corner of the box is too far from the cover'),
    # Not a number.
    ({'top_left_y': '1.5'}, 'The box is not valid'),
    ({'scan_aspect': '0'}, 'The proportions of the scan are not valid'),
    # The top and the left side swapped give a mirrored box.
    ({'top_right_x': 1000, 'top_right_y': 6500,
      'bottom_left_x': 4000, 'bottom_left_y': 2000},
     'The corners of the box are not in order'),
    # A corner missing.
    ({'bottom_left_y': ''}, 'The box is incomplete'),
])
def test_corner_checks(client, world, corners, message):
    """A wrong box is not saved and the page tells why."""
    client.force_login(world['user'])
    data = _page_data(client, world)
    data.update({'box-1-%s' % name: value
                 for name, value in UPRIGHT.items()})
    data.update({'box-1-%s' % name: value
                 for name, value in corners.items()})

    response = client.post(world['url'], data)

    assert response.status_code == 200
    content = response.content.decode()
    assert message in content
    # One message for one fault.
    if message != 'The box is incomplete':
        assert 'The box is incomplete' not in content
    assert world['beta_revision'].id not in _boxes(world)


def test_box_on_the_current_scan_shows_its_cut_out(client, world):
    """
    A box drawn on the scan the cover has now shows the cut-out as drawn,
    under the name of its character; a character not marked shows none.
    """
    box_revision = world['box_revision']
    box_revision.scan_date = world['cover'].last_upload
    box_revision.save()
    client.force_login(world['user'])

    content = client.get(world['url']).content.decode()

    assert content.count('data-box-cut-out') == 1
    assert 'viewBox="0 0 3000 6918.75"' in content


def test_corners_may_leave_the_cover(client, world):
    """A character near the edge has corners outside the front."""
    client.force_login(world['user'])
    data = _page_data(client, world)
    data.update({'box-1-%s' % name: value
                 for name, value in UPRIGHT.items()})
    data.update({'box-1-top_left_x': -2000, 'box-1-bottom_left_x': -2000,
                 'box-1-top_right_x': 3000})

    response = client.post(world['url'], data)

    assert response.status_code == 302
    box = _boxes(world)[world['beta_revision'].id]
    assert (box.top_left_x, box.top_right_x) == (-2000, 3000)


def test_only_changed_boxes_are_written(client, world):
    """
    A box saved again unchanged keeps its revision untouched, an added
    one is created with the last upload of the scan.
    """
    box_revision = world['box_revision']
    cover = world['cover']
    # Alpha confirmed on the current scan.
    box_revision.scan_date = cover.last_upload
    box_revision.save()
    modified = CoverCharacterBoxRevision.objects.get(
        id=box_revision.id).modified
    client.force_login(world['user'])
    data = _page_data(client, world)

    response = client.post(world['url'], data)
    assert response.status_code == 302
    assert len(_boxes(world)) == 1
    assert CoverCharacterBoxRevision.objects.get(
        id=box_revision.id).modified == modified

    data.update({'box-1-%s' % name: value
                 for name, value in TURNED.items()})
    response = client.post(world['url'], data)

    assert response.status_code == 302
    boxes = _boxes(world)
    assert CoverCharacterBoxRevision.objects.get(
        id=box_revision.id).modified == modified
    added = boxes[world['beta_revision'].id]
    assert added.cover_character_box is None
    assert added.cover == cover
    assert added.scan_date == cover.last_upload
    for name, value in TURNED.items():
        assert getattr(added, name) == value


def test_scan_date_comes_from_last_upload(client, world):
    """
    A box drawn on an older scan gets the last upload when it is saved.
    """
    client.force_login(world['user'])
    data = _page_data(client, world)
    data['box-0-top_right_x'] = '4500'

    response = client.post(world['url'], data)

    assert response.status_code == 302
    box = CoverCharacterBoxRevision.objects.get(
        id=world['box_revision'].id)
    assert box.top_right_x == 4500
    assert box.scan_date == world['cover'].last_upload
    content = client.get(world['url']).content.decode()
    assert 'Drawn on an older scan' not in content


def test_box_left_as_it_was_stays_on_its_older_scan(client, world):
    """
    Saving the page for another character leaves a box on an older scan
    waiting: its proportions are of that scan.
    """
    client.force_login(world['user'])
    older = world['box_revision'].scan_date
    data = _page_data(client, world)
    data.update({'box-1-%s' % name: value
                 for name, value in UPRIGHT.items()})

    response = client.post(world['url'], data)

    assert response.status_code == 302
    box = CoverCharacterBoxRevision.objects.get(
        id=world['box_revision'].id)
    assert box.scan_date == older
    content = client.get(world['url']).content.decode()
    assert 'Drawn on an older scan' in content


def _statuses(content):
    """The status of each row of the page, in order."""
    return re.findall(r'<span data-box-status aria-live="polite">([^<]*)<',
                      content)


def test_rows_sent_back_with_errors_show_what_is_not_saved(client, world):
    """
    A page sent back with an error shows a changed box, or a box with
    Remove ticked, as not saved and without the cut-out of the saved box.
    """
    box_revision = world['box_revision']
    box_revision.scan_date = world['cover'].last_upload
    box_revision.save()
    client.force_login(world['user'])
    data = _page_data(client, world)
    # Beta has an incomplete box: an error.
    data['box-1-top_left_x'] = '1000'

    unchanged = client.post(world['url'], data).content.decode()
    data['box-0-top_right_x'] = '4500'
    redrawn = client.post(world['url'], data).content.decode()
    data['box-0-top_right_x'] = '4000'
    data['box-0-DELETE'] = 'on'
    removed = client.post(world['url'], data).content.decode()

    assert _statuses(unchanged) == ['marked', 'drawn, not saved']
    assert 'data-box-cut-out' in unchanged
    assert _statuses(redrawn) == ['drawn, not saved', 'drawn, not saved']
    assert 'data-box-cut-out' not in redrawn
    assert _statuses(removed) == ['removed, not saved', 'drawn, not saved']
    assert 'data-box-cut-out' not in removed
    assert CoverCharacterBoxRevision.objects.get(
        id=box_revision.id).top_right_x == 4000


def test_box_with_collinear_corners_is_refused(client, world):
    """
    The corners are on one line, though rounding the sides to the scan
    would hide it: the cut-out could not be shown.
    """
    client.force_login(world['user'])
    data = _page_data(client, world)
    data.update({'box-1-top_left_x': '1376', 'box-1-top_left_y': '4467',
                 'box-1-top_right_x': '2108', 'box-1-top_right_y': '5475',
                 'box-1-bottom_left_x': '2657', 'box-1-bottom_left_y': '6231',
                 'box-1-scan_aspect': '17313'})

    response = client.post(world['url'], data)

    assert response.status_code == 200
    assert 'The corners of the box are not in order' \
        in response.content.decode()
    assert world['beta_revision'].id not in _boxes(world)


def test_parameters_that_look_like_digits_do_not_fail(client, world):
    """A superscript counts as a digit for isdigit, but int refuses it."""
    client.force_login(world['user'])

    assert _is_error(client.get(world['url'] + '?cover=%C2%B2'))
    assert client.get(world['url'] + '?mark=%C2%B2').status_code == 200


def test_scan_replaced_while_marking(client, world):
    """A box drawn on a scan replaced meanwhile is not saved."""
    client.force_login(world['user'])
    data = _page_data(client, world)
    cover = world['cover']
    cover.last_upload = cover.last_upload + timedelta(minutes=5)
    cover.save()
    data.update({'box-1-%s' % name: value
                 for name, value in UPRIGHT.items()})

    response = client.post(world['url'], data)

    assert response.status_code == 200
    content = response.content.decode()
    assert 'The cover scan was replaced' in content
    assert world['beta_revision'].id not in _boxes(world)
    # The page now carries the new scan, so it can be saved after a check.
    assert _parse(response).data['box-1-scan_date'] == \
        cover.last_upload.isoformat()


def test_remove_cloned_box_marks_it_deleted(client, world):
    """A removed box of the display is deleted when approved."""
    client.force_login(world['user'])
    data = _page_data(client, world)
    data['box-0-DELETE'] = 'on'
    # The fields of a removed box are not checked.
    data['box-0-top_right_x'] = '1000'

    response = client.post(world['url'], data)

    assert response.status_code == 302
    box = CoverCharacterBoxRevision.objects.get(
        id=world['box_revision'].id)
    assert box.deleted is True
    assert box.top_right_x == 4000
    content = client.get(world['url']).content.decode()
    assert 'removed in this change' in content
    # Unchecking "Remove" brings it back.
    data = _page_data(client, world)
    assert data['box-0-DELETE'] == 'on'
    del data['box-0-DELETE']
    client.post(world['url'], data)
    box.refresh_from_db()
    assert box.deleted is False


def test_removing_a_removed_box_again_writes_nothing(client, world):
    """A box already removed in this change is left as it is."""
    box_revision = world['box_revision']
    box_revision.deleted = True
    box_revision.save()
    modified = CoverCharacterBoxRevision.objects.get(
        id=box_revision.id).modified
    client.force_login(world['user'])
    data = _page_data(client, world)
    assert data['box-0-DELETE'] == 'on'

    response = client.post(world['url'], data)

    assert response.status_code == 302
    assert CoverCharacterBoxRevision.objects.get(
        id=box_revision.id).modified == modified


def test_removed_box_counts_as_not_marked_for_the_choice(client, world):
    """
    The first character without a box is chosen for marking, and a box
    removed in this change is none.
    """
    box_revision = world['box_revision']
    box_revision.deleted = True
    box_revision.save()
    client.force_login(world['user'])

    assert _page_data(client, world)['mark'] == '1'


def test_remove_added_box_deletes_it(client, world):
    """A removed box added in this changeset is gone."""
    added = CoverCharacterBoxRevision.objects.create(
        changeset=world['changeset'],
        story_character_revision=world['beta_revision'],
        cover=world['cover'], scan_date=world['cover'].last_upload,
        **TURNED)
    client.force_login(world['user'])
    data = _page_data(client, world)
    data['box-1-DELETE'] = 'on'

    response = client.post(world['url'], data)

    assert response.status_code == 302
    assert not CoverCharacterBoxRevision.objects.filter(
        id=added.id).exists()
    assert world['box_revision'].id in {
        box.id for box in _boxes(world).values()}


def test_remove_on_a_row_without_box_changes_nothing(client, world):
    """Remove ticked on a character not marked writes nothing."""
    client.force_login(world['user'])
    data = _page_data(client, world)
    data['box-1-DELETE'] = 'on'

    response = client.post(world['url'], data)

    assert response.status_code == 302
    assert world['beta_revision'].id not in _boxes(world)
    assert len(_boxes(world)) == 1


def test_clear_removes_saved_boxes_on_saving(client, world):
    """
    What Clear leaves on the rows of two saved boxes, no corners with
    Remove checked, removes them when the page is saved.
    """
    added = CoverCharacterBoxRevision.objects.create(
        changeset=world['changeset'],
        story_character_revision=world['beta_revision'],
        cover=world['cover'], scan_date=world['cover'].last_upload,
        **TURNED)
    client.force_login(world['user'])
    data = _page_data(client, world)
    for row in ('box-0', 'box-1'):
        for name in UPRIGHT:
            data['%s-%s' % (row, name)] = ''
        data['%s-DELETE' % row] = 'on'

    response = client.post(world['url'], data)

    assert response.status_code == 302
    assert not CoverCharacterBoxRevision.objects.filter(
        id=added.id).exists()
    box = CoverCharacterBoxRevision.objects.get(
        id=world['box_revision'].id)
    assert box.deleted is True


@pytest.mark.parametrize('button, target', [
    ('save', 'page'),
    ('save_return', 'changeset'),
    ('return_sequence', 'sequence'),
    ('cancel', 'sequence'),
])
def test_buttons(client, world, button, target):
    """
    Each button goes to its page; all but Cancel save the boxes.
    """
    client.force_login(world['user'])
    data = _page_data(client, world)
    data.update({'box-1-%s' % name: value
                 for name, value in UPRIGHT.items()})
    data[button] = 'Go'

    response = client.post(world['url'], data)

    assert response.status_code == 302
    urls = {
        'page': '%s?cover=%d&mark=2' % (world['url'], world['cover'].id),
        'changeset': reverse('edit', kwargs={'id': world['changeset'].id}),
        'sequence': reverse('edit_revision', kwargs={
          'model_name': 'story', 'id': world['story_revision'].id}),
    }
    assert response.url == urls[target]
    saved = world['beta_revision'].id in _boxes(world)
    assert saved is (button != 'cancel')


def test_saving_with_a_mark_that_is_not_a_row(client, world):
    """
    Saving with a mark parameter that is not a number comes back to the
    page without it.
    """
    client.force_login(world['user'])
    data = _page_data(client, world)
    data['mark'] = 'x'
    data['save'] = 'Save'

    response = client.post(world['url'], data)

    assert response.url == '%s?cover=%d' % (world['url'], world['cover'].id)


@pytest.mark.parametrize('variant', [False, True])
def test_cover_moved_away_in_the_change_is_not_offered(client, world,
                                                       variant):
    """
    A cover the change moves to another issue no longer shows the
    sequence: it is not offered, and without another cover there is no
    button and the page says there is no cover.
    """
    issue = world['issue']
    if variant:
        scan_variant = _variant_cover(issue, 2)
    changeset = world['changeset']
    changeset.change_type = CTYPES['two_issues']
    changeset.save()
    other = Issue.objects.create(
        number='2', series=issue.series, sort_code=5,
        publication_date='1965', key_date='1965-02-00')
    for each in (issue, other):
        IssueRevision.objects.create(changeset=changeset, issue=each,
                                     series=issue.series, number=each.number)
    CoverRevision.objects.create(changeset=changeset, cover=world['cover'],
                                 issue=issue)
    client.force_login(world['user'])

    assert _has_mark_button(world['story_revision'], world['user']) \
        is variant
    response = client.get(world['url'])
    if variant:
        assert _parse(response).data['cover'] == str(scan_variant.id)
        assert _is_error(client.get(
            world['url'] + '?cover=%d' % world['cover'].id))
    else:
        assert _is_error(response)


@pytest.mark.parametrize('choice', ['deleted', 'missing', 'other issue',
                                    'text'])
def test_page_refuses_a_cover_it_cannot_mark_on(client, world, choice):
    """
    A cover parameter for a deleted cover, one that does not exist, one of
    another issue or one that is not a number shows an error, on opening
    and on saving, and nothing is written.
    """
    issue = world['issue']
    if choice == 'deleted':
        cover_id = str(Cover.objects.create(
            issue=issue, deleted=True, last_upload=timezone.now()).id)
    elif choice == 'missing':
        cover_id = str(Cover.objects.order_by('-id').first().id + 1000)
    elif choice == 'other issue':
        other = Issue.objects.create(
            number='2', series=issue.series, sort_code=1,
            publication_date='1965', key_date='1965-02-00')
        cover_id = str(Cover.objects.create(
            issue=other, last_upload=timezone.now()).id)
    else:
        cover_id = 'front'
    client.force_login(world['user'])
    data = _page_data(client, world)
    data.update({'box-1-%s' % name: value
                 for name, value in UPRIGHT.items()})
    data['cover'] = cover_id

    assert _is_error(client.get(world['url'] + '?cover=' + cover_id))
    assert _is_error(client.post(world['url'], data))
    assert len(_boxes(world)) == 1


def test_cover_without_upload_date(client, world):
    """
    On a cover scan without a date of its last upload, as old covers are,
    a box is saved without a scan date and counts as drawn on it.
    """
    cover = world['cover']
    cover.last_upload = None
    cover.save()
    box_revision = world['box_revision']
    box_revision.scan_date = None
    box_revision.save()
    client.force_login(world['user'])

    response = client.get(world['url'])
    content = response.content.decode()
    assert '<span data-box-status aria-live="polite">marked</span>' in content
    assert content.count('data-box-cut-out') == 1
    data = _parse(response).data
    assert data['box-1-scan_date'] == ''
    data.update({'box-1-%s' % name: value
                 for name, value in UPRIGHT.items()})

    response = client.post(world['url'], data)

    assert response.status_code == 302
    added = _boxes(world)[world['beta_revision'].id]
    assert added.scan_date is None
    content = client.get(world['url']).content.decode()
    assert content.count('data-box-cut-out') == 2


def test_hidden_cover_keeps_its_boxes(client, world):
    """
    A cover scan not shown on the site cannot be drawn on; saving the page
    keeps the boxes, and a box shows the image of a missing cover instead
    of its cut-out.
    """
    cover = world['cover']
    cover.limit_display = True
    cover.save()
    box_revision = world['box_revision']
    box_revision.scan_date = cover.last_upload
    box_revision.save()
    client.force_login(world['user'])

    response = client.get(world['url'])
    content = response.content.decode()
    assert 'This cover scan is not shown on the site' in content
    assert 'data-cover-boxes' not in content
    assert 'img/nocover_large.png' in content
    data = _parse(response).data

    response = client.post(world['url'], data)

    assert response.status_code == 302
    box = CoverCharacterBoxRevision.objects.get(id=box_revision.id)
    assert box.scan_date == cover.last_upload
    for name, value in UPRIGHT.items():
        assert getattr(box, name) == value
    assert len(_boxes(world)) == 1


def test_sequence_without_characters(client, world):
    """
    A cover sequence whose characters were all removed has no rows; the
    page opens and saving it writes nothing.
    """
    StoryCharacterRevision.objects.filter(
        story_revision=world['story_revision']).update(deleted=True)
    client.force_login(world['user'])

    response = client.get(world['url'])

    assert response.status_code == 200
    parsed = _parse(response)
    assert parsed.rows == 0
    assert parsed.data['box-TOTAL_FORMS'] == '0'
    assert 'name="mark"' not in response.content.decode()
    modified = world['box_revision'].modified
    response = client.post(world['url'], parsed.data)
    assert response.status_code == 302
    assert len(_boxes(world)) == 1
    assert CoverCharacterBoxRevision.objects.get(
        id=world['box_revision'].id).modified == modified


def test_same_form_sent_twice_adds_one_box(client, world):
    """
    The same page sent twice, as with a double click, writes the box of
    the second character once.
    """
    client.force_login(world['user'])
    data = _page_data(client, world)
    data.update({'box-1-%s' % name: value
                 for name, value in UPRIGHT.items()})

    for _ in range(2):
        assert client.post(world['url'], data).status_code == 302

    assert CoverCharacterBoxRevision.objects.filter(
        changeset=world['changeset'],
        story_character_revision=world['beta_revision']).count() == 1


def _other_sequence_appearance(world):
    """
    An appearance revision of a character in another sequence of the same
    issue, in the same change.
    """
    story_type = StoryType.objects.get_or_create(
        id=STORY_TYPES['comic story'],
        defaults={'name': 'comic story', 'sort_code': 19})[0]
    story = Story.objects.create(issue=world['issue'], type=story_type,
                                 sequence_number=1)
    story_revision = StoryRevision.objects.create(
        changeset=world['changeset'], story=story, issue=world['issue'],
        type=story_type, sequence_number=1)
    return StoryCharacterRevision.objects.create(
        changeset=world['changeset'],
        character=world['alpha_revision'].character,
        story_revision=story_revision, notes='')


@pytest.mark.parametrize('tamper', ['other sequence', 'listed twice',
                                    'more rows', 'no management form'])
def test_tampered_form_writes_nothing(client, world, tamper):
    """
    A form changed by hand, with a character of another sequence, a
    character listed twice, more rows than sent or without the management
    form, shows the page again with an error and writes nothing.
    """
    client.force_login(world['user'])
    data = _page_data(client, world)
    data.update({'box-1-%s' % name: value
                 for name, value in UPRIGHT.items()})
    if tamper == 'other sequence':
        data['box-1-appearance'] = str(_other_sequence_appearance(world).id)
    elif tamper == 'listed twice':
        data['box-1-appearance'] = data['box-0-appearance']
    elif tamper == 'more rows':
        # A third row sent as one of the page, without its character.
        data['box-TOTAL_FORMS'] = data['box-INITIAL_FORMS'] = '3'
    else:
        for name in list(data):
            if name.startswith('box-') and name.endswith('_FORMS'):
                del data[name]
    modified = world['box_revision'].modified

    response = client.post(world['url'], data)

    assert response.status_code == 200
    content = response.content.decode()
    assert 'errorlist' in content
    if tamper == 'listed twice':
        assert 'A character is listed twice, reload the page.' in content
    assert len(_boxes(world)) == 1
    assert CoverCharacterBoxRevision.objects.get(
        id=world['box_revision'].id).modified == modified
    assert_valid_ids(content)


@pytest.mark.parametrize('mark, chosen', [
    ('1', '1'), ('2', '2'), ('3', '2'), ('0', '2'), ('', '2'), ('x', '2')])
def test_row_chosen_for_marking(client, world, mark, chosen):
    """
    The row of the mark parameter is chosen for marking, the first one
    without a box when the parameter names no row.
    """
    client.force_login(world['user'])

    data = _page_data(client, world, '?mark=' + mark)

    assert data['mark'] == chosen


@pytest.mark.parametrize('name, low, high', [
    ('top_left_x', -32768, 32767), ('bottom_left_y', -32768, 32767),
    ('scan_aspect', 1, 2147483647)])
def test_values_are_limited_to_the_database_columns(name, low, high):
    """
    The corners fit a signed small integer and the proportions of the
    scan a positive integer, as they are stored.
    """
    field = CoverCharacterBoxForm().fields[name]

    assert field.clean(str(low)) == low
    assert field.clean(str(high)) == high
    for value in (low - 1, high + 1):
        with pytest.raises(ValidationError):
            field.clean(str(value))


@pytest.mark.parametrize('invalid', [False, True])
def test_page_html_ids_are_unique(client, world, invalid):
    """
    Every id of the page is used once and every label names a field, also
    when the page comes back with errors.
    """
    client.force_login(world['user'])
    _variant_cover(world['issue'], 2)
    if invalid:
        data = _page_data(client, world)
        data['box-1-top_left_x'] = '1000'
        response = client.post(world['url'], data)
        assert response.status_code == 200
    else:
        response = client.get(world['url'])

    assert_valid_ids(response.content.decode())
