# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import mock
import pytest

from django.contrib.contenttypes.models import ContentType

from apps.gcd.models import Image, ImageType
from apps.oi.models import Revision, ImageRevision


def test_excluded_fields():
    assert ImageRevision._get_excluded_field_names() == {
        'image_file',
        'scaled_image',
        'thumbnail',
        'icon',
    } | Revision._get_excluded_field_names()


def test_classification():
    meta = Image._meta
    gf = meta.get_field
    regular_fields = {
        'content_type': gf('content_type'),
        'object_id': gf('object_id'),
        'type': gf('type'),
    }
    irregular_fields = {}
    meta_fields = {
        'marked': gf('marked'),
    }

    assert ImageRevision._get_regular_fields() == regular_fields
    assert ImageRevision._get_irregular_fields() == irregular_fields
    assert ImageRevision._get_meta_fields() == meta_fields

    assert ImageRevision._get_single_value_fields() == regular_fields
    assert ImageRevision._get_multi_value_fields() == {}


@pytest.mark.parametrize('edited, added, unique, exists', [
    # With edited as True (so added is False), the 2nd check is not reached.
    (True, False, True, True),
    # These test the 2nd check by making one of each of the three conditions
    # used False at a time, with the other two True.
    (False, False, True, True),
    (False, True, False, True),
    (False, True, True, False),
])
def test_pre_commit_check(edited, added, unique, exists):
    # We need to patch the two peices of the generic relation because
    # they are referenced in the arguments to filter().  We don't need
    # any specific behavior, we just need them to not try to hit the database.
    with mock.patch('apps.oi.models.Image.objects') as image_obj_mock, \
            mock.patch('apps.oi.models.ImageRevision.object'), \
            mock.patch('apps.oi.models.ContentType.objects.get_for_model',
                       return_value=ContentType()):
        image_obj_mock.filter.return_value.exists.return_value = exists

        previous = None if added else ImageRevision()
        rev = ImageRevision(type=ImageType(unique=unique),
                            is_replacement=False,
                            previous_revision=previous,
                            deleted=not added and not edited)
        # If this doesn't raise, then we pass.
        rev._pre_commit_check()


def test_pre_commit_fail_non_edit_replace():
    # This is an add because no previous revision, so not an edit.
    rev = ImageRevision(is_replacement=True)
    with pytest.raises(ValueError) as excinfo:
        rev._pre_commit_check()

    msg = unicode(excinfo.value)
    assert "Can only replace during edit, not add" in msg


def test_pre_commit_fail_no_additional():
    # See unit test for passing this check on why so many patches.
    with mock.patch('apps.oi.models.Image.objects') as image_obj_mock, \
            mock.patch('apps.oi.models.ImageRevision.object'), \
            mock.patch('apps.oi.models.ContentType.objects.get_for_model',
                       return_value=ContentType()):

        image_obj_mock.filter.return_value.exists.return_value = True
        rev = ImageRevision(type=ImageType(unique=True),
                            is_replacement=False)
        with pytest.raises(ValueError) as excinfo:
            rev._pre_commit_check()

        msg = unicode(excinfo.value)
        assert "Additional images cannot be uploaded" in msg


def test_post_save_object():
    with mock.patch('apps.gcd.models.image.Image.image_file',
                    new_callable=mock.PropertyMock), \
            mock.patch('apps.oi.models.ImageRevision.image_file',
                       new_callable=mock.PropertyMock):
        # Do this as an add- that way if we incorrectly are viewed as
        # a replacement, the attempt to access the previous revision
        # will trigger an exception.
        data_image = Image(id=1)
        rev = ImageRevision(image=data_image)
        rev._post_save_object({})
        rev.image.image_file.save.assert_called_once_with(
            '1.jpg', content=rev.image_file)
        rev.image_file.delete.assert_called_once_with()


def test_post_save_object_replacement():
    with mock.patch('apps.gcd.models.image.Image.image_file',
                    new_callable=mock.PropertyMock), \
            mock.patch('apps.oi.models.ImageRevision.image_file',
                       new_callable=mock.PropertyMock):
        # Do this as an add- that way if we incorrectly are viewed as
        # a replacement, the attempt to access the previous revision
        # will trigger an exception.
        data_image = Image(id=1)
        previous = ImageRevision(id=100, image=data_image)
        rev = ImageRevision(id=101,
                            image=data_image,
                            previous_revision=previous,
                            is_replacement=True)
        rev._post_save_object({})
        previous.image_file.save.assert_called_once_with(
            '100.jpg', content=data_image.image_file)
        rev.image.image_file.delete.assert_called_once_with()
        rev.image.image_file.save.assert_called_once_with(
            '1.jpg', content=rev.image_file)
        rev.image_file.delete.assert_called_once_with()
