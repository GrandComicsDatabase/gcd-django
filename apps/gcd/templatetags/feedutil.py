# Based on http://code.google.com/p/django-feedutil/ by Douglas Napoleone
#
import facebook
from time import mktime
from datetime import datetime
from django import template
from django.conf import settings
from django.core.cache import cache
from django.template.defaultfilters import urlizetrunc, linebreaksbr, urlize
from django.utils.http import urlquote
from django.utils.safestring import mark_safe

def _getdefault(name, default=None):
    try:
        default = getattr(settings, name)
    except:
        pass
    return default

FEEDUTIL_NUM_POSTS = _getdefault('FEEDUTIL_NUM_POSTS', -1)
FEEDUTIL_CACHE_MIN = _getdefault('FEEDUTIL_CACHE_MIN', 30)
FEEDUTIL_SUMMARY_LEN = _getdefault('FEEDUTIL_SUMMARY_LEN', 150)
FEEDUTIL_SUMMARY_HTML_WORDS =  _getdefault('FEEDUTIL_SUMMARY_HTML_WORDS', 25)

register = template.Library()

def summarize(text):
    cleaned = template.defaultfilters.striptags(text)
    l = len(cleaned)
    if len(cleaned) > FEEDUTIL_SUMMARY_LEN:
        cleaned = cleaned[:FEEDUTIL_SUMMARY_LEN] + '...'
    return cleaned

def summarize_html(text):
    return template.defaultfilters.truncatewords_html(text,
                            FEEDUTIL_SUMMARY_HTML_WORDS) + ' ...'

def parse_comments(fb_comments):
    # if we want to add comments from Facebook:
    # a) add comments to fields in pull_feed
    # b) add 'comments':
    #    parse_comments(entry['comments']) if entry.has_key('comments') else ''
    #    to an entry in posts
    comments = ''
    for comment in fb_comments['data']:
        comments += comment['message'] + '<br>'
    return mark_safe(comments)

def pull_feed(feed_url, posts_to_show=None, cache_expires=None):
    if not hasattr(settings, 'FB_API_ACCESS_TOKEN'):
        return []
    if posts_to_show is None:
        posts_to_show = FEEDUTIL_NUM_POSTS
    if cache_expires is None:
        cache_expires = FEEDUTIL_CACHE_MIN
    cachename = 'feed_cache_' + template.defaultfilters.slugify(feed_url)
    posts = []
    data = None
    if cache_expires > 0:
        data = cache.get(cachename)
    if data is None:
        # load feed
        try:
            graph = facebook.GraphAPI(
              access_token=settings.FB_API_ACCESS_TOKEN, version='2.7')
            # we need to fetch more than posts_to_show posts since
            # non-birthday posts are filtered out
            json_posts = graph.request('/GrandComicsDatabase/posts',
              args={'fields': 'full_picture, link, message, application,'
                              ' created_time',
                    'limit': 4*posts_to_show})
            entries = list(json_posts.items())[1][1]
            if posts_to_show > 0 and len(entries) > posts_to_show:
                entries = entries[:4*posts_to_show]
            posts = [{
                'author': 'Grand Comics Database',
                'summary_html': summarize_html(entry['message']),
                'content': linebreaksbr(urlizetrunc(entry['message'], 75)),
                'mail_body': urlquote(entry['message']),
                'mail_subject': urlquote('From the %s' % settings.SITE_NAME),
                'url': entry['link'],
                'picture': entry['full_picture'],
                'published': entry['created_time']}
              for entry in entries if all (k in entry for k in ('message',
                                           'full_picture'))]
            # one used to get info about application via entry['application']
            # post['application']['name'] would filter those from hootsuite
            #
            # this is now restricted to admins / or site owner, and it is
            # not clear how to do that now via the API
            posts = posts[:posts_to_show]
        except:
            if settings.DEBUG:
                raise
            return []
        if cache_expires > 0:
            cache.set(cachename, posts, cache_expires*60)
    else:
        #load feed from cache
        posts = data

    return posts

@register.inclusion_tag('gcd/bits/calendar_feed.html', takes_context=True)
def feed(context, feed_url, posts_to_show=None, cache_expires=None):
    """
    Render an RSS/Atom feed using the 'gcd/bits/calendar_feed.html' template.

    ::
        {% feed feed_url [posts_to_show] [cache_expires] %}
        {% feed "https://foo.net/timeline?max=5&format=rss" 5 60 %}


    feed_url:      full url to the feed (required)
    posts_to_show: Number of posts to pull. <=0 for all
                   (default: settings.FEEDUTIL_NUM_POSTS or -1)
    cache_expired: Number of minuites for the cache. <=0 for no cache.
                   (default: settings.FEEDUTIL_CACHE_MIN or 30)

    """
    return {
      'posts': pull_feed(feed_url, posts_to_show, cache_expires),
    }

class GetFeedNode(template.Node):
    def __init__(self, var_name, feed_url, posts_to_show=None,
                 cache_expires=None):
        self.var_name = var_name
        self.feed_url = feed_url
        self.posts_to_show = posts_to_show
        self.cache_expires = cache_expires
    def render(self, context):
        posts_to_show = cache_expires = None
        try:
            feed_url = template.resolve_variable(self.feed_url, context)
        except:
            if settings.DEBUG:
                raise
            context[self.var_name] = []
            return ''
        if self.posts_to_show is not None:
            try:
                posts_to_show = template.resolve_variable(self.posts_to_show,
                                                          context)
            except template.VariableDoesNotExist:
                if settings.DEBUG:
                    raise
        if self.cache_expires is not None:
            try:
                cache_expires = template.resolve_variable(self.cache_expires,
                                                          context)
            except template.VariableDoesNotExist:
                if settings.DEBUG:
                    raise
        context[self.var_name] = pull_feed(feed_url,
                                           posts_to_show,
                                           cache_expires)
        return ''

@register.tag
def get_feed(parser, token):
    """
    Pull a RSS or Atom feed into the context as the supplied variable.

    ::
        {% get_feed feed_url [posts_to_show] [cache_expires] as var %}
        {% get_feed "https://foo.net/timeline?max=5&format=rss" 5 60 as myfeed %}

    feed_url:      full url to the feed (required)
    posts_to_show: Number of posts to pull. <=0 for all
                   (default: settings.FEEDUTIL_NUM_POSTS or -1)
    cache_expired: Number of minuites for the cache. <=0 for no cache.
                   (default: settings.FEEDUTIL_CACHE_MIN or 30)
    var:           Name of variable to set the feed to in the current context


    Format of var:

    ::

        [ { 'title': "A title" , 'summary': "The summary",
            'url': "http://foo.net/a-title",
            'published': datetime(10, 20, 2007) },
          ... ]


    """
    args = token.split_contents()
    args.pop(0)
    if len(args) < 3 or len(args) > 5 or args[-2] != 'as':
        raise template.TemplateSyntaxError("Malformed arguments to get_feed tag.")
    nargs = [args[-1]] + args[:-2]
    return GetFeedNode(*nargs)
