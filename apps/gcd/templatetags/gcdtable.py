from django import template

register = template.Library()


def finishrow(position, width):
    """For filling out the rest of a table row with '&nbsp;' characters
    to make bordered tables look nice in non-CSS-supporing browsers.
    There's no real way to do this without a while loop or some arithmetic
    operators, so it needs a custom tempate tag."""

    # position = int(position)
    # width = int(width)
    cells = ''
    while (position % width):
        cells += '<td>&nbsp;</td>'
        position += 1

    return cells

register.filter(finishrow)
