from django import template
from django.utils.translation import ugettext as _
from django.utils.safestring import mark_safe
from django.utils.html import conditional_escape as esc

from apps.gcd.models import Issue,Story

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

# list checks we should/could do when we use this for the migration
# - keydate of from should be smaller, keydate of to should be larger
# - if no keydate exists on one side maybe check on series year
# - search for title match of story as well
# - search for matching page count
# - search for reprint link back

# other stuff to consider in the display
# - sort the reprints according to keydate
# - sort domestic/foreign reprints

def find_reprint_sequence_in_issue(from_story,to_issue):
    '''look for sequence in <to_issue> which fits <from_story>'''
    
    results = Story.objects.all()
    results = results.filter(issue__id = to_issue)
    results = results.filter(title__icontains = from_story.title.strip().strip('!').strip('.'))
    if (results.count() > 1):
        results = results.filter(page_count = from_story.page_count)
    if (results.count() == 1):
        return results[0].sequence_number
    #for i in range(results.count()):
        #print results[i].title
    return -1


def generate_reprint_link(from_story, to_issue, from_to):
    ''' generate reprint link to_issue'''
    
    link = "<a href=\"/gcd/issue/"+str(to_issue.id)
    sequence = find_reprint_sequence_in_issue(from_story,to_issue.id)
    if (sequence >= 0):
        link += "/#" + esc(sequence) +"\">"
    else:
        link += "/\">"
    link += esc(from_to) + esc(to_issue.series.name) 
    link += " (" + esc(to_issue.series.publisher) + ", "
    link += esc(to_issue.series.year_began) + " series) #"
    link += esc(to_issue.number) + "</a>"
    link += " (" + esc(to_issue.publication_date) + ")"
    return link
    

def parse_reprint_fr(reprints):
    """ parse a reprint entry starting with "fr." Often found in older indices.
    Don't trust this parsing too much."""

    try:# for format: fr. seriesp #nr (issue date) date unused for parsing
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
            results = Issue.objects.all()
            results = results.filter(series__name__icontains = series)
            results = results.filter(number__exact = number)
            if year:
                results = results.filter(key_date__icontains = year)
            #print results.count()
        except:
            pass
    
    return results


def parse_reprint(reprints, from_to):
    """ parse a reprint entry, first for our standard, them some for
    other common version.  We may turn the others off or add even more. ;-)"""
    notes = None
    
    if reprints.lower().startswith(from_to):
        try:# our preferred format: seriesname (publisher, year <series>) #nr
            position = reprints.find(' (')
            series = reprints[len(from_to):position].strip().strip("The ").strip("the ")
            string = reprints[position+2:]
            after_series = string # use in other formats
            #print series 
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
            #print number
            results = Issue.objects.all()
            results = results.filter(series__name__icontains = series)
            results = results.filter(series__publisher__name__icontains 
            = publisher)
            results = results.filter(series__year_began__exact = int(year))
            results = results.filter(number__exact = number)
        except:
            pass
        
        if results.count() == 0 or results.count() > 10:
            try:# our typoed format: seriesname (publisher year <series>) #nr
                # use series from before
                string = after_series
                position = string.find(' 1')
                if position > 0:
                    publisher = string[:position].strip()
                else:
                    position = string.find(' 2')
                    publisher = string[:position].strip()                    
                #print publisher
                position+=1
                string = string[position:]
                year = string[:4]
                #print year
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
                #print number
                if position > 0 and position_end > position:
                    notes = string[position:position_end+1]
                results = Issue.objects.all()
                results = results.filter(series__name__icontains = series)
                results = results.filter(series__publisher__name__icontains 
                = publisher)
                results = results.filter(series__year_began__exact = int(year))
                results = results.filter(number__exact = number)
            except:
                pass
        
        if results.count() == 0 or results.count() > 10:
            try:# for format: seriesname (year series) #nr
                # use series from before
                string = after_series
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
                position_end = string.find(']')
                if position > 0 and position_end > position:
                    notes = string[position:position_end+1]
                results = Issue.objects.all()
                results = results.filter(series__name__icontains = series)
                results = results.filter(series__year_began__exact = int(year))
                results = results.filter(number__exact = number)
            except:
                pass
                
        if results.count() == 0 or results.count() > 10:
            try:# for format: seriesname #nr(publisher, year <series>)
                position = reprints.find(' #')
                series = reprints[len(from_to):position].strip().strip("The ").strip("the ")
                #print series 
                position += 2
                string = reprints[position:]
                after_series = string
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
                
        if results.count() == 0 or results.count() > 10:
            try:# for format: seriesname #nr (year)
                # use series from before                
                string = after_series
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
        return results
    else:
        return Issue.objects.none()


def show_reprint(story):
    """ Filter for reprint line.  First step into database migration."""
    
    if story.reprints:
        reprint = ""
        for string in story.reprints.split(';'):
            string = string.strip()
            for from_to in ("from ","in ",""):
                next_reprint = parse_reprint(string, from_to)
                if next_reprint.count() > 1 and next_reprint.count() <= 15:
                    a = []
                    for i in range(next_reprint.count()):
                        nr = find_reprint_sequence_in_issue(story,
                                                         next_reprint[i].id)
                        if (nr > 0):
                            a.append(i)
                    if len(a) == 1:
                        next_reprint = next_reprint.filter(id =
                                                next_reprint[a[0]].id)
                if next_reprint.count() == 1:
                    if len(reprint) > 0:
                        reprint += '\n'
                    reprint += generate_reprint_link(story,next_reprint[0],from_to)
                    break
            if next_reprint.count() != 1:
                next_reprint = parse_reprint_fr(string)
                if len(reprint) > 0:
                    reprint += '\n'
                if next_reprint.count() > 1 and next_reprint.count() <= 15:
                    a = []
                    for i in range(next_reprint.count()):
                        nr = find_reprint_sequence_in_issue(story,
                                                         next_reprint[i].id)
                        if (nr > 0):
                            a.append(i)
                    if len(a) == 1:
                        next_reprint = next_reprint.filter(id =
                                                next_reprint[a[0]].id)
                if next_reprint.count() == 1:
                    reprint += generate_reprint_link(story,next_reprint[0],"from ")
                else:
                    reprint += esc(string)
        return mark_safe("<p><b>Reprinted:</b><br> " + reprint + "</p>")
    else:
        return ""
        
register.filter(show_credit)
register.filter(show_details)
register.filter(show_reprint)
