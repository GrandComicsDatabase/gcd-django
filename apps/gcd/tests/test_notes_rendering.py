from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from django.contrib.auth.models import AnonymousUser
from django.http import Http404
from django.template import Context, Template
from django.template.base import VariableNode
from django.template.defaulttags import ForNode, IfNode
from django.template.loader import get_template, render_to_string
from django.urls import reverse
from django.test import RequestFactory, override_settings
from markdownx.utils import markdownify

from apps.gcd.markdown_extension import render_markdown
from apps.stddata.models import Country, Language
from apps.gcd.models import (
    Character, CharacterNameDetail, Group, GroupMembership, GroupNameDetail,
    Issue, Publisher, Reprint, Series, Story, StoryType)
from apps.gcd.models.character import GroupMembershipType
from apps.gcd.models.story import character_notes
from apps.gcd.templatetags.credits import (
    follow_reprint_link, generate_reprint_link, generate_reprint_link_sequence,
    show_credit, show_reprints, split_reprint_string)
from apps.gcd.templatetags.display import show_series_tracking
from apps.gcd.views.details import show_group_membership
from apps.oi.models import StoryCharacterRevision
from apps.oi.templatetags.compare import field_value, show_diff_markdown


SOURCE = ('**Membership note** [reference](https://example.org/source)'
          '\nNext line')


@pytest.mark.parametrize('name', [
    'award', 'received_award', 'character_relation', 'group_membership',
    'group_relation', 'feature_logo', 'feature_relation',
    'creator_art_influence', 'creator_degree', 'creator_membership',
    'creator_non_comic_work', 'creator_relation', 'creator_school',
    'creator_signature'])
@pytest.mark.parametrize('prefix', ['', 'tw_'])
def test_other_detail_notes_do_not_gain_markdown(name, prefix):
    template = get_template(f'gcd/details/{prefix}{name}.html').template
    record = SimpleNamespace(notes='**Literal** <b>text</b>')
    context = Context({name: record, 'page': SimpleNamespace(number=1)})
    nodes = [node for node in template.nodelist.get_nodes_by_type(IfNode)
             if node.token.contents.startswith(f'if {name}.notes')]
    assert nodes
    with context.bind_template(template):
        for node in nodes:
            rendered = node.render(context)
            assert '**Literal** &lt;b&gt;text&lt;/b&gt;' in rendered
            assert '<strong>Literal</strong>' not in rendered


def test_baseform_notes_keep_markdown_without_expanding_tracking_fields():
    from markdownx.widgets import MarkdownxWidget
    from apps.oi.forms.character import (
        GroupRevisionForm, GroupMembershipRevisionForm)
    from apps.oi.forms.series import SeriesRevisionForm
    assert isinstance(GroupRevisionForm.base_fields['notes'].widget,
                      MarkdownxWidget)
    assert not isinstance(GroupMembershipRevisionForm.base_fields['notes']
                          .widget, MarkdownxWidget)
    assert not isinstance(SeriesRevisionForm.base_fields['tracking_notes']
                          .widget, MarkdownxWidget)


@pytest.mark.parametrize('model', ['character', 'group'])
@pytest.mark.parametrize('prefix', ['', 'tw_'])
def test_inline_relationship_and_membership_lists_remain_plain(model, prefix):
    template = get_template(f'gcd/details/{prefix}{model}.html').template
    source = SOURCE + ' <b>literal</b>'
    target = SimpleNamespace(id=1, descriptor='Target')
    row = SimpleNamespace(
        id=1, notes=source, character=target, group=target,
        to_character=target, to_group=target,
        pre_process_relation=lambda obj: (target, 'Related'))
    fields = ('active_relations_own', 'active_translations',
              'active_alternate_universe_versions',
              ('active_memberships' if model == 'character'
               else 'active_members'))
    obj = SimpleNamespace(**{field: [row] for field in fields})
    context = Context({model: obj})
    # Render the real list loops without unrelated page/database dependencies.
    loops = [node for node in template.nodelist.get_nodes_by_type(ForNode)
             if node.sequence.token in {
                 f'{model}.{field}' for field in fields}]
    assert len(loops) == (3 if model == 'group' and not prefix else 4)
    with context.bind_template(template):
        for loop in loops:
            rendered = loop.render(context)
            assert SOURCE in rendered
            assert '&lt;b&gt;literal&lt;/b&gt;' in rendered
            assert '<strong>Membership note</strong>' not in rendered
            assert 'href="https://example.org/source"' not in rendered


