# -*- coding: utf-8 -*-

import pytest
import mock

from django.core.management import call_command

from apps.gcd.models import Publisher
from apps.oi.models import PublisherRevision
from apps.stats.models import CountStats


@pytest.mark.django_db
def test_create_add_revision(any_added_publisher_rev, publisher_add_values,
                             any_adding_changeset, keywords):
    rev = any_added_publisher_rev

    for k, v in publisher_add_values.items():
        assert getattr(rev, k) == v
    assert rev.publisher is None

    assert rev.changeset == any_adding_changeset
    assert rev.date_inferred is False

    assert rev.source is None
    assert rev.source_name == 'publisher'


@pytest.mark.django_db
def test_commit_added_revision(any_added_publisher_rev, publisher_add_values,
                               keywords):
    rev = any_added_publisher_rev
    update_all = 'apps.stats.models.CountStats.objects.update_all_counts'
    with mock.patch(update_all) as updater:
        rev.commit_to_display()

    updater.assert_has_calls([
        mock.call({}, country=None, language=None, negate=True),
        mock.call({'publishers': 1},
                  country=rev.publisher.country, language=None),
    ])
    assert updater.call_count == 2

    assert rev.publisher is not None
    assert rev.source is rev.publisher

    for k, v in publisher_add_values.items():
        if k == 'keywords':
            # rev.###.keywords.names() gives wrong result for 'Bar', 'bar'
            pub_kws = [k.name for k in rev.publisher.keywords.all()]
            pub_kws.sort()
            assert pub_kws == keywords['list']
        else:
            assert getattr(rev.publisher, k) == v
    assert rev.publisher.brand_count == 0
    assert rev.publisher.indicia_publisher_count == 0
    assert rev.publisher.series_count == 0
    assert rev.publisher.issue_count == 0


@pytest.mark.django_db
def test_create_edit_revision(any_added_publisher, publisher_add_values,
                              any_editing_changeset, keywords):
    rev = PublisherRevision.clone(
        data_object=any_added_publisher,
        changeset=any_editing_changeset)

    for k, v in publisher_add_values.items():
        if k == 'keywords':
            # rev.###.keywords.names() gives wrong result for 'Bar', 'bar'
            pub_kws = [k.name for k in rev.publisher.keywords.all()]
            pub_kws.sort()
            assert pub_kws == keywords['list']
        else:
            assert getattr(rev, k) == v
    assert rev.publisher is any_added_publisher

    assert rev.changeset == any_editing_changeset
    assert rev.date_inferred is False

    assert rev.source is any_added_publisher
    assert rev.source_name == 'publisher'


@pytest.mark.django_db
def test_commit_delete_revision_removes_keywords(any_added_publisher,
                                                 any_deleting_changeset,
                                                 keywords):
    rev = PublisherRevision.clone(data_object=any_added_publisher,
                                  changeset=any_deleting_changeset)
    rev.deleted = True
    rev.save()

    rev.commit_to_display()

    publisher = Publisher.objects.get(pk=any_added_publisher.pk)
    assert publisher.deleted
    assert list(publisher.keywords.all()) == []
    # The revision keeps the keywords as text for the change history.
    rev = PublisherRevision.objects.get(pk=rev.pk)
    assert sorted(rev.keywords.split('; ')) == keywords['list']


@pytest.mark.django_db(transaction=True)
def test_commit_after_a_flush(request):
    """
    A transactional test empties the database when it ends.  A commit in a
    test after it still finds the statistics that it updates, whichever
    test ran before.
    """
    call_command('flush', verbosity=0, interactive=False,
                 reset_sequences=False)
    # Made after the flush, which would delete it.
    rev = request.getfixturevalue('any_added_publisher_rev')

    rev.commit_to_display()

    for country in (None, rev.publisher.country):
        assert CountStats.objects.get(name='publishers', language=None,
                                      country=country).count == 1
