# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import mock

from django.db import models

from apps.gcd.models.gcddata import GcdLink
from apps.oi.models import Changeset, LinkRevision


class DummyLink(GcdLink):
    revisions = mock.MagicMock(spec=models.QuerySet)


class DummyLinkRevision(LinkRevision):
    class Meta:
        app_label = 'oi'

    # Don't set related_name here b/c we fake it in DummyLink.
    dummy_link = models.ForeignKey(DummyLink, null=True)

    @property
    def source(self):
        return self.dummy_link

    @source.setter
    def source(self, value):
        self.dummy_link = value


def test_pre_delete():
    with mock.patch('apps.oi.models.LinkRevision.save') as save_mock:
        c = Changeset()
        link = DummyLink()
        add_rev = DummyLinkRevision(changeset=c, dummy_link=link)
        del_rev = DummyLinkRevision(changeset=c, dummy_link=link,
                                    previous_revision=add_rev)
        link.revisions.all.return_value = [add_rev, del_rev]

        del_rev._pre_delete(changes={})
        assert add_rev.series_bond_id is None
        assert del_rev.series_bond_id is None
        save_mock.assert_has_calls([mock.call(), mock.call()])
        assert save_mock.call_count == 2
