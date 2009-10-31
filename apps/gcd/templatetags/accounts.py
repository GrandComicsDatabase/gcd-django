from django.utils.safestring import mark_safe

from django import template

register = template.Library()

def can_view_profile_details(viewer, user):
    if (viewer is not None and viewer.is_authenticated() and
        (user == viewer or viewer.has_perm('gcd.can_mentor'))):
        return True
    return False

register.filter(can_view_profile_details)

