# -*- coding: utf-8 -*-

import re
from urllib import urlopen
import codecs

from django.db.models import Q
from django.conf import settings
from django.shortcuts import render_to_response, \
                             get_object_or_404, \
                             get_list_or_404
from django.http import HttpResponseRedirect
from django.views.generic.list_detail import object_list
from django.utils.encoding import smart_unicode as uni
from django.utils.encoding import smart_str
from django.db import transaction

from apps.gcd.models import Publisher, Series, Issue, Story, Reprint, ReprintFromIssue, ReprintToIssue
from apps.oi.models import ReprintRevision, REPRINT_FIELD
from apps.gcd.migration.reprints.parse_reprints import parse_reprint, parse_reprint_full, parse_reprint_fr, find_reprint_sequence_in_issue, parse_reprint_lars

from apps.gcd.templatetags.credits import split_reprint_string
from apps.gcd.migration import migrate_reserve, do_auto_approve

def migrate_reprints_lars():
    # 18732  Superman
    # 26245  Superboy
    # 31648  Batman Sonderheft
    # 36955  Grüne Leuchte
    # 36980  Wundergirl
    # 36973  Superman Sonderausgabe
    # 36949  Batman Sonderausgabe
    # 36975  Superman Superband
    # 36964  Roter Blitz
    issues = Issue.objects.exclude(deleted=True).filter(series__id__in = [18732,26245,31648,36955,36980,36973,36949,36975,36964], reserved=False)
    #issues = Issue.objects.filter(series__id__in = [36975,36964], reserved=False)
    migrated = []
    for migrate_issue in issues:
        changeset = migrate_reserve(migrate_issue, 'issue', 'to migrate reprint notes into links')
        if not changeset: # this should not happen since we filter out reserved issues
            raise ValueError, "%s is reserved" % migrate_issue
        #else:
            #print migrate_issue, migrate_issue.id
        things = changeset.storyrevisions.all()
        for i in things:
            text_reprint = ""
            if i.reprint_notes:
                for string in split_reprint_string(i.reprint_notes):
                    #print len(string)
                    if string == " USA":
                        break
                    #print string
                    issue, notes, sequence_number, story = parse_reprint_lars(string)
                    if issue and issue.series.language.code.lower() == 'en' and string.startswith('in '):
                        # Lars sometimes copied further US printings, don't create links
                        #print "double", string
                        issue = None
                    #print issue, notes, sequence_number, story
                    if sequence_number < 0 and issue:
                        if i.sequence_number == 0:
                            story = Story.objects.exclude(deleted=True).filter(issue = issue)
                            story = story.filter(sequence_number = 0)
                            if story.count() == 1:
                                story = story[0]
                                sequence_number = 0
                            else:
                                story = False
                        #else:
                            #print "no sequence number found", string, issue
                    #print issue
                    if issue:
                        if sequence_number >= 0 and story:
                            changeset.reprintrevisions.create(origin_story=story, target_story=i.story, notes=notes)
                        else:
                            if issue.series.language.code.lower() == 'de':
                                nr = find_reprint_sequence_in_issue(i.story, issue.id)
                                if string.lower().startswith('from'):
                                    if nr > 0:
                                        story = issue.active_stories().get(sequence_number = nr)
                                        changeset.reprintrevisions.create(origin_story=story, target_story=i.story, notes=notes)
                                    else:
                                        changeset.reprintrevisions.create(origin_issue=issue, target_story=i.story, notes=notes)
                                else:
                                    if nr > 0:
                                        story = issue.active_stories().get(sequence_number = nr)
                                        changeset.reprintrevisions.create(origin_story=i.story, target_story=story, notes=notes)
                                    else:
                                        changeset.reprintrevisions.create(target_issue=issue,
                                                            origin_story=i.story, notes=notes)
                            else:
                                changeset.reprintrevisions.create(origin_issue=issue, target_story=i.story, notes=notes)
                    else:
                        text_reprint += string + "; "
                if len(text_reprint) > 0:
                    text_reprint = text_reprint[:-2]
                    #print "Reprint Note Left: ", i.issue, i.issue.id, text_reprint
                    i.migration_status.reprint_needs_inspection = True
                    i.migration_status.save()
                i.reprint_notes = text_reprint
                i.save()
        if changeset.reprintrevisions.count():
            migrated.append((changeset, True))
        else: # nothing migrated
            #print 'nothing migrated'
            changeset.discard(changeset.indexer) # free reservation
            changeset.delete() # no need to keep changeset
        if len(migrated) > 100:
            do_auto_approve(migrated, 'reprint note migration')
            migrated = []
    if len(migrated):
        do_auto_approve(migrated, 'reprint note migration')

