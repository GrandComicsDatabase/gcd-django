# -*- coding: utf-8 -*-

import pytest
import mock

from apps.oi.models import PrinterRevision


@pytest.mark.django_db
def test_create_add_revision(any_added_printer_rev, printer_add_values,
                             any_adding_changeset, keywords):
    rev = any_added_printer_rev

    for k, v in printer_add_values.items():
        assert getattr(rev, k) == v
    assert rev.printer is None

    assert rev.changeset == any_adding_changeset

    assert rev.source is None
    assert rev.source_name == 'printer'


@pytest.mark.django_db
def test_commit_added_revision(any_added_printer_rev, printer_add_values,
                               keywords):
    rev = any_added_printer_rev
    update_all = 'apps.stats.models.CountStats.objects.update_all_counts'
    with mock.patch(update_all) as updater:
        rev.commit_to_display()

    updater.assert_has_calls([
        mock.call({}, country=None, language=None, negate=True),
        mock.call({}, country=rev.printer.country, language=None),
    ])
    assert updater.call_count == 2

    assert rev.printer is not None
    assert rev.source is rev.printer

    for k, v in printer_add_values.items():
        if k == 'keywords':
            # rev.printer.keywords.names() gives wrong result for 'Bar', 'bar'
            pub_kws = [k.name for k in rev.printer.keywords.all()]
            pub_kws.sort()
            assert pub_kws == keywords['list']
        else:
            assert getattr(rev.printer, k) == v
    assert rev.printer.indicia_printer_count == 0
    assert rev.printer.issue_count == 0


@pytest.mark.django_db
def test_create_edit_revision(any_added_printer, printer_add_values,
                              any_editing_changeset, keywords):
    rev = PrinterRevision.clone(
        data_object=any_added_printer,
        changeset=any_editing_changeset)

    for k, v in printer_add_values.items():
        if k == 'keywords':
            # rev.###.keywords.names() gives wrong result for 'Bar', 'bar'
            kws = [k.name for k in rev.printer.keywords.all()]
            kws.sort()
            assert kws == keywords['list']
        else:
            assert getattr(rev, k) == v
    assert rev.printer is any_added_printer

    assert rev.changeset == any_editing_changeset

    assert rev.source is any_added_printer
    assert rev.source_name == 'printer'
