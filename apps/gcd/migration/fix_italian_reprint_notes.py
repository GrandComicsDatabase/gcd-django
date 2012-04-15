# -*- coding: utf-8 -*-
from django.utils.encoding import smart_unicode as uni
from django.db.models import Q
from django.db import transaction, connection, settings
from django.contrib.auth.models import User

from apps.gcd.models import Story, Issue
from apps.gcd.migration import migrate_reserve, do_auto_approve

anon = User.objects.get(username=settings.ANON_USER_NAME)

###########################
# fix Italian series
###########################
def find_italian_disney(string, own_name, own_number):
    '''
    find series name and replace by series name (publisher, year)

    many of the Italian Disneys include the issue iself in the reprint notes,
    filter these out via <own_name> and <own_number>
    '''

    not_in_db = ['Maestri Disney','I Maestri Disney','Super Disney','Paperino',
                'Noi due Paperina e Minni',"Piu' Disney",'Disney Time','Albi d\'oro',
                "Zio Paperone",'Capolavori Disney','I classici del fumetto',
                'Speciale Disney','Le Grandi Parodie Disney','Paperino d\'oro',
                'Don Rosa e il rinascimento Disneyano','Omaggio Fruttolo','Ridi Topolino',
                'Oscar Mondadori (Oscar Fumetto)','Il meglio di...','Nel Regno di Topolino',
                'Topolino Sport 1993','Cartonati Disney','GM - Giovani Marmotte',
                'Il Messaggero','Topostrips','Supplemento al Giornale: Topolino',
                'Albi Nerbini Anteguerra','Special Mongo','Mickey Mouse Mystery Magazine',
                'Le Grandi Storie di Walt Disney','Paper Fantasy','Topolino adventure',
                'I Miti Mondadori','Risatissima','Paper Motori','Magico Natale',
                'Tesori','Le Grandi Parodie Mondadori','Super Miti Mondadori',
                'Cartonatoni Disney']
    d = string.strip().split(' ')
    direction = ''
    if d[0] == u'in':
        direction = 'in '
        d.pop(0)
    elif d[0] == u'from':
        direction = 'from '
        d.pop(0)
    series = ' '.join(d[0:-1])
    if series.find(own_name) >= 0:
        if int(d[-1]) == own_number:
            return None
        elif int(d[-1]) > own_number:
            direction = 'in '
        else:
            direction = 'from '
    if series.find('Topolino (Libretto)') >= 0 or series.find('Topolino') == 0:
        try:
            if int(d[-1]) < 1702:
                return direction + 'Topolino (Arnoldo Mondadori, 1949 series) #' + d[-1]
            else:
                return direction + 'Topolino (Walt Disney Company Italia, 1988 series) #' + d[-1]
        except:
            return direction + 'Topolino (Arnoldo Mondadori, 1949 series) #' + d[-1]
    elif series.find('I Classici di Walt Disney') >= 0:
        if series.find('prima') >= 0:
            return direction + 'I Classici di Walt Disney (Arnoldo Mondadori, 1957 series) #[' + d[-1] +']'
        elif int(d[-1]) < 140:
            return direction + 'I Classici di Walt Disney (Arnoldo Mondadori, 1977 series) #' + d[-1]
        else:
            return direction + 'I Classici di Walt Disney (Walt Disney Company Italia, 1988 series) #' + d[-1]
    elif series.find('Classici Walt Disney seconda serie') >= 0:
        return direction + 'I Classici di Walt Disney (Arnoldo Mondadori, 1977 series) #' + d[-1]
    elif series.find('Grandi Classici Disney') >= 0:
        if int(d[-1]) < 35:
            return direction + 'I Grandi Classici Disney (Arnoldo Mondadori, 1980 series) #' + d[-1]
        else:
            return direction + 'I Grandi Classici Disney (Walt Disney Company Italia, 1988 series) #' + d[-1]
    elif series.find('Albi della Rosa') >= 0:
        if int(d[-1]) < 635:
            return direction + 'Albi della Rosa (Arnoldo Mondadori, 1954 Series) #' + d[-1]
        else:
            return direction + 'Albi di Topolino (Arnoldo Mondadori, 1967 series) #' + d[-1]
    elif series.find('Topomistery') >= 0:
        return direction + "Topomistery (Walt Disney Company Italia, 1991 Series) #" + d[-1]
    elif series.find('Mega ') >= 0:
        num = int(d[-1])
        if num < 379:
            return direction + 'Mega Almanacco (Arnoldo Mondadori, 1985 Series) #'  + d[-1]
        elif num < 424:
            return direction + 'iMega Almanacco (Walt Disney Company Italia, 1988 Series) #'  + d[-1]
        elif num < 521:
            return direction + 'Mega 2000 (Walt Disney Company Italia, 1992 Series) #' + d[-1]
        else:
            return direction + 'Mega 3000 (Walt Disney Company Italia, 2000 Series) #' + d[-1]
    elif series.find('Paperino Mese / Paperino') >= 0:
        num = int(d[-1])
        if num < 67:
            fail
        elif num < 98:
            return direction + 'Paperino Mese (Arnoldo Mondadori Editore, 1986 Series) #' + d[-1]
            #print i.issue
        else:
            return direction + 'Paperino Mese (Walt Disney Company Italia, 1988 Series) #' + d[-1]
            #print i.issue
    elif series.find('Albi di Topolino nuova serie') >= 0:
        return direction + 'Albi di Topolino (Walt Disney Company Italia, 1993 Series) #' + d[-1]
    elif series.find('Paperinik e altri supereroi') >= 0:
        return direction + 'Paperinik (Walt Disney Company Italia, 1993 Series) #' + d[-1]
    elif series.find('Tutto Disney') >= 0:
        return direction + 'Tutto Disney (Walt Disney Company Italia, 1995 Series) #' + d[-1]
    elif series.find('Super Almanacco (di) Paperino') >= 0:
        if int(d[-1]) < 43:
            return direction + 'Super Almanacco Paperino (Arnoldo Mondadori Editore, 1980 Series) #' + d[-1]
        else:
            return direction + 'Super Almanacco di Paperino (Arnoldo Mondadori Editore, 1984 Series) #' + d[-1]
    elif series.find('Super Almanacco Paperino') >= 0:
        return direction + 'Super Almanacco Paperino (Arnoldo Mondadori Editore, 1976 Series) #' + d[-1]
    elif series.find('Almanacco Topolino nuova serie') >= 0:
        return direction + 'Almanacco Topolino (Walt Disney Company Italia, 1999) #' + d[-1]
    elif series.find('Almanacco Topolino') >= 0:
        return direction + 'Almanacco Topolino (Arnoldo Mondadori, 1957) #' + d[-1]
    elif series.find('Paperino & Co. / Paperino') >= 0:
        if int(d[-1]) < 57:
            return direction + 'Paperino & C. (Arnoldo Mondadori, 1981) #' + d[-1]
        else:
            return direction + 'Paperino (Arnoldo Mondadori, 1982) #' + d[-1]
    elif series == '' and d[0].strip().find('ABB') == 0:
        return direction + 'Omaggio Abbonati #' + d[0][3:]
    elif series.strip() in not_in_db:
        return direction + series.strip() + ' #' + d[-1]
    else:
        # might find out what these are...
        print "yes", series, string, d
