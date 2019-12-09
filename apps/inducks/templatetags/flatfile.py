# -*- coding: utf-8 -*-
# coding=utf-8
import re
import locale
from mx.DateTime.ISO import ParseDateTimeUTC
from mx.DateTime import DateTimeDelta
from MySQLdb import OperationalError

from django import template
from django.utils.encoding import smart_unicode as uni
from django.utils.translation import ugettext as _
from django.utils.translation import activate, deactivate
from django.core.exceptions import MultipleObjectsReturned 

from apps.inducks.models import SupportRole, StoryVersion, Story
from apps.gcd.models import Series as GCD_Series
from apps.gcd.models import Issue as GCD_Issue
register = template.Library()

def show_issue_credit(issue, credit):
    credit_value = ""
    if credit == "translation":
        translator = issue.issuerole_set.filter(role = 't')
        #print "Trans", len(translator)
        #translator = story.supportrole_set.filter(role = 't')
        for i in translator:
            credit_value += i.creator.name + " (" + _('translation') + "); "
        credit_value = credit_value[0:-2]
    elif credit == "colors":
        colors = issue.issuerole_set.filter(role = 'c')
        # not sure why this doesn't work, it did work in the beginning
        # colors = story.supportrole_set.filter(role = 'c')
        for i in colors:
            credit_value += i.creator.name + "; "
        credit_value = credit_value[0:-2]
    elif credit == "letters":
        letters = issue.issuerole_set.filter(role = 'l')
        #letters = story.supportrole_set.filter(role = 'l')
        for i in letters:
            credit_value += i.creator.name + "; "
        credit_value = credit_value[0:-2]
    elif credit == "indexer":
        indexer = issue.issuerole_set.filter(role = 'i')
        for i in indexer:
            credit_value += i.creator.name + "; "
        credit_value = credit_value[0:-2]
    return uni(credit_value)
    
def show_credit(story, credit, force = False, default = ""):
    """ For showing the credits on the search results page.
    For creator credits force sets '?' for empty story credits.
    For cover type force sets type 'backcovers' """

    if not story:
        return ""

    if credit == 'type':
        if story.story_version.type == 'n':
            return 'Story'
        elif story.story_version.type == 'i':
            return 'Pinup'
        elif story.story_version.type == 'c':
            if force == False:
                return 'Cover'
            else:
                return 'Pinup'
        elif story.story_version.type == 'f': 
            return 'centerfold'
        elif story.story_version.type == 't':
            return 'Text Story'
        elif story.story_version.type == 'a':
            if story.title.startswith('Letter'):
                return 'Letters'
            else:
                return 'Text Article'
        elif story.story_version.type == 'g':
            return 'Activity'
        elif story.story_version.type == 's':
            return 'strange layout'
        elif story.story_version.type in ['L','P']:
            return 'Pinup'
        elif story.story_version.type == 'k':
            return 'newspaper strip'

    if credit == "pencils":
        pencils = story.story_version.creatorrole_set.filter(role = 'a')
        credit_value = ""
        for i in pencils:
            credit_value += uni(i.creator.name) + "; "
        credit_value = credit_value[0:-2]
    elif credit == "inks":
        inks = story.story_version.creatorrole_set.filter(role = 'i')
        credit_value = ""
        for i in inks:
            credit_value += uni(i.creator.name) + "; "
        credit_value = credit_value[0:-2]
        if credit_value == "": # no-inks --> inks=pencils
            credit_value = default
    elif credit == "script":
        script = story.story_version.creatorrole_set.filter(role = 'w')
        plot = story.story_version.creatorrole_set.filter(role = 'p')
        credit_value = uni("")
        for i in script:
            if len(plot) > 0 and i not in plot:
                credit_value += uni(i.creator.name) + " (" + _("script") + "); "
            else:
                credit_value += uni(i.creator.name) + "; "
        for i in plot:
            if i not in script:
                credit_value += uni(i.creator.name) + " (" + _("plot") + "); "
        translator = SupportRole.objects.filter(story = story.id).filter(role = 't')
        #print "Trans", len(translator)
        #translator = story.supportrole_set.filter(role = 't')
        if not __credit_visible(credit_value) and force:
            credit_value = '?; '
        if len(translator) > 0:
            for i in translator:
                credit_value += uni(i.creator.name) + " (" + _("translation") + "); "
        elif default != "":
            credit_value += default + "; "
        credit_value = credit_value[0:-2]
    elif credit == "colors":
        colors = SupportRole.objects.filter(story__exact = story.id).filter(role = 'c')
        # not sure why this doesn't work, it did work in the beginning
        # colors = story.supportrole_set.filter(role = 'c')
        credit_value = ""
        for i in colors:
            credit_value += uni(i.creator.name) + "; "
        credit_value = credit_value[0:-2]
        if credit_value == "":
            credit_value = default
    elif credit == "letters":
        letters = SupportRole.objects.filter(story__exact = story.id).filter(role = 'l')
        #letters = story.supportrole_set.filter(role = 'l')
        credit_value = ""
        for i in letters:
            credit_value += uni(i.creator.name) + "; "
        credit_value = credit_value[0:-2]
        if credit_value == "":
            credit_value = default
    else:
        credit_value = story.__dict__[credit]

    if "no one" in credit_value and len(credit_value) <= 8:
        credit_value = "none"

    if not __credit_visible(credit_value) and force:
        return '?'
    else:
        return uni(credit_value.strip(','))

