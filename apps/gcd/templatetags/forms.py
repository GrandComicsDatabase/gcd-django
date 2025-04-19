from django.utils.safestring import mark_safe

from django import template

register = template.Library()


def show_form(field):
    """
    For showing form fields for credits and similar fields as list items
    on a per-field bases instead of the whole-form approach of the standard
    list display methods.
    """
    return mark_safe('<li class="my-1">%s%s%s</li>' %
                     (field.label_tag(attrs={'class':
                      'me-2 w-36 sm:w-24 lg:w-44 text-right inline-block'}),
                      field, field.errors))


def show_form_as_row(field):
    """
    For showing form fields as table rows on a per-field basis instead
    of the whole-form approach of the standard as_table method.
    """
    last_row_tag = '<tr>'

    label_cell = '<th class="lg:w-64 text-right pe-2">%s</th>' % \
                 field.label_tag()
    value_cell = '<td>%s</td>' % field

    main_row_tag = '<tr>'
    if not field.help_text and not field.errors:
        main_row_tag = last_row_tag
    rows = '%s%s%s</tr>' % (main_row_tag, label_cell, value_cell)

    if field.help_text:
        help_row_tag = '<tr>'
        if not field.errors:
            help_row_tag = last_row_tag
        help_row = ('%s<td></td><td>%s</td></tr>' %
                    (help_row_tag, field.help_text))
        rows += help_row
    if field.errors:
        error_row = ('%s<td></td><td>%s</td></tr>' %
                     (last_row_tag, field.errors))
        rows += error_row

    return mark_safe(rows)


register.filter(show_form)
register.filter(show_form_as_row)
