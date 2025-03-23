# -*- coding: utf-8 -*-
import icu

import markdown as md

from django import template
from django.conf import settings
from django.template.defaultfilters import stringfilter
from django.utils.translation import gettext as _
from django.utils.translation import ngettext
from django.utils.safestring import mark_safe
from django.utils.html import conditional_escape as esc
import django.urls as urlresolvers

from apps.stddata.models import Country, Language
from apps.gcd.models.story import AD_TYPES, Story
from apps.gcd.models.support import GENRES
from apps.gcd.models import STORY_TYPES, CREDIT_TYPES

register = template.Library()


def sc_in_brackets(reprints, bracket_begin, bracket_end, sc_pos):
    begin = reprints.find(bracket_begin)
    end = reprints.find(bracket_end)
    if sc_pos in range(begin, end):
        sc_pos = reprints[end:].find(';')
        if sc_pos > -1:
            return end + sc_pos
        else:
            return -1
    else:
        return sc_pos


@register.filter
def split_reprint_string(reprints):
    '''
    split the reprint string
    need our own routine to take care of the ';' in publisher names and notes
    '''
    liste = []
    sc_pos = reprints.find(';')
    while sc_pos > -1:
        sc_pos = sc_in_brackets(reprints, '(', ')', sc_pos)
        sc_pos = sc_in_brackets(reprints, '[', ']', sc_pos)
        if sc_pos > -1:
            liste.append(reprints[:sc_pos].strip())
            reprints = reprints[sc_pos+1:]
            sc_pos = reprints.find(';')
    liste.append(reprints.strip())
    return liste


def find_credit_search(credit, target, collator):
    if settings.USE_ELASTICSEARCH:
        result = 1
        for string in target.split(' '):
            if string:
                search = icu.StringSearch(string.lower(),
                                          credit, collator)
                result = min(result, search.first())
        return result
    else:
        search = icu.StringSearch(target.lower(),
                                  credit,
                                  collator)
        return search.first()


@register.filter
def show_award_list(awards):
    display_awards = ''
    for award in awards:
        display_awards += '<li>' + esc(award.full_name_with_link()) + '</li>'
    return mark_safe(display_awards)


