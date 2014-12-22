from django.conf import settings
from apps.oi import states
from apps.gcd.models.cover import ZOOM_SMALL, ZOOM_MEDIUM, ZOOM_LARGE

def gcd(request):
    stuff = { 'states': states, 'site_name': settings.SITE_NAME, 
              'ICON_SET': settings.ICON_SET,
              'ZOOM_SMALL': ZOOM_SMALL,
              'ZOOM_MEDIUM': ZOOM_MEDIUM,
              'ZOOM_LARGE': ZOOM_LARGE}

    if hasattr(settings, 'BETA'):
        stuff['BETA'] = settings.BETA
    if hasattr(settings, 'ADVERTISING'):
        stuff['ADVERTISING'] = settings.ADVERTISING
    if hasattr(settings, 'MYCOMICS'):
        stuff['MYCOMICS'] = settings.MYCOMICS
    return stuff