def find_migration_candidates(story, string, standard = True):
    """
    Calls parser for reprint notes and returns results.

    returns:
        found issue
        notes found in []
        sequence number of origin story (if found)
        origin story (if found)
        True if story is original, False otherwise
    """

    string = string.strip()
    if string == '?' or string == '' or string[-1] == '?' or \
      string.startswith('from ?') or string.startswith('uit ?') or \
      string.startswith(uni("från ?")):
        return False, '', -1, False, False


    if standard == False: #otherwise some Disney stuff takes ages
        if string.lower().find('donald daily') >= 0:
            return False,'',-1,False,False
        elif string.lower().find('duck daily') >= 0:
            return False,'',-1,False,False
        elif string.lower().find('duck sunday') >= 0:
            return False,'',-1,False,False
        elif string.lower().find('donald sunday') >= 0:
            return False,'',-1,False,False
        elif string.lower().find('mouse sunday') >= 0:
            return False,'',-1,False,False
        elif string.lower().find('mickey sunday') >= 0:
            return False,'',-1,False,False
        elif string.lower().find('mouse daily') >= 0:
            return False,'',-1,False,False
        elif string.lower().find('mickey daily') >= 0:
            return False,'',-1,False,False

    # possible from/in in other languages
    reprint_direction = ["from ", "in "]
    if story.issue.series.language.code.lower() == 'it': #da, in
        reprint_direction = ["da ", "di "] + reprint_direction
    elif story.issue.series.language.code.lower() in ['es', 'pt']: #de, en
        reprint_direction = ["de ", "en "] + reprint_direction
    elif story.issue.series.language.code.lower() == 'nl': # uit, in
        reprint_direction = ["uit "] + reprint_direction
    elif story.issue.series.language.code.lower() in ['sv', 'no']: # från, i
        reprint_direction = [uni("från "), "i "] + reprint_direction
    elif story.issue.series.language.code.lower() == 'de': # aus
        reprint_direction = ["aus "] + reprint_direction
    reprint_direction_search = reprint_direction + [""]
    other_fr = True

    for from_to in reprint_direction_search:
        if standard:
            # check for our format
            reprint, notes = parse_reprint(string, from_to)
            # exclude same series if several issues (all with same starting year) are found
            if reprint.count() > 1:
                reprint = reprint.exclude(series__id = story.issue.series.id)
            if reprint.count() > 1 and reprint.count() <= 15:
                a = []
                for i in range(reprint.count()):
                    nr = find_reprint_sequence_in_issue(story,
                                                        reprint[i].id)
                    if (nr >= 0):
                        a.append(i)
                if len(a) == 1:
                    reprint = reprint.filter(id =
                                            reprint[a[0]].id)
        else:
            # check for some others
            reprint,notes = parse_reprint_full(string, from_to)
            reprint = reprint.exclude(id = story.issue.id)
            if reprint.count() > 1 and reprint.count() <= 15:
                a = []
                for i in range(reprint.count()):
                    nr = find_reprint_sequence_in_issue(story,
                                                    reprint[i].id)
                    if (nr >= 0):
                        a.append(i)
                if len(a) == 1:
                    reprint = reprint.filter(id =
                                            reprint[a[0]].id)
            # one other routine for a few specials
            if reprint.count() == 0 or reprint.count() > 5:
                if other_fr: # need marker to only do once
                    other_fr = False
                    reprint = parse_reprint_fr(string)
                    reprint = reprint.exclude(id = story.issue.id)
                    if reprint.count() > 1 and reprint.count() <= 15:
                        a = []
                        for i in range(reprint.count()):
                            nr = find_reprint_sequence_in_issue(story,
                                                            reprint[i].id)
                            if (nr >= 0):
                                a.append(i)
                        if len(a) == 1:
                            reprint = reprint.filter(id =
                                                    reprint[a[0]].id)

        if reprint.count() == 1:
            nr = find_reprint_sequence_in_issue(story,
                                                    reprint[0].id)
            if from_to in ["from ", "aus ", "da ", "di ", "de ", \
                            "uit ",u"från "]:
                origin = False
            elif from_to == "":
                origin = False
                if notes:
                    notes += " Confirm: direction of reprint"
                else:
                    notes = "Confirm: direction of reprint"
            else:
                origin = True
            if notes:
                if notes.find('originaltitel'):
                    pos = notes.find('originaltitel')
                    notes.replace(notes[pos:pos+len('originaltitel')], 'original title')
                if notes.find('Originaltitel'):
                    pos = notes.find('Originaltitel')
                    notes.replace(notes[pos:pos+len('Originaltitel')], 'original title')
                if notes.lower().find(uni('história original')):
                    pos = notes.lower().find(uni('história original'))
                    notes.replace(notes[pos:pos+len(uni('história original'))], 'original title')
                if notes.lower().find(uni('História original')):
                    pos = notes.lower().find(uni('História original'))
                    notes.replace(notes[pos:pos+len(uni('História original'))], 'original title')
                if notes.lower().find('titolo originale'):
                    pos = notes.lower().find('titolo originale')
                    notes.replace(notes[pos:pos+len('titolo originale')], 'original title')
                if notes.find('titre original'):
                    pos = notes.find('titre original')
                    notes.replace(notes[pos:pos+len('titre original')], 'original title')
                if notes.find('Titre original'):
                    pos = notes.find('Titre original')
                    notes.replace(notes[pos:pos+len('Titre original')], 'original title')
                if notes.lower().find('originally titled'):
                    pos = notes.lower().find('originally titled')
                    notes.replace(notes[pos:pos+len('originally titled')], 'original title')
            if nr >= 0:
                other_story = Story.objects.exclude(deleted=True).filter(issue = reprint[0])
                other_story = other_story.filter(sequence_number = nr)
                return reprint[0],notes,nr,other_story[0],origin
            elif notes and notes.lower().find('original ti') >=0:
                pos = notes.lower().find('original ti')
                pos2 = notes[pos:].find('"')
                if pos2 > 0:
                    pos3 = notes[pos+pos2+1:].find('"')
                    if pos3 > 0:
                        original_title = notes[pos+pos2+1:pos+pos2+pos3]
                        end_title = pos+pos2+pos3+2
                    else:
                        original_title = notes[pos+pos2:]
                        end_title = len(notes)
                else:
                    pos2 = notes[pos:].find(']')
                    if pos2 > 0:
                        original_title = notes[pos+len('original title'):pos+pos2]
                        end_title = pos+pos2+1
                    else:
                        original_title = ''
                        end_title = len(notes)
                results = Story.objects.exclude(deleted=True)
                results = results.filter(issue = reprint[0])
                results = results.filter(title__icontains = original_title.strip(' !.":'))
                if results.count() == 1:
                    notes = notes[:pos] + notes[end_title:]
                    return reprint[0],notes,results[0].sequence_number,results[0],origin
                else:
                    return reprint[0],notes,-1,False,origin
            else:
                return reprint[0],notes,-1,False,origin
    return False,'',-1,False,False