@register.filter
def show_credit(story, credit, tailwind=False, bare_value=False):
    """
    For showing the credits on the search results page.
    As far as I can tell Django template filters can only take
    one argument, hence the icky splitting of 'credit'.  Suggestions
    on a better way welcome, as clearly I'm abusing the Django filter
    convention here.
    """
    if not story:
        return ""

    if credit.startswith('any:'):
        collator = icu.Collator.createInstance()
        collator.setStrength(0)  # so that umlaut/accent behave as in MySql
        target = credit[4:]
        credit_string = ''
        for c in ['script', 'pencils', 'inks', 'colors', 'letters', 'editing']:
            story_credit = getattr(story, c).lower()
            if getattr(story, 'matched_credits', None):
                # results are from using elasticsearch
                if c in story.matched_credits:
                    credit_string += ' ' + __format_credit(story, c,
                                                           tailwind=tailwind)
                    if tailwind:
                        credit_string += '<br>'
                    if credit_string == ' ':
                        credit_string = __format_credit(story.issue, c,
                                                        tailwind=tailwind)\
                                        .replace('Editing', 'Issue Editing')
            elif story_credit:
                result = find_credit_search(story_credit, target, collator)
                if result != -1:
                    credit_string += ' ' + __format_credit(story, c,
                                                           tailwind=tailwind)
                    if tailwind:
                        credit_string += '<br>'
        if not getattr(story, 'matched_credits', None) and story.issue.editing:
            result = find_credit_search(story.issue.editing.lower(), target,
                                        collator)
            if result != -1:
                credit_string += __format_credit(story.issue, 'editing',
                                                 tailwind=tailwind)\
                                 .replace('Editing', 'Issue Editing')
        if credit_string and tailwind:
            credit_string = credit_string[:-4]
        return credit_string

    elif credit.startswith('editing_search:'):
        collator = icu.Collator.createInstance()
        collator.setStrength(0)
        target = credit[15:]
        formatted_credit = ""
        formatted_credit = __format_credit(story, 'editing',
                                           tailwind=tailwind).replace(
                                             'Editing', 'Story Editing')
        if formatted_credit and tailwind:
            formatted_credit += '<br>'
        formatted_credit += __format_credit(story.issue,
                                            'editing',
                                            tailwind=tailwind).replace(
                                              'Editing', 'Issue Editing')
        if formatted_credit.endswith('<br>'):
            formatted_credit = formatted_credit[:-4]
        return formatted_credit

    elif credit.startswith('characters:'):
        collator = icu.Collator.createInstance()
        collator.setStrength(0)
        target = credit[len('characters:'):]
        formatted_credit = ""
        if getattr(story, 'matched_credits', None):
            # results are from using elasticsearch
            for c in ['characters', 'feature']:
                if c in story.matched_credits:
                    formatted_credit += ' ' + __format_credit(
                      story, c, tailwind=tailwind)
                    if tailwind:
                        formatted_credit += '<br>'
            if formatted_credit.endswith('<br>'):
                formatted_credit = formatted_credit[:-4]
        else:
            if story.characters or story.appearing_characters.count():
                character_string = story.show_characters_as_text()
                search = icu.StringSearch(target.lower(),
                                          character_string.lower(),
                                          collator)
                if search.first() != -1:
                    formatted_credit = __format_credit(story, 'characters',
                                                       character_string,
                                                       tailwind=tailwind)

            if story.feature or story.feature_object.count():
                feature_string = story.show_feature_as_text()
                search = icu.StringSearch(target.lower(),
                                          feature_string.lower(),
                                          collator)
                if search.first() != -1:
                    formatted_credit += __format_credit(story, 'feature',
                                                        feature_string,
                                                        tailwind=tailwind)
        return formatted_credit
    elif credit == 'genre':
        genres = story.genre.lower()
        for feature in story.feature_object.all():
            for genre in feature.genre.split(';'):
                genre = genre.strip()
                if genre not in genres:
                    if genres == '':
                        genres = genre
                    else:
                        genres += '; %s' % genre
        if genres and getattr(story, 'issue', None):
            language = story.issue.series.language.code
            if language == 'en' and story.issue.series.country.code != 'us':
                genres = genres.replace('humor', 'humour')
                genres = genres.replace('sports', 'sport')
                genres = genres.replace('math & science', 'maths & science')
            if language == 'en' or story.issue.series.language.code \
                           not in GENRES:
                display_genre = genres.replace('fantasy',
                                               'fantasy-supernatural')
            else:
                display_genre = ''
                for genre in genres.split(';'):
                    genre = genre.strip()
                    if genre in GENRES['en']:
                        translation = GENRES[language][
                                             GENRES['en'].index(genre)]
                    else:
                        translation = ''
                    if translation:
                        display_genre += '%s (%s); ' % (translation, genre)
                    else:
                        display_genre += genre + '; '
                display_genre = display_genre.replace('(fantasy)',
                                                      '(fantasy-supernatural)')
                display_genre = display_genre[:-2]
        else:
            display_genre = genres
        story.genre = display_genre
        return __format_credit(story, credit, tailwind=tailwind)
    elif credit == 'pages':
        if story.page_began:
            if story.page_ended:
                story.pages = "%s - %s" % (story.page_began, story.page_ended)
            else:
                story.pages = story.page_began
            return __format_credit(story, credit, tailwind=tailwind)
        return ""
    elif credit == 'show_awards':
        if story.active_awards().count():
            display_award = '<ul>%s</ul>' % show_award_list(story
                                                            .active_awards())
            story.show_awards = mark_safe(display_award)
            return __format_credit(story, credit, bare_value=bare_value)
        else:
            return ""
    elif hasattr(story, credit):
        return __format_credit(story, credit, tailwind=tailwind,
                               bare_value=bare_value)
    else:
        return ""


@register.filter
def show_credit_tw_inline(story, credit):
    return show_credit(story, credit, tailwind=True)


@register.filter
def show_credit_bare_value(story, credit):
    value = show_credit(story, credit, bare_value=True)
    if value:
        return mark_safe(value[1][4:-5])
    else:
        return ''