def __credit_visible(value):
    """ Check if credit exists and if we want to show it.  Could add
    further conditions for not showing the credit here."""
    return value and value != ','

def get_feature(story):
    feature = ""
    try: #shouldn't be there a different way to check for existence ?
        features = story.story_version.base_story.feature_set.all()
    except:
        return feature
    for i in features:
        if i.feature.name != "--":
            #feature += i.feature.name + "; "
            try:
                feature += i.feature.charactername_set.filter(language = story.language).filter(preferred = 'Y')[0].name + "; "
            except IndexError:
                feature += i.feature.name + "; "
    feature = feature[:-2]
    return uni(feature)

def get_characters(story):
    characters = story.story_version.appearance_set\
                    .filter(character__gt = "")
    appearance = ""
    for i in characters:
        # TODO: there is also entrycharacternames, to have
        # the name for a given story, this is also 
        # linked to the character
        try:
            tmp = i.character.charactername_set\
                    .filter(language = story.language)\
                    .filter(preferred = 'Y')
        except MultipleObjectsReturned: 
        # some one-shot characters are twice in character-db
            tmp = Character.objects\
                    .filter(character__exact = i.character_code)
            # could use entrycharacternames especially here
        if len(tmp) == 0:
            appearance += i.character.name  + "; "
        else:
            appearance += tmp[0].name + "; "
    appearance = appearance[:-2]
    if appearance == "--":
        return ""
    else:
        return uni(appearance)
    
def get_page_count(story):
    pages = str(story.story_version.page_count)
    if story.story_version.no_broken_page == 'N':
        broken_page = float(story.story_version.page_numerator)/ float(story.story_version.page_denominator)
        if broken_page > 0:
            add_broken = "%0.5g" % broken_page
            pages += add_broken[1:]
    return pages
    
def get_job_number(story):
    if story.job_number != "":
        return story.job_number 
    else:
        return story.story_version.id

def convert_isv_date(date_string, language_code = 'en_US'):
    try:
        date = ParseDateTimeUTC(date_string)
    except ValueError:
        date = ParseDateTimeUTC(date_string[0:4])
    if len(language_code) == 5:
        language_code = language_code[0:2] + '_' + language_code[3:5]
    #print language_code, locale.normalize(language_code)
    locale.setlocale(locale.LC_ALL, (language_code,'utf-8'))
    if len(date_string) >= 9:
        return date.strftime("%e %B %Y").strip() 
    if len(date_string) >= 6:
        return date.strftime("%B %Y") 
    return date.strftime("%Y")

def newspaper_date(date_string):
    return "19" + date_string[0:2] + "." + date_string[3:5] + "." + date_string[6:]

def get_printings(original_story, first_publication_date):
    printings = Story.objects.filter(story_version__base_story =\
                original_story).filter(issue__publication_date__gt = "")\
                .order_by('issue__publication_date')
    if len(first_publication_date) <= 4 or 'Q' in first_publication_date:
        first_printings = printings.filter(issue__publication_date__icontains\
            = first_publication_date[0:4])
    else:
        end_date = ParseDateTimeUTC(first_publication_date[0:7])
        end_date += DateTimeDelta(120)
        end_date = end_date.strftime("%Y-%m")
        first_printings = printings.filter(issue__publication_date__gte \
            = first_publication_date[0:7]).filter(issue__publication_date__lte \
            = end_date)
        if not first_printings:
            first_printings = \
                printings.filter(issue__publication_date__icontains \
                = first_publication_date[0:4])
    return printings,first_printings

