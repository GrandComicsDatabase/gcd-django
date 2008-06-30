"""View methods related to displaying search and search results pages."""

import re
from urllib import urlopen

from django.db.models import Q
from django.conf import settings
from django.shortcuts import render_to_response, \
                             get_object_or_404, \
                             get_list_or_404
from django.http import HttpResponseRedirect
from django.views.generic.list_detail import object_list

from apps.gcd.models import Publisher, Series, Issue, Story
from apps.gcd.views.diggpaginator import DiggPaginator

ORDER_ALPHA = "alpha"
ORDER_CHRONO = "chrono"

def generic_by_name(request, name, q_obj, sort,
                    class_name = Story,
                    template = 'default_search.html',
                    credit = None):
    """Helper function for the most common search cases."""

    if (class_name is Series):
        things = Series.objects.filter(q_obj)
        if (sort == ORDER_ALPHA):
            things = things.order_by("name")
        elif (sort == ORDER_CHRONO):
            things = things.order_by("year_began", "name")

    else:
        # NOTE:  ORDER BY on joined tables is a bit of a mess right now,
        # see Django bug #2076.  This works as of SVN revision 6980.
        # In particular, for some reason it insists on "bk_name" instead
        # of translating "name" for the series.  But it accepts the
        # other model names such as "year_began" in place of "yr_began".

        things = class_name.objects.filter(q_obj)
        # TODO: This order_by stuff only works for Stories, which is 
        # TODO: OK for now, but might not always be.
        if (sort == ORDER_ALPHA):
            # Hack to make the join table available for ORDER BY.
            # Calling order_by should do this, but does not.
            # No series with ID 0 in DB.
            things = things.filter(issue__series__id__gt = "0")
            things = things.order_by("stories__issue__series.bk_name",
                                     "stories__issue__series.year_began",
                                     "stories__issue.key_date",
                                     "sequence_number")
        elif (sort == ORDER_CHRONO):
            # Hack to make the join table available for ORDER BY.
            # Calling order_by should do this, but does not.
            # No issue with ID 0 in DB.
            things = things.filter(issue__id__gt = "0")
            things = things.order_by("stories__issue.key_date",
                                     "sequence_number")

    if 'page' in request.GET:
        pageno=request.GET['page']
    else:
        pageno=1    
    if 'entries_per_page' in request.session:
        entries = request.session['entries_per_page']
    else:
        entries = 50
    digg_paginator = DiggPaginator(things,entries,page=pageno, body=7)
    return object_list(request,things, paginate_by = entries, 
                       template_name = template,extra_context ={
                       'search_term' : name,
                       'media_url' : settings.MEDIA_URL, 
                       'digg_paginator' : digg_paginator,
                       'which_credit' : credit})

def publishers_by_name(request, publisher_name, sort=ORDER_ALPHA):
    """Finds publishers that (probably) aren't imprints."""

    pubs = Publisher.objects.filter(
      name__icontains = publisher_name, is_master = 1)
    if (sort == ORDER_ALPHA):
        pubs = pubs.order_by('name', 'year_began')
    elif (sort == ORDER_CHRONO):
        pubs = pubs.order_by('year_began', 'name')

    return render_to_response('publisher_list.html', {
      'publisher_set' : pubs,
      'publisher_count' : len(pubs),
      'media_url' : settings.MEDIA_URL })


def character_appearances(request, character_name, sort=ORDER_ALPHA):
    """Find stories based on characters.  Since characters for whom a feature
    is named are often not also listed under character appearances, this
    search looks at both the feature and characters fields."""

    q_obj = Q(characters__icontains = character_name) | \
            Q(feature__icontains = character_name)
    return generic_by_name(request, character_name, q_obj, sort)


def writer_by_name(request, writer, sort=ORDER_ALPHA):
    q_obj = Q(script__icontains = writer)
    return generic_by_name(request, writer, q_obj, sort, credit="script")


