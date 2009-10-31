from django.conf import settings

def beta(request):
    if hasattr(settings, 'BETA'):
        return { 'BETA': settings.BETA }
    return { 'BETA': False }

