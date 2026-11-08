import pytest
from django.urls import reverse

from apps.gcd.models import Brand, BrandUse, Publisher, Series
from apps.oi import states
from apps.oi.models import Changeset, IssueRevision

# Does the new publisher use the brand of the issue, or another of that name?
BRANDS_OF_THE_NEW_PUBLISHER = (
    (True, False),
    (True, True),
    (False, True),
    (False, False),
)


def _new_publisher(country, brand, uses_same_brand, uses_namesake):
    """ The publisher to move to, and the brands the issue should end with. """
    publisher = Publisher.objects.create(name='New Publisher', country=country,
                                         year_began=1940)
    expected = []
    if uses_namesake:
        namesake = Brand.objects.create(name=brand.name)
        BrandUse.objects.create(publisher=publisher, emblem=namesake)
        expected = [namesake]
    if uses_same_brand:
        BrandUse.objects.create(publisher=publisher, emblem=brand)
        expected = [brand]
    return publisher, expected


def _login(client, indexer):
    indexer.is_superuser = True
    indexer.save()
    indexer.indexer.max_reservations = 10
    indexer.indexer.save()
    client.force_login(indexer)


@pytest.mark.django_db
@pytest.mark.parametrize(('uses_same_brand', 'uses_namesake'),
                         BRANDS_OF_THE_NEW_PUBLISHER)
def test_series_move_keeps_a_brand_the_new_publisher_uses(
  client, any_indexer, any_country, any_added_issue, uses_same_brand,
  uses_namesake):
    publisher, expected = _new_publisher(
      any_country, any_added_issue.brand_emblem.get(), uses_same_brand,
      uses_namesake)
    _login(client, any_indexer)
    client.post(reverse('reserve_revision',
                        kwargs={'model_name': 'series',
                                'id': any_added_issue.series.id}))
    changeset = Changeset.objects.get(
      seriesrevisions__series=any_added_issue.series, state=states.OPEN)
    revision = changeset.seriesrevisions.get()

    client.post(reverse('move_series',
                        kwargs={'series_revision_id': revision.id,
                                'publisher_id': publisher.id}),
                {'comments': ''})

    assert list(changeset.issuerevisions.get().brand_emblem.all()) == expected


@pytest.mark.django_db
@pytest.mark.parametrize(('uses_same_brand', 'uses_namesake'),
                         BRANDS_OF_THE_NEW_PUBLISHER)
def test_issue_move_keeps_a_brand_the_new_publisher_uses(
  client, any_indexer, any_country, any_added_issue, any_editing_changeset,
  uses_same_brand, uses_namesake):
    publisher, expected = _new_publisher(
      any_country, any_added_issue.brand_emblem.get(), uses_same_brand,
      uses_namesake)
    old_series = any_added_issue.series
    new_series = Series.objects.create(
      name='New Series', sort_name='New Series', year_began=1990,
      country=old_series.country, language=old_series.language,
      publication_type=old_series.publication_type, publisher=publisher)
    issue_revision = IssueRevision.clone(data_object=any_added_issue,
                                         changeset=any_editing_changeset)
    _login(client, any_indexer)

    client.post(reverse('move_issue',
                        kwargs={'issue_revision_id': issue_revision.id,
                                'series_id': new_series.id}))

    issue_revision = IssueRevision.objects.get(pk=issue_revision.pk)
    assert issue_revision.series == new_series
    assert list(issue_revision.brand_emblem.all()) == expected
