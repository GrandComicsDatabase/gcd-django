# -*- coding: utf-8 -*-
# coding=utf-8
from django import template
from django.utils.translation import ugettext as _
from django.utils.safestring import mark_safe
from django.utils.html import conditional_escape as esc

from apps.gcd.models import Issue, Story, StoryType

register = template.Library()

leading_articles = ['the', 'an', 'a', 'die', 'der', 'das', 'ein', 'los',
                    'la', 'le', 'lo', "l'", 'las', 'les', 'el', 'un', 'Uua',
                    'unos', 'unas', 'une', 'il', 'i', 'gli', 'en', 'et', 'ett',
                    'de', 'het', 'een']
# list checks we should/could do when we use this for the migration
# - keydate of from should be smaller, keydate of to should be larger
# - if no keydate exists on one side maybe check on series year
# - search for title match of story as well
# - search for matching page count
# - search for reprint link back

def find_reprint_sequence_in_issue(from_story,to_issue):
    '''look for sequence in <to_issue> which fits <from_story>'''

    results = Story.objects.exclude(deleted=True)
    results = results.filter(issue__id = to_issue)
    # limit to the same (or closely related) sequence
    # 6,7 are cover and cover reprint
    if not from_story.type.id in [6, 7]:
        results = results.filter(type=from_story.type)
        results = results.filter(title__icontains = from_story.title.strip().strip('!').strip('.'))
    if (results.count() > 1):
        try:
            results = results.filter(page_count = from_story.page_count)
        except:
            pass
    if (results.count() == 1):
        return results[0].sequence_number
    #for i in range(results.count()):
        #print results[i].title
    return -1

def parse_reprint_lars(reprints, max_found = 10):
    notes = ''
    story_type = StoryType.objects.get(name='comic story')
    #print reprints
    if reprints.startswith(('from ','From ', 'FROM ')):
        reprints = reprints[5:]
    elif reprints.startswith(' from '):
        reprints = reprints[6:]
    elif reprints.startswith(' in '):
        reprints = reprints[4:]
    elif reprints.startswith('in '):
        reprints = reprints[3:]
    elif reprints.startswith('Cover von '):
        reprints = reprints[10:]
    elif reprints.startswith('von '):
        reprints = reprints[4:]
    elif reprints.startswith('vom '):
        reprints = reprints[4:]
    #try:# our preferred format: seriesname (publisher, year <series>) #nr
    #check for Superman(
    position = reprints.find(' (')
    series = reprints[0:position].strip(",Tthe ")
    string = reprints[position+2:]
    after_series = string # use in other formats
    end_bracket = string.find(')')
    position = string[:end_bracket].rfind(', ')
    if position == -1:
        position = string[:end_bracket].rfind(',')
        publisher = string[:position].strip()
        position+=1
    else:
        publisher = string[:position].strip()
        position+=2
    string = string[position:]
    year = string[:4]
    string = string[4:]
    position = string.find(' #')+2
    if position == 1:
        position = string.find(')#')+2
    string = string[position:]
    position = string.find(' [') #check for notes
    if position > 0:
        position_end = string.find(']')
        if position_end > position:
            notes = string[position:position_end+1]
        date_pos = string.find(' (') #check for (date)
        if date_pos > 0 and date_pos < position:
            position = date_pos
    else:
        position = string.find(' (') #check for (date)
        if position > 0: #if found ignore later
            pass
        else:
            #allow #nr date without ( ) only
            #if there is a number before the space
            position = string.find(',')
            if position > 0:
                if string[:position].strip().isdigit():
                    pass
                else:
                    position = 0
    if string.isdigit(): #in this case we are fine
        number = string
    else:
        if position > 0:
            number = string[:position].strip()
        else:
            number = string.strip().strip('.,')
    #print series, publisher, number, year
    #if publisher == 'Ehapa':
        #print series, year, number
    try:
        results = Issue.objects.exclude(deleted=True).filter(variant_of=None)
        results = results.filter(series__name__icontains = series)
        results = results.filter(series__publisher__name__icontains
        = publisher)
        results = results.filter(series__year_began__exact = int(year))
        results = results.filter(number__exact = number)
        #print results, series, publisher, number, year
        if results.count() == 0 or results.count() > max_found:
            # try stripping ',.' from before whitespace/from the end
            position = string.find(' ')
            if position > 0:
                number = string[:position].strip('.,')
            else:
                number = string.strip('.,')
            results = Issue.objects.exclude(deleted=True).filter(variant_of=None)
            results = results.filter(series__name__icontains = series)
            results = results.filter(series__publisher__name__icontains
            = publisher)
            results = results.filter(series__year_began__exact = int(year))
            results = results.filter(number__exact = number)
        position = string.find('.Sequence')
        #print results, series, publisher, number, year, position
        if results.count() > 0:
            if position > 0:
                position_before = string[:position].rfind(' ')
                #print position_before, string[position_before:position].strip(' [')
                sequence_number = int(string[position_before:position].strip(' ['))
                #print sequence_number
                story = Story.objects.exclude(deleted=True).filter(issue=results[0])
                story = story.filter(sequence_number=sequence_number, type=story_type)
                if story.count() > 0:
                    story = story[0]
                else:
                    story = False
                    sequence_number = -1
            else:
                story = False
                sequence_number = -1
            return results[0],notes,sequence_number,story
        else:
            return False,'',-1,False
    except:
        return False,'',-1,False

