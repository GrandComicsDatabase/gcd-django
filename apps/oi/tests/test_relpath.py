# -*- coding: utf-8 -*-


import mock
import pytest

from django.db import models
from django.db.models import options, fields
from django.db.models.fields import related

from apps.oi.relpath import RelPath


@pytest.fixture
def classes_and_fields():

    # The 'objects' class member is some sort of weird magic thing
    # in Django, so when using MagicMock(spec=type(models.Model))
    # the mock library thinks it violates the spec.  Add on a data
    # member here and use this subclass as the spec so that the
    # mock spec code stops freaking out.
    class FakeObjectsModelType(type(models.Model)):
        objects = mock.MagicMock()

    starting_model_class = mock.MagicMock(spec=FakeObjectsModelType)
    starting_model_class._meta = mock.MagicMock(spec=options.Options)

    foo_model_class = mock.MagicMock(spec=FakeObjectsModelType)
    foo_model_class._meta = mock.MagicMock(spec=options.Options)

    bar_model_class = mock.MagicMock(spec=FakeObjectsModelType)
    bar_model_class._meta = mock.MagicMock(spec=options.Options)

    single_value_field = mock.MagicMock(spec=related.ForeignKey)
    single_value_field.many_to_many = False
    single_value_field.one_to_many = False

    multi_value_field = mock.MagicMock(spec=related.ManyToManyField)
    multi_value_field.many_to_many = True
    multi_value_field.one_to_many = False

    non_relational_field = mock.MagicMock(spec=fields.Field)
    non_relational_field.one_to_one = None
    non_relational_field.one_to_many = None
    non_relational_field.many_to_many = None
    non_relational_field.many_to_one = None

    return (starting_model_class, foo_model_class, bar_model_class,
            single_value_field, multi_value_field, non_relational_field)


@pytest.fixture
def class_and_field_setup(classes_and_fields):
    (
        starting_model_class, foo_model_class, bar_model_class,
        single_value_field, multi_value_field, non_relational_field,
    ) = classes_and_fields

    starting_model_class._meta.get_field.return_value = single_value_field
    single_value_field.rel.model = foo_model_class
    foo_model_class._meta.get_field.return_value = multi_value_field
    multi_value_field.rel.model = bar_model_class

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
    assert single_relpath._first_model_class == starting_model_class
    assert single_relpath._model_classes == [foo_model_class]
    assert single_relpath._fields == [single_value_field]
    assert single_relpath.multi_valued is False
    assert single_relpath.boolean_valued is False
    assert single_relpath.get_field() == single_value_field
    assert single_relpath.get_empty_value() is None


def test_init_and_get_field_terminal_multi(multi_relpath,
                                           class_and_field_setup):
    (starting_model_class, foo_model_class, bar_model_class,
     single_value_field, multi_value_field) = class_and_field_setup

    starting_model_class._meta.get_field.assert_called_once_with('foo')
    foo_model_class._meta.get_field.assert_called_once_with('bar')

    assert multi_relpath._names == ('foo', 'bar')
    assert multi_relpath._first_model_class == starting_model_class
    assert multi_relpath._model_classes == [foo_model_class, bar_model_class]
    assert multi_relpath._fields == [single_value_field, multi_value_field]
    assert multi_relpath.multi_valued is True
    assert multi_relpath.boolean_valued is False
    assert multi_relpath.get_field() == multi_value_field
    assert len(multi_relpath.get_empty_value()) == 0


def test_init_prefix_multi(classes_and_fields):
    (
        starting_model_class, foo_model_class, bar_model_class,
        single_value_field, multi_value_field, non_relational_field,
    ) = classes_and_fields

    starting_model_class._meta.get_field.return_value = multi_value_field
    multi_value_field.rel.model = foo_model_class
    foo_model_class._meta.get_field.return_value = single_value_field
    single_value_field.rel.model = bar_model_class

    with pytest.raises(ValueError) as excinfo:
        RelPath(starting_model_class, 'foo', 'bar')

    assert ("Many-valued relations cannot appear before the end of the path" in
            str(excinfo.value))


