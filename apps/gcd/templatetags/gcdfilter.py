from django import template
from django.utils.translation import ugettext as _
from django.utils.safestring import mark_safe
from django.utils.html import conditional_escape as esc

from apps.gcd.models import Issue

register = template.Library()

def show_credit(story,credit):
    """ For showing the credits on the search results page."""
    
    if credit == 'script':
        return _('Script')+": "+story.script
    elif credit == 'pencils':
        return _('Pencils')+": "+story.pencils
    elif credit == 'inks':
        return _('Inks')+": "+story.inks
    elif credit == 'colors':
        return _('Colors')+": "+story.colors
    elif credit == 'letters':
        return _('Letters')+": "+story.letters
    elif credit == 'editor':
        return _('Editor')+": "+story.editor
    elif credit == 'job':
        return _('Job number')+": "+story.job_number
    elif credit == 'title':
        return _('Title')+": "+story.title
    elif credit.startswith('any:'):
        credit_string=""
        if story.script.find(credit[4:]) != -1:
            credit_string += _('Script')+": "+story.script
        if story.pencils.find(credit[4:]) != -1:
            credit_string += _('Pencils')+": "+story.pencils
        if story.inks.find(credit[4:]) != -1:
            credit_string += _('Inks')+": "+story.inks
        if story.colors.find(credit[4:]) != -1:
            credit_string += _('Colors')+": "+story.colors
        if story.letters.find(credit[4:]) != -1:
            credit_string += _('Letters')+": "+story.letters
        if story.editor.find(credit[4:]) != -1:
            credit_string += _('Editor')+": "+story.editor
        return credit_string
    else:
        return ""


# we may want to move this somewhere else
def is_visible_credit(credit):
    """ Check if credit exists and if we want to show it.  Could add
    further conditions for not showing the credit here."""
     
    if credit:
        if credit.lower != 'none':
            return True
    return False


def show_details(story,credit):
    """ For showing the credits on the issue page."""
    
    if credit == 'script':
        if is_visible_credit(story.script):
            return story.script + " (" + _('Script') + "), "
    elif credit == 'pencils':
        if is_visible_credit(story.pencils):
            return story.pencils + " ("+_('Pencils')+"), "
    elif credit == 'inks':
        if is_visible_credit(story.inks):
            return story.inks + " ("+_('Inks')+"), "
    elif credit == 'colors':
        if is_visible_credit(story.colors):
            return story.colors +" ("+_('Colors')+"), "
    elif credit == 'letters':
        if is_visible_credit(story.letters):
            return story.letters +" ("+_('Letters')+")."
    elif credit == 'editor':
        if is_visible_credit(story.editor):
            return story.editor +" ("+_('Editor')+")."
    elif credit == 'job':
        return _('Job number')+": "+story.job_number
    else:
        return ""
    return ""


def parse_reprint_fr(reprints):
    """ parse a reprint entry starting with "fr." Often found in older indices.
    Don't trust this parsing too much."""

    try:#for format: fr. seriesname #nr (issue date) date unused for parsing
        position = reprints.find(' #')
        series = reprints[3:position].strip()
        #print series 
        position += 2
        string = reprints[position:]
        position = string.find('(')
        number = string[:position].strip()
        #print number
        results = Issue.objects.all()
        results = results.filter(series__name__icontains = series)
        results = results.filter(number__exact = number)
        #print results.count()
    except:
        pass
        
    if results.count() == 0:
        try:#for format: from seriesname #nr (issue date) date unused for parsing
            #and for format: from seriesname #nr
            position = reprints.find(' #')
            series = reprints[4:position].strip()
            #print series 
            position += 2
            string = reprints[position:]
            position = string.find('(')
            if position > 0:
                number = string[:position].strip()
            elif string.isdigit():#we don't even have (issue date)
                number = string
            #print number
            results = Issue.objects.all()
            results = results.filter(series__name__icontains = series)
            results = results.filter(number__exact = number)
            #print results.count()
        except:
            pass
    
    if results.count() == 1:
        issue = results[0]
        link = "<a href=\"/gcd/issue/"+str(issue.id)+"/\">"
        link += "From " + esc(issue.series.name) 
        link += " (" + esc(issue.series.publisher) + ", "
        link += esc(issue.series.year_began) + " series) #"
        link += esc(issue.number) + "</a>"
        return link
    else:
        return None