def migrate_reprint_notes(i, standard = True, do_save = True):
    text_reprint = ""
    for string in split_reprint_string(i.reprint_notes):
        issue, notes, sequence_number, story,is_origin = \
          find_migration_candidates(i, string, standard=standard)
        if notes == None:
            notes = ''
        if issue and sequence_number < 0:
            if i.sequence_number == 0 and is_origin == False:
                sequence_number = 0
                story = Story.objects.exclude(deleted=True).filter(issue = issue)
                story = story.filter(sequence_number = \
                                                sequence_number)
                if len(story) == 1:
                    story = story[0]
                else:
                    sequence_number = -1
                    story = None
        if story:
            if is_origin:
                if Reprint.objects.filter(origin = i.story, target = story).count() > 0 \
                  or ReprintRevision.objects.filter(origin_story=i.story, target_story=story, changeset__state=1).count() > 0:
                    if notes:
                        existing_revision = ReprintRevision.objects.filter(origin_story = i.story,
                                                          target_story = story, changeset__state=1)
                        if existing_revision:
                            if existing_revision.count() > 1:
                                raise ValueError
                            existing_revision = existing_revision[0]
                            if existing_revision.notes != notes:
                                if existing_revision.notes:
                                    existing_revision.notes += '; ' + notes
                                else:
                                    existing_revision.notes = notes
                                existing_revision.save()
                        else:
                            existing = Reprint.objects.get(origin = i.story,
                                                            target = story)
                            if existing.notes != notes:
                                reprint_revision = ReprintRevision.objects.clone_revision(\
                                    reprint=existing, changeset=i.changeset)
                                if reprint_revision.notes:
                                    reprint_revision.notes += '; ' + notes
                                else:
                                    reprint_revision.notes = notes
                                reprint_revision.save()
                else:
                    if do_save:
                        i.changeset.reprintrevisions.create(origin_story=i.story, target_story=story, notes=notes)
                        #test = Reprint(origin=i, target=story,
                                                    #notes=notes)
                        #test.save()
                    else:
                        print "S2S:",string, "to:"
                        print i, i.issue, story, story.issue
            else:
                if Reprint.objects.filter(origin = story, target = i.story).count() > 0 \
                  or ReprintRevision.objects.filter(origin_story=story, target_story=i.story, changeset__state=1).count() > 0:
                    if notes:
                        existing_revision = ReprintRevision.objects.filter(origin_story = story,
                                                          target_story = i.story, changeset__state=1)
                        if existing_revision:
                            if existing_revision.count() > 1:
                                raise ValueError
                            existing_revision = existing_revision[0]
                            if existing_revision.notes != notes:
                                if existing_revision.notes:
                                    existing_revision.notes += '; ' + notes
                                else:
                                    existing_revision.notes = notes
                                existing_revision.save()
                        else:
                            existing = Reprint.objects.get(origin = story,
                                                            target = i.story)
                            if existing.notes != notes:
                                reprint_revision = ReprintRevision.objects.clone_revision(\
                                    reprint=existing, changeset=i.changeset)
                                if reprint_revision.notes:
                                    reprint_revision.notes += '; ' + notes
                                else:
                                    reprint_revision.notes = notes
                                reprint_revision.save()
                else:
                    if do_save:
                        i.changeset.reprintrevisions.create(origin_story=story, target_story=i.story, notes=notes)
                        #test = Reprint(origin=story, target=i,
                                                    #notes=notes)
                        #test.save()
                    else:
                        print "S2S",string, "to:"
                        print story, story.issue, i, i.issue
        elif issue:
            if do_save:
                if is_origin:
                    i.changeset.reprintrevisions.create(origin_story=i.story, target_issue=issue, notes=notes)
                    #test = ReprintToIssue(origin=i, target_issue=issue,
                                                        #notes=notes)
                else:
                    i.changeset.reprintrevisions.create(origin_issue=issue, target_story=i.story, notes=notes)
                    #test = ReprintFromIssue(origin_issue=issue, target=i,
                                                        #notes=notes)
                #test.save()
            else:
                print "S2I",string, "to:"
                print i, i.issue, issue
        elif string.strip() != '':
            text_reprint += string + "; "
    if len(text_reprint) > 0:
        text_reprint = text_reprint[:-2]
    if do_save:
        if i.reprint_notes != text_reprint:
            i.reprint_notes = text_reprint
            i.save()
            if not standard:
                i.story.migration_status.reprint_needs_inspection = True
                i.story.migration_status.save()
            return True
        else:
            return False
    else:
        if i.reprint_notes != text_reprint:
            print "changed:", i.reprint_notes
            print "to:", text_reprint
        #else:
            #print "keep:", i.reprint_notes