def penciller_by_name(request, penciller, sort=ORDER_ALPHA):
    q_obj = Q(pencils__icontains = penciller)
    return generic_by_name(request, penciller, q_obj, sort, credit="pencils")


def inker_by_name(request, inker, sort=ORDER_ALPHA):
    q_obj = Q(inks__icontains = inker)
    return generic_by_name(request, inker, q_obj, sort, credit="inks")


def colorist_by_name(request, colorist, sort=ORDER_ALPHA):
    q_obj = Q(colors__icontains = colorist)
    return generic_by_name(request, colorist, q_obj, sort, credit="colors")


def letterer_by_name(request, letterer, sort=ORDER_ALPHA):
    q_obj = Q(letters__icontains = letterer)
    return generic_by_name(request, letterer, q_obj, sort, credit="letters")


def editor_by_name(request, editor, sort=ORDER_ALPHA):
    q_obj = Q(editor__icontains = editor)
    return generic_by_name(request, editor, q_obj, sort, credit="editor")


def story_by_credit(request, name, sort=ORDER_ALPHA):
    """Implements the 'Any Credit' story search."""
    q_obj = Q(script__icontains = name) | \
            Q(pencils__icontains = name) | \
            Q(inks__icontains = name) | \
            Q(colors__icontains = name) | \
            Q(letters__icontains = name) | \
            Q(editor__icontains = name)
    return generic_by_name(request, name, q_obj, sort, credit=('any:'+name))


def story_by_job(request, number, sort=ORDER_ALPHA):
    q_obj = Q(job_number = number)
    return generic_by_name(request, number, q_obj, sort, credit="job")


def story_by_reprint(request, reprints, sort=ORDER_ALPHA):
    q_obj = Q(reprints__icontains = reprints)
    return generic_by_name(request, reprints, q_obj, sort)


def story_by_title(request, title, sort=ORDER_ALPHA):
    """Looks up story by story (not issue or series) title."""
    q_obj = Q(title__icontains = title)
    return generic_by_name(request, title, q_obj, sort)

def story_by_feature(request, feature, sort=ORDER_ALPHA):
    """Looks up story by feature."""
    q_obj = Q(feature__icontains = feature)
    return generic_by_name(request, feature, q_obj, sort)
    

def series_by_name(request, series_name, sort=ORDER_ALPHA):
    q_obj = Q(name__icontains = series_name)
    return generic_by_name(request, series_name, q_obj, sort,
                           Series, 'title_search.html')


def search(request):
    """Handle the form-style URL from the basic search form by mapping
    it into the by-name lookup URLs the system already knows how to handle."""

    return HttpResponseRedirect("/gcd/" + \
                                request.GET["type"] + \
                                "/name/" + \
                                request.GET["query"] + \
                                "/sort/" + \
                                request.GET["sort"] + \
                                "/")


def advanced_search(request):
    """Handler for advanced searches.  If no search is specified, this
    displayes the advanced search page.  Otherwise it runs the search.
    Currently, this is done by seing if the mandatory field 'target'
    is set, which tells us whether we're looking for stories or series."""

    if (not request.GET.has_key("target")):
        return render_to_response('advanced_search.html',
                                  { 'media_url' : settings.MEDIA_URL })

    if (request.GET["target"] == "stories"):
        return search_stories(request)
    else:
        return search_series(request)


