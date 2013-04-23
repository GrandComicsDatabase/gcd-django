# -*- coding: utf-8 -*-
import sys

from django.db import transaction, connection, settings
from django.contrib.auth.models import User
from django.utils.encoding import smart_str

from apps.gcd.models import Issue, StoryType
from apps.gcd.migration import migrate_reserve, do_auto_approve
from apps.oi.models import GENRES

anon = User.objects.get(username=settings.ANON_USER_NAME)

GENRE_CONVERSIONS = {#u'funny animal': u'anthropomorphic-funny animals',
                    #u'funny animals': u'anthropomorphic-funny animals',
                    u'western': u'western-frontier',
                    u'horror': u'horror-suspense',
                    u'fact': u'non-fiction',
                    u'gag': u'humor',
                    u'gags': u'humor',
                    u'satire': u'satire-parody',
                    u'detective': u'detective-mystery',
                    u'period': u'historical',
                    u'umoristico': u'humor',
                    u'supereroi': u'superhero',
                    u'avventura': u'adventure',
                    u'super-hero': u'superhero',
                    u'humour': u'humor',
                    u'fantascienza': u'science fiction',
                    u'super-héroes': u'superhero',
                    u'mystery': u'detective-mystery',
                    u'guerra': u'war',
                    u'fantastico': u'fantasy',
                    u'storico': u'historical',
                    u'nero': u'crime',
                    u'orrore': u'horror-suspense',
                    u'poliziesco': u'detective-mystery',
                    u'abenteuer': u'adventure',
                    u'superhelden': u'superhero',
                    u'fantasía': u'fantasy',
                    u'spionaggio': u'spy',
                    u'superhéroe': u'superhero',
                    u'super-heros': u'superhero',
                    u'religione': u'religious',
                    u'romantico': u'romance',
                    u'oeste': u'western-frontier',
                    u'ciencia-ficción': u'science fiction',
                    u'kinder': u'children',
                    u'aventura': u'adventure',
                    u'erotico': u'erotica',
                    u'krimi': u'detective-mystery',
                    u'science-fiction': u'science fiction',
                    u'dschungel': u'jungle',
                    u'religioso': u'religious',
                    u'satira-parodia': u'satire-parody',
                    u'animali': u'animal',
                    u'giungla': u'jungle',
                    u'documentale': u'non-fiction',
                    u'juvenil' : u'teen',
                    u'romantiek': u'romance',
                    u'avontuur': u'adventure',
                    u'biographical': u'biography',
                    u'crimen': u'crime',
                    u'deportes': u'sports',
                    u'ficção científica': u'science fiction',
                    u'superheroe': u'superhero',
                    u'biografico': u'biography',
                    u'detektiv': u'detective-mystery',
                    u'histórico': u'historical',
                    u'fantasia': u'fantasy',
                    u'fantaisy': u'fantasy',
                    u'sobrenatural': u'horror-suspense',
                    u'sportivo': u'sports',
                    u'biografía': u'biography',
                    u'djungle': u'jungle',
                    u'erotik': u'erotica',
                    u'szuperhos': u'superhero',
                    u'naturwissenschaft': u'math & science',
                    u'infantil': u'children',
                    u'horreur': u'horror-suspense',
                    u'policiaco': u'detective-mystery',
                    u'ficção': u'drama',
                    u'historie': u'historical',
                    u'espionaje': u'spy',
                    u'scienza': u'math & science',
                    u'super-herói': u'superhero',
                    u'feit': u'non-fiction',
                    u'parodie': u'satire-parody'}

GENRE_KEYWORD_CONVERSIONS = {'adult': ['', 'adult'],
    'giallo': ['detective-mystery; horror-suspense', 'giallo'] }
                             
def convert_genre(genre, language):
    genres = genre.split(';')
    converted = u''
    keyword = u''
    for genre in genres:
        genre = genre.strip()
        genre = genre.lower()
        if genre:
            if genre in GENRES['en']:
                converted += genre + '; '
            elif genre in GENRE_CONVERSIONS:
                converted += GENRE_CONVERSIONS[genre] + '; '
            elif genre in GENRE_KEYWORD_CONVERSIONS:
                [conv_genre, new_keyword] = GENRE_KEYWORD_CONVERSIONS[genre]
                if conv_genre:
                    converted += conv_genre + '; '
                if new_keyword:
                    keyword += new_keyword + '; '
            else:
                converted += genre + '; '
    if converted:
        converted = converted[:-2]
    if keyword:
        keyword = keyword[:-2]
    if converted.count(';') >= 1:
        genres = converted.split('; ')
        genre_dict = {}
        for genre in genres:
            if genre in GENRES['en']:
                genre_dict[GENRES['en'].index(genre)] = genre
            else:
                genre_dict[-1] = genre
        converted = ''
        for order in sorted(genre_dict):
            converted += genre_dict[order] + '; '
        converted = converted[:-2]
    return converted, keyword

@transaction.commit_on_success
def genre_migration(issues):
    changes = []
    for i in issues:
        c = migrate_reserve(i, 'issue', 'to migrate genre names')
        if c:
            ir = c.issuerevisions.all()[0]
            sr = c.storyrevisions.all()
            changed = False
            for s in sr:
                s.genre, keywords = convert_genre(s.genre, ir.series.language.code)
                if keywords:
                    if s.keywords:
                        s.keywords += '; ' + keywords
                    else:
                        s.keywords = keywords
                if not changed:
                    s.compare_changes()
                    if s.is_changed:
                        changed = True
                s.save()
            if changed:
                changes.append((c, True))
            else:
                print "nothing changed in ", c
                c.discard(anon)
                c.delete()
        else:
            print "%s is reserved" % i
        if len(changes) > 25:
            do_auto_approve(changes, 'migrating genre names')
            changes = []
    do_auto_approve(changes, 'migrating genre names')

@transaction.commit_on_success
def main():
    for genre in GENRE_CONVERSIONS:
        print smart_str(genre)
        issues = Issue.objects.filter(story__genre__istartswith=genre, story__deleted=False).filter(deleted=False).distinct()
        print issues.count()
        genre_migration(issues)
        issues = Issue.objects.filter(story__genre__icontains='; ' + genre, story__deleted=False).filter(deleted=False).distinct()
        print issues.count()
        genre_migration(issues)
    for genre in GENRE_KEYWORD_CONVERSIONS:
        print smart_str(genre)
        issues = Issue.objects.filter(story__genre__istartswith=genre, story__deleted=False).filter(deleted=False).distinct()
        print issues.count()
        genre_migration(issues)
        issues = Issue.objects.filter(story__genre__icontains='; ' + genre, story__deleted=False).filter(deleted=False).distinct()
        print issues.count()
        genre_migration(issues)
    
if __name__ == '__main__':
    main()
                                                                                                                                                                                                                                                                
