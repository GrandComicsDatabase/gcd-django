from django.utils.safestring import mark_safe

import django_tables2 as tables

TW_COLUMN_ALIGN_RIGHT = 'px-2 sm:text-right text-left'


def render_publisher(value, addon=''):
    from apps.gcd.templatetags.display import absolute_url
    from apps.gcd.templatetags.credits import show_country_info
    display_publisher = "<img class='pe-1 inline' %s>" % (
        show_country_info(value.country))
    return mark_safe(display_publisher) + absolute_url(value) + mark_safe(addon)


class DailyChangesTable(tables.Table):
    change_history = tables.Column(accessor='id', orderable=False,
                                   verbose_name='Change History')

    def __init__(self, *args, **kwargs):
        data_source = None
        # Extract data source from args or kwargs before calling super
        if 'data' in kwargs:
            data_source = kwargs['data']
        elif args:
            # Assuming the first positional argument is the data source
            if len(args) > 0:
                data_source = args[0]
        if 'column_to_count' in kwargs:
            # Remove column_count from kwargs to avoid passing it to super
            name = kwargs['column_to_count']
            del kwargs['column_to_count']
        else:
            name = 'name'

        # Calculate count from the initial data source
        data_count = 0
        if data_source is not None:
            # Use count() method for querysets (if not already evaluated)
            if hasattr(data_source, 'count') and callable(data_source.count) \
               and not isinstance(data_source, (list, tuple)):
                data_count = data_source.count()
            # Use len() for lists, tuples, or evaluated querysets
            elif hasattr(data_source, '__len__'):
                data_count = len(data_source)

        super().__init__(*args, **kwargs)
        verbose_name = self.columns[name].verbose_name

        # Define the dynamic column to override the base 'name' column
        # We use at least two different types, now with a dynamic verbose_name
        if not hasattr(self.base_columns[name], 'template_name'):
            dynamic_name_column = tables.Column(
              verbose_name=f'{verbose_name} ({data_count})')
        else:
            dynamic_name_column = tables.TemplateColumn(
              accessor='id',
              verbose_name=f'{verbose_name} ({data_count})',
              template_name=self.base_columns[name].template_name,)
        dynamic_name_column.order = self.base_columns[name].order

        # Prepare extra_columns argument for super().__init__
        extra_columns = kwargs.get('extra_columns', [])
        # Ensure 'name' is replaced or added correctly
        found = False
        for i, (col_name, col_instance) in enumerate(extra_columns):
            if col_name == name:
                extra_columns[i] = (name, dynamic_name_column)
                found = True
                break
        if not found:
            extra_columns.append((name, dynamic_name_column))
        kwargs['extra_columns'] = extra_columns

        # Call super().__init__ with modified kwargs
        super().__init__(*args, **kwargs)

    def render_change_history(self, record):
        name_link = '<a href="%shistory">Change History</a>' % (
          record.get_absolute_url())
        return mark_safe(name_link)
