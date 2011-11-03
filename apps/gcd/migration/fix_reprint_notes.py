# -*- coding: utf-8 -*-
import sys

from django.db import transaction, connection, settings
from django.contrib.auth.models import User
from django.utils.encoding import smart_unicode as uni

from apps.gcd.models import Issue
from apps.gcd.migration import migrate_reserve, do_auto_approve

anon = User.objects.get(username=settings.ANON_USER_NAME)

def fix_reprint_notes(issues, old_reprint_note, new_reprint_note, check_double_semi=False, exact=False):
    changes = []
    for i in issues[:450]:
        c = migrate_reserve(i, 'issue', 'to fix reprint notes')
        if c:
            ir = c.issuerevisions.all()[0]
            if exact:
                crs = c.storyrevisions.filter(reprint_notes=old_reprint_note)
            else:
                crs = c.storyrevisions.filter(reprint_notes__icontains=old_reprint_note)
            if check_double_semi:
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
            if not check_double_semi or changed:
                changes.append((c, True))
            else:
                print "nothing changed in ", c
                c.discard(anon)
                c.delete()
        else:
            print "%s is reserved" % i
        if len(changes) > 450:
            do_auto_approve(changes, 'fixing reprint notes')
            changes = []
    do_auto_approve(changes, 'fixing reprint notes')

def fix_reprint_notes_global(old_reprint_note, new_reprint_note):
    issues = Issue.objects.filter(story__reprint_notes__icontains=old_reprint_note,
                                  story__deleted=False).filter(deleted=False).distinct()
    print issues.count(), old_reprint_note
    #fix_reprint_notes(issues, old_reprint_note, new_reprint_note)

def fix_reprint_notes_series(series_id, old_reprint_note, new_reprint_note, check_double_semi=False):
    issues = Issue.objects.filter(story__reprint_notes__icontains=old_reprint_note,
                                  story__deleted=False,
                                  series__id=series_id).filter(deleted=False).distinct()
    print issues.count(), old_reprint_note
    #fix_reprint_notes(issues, old_reprint_note, new_reprint_note, check_double_semi)

