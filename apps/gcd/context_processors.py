from django.conf import settings
from apps.oi import states

def gcd(request):
    stuff = { 'states': states }

    if hasattr(settings, 'BETA'):
        stuff['BETA'] = settings.BETA
    return stuff