@pytest.mark.parametrize('collection', ['open_items', 'pending_items'])
def test_voting_notes_keep_plain_text_and_linebreaks(collection):
    template = get_template('voting/agenda.html').template
    item = SimpleNamespace(notes=SOURCE + '<b>x</b>')
    context = Context({collection: [item]})
    loop, = [node for node in template.nodelist.get_nodes_by_type(ForNode)
             if node.sequence.token == collection]
    with context.bind_template(template):
        rendered = loop.render(context)
    assert '**Membership note**' in rendered
    assert '<br>Next line&lt;b&gt;x&lt;/b&gt;' in rendered
    assert '<a ' not in rendered


def test_mycomics_notes_keep_plain_text():
    template = get_template('mycomics/collection_item.html').template
    context = Context({'item': SimpleNamespace(notes=SOURCE + '<b>x</b>')})
    node, = [node for node in template.nodelist.get_nodes_by_type(IfNode)
             if node.token.contents == 'if item.notes']
    with context.bind_template(template):
        rendered = node.render(context)
    assert SOURCE + '&lt;b&gt;x&lt;/b&gt;' in rendered
    assert '<a ' not in rendered


@pytest.mark.parametrize('prefix', ['', 'tw_'])
def test_story_template_reprint_newlines_are_converted_once(prefix):
    template = get_template(f'gcd/details/{prefix}single_story.html').template
    story = Mock(reprint_notes='First\nSecond', type_id=0)
    for manager in (story.from_all_reprints, story.to_all_reprints):
        manager.select_related.return_value.order_by.return_value = []
    context = Context({'story': story})
    node, = [node for node in template.nodelist.get_nodes_by_type(VariableNode)
             if 'show_reprints' in node.filter_expression.token]
    with context.bind_template(template):
        rendered = node.render(context)
    assert 'First<br>Second' in rendered
    assert '<br><br>' not in rendered


@pytest.mark.parametrize('source, expected', [
    ('', ''), (None, ''), ('Plain & simple', 'Plain &amp; simple'),
    ('**bold** and *italic*', '<strong>bold</strong> and <em>italic</em>'),
    ('one\ntwo', 'one<br>\ntwo'),
    ('- one\n- two', '<ul class="list-disc list-outside ps-8">'),
    ('[label](https://example.org)', 'href="https://example.org"'),
    ('https://example.org/' + 'x' * 100, 'https://example.org/' + 'x' * 100),
    ('<b>legacy HTML</b>', '<b>legacy HTML</b>'),
    ('<div markdown="1">**bold**</div>', '<strong>bold</strong>'),
])
def test_renderer_and_editor_preview_share_policy(source, expected):
    rendered = render_markdown(source)
    assert expected in rendered
    if source is not None:
        assert rendered == markdownify(source)


@pytest.mark.parametrize('source, destination, label, suffix', [
    ('www.example.org', 'http://www.example.org', 'www.example.org', ''),
    ('editor@example.org', 'mailto:editor@example.org',
     'editor@example.org', ''),
    ('**editor@example.org**', 'mailto:editor@example.org',
     'editor@example.org', ''),
    ('**www.example.org**', 'http://www.example.org', 'www.example.org', ''),
    ('(www.example.org).', 'http://www.example.org', 'www.example.org', ').'),
    ('editor+notes@example.org,', 'mailto:editor%2Bnotes@example.org',
     'editor+notes@example.org', ','),
    ('https://example.org/a_(b).', 'https://example.org/a_(b)',
     'https://example.org/a_(b)', '.'),
    ('www.example.org/?a=1&b=2', 'http://www.example.org/?a=1&amp;b=2',
     'www.example.org/?a=1&amp;b=2', ''),
])
def test_automatic_links_preserve_legacy_addresses(
        source, destination, label, suffix):
    rendered = render_markdown(source)
    assert rendered.count('<a ') == 1
    assert f'href="{destination}"' in rendered
    assert f'>{label}</a>{suffix}' in rendered
    assert rendered == markdownify(source)
    assert rendered in render_to_string(
        'gcd/bits/notes.html', {'value': source})


