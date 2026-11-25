"""The page of a bulk change: rows of exact changes, pages, actions."""
from decimal import Decimal

import pytest

from django.contrib.auth.models import Permission
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils.html import strip_tags

from apps.gcd.models import Issue, Series
from apps.oi import states
from apps.oi.bulk import _shown_change
from apps.oi.models import (
    Changeset, IndiciaPrinterRevision, IndiciaPublisherRevision,
    IssueRevision, CTYPES)


def compare_url(changeset):
    """The address of the page of a change."""
    return reverse('compare', kwargs={'id': changeset.id})


@pytest.fixture
def many_approved_issues(approved_issues, any_adding_changeset):
    """101 approved issues of one series."""
    issues = list(approved_issues)
    first = issues[0]
    while len(issues) < 101:
        revision = IssueRevision(
          changeset=any_adding_changeset, number=str(len(issues) + 42),
          after=issues[-1], series=first.series, no_title=True,
          no_volume=True, indicia_publisher=first.indicia_publisher,
          publication_date='January 1947', price='0.10 USD',
          indicia_frequency='monthly')
        revision.save()
        revision.commit_to_display()
        issues.append(revision.issue)
    return issues


@pytest.fixture
def second_indicia_publisher(indicia_publisher_add_values,
                             any_adding_changeset):
    """An approved indicia publisher besides that of the issues."""
    revision = IndiciaPublisherRevision(
      changeset=any_adding_changeset,
      **dict(indicia_publisher_add_values, name='Second Publisher'))
    revision.save()
    revision.commit_to_display()
    return revision.indicia_publisher


@pytest.mark.django_db
def test_one_row_for_each_changed_object(client, bulk_change,
                                         approved_issues):
    """Each object links to its page; spaces and case show."""
    changeset = bulk_change(approved_issues, IssueRevision,
                            indicia_frequency='Monthly',
                            price='0.10  USD')
    client.force_login(changeset.indexer)

    response = client.get(compare_url(changeset))

    assert response.status_code == 200
    assert response.context['heading'] == '3 issues'
    rows = response.context['rows']
    assert [revision.issue for revision, name, fields in rows] == \
        approved_issues
    case = ('Indicia Frequency', "<span class='deleted'>m</span>onthly",
            "<span class='added'>M</span>onthly")
    spaces = ('Price', '0.10 USD',
              "0.10 <span class='added'>\u00a0</span>USD")
    assert all(fields == [case, spaces] for revision, name, fields in rows)
    content = response.content.decode()
    for issue in approved_issues:
        assert 'href="%s"' % issue.get_absolute_url() in content
    assert 'rowspan="2"' in content
    assert "<span class='added'>\u00a0</span>" in content
    assert reverse('preview_revision',
                   kwargs={'model_name': 'issue',
                           'id': rows[0][0].id}) not in content


@pytest.mark.parametrize('old, new, shown', [
  ('X', 'A  B', "<span class='added'>A  B</span>"),
  ('X', 'A	B', "<span class='added'>A B</span>"),
  ('X', 'A B', "<span class='added'>A B</span>")])
def test_changed_text_keeps_the_spaces_html_hides(old, new, shown):
    """
    A changed part shows as no-break spaces the spaces that HTML would
    merge or hide, as the value lists of the entry page do; a single
    space between words stays a space.
    """
    field = IssueRevision._meta.get_field('notes')

    assert _shown_change(field, old, new, {})[1] == shown


@pytest.mark.django_db
def test_rows_of_a_sequence_change(client, sequence_change,
                                   approved_stories):
    """
    Sequences are rows, in the order of their issues, whatever the order
    of their revisions; the issues that anchor them are not.
    """
    changeset = sequence_change(approved_stories[::-1], genre='Superhero')
    client.force_login(changeset.indexer)

    response = client.get(compare_url(changeset))

    assert response.context['heading'] == '2 sequences in 2 issues'
    assert [(name, fields) for revision, name, fields
            in response.context['rows']] == \
        [('%s sequence %d' % (story.issue, number),
          [('Genre', "<span class='deleted'>s</span>uperhero",
            "<span class='added'>S</span>uperhero")])
         for number, story in enumerate(approved_stories, start=1)]
    content = response.content.decode()
    for story in approved_stories:
        assert 'href="%s"' % story.get_absolute_url() in content


