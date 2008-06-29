from django.conf import settings
from django.shortcuts import render_to_response

from apps.gcd.models import Issue

# Maximum number of recently modified issues to display.
MAX = 6

def index(request):
    """Generates the front index page."""
    latest_updated_indexes = \
      Issue.objects.all().order_by('-modified', '-modification_time')[:MAX]
    vars = {
        'latest_updated_indexes' : latest_updated_indexes,
        'media_url' : settings.MEDIA_URL,
    }
    return render_to_response('index.html', vars)
      

def prototype(request, name):
    """Load a template (really a static page) for a UI prototype."""
    return render_to_response('new/' + name + '.html',
                              { 'media_url' : settings.MEDIA_URL })

