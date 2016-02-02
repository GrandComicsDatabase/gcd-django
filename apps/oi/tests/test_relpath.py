# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import mock
import pytest

from django.db import models
from django.db.models import options
from django.db.models.fields import related

from apps.oi.relpath import RelPath


@pytest.fixture
def classes_and_fields():
    starting_model_class = mock.MagicMock(spec=type(models.Model))
    starting_model_class._meta = mock.MagicMock(spec=options.Options)

    foo_model_class = mock.MagicMock(spec=type(models.Model))
    foo_model_class._meta = mock.MagicMock(spec=options.Options)

    bar_model_class = mock.MagicMock(spec=type(models.Model))
    bar_model_class._meta = mock.MagicMock(spec=options.Options)

    single_value_field = mock.MagicMock(spec=related.ForeignKey)
    single_value_field.many_to_many = False
    single_value_field.one_to_many = False

    multi_value_field = mock.MagicMock(spec=related.ManyToManyField)
    multi_value_field.many_to_many = True
    multi_value_field.one_to_many = False

    return (starting_model_class, foo_model_class, bar_model_class,
            single_value_field, multi_value_field)


@pytest.fixture
def class_and_field_setup(classes_and_fields):
    (starting_model_class, foo_model_class, bar_model_class,
     single_value_field, multi_value_field) = classes_and_fields

    starting_model_class._meta.get_field.return_value = single_value_field
    single_value_field.model = foo_model_class
    foo_model_class._meta.get_field.return_value = multi_value_field
    multi_value_field.model = bar_model_class

    return (starting_model_class, foo_model_class, bar_model_class,
            single_value_field, multi_value_field)


@pytest.fixture
def single_relpath(class_and_field_setup):
    return RelPath(class_and_field_setup[0], 'foo')


@pytest.fixture
def multi_relpath(class_and_field_setup):
    return RelPath(class_and_field_setup[0], 'foo', 'bar')


def test_init_and_get_field_single(single_relpath, class_and_field_setup):
    (starting_model_class, foo_model_class, bar_model_class,
     single_value_field, multi_value_field) = class_and_field_setup

    starting_model_class._meta.get_field.assert_called_once_with('foo')

    assert single_relpath._names == ('foo',)
    assert single_relpath._model_classes == [foo_model_class]
    assert single_relpath._fields == [single_value_field]
    assert single_relpath._many_valued is False
    assert single_relpath.get_field() == single_value_field


def test_init_and_get_field_terminal_multi(multi_relpath,
                                           class_and_field_setup):
    (starting_model_class, foo_model_class, bar_model_class,
     single_value_field, multi_value_field) = class_and_field_setup

    starting_model_class._meta.get_field.assert_called_once_with('foo')
    foo_model_class._meta.get_field.assert_called_once_with('bar')

    assert multi_relpath._names == ('foo', 'bar')
    assert multi_relpath._model_classes == [foo_model_class, bar_model_class]
    assert multi_relpath._fields == [single_value_field, multi_value_field]
    assert multi_relpath._many_valued is True
    assert multi_relpath.get_field() == multi_value_field


def test_init_prefix_multi(classes_and_fields):
    (starting_model_class, foo_model_class, bar_model_class,
     single_value_field, multi_value_field) = classes_and_fields

    starting_model_class._meta.get_field.return_value = multi_value_field
    multi_value_field.model = foo_model_class
    foo_model_class._meta.get_field.return_value = single_value_field
    single_value_field.model = bar_model_class

    with pytest.raises(ValueError) as excinfo:
        RelPath(starting_model_class, 'foo', 'bar')

    assert ("Many-valued relations cannot appear before the end of the path" in
            unicode(excinfo.value))


def test_init_no_field_names():
    with pytest.raises(TypeError) as excinfo:
        RelPath(models.Model)
    assert "At least one field name is required" in unicode(excinfo.value)


@pytest.fixture
def instance():
    instance = mock.MagicMock()
    foo = mock.MagicMock()
    bar = mock.MagicMock()

    bar.all.return_value = mock.MagicMock(spec=models.QuerySet)
    foo.bar = bar
    instance.foo = foo
    return instance


@pytest.fixture
def single_isinstance_passes(single_relpath):
    # Make sure that the isinstance() check passes by setting the relevant
    # class to object.  _model_classes is not otherwise used by get/set_value()
    single_relpath._model_classes[0] = object
    return single_relpath


@pytest.fixture
def multi_isinstance_passes(multi_relpath):
    # Make sure that the isinstance() check passes by setting the relevant
    # class to object.  _model_classes is not otherwise used by get/set_value()
    multi_relpath._model_classes[0] = object
    return multi_relpath


def test_expand(multi_relpath, instance):
    values = multi_relpath._expand(instance)
    assert values == [instance.foo, instance.foo.bar]


def test_get_value_single(single_isinstance_passes, instance):
    value = single_isinstance_passes.get_value(instance)
    assert value == instance.foo


def test_get_value_single_empty(single_isinstance_passes, instance):
    # Also ensure that an instance of None works with empty=True
    value = single_isinstance_passes.get_value(None, empty=True)
    assert value is None


def test_get_value_multi(multi_isinstance_passes, instance):
    value = multi_isinstance_passes.get_value(instance)
    assert value == instance.foo.bar.all.return_value


def test_get_value_multi_empty(multi_isinstance_passes, instance):
    # For the empty multi-value, we get a queryset using only the
    # fields, in case there is actually no related object present
    # in the instance.
    empty_queryset = mock.MagicMock(spec=models.QuerySet)
    multi_isinstance_passes._fields[-1].rel.model.objects.none.return_value = \
        empty_queryset

    value = multi_isinstance_passes.get_value(instance, empty=True)
    assert value == empty_queryset


def test_get_value_instance_check(single_relpath, instance):
    # Need to make sure there is an actual type and not a mock object
    single_relpath._model_classes[0] = models.Model
    with pytest.raises(ValueError) as excinfo:
        single_relpath.get_value(instance)
    assert 'is not an instance of' in unicode(excinfo.value)


def test_set_value_single(single_isinstance_passes, instance):
    value = mock.MagicMock()
    with mock.patch('apps.oi.relpath.setattr') as setattr_mock:
        single_isinstance_passes.set_value(instance, value)
        setattr_mock.assert_called_once_with(instance, 'foo', value)


def test_set_value_multiple(multi_isinstance_passes, instance):
    value = [mock.MagicMock(), mock.MagicMock(), mock.MagicMock()]
    with mock.patch('apps.oi.relpath.setattr') as setattr_mock:
        multi_isinstance_passes.set_value(instance, value)
        setattr_mock.assert_called_once_with(instance.foo, 'bar', value)


def test_set_value_instance_check(multi_relpath, instance):
    # Need to make sure there is an actual type and not a mock object
    multi_relpath._model_classes[0] = models.Model
    with pytest.raises(ValueError) as excinfo:
        multi_relpath.set_value(instance, [1, 2, 3])
    assert 'is not an instance of' in unicode(excinfo.value)