def search_stories(request):
    """Implements advanced searches for stories.  Considerable code
    duplication with generic_by_name and search_series that should
    be refactored."""

    results = Story.objects.all()
    if (request.GET["series"] != ""):
        results = \
          results.filter(issue__series__name__icontains = request.GET["series"])

    if (request.GET["publisher"] != ""):
        results = results.filter(issue__series__publisher__name__icontains =
          request.GET["publisher"])

    if (request.GET["feature"] != ""):
        results = results.filter(feature__icontains = request.GET["feature"])

    if (request.GET["story"] != ""):
        results = results.filter(title__icontains = request.GET["story"])

    if (request.GET["character"] != ""):
        results = results.filter(
          Q(characters__icontains = request.GET["character"]) | \
          Q(feature__icontains = request.GET["character"]))

    if (request.GET["writer"] != ""):
        results = results.filter(script__icontains = request.GET["writer"])
    if (request.GET["penciller"] != ""):
        results = results.filter(pencils__icontains = request.GET["penciller"])
    if (request.GET["inker"] != ""):
        results = results.filter(inks__icontains = request.GET["inker"])
    if (request.GET["colorist"] != ""):
        results = results.filter(colors__icontains = request.GET["colorist"])
    if (request.GET["letterer"] != ""):
        results = results.filter(letters__icontains = request.GET["letterer"])
    if (request.GET["editor"] != ""):
        results = results.filter(editor__icontains = request.GET["editor"])

    # Hack to make the join table available for ORDER BY, in case no
    # query field forced the join already.
    # Calling order_by should do this, but does not.
    # No series with ID 0 in DB.
    # TODO: Only do this if needed.
    results = results.filter(issue__series__id__gt = "0")

    # NOTE:  ORDER BY on joined tables is a bit of a mess right now,
    # see Django bug #2076.  This works as of SVN revision 6980.
    # In particular, for some reason it insists on "bk_name" instead
    # of translating "name" for the series.  But it accepts the
    # other model names such as "year_began" in place of "yr_began".
    if (request.GET["sort"] == ORDER_ALPHA):
        results = results.order_by("stories__issue__series.bk_name",
                                   "stories__issue__series.year_began",
                                   "stories__issue.key_date",
                                   "sequence_number")
    elif (request.GET["sort"] == ORDER_CHRONO):
        results = results.order_by("stories__issue.key_date",
                                   "stories__issue__series.bk_name",
                                   "stories__issue.id",
                                   "sequence_number")

    # query_string is needed for links to prev/next page
    # page=<number> is always added by the template, so the '&' is fine
    # we get a copy of GET and make sure there is no page entry
    search_query = request.GET.copy()
    if 'page' in search_query:
        pageno = search_query['page']
        del search_query['page']
    else:
        pageno = 1    

    digg_paginator = DiggPaginator(results,50,page=pageno, body=7)

    return object_list(request, results, paginate_by = 50, 
      template_name = 'default_search.html',extra_context ={
      'search_term' : "[TODO: Stringify advanced queries]",
      'media_url' : settings.MEDIA_URL,
      'query_string' : search_query.urlencode()+'&',
      'digg_paginator' : digg_paginator})


def search_series(request):
    """Implements advanced searches for series.  Considerable code duplication
    with generic_by_name and search_stories that should be refactored."""

    # TODO: Overhaul this, as it really doesn't work for creator credits
    # TODO: (or features, or characters, or other story attributes)
    # TODO: at all.  It needs to search the story tables for those, and then
    # TODO: factor out the distinct series.  However, if no creator fields
    # TODO: are searched, then the lookup should be on Series directly.
    #
    # NOTE: Currently, story attribute fields are ignored, so this search
    # is of limited use at best.

    results = Series.objects.all()
    if (request.GET["series"] != ""):
        results = results.filter(name__icontains = request.GET["series"])

    if (request.GET["publisher"] != ""):
        results = results.filter(publisher__name__icontains =
                                 request.GET["publisher"])

    if (request.GET["sort"] == ORDER_ALPHA):
        results = results.order_by('name', 'year_began')
    elif (request.GET["sort"] == ORDER_CHRONO):
        results = results.order_by('year_began', 'name')

    # see search_stories
    search_query = request.GET.copy()
    if 'page' in search_query:
        pageno=search_query['page']
        del search_query['page']
    else:
        pageno=1    
    digg_paginator = DiggPaginator(results,50,page=pageno, body=7)
    return object_list(request,results, paginate_by = 50, 
      template_name = 'title_search.html',extra_context ={
      'search_term' : "[TODO: Stringify advanced queries]",
      'media_url' : settings.MEDIA_URL,
      'query_string' : search_query.urlencode()+'&',
      'digg_paginator' : digg_paginator})