@transaction.commit_on_success
def migrate_reprints_series(number, standard = True, do_save = True):
    issues = Issue.objects.exclude(deleted=True).filter(series__id = number, reserved=False).filter(story__reprint_notes__contains=' ').distinct()
    migrated = []
    for issue in issues:
        #print issue
        if issue.active_stories().exclude(reprint_notes=None).exclude(reprint_notes='').exclude(reprint_notes='from ?').exclude(reprint_notes=u'fr\xe5n ?').exclude(reprint_notes='uit ?').exclude(reprint_notes='da ?').count():
            changeset = migrate_reserve(issue, 'issue', 'to migrate reprint notes into links')
            if not changeset: # this should not happen since we filter out reserved issues
                raise ValueError, "%s is reserved" % issue
            things = changeset.storyrevisions.all()
            #things = issue.active_stories()
            things = things.exclude(reprint_notes=None).exclude(reprint_notes='').exclude(reprint_notes='from ?').exclude(reprint_notes=u'fr\xe5n ?').exclude(reprint_notes='uit ?').exclude(reprint_notes='da ?')
            is_changed = False
            if not standard:
                things = things.exclude(reprint_notes__icontains=' syndicate)').exclude(reprint_notes__icontains=' egmont ()')
            for i in things:
                if i.reprint_notes:
                    #print i.reprint_notes
                    is_changed |= migrate_reprint_notes(i, standard=standard, do_save=do_save)
                #else:
                    #i.save()
            if is_changed or changeset.reprintrevisions.count():
                migrated.append((changeset, True))                
            else: # nothing migrated
                print issue, 'nothing migrated'
                changeset.discard(changeset.indexer) # free reservation
                changeset.delete() # no need to keep changeset
            if len(migrated) > 100:
                do_auto_approve(migrated, 'reprint note migration')
                migrated = []
    if len(migrated):
        do_auto_approve(migrated, 'reprint note migration')

def migrate_reprints(request, select = 1):
    migrate_reprints_standard(select)
    return render_to_response('gcd/index.html')

def migrate_reprints_standard(select = -1):
    series = Series.objects.exclude(deleted=True).order_by("id")
    # exclude Lars
    series = series.exclude(id__in = [18732,26245,31648,36955,36980,36973,36949,36964])
    if type(select) != int:
        select = int(select)
    if select > 0:
        series = series.filter(id__gt = str((select-1)*1000))
        series = series.filter(id__lte = str(select*1000))

    for serie in series:
        migrate_reprints_series(serie.id)

def migrate_reprints_second(request):
    for i in range(50):
        migrate_reprints_other(i)
    return render_to_response('gcd/index.html')

