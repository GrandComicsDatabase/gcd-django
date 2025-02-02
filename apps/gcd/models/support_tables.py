from django.utils.safestring import mark_safe

TW_COLUMN_ALIGN_RIGHT = 'px-2 sm:text-right text-left'


def render_publisher(value, addon=''):
    from apps.gcd.templatetags.display import absolute_url
    from apps.gcd.templatetags.credits import show_country_info
    display_publisher = "<img class='pe-1 inline' %s>" % (
        show_country_info(value.country))
    return mark_safe(display_publisher) + absolute_url(value) + mark_safe(addon)