@register.filter
def show_credit_description_list(story, credit):
    try:
        label, value = show_credit(story, credit, bare_value=True)
    except ValueError as e:
        if str(e) != 'not enough values to unpack (expected 2, got 0)':
            raise
        else:
            return ''
    return mark_safe('<dt class="field-name-label">' + label +
                     ':</dt><dd>' + value + '</dd>')


def __credit_visible(value):
    """
    Check if credit exists and if we want to show it.
    This used to be a bit more complicated but it's very simple now.
    """
    return value is not None and value != ''


def __label(story, field):
    if field == 'job_number':
        return _('Job Number')
    elif field == 'first_line':
        return _('First Line of Dialogue or Text')
    elif field == 'doi':
        return 'DOI'
    elif field == 'show_awards':
        return 'Awards'
    if (field in ['reprint_notes', 'reprint_original_notes']):
        return _('Reprinted')
    else:
        return _(field.title())


def __format_credit(story, credit, computed_value='', tailwind=False,
                    bare_value=False):
    if bare_value and tailwind:
        raise ValueError('Cannot have both bare_value and tailwind')
    label = __label(story, credit)
    if credit in ['script', 'pencils', 'inks', 'colors', 'letters', 'editing']:
        credit_value = __credit_value(story, credit, url=True)
    elif credit in ['characters', 'feature']:
        credit_value = computed_value
    else:
        credit_value = getattr(story, credit)
    if credit == 'feature':
        credit_value = story.show_feature()
    if credit == 'characters':
        credit_value = story.show_characters(css_style=False)
    if not __credit_visible(credit_value):
        return ''

    if (credit in ['reprint_notes', 'reprint_original_notes']):
        values = split_reprint_string(credit_value)
        credit_value = '<ul>'
        for value in values:
            credit_value += '<li>' + esc(value)
        credit_value += '</ul>'
    elif credit == 'keywords':
        model_name = story._meta.model_name
        if model_name == 'issue' and story.series.is_singleton:
            keywords = story.keywords.all() | story.series.keywords.all()
        else:
            keywords = story.keywords
        credit_value = __format_keywords(keywords,
                                         model_name=model_name)
        if credit_value == '':
            return ''
    elif credit == 'feature_logo':
        credit_value = esc(story.show_feature_logo())
        if credit_value == '':
            return ''
    else:  # This takes care of escaping the database entries we display
        credit_value = esc(credit_value)
    if tailwind:
        return mark_safe('<span class="field-name-label">' + label +
                         ':</span>' + credit_value)
    elif bare_value:
        return label, credit_value
    else:
        dt = '<dt class="credit_tag'
        dd = '<dd class="credit_def'
        if credit in ['genre', 'job_number', 'feature_logo']:
            dt += ' short'
            dd += ' short'
        dt += '">'
        dd += '">'

        return mark_safe(
            dt + '<span class="credit_label">' + label + '</span></dt>' +
            dd + '<span class="credit_value">' + credit_value + '</span></dd>')


@register.filter
def search_creator_credit(story, credit_type):
    credits = story.active_credits.filter(
              credit_type_id=CREDIT_TYPES[credit_type])
    if not credits:
        return ''
    credit_value = '%s' % credits[0].creator.display_credit(credits[0],
                                                            search=True)

    for credit in credits[1:]:
        credit_value = '%s; %s' % (credit_value,
                                   credit.creator.display_credit(credit,
                                                                 search=True))

    return mark_safe(credit_value)