@transaction.commit_on_success
def main():
    reprint_notes = [
    ['Marvel Masterworks:  ','Marvel Masterworks: '],
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
    ['Reprinted from ','from '],
    ['reprinted from ','from '],
    [') in Kamp Serien #', '); in Kamp Serien #'],
    [') in Kamp Spesial #', '); in Kamp Spesial #'],
    ['in Kamp Serien #', 'in Kamp Serien (Se-Bladene, 1964 Series) #'],
    ['Kamp Spesial #', 'Kamp Spesial (Se-Bladene, 1986 Series) #'],
    ['eries)#','eries) #'],
    ['Superman Extra (DC, 1980 Serie)','Superman Extra (Ehapa, 1980 Serie)'],
    ['Superman Taschenbuch (DC, 1976 Serie)','Superman Taschenbuch (Ehapa, 1976 Serie)'],
    [', Superman Taschenbuch (','; Superman Taschenbuch ('],
    ['Batman(DC,','Batman (DC, '],
    ['Superman Superband ( Ehapa,1974 Serie)# ','Superman Superband (Ehapa, 1973 Serie) #'],
    ['.Seuqence', '.Sequence'],
    ['(AC Comics, ','(AC, '],
    [' (DC 19',' (DC, 19'],
    ['From DC Super Stars [DC, 1976 Series)', 'From DC Super Stars (DC, 1976 Series)'],
    ['Black Cat (Harvey; 1946 series) #','Black Cat (Harvey, 1946 series) #'],
    ['from Fables (DC, 2003 series) #','from Fables (DC, 2002 series) #'],
    ['Testament (DC, 2005 series) #','Testament (DC, 2006 series) #'],
    ['from Quantum And Woody (Acclaim, 1997 Series) #','from Quantum & Woody (Acclaim, 1997 Series) #'],
    ['from Dynamic Comics (Superior Publishers Limited, 1948 series) #','from Dynamic Comics (Superior Publishers Limited, 1947 series) #'],
    ['In Nexus Archives (Dark Horse Books, 2005 series) #','In Nexus Archives (Dark Horse, 2006 series) #'],
    ['Flash Album, The (K. G. Murray, 1978 series)','Flash Album, The (K. G. Murray, 1976 series)'],
    ['Essential X-Men #','Essential X-Men (Marvel, 1996 series) #'],
    ['Marvel\'s Greatest Comics (Marvel, 1961 series)','Marvel\'s Greatest Comics (Marvel, 1969 series)'],
    ['in Superboy (Ehapa Verlag, 1980 series) #','in Superboy (Egmont, 1980 series) #'],
    ['Da DC: THE NEW FRONTIER #','Da DC: The New Frontier (DC, 2004 series) #'],
    ['from Pink Panther, The (Gold Key, 1971 series) #78','from Pink Panther, The (Whitman, 1982 series) #78'],
    ['from Pink Panther, The (Gold Key, 1971 series) #75','from Pink Panther, The (Whitman, 1982 series) #75'],
    ['from Pink Panther, The (Gold Key, 1971 series) #74','from Pink Panther, The (Whitman, 1982 series) #74'],
    ['from Pink Panther, The (Gold Key, 1971 series) #83','from Pink Panther, The (Whitman, 1982 series) #83'],
    ['from Pink Panther, The (Gold Key, 1971 series) #84','from Pink Panther, The (Whitman, 1982 series) #84'],
    ['from Pink Panther, The (Gold Key, 1971 series) #85','from Pink Panther, The (Whitman, 1982 series) #85'],
    ['from Pink Panther, The (Gold Key, 1971 series) #76','from Pink Panther, The (Whitman, 1982 series) #76'],
    ['from Pink Panther, The (Gold Key, 1971 series) #77','from Pink Panther, The (Whitman, 1982 series) #77'],
    ['from Pink Panther, The (Gold Key, 1971 series) #79','from Pink Panther, The (Whitman, 1982 series) #79'],
    ['from Pink Panther, The (Gold Key, 1971 series) #81','from Pink Panther, The (Whitman, 1982 series) #81'],
    ['from Pink Panther, The (Gold Key, 1971 series) #80','from Pink Panther, The (Whitman, 1982 series) #80'],
    ['from Pink Panther, The (Gold Key, 1971 series) #82','from Pink Panther, The (Whitman, 1982 series) #82'],
    ['Serie-pocket (Semic AS, 1975 series) #38','Serie-pocket (Semic AS, 1977 series) #38'],
    ['Serie-pocket (Semic AS, 1975 series) #61','Serie-pocket (Semic AS, 1977 series) #61'],
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
    ["from, World's Finest Comics", "from World's Finest Comics"],
    ['Superboy(DC,1949 Series)', 'Superboy (DC, 1949 Series)'],
    ['Superman Superband( Ehapa, 1973 Serie)#', 'Superman Superband (Ehapa, 1973 Serie) #'],
    ['Superman Superband (Ehapa,1974 Serie)', 'Superman Superband (Ehapa, 1974 Serie)'],
    ['Batman (DC,  1940 Series)','Batman (DC, 1940 Series)'],
    ['Batman Supermand (Ehapa, 1974 ', 'Batman Superman (Ehapa, 1974 '],
    ['from Legion of Superheroes, the [DC, 1980 Series] # ', 'from The Legion of Super-heroes (DC, 1980 Series) #'],
    ['from Superboy Spectacular [DC', 'from Superboy Spectacular (DC'],
    [',1.Sequence', ', 1.Sequence'],
    [',2.Sequence', ', 2.Sequence'],
    [',3.Sequence', ', 3.Sequence'],
    [',5.Sequence', ', 5.Sequence'],
    ]
    for [old, new] in reprint_notes:
        fix_reprint_notes_global(old, new)

    #fix_reprint_notes(issues, old_reprint_note, new_reprint_note)

    #sar_reprint_notes_series(28131,'',)
    #sar_reprint_notes_series(28131,';Vill Vest (Se-Bladene, 1955 series)','; in Vill Vest  (Se-Bladene, 1957 series)')
    #old_reprint_note = ' in Vill Vest (Se-Bladene, 1955 series)'
    #new_reprint_note = '; in Vill Vest  (Se-Bladene, 1955 series)'
    #issues = Issue.objects.filter(story__reprint_notes__iregex='The Lone Ranger [0-9]', series__id=538,
                                  #story__deleted=False).filter(deleted=False).distinct()
    #fix_reprint_notes(issues, old_reprint_note, new_reprint_note)

    old_reprint_note = 'in Complete Jack Kirby (Pure Imagination, 1997 series) #1'
    new_reprint_note = 'in Complete Jack Kirby (Pure Imagination, 1997 series) #1 1917-1940'
    issues = Issue.objects.filter(story__reprint_notes=old_reprint_note,
                                  story__deleted=False).filter(deleted=False).distinct()
    print issues.count(), old_reprint_note
    fix_reprint_notes(issues, old_reprint_note, new_reprint_note, exact=True)

    old_reprint_note = 'in Complete Jack Kirby (Pure Imagination, 1997 series) #2'
    new_reprint_note = 'in Complete Jack Kirby (Pure Imagination, 1997 series) #1940-1941 [2]'
    issues = Issue.objects.filter(story__reprint_notes=old_reprint_note,
                                  story__deleted=False).filter(deleted=False).distinct()
    print issues.count(), old_reprint_note
    fix_reprint_notes(issues, old_reprint_note, new_reprint_note, exact=True)

    old_reprint_note = 'in Complete Jack Kirby (Pure Imagination, 1997 series) #3'
    new_reprint_note = 'in Complete Jack Kirby (Pure Imagination, 1997 series) #March-May 1947 [3]'
    issues = Issue.objects.filter(story__reprint_notes=old_reprint_note,
                                  story__deleted=False).filter(deleted=False).distinct()
    print issues.count(), old_reprint_note
    fix_reprint_notes(issues, old_reprint_note, new_reprint_note, exact=True)

    series_reprint_notes = [
        [7049,'From Superman #','From Superman (DC, 1939 series) #'],
        [7049,'From Detective Comics #','From Detective Comics (DC, 1937 series) #'],
        [7049,'From Batman #','From Batman (DC, 1940 series) #'],
        [7049,'From Superboy #','From Superboy (DC, 1949 series) #'],
        [7049,'From Adventure Comics #','From Adventure Comics (DC, 1938 series) #'],
        [7049,'From Action Comics #','From Action Comics (DC, 1938 series) #'],
        [7049,'From World\'s Finest Comics #','From World\'s Finest Comics (DC, 1941 series) #'],
        [7697,'From Superman #','From Superman (DC, 1939 series) #'],
        [7697,'From Superboy #','From Superboy (DC, 1949 series) #'],
        [7697,'From Action Comics #','From Action Comics (DC, 1938 series) #'],
        [7697,'From House Of Mystery #','From House Of Mystery (DC, 1951 series) #'],
        [7697,'From Adventure Comics #','From Adventure Comics (DC, 1938 series) #'],
        [19745,'van ','from '],
        [7538,'da Turok #','da Turok, Son of Stone (Gold Key, 1962) #'],
        [7538, '[GOLD KEY, USA]',''],
        [20371,'from STAR-STUDDED COMICS #','from Star-Studded Comics (Texas Trio, 1963 series) #'],
        [10458,'from Jonah Hex: Two-Gun Mojo #','from Jonah Hex: Two Gun Mojo (DC, 1993 series) #'],
        [10458,'from Jonah Hex #','from Jonah Hex (DC, 1977 series) #'],
        [3960,'Da KEN PARKER #','da Ken Parker (Sergio Bonelli, 1977 series) #'],
        [7537, 'da Magnus #','da Magnus (Gold Key, 1963) #'],
        [7537, '[GOLD KEY, USA]',''],
        [36980, 'from Wonder Woman Vol.1 (DC, 1942 Series)','from Wonder Woman (DC, 1942 Series)'],
        [18732, '. Sequence', '.Sequence'],
        [3771, 'from BLACK CAT #','from Black Cat (Harvey, 1946 series) #'],
        ]
    for [series, old, new] in series_reprint_notes:
        fix_reprint_notes_series(series, old, new)

    norwegian_series=[
        [22049,' in Kamp Serien (Se-Bladene, 1964)','; from Kamp Serien (Se-Bladene, 1964)'],
        [22049,' in Kamp serien (Se-Bladene, 1964)','; from Kamp Serien (Se-Bladene, 1964)'],
        [22049,uni(' in På Vingene '),uni('; in På Vingene ')],
        [10459,uni(' in På Vingene '),uni('; in På Vingene ')],
        [28157,' in Kid Paddle ','; in Kid Paddle '],
        [28160,' in Kid Paddle ','; in Kid Paddle '],
        [28131,' in Vill Vest (Se-Bladene, 1955 series)','; in Vill Vest  (Se-Bladene, 1957 series)'],
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
        [10562,' from Walt Disney','; from Walt Disney'],
        [10562,' in Walt Disney','; in Walt Disney'],
        [10562,' in Donald Duck','; in Donald Duck'],
        [10562,'] in ',']; in '],
        [10562,') in ','); in '],
        [10562,'? in ','?; in '],
        ]
    for [series, old, new] in norwegian_series:
        fix_reprint_notes_series(series, old, new, check_double_semi=True)

if __name__ == '__main__':
    main()