@pytest.mark.parametrize('entity', ['&amp;', '&#38;', '&#x26;'])
@pytest.mark.parametrize('prefix', ['https://', 'www.'])
@pytest.mark.parametrize('ending', ['b=2', ''])
def test_automatic_links_decode_entities_in_labels_and_destinations(
        entity, prefix, ending):
    source = f'{prefix}example.org/?a=1{entity}{ending}'
    plain = f'{prefix}example.org/?a=1&{ending}'
    # Entity decoding changes the candidate's length, but must not consume
    # following text or leave the entity's semicolon outside the link.
    rendered = render_markdown(source + ' Next')
    assert rendered == render_markdown(plain + ' Next')
    assert rendered == markdownify(source + ' Next')
    assert rendered.count('<a ') == 1
    assert '</a> Next' in rendered
    assert '&amp;amp;' not in rendered


def test_decoded_url_entities_remain_escaped():
    source = ('https://example.org/?q=&quot;&lt;script&gt;'
              'alert(1)&lt;/script&gt;')
    rendered = render_markdown(source)
    assert '<script' not in rendered
    assert '&lt;script&gt;' in rendered
    assert rendered == markdownify(source)


@pytest.mark.parametrize('source', [
    '[www.example.org](https://example.net)',
    '[editor@example.org](mailto:other@example.net)',
    '<https://example.org>',
    '<editor@example.org>',
])
def test_automatic_links_do_not_nest_in_markdown_links(source):
    rendered = render_markdown(source)
    assert rendered.count('<a ') == 1
    assert rendered.count('</a>') == 1
    assert rendered == markdownify(source)


@pytest.mark.parametrize('source', [
    '`www.example.org editor@example.org`',
    '    www.example.org editor@example.org',
    '<span title="www.example.org editor@example.org">label</span>',
    '<img src="https://example.org/image.png" alt="editor@example.org">',
])
def test_automatic_links_leave_code_and_html_attributes_alone(source):
    rendered = render_markdown(source)
    assert '<a ' not in rendered
    assert rendered == markdownify(source)


@pytest.mark.parametrize('model, field', [
    ('creator', 'bio'), ('group', 'description')])
@pytest.mark.parametrize('prefix', ['', 'tw_'])
def test_biography_and_description_use_shared_rich_text(model, field, prefix):
    template = get_template(f'gcd/details/{prefix}{model}.html').template
    source = ('**Bold** www.example.org\n\n- First\n- Second\n\n'
              '<script>alert(1)</script>')
    context = Context({model: SimpleNamespace(**{field: source})})
    node, = [node for node in template.nodelist.get_nodes_by_type(IfNode)
             if node.token.contents == f'if {model}.{field}']
    with context.bind_template(template):
        rendered = node.render(context)
    expected = render_to_string('gcd/bits/rich_text.html', {'value': source})
    assert expected in rendered
    assert '<strong>Bold</strong>' in rendered
    assert 'href="http://www.example.org"' in rendered
    assert '<li>First</li>' in rendered
    assert '<script' not in rendered
    assert '<p><strong>Biography:' not in rendered


@pytest.mark.parametrize('source', [
    '<script>alert(1)</script>',
    '<img src="x" onerror="alert(1)">',
    '[click](javascript:alert%281%29)',
    '<a href="java&#x73;cript:alert(1)">click</a>',
    '<svg onload="alert(1)"></svg>',
    '<div style="position:fixed" onclick="alert(1)">x</div>',
])
def test_renderer_removes_executable_html(source):
    rendered = render_markdown(source)
    assert not any(token in rendered.lower() for token in (
        '<script', '<svg', 'onerror=', 'onclick=', 'onload=',
        'javascript:', 'style='))
    assert rendered == markdownify(source)


@override_settings(MARKDOWNX_MARKDOWN_EXTENSIONS=[])
def test_display_sanitizes_without_preview_extension():
    rendered = render_markdown('<img src="x" onerror="alert(1)">')
    assert 'onerror' not in rendered
    assert '<img' not in rendered