def parse_reprint_fr(reprints):
    """ parse a reprint entry starting with "fr." Often found in older indices.
    Don't trust this parsing too much."""

    try:# for format: fr. seriesp #nr (issue date) date unused for parsing
        position = reprints.find(' #')
        series = reprints[3:position].strip()
        position += 2
        string = reprints[position:]
        position = string.find('(')
        number = string[:position].strip()
        results = Issue.objects.exclude(deleted=True).filter(variant_of=None)
        results = results.filter(series__name__icontains = series)
        results = results.filter(number__exact = number)
    except:
        pass

    if results.count() == 0 or results.count() > 10:
        try:# for format: from seriesname #nr (issue date) date unused for parsing
            #and for format: from seriesname #nr
            position = reprints.find(' #')
            if reprints.lower().startswith('from'):
                series = reprints[4:position].strip()
            elif reprints.lower().startswith('rpt. from'):
                series = reprints[9:position].strip()
            elif reprints.lower().startswith('rep from'):
                series = reprints[8:position].strip()
            else:
                return Issue.objects.none()
            position += 2
            string = reprints[position:]
            position = string.find('(')
            if position > 0:
                number = string[:position].strip()
                position_end = string.find(')')
                if position_end > position:
                    year = string[position_end-4:position_end]
            elif string.isdigit():#we don't even have (issue date)
                number = string
            else:
                number = string[:string.find(' ')].strip()
            results = Issue.objects.exclude(deleted=True).filter(variant_of=None)
            results = results.filter(series__name__icontains = series)
            results = results.filter(number__exact = number)
            if year:
                results = results.filter(key_date__icontains = year)
        except:
            pass

    return results