def __credit_value(story, credit_type, url, show_sources=False, use_div=False):
    # We use .credits.all() to allow prefetching of the credits when the
    # story is fetched from the db, otherwise the filter would invalidated
    # the prefetched data. Prefetching is done by
    # - issue.shown_stories for show_issue
    # - the name-value export script
    #
    # For results from elasticsearch we need to go to the object.
    if '_object' in story.__dict__:
        credits = story.objects.credits.all()
    else:
        credits = story.credits.all()
    credit_value = ''
    for credit in credits:
        if credit.credit_type_id == CREDIT_TYPES[credit_type] and \
           not credit.deleted:
            displayed_credit = credit.creator.display_credit(
              credit, url=url, show_sources=show_sources)
            if use_div:
                credit_value += '<div>' + displayed_credit + '</div>'
            elif credit_value:
                credit_value += '; %s' % displayed_credit
            else:
                credit_value = displayed_credit
    old_credit_field = getattr(story, credit_type)
    if old_credit_field:
        if use_div:
            old_credits = ''
            for old_credit in old_credit_field.split(';'):
                old_credits += '<div>' + esc(old_credit) + '</div>'
            credit_value = '%s%s' % (credit_value, mark_safe(old_credits))
        elif credit_value:
            credit_value = '%s; %s' % (credit_value, esc(old_credit_field))
        else:
            credit_value = esc(old_credit_field)
    return mark_safe(credit_value)


@register.simple_tag
def show_full_credits(story, credit_type, show_sources):
    return show_creator_credit(story, credit_type,
                               show_sources=show_sources)


@register.simple_tag(takes_context=True)
def show_bare_creator_credits(context, story, credit_type, show_sources=False):
    if credit_type == 'letters' and story.type_id == STORY_TYPES['cover']:
        request = context['request']
        preview = context.get('preview')
        if request.user.is_authenticated and not preview and \
           request.user.indexer.cover_letterer_creator_only:
            if (story.letters == 'typeset' or story.letters == '?') and not\
              story.active_credits.filter(credit_type_id=CREDIT_TYPES[
                                                         'letters']):
                return ''
    credit_value = __credit_value(story, credit_type, True,
                                  show_sources, use_div=True)
    return credit_value


@register.filter
def show_bare_cover_letterer_credit(story):
    if (story.letters == 'typeset' or story.letters == '?') and not\
      story.active_credits.filter(credit_type_id=CREDIT_TYPES['letters']):
        return ''
    return show_creator_credit(story, 'letters')


@register.filter
def show_creator_credit_bare(story, credit_type):
    if credit_type == 'feature':
        credit_value = story.show_feature()
    elif credit_type.startswith('character'):
        credit_value = story.show_characters(css_style=False)
    else:
        credit_value = __credit_value(story, credit_type, url=True)
    return credit_value


@register.filter
def show_creator_credit(story, credit_type, url=True,
                        show_sources=False):
    credit_value = __credit_value(story, credit_type, url,
                                  show_sources)
    if credit_value and url:
        val = '<dt class="credit_tag"><span class="credit_label">'
        if type(story) is Story:
            val += '<a hx-get="/story/%d/%s/history/" ' % (story.id,
                                                           credit_type) + \
                   'hx-target="body" hx-swap="beforeend" ' +\
                   'style="cursor: pointer; color: #00e;">'
        val += credit_type.capitalize() + '</a></span></dt>' + \
            '<dd class="credit_def"><span class="credit_value">' + \
            credit_value + '</span></dd>'
        return mark_safe(val)
    else:
        return credit_value


@register.filter
def show_cover_letterer_credit(story):
    if (story.letters == 'typeset' or story.letters == '?') and not\
      story.active_credits.filter(credit_type_id=CREDIT_TYPES['letters']):
        return ''
    return show_creator_credit(story, 'letters')


@register.filter()
@stringfilter
def markdown(value):
    return mark_safe(md.markdown(value))


def __format_keywords(keywords, join_on='; ', model_name='story', url=True):
    if type(keywords) is str:
        credit_value = keywords
    else:
        keyword_list = list()
        for i in keywords.all().order_by('name'):
            if model_name in ['story', 'issue'] and url:
                keyword_list.append('<a href="%s%s/">%s</a>' % (
                                    urlresolvers.reverse(
                                      'show_keyword', kwargs={'keyword': i}),
                                    esc(model_name), esc(i)))
            else:
                keyword_list.append(esc(i))
        credit_value = join_on.join(str(i) for i in keyword_list)
    return mark_safe(credit_value)


@register.filter
def show_keywords(object):
    return __format_keywords(object.keywords)


