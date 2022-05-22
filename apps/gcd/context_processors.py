from django.conf import settings
from apps.oi import states

def gcd(request):
    stuff = { 'states': states, 'site_name': settings.SITE_NAME, 
              'ICON_SET': settings.ICON_SET,
              'ICON_SET_SYMBOLIC': settings.ICON_SET_SYMBOLIC}

    if hasattr(settings, 'BETA'):
        stuff['BETA'] = settings.BETA
    if hasattr(settings, 'ADVERTISING'):
        stuff['ADVERTISING'] = settings.ADVERTISING
    if hasattr(settings, 'MYCOMICS'):
        stuff['MYCOMICS'] = settings.MYCOMICS
    if hasattr(settings, 'USE_ELASTICSEARCH'):
        stuff['USE_ELASTICSEARCH'] = settings.USE_ELASTICSEARCH
    if hasattr(settings, 'USE_TEMPLATESADMIN'):
        stuff['USE_TEMPLATESADMIN'] = settings.USE_TEMPLATESADMIN
    if not hasattr(stuff, 'EDITING'):
        stuff['EDITING'] = False
    return stuff