def parse_reprint_full(reprints, from_to, max_found = 10):
    """ parse a reprint entry, first for our standard, them some for
    other common version.  We may turn the others off or add even more. ;-)"""
    notes = ''
    all_issues = Issue.objects.exclude(deleted=True).filter(variant_of=None, deleted=False)
    results = None
    if reprints.lower().startswith(from_to):
        try:# our preferred format: seriesname (publisher, year <series>) #nr
            position = reprints.find(' (')
            # TODO change series name for trailing articles
            series = reprints[len(from_to):position].strip(",Tthe ")
            string = reprints[position+2:]
            after_series = string # use in other formats
            end_bracket = string.find(')')
            position = string[:end_bracket].rfind(', ')
            publisher = string[:position].strip()
            position+=2
            string = string[position:]
            year = string[:4]
            if from_to in ['da ', 'in ', 'de ', 'en ']: #italian and spanish from/in
                if year.isdigit() != True:
                    position = string.find(')')
                    year = string[position-4:position]
            string = string[4:]
            position = string.find(' #')+2
            string = string[position:]
            position = string.find(' [') #check for notes
            if position > 0:
                position_end = string.find(']')
                if position_end > position:
                    notes = string[position+2:position_end]
                date_pos = string.find(' (') #check for (date)
                if date_pos > 0 and date_pos < position:
                    position = date_pos
            else:
                position = string.find(' (') #check for (date)
                if position > 0: #if found ignore later
                    pass
                else:
                    #allow #nr date without ( ) only
                    #if there is a number before the space
                    position = string.find(' ')
                    if position > 0:
                        if string[:position].isdigit():
                            pass
                        else:
                            position = 0
            if string.isdigit(): #in this case we are fine
                number = string
            else:
                if position > 0:
                    number = string[:position].strip()
                else:
                    number = string.strip().strip('.')
            results = all_issues
            results = results.filter(series__name__icontains = series)
            results = results.filter(series__publisher__name__icontains
            = publisher)
            results = results.filter(series__year_began__exact = int(year))
            results = results.filter(number__exact = number)
            if results.count() == 0 or results.count() > max_found:
                # try stripping ',.' from before whitespace/from the end
                position = string.find(' ')
                if position > 0:
                    number = string[:position].strip('.,')
                else:
                    number = string.strip('.,')
                results = all_issues
                results = results.filter(series__name__icontains = series)
                results = results.filter(series__publisher__name__icontains
                = publisher)
                results = results.filter(series__year_began__exact = int(year))
                results = results.filter(number__exact = number)
        except:
            pass

        if results.count() == 0 or results.count() > max_found:
            try:# our typoed format: seriesname (publisher year <series>) #nr
                # use series from before
                string = after_series
                position = string.find(' 1')
                if position > 0:
                    publisher = string[:position].strip()
                else:
                    position = string.find(' 2')
                    publisher = string[:position].strip()
                position+=1
                string = string[position:]
                year = string[:4]
                string = string[4:]
                position = string.find(' #')+2
                string = string[position:]
                position = string.find(' [') #check for notes
                if position > 0:
                    position_end = string.find(']')
                else:
                    position = string.find(' (') #check for (date)
                    if position > 0: #if found ignore later
                        position_end = 0
                if string.isdigit(): #in this case we are fine
                    number = string
                else:
                    if position > 0:
                        number = string[:position].strip()
                    else:
                        number = string.strip()
                if position > 0 and position_end > position:
                    notes = string[position:position_end+1]
                results = all_issues
                results = results.filter(series__name__icontains = series)
                results = results.filter(series__publisher__name__icontains
                = publisher)
                results = results.filter(series__year_began__exact = int(year))
                results = results.filter(number__exact = number)
            except:
                pass

        if results.count() == 0 or results.count() > max_found:
            try:# for format: seriesname (year series) #nr
                # use series from before
                string = after_series
                year = string[:4]
                string = string[4:]
                position = string.find(' #')+2
                string = string[position:]
                if string.isdigit():
                    number = string
                else:
                    number = string[:string.find(' ')]
                position = string.find('[')
                position_end = string.find(']')
                if position > 0 and position_end > position:
                    notes = string[position:position_end+1]
                results = all_issues
                results = results.filter(series__name__icontains = series)
                results = results.filter(series__year_began__exact = int(year))
                results = results.filter(number__exact = number)
            except:
                pass

        if results.count() == 0 or results.count() > max_found:
            try:# for format: seriesname #nr(publisher, year <series>)
                position = reprints.find(' #')
                series = reprints[len(from_to):position].strip("Tthe ")
                position += 2
                string = reprints[position:]
                after_series = string
                position = string.find('(')
                number = string[:position].strip()
                position += 1
                string = string[position:]
                end_bracket = string.find(')')
                position = string[:end_bracket].rfind(', ')
                publisher = string[:position].strip()
                position += 2
                string = string[position:]
                year = string[:4]
                position = string.find('[')
                if position > 0:
                    notes = string[position:]
                results = all_issues
                results = results.filter(series__name__icontains = series)
                results = results.filter(series__publisher__name__icontains
                = publisher)
                results = results.filter(series__year_began__exact = int(year))
                results = results.filter(number__exact = number)
            except:
                pass

        if results.count() == 0 or results.count() > max_found:
            try:# for format: seriesname #nr (year)
                # use series from before
                string = after_series
                position = string.find('(')
                number = string[:position].strip()
                position += 1
                string = string[position:]
                year = string[:4]
                position = string.find('[')
                if position > 0:
                    notes = string[position:]
                results = all_issues
                results = results.filter(series__name__icontains = series)
                results = results.filter(series__year_began__exact = int(year))
                results = results.filter(number__exact = number)
            except:
                pass

        if from_to == u"från " and (results.count() == 0 or results.count() > max_found):
            try:# for format: seriesname #nr [country, publication year]
                # use series from before
                string = after_series
                position = string.find('[')
                number = string[:position].strip()
                position += 1
                string = string[position:]
                position = string.find(']')
                pub_year = string[position-4:position]
                results = all_issues
                results = results.filter(series__name__icontains = series)
                #results = results.filter(series__year_began__exact = int(year))
                results = results.filter(publication_date__icontains = pub_year)
                results = results.filter(number__exact = number)
            except:
                pass
        return results,notes
    else:
        return Issue.objects.none(),None


