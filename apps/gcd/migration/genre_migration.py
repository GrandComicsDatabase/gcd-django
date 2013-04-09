# -*- coding: utf-8 -*-
import sys

from django.db import transaction, connection, settings
from django.contrib.auth.models import User

from apps.gcd.models import Issue, StoryType
from apps.gcd.migration import migrate_reserve, do_auto_approve
from apps.oi.models import GENRES

anon = User.objects.get(username=settings.ANON_USER_NAME)

GENRE_CONVERSIONS = {'funny animal': 'anthropomorphic-funny animals',
                    'funny animals': 'anthropomorphic-funny animals',
                    'western': 'western-frontier',
                    'horror': 'horror-suspense',
                    'fact': 'non-fiction',
                    'gag': 'humor',
                    'gags': 'humor',
                    'satire': 'satire-parody',
                    'detective': 'detective-mystery',
                    'period': 'historical',
                    'umoristico': 'humor',
                    'supereroi': 'superhero',
                    'avventura': 'adventure',
                    'super-hero': 'superhero',
                    'humour': 'humor',
                    'fantascienza': 'science fiction',
                    'super-héroes': 'superhero',
                    'mystery': 'detective-mystery',
                    'guerra': 'war',
                    'fantastico': 'fantasy',
                    'storico': 'historical',
                    'nero': 'crime',
                    'orrore': 'horror-suspense',
                    'poliziesco': 'detective-mystery',
                    'abenteuer': 'adventure',
                    'superhelden': 'superhero',
                    'fantasía': 'fantasy',
                    'spionaggio': 'spy',
                    'superhéroe': 'superhero',
                    'super-heros': 'superhero',
                    'religione': 'religious',
                    'romantico': 'romance',
                    'oeste': 'western-frontier',
                    'ciencia-ficción': 'science fiction',
                    'kinder': 'children',
                    'aventura': 'adventure',
                    'erotico': 'erotica',
                    'krimi': 'detective-mystery',
                    'science-fiction': 'science fiction',
                    'dschungel': 'jungle',
                    'religioso': 'religious',
                    'satira-parodia': 'satire-parody',
                    'animali': 'animal',
                    'giungla': 'jungle',
                    'documentale': 'non-fiction',
                    'juvenil' : 'teen',
                    'romantiek': 'romance',
                    'avontuur': 'adventure',
                    'biographical': 'biography',
                    'crimen': 'crime',
                    'deportes': 'sports',
                    'ficção científica': 'science fiction',
                    'superheroe': 'superhero',
                    'biografico': 'biography',
                    'detektiv': 'detective-mystery',
                    'histórico': 'historical',
                    'fantasia': 'fantasy',
                    'fantaisy': 'fantasy',
                    'sobrenatural': 'horror-suspense',
                    'sportivo': 'sports',
                    'biografía': 'biography',
                    'djungle': 'jungle',
                    'erotik': 'erotica',
                    'szuperhos': 'superhero',
                    'naturwissenschaft': 'math & science',
                    'infantil': 'children',
                    'horreur': 'horror-suspense',
                    'policiaco': 'detective-mystery',
                    'ficção': 'drama',
                    'historie': 'historical',
                    'espionaje': 'spy',
                    'scienza': 'math & science',
                    'super-herói': 'superhero',
                    'feit': 'non-fiction',
                    'parodie': 'satire-parody'}

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
            for s in sr:
                s.genre, keywords = convert_genre(s.genre, ir.series.language.code)
                if keywords:
                    if s.keywords:
                        s.keywords += '; ' + keywords
                    else:
                        s.keywords = keywords
                s.save()
            changes.append((c, True))
        else:
            print "%s is reserved" % i
        if len(changes) > 25:
            do_auto_approve(changes, 'migrating genre names')
            changes = []
    do_auto_approve(changes, 'migrating genre names')

@transaction.commit_on_success
def main():
    for genre in GENRE_CONVERSIONS:
        print genre
        issues = Issue.objects.filter(story__genre__istartswith=genre, story__deleted=False).filter(deleted=False).distinct()
        print issues.count()
        genre_migration(issues)
        issues = Issue.objects.filter(story__genre__icontains='; ' + genre, story__deleted=False).filter(deleted=False).distinct()
        print issues.count()
        genre_migration(issues)
    for genre in GENRE_KEYWORD_CONVERSIONS:
        print genre
        issues = Issue.objects.filter(story__genre__istartswith=genre, story__deleted=False).filter(deleted=False).distinct()
        print issues.count()
        genre_migration(issues)
        issues = Issue.objects.filter(story__genre__icontains='; ' + genre, story__deleted=False).filter(deleted=False).distinct()
        print issues.count()
        genre_migration(issues)
    
if __name__ == '__main__':
    main()
                                                                                                                                                                                                                                                                
