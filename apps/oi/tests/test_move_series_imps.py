import pytest
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse

from apps.gcd.models import (
    Brand, BrandUse, ExternalSite, IndiciaPublisher, Publisher)
from apps.oi import states
from apps.oi.models import (
    Changeset, CTYPES, ExternalLinkRevision, IssueRevision, SeriesRevision)


def _add_issue(series, indexer, number, indicia_publisher, brand, after):
    changeset = Changeset.objects.create(state=states.OPEN, indexer=indexer,
                                         change_type=CTYPES['issue_add'])
    revision = IssueRevision.objects.create(
      changeset=changeset, series=series, number=number, after=after,
      no_title=True, no_volume=True, no_isbn=True, no_barcode=True,
      no_rating=True, indicia_publisher=indicia_publisher,
      publication_date='February 1947', key_date='1947-02-00')
    revision.brand_emblem.set([brand])
    revision.commit_to_display()
    changeset.state = states.APPROVED
    changeset.save()
    return revision.issue


def _two_issues_of_a_series(any_indexer, any_added_issue):
    brand = any_added_issue.brand_emblem.get()
    second = _add_issue(any_added_issue.series, any_indexer, '43',
                        any_added_issue.indicia_publisher, brand,
                        after=any_added_issue)
    return [any_added_issue, second]


def _target_publisher(issue, country, with_same_names=True):
    """ A publisher, with its own brand and indicia publisher on request. """
    target = Publisher.objects.create(name='Target Publisher', country=country,
                                      year_began=1940)
    if not with_same_names:
        return target, None, None
    indicia_publisher = IndiciaPublisher.objects.create(
      name=issue.indicia_publisher.name, parent=target, country=country,
      year_began=1940)
    brand = Brand.objects.create(name=issue.brand_emblem.get().name)
    BrandUse.objects.create(publisher=target, emblem=brand)
    return target, indicia_publisher, brand


def _reserve_series(client, indexer, series):
    indexer.is_superuser = True
    indexer.save()
    indexer.indexer.max_reservations = 10
    indexer.indexer.save()
    client.force_login(indexer)
    client.post(reverse('reserve_revision',
                        kwargs={'model_name': 'series', 'id': series.id}))
    changeset = Changeset.objects.get(seriesrevisions__series=series,
                                      state=states.OPEN)
    return changeset, changeset.seriesrevisions.get()


def _move_series(client, revision, target):
    client.post(reverse('move_series',
                        kwargs={'series_revision_id': revision.id,
                                'publisher_id': target.id}),
                {'comments': ''})
    return Changeset.objects.get(id=revision.changeset_id)


@pytest.mark.django_db
@pytest.mark.parametrize('with_same_names', [True, False])
def test_series_move_counts_only_the_move(client, any_indexer, any_country,
                                          any_added_issue, with_same_names):
    issues = _two_issues_of_a_series(any_indexer, any_added_issue)
    target, indicia_publisher, brand = _target_publisher(
      any_added_issue, any_country, with_same_names)
    changeset, revision = _reserve_series(client, any_indexer,
                                          any_added_issue.series)

    changeset = _move_series(client, revision, target)

    assert changeset.state == states.PENDING
    assert changeset.issuerevisions.count() == len(issues)
    for issue_revision in changeset.issuerevisions.all():
        assert issue_revision.indicia_publisher == indicia_publisher
        assert list(issue_revision.brand_emblem.all()) == (
          [brand] if brand else [])
    # The publisher of the series, and nothing for what followed from it.
    assert changeset.imps == 1


@pytest.mark.django_db
def test_series_move_keeps_the_imps_of_the_indexers_own_edits(
  client, any_indexer, any_country, any_added_issue):
    _two_issues_of_a_series(any_indexer, any_added_issue)
    target, _, _ = _target_publisher(any_added_issue, any_country)
    changeset, revision = _reserve_series(client, any_indexer,
                                          any_added_issue.series)
    revision.notes = 'A note from the indexer'
    revision.save()
    link = ExternalLinkRevision(
      site=ExternalSite.objects.create(site='Example', matching='example'),
      link='https://example.com/series')
    link.save_added_revision(
      changeset=changeset, object_id=revision.id,
      content_type=ContentType.objects.get_for_model(SeriesRevision))

    changeset = _move_series(client, revision, target)

    assert changeset.state == states.PENDING
    # The publisher, the notes, and the two fields of the new link.
    assert changeset.imps == 4