def parse_reprint(reprints, from_to):
    """ parse a reprint entry for exactly our standard """
    notes = ''
    results = Issue.objects.none()
    if reprints.lower().startswith(from_to):
        try:# our format: seriesname (publisher, year <series>) #nr
            position = reprints.find(' (')
            series = reprints[len(from_to):position]
            # could remove the/The from beginning and from end with ','
            string = reprints[position+2:]
            after_series = string # use in other formats
            end_bracket = string.find(')')
            position = string[:end_bracket].rfind(', ')
            if position < 0:
                series_pos = string.lower().find('series)')
                if series_pos > 0:
                    position = string[:series_pos].rfind(', ')
            publisher = string[:position].strip()
            position+=2
            string = string[position:]
            year = string[:4]
            if from_to in ['da ', 'in ', 'de ', 'en ']: #italian and spanish from/in
                if year.isdigit() != True:
                    position = string.find(')')
                    year = string[position-4:position]
            string = string[4:]
            position = string.find(' #')+2
            string = string[position:]
            position = string.find(' [') #check for notes
            if position > 0:
                position_end = string.find(']')
                if position_end > position:
                    notes = string[position+2:position_end]
                date_pos = string.find(' (') #check for (date)
                if date_pos > 0 and date_pos < position:
                    position = date_pos
            else:
                position = string.find(' (') #check for (date)
                if position > 0: #if found ignore later
                    pass
            volume = None
            if string.isdigit(): #in this case we are fine
                number = string
            elif string[0].lower() == 'v' and string.find('#') > 0:
                #print "A", string
                n_pos = string.find('#')
                volume = string[1:n_pos]
                if position > 0:
                    number = string[n_pos+1:position]
                else:
                    number = string[n_pos+1:]
                #print from_to, volume, number, position, string
            else:
                hyphen = string.find(' -')
                # following issue title after number
                if hyphen > 0 and string[:hyphen].isdigit() and not string[hyphen+2:].strip()[0].isdigit():
                    number = string[:hyphen]
                else:
                    if position > 0:
                        number = string[:position].strip('., ')
                    else:
                        number = string.strip('., ')
            if number == 'nn':
                number = '[nn]'
            # TODO change series name for trailing articles
            #print series, number
            if series[series.rfind(', ')+2:].lower() in leading_articles:
                #print "A", series
                series = series[series.rfind(', ')+2:] + " " + series[:series.rfind(', ')]
                #print series
            results = Issue.objects.exclude(deleted=True).filter(variant_of=None, deleted=False)
            results = results.filter(series__name__icontains = series)
            results = results.filter(series__publisher__name__icontains
            = publisher)
            results = results.filter(series__year_began__exact = int(year))
            results = results.filter(number__exact = number)
            if volume:
                results = results.filter(volume__exact = volume)
            #print results, series, reprints, number
            if results.count() > 1:
                results = results.filter(series__name__exact = series)
        except:
            #print "???", notes, reprints
            pass

        return results, notes
    else:
        return Issue.objects.none(), None