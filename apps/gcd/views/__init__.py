from django.conf import settings
from django.shortcuts import render_to_response

def index(request):
    """Generates the front index page."""

    style = 'default'
    if request.GET.has_key('style'):
        style = request.GET['style']

    vars = {
        'style' : style,
        'media_url' : settings.MEDIA_URL,
    }
    return render_to_response('gcd/index.html', vars)
      

def prototype(request, name):
    """Load a template (really a static page) for a UI prototype."""
    return render_to_response('new/' + name + '.html',
                              { 'media_url' : settings.MEDIA_URL })

