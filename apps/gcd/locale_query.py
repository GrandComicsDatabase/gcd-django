from django.utils import translation
from django.utils.deprecation import MiddlewareMixin

class LocaleQueryMiddleware(MiddlewareMixin):
    def process_request(self, request):
        if 'lang' in request.GET:
            translation.activate(request.GET['lang'])
        else:
            translation.activate('en')
        request.LANGUAGE_CODE = translation.get_language()