def gcd_series(issue, publisher):
    try:
        if len(issue.number) == 7 and issue.number[4] == '-':
            number = issue.number[5:7].lstrip('0') + "/" + issue.number[0:4]
        else:
            number = issue.number
        gcd_issue = GCD_Issue.objects.filter(series__name__icontains = \
                    issue.series.name).filter(number = number)\
                    .filter(series__country_code__iexact =\
                    issue.series.country_code.code)
        if len(gcd_issue) > 1:
            gcd_issue_2 = gcd_issue.filter(series__name__istartswith = \
                        issue.series.name)
            if len(gcd_issue_2) > 0:
                gcd_issue = gcd_issue_2
        if len(gcd_issue) > 0:
            if len(gcd_issue) > 1:
                gcd_issue = gcd_issue.filter(series__name = \
                    issue.series.name)
            #print gcd_issue, issue.series.name
            if len(gcd_issue) == 1:
                return "from " + uni(gcd_issue[0].series.name) + " (" +\
                uni(gcd_issue[0].series.publisher.name) + ", " +\
                uni(gcd_issue[0].series.year_began) + " series) #" +\
                gcd_issue[0].number
        gcd_series = GCD_Series.objects.filter(name__startswith = \
                issue.series.name).filter(country_code__iexact =\
                issue.series.country_code.code)
        #print issue.series.name, issue.series.country_code
        if len(gcd_series) > 1 and publisher != "":
            gcd_series = gcd_series.\
                        filter(publisher__name__icontains = publisher)
        if len(gcd_series) == 1:
            #print gcd_series, issue.series.name
            return "from " + gcd_series[0].name + " (" +\
                    gcd_series[0].publisher.name + ", " +\
                    uni(gcd_series[0].year_began) + " series) #" + number
        else:
            for i in gcd_series:
                print(i, i.country_code)
            return ""
    except OperationalError:
        print(issue.series.name)

def reprints(story):
    try:
        if story.story_version.base_story:
            pass
    except:
        return ""
    original_story = story.story_version.base_story.original_story
    printings, first_printing = get_printings(original_story,
                    story.story_version.base_story.first_publication_date)
    country_first = False
    reprint = ""
    if first_printing:
        if first_printing.filter(id = story.id):
            if original_story[0] == 'D':
                reprint = "from Egmont (DK); "
            elif original_story[0] == 'Q':
                reprint = ""
            elif original_story[0] == 'H':
                reprint = "from Netherlands; "
            elif original_story[0] == 'S':
                reprint = "Disney Studio (US); "
            elif story.story_version.type != 'c':
                reprint = "ask Jochen to include studio code: " + original_story[0] + "; " 
#                print original_story
        for source in first_printing[0:3]:
            if source.id != story.id:
                if source.id[0:4] in ["us/Z", "us/Y"]:
                    if original_story[1] == 'M':
                        reprint += "from Mickey Mouse"
                    elif original_story[1] == 'D':
                        reprint += "from Donald Duck"
                    elif original_story[1] == 'X':
                        reprint += "from Scamp"
                    else:
                        reprint += "from some strip, find out and tell Jochen"
                        print(original_story)
                    if original_story[0] == 'Y':
                        reprint += " daily"
                    elif original_story[0] == 'Z':
                        reprint += " Sunday"
                    reprint += " (King Features Syndicate) " + \
                                newspaper_date(original_story[3:]) + "; "
                else:
                    publisher = source.issue.publisherjob_set.all()
                    if publisher:
                        publisher_name = publisher[0].publisher.name
                    else:
                        publisher_name = "?"
                    gcd_reprint = gcd_series(source.issue, publisher_name)
                    #print "B",gcd_reprint
                    if gcd_reprint != "":
                        reprint += uni(gcd_reprint) + " (" + \
                                uni(convert_isv_date(source.\
                                issue.publication_date,story\
                                .issue.series.language_code))
                    else:
                        if len(source.issue.number) == 7 \
                                and source.issue.number[4] == '-':
                            number = source.issue.number[5:7].lstrip('0') + "/" \
                                    + source.issue.number[0:4]
                        else:
                            number = source.issue.number
                        reprint += "from " + uni(source.issue.series.name) + \
                                " (" + uni(publisher_name) + ", ???? series) #" \
                                + number + " (" + \
                                convert_isv_date(source.issue.publication_date, \
                                story.issue.series.language_code)
                    if source.issue.series.country_code != \
                                story.issue.series.country_code:
                        if source.issue.series.country_code.\
                          countryname_set.filter(language = story.language):
                            reprint += ") [" + uni(source.issue.series\
                            .country_code.countryname_set\
                            .filter(language = story.language)[0].name) + \
                            "]; "
                    else:
                        reprint += "); "
            else:
                country_first = True
        if len(first_printing) > 3:
            reprint += "another " + str(len(first_printing)-3) \
                    + " issues within 4 months; "
        for source in first_printing:
            if source.issue.series.country_code == \
                            story.issue.series.country_code:
                country_first = True

    if country_first == False:
        own_country = printings.filter(issue__series__country_code = \
                story.issue.series.country_code)\
                .filter(issue__series__language_code = \
                story.issue.series.language_code) \
                .order_by('issue__publication_date')
        if own_country:# and not (own_country[0] == story):
            if own_country[0].id == story.id:
                pass # TODO: look for reprints
            else:
                publisher = own_country[0].issue.publisherjob_set.all()
                if publisher:
                    publisher_name = publisher[0].publisher.name
                else:
                    publisher_name = ""
                gcd_reprint = gcd_series(own_country[0].issue, publisher_name)
                if gcd_reprint != "":
                    reprint += uni(gcd_reprint) + " (" + \
                                uni(convert_isv_date(own_country[0].\
                                issue.publication_date,story\
                                .issue.series.language_code)) + "); " 
                else:
                    if len(own_country[0].issue.number) == 7 \
                            and own_country[0].issue.number[4] == '-':
                        number = own_country[0].issue.number[5:7].lstrip('0') \
                                + "/" + own_country[0].issue.number[0:4]
                    else:
                        number = own_country[0].issue.number
                    reprint += "from " + uni(own_country[0].issue.series.name)+\
                                " (" + uni(publisher_name) + ", ???? series) #"\
                                + number + " (" + \
                                uni(convert_isv_date(own_country[0].\
                                issue.publication_date,story\
                                .issue.series.language_code)) + "); "
    reprint = reprint[:-2]
    return reprint
    return ""