def migrate_reprints_other(select = -1):
    series = Series.objects.exclude(deleted=True).order_by("id")
    if select > 0:
        series = series.filter(id__gt = str((select-1)*1000))
        series = series.filter(id__lte = str(select*1000))
    # exclude Lars
    series = series.exclude(id__in = [18732,26245,31648,36955,36980,36973,36949,36964])

    series = series.exclude(id=153)# Walt Disney's Comics and Stories
    #series = series.exclude(id=687)# Topolino
    series = series.exclude(id=1923)# Alan Ford
    series = series.exclude(id=2017)# Lucky Lukes äventyr
    series = series.exclude(id=2199)# Little Orphan Annie
    series = series.exclude(id=2672)# Martin Mystère
    series = series.exclude(id=2695)# Eternauta, L'
    #series = series.exclude(id=3706)# Grandi Classici Disney, I
    series = series.exclude(id=3744)# Spicy Tales
    series = series.exclude(id=3817)# Sandman, The,
    series = series.exclude(id=7052)# Gustafs bästa sidor
    series = series.exclude(id=7087)# Serie-paraden
    series = series.exclude(id=7155)# Heavy Metal Magazine
    series = series.exclude(id=7208)# Dr. Seuss Goes to War
    #series = series.exclude(id=7536)# Albi Di Topolino
    #series = series.exclude(id=7539)# Almanacco Topolino
    #series = series.exclude(id=7540)# Almanacco Topolino
    series = series.exclude(id=7555)# Euracomix
    #series = series.exclude(id=7566)# Classici di Walt Disney, I
    #series = series.exclude(id=7569)# Grandi Classici Disney, I
    series = series.exclude(id=7582)# Manga Sun
    series = series.exclude(id=7587)# Pilot
    series = series.exclude(id=7640)# 91:an Karlsson [julalbum]
    series = series.exclude(id=7645)# Asterix
    series = series.exclude(id=7646)# Asterix [nytryck]
    series = series.exclude(id=7652)# Biffen och Bananen Ett glatt återseende
    series = series.exclude(id=7657)# Familjen Svenssons äventyr
    series = series.exclude(id=7670)# Lilla Fridolf [julalbum]
    series = series.exclude(id=8101)# James Bond
    series = series.exclude(id=8110)# Epix
    series = series.exclude(id=8118)# Tung metall
    series = series.exclude(id=8510)# Felix - Jan Lööf's Felix
    series = series.exclude(id=8511)# Felix' äventyr
    series = series.exclude(id=10413)# Naturens under
    series = series.exclude(id=10458)# Caliber
    series = series.exclude(id=10562)# Donald Duck & Co
    series = series.exclude(id=12068)# Boys Love Girls...More or Less 12068
    series = series.exclude(id=12498)# Colt
    series = series.exclude(id=14584)# Journal de Spirou, Le
    series = series.exclude(id=18705)# Korak
    series = series.exclude(id=19940)# Fandom's Finest Comics
    series = series.exclude(id=21132)# Norske Serieperler
    series = series.exclude(id=21200)# Donald Duck & Co
    series = series.exclude(id=21672)# Action Serien
    series = series.exclude(id=23238)# Front serien
    series = series.exclude(id=27342)# Donald Duck
    series = series.exclude(id=28131)# Vill Vest
    series = series.exclude(id=29937)# Pocket Book of Esquire Cartoons, The
    series = series.exclude(id=31372)# Mummitrollet
    series = series.exclude(id=32745)# Flippie Flink
    series = series.exclude(id=35202)# Heathcliff Catch of The Day
    series = series.exclude(id=36911)# Pyton
    series = series.exclude(id=36912)# Pyton
    series = series.exclude(id=53)# Wally - His Cartoons of the A.E.F. 51 51
    series = series.exclude(id=60)# How They Draw Prohibition 72 72
    series = series.exclude(id=69)# Aventures De Tintin, Les 55 55
    series = series.exclude(id=73)# Mickey Mouse Magazine 77 77
    series = series.exclude(id=82)# King Comics 658 658
    series = series.exclude(id=84)# Popular Comics 64 64
    series = series.exclude(id=107)# Super Comics 56 56
    series = series.exclude(id=111)# Jumbo Comics 53 93
    series = series.exclude(id=119)# Magic Comics 52 52
    series = series.exclude(id=240)# USA Comics 51 51
    series = series.exclude(id=538)# Lone Ranger, The 185 282
    series = series.exclude(id=593)# Collana Del Tex - Prima Serie 60 60
    series = series.exclude(id=1017)# Rocky Lane Western 61 78
    series = series.exclude(id=2867)# Doctor Who 61 61
    series = series.exclude(id=4900)# New Yorker Book of Lawyer Cartoons, The 85 85
    series = series.exclude(id=5839)# Smithsonian Book of Newspaper Comics, The 118 118
    series = series.exclude(id=6193)# Lanciostory Anno XXV 57 58
    series = series.exclude(id=6194)# Skorpio Anno XXIII 53 53
    series = series.exclude(id=7593)# Tutto Disney 126 126
    series = series.exclude(id=9787)# Kalle Anka & C:o 399 414
    series = series.exclude(id=12754)# Jokebook Comics Digest Annual 148 149
    series = series.exclude(id=14027)# Green Hornet, The 53 53
    series = series.exclude(id=14988)# Angel Heart 50 50
    series = series.exclude(id=15308)# Techno 95 95
    series = series.exclude(id=16632)# Kalar 94 94
    series = series.exclude(id=16996)# Sabotør Q5 137 137
    series = series.exclude(id=18403)# Madhouse Comics Digest 68 68
    series = series.exclude(id=19745)# Sheriff Classics 62 62
    series = series.exclude(id=19751)# Helgenen 116 118
    series = series.exclude(id=20751)# Cartoons The French Way 154 154
    series = series.exclude(id=21769)# Alarm 170 176
    series = series.exclude(id=22370)# Brumle 71 71
    series = series.exclude(id=24745)# Hjerterevyen 375 377
    series = series.exclude(id=26396)# Jippo 137 137
    series = series.exclude(id=26559)# Best Cartoons from Argosy 153 153
    series = series.exclude(id=29924)# Lasso 75 75
    series = series.exclude(id=30264)# Little Orphan Annie 59 59
    a = codecs.open( "/tmp/reprints_processing", "a", "utf-8" )
    import time
    for serie in series:
        c_start = time.time()
        #print serie, #serie.id
        migrate_reprints_series(serie.id, standard=False)#, do_save = False)
        used_time = time.time()-c_start
        a.write(uni(serie) + uni(", ") + uni(serie.id) + uni(": ") + uni(used_time) + uni("\n"))