@pytest.mark.parametrize('source', [
    '![Cover](https://example.org/cover.png)',
    '<img src="https://example.org/cover.png" alt="Cover" width="100">',
])
def test_images_are_removed_from_display_and_preview(source):
    for rendered in (render_markdown(source), markdownify(source)):
        assert '<img' not in rendered
        assert 'cover.png' not in rendered
    assert 'Before' in render_markdown('Before ' + source + ' After')
    assert 'After' in render_markdown('Before ' + source + ' After')


@pytest.mark.parametrize('source', [
    '<blockquote><p>Legacy <em>quotation</em></p></blockquote>',
    '<table><tbody><tr><th scope="col">Heading</th>'
    '<td colspan="2">Value</td></tr></tbody></table>',
    '<a href="/issue/123/" title="Reference">Local link</a>',
    '<img src="https://example.org/image.png" alt="Cover" width="100">',
])
def test_legacy_html_uses_the_same_display_and_preview_policy(source):
    assert render_markdown(source) == markdownify(source)
    assert render_markdown(render_markdown(source)) == render_markdown(source)


def test_appearance_template_preserves_plain_text():
    appearance = StoryCharacterRevision(
        notes='**Literal** [reference](https://example.org) <b>text</b>')
    # The list template needs only a display name/link, not a persisted story.
    row = SimpleNamespace(
        character=SimpleNamespace(
            name='Hero', get_absolute_url='/character/1/'),
        show_notes=appearance.show_notes())
    rendered = render_to_string('gcd/bits/tw_character_list.html', {
        'character_list': [(row, [], None)]})
    assert '**Literal** [reference](https://example.org)' in rendered
    assert '&lt;b&gt;text&lt;/b&gt;' in rendered
    assert '<strong>' not in rendered
    assert '<p' not in rendered


def test_gcd_links_and_missing_references():
    obj = Mock()
    obj.get_absolute_url.return_value = '/group/123/'
    obj.object_markdown_name.return_value = 'Example & Friends'
    with patch('apps.gcd.markdown_extension.get_object_or_404',
               return_value=obj):
        rendered = render_markdown('[gcd_link_group](123)')
        assert 'href="/group/123/"' in rendered
        assert 'Example &amp; Friends' in rendered
        rendered = render_markdown('[gcd_link_name_group](123){Team}')
        assert '>Team</a>' in rendered
    with patch('apps.gcd.markdown_extension.get_object_or_404',
               side_effect=Http404):
        assert 'No corresponding GCD object found' in render_markdown(
            '[gcd_link_group](123)')


def test_group_appearance_template_preserves_plain_text():
    group = SimpleNamespace(
        group_name=SimpleNamespace(
            name='Team', group=SimpleNamespace(get_absolute_url='/group/1/')),
        notes='**Literal** <b>text</b>')
    rendered = render_to_string('gcd/bits/tw_story_characters.html', {
        'characters': ([(group, None, [])], [])})
    assert '(**Literal** &lt;b&gt;text&lt;/b&gt;)' in rendered
    assert '<strong>' not in rendered


def test_reprint_comparison_preserves_plain_text():
    issue = Mock()
    issue.get_absolute_url.return_value = '/issue/1/'
    issue.full_name.return_value = 'Example #1'
    reprint = SimpleNamespace(
        origin_issue=issue, target_issue=issue, target=None,
        notes='**Literal** [link](https://example.org) <b>text</b>')
    rendered = Reprint.get_compare_string(reprint, issue)
    assert '**Literal** [link](https://example.org) &lt;b&gt;text&lt;/b&gt;' \
        in rendered
    assert '<strong>' not in rendered


@pytest.mark.parametrize('table_name', [
    'BrandGroupEmblemTable', 'BrandEmblemPublisherTable',
    'BrandEmblemGroupTable'])
