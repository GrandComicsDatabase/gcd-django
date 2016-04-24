# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import os.path
import datetime
import pytest

from django.conf import settings
from django.core.files.base import ContentFile
from django.contrib.contenttypes.models import ContentType

from apps.gcd.models import Image, ImageType
from apps.oi.models import ImageRevision


INITIAL_CONTENTS = 'these are test contents'
REPLACEMENT_CONTENTS = 'replacement data goes here'
ADDITIONAL_CONTENTS = 'for data with two images'


def _build_data_file_path(data_id):
    data_file = '%d.jpg' % data_id
    data_dir = os.path.join(settings.GENERIC_IMAGE_DIR,
                            '%s' % (data_id / 1000))
    return data_dir, data_file


def _build_rev_file_path(rev_id):
    # Technically this can fail due to a race condition if the tests
    # happen to run exactly on midnight when a month changes.
    # It's not worth the trouble to deal with that, to put it mildly.
    today = datetime.date.today()
    rev_file = '%d.jpg' % rev_id
    rev_dir = os.path.join(settings.NEW_GENERIC_IMAGE_DIR,
                           '%02d_%04d' % (today.month, today.year))
    return rev_dir, rev_file


def _verify_files(obj_with_file, file_path, file_contents,
                  obj_no_file=None):
    if obj_no_file:
        assert not obj_no_file.image_file

    url = obj_with_file.image_file.url
    assert url.endswith(file_path)
    assert obj_with_file.image_file.read() == file_contents


@pytest.fixture
def unique_type():
    return ImageType.objects.get_or_create(name='test',
                                           unique=True,
                                           description='')[0]


@pytest.fixture
def added_marked_image_revision(unique_type, any_added_publisher,
                                any_adding_changeset):
    content_type = ContentType.objects.get_for_model(any_added_publisher)
    image_type = ImageType.objects.get_or_create(name='test',
                                                 unique=True,
                                                 description='')[0]
    rev = ImageRevision(changeset=any_adding_changeset,
                        content_type=content_type,
                        object_id=any_added_publisher.id,
                        type=image_type,
                        marked=True)
    rev.save()
    rev_dir, rev_file = _build_rev_file_path(rev.id)
    rev.image_file.save(rev_file, content=ContentFile(INITIAL_CONTENTS))
    return rev


@pytest.fixture
def added_marked_image(added_marked_image_revision):
    added_marked_image_revision.commit_to_display()
    return added_marked_image_revision.image


@pytest.fixture
def replaced_image_revision(added_marked_image, any_editing_changeset):
    rev = ImageRevision.clone(added_marked_image, any_editing_changeset)
    rev.is_replacement = True
    rev_dir, rev_file = _build_rev_file_path(rev.id)
    rev.image_file.save(rev_file, content=ContentFile(REPLACEMENT_CONTENTS))
    return rev


@pytest.mark.django_db
def test_create_marked_image_revision(added_marked_image_revision,
                                      any_added_publisher, unique_type,
                                      any_adding_changeset):
    # rev = added_marked_image_revision
    rev = ImageRevision.objects.get(pk=added_marked_image_revision.id)
    rev_dir, rev_file = _build_rev_file_path(rev.id)
    full_rev_path = os.path.join(rev_dir, rev_file)

    assert rev.object == any_added_publisher
    assert rev.type == unique_type
    assert rev.marked is True
    assert rev.is_replacement is False

    _verify_files(rev, full_rev_path, INITIAL_CONTENTS)


@pytest.mark.django_db
def test_commit_added_marked_image_revision(added_marked_image_revision):
    rev = added_marked_image_revision
    rev.commit_to_display()
    rev = ImageRevision.objects.get(pk=rev.id)

    assert isinstance(rev.image, Image)
    assert rev.image.id
    assert rev.image.object == rev.object
    assert rev.image.type == rev.type
    assert rev.image.marked is rev.marked

    full_data_path = os.path.join(*_build_data_file_path(rev.source.id))
    _verify_files(rev.source, full_data_path, INITIAL_CONTENTS, rev)


@pytest.mark.django_db
def test_clone_image_revision(added_marked_image, any_editing_changeset):
    data = added_marked_image
    rev = ImageRevision.clone(data, any_editing_changeset)
    rev = ImageRevision.objects.get(pk=rev.id)

    assert rev.image == data
    assert rev.object == data.object
    assert rev.type == data.type

    # The mark should be ignored when setting up the ImageRevision.
    assert rev.marked is False

    # We do not automatically do anything with is_replacement
    assert rev.is_replacement is False

    # We do not automatically populate the file field.
    assert not rev.image_file


@pytest.mark.django_db
def test_replace_image(replaced_image_revision):
    rev = replaced_image_revision
    rev.commit_to_display()

    data = rev.image
    assert data.object == rev.object
    assert data.type == rev.type
    assert data.marked is rev.marked

    full_data_path = os.path.join(*_build_data_file_path(data.id))
    _verify_files(data, full_data_path, REPLACEMENT_CONTENTS, rev)

    full_prev_path = os.path.join(*_build_rev_file_path(
        rev.previous_revision.id))
    _verify_files(rev.previous_revision, full_prev_path, INITIAL_CONTENTS)


@pytest.mark.django_db
def test_delete_image(added_marked_image, any_deleting_changeset):
    # No need to re-test clone as test_clone_image_revision covers it.
    rev = ImageRevision.clone(added_marked_image, any_deleting_changeset)
    rev.deleted = True
    rev.commit_to_display()

    # Reload to make sure we did the usual not-really-delete.
    data = Image.objects.get(pk=added_marked_image.pk)
    assert rev.image == data
    assert data.deleted is True
    _verify_files(data, os.path.join(*_build_data_file_path(data.id)),
                  INITIAL_CONTENTS, rev)

    # Also verify that we didn't copy anything back to the previous revision
    assert not rev.previous_revision.image_file
