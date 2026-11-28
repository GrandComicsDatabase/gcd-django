from django.conf import settings
from django.conf.locale import LANG_INFO
from django.utils import translation
from django.utils.deprecation import MiddlewareMixin


class LocaleQueryMiddleware(MiddlewareMixin):
    """Activate the language named by the lang query parameter."""

    def process_request(self, request):
        """Activate ?lang= if it is a known language code, else English.

        A known code is one of Django's languages or of
        settings.LANGUAGES. Any other value counts as no parameter.
        """
        language = request.GET.get('lang', 'en')
        if language not in LANG_INFO and \
           language not in dict(settings.LANGUAGES):
            language = 'en'
        translation.activate(language)
        request.LANGUAGE_CODE = translation.get_language()