@pytest.mark.django_db
def test_related_objects_and_flags_by_name(client, bulk_change,
                                           approved_issues,
                                           second_indicia_publisher):
    """
    A foreign key shows names, a flag Yes or No, a page count as on the
    site, in model order.
    """
    issue = approved_issues[1]
    changeset = bulk_change([issue], IssueRevision, no_volume=False,
                            page_count=Decimal('32.500'),
                            indicia_publisher=second_indicia_publisher)
    client.force_login(changeset.indexer)

    response = client.get(compare_url(changeset))

    [(revision, name, fields)] = response.context['rows']
    assert fields == [
      ('No Volume', "<span class='deleted'>Yes</span>",
       "<span class='added'>No</span>"),
      ('Page Count', '', "<span class='added'>32.5</span>"),
      ('Indicia Publisher',
       "<span class='deleted'>%s</span>" % issue.indicia_publisher,
       "<span class='added'>Second Publisher</span>")]


@pytest.mark.django_db
def test_page_follows_the_limit(client, settings, bulk_change,
                                approved_issues):
    """A page holds BULK_CHANGE_MAX objects, the most that a change has."""
    settings.BULK_CHANGE_MAX = 2
    changeset = bulk_change(approved_issues, IssueRevision, price='0.25 USD')
    client.force_login(changeset.indexer)

    assert len(client.get(compare_url(changeset)).context['rows']) == 2


@pytest.mark.django_db
def test_second_page_after_100_objects(client, bulk_change,
                                       many_approved_issues):
    """The page holds 100 objects; the next ones are on page 2."""
    changeset = bulk_change(many_approved_issues, IssueRevision,
                            price='0.25 USD')
    client.force_login(changeset.indexer)

    first = client.get(compare_url(changeset))
    second = client.get(compare_url(changeset), {'page': 2})

    assert first.context['heading'] == '101 issues'
    assert len(first.context['rows']) == 100
    assert 'page=2' in first.content.decode()
    assert [revision for revision, name, fields
            in second.context['rows']] == \
        [changeset.issuerevisions.order_by('id').last()]


@pytest.mark.django_db
def test_actions_of_any_change(client, bulk_change, approved_issues,
                               any_approver):
    """The indexer and the approver find the buttons of any change."""
    changeset = bulk_change(approved_issues, IssueRevision,
                            price='0.25 USD')
    process = 'action="%s"' % reverse('process',
                                      kwargs={'id': changeset.id})
    client.force_login(changeset.indexer)

    content = client.get(compare_url(changeset)).content.decode()

    assert process in content
    for name in ('submit', 'discard', 'add_comment'):
        assert 'name="%s"' % name in content

    changeset.submit()
    changeset.assign(any_approver)
    client.force_login(any_approver)

    content = client.get(compare_url(changeset)).content.decode()

    assert process in content
    for name in ('approve', 'discuss', 'cancel', 'release', 'add_comment'):
        assert 'name="%s"' % name in content


@pytest.mark.django_db
def test_edit_leads_to_the_page(client, bulk_change, approved_issues):
    """The edit address of a bulk change redirects to its page."""
    changeset = bulk_change(approved_issues, IssueRevision,
                            price='0.25 USD')
    changeset.indexer.user_permissions.add(Permission.objects.get(
      content_type__app_label='indexer', codename='can_reserve'))
    client.force_login(changeset.indexer)

    response = client.get(reverse('edit', kwargs={'id': changeset.id}))

    assert response.status_code == 302
    assert response.url == compare_url(changeset)


@pytest.mark.django_db
def test_page_of_an_empty_change(client, any_indexer):
    """A bulk change without revisions has a page without rows."""
    changeset = Changeset.objects.create(
      indexer=any_indexer, state=states.OPEN, change_type=CTYPES['bulk'])
    client.force_login(any_indexer)

    response = client.get(compare_url(changeset))

    assert response.status_code == 200
    assert response.context['heading'] == 'no objects'
    assert response.context['rows'] == []


