from django.conf import settings
from django.utils import translation
from apps.oi import states

def gcd(request):
    stuff = { 'states': states, 'site_name': settings.SITE_NAME, 
              'ICON_SET': settings.ICON_SET,
              'ICON_SET_SYMBOLIC': settings.ICON_SET_SYMBOLIC}

    if hasattr(settings, 'BETA'):
        stuff['BETA'] = settings.BETA
    if hasattr(settings, 'FAKE_IMAGES'):
        stuff['FAKE_IMAGES'] = settings.FAKE_IMAGES
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
    stuff['page_language'] = page_language()
    return stuff


def page_language():
    """
    The language for the lang attribute of a page: the active language if
    it is one of the languages of the site (settings.LANGUAGES), otherwise
    English. The front page takes any language in its address, to show the
    counts of that language on a page in English.
    """
    try:
        return translation.get_supported_language_variant(
          translation.get_language())
    except LookupError:
        return 'en'