def consistency_check_double_links():
    # helper routine for after devel runs
    # should catch these while adding them
    for i in Reprint.objects.all():
        a = Reprint.objects.filter(origin = i.origin, target = i.target)
        if a.count() > 1:
            print a[0].origin, a[0].origin.issue, a[0].target, i.target.issue, a[0].notes
            if a[1].notes:
                print a[1].notes
                c = a[0]
                if c.notes:
                    c.notes += '; ' + a[1].notes
                else:
                    c.notes = a[1].notes
                c.save()
            a[1].delete()

#@transaction.commit_on_success
def merge_reprint_link_notes(keep, delete):
    #delete.delete()
    #return
    revision_delete = delete.revisions.latest('modified')
    revision_keep = keep.revisions.latest('modified')
    mod_notes = False
    if revision_delete.notes and revision_delete.notes != revision_keep.notes:
        if revision_keep.notes:
            if revision_delete.notes != revision_keep.notes:
                revision_keep.notes = revision_keep.notes + '; ' + revision_delete.notes
        else:
            revision_keep.notes = revision_delete.notes
        revision_keep.save()
        keep.notes = revision_keep.notes
        keep.save()
        mod_notes = True
    if revision_delete.changeset.id < revision_keep.changeset.id:
        revision_keep.previous_revision = revision_delete
        changeset = revision_keep.changeset
        revision = revision_keep
        revision.in_type = revision_delete.out_type
        revision.save()
        field_name = REPRINT_FIELD[revision_delete.out_type] + '_id'
        setattr(revision_delete, field_name, None)
        revision_delete.save()
    else:
        revision_delete.previous_revision = revision_keep
        changeset = revision_delete.changeset
        revision = revision_delete
        for field_name in revision.field_list():
            setattr(revision, field_name, getattr(revision_keep, field_name))
        revision.reprint = keep
        field_name = REPRINT_FIELD[revision_delete.out_type] + '_id'
        setattr(revision, field_name, None)
        revision.out_type = revision_keep.out_type
        revision.in_type = revision_keep.out_type

    #print revision_delete.changeset.id, revision_keep.changeset.id
    #print changeset, changeset.id, revision_keep.notes
    #print changeset.reprintrevisions.all()
    #print keep.revisions.all()
    #print smart_str("cnt %d: %s" % (issues.count(), old_reprint_note.encode("utf-8")))
    print smart_str("delete: %s" % str(delete))
    print smart_str("keep: %s" % str(keep))
    if mod_notes:
        revision.comments.create(commenter=changeset.indexer,
                                    changeset=changeset,
                                    text='Automatic merging of double reprint links.',
                                    old_state=changeset.state,
                                    new_state=changeset.state)
    delete.delete()

def check_double_links():
    max_cnt = 10000000
#    max_cnt = 1
    cnt = 0
    for i in ReprintToIssue.objects.all():
        a = Reprint.objects.filter(origin = i.origin,
                                            target__issue = i.target_issue)
        if a.count()==1:
            merge_reprint_link_notes(a[0], i)
            cnt += 1
            if cnt > max_cnt:
                return

    cnt = 0
    for i in ReprintFromIssue.objects.all():
        a = Reprint.objects.filter(origin__issue = i.origin_issue,
                                                    target = i.target)
        if a.count()==1:
            merge_reprint_link_notes(a[0], i)
            cnt += 1
            if cnt > max_cnt:
                return