#        if series in ['MMORIG1','SPTL','']:
#            return None
        return string

def do_italian_fixing(series_name, i):
    # some issues of some series have been corrected
    if i.reprint_notes.find('#') > 0:
        return
    reprints = None
    c = i.reprint_notes.split(',')
    for j in c:
        if j.strip != '':
            string = find_italian_disney(j,series_name,int(i.issue.number.strip('[]')))
            if string:
                if reprints:
                    reprints += "; " + string
                else:
                    reprints = string
    if reprints:
        i.reprint_notes = reprints
    else:
        i.reprint_notes = ''
    i.save()

def fix_italian(series_id, series_name):
    changes = []
    issues = Issue.objects.filter(series__id = series_id)
    for issue in issues:
        c = migrate_reserve(issue, 'issue', 'to fix reprint notes')
        if c:
            crs = c.storyrevisions.exclude(reprint_notes="").exclude(reprint_notes__icontains='?')
            changed = False
            for cr in crs:
                do_italian_fixing(series_name, cr)
                if not changed:
                    cr.compare_changes()
                    if cr.is_changed:
                        changed = True
                cr.save()
            if changed:
                changes.append((c, True))
            else:
                print "nothing changed in ", c
                c.discard(anon)
                c.delete()
        else:
            print "%s is reserved" % issue
        if len(changes) > 10:
            do_auto_approve(changes, 'fixing reprint notes')
            changes = []
    do_auto_approve(changes, 'fixing reprint notes')