@pytest.mark.django_db
def test_rows_in_the_order_of_the_list(client, bulk_change,
                                       approved_issues):
    """
    The rows follow the issues in their series, not the order in which
    the change made their revisions; only changed objects have a row.
    """
    changeset = bulk_change(approved_issues[::-1], IssueRevision,
                            price='0.25 USD')
    changeset.issuerevisions.filter(issue=approved_issues[1]).update(
      price='0.10 USD')
    client.force_login(changeset.indexer)

    response = client.get(compare_url(changeset))

    assert [revision.issue for revision, name, fields
            in response.context['rows']] == \
        [approved_issues[0], approved_issues[2]]
    assert str(changeset) == '%s and 2 other issues' % approved_issues[0]


@pytest.mark.django_db
def test_page_of_one_object(client, bulk_change, approved_issues):
    """One object is named in the singular; the page is never cached."""
    changeset = bulk_change(approved_issues[:1], IssueRevision,
                            price='0.25 USD')
    client.force_login(changeset.indexer)

    response = client.get(compare_url(changeset))

    assert response.context['heading'] == '1 issue'
    assert 'no-store' in response['Cache-Control']


@pytest.mark.django_db
def test_links_to_many_objects_by_name(client, bulk_change,
                                       approved_issues,
                                       any_added_indicia_printer,
                                       indicia_printer_add_values,
                                       any_adding_changeset):
    """A many-to-many field shows the names of its objects, sorted."""
    revision = IndiciaPrinterRevision(
      changeset=any_adding_changeset,
      **dict(indicia_printer_add_values, name='Another Printer'))
    revision.save()
    revision.commit_to_display()
    issue = approved_issues[0]
    changeset = bulk_change([issue], IssueRevision)
    changeset.issuerevisions.get().indicia_printer.add(
      revision.indicia_printer)
    client.force_login(changeset.indexer)

    response = client.get(compare_url(changeset))

    [(revision, name, fields)] = response.context['rows']
    old = '; '.join(sorted(str(printer)
                           for printer in issue.indicia_printer.all()))
    new = '; '.join(sorted([old, 'Another Printer']))
    assert fields[0][0] == 'Indicia Printer'
    assert strip_tags(fields[0][1]) == old
    assert strip_tags(fields[0][2]) == new


@pytest.mark.django_db
def test_page_shows_the_comments(client, bulk_change, approved_issues):
    """The comments of the change are on its page."""
    changeset = bulk_change(approved_issues, IssueRevision,
                            price='0.25 USD')
    changeset.comments.create(commenter=changeset.indexer,
                              text='Prices of the reprint edition.',
                              old_state=states.OPEN, new_state=states.OPEN)
    client.force_login(changeset.indexer)

    response = client.get(compare_url(changeset))

    assert 'Prices of the reprint edition.' in response.content.decode()


@pytest.mark.django_db
def test_queries_do_not_grow_with_the_rows(client, bulk_change,
                                           approved_issues):
    """A page of three objects needs as many queries as one of two."""
    counts = []
    for issues in (approved_issues[:2], approved_issues):
        changeset = bulk_change(issues, IssueRevision, price='0.25 USD')
        client.force_login(changeset.indexer)
        # The first request also fills the caches of the site.
        client.get(compare_url(changeset))
        with CaptureQueriesContext(connection) as queries:
            client.get(compare_url(changeset))
        counts.append(len(queries))
        changeset.discard(changeset.indexer)

    assert counts[0] == counts[1]


@pytest.mark.django_db
def test_rows_keep_series_of_one_name_apart(client, bulk_change,
                                            approved_issues):
    """Two series of one name and year keep their issues apart."""
    series = Series.objects.get(id=approved_issues[0].series_id)
    series.pk = series.id = None
    series.save()
    Issue.objects.filter(id=approved_issues[0].id).update(series=series)
    issues = Issue.objects.filter(id__in=[issue.id for issue
                                          in approved_issues])
    changeset = bulk_change(issues, IssueRevision, price='0.25 USD')
    client.force_login(changeset.indexer)

    response = client.get(compare_url(changeset))

    assert [revision.issue_id for revision, name, fields
            in response.context['rows']] == \
        [approved_issues[1].id, approved_issues[2].id, approved_issues[0].id]
