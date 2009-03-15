from django.conf import settings
from django.shortcuts import render_to_response
from django.core.urlresolvers import reverse

def index(request):
    """Generates the front index page."""

    style = 'default'
    if request.GET.has_key('style'):
        style = request.GET['style']

    print reverse('apps.inducks.views.index')
    vars = {
        'style' : style,
        'media_url' : settings.MEDIA_URL,
	'base_url' : reverse('apps.inducks.views.index')
    }
    return render_to_response('inducks/index.html', vars)
      