def fix_italian_series_687():
    changes = []
    do_save = True
    issues = Issue.objects.filter(series__id = 687)
    for issue in issues:
        if issue.active_stories().exclude(reprint_notes="").exclude(reprint_notes__icontains='?').count():
            c = migrate_reserve(issue, 'issue', 'to fix reprint notes')
            if c:
                crs = c.storyrevisions.exclude(reprint_notes="").exclude(reprint_notes__icontains='?')
                changed = False
                # fix missing semicolons
                for cr in crs:
                    string = cr.reprint_notes.replace(' e ristampata su ','; ristampata su ')
                    if string.find(' e su ') > 0:
                        string = string.replace(' e su ','; ristampata su ')
                    if string.find(' e ') > 0:
                        string = string.replace(' e ','; ristampata su ')
                    cr.reprint_notes = string
                    cr.save()

                q_obj = Q(reprint_notes__icontains='ristampata su ')  | Q(reprint_notes__icontains='Ristampa da ')
                crs = crs.filter(q_obj)
                for cr in crs:
                    # now split via ';'
                    string = cr.reprint_notes.replace('ristampata su ','in ')
                    string = string.replace('Ristampata su ','in ')
                    string = string.replace('Ristampa su ','in ')
                    string = string.replace('Ristampa da ','from ')

                    e = string.strip().split(';')
                    reprints = None
                    for st in e:
                        d = st.strip().split(' ')
                        series = ' '.join(d[0:-1])

                        try:
                            num = int(d[-1])
                            res = find_italian_disney(st,'',0)
                            if res:
                                result = res
                            else:
                                result = series + " #" + str(num)
                        except:
                            result = st
                        if reprints:
                            reprints += "; " + result
                        else:
                            reprints = result
                    #print cr.reprint_notes, reprints
                    if reprints:
                        cr.reprint_notes = reprints
                    else:
                        cr.reprint_notes = ''
                    if not changed:
                        cr.compare_changes()
                        if cr.is_changed:
                            changed = True
                    cr.save()
                if changed:
                    changes.append((c, True))
                else:
                    print "nothing changed in ", c
                    c.discard(anon)
                    c.delete()
            else:
                print "%s is reserved" % issue
            if len(changes) > 10:
                do_auto_approve(changes, 'fixing reprint notes')
                changes = []
    do_auto_approve(changes, 'fixing reprint notes')


def fix_italian_series():
    fix_italian(7536, 'Albi di Topolino nuova serie')
    fix_italian(7593, 'Tutto Disney')
    fix_italian(7540, 'Almanacco Topolino')
    fix_italian(7539, 'Almanacco Topolino nuova serie')
    fix_italian(3706, 'Grandi Classici Disney')
    fix_italian(7569, 'Grandi Classici Disney')
    fix_italian(7566, 'I Classici di Walt Disney prima serie')
    fix_italian_series_687()

if __name__ == '__main__':
    fix_italian_series()
