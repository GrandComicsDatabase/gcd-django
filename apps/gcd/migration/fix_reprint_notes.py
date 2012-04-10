# -*- coding: utf-8 -*-
import sys

from django.db import transaction, connection, settings
from django.contrib.auth.models import User
from django.utils.encoding import smart_unicode as uni
from django.utils.encoding import smart_str

from apps.gcd.models import Issue
from apps.gcd.migration import migrate_reserve, do_auto_approve

anon = User.objects.get(username=settings.ANON_USER_NAME)

#@transaction.commit_on_success
def fix_reprint_notes(issues, old_reprint_note, new_reprint_note, check_double_semi=False, exact=False):
    changes = []
    for i in issues:
        c = migrate_reserve(i, 'issue', 'to fix reprint notes')
        if c:
            ir = c.issuerevisions.all()[0]
            if exact:
                crs = c.storyrevisions.filter(reprint_notes=old_reprint_note)
            else:
                crs = c.storyrevisions.filter(reprint_notes__icontains=old_reprint_note)
            changed = False
            for cr in crs:
                cr.reprint_notes = cr.reprint_notes.replace(old_reprint_note,
                                                            new_reprint_note)
                if check_double_semi:
                    cr.reprint_notes = cr.reprint_notes.replace(';;', ';')
                    cr.reprint_notes = cr.reprint_notes.replace('; ;', ';')
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
            print "%s is reserved" % i
        if len(changes) > 10:
            do_auto_approve(changes, 'fixing reprint notes')
            changes = []
    do_auto_approve(changes, 'fixing reprint notes')

def fix_reprint_notes_global(old_reprint_note, new_reprint_note):
    issues = Issue.objects.filter(story__reprint_notes__icontains=old_reprint_note,
                                  story__deleted=False).filter(deleted=False).distinct()
    print smart_str("cnt %d: %s" % (issues.count(), old_reprint_note.encode("utf-8")))
    fix_reprint_notes(issues, old_reprint_note, new_reprint_note)

def fix_reprint_notes_series(series_id, old_reprint_note, new_reprint_note, check_double_semi=False):
    issues = Issue.objects.filter(story__reprint_notes__icontains=old_reprint_note,
                                  story__deleted=False,
                                  series__id=series_id).filter(deleted=False).distinct()
    print smart_str("cnt %d: %s" % (issues.count(), old_reprint_note.encode("utf-8")))
    fix_reprint_notes(issues, old_reprint_note, new_reprint_note, check_double_semi)

