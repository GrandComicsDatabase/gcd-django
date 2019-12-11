# -*- coding: utf-8 -*-



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
        for i in range(0, len(self._names)):
            field = cls._meta.get_field(self._names[i])
            if i != last_i and (field.many_to_many or field.one_to_many):
                # Supporting internal multi-valued fields would get us into
                # wierd set-of-sets (and set-of-set-of-sets, etc.) situations
                # that we don't currently need anyway.
                raise ValueError("Many-valued relations cannot appear before "
                                 "the end of the path")

            self._fields.append(field)
            if any((field.one_to_one, field.one_to_many,
                    field.many_to_many, field.many_to_one)):
                cls = field.rel.model
                self._model_classes.append(cls)
            elif i != last_i:
                # We have further to go, but can't because the current
                # field does not represent a relation.  This is an error.
                raise ValueError("Only the last element of the path may be "
                                 "a non-relational field")

        last = self._fields[-1]
        self._multi_valued = bool(last.many_to_many or last.one_to_many)

    @property
    def multi_valued(self):
        return self._multi_valued

    @property
    def boolean_valued(self):
        return self.get_field().get_internal_type() in ('BooleanField',
                                                        'NullBooleanField')

    def get_empty_value(self, field=None):
        if field is None:
            field = self._fields[-1]
        if field.many_to_many or field.one_to_many:
            return field.rel.model.objects.none()
        return None

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
        object, we will not be able to determine add/delete from the instance,
        so the caller needs to tell us to treat it as empty.

        For a simple instance of None or intermediate field values of None,
        we will get the correct result whether empty is True or False.

        A single-valued relation will result in a single value returned,
        while a multi-valued relation will result in a queryset.
        """
        if empty:
            return self.get_empty_value()

        # Check after the check for empty, because if we are empty we may
        # have None for the instance, and we won't use the instance anyway.
        if not isinstance(instance, self._first_model_class):
            raise ValueError("'%s' is not an instance of '%s'" %
                             (instance, self._first_model_class))

        values = self._expand(instance)
        if self._multi_valued:
            return values[-1].all()
        return values[-1]

    def set_value(self, instance, value):
        """
        Updates the value pointed to by this path on the given instance.

        This handles both single- and multi-valued relations.  In the case
        of a multi-valued relation, value can be a QuerySet or other iterable
        """
        if not isinstance(instance, self._first_model_class):
            raise ValueError("'%s' is not an instance of '%s'" %
                             (instance, self._first_model_class))
        # We want to change the final value.  So do that by applying
        # the final name to the next-to-last value with setattr.
        # If there is only one name/field/value, the "second to last value"
        # is the instance itself.
        #
        # As of Django 1.9, assigning to a many-to-many relation is the
        # same as using the set() method to update the relation.
        values = self._expand(instance)
        values.insert(0, instance)

        # We want values[-2] as the object on which we set the attribute.
        # values[-1] is the value that we are replacing, and is named
        # by self._names[-1].  Insering the instance at the beginning of the
        # values list returned from _expand() ensures that there is always
        # an existing values[-2]
        setattr(values[-2], self._names[-1], value)

    def _expand(self, instance):
        """
        Produces a list of values matching self._names for the instance.

        The returned values list has the following property:

        values[i] == getattr(values[i-1], self._names[i])

        with the passed in instance serving as values[0-1].
        """
        current_object = instance
        values = []
        for name, i in zip(self._names, range(0, len(self._names))):
            try:
                current_object = getattr(current_object, name)
                values.append(current_object)
            except AttributeError:
                values.append(self.get_empty_value(field=self._fields[i]))
        return values

    def __str__(self):
        return '%s.%s' % (self._first_model_class.__name__,
                          '.'.join(self._names))

    def __repr__(self):
        return '<RelPath: %s>' % self