def issue_flatfile(issue):
    """ For showing the flatfile lines for an issue."""

    if not issue:
        return ""
    activate(issue.series.language_code) # for translation stuff
    # a bit of general stuff
    stories = list(issue.story_set.order_by('sequence_number'))
    letter_default = show_issue_credit(issue,"letters")
    color_default = show_issue_credit(issue,"colors")
    translation_default = show_issue_credit(issue,"translation")
    #indexer = show_issue_credit(issue,"indexer")
    # first cover sequence
    line = issue.number + "\t" \
        + convert_isv_date(issue.publication_date, issue.series.language_code)\
        + "\t" + show_credit(stories[0],"type") + \
        "\t" + "\t" + get_feature(stories[0]) + "\t" + uni(stories[0].title) + \
        "\t" + show_credit(stories[0],"pencils", True) + "\t" +\
        show_credit(stories[0],"inks", show_credit(stories[0],"pencils")) + \
        "\t" + "\t" + show_credit(stories[0],"colors", True) + "\t" +\
        show_credit(stories[0],"letters", False) + "\t" +\
        "?\t" + issue.page_count + "\t" + issue.price + "\t" \
        + get_characters(stories[0]) 
    line += "\tIssue data imported from inducks.org. "
    line += "If you edit entries please give the updated information also to inducks.org. "
    #line += "Original inducks indexer " + indexer
    line += "[inducks issue-id:" + issue.id \
        + "][inducks story-id:" + stories[0].id + \
        "][inducks storyversion-id:" \
        + stories[0].story_version.id + "]\t" 
    line += "\t" + uni(reprints(stories[0])) + "\t" \
        + stories[0].job_number
    for num in range(1,len(stories)):
        story = stories[num]
        force = story.story_version.type == 'n'
        script = show_credit(story,"script", force or story.story_version.type in ['t', 'a'], translation_default)
        notes = ""
        if story.story_version.type in ['c', 'i']:
            #notes += "Illustration idea by " + script
            script = ""
        if story.included_in_story:
            notes += " This sequence is included in " + \
                    story.included_in_story + ", please edit"
        line += "\n\t\t" + show_credit(story,"type", True) + "\t" + "\t" +\
            get_feature(story) + "\t" + uni(story.title) + "\t" +\
            show_credit(story,"pencils", force) + "\t" +\
            show_credit(story,"inks", force, show_credit(story,"pencils")) \
            + "\t" + script + "\t" +\
            show_credit(story,"colors", force, color_default) + "\t" +\
            show_credit(story,"letters", force, letter_default) + "\t" +\
            "\t" + get_page_count(story) + "\t" + "\t" +\
            uni(get_characters(story)) + "\t[inducks story-id:" + \
            story.id + "][inducks storyversion-id:" + \
            story.story_version.id + "]" + uni(story.notes) + \
            uni(notes) + "\t" + "\t" + uni(reprints(story)) + "\t" +\
            story.job_number
    deactivate()
    return line

# GCD Flatfile format for sequence
#Issue ^T PubDate ^T Type ^T Genre ^T Feature ^T Title ^T Pencils
#^T Inks ^T Script ^T Colors ^T Letters ^T Editing ^T PageCount ^T
#Price ^T Characters ^T Notes ^T Synopsis ^T Reprints

register.filter(show_credit)
register.filter(issue_flatfile)