#@transaction.commit_on_success
def fix_all_reprint_notes():
    reprint_notes = [
    ['Marvel Masterworks: Golden Age USA Comics (Marvel, 2007 series)','Marvel Masterworks: Golden Age U.S.A. Comics (Marvel, 2007 series)'],
    ['(Editorial Planeta DeAgostini S.A.','(Planeta DeAgostini'],
    ['Uncle Scrooge (Gold Key, 1962 series)', 'Uncle Scrooge (Gold Key, 1963 series)'],
    ['Uncle Scrooge (Gold Key, 1962 Series)', 'Uncle Scrooge (Gold Key, 1963 series)'],
    ['Drawn and Quarterly','Drawn & Quarterly'],
    ['Essential Wolverine #','Essential Wolverine (Marvel, 1996 series) #'],
    ['Apache Kid (Marvel, 1951 series)','Apache Kid (Marvel, 1950 series)'],
    ['Ghost Stories #','Ghost Stories (Dell, 1962 series) #'],
    ['in Tip Top Comic Monthly (K. G. Murray, 1963 series)','in Tip Top Comic Monthly (K. G. Murray, 1965 series)'],
    ['from Jessy (Panini Verlag, 2004 series)','from Jessy (Panini, 2004 series)'],
    ['from Jessy (Panini Verlag, 2004) #','from Jessy (Panini, 2004 series) #'],
    ['World\'s Finest Comics (DC, 1940 Series)','World\'s Finest Comics (DC, 1941 Series)'],
    ['Superman: The World\'s Finest Comics Archives','Superman: The World\'s Finest Archives'],
    ['(DC/Vertigo, ','(DC, '],
    ['Superman(DC,1939 Series)','Superman (DC, 1939 Series)'],
    ['In Essential Ghost Rider #','in Essential Ghost Rider (Marvel, 2005 series) #'],
    ['from Captain Marvel Adventures #','from Captain Marvel Adventures (Fawcett, 1941 Series) #'],
    ['X-Men (1963 series)','X-Men (Marvel, 1963 series)'],
    ['(Ediciones Zinco, ','(Zinco, '],
    ['EC Archives:  Two-Fisted Tales (Gemstone, 2007 series)','EC Archives: Two-Fisted Tales (Gemstone, 2007 series)'],
    ['rom Commando #', 'rom Commando (D.C. Thomson, 1961) #'],
    [uni('från Detective Comics (DC, 1939)'),uni('från Detective Comics (DC, 1937)')],
    ['reprinted from ','from '],
    ['Reprinted from ','from '],
    [') in Kamp Serien #', '); in Kamp Serien (Se-Bladene, 1964 Series) #'],
    [') in Kamp serien #', '); in Kamp Serien (Se-Bladene, 1964 Series) #'],
    [') in Kamp Spesial #', '); in Kamp Spesial (Se-Bladene, 1986 Series) #'],
    ['in Kamp Serien #', 'in Kamp Serien (Se-Bladene, 1964 Series) #'],
    ['Kamp Spesial #', 'Kamp Spesial (Se-Bladene, 1986 Series) #'],
    ['\r\nfrom Harry die bunte Jugendzeitung (Lehning, 1958 series)#', '; from Harry die bunte Jugendzeitung (Lehning, 1958 series) #'],
    ['eries)#','eries) #'],
    ['Superman Extra (DC, 1980 Serie)','Superman Extra (Ehapa, 1980 Serie)'],
    ['Superman Taschenbuch (DC, 1976 Serie)','Superman Taschenbuch (Ehapa, 1976 Serie)'],
    [', Superman Taschenbuch (','; Superman Taschenbuch ('],
    ['Batman(DC,','Batman (DC, '],
    ['.Seuqence', '.Sequence'],
    ['(AC Comics, ','(AC, '],
    [' (DC 19',' (DC, 19'],
    [' (DC 20',' (DC, 20'],
    [' (Marvel 19',' (Marvel, 19'],
    [' (Marvel 20',' (Marvel, 20'],
    ['From DC Super Stars [DC, 1976 Series)', 'From DC Super Stars (DC, 1976 Series)'],
    ['Black Cat (Harvey; 1946 series) #','Black Cat (Harvey, 1946 series) #'],
    ['from Fables (DC, 2003 series) #','from Fables (DC, 2002 series) #'],
    ['Testament (DC, 2005 series) #','Testament (DC, 2006 series) #'],
    ['from Quantum And Woody (Acclaim, 1997 Series) #','from Quantum & Woody (Acclaim, 1997 Series) #'],
    ['n Nexus Archives (Dark Horse Books, 2005 series) #','n Nexus Archives (Dark Horse, 2006 series) #'],
    ['Flash Album, The (K. G. Murray, 1978 series)','Flash Album, The (K. G. Murray, 1976 series)'],
    ['Essential X-Men #','Essential X-Men (Marvel, 1996 series) #'],
    ['Marvel\'s Greatest Comics (Marvel, 1961 series)','Marvel\'s Greatest Comics (Marvel, 1969 series)'],
    ['in Superboy (Ehapa Verlag, 1980 series) #','in Superboy (Egmont, 1980 series) #'],
    ['Da DC: THE NEW FRONTIER #','Da DC: The New Frontier (DC, 2004 series) #'],
    ['Serie-pocket (Semic AS, 1975 series) #38','Serie-pocket (Semic AS, 1977 series) #38'],
    ['in Showcase Presents Martian Manhunter  (DC, 2007 series) #','in Showcase Presents: Martian Manhunter (DC, 2007 series) #'],
    ['Marvel Masterworks Atlas Era Heroes (Marvel, 2007 series) #','Marvel Masterworks: Atlas Era Heroes (Marvel, 2007 series) #'],
    ['Da XENOZOIC TALES #','Da Xenozoic Tales (Kitchen Sink, 1987) #'],
    ['Super-Team-Family','Super-Team Family'],
    ['From Flash, The (DC, 1959 Series) #300, August 1981, 1.Sequence', 'From Flash, The (DC, 1959 Series) #300, August 1981, 2.Sequence'],
    [uni("All-New Collectors´ Edition"), uni("All-New Collectors' Edition")],
    [' (Marvel/DC, 19', ' (Marvel / DC, 19'],
    ['World of Krypton [DC, 1979 ', 'World of Krypton (DC, 1979 '],
    ['DC Comics Persents (DC, 1978 Series)', 'DC Comics Presents (DC, 1978 Series)'],
    ['from from The New Adventures of Superboy', 'from The New Adventures of Superboy'],
    ['from from Superboy (DC, 1949 Series) #225', 'from Superboy (DC, 1949 Series) #225'],
    ['From, Justice League of America','From Justice League of America'],
    ["from, World's Finest Comics", "from World's Finest Comics"],
    ['rom TOP Comics Blitzmann [BSV - Williams, 1970 Serie]', 'rom TOP Comics Blitzmann (BSV - Williams, 1970 Serie)'],
    ['Superboy(DC,1949 Series)', 'Superboy (DC, 1949 Series)'],
    ['Superman Superband (Ehapa,1974 Serie)', 'Superman Superband (Ehapa, 1974 Serie)'],
    ['Batman Supermand (Ehapa, 1974 ', 'Batman Superman (Ehapa, 1974 '],
    ['from Legion of Superheroes, the [DC, 1980 Series] # ', 'from The Legion of Super-heroes (DC, 1980 Series) #'],
    ['from Superboy Spectacular [DC', 'from Superboy Spectacular (DC'],
    [',1.Sequence', ', 1.Sequence'],
    [',2.Sequence', ', 2.Sequence'],
    [',3.Sequence', ', 3.Sequence'],
    [',5.Sequence', ', 5.Sequence'],
    [uni("Superman´s Pal,Jimmy Olsen"), "Superman's Pal, Jimmy Olsen"],
    ['Simon & Schuster', 'Simon and Schuster'],
    ['Acts of Vengeance Omnibus (Marvel, 2010 series)', 'Acts of Vengeance Omnibus (Marvel, 2011 series)'],
    ['(Semic Press AB, ', '(Semic, '],
    ['2099 A.D. #1 (Marvel Italia, 1995)', '2099 A.D. (Marvel Italia, 1995) #1'],
    ['2099 A.D. #2 (Marvel Italia, 1996)', '2099 A.D. (Marvel Italia, 1995) #2'],
    ['2099 A.D. #3 (Marvel Italia, 1996)', '2099 A.D. (Marvel Italia, 1995) #3'],
    ['2099 A.D. #4 (Marvel Italia, 1996)', '2099 A.D. (Marvel Italia, 1995) #4'],
    ['2099 A.D. #5 (Marvel Italia, 1996)', '2099 A.D. (Marvel Italia, 1995) #5'],
    ['2099 A.D. #6 (Marvel Italia, 1996)', '2099 A.D. (Marvel Italia, 1995) #6'],
    ['2099 A.D. #7 (Mavel Italia, 1996)', '2099 A.D. (Marvel Italia, 1995) #7'],
    ['2099 A.D. #8 (Marvel Italia, 1996)', '2099 A.D. (Marvel Italia, 1995) #8'],
    ['2099 A.D. #9 (Marvel Italia, 1996)', '2099 A.D. (Marvel Italia, 1995) #9'],
    ['2099 A.D. #10 (Marvel Italia, 1996)', '2099 A.D. (Marvel Italia, 1995) #10'],
    ['2099 A.D. #11 (Marvel Itaia, 1996)', '2099 A.D. (Marvel Italia, 1995) #11'],
    ['2099 A.D. #12 (Marvel Italia, 1996)', '2099 A.D. (Marvel Italia, 1995) #12'],
    ['2099 Special #13 (Marvel Italia, 12/1996)', '2099 Special (Marvel Italia, 1994) #13'],
    ['2099 Special #15 (Marvel Italia, 04/1997)', '2099 Special (Marvel Italia, 1994) #15'],
    ['2099 Special #16 (Marvel Italia, 06/1997)', '2099 Special (Marvel Italia, 1994) #16'],
    ['2099 Special #17 (Marvel Italia, 08/1997)', '2099 Special (Marvel Italia, 1994) #17'],
    ['Stormwatch:  A Finer World (DC, 1999 series) #[nn]', 'Stormwatch: A Finer World (DC, 1999 series) #[nn]'],
    ['n Fantastic Four [Trade Paperback] (Marvel, 2003 ', 'n Fantastic Four (Marvel, 2003 '],
    ['n The Batman Archives (DC, 1990 series)', 'n Batman Archives (DC, 1990 series)'],
    ['n Batman Archives, The (DC, 1990 series)', 'n Batman Archives (DC, 1990 series)'],
    ['n The Batman archives (DC, 1990 series)', 'n Batman Archives (DC, 1990 series)'],
    ['Showcase Presents Martian Manhunter (DC, 2007 series)', 'Showcase Presents: Martian Manhunter (DC, 2007 series)'],
    ['Boy Commandos by Joe Simon and Jack Kirby, The (DC, 2010 series)', 'The Boy Commandos by Joe Simon & Jack Kirby (DC, 2010 series)'],
    ['Greatest Batman Stories Ever Told, The (DC, 1988 series) #nn [1]', 'The Greatest Batman Stories Ever Told (DC, 1988 series) #[nn] [1]'],
    [uni(' (Egmont Serieförlaget AB, '), ' (Egmont, '],
    ['Magic Book (Magic Press, 2002 series)', 'Magic Book (Magic Press, 2000 series)'],
    ['(BSV-Williams,', '(BSV - Williams,'],
    ['Marvel Masterworks: Spider-Man (', 'Marvel Masterworks: The Amazing Spider-Man ('],
    ["Uomo Ragno, L' [Collana Super-Eroi] (", "L' Uomo Ragno [Collana Super-Eroi] ("],
    ['cover reprinted in G.I. ', 'in G.I. '],
    ['in Starman: Night and Day (DC, 1997 series) #[nn]', 'in Starman (DC, 1995 series) #2'],
    ['Collected Omaha, The (Kitchen Sink Press, Inc., 1987 series) #Volume ', 'The Collected Omaha (Kitchen Sink Press, 1987 series) #'],
    ['(Kitchen Sink Press, Inc., ', '(Kitchen Sink Press, '],
    ['Air Ace Picture Library (Fleetway Publications, 1960 series)', 'Air Ace Picture Library (IPC Magazines, 1960 series)'],
    ['Air Ace Picture Library (Fleetway Publications, 1960)', 'Air Ace Picture Library (IPC Magazines, 1960 series)'],
    [') in Front serien (1967 series) #', '); in Front serien (Williams Forlag, 1967 series) #'],
    [') in Bajonett serien (1967 series) #', '); in Bajonett serien (Williams Forlag, 1967 series) #'],
    [') in Front serien (1965 series) #', '); in Front serien (Illustrerte Klassikere, 1965 series) #'],
    ['from ? (UK) in ', 'from ? (UK); in '],
    ['(Dupuis, 1', '(Editions Dupuis, 1'],
    ['(Dupuis, 2', '(Editions Dupuis, 2'],
    ['(Dargaud, 1', uni('(Dargaud éditions, 1')],
    ['(Dargaud, 2', uni('(Dargaud éditions, 2')],
    ['Lucky Luke (Dargaud Publishing, 1968 series)', uni('Lucky Luke (Dargaud Benelux, 1968 series)')],
    [uni('Lucky Luke (Dargaud éditions, 1968 series)'), 'Lucky Luke (Dargaud Benelux, 1968 series)'],
    ['Lucky Luke (Dupuis Publishing, 1949 series)', uni('Lucky Luke (Editions Dupuis, 1949 series)')],
    ['Vill Vest  (Se-Bladene, 1957 series)', 'Vill Vest (Se-Bladene, 1955 series)'],
    ['; o; ', '; '],
    ['(Oog & Blick, ', '(Oog & Blik, '],
    [uni('from (À Suivre) (Casterman'), uni('from À Suivre (Casterman')],
    ['I.W. Publishing;Super Comics', 'I. W. Publishing; Super Comics'],
    ['I.W. Publishing; Super Comics', 'I. W. Publishing; Super Comics'],
    ]
    for [old, new] in reprint_notes:
        fix_reprint_notes_global(old, new)


    old_reprint_note = ' in Vill Vest (Se-Bladene, 1955 series)'
    new_reprint_note = '; in Vill Vest  (Se-Bladene, 1955 series)'
    issues = Issue.objects.filter(story__reprint_notes__iregex='The Lone Ranger [0-9]', series__id=538,
                                  story__deleted=False).filter(deleted=False).distinct()
    fix_reprint_notes(issues, old_reprint_note, new_reprint_note)

    series_reprint_notes = [
        [7049,'From Superman #','From Superman (DC, 1939 series) #'],
        [7049,'From Detective Comics #','From Detective Comics (DC, 1937 series) #'],
        [7049,'From Batman #','From Batman (DC, 1940 series) #'],
        [7049,'From Superboy #','From Superboy (DC, 1949 series) #'],
        [7049,'From Adventure Comics #','From Adventure Comics (DC, 1938 series) #'],
        [7049,'From Action Comics #','From Action Comics (DC, 1938 series) #'],
        [7049,'From World\'s Finest Comics #','From World\'s Finest Comics (DC, 1941 series) #'],
        [19745,'van ','from '],
        [7538,'da Turok #','da Turok, Son of Stone (Gold Key, 1962) #'],
        [7538, '[Gold Key, USA]',''],
        [20371,'from STAR-STUDDED COMICS #','from Star-Studded Comics (Texas Trio, 1963 series) #'],
        [10458,'from Jonah Hex: Two-Gun Mojo #','from Jonah Hex: Two Gun Mojo (DC, 1993 series) #'],
        [10458,'from Jonah Hex #','from Jonah Hex (DC, 1977 series) #'],
        [3960,'Da KEN PARKER #','da Ken Parker (Sergio Bonelli, 1977 series) #'],
        [7537, 'da Magnus #','da Magnus (Gold Key, 1963) #'],
        [7537, '[GOLD KEY, USA]',''],
        [36980, 'from Wonder Woman Vol.1 (DC, 1942 Series)','from Wonder Woman (DC, 1942 Series)'],
        [18732, '. Sequence', '.Sequence'],
        [3771, 'from BLACK CAT #','from Black Cat (Harvey, 1946 series) #'],
        [687,"Dell Giant Comics","Dell Giant"],
        [687,"Four Color Comic","Four Color"],
        [687,"Walt Disney's Stories and Comics","Walt Disney's Comics and Stories"],
        [7540,'in Walt Disney Stories and Comics (Gemstone, 2003 series) #668 May 2006','in Walt Disney\'s Comics and Stories (Gemstone, 2003 series) #668'],
        [7540,'da Kalle Anka & C:o (Egmont, serie del 1948) #1979-34 (22 Agosto 1979) [Svezia]','da Kalle Anka & C:o (Hemmets Journal, 1957) #34/1979 (22 Agosto 1979)'],
        [7540,'da Kalle Anka & C:o (Egmont, serie del 1948) #1979-35 (29 Agosto 1979) [Svezia]','da Kalle Anka & C:o (Hemmets Journal, 1957) #35/1979'],
        [7566,'Topolino (Libretto) 7/12','Topolino (Libretto) 7, Topolino (Libretto) 8, Topolino (Libretto) 9, Topolino (Libretto) 10, Topolino   (Libretto) 11, Topolino (Libretto) 12'],
        [1701, "Ripley's Believe It or Not True (Gold Key, 1965 series)", "Ripley's Believe It or Not (Gold Key, 1965 series)"]
        ]
    for [series, old, new] in series_reprint_notes:
        fix_reprint_notes_series(series, old, new)

    old_reprint_note = "Chip'N'Dale "
    new_reprint_note = "Chip 'n' Dale (Dell, 1955 series) #"
    issues = Issue.objects.filter(story__reprint_notes__regex="Chip'N'Dale [0-9]", series__id=687,
                                  story__deleted=False).filter(deleted=False).distinct()
    print issues.count(), old_reprint_note
    fix_reprint_notes(issues, old_reprint_note, new_reprint_note)

    old_reprint_note = "Chip'n'Dale "
    new_reprint_note = "Chip 'n' Dale (Dell, 1955 series) #"
    issues = Issue.objects.filter(story__reprint_notes__regex="Chip'n'Dale [0-9]", series__id=687,
                                  story__deleted=False).filter(deleted=False).distinct()
    print issues.count(), old_reprint_note
    fix_reprint_notes(issues, old_reprint_note, new_reprint_note)

    old_reprint_note = "Donald Duck "
    new_reprint_note = "Donald Duck (Dell, 1952 series) #"
    issues = Issue.objects.filter(story__reprint_notes__iregex="Donald Duck [0-9]", series__id=687,
                                  story__deleted=False).filter(deleted=False).distinct()
    print issues.count(), old_reprint_note
    fix_reprint_notes(issues, old_reprint_note, new_reprint_note)

    old_reprint_note = "Mickey Mouse "
    new_reprint_note = "Mickey Mouse (Dell, 1952 series) #"
    issues = Issue.objects.filter(story__reprint_notes__iregex="Mickey Mouse [0-9]", series__id=687,
                                  story__deleted=False).filter(deleted=False).distinct()
    print issues.count(), old_reprint_note
    fix_reprint_notes(issues, old_reprint_note, new_reprint_note)

    old_reprint_note = "Dell Giant "
    new_reprint_note = "Dell Giant (Dell, 1959 series) #"
    issues = Issue.objects.filter(story__reprint_notes__iregex="Dell Giant [0-9]", series__id=687,
                                  story__deleted=False).filter(deleted=False).distinct()
    print issues.count(), old_reprint_note
    fix_reprint_notes(issues, old_reprint_note, new_reprint_note)


    old_reprint_note = "Walt Disney's Comics and Stories "
    new_reprint_note = "Walt Disney's Comics and Stories (Dell, 1940 series) #"
    issues = Issue.objects.filter(story__reprint_notes__iregex="Walt Disney's Comics and Stories [0-9]", series__id=687,
                                  story__deleted=False).filter(deleted=False).distinct()
    print issues.count(), old_reprint_note
    fix_reprint_notes(issues, old_reprint_note, new_reprint_note)

    for i in range(86,126):
        old = '2000 AD (IPC Magazines Ltd, 1977 series) #%d' % i
        new = '2000 AD and Star Lord (IPC Magazines Ltd, 1978 series) #%d' % i
        fix_reprint_notes_global(old, new)

    for i in range(127, 177):
        old = '2000 AD (IPC Magazines Ltd, 1977 series) #%d' % i
        new = '2000 AD and Tornado (IPC Magazines Ltd, 1978 series) #%d' % i
        fix_reprint_notes_global(old, new)

    norwegian_series=[
        [22049,' in Kamp Serien (Se-Bladene, 1964)','; from Kamp Serien (Se-Bladene, 1964)'],
        [22049,' in Kamp serien (Se-Bladene, 1964)','; from Kamp Serien (Se-Bladene, 1964)'],
        [22049,uni(' in På Vingene '),uni('; in På Vingene ')],
        [10459,uni(' in På Vingene '),uni('; in På Vingene ')],
        [28131,' in Vill Vest (Se-Bladene, 1955 series)','; in Vill Vest (Se-Bladene, 1955 series)'],
        [21672,' in Action serien (1976 series)','; in Action serien (Atlantic, 1976 series)'],
        [21672,'from Combat Picture Library (1960','from Combat Picture Library (Micron, 1960'],
        [21672,'from Combat Picture Library #','from Combat Picture Library (Micron, 1960 series) #'],
        [23238,'in Granat serien (1976 series)','; in Granat serien (Atlantic, 1976 series)'],
        [23238,'; Granat serien (1976 series)','; in Granat serien (Atlantic, 1976 series)'],
        [23238,' in Front serien (1967 series)','; in Front serien (Williams, 1967 series)'],
        [23238,'; Action serien (1976 series)','; in Action serien (Atlantic, 1976 series)'],
        [23238,' in Action serien (1976 series)','; in Action serien (Atlantic, 1976 series)'],
        [22804,' in Front serien (1967 series)','; in Front serien (Williams, 1967 series)'],
        [22804,' in Action serien (1976 series)','; in Action serien (Atlantic, 1976 series)'],
        [22804,'; Action serien (1976 series)','; in Action serien (Atlantic, 1976 series)'],
        [22804,'in Granat serien (1976 series)','; in Granat serien (Atlantic, 1976 series)'],
        [22804,'; Granat serien (1976 series)','; in Granat serien (Atlantic, 1976 series)'],
        [23238,'from Combat Picture Library (1960','from Combat Picture Library (Micron, '],
        [21769,'in Granat serien (1976 series)','; in Granat serien (Atlantic, 1976 series)'],
        [21961,'; Action serien (1976 series)','; in Action serien (Atlantic, 1976 series)'],
        [21961,'in Granat serien (1976 series)','; in Granat serien (Atlantic, 1976 series)'],
        [21961,'; Granat serien (1976 series)','; in Granat serien (Atlantic, 1976 series)'],
        [21961,'from Combat Picture Library #','from Combat Picture Library (Micron, 1960 series) #'],
        [21960,'in Action serien (1976 series)','; in Action serien (Atlantic, 1976 series)'],
        [21960,'; Action serien (1976 series)','; in Action serien (Atlantic, 1976 series)'],
        [23447,'in Granat serien (1976 series)','; in Granat serien (Atlantic, 1976 series)'],
        [23447,'; Granat serien (1976 series)','; in Granat serien (Atlantic, 1976 series)'],
        [21672,' in Bajonett serien (1967 series)','; in Bajonett serien (Williams, 1967 series)'],
        [21672,' in Front serien (1967 series)','; in Front serien (Williams, 1967 series)'],
        [21672,' in Front serien (1965 series)','; in Front serien (Illustrerte Klassikere, 1965 series)'],
        [21672,' in Alarm (1967 series)','; in Alarm (Williams, 1967 series)'],
        [21672,' in Alarm (1964 series)','; in Alarm (Illustrerte Klassikere, 1964 series)'],
        [21672,' in Bajonett serien (Williams Forlag A/S','; in Bajonett serien (Williams'],
        [23238,' in Bajonett serien (1967 series)','; in Bajonett serien (Williams, 1967 series)'],
        [23238,' in Front serien (1965 series)','; in Front serien (Illustrerte Klassikere, 1965 series)'],
        [23447,' in Front serien (1967 series)','; in Front serien (Williams, 1967 series)'],
        [21960,' in Front serien (1967 series)','; in Front serien (Williams, 1967 series)'],
        [23447,' in Bajonett serien (1967 series)','; in Bajonett serien (Williams, 1967 series)'],
        [23447,' in Alarm (1967 series)','; in Alarm (Williams, 1967 series)'],
        [23447,' in Front serien (1965 series)','; in Front serien (Illustrerte Klassikere, 1965 series)'],
        [26337,' in Jessy ','; in Jessy '],
        [21200,'from Egmont (DK) ','from Egmont (DK); '],
        [21200,' in Donald Duck','; in Donald Duck'],
        [10562,'Tegneserie Bokklubben #','Tegneserie Bokklubben (Hjemmet, 1985) #'],
        [10562,' in Walt Disney','; in Walt Disney'],
        [10562,' in Donald Duck','; in Donald Duck'],
        [10562,'] in ',']; in '],
        [10562,') in ','); in '],
        [10562,'? in ','?; in '],
        [16059, ') in ', '); in '],
        [16197, ') in ', '); in '],
        [16994, ') in ', '); in '],
        ]
    for [series, old, new] in norwegian_series:
        fix_reprint_notes_series(series, old, new, check_double_semi=True)

if __name__ == '__main__':
    fix_all_reprint_notes()

