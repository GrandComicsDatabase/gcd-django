from django.conf import settings
from django.utils import translation
from django.utils.deprecation import MiddlewareMixin

LANGUAGE_SESSION_KEY = 'front_page_language'


class LocaleQueryMiddleware(MiddlewareMixin):
    """
    Activates the language of the request: the lang of the address, else
    the language of the start page the reader chose last, else English.
    """

    def process_request(self, request):
        """
        A lang of a start page (settings.FRONT_PAGE_LANGUAGES) is kept in
        the session, written only when it changes. Any other lang counts
        for this request only: the front page takes it to show the counts
        of that language.
        """
        chosen = request.session.get(LANGUAGE_SESSION_KEY, 'en')
        language = request.GET.get('lang', chosen)
        if language != chosen and language in settings.FRONT_PAGE_LANGUAGES:
            request.session[LANGUAGE_SESSION_KEY] = language
        translation.activate(language)
        request.LANGUAGE_CODE = translation.get_language()