#@transaction.commit_on_success
def merge_reprint_links(from_issue, to_issue, cover=False):
    #print from_issue, from_issue.id, from_issue.revisions.all()
    #print to_issue, to_issue.id, to_issue.revisions.all()
    #to_issue.delete()
    #return
    revision_from = from_issue.revisions.latest('modified')
    revision_to = to_issue.revisions.latest('modified')
    # the link from the older changeset gets deleted
    # the link from the newer changeset gets modified via commit_to_display
    if revision_from.changeset.id < revision_to.changeset.id:
        older = from_issue
        newer = to_issue
        revision_older = revision_from
        revision_newer = revision_to

        changeset = revision_newer.changeset
        #print "A", revision_newer
        revision_newer.previous_revision = revision_older
        revision_newer.in_type = revision_older.out_type
        revision_newer.target_story = revision_older.target_story
        revision_newer.target_issue = None
        field_name = REPRINT_FIELD[revision_newer.out_type] + '_id'
        setattr(revision_newer, field_name, None)
        revision_newer.out_type = None
        field_name = REPRINT_FIELD[revision_older.out_type] + '_id'
        setattr(revision_newer, field_name, getattr(revision_older, field_name))
        #print "B", revision_newer
        #print getattr(revision_newer, field_name)

        #revision_newer.save()
        #revision_older.save()
    else:
        older = to_issue
        newer = from_issue
        revision_older = revision_to
        revision_newer = revision_from

        changeset = revision_newer.changeset
        #print "A", revision_newer
        revision_newer.previous_revision = revision_older
        revision_newer.in_type = revision_older.out_type
        revision_newer.origin_story = revision_older.origin_story
        revision_newer.origin_issue = None
        field_name = REPRINT_FIELD[revision_newer.out_type] + '_id'
        setattr(revision_newer, field_name, None)
        revision_newer.out_type = None
        field_name = REPRINT_FIELD[revision_older.out_type] + '_id'
        setattr(revision_newer, field_name, getattr(revision_older, field_name))
        #print "B", revision_newer
        #print getattr(revision_newer, field_name)
        #setattr(revision_older, field_name, None)

        #revision_newer.save()
        #revision_older.save()

    if revision_older.notes and revision_older.notes != revision_newer.notes:
        if revision_newer.notes:
            if revision_older.notes != revision_newer.notes:
                revision_newer.notes = revision_newer.notes + '; ' + revision_older.notes
        else:
            revision_newer.notes = revision_older.notes
        revision_newer.save()

    #print revision_older.changeset.id, revision_newer.changeset.id
    #print changeset, changeset.id, revision_newer.notes
    #print changeset.reprintrevisions.all()
    #print keep.revisions.all()
    print smart_str("older: %s" % str(older))
    print smart_str("newer: %s" % str(newer))
    #print newer.revisions.all()
    #print older.revisions.all()
    #print "newer:", revision_newer
    #print "previous:", revision_newer.previous_revision
    #print "newer:", revision_newer.origin
    #print "previous:", revision_newer.previous_revision.origin
    revision_newer.commit_to_display()
    #print "newer origin:", revision_newer.origin
    #print "previous origin:", revision_newer.previous_revision.origin
    if cover:
        text='Automatic merging of back and forth cover from/to-issue links.'
    else:
        text='Automatic merging of back and forth story from/to-issue links.'
    revision_newer.comments.create(commenter=changeset.indexer,
                                   changeset=changeset,
                                   text=text,
                                   old_state=changeset.state,
                                   new_state=changeset.state)
    newer.revisions.all()
    newer.delete()

def merge_return_links_cover():
    max_cnt = 5000000
    cnt = 0
    for i in ReprintToIssue.objects.filter(origin__type__name = 'cover'):
        a = ReprintFromIssue.objects.filter(origin_issue = i.origin.issue,
                                            target__issue = i.target_issue)
        if a.count():
            b = a.filter(target__type__name= 'cover')
            if b.count() == 1:
                a = b
            else:
                b = a.filter(target__type__name__icontains = 'cover reprint')
                if b.count() == 1:
                    a = b
                else:
                    a = a.filter(target__type__name__icontains = 'illustration')
            if a.count() == 1:
                #reprint = a[0]
                #print reprint.origin_issue, i.origin, reprint.target, i.target_issue
                merge_reprint_links(a[0], i, cover=True)
                cnt += 1
                if cnt > max_cnt:
                    return

def merge_links_story():
    max_cnt = 50000000
    cnt = 0
    for i in ReprintToIssue.objects.filter(origin__type__name = 'comic story'):
        if i.origin.issue.active_stories().filter(type=i.origin.type).count() == 1:
            if i.target_issue.active_stories().filter(type=i.origin.type).count() == 1:
                a = ReprintFromIssue.objects.filter(origin_issue = i.origin.issue,
                                                    target__issue = i.target_issue,
                                                    target__type__name = 'comic story')
                if a.count() == 1:
                    reprint = a[0]
                    if ReprintToIssue.objects.filter(origin__issue = i.origin.issue,
                                                    target_issue = i.target_issue,
                                                    origin__type__name = 'comic story').count() == 1:
                        #print i.origin, reprint.origin_issue, reprint.target, i.target_issue
                        merge_reprint_links(reprint, i)
                        cnt += 1
                        if cnt > max_cnt:
                            return