@register.filter
def show_keywords_as_text(object):
    return __format_keywords(object.keywords, url=False)


@register.filter
def show_keywords_comma(object):
    return __format_keywords(object.keywords, ', ')


@register.filter
def show_cover_contributor(cover_revision):
    if cover_revision.file_source:
        if cover_revision.changeset.indexer_id == 381:  # anon user
            # filter away '( email@domain.part )' for old contributions
            text = cover_revision.file_source
            bracket = text.rfind('(')
            if bracket >= 0:
                return text[:bracket]
            else:
                return text
        else:
            return str(cover_revision.changeset.indexer.indexer) + \
              ' (from ' + cover_revision.file_source + ')'
    else:
        return cover_revision.changeset.indexer.indexer


@register.filter
def show_country_info_by_code(code, name):
    src = 'src="%simg/gcd/flags/%s.png"' % (settings.STATIC_URL,
                                            code.lower())
    alt = 'alt="%s"' % esc(code.upper())
    title = 'title="%s"' % esc(name)
    return mark_safe('%s %s %s' % (src, alt, title))


@register.filter
def show_country_info(country):
    if country:
        code = country.code
        name = country.name
    else:
        code = 'zz'
        name = 'unknown country'
    return show_country_info_by_code(code, name)


@register.filter
def get_country_flag(country):
    return mark_safe('<img %s class="inline">'
                     % show_country_info(country))


@register.filter
def get_country_flag_by_name(country_name):
    try:
        return get_country_flag(Country.objects.get(name=country_name))
    except Country.DoesNotExist:
        return country_name


@register.filter
def get_native_language_name(language_code):
    language = Language.objects.get(code=language_code)
    return language.get_native_name()


@register.filter
def show_page_count(story, show_page=False):
    """
    Return a properly formatted page count, with "?" as needed.
    """
    if story is None:
        return ''

    if story.page_count is None:
        if story.page_count_uncertain:
            return '?'
        return ''

    p = format_page_count(story.page_count)
    if story.page_count_uncertain:
        p = '%s ?' % p
    if show_page:
        p = p + ' ' + ngettext('page', 'pages', story.page_count)
    return p


@register.filter
def format_page_count(page_count):
    if page_count is not None and page_count != '':
        return f'{float(page_count):.10g}'
    else:
        return ''


@register.filter
def show_title(story, use_first_line=False):
    """
    Return a properly formatted title.
    """
    if story is None:
        return ''
    return story.show_title(use_first_line)


def generate_reprint_link(issue, from_to, notes=None, li=True,
                          only_number=False):
    ''' generate reprint link to_issue'''

    if only_number:
        link = ', <a href="%s">%s</a>' % (issue.get_absolute_url(),
                                          esc(issue.display_number))
    else:
        link = '%s %s <a href="%s">%s</a>' % \
          (get_country_flag(issue.series.country), from_to,
           issue.get_absolute_url(), esc(issue.full_name()))

    if issue.publication_date:
        link += " (" + esc(issue.publication_date) + ")"
    if notes:
        link = '%s [%s]' % (link, esc(notes))
    if li and not only_number:
        return '<li> ' + link
    else:
        return link


def generate_reprint_link_sequence(story, issue, from_to, notes=None, li=True,
                                   only_number=False):
    ''' generate reprint link to story'''
    if only_number:
        if story.sequence_number == 0 and \
           story.issue.variant_cover_status == 3:
            link = ', <a href="%s#%d">%s</a>' % (
              issue.get_absolute_url(),
              story.id,
              esc(issue.display_full_descriptor))
        else:
            link = ', <a href="%s#%d">%s</a>' % (issue.get_absolute_url(),
                                                 story.id,
                                                 esc(issue.display_number))
    elif story.sequence_number == 0:
        link = '%s %s <a href="%s#%d">%s</a>' % \
          (get_country_flag(issue.series.country), from_to,
           issue.get_absolute_url(), story.id,
           esc(issue.full_name()))
    else:
        link = '%s %s <a href="%s#%d">%s</a>' % \
          (get_country_flag(issue.series.country), from_to,
           issue.get_absolute_url(), story.id,
           esc(issue.full_name(variant_name=False)))
    if issue.publication_date:
        link = "%s (%s)" % (link, esc(issue.publication_date))
    if notes:
        link = '%s [%s]' % (link, esc(notes))
    if li and not only_number:
        return '<li> ' + link
    else:
        return link