def parse_reprint(reprints, from_to):
    """ parse a reprint entry, first for our standard, them some for
    other common version.  We may turn the others off or add even more. ;-)"""
    notes = None
    
    if reprints.startswith(from_to):
        try:#our preferred format: seriesname (publisher, year <series>) #nr
            position = reprints.find(' (')
            series = reprints[len(from_to):position].strip()
            #print series 
            string = reprints[position+2:]
            position = string.find(', ')
            publisher = string[:position].strip()
            #print publisher
            position+=2
            string = string[position:]
            year = string[:4]
            #print year
            string = string[4:]
            position = string.find(' #')+2
            string = string[position:]
            if string.isdigit():
                number = string
            else:
                number = string[:string.find(' ')].strip('.')
            #print number
            position = string.find('[')
            if position > 0:
                notes = string[position:]
            results = Issue.objects.all()
            results = results.filter(series__name__icontains = series)
            results = results.filter(series__publisher__name__icontains 
            = publisher)
            results = results.filter(series__year_began__exact = int(year))
            results = results.filter(number__exact = number)
        except:
            pass
        
        if results.count() == 0:
            try:#for format: seriesname (year series) #nr
                position = reprints.find(' (')
                series = reprints[len(from_to):position].strip()
                #print series 
                position += 2
                string = reprints[position:]
                year = string[:4]
                #print year
                string = string[4:]
                position = string.find(' #')+2
                string = string[position:]
                #print string
                if string.isdigit():
                    number = string
                else:
                    number = string[:string.find(' ')]
                #print number
                position = string.find('[')
                if position > 0:
                    notes = string[position:]
                results = Issue.objects.all()
                results = results.filter(series__name__icontains = series)
                results = results.filter(series__year_began__exact = int(year))
                results = results.filter(number__exact = number)
            except:
                pass
        if results.count() == 0:
            try:#for format: seriesname #nr(publisher, year <series>)
                position = reprints.find(' #')
                series = reprints[len(from_to):position].strip()
                #print series 
                position += 2
                string = reprints[position:]
                position = string.find('(')
                number = string[:position].strip()
                #print number
                position += 1
                string = string[position:]
                position = string.find(', ')
                publisher = string[:position].strip()
                #print publisher
                position += 2
                string = string[position:]
                year = string[:4]
                position = string.find('[')
                if position > 0:
                    notes = string[position:]
                #print year
                results = Issue.objects.all()
                results = results.filter(series__name__icontains = series)
                results = results.filter(series__publisher__name__icontains 
                = publisher)
                results = results.filter(series__year_began__exact = int(year))
                results = results.filter(number__exact = number)
            except:
                pass
        if results.count() == 0:
            try:#for format: seriesname #nr (year)
                position = reprints.find(' #')
                series = reprints[len(from_to):position].strip()
                #print series 
                position += 2
                string = reprints[position:]
                position = string.find('(')
                number = string[:position].strip()
                #print number
                position += 1
                string = string[position:]
                year = string[:4]
                position = string.find('[')
                if position > 0:
                    notes = string[position:]
                #print year
                results = Issue.objects.all()
                results = results.filter(series__name__icontains = series)
                results = results.filter(series__year_began__exact = int(year))
                results = results.filter(number__exact = number)
            except:
                pass
        
        if results.count() == 1:
            issue = results[0]
            link = "<a href=\"/gcd/issue/"+str(issue.id)+"/\">"
            link += from_to.capitalize() + " " + esc(issue.series.name) 
            link += " (" + esc(issue.series.publisher) + ", "
            link += esc(issue.series.year_began) + " series) #"
            link += esc(issue.number) + "</a>"
            if  notes:
                link += " " + esc(notes)
            return link
        else:
            return None


def show_reprint(story):
    """ Filter for reprint line.  First step into database migration."""
    
    if story.reprints:
        reprint = ""
        for string in story.reprints.split(';'):
            string = string.strip()
            for from_to in ("from ","From ","In ","in ",""):
                next_reprint = parse_reprint(string,from_to)
                if next_reprint:
                    if len(reprint) > 0:
                        reprint += '; '
                    reprint += next_reprint
                    break
            if next_reprint == None:
                next_reprint = parse_reprint_fr(string)
                if len(reprint) > 0:
                    reprint += '; '
                if next_reprint:
                    reprint += next_reprint
                else:
                    reprint += esc(string)
        return mark_safe("<p><b>Reprinted:</b> " + reprint + "</p>")
    else:
        return ""
        
register.filter(show_credit)
register.filter(show_details)
register.filter(show_reprint)
