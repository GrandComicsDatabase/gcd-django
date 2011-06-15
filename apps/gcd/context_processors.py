from django.conf import settings
from apps.oi import states

def gcd(request):
    stuff = { 'states': states, 'site_name': settings.SITE_NAME, 
              'ICON_SET': settings.ICON_SET }

    if hasattr(settings, 'BETA'):
        stuff['BETA'] = settings.BETA
    return stuff