# stuff to consider in the display
# - sort domestic/foreign reprints


def generate_reprint_notes(from_reprints=[], to_reprints=[], level=0,
                           no_promo=False):
    reprint = ""
    last_series = None
    last_follow = None
    same_issue_cnt = 0
    for from_reprint in from_reprints:
        if not from_reprint.origin:
            follow_info = ''
            if last_series == from_reprint.origin_issue.series and \
               last_follow == follow_info:
                reprint += generate_reprint_link(from_reprint.origin_issue,
                                                 "from ",
                                                 notes=from_reprint.notes,
                                                 only_number=True)
                same_issue_cnt += 1
            else:
                if last_follow is not None:
                    if same_issue_cnt > 0:
                        last_follow = last_follow.replace('which is',
                                                          'which are', 1)
                    reprint += '</li>' + last_follow
                same_issue_cnt = 0
                last_series = from_reprint.origin_issue.series
                reprint += generate_reprint_link(from_reprint.origin_issue,
                                                 "from ",
                                                 notes=from_reprint.notes)
                last_follow = follow_info
        else:
            follow_info = follow_reprint_link(from_reprint, 'from',
                                              level=level+1)
            if last_series == from_reprint.origin_issue.series and \
               last_follow == follow_info:
                reprint += generate_reprint_link_sequence(
                             from_reprint.origin, from_reprint.origin_issue,
                             "from ",
                             notes=from_reprint.notes, only_number=True)
                same_issue_cnt += 1
            else:
                if last_follow:
                    if same_issue_cnt > 0:
                        last_follow = last_follow.replace('which is',
                                                          'which are', 1)
                    reprint += '</li>' + last_follow
                same_issue_cnt = 0
                last_series = from_reprint.origin_issue.series

                reprint += generate_reprint_link_sequence(
                             from_reprint.origin, from_reprint.origin_issue,
                             "from ", notes=from_reprint.notes)
            last_follow = follow_info

    if last_follow:
        if same_issue_cnt > 0:
            last_follow = last_follow.replace('which is', 'which are', 1)
        reprint += '</li>' + last_follow
    last_series = None
    last_follow = None
    same_issue_cnt = 0

    for to_reprint in to_reprints:
        if not to_reprint.target:
            follow_info = ''
            if last_series == to_reprint.target_issue.series and \
               last_follow == follow_info:
                reprint += generate_reprint_link(
                             to_reprint.target_issue, "in ",
                             notes=to_reprint.notes, only_number=True)
                same_issue_cnt += 1
            else:
                if last_follow is not None:
                    if same_issue_cnt > 0:
                        last_follow = last_follow.replace('which is',
                                                          'which are', 1)
                    reprint += '</li>' + last_follow
                same_issue_cnt = 0
                last_series = to_reprint.target_issue.series
                reprint += generate_reprint_link(
                             to_reprint.target_issue, "in ",
                             notes=to_reprint.notes)
                last_follow = follow_info
        else:
            if no_promo and to_reprint.target.type_id in AD_TYPES:
                pass
            else:
                follow_info = follow_reprint_link(to_reprint, 'in',
                                                  level=level+1)
                if last_series == to_reprint.target_issue.series and \
                   last_follow == follow_info:
                    reprint += generate_reprint_link_sequence(
                                 to_reprint.target, to_reprint.target_issue,
                                 "in ", notes=to_reprint.notes,
                                 only_number=True)
                    same_issue_cnt += 1
                else:
                    if last_follow:
                        if same_issue_cnt > 0:
                            last_follow = last_follow.replace('which is',
                                                              'which are', 1)
                        reprint += '</li>' + last_follow
                    same_issue_cnt = 0
                    last_series = to_reprint.target_issue.series

                    reprint += generate_reprint_link_sequence(
                                 to_reprint.target, to_reprint.target_issue,
                                 "in ", notes=to_reprint.notes)
                last_follow = follow_info
    if last_follow:
        if same_issue_cnt > 0:
            last_follow = last_follow.replace('which is', 'which are', 1)
        reprint += '</li>' + last_follow

    return reprint