def test_inline_brand_table_notes_remain_plain(table_name):
    from apps.gcd.models import publisher
    table = getattr(publisher, table_name)([{'notes': SOURCE + '<b>x</b>'}])
    # Ordinary columns leave escaping to the table's template context.
    cell = table.rows[0].get_cell('notes')
    rendered = Template('{{ cell }}').render(Context({'cell': cell}))
    assert SOURCE + '&lt;b&gt;x&lt;/b&gt;' == rendered
    assert table.rows[0].get_cell_value('notes') == SOURCE + '<b>x</b>'


def test_partial_handles_blocks_and_escapes_label():
    rendered = render_to_string('gcd/bits/notes.html', {
        'value': '- one\n- two', 'label': '<script>label</script>'})
    assert '<li>one</li>' in rendered
    assert '<div class="notes"' in rendered
    assert '&lt;script&gt;label&lt;/script&gt;' in rendered
    assert render_to_string('gcd/bits/notes.html', {'value': ''}).strip() == ''


def test_appearance_notes_keep_plain_text_contract():
    character = SimpleNamespace(
        is_flashback=True, is_death=False, is_origin=False,
        role='<b>role</b>', notes=SOURCE)
    text = character_notes(character)
    assert SOURCE in text
    html = character_notes(character, html=True)
    assert SOURCE in html
    assert '<strong>' not in html
    assert '&lt;b&gt;role&lt;/b&gt;' in html
    assert '(flashback)' in html
    assert character.notes == SOURCE


def test_revision_appearance_notes_match_published_display():
    revision = StoryCharacterRevision(notes=SOURCE)
    assert SOURCE in revision.show_notes()
    assert '<strong>' not in revision.show_notes()
    assert SOURCE in revision.show_character_notes()


def test_reprint_link_notes_and_semicolon_compatibility():
    issue = Mock(publication_date='', variant_cover_status=0)
    issue.series.country.code = 'us'
    issue.get_absolute_url.return_value = '/issue/123/'
    issue.full_name.return_value = 'Example #1'
    story = SimpleNamespace(sequence_number=1, id=456)
    for rendered in (generate_reprint_link(issue, 'from', notes=SOURCE),
                     generate_reprint_link_sequence(
                         story, issue, 'in', notes=SOURCE)):
        assert '[' + SOURCE + ']' in rendered
        assert '<strong>' not in rendered
        assert 'href="https://example.org/source"' not in rendered
    assert split_reprint_string('from A (x; y); in **B** [z; w]') == [
        'from A (x; y)', 'in **B** [z; w]']
    revision = SimpleNamespace(reprint_notes='from **A**; in *B*')
    rendered = field_value(revision, 'reprint_notes')
    assert 'from **A**' in rendered
    assert 'in *B*' in rendered


@pytest.mark.parametrize('surface', [
    'credit', 'original_credit', 'story', 'comparison', 'from', 'to'])
def test_reprint_note_lists_stay_plain_text(surface):
    source = ('from **First** [reference](https://example.org/source)'
              '\n\nNext paragraph; in *Second* & <b>more</b>')
    if surface in ('credit', 'original_credit', 'comparison'):
        field = ('reprint_original_notes' if surface == 'original_credit'
                 else 'reprint_notes')
        record = SimpleNamespace(**{field: source})
        if surface == 'comparison':
            rendered = field_value(record, field)
        else:
            rendered = show_credit(record, field, bare_value=True)[1]
    elif surface == 'story':
        record = Mock(reprint_notes=source, type_id=0)
        # Empty relations isolate textual notes without touching a database.
        for manager in (record.from_all_reprints, record.to_all_reprints):
            manager.select_related.return_value.order_by.return_value = []
        rendered = show_reprints(record, bare_value=True)
    else:
        endpoint = Mock(reprint_notes=source)
        endpoint.from_reprints.all.return_value = []
        endpoint.to_reprints.all.return_value = []
        reprint = SimpleNamespace(origin=endpoint, target=endpoint)
        rendered = follow_reprint_link(reprint, surface)

    # bare_value returns list items for the caller's ul.
    if surface != 'story':
        assert '<ul>' in rendered
    assert '<li>' in rendered
    # Short annotations must not interpret Markdown or user-supplied HTML.
    assert '<p' not in rendered
    assert 'pt-4' not in rendered
    assert '<strong>' not in rendered
    assert '<em>' not in rendered
    assert '<b>' not in rendered
    assert '<a ' not in rendered
    assert '<br' not in rendered
    if surface != 'to':
        assert '**First** [reference](https://example.org/source)' in rendered
        assert 'Next paragraph' in rendered
    if surface != 'from':
        assert '*Second* &amp; &lt;b&gt;more&lt;/b&gt;' in rendered
    if surface in ('from', 'to'):
        assert ('*Second*' if surface == 'from'
                else '**First**') not in rendered
    else:
        assert rendered.count('<li>') == 2