def check_return_links_story():
    changesets = []
    for i in ReprintFromIssue.objects.filter(target__type__name = 'comic story'):
        results = Story.objects.exclude(deleted=True).all()
        results = results.filter(issue = i.origin_issue)
        results = results.filter(type = i.target.type)
        if results.count() == 1:
            if ReprintFromIssue.objects.filter(target__issue=i.target.issue, target__type__name='comic story', origin_issue=i.origin_issue).count() == 1:
                story = results[0]
                print i.origin_issue, i.target.issue
                changeset = migrate_reserve(i.origin_issue, 'issue', 'to merge reprint links')
                if not changeset:
                    changeset = migrate_reserve(i.target.issue, 'issue', 'to merge reprint links')
                if not changeset:
                    raise ValueError
                revision = ReprintRevision.objects.clone_revision(\
                    reprint=i, changeset=changeset)
                revision.origin = story
                revision.origin__issue = None
                revision.save()
                changesets.append((changeset, True))
        if len(changesets) > 100:
            do_auto_approve(changesets, 'reprint link merging')
            changesets = []
    do_auto_approve(changesets, 'reprint link merging')
    changesets = []

    for i in ReprintToIssue.objects.filter(origin__type__name = 'comic story'):
        results = Story.objects.exclude(deleted=True).all()
        results = results.filter(issue = i.target_issue)
        results = results.filter(type = i.origin.type)
        if results.count() == 1:
            if ReprintToIssue.objects.filter(origin__issue=i.origin.issue, origin__type__name='comic story', target_issue = i.target_issue).count() == 1:
                story = results[0]
                print i.origin.issue, i.target_issue
                changeset = migrate_reserve(i.origin.issue, 'issue', 'to merge reprint links')
                if not changeset:
                    changeset = migrate_reserve(i.target_issue, 'issue', 'to merge reprint links')
                if not changeset:
                    raise ValueError
                revision = ReprintRevision.objects.clone_revision(\
                    reprint=i, changeset=changeset)
                revision.target = story
                revision.target__issue = None
                revision.save()
                changesets.append((changeset, True))
        if len(changesets) > 100:
            do_auto_approve(changesets, 'reprint link merging')
            changesets = []
    do_auto_approve(changesets, 'reprint link merging')
    changesets = []


#def check_return_links():
    #for i in ReprintToIssue.objects.all():
        #a = ReprintFromIssue.objects.filter(origin_issue = i.origin.issue, target__issue = i.target_issue)
        #if a.count() == 1:
            #reprint = a[0]
            #b = ReprintToIssue.objects.filter(origin__issue = i.origin.issue, target_issue = i.target)
            #if b.count() > 1 and i.origin.type == reprint.target.type:
                #b = b.filter(origin__type = i.origin.type)
            #if b.count() == 1:
                #print reprint.origin, i.origin, reprint.target, i.target_issue
                #notes = ""
                #if i.notes:
                    #notes = i.notes
                #if reprint.notes:
                    #notes += reprint.notes
                #test = Reprint(origin=i.origin, target=reprint.target, notes=notes)
                #test.save()
                #i.delete()
                #reprint.delete()

#migrate_reprints_lars()
#migrate_reprints_standard()
#migrate_reprints_other()

#check_double_links()
#merge_return_links_cover()
merge_links_story()

#migrate_reprints_series(28131)
#migrate_reprints_series(38517)
#migrate_reprints_series(44227)
#migrate_reprints_series(32067)
#migrate_reprints_series(33759)
#consistency_check_double_links()
#for i in range(468,1001):
    #migrate_reprints_series(i)
#migrate_reprints_standard(0)
#migrate_reprints_standard(65)
#migrate_reprints_standard(66)
#migrate_reprints_standard(67)
#migrate_reprints_standard(68)
#migrate_reprints_standard(69)
#migrate_reprints_standard(70)
#migrate_reprints_standard(71)
#migrate_reprints_standard(72)
#migrate_reprints_standard(73)
#migrate_reprints_standard(74)

#for i in range(100):
#migrate_reprints_series(68, standard = True, do_save = True)
#check_double_links()
#merge_return_links_cover()
#merge_links_story()

#migrate_reprints_other(60)
#migrate_reprints_other(61)
#migrate_reprints_other(62)
#migrate_reprints_other(63)
#migrate_reprints_other(64)
#migrate_reprints_other(65)
#migrate_reprints_other(66)
#migrate_reprints_other(67)
#migrate_reprints_other(68)
#migrate_reprints_other(69)
