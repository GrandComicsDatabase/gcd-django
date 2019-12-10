from django.conf import settings
from django.shortcuts import render_to_response
from django.core.urlresolvers import reverse

def index(request):
    """Generates the front index page."""

    style = 'default'
    if 'style' in request.GET:
        style = request.GET['style']

    print(reverse('apps.inducks.views.index'))
    vars = {
        'style' : style,
        'base_url' : reverse('apps.inducks.views.index')
    }
    return render_to_response('inducks/index.html', vars)
      
