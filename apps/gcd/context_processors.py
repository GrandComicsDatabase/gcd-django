from django.conf import settings
from apps.oi import states

def gcd(request):
    stuff = { 'states': states, 'site_name' : settings.SITE_NAME }

    if hasattr(settings, 'BETA'):
        stuff['BETA'] = settings.BETA
    return stuff