def follow_reprint_link(reprint, direction, level=0):
    if level > 10:  # max level to avoid loops
        return ''
    reprint_note = ''
    if direction == 'from':
        if type(reprint.origin) is Story:
            further_reprints = reprint.origin.from_all_reprints \
              .select_related('origin_issue__series__publisher')\
              .order_by('origin_issue__key_date',
                        'origin_issue__series',
                        'origin_issue__sort_code')
        else:
            further_reprints = list(reprint.origin.from_reprints.all())
        reprint_note += generate_reprint_notes(from_reprints=further_reprints,
                                               level=level)
        if reprint.origin.reprint_notes:
            for string in split_reprint_string(reprint.origin.reprint_notes):
                string = string.strip()
                if string.lower().startswith('from '):
                    reprint_note += '<li> ' + esc(string) + ' </li>'
    else:
        if type(reprint.target) is Story:
            further_reprints = reprint.target.to_all_reprints\
              .select_related('target_issue__series__publisher')\
              .order_by('target_issue__key_date',
                        'target_issue__series',
                        'target_issue__sort_code')
        else:
            further_reprints = list(reprint.target.to_reprints.all())
        reprint_note += generate_reprint_notes(to_reprints=further_reprints,
                                               level=level)
        if reprint.target.reprint_notes:
            for string in split_reprint_string(reprint.target.reprint_notes):
                string = string.strip()
                if string.lower().startswith('in '):
                    reprint_note += '<li> ' + esc(string) + ' </li>'

    if reprint_note != '':
        reprint_note = 'which is reprinted<ul>%s</ul>' % reprint_note
    return reprint_note


@register.filter
def show_reprints(story, bare_value=False):
    """ Filter for our reprint line on the story level."""
    from_reprints = story.from_all_reprints \
                         .select_related('origin_issue__series__publisher',
                                         'origin')\
                         .order_by('origin_issue__key_date',
                                   'origin_issue__series',
                                   'origin_issue__sort_code')
    reprint = generate_reprint_notes(from_reprints=from_reprints)

    if story.type_id not in [STORY_TYPES['preview'],
                             STORY_TYPES['comics-form ad']]:
        no_promo = True
    else:
        no_promo = False
    to_reprints = story.to_all_reprints\
                       .select_related('target_issue__series__publisher',
                                       'target')\
                       .order_by('target_issue__key_date',
                                 'target_issue__series',
                                 'target_issue__sort_code')
    reprint += generate_reprint_notes(to_reprints=to_reprints,
                                      no_promo=no_promo)

    if story.reprint_notes:
        for string in split_reprint_string(story.reprint_notes):
            string = string.strip()
            reprint += '<li> ' + esc(string) + ' </li>'

    if reprint != '':
        if bare_value:
            return mark_safe(reprint)
        label = _('Reprints')
        return mark_safe('<dt class="credit_tag">' +
                         '<span class="credit_label">' + label +
                         '</span></dt>' + '<dd class="credit_def">' +
                         '<span class="credit_value">' +
                         '<ul>' + reprint + '</ul></span></dd>')
    else:
        return ""


@register.filter
def show_reprints_for_issue(issue):
    """ show reprints stored on the issue level. """

    from_reprints = issue.from_reprints\
                         .select_related('origin_issue__series__publisher')\
                         .order_by('origin_issue__sort_code')
    reprint = generate_reprint_notes(from_reprints=from_reprints)

    to_reprints = issue.to_reprints\
                       .select_related('target_issue__series__publisher')\
                       .order_by('target_issue__sort_code')
    reprint += generate_reprint_notes(to_reprints=to_reprints,
                                      no_promo=True)

    if reprint != '':
        label = _('Parts of this issue are reprinted') + ': '

        return mark_safe(label + '<ul class="object-page-link-list columns-1">'
                         + reprint + '</ul>')
    else:
        return ""