def test_init_non_rel(classes_and_fields):
    (
        starting_model_class, foo_model_class, bar_model_class,
        single_value_field, multi_value_field, non_relational_field,
    ) = classes_and_fields

    starting_model_class._meta.get_field.return_value = non_relational_field

    nonrel_relpath = RelPath(starting_model_class, 'nonrel')

    assert nonrel_relpath._names == ('nonrel',)
    assert nonrel_relpath._first_model_class == starting_model_class
    assert nonrel_relpath._model_classes == []
    assert nonrel_relpath._fields == [non_relational_field]
    assert nonrel_relpath._multi_valued is False
    assert nonrel_relpath.get_field() == non_relational_field


def test_init_prefix_non_rel(classes_and_fields):
    (
        starting_model_class, foo_model_class, bar_model_class,
        single_value_field, multi_value_field, non_relational_field,
    ) = classes_and_fields

    starting_model_class._meta.get_field.return_value = non_relational_field

    with pytest.raises(ValueError) as excinfo:
        RelPath(starting_model_class, 'nonrel', 'doesntmatter')

    assert "non-relational field" in str(excinfo.value)


def test_init_no_field_names():
    with pytest.raises(TypeError) as excinfo:
        RelPath(models.Model)
    assert "At least one field name is required" in str(excinfo.value)


def test_empty_with_field(single_relpath, multi_relpath,
                          class_and_field_setup):
    (starting_model_class, foo_model_class, bar_model_class,
     single_value_field, multi_value_field) = class_and_field_setup

    assert single_relpath.get_empty_value(field=single_value_field) is None
    assert len(single_relpath.get_empty_value(field=multi_value_field)) == 0
    assert multi_relpath.get_empty_value(field=single_value_field) is None
    assert len(multi_relpath.get_empty_value(field=multi_value_field)) == 0


@pytest.mark.parametrize('field', ['BooleanField', 'NullBooleanField'])
def test_boolean_field(field, class_and_field_setup):
    (starting_model_class, foo_model_class, bar_model_class,
     single_value_field, multi_value_field) = class_and_field_setup

    with mock.patch('apps.oi.relpath.RelPath.get_field') as get_field_mock:
        get_field_mock.return_value.get_internal_type.return_value = field
        rp = RelPath(starting_model_class, 'foo')
        assert rp.boolean_valued is True


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
    single_relpath._first_model_class = object
    return single_relpath


@pytest.fixture
def multi_isinstance_passes(multi_relpath):
    # Make sure that the isinstance() check passes by setting the relevant
    # class to object.  _model_classes is not otherwise used by get/set_value()
    multi_relpath._first_model_class = object
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


def test_get_value_all_none_or_empty(multi_isinstance_passes):
    # In this case, we want to get a proper empty value on an existing
    # instance, even if the value of the first field in the chain is None,
    # and we don't know in advance to ask for an empty value.
    #
    # The intermediate field results are not accessible in the public interface
    # so we don't check them specifically, just the final value.
    empty_queryset = mock.MagicMock(spec=models.QuerySet)
    stored_last_field = multi_isinstance_passes.get_field()
    stored_last_field.rel.model.objects.none \
                     .return_value.all.return_value = empty_queryset

    value = multi_isinstance_passes.get_value(None)
    assert value == empty_queryset


def test_get_value_instance_check(single_relpath, instance):
    # Need to make sure there is an actual type and not a mock object
    single_relpath._first_model_class = models.Model
    with pytest.raises(ValueError) as excinfo:
        single_relpath.get_value(instance)
    assert 'is not an instance of' in str(excinfo.value)


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
    multi_relpath._first_model_class = models.Model
    with pytest.raises(ValueError) as excinfo:
        multi_relpath.set_value(instance, [1, 2, 3])
    assert 'is not an instance of' in str(excinfo.value)
