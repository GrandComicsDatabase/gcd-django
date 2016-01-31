# -*- coding: utf-8 -*-
from __future__ import unicode_literals


class RelPath(object):
    """
    Represents a sequence of model attributes to access related fields/objects.

    Successivly applying each attribute to an instance will result in a
    related object.  i.e. applying ('series', 'publisher') to an issue
    will result in issue_instance.series.publisher, which is an instance
    of class Publisher.

    Successivly applying each attribute to a class with get_field will
    result in the field implementing the last step of the relation.
    i.e. applying ('series', 'publisher') to the class Issue will result
    in the Series.publisher ForeignKey object, an instance of Field.

    When applying an attribute for a many-to-many or one-to-many field
    to an instance, multiple values will be returned for each object
    in the many-to-many relation.  See apply_for_value for details.
    """

    def __init__(self, model_class, *path_field_names):
        if not path_field_names:
            raise TypeError("At least one field name is required")

        self._names = path_field_names
        """ The field names in the path. """

        self._fields = []
        """ _fields[i] is the field corresponding to _names[i] """

        self._first_model_class = model_class
        """ The model class that is the starting point for the path. """

        self._model_classes = []
        """ _model_classes[i] is the target model of _fields[i] """

        cls = self._first_model_class
        last_i = len(self._names) - 1
        for i in xrange(0, len(self._names)):
            field = cls._meta.get_field(self._names[i])
            if i != last_i and (field.many_to_many or field.one_to_many):
                # Supporting internal many-valued fields would get us into
                # weird set-of-sets (and set-of-set-of-sets, etc.) situations
                # that we don't currently need anyway.
                raise ValueError("Many-valued relations cannot appear before "
                                 "the end of the path")
            cls = field.model
            self._fields.append(field)
            self._model_classes.append(cls)

        last = self._fields[-1]
        self._many_valued = last.many_to_many or last.one_to_many

    def get_field(self):
        """
        Returns the field object for the last relation in the sequence.

        In the ('series', 'publisher') example for Issue, this would
        be the publisher ForeignKey field on the Series class.
        For ('brand', 'group') on Issue, it would be the group
        ManyToManyField on the Brand class.
        """
        return self._fields[-1]

    def get_value(self, instance, empty=False):
        """
        Returns the value of the relation pointed to by the path.

        If empty is true, just return the appropriate empty value even
        if the instance has values.  This is used to handle newly added
        and deleted instances.  If we are using this RelPath with a data
        object, we will not be able to determine add/delete from the instance.

        A single-valued relation will result in a single value returned,
        while a many-valued relation will result in a queryset.
        """
        if not isinstance(instance, self._model_classes[0]):
            raise ValueError("'%s' is not an instance of '%s'" %
                             (instance, self._model_class))
        if empty:
            if self._many_valued:
                return self._fields[-1].rel.model.objects.none()
            return None

        values = self._expand(instance)
        if self._many_valued:
            return values[-1].all()
        return values[-1]

    def _expand(self, instance):
        """
        Produces a list of values matching self._names for the instance.

        The returned values list has the following property:

        values[i] == getattr(values[i-1], self._names[i])

        with the passed in instance serving as values[0-1].
        """
        current_object = instance
        values = []
        for name in self._names:
            current_object = getattr(current_object, name)
            values.append(current_object)
        return values