def test_bond_notes_remain_plain_in_tracking():
    series = Mock()
    bond = SimpleNamespace(
        origin=series, target=None, notes=SOURCE + '<b>x</b>',
        bond_type=SimpleNamespace(id=1))
    relative = SimpleNamespace(
        bond=bond, near_issue=None, near_issue_default=None,
        has_explicit_far_issue=False, far_series=Mock())
    relative.far_series.full_name_with_link.return_value = 'Another series'
    series.series_relative_bonds.return_value = [relative]
    rendered = show_series_tracking(series)
    assert SOURCE + '&lt;b&gt;x&lt;/b&gt;' in rendered
    assert '<strong>Membership note</strong>' not in rendered
    assert '</dd></dl>' in rendered


def test_review_preview_preserves_markdown_source():
    rendered = show_diff_markdown([(1, SOURCE)], 'change')
    assert '<strong>Membership note</strong>' in rendered
    assert '**Membership note**' in rendered
    assert field_value(SimpleNamespace(tracking_notes=SOURCE),
                       'tracking_notes') == SOURCE.replace('\n', '<br>')


@pytest.mark.django_db
@pytest.mark.parametrize('template_name', [
    'gcd/details/single_story.html', 'gcd/details/tw_single_story.html'])
def test_story_templates_convert_note_newlines_once(template_name):
    country = Country.objects.get(code='us')
    language = Language.objects.get(code='en')
    publisher = Publisher.objects.create(name='Example', country=country)
    series = Series.objects.create(
        name='Example', publisher=publisher, country=country,
        language=language, year_began=2020)
    issue = Issue.objects.create(series=series, number='1', sort_code=1)
    story = Story.objects.create(
        issue=issue, sequence_number=1, title='Example',
        type=StoryType.objects.get(name='comic story'),
        characters='Legacy first\nLegacy second',
        reprint_notes='Note first\nNote second')
    request = RequestFactory().get('/')
    request.user = AnonymousUser()
    rendered = render_to_string(template_name, {
        'story': story, 'request': request, 'user': request.user})
    assert 'Note first<br>Note second' in rendered
    assert 'Note first<br><br>' not in rendered
    if template_name == 'gcd/details/single_story.html':
        assert 'Legacy first<br>Legacy second' in rendered


@pytest.mark.django_db
def test_group_membership_detail_and_parent_pages(client):
    language = Language.objects.get(code='en')
    character = Character.objects.create(
        name='Example Hero', language=language)
    group = Group.objects.create(name='Example Team', language=language)
    CharacterNameDetail.objects.create(
        character=character, name=character.name, is_official_name=True)
    GroupNameDetail.objects.create(
        group=group, name=group.name, is_official_name=True)
    membership_type = GroupMembershipType.objects.create(
        type='Member', reverse_type='Includes')
    membership = GroupMembership.objects.create(
        character=character, group=group, membership_type=membership_type,
        notes=SOURCE)
    for name, kwargs in [
        ('show_group_membership', {'group_membership_id': membership.pk}),
        ('show_group', {'group_id': group.pk}),
        ('show_character', {'character_id': character.pk}),
    ]:
        response = client.get(reverse(name, kwargs=kwargs))
        assert response.status_code == 200
        content = response.content.decode()
        assert '**Membership note**' in content
        assert '<strong>Membership note</strong>' not in content
    membership.refresh_from_db()
    assert membership.notes == SOURCE
    request = RequestFactory().get('/')
    request.user = AnonymousUser()
    preview = show_group_membership(request, membership, preview=True)
    assert '**Membership note**' in preview.content.decode()
    assert '<strong>Membership note</strong>' not in preview.content.decode()
