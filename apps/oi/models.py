# -*- coding: utf-8 -*-
import itertools
import operator
import re
import calendar
import os
import glob
from stdnum import isbn

from django import forms
from django.conf import settings
from django.db import models, transaction, IntegrityError
from django.db.models import Q, F, Manager
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey, \
                                               GenericRelation
from django.utils.safestring import mark_safe
from django.utils.html import conditional_escape as esc
from django.core.validators import RegexValidator, URLValidator
from django.core.exceptions import ValidationError

from imagekit.models import ImageSpecField
from imagekit.processors import ResizeToFit

from apps.oi import states

from apps.stddata.models import Country, Language, Date
from apps.stats.models import RecentIndexedIssue, CountStats

from apps.gcd.models import (
    Publisher, IndiciaPublisher, BrandGroup, Brand, BrandUse,
    Series, SeriesBond, Cover, Image, Issue, Story, Reprint, ReprintToIssue,
    ReprintFromIssue, IssueReprint, SeriesPublicationType, SeriesBondType,
    StoryType, ImageType, Creator, CreatorArtInfluence, CreatorAward,
    CreatorDegree, CreatorMembership, CreatorNameDetail, CreatorNonComicWork,
    CreatorSchool, Award, DataSource, CreatorRelation, NonComicWorkYear)

from apps.gcd.models.issue import INDEXED, issue_descriptor
from apps.gcd.models.creator import _display_day, _display_place

from apps.legacy.models import Reservation, MigrationStoryStatus

LANGUAGE_STATS = ['de']

MONTH_CHOICES = [(i, calendar.month_name[i]) for i in range(1, 13)]

# Changeset type "constants"
CTYPES = {
    'unknown': 0,
    'publisher': 1,
    'brand': 2,
    'indicia_publisher': 3,
    'series': 4,
    'issue_add': 5,
    'issue': 6,
    'cover': 7,
    'issue_bulk': 8,
    'variant_add': 9,
    'two_issues': 10,
    'reprint': 11,
    'image': 12,
    'brand_group': 13,
    'brand_use': 14,
    'series_bond': 15,
    'creator': 16,
    'creator_art_influence': 17,
    'creator_award': 18,
    'creator_degree': 19,
    'creator_membership': 20,
    'creator_non_comic_work': 21,
    'creator_relation': 22,
    'creator_school': 23,
}

CTYPES_INLINE = frozenset((CTYPES['publisher'],
                           CTYPES['brand'],
                           CTYPES['brand_group'],
                           CTYPES['brand_use'],
                           CTYPES['indicia_publisher'],
                           CTYPES['series'],
                           CTYPES['cover'],
                           CTYPES['reprint'],
                           CTYPES['image'],
                           CTYPES['series_bond'],
                           CTYPES['creator'],
                           CTYPES['creator_art_influence'],
                           CTYPES['creator_award'],
                           CTYPES['creator_degree'],
                           CTYPES['creator_membership'],
                           CTYPES['creator_non_comic_work'],
                           CTYPES['creator_relation'],
                           CTYPES['creator_school'],
                           ))

# Change types that *might* be bulk changes.  But might just have one revision.
CTYPES_BULK = frozenset((CTYPES['issue_bulk'],
                         CTYPES['issue_add']))

ACTION_ADD = 'add'
ACTION_DELETE = 'delete'
ACTION_MODIFY = 'modify'

IMP_BONUS_ADD = 10
IMP_COVER_VALUE = 5
IMP_IMAGE_VALUE = 5
IMP_APPROVER_VALUE = 3
IMP_DELETE = 1

# Reprint link type "constants"
REPRINT_TYPES = {
    'story_to_story': 0,
    'story_to_issue': 1,
    'issue_to_story': 2,
    'issue_to_issue': 3,
    'reprint': 0,
    'reprint_to_issue': 1,
    'reprint_from_issue': 2,
    'issue_reprint': 3
}

REPRINT_CLASSES = {
    0: Reprint,
    1: ReprintToIssue,
    2: ReprintFromIssue,
    3: IssueReprint
}

REPRINT_FIELD = {
    0: 'reprint',
    1: 'reprint_to_issue',
    2: 'reprint_from_issue',
    3: 'issue_reprint'
}

# translations of genre names. Once we have real considerations about
# internationalization this probably will be elsewhere
GENRES = {
    'de': [u'Abenteuer',
           u'Drama',
           u'Humor',
           u'Sachgeschichten',
           u'Fürsprache',
           u'Tier',
           u'Anthropomorph',
           u'Flieger',
           u'Biografie',
           u'Auto',
           u'Kinder',
           u'Verbrechen',
           u'Detektive',
           u'Familienleben',
           u'Erotik',
           u'Fantasy',
           u'Mode',
           u'Historie',
           u'Geschichte',
           u'Horror/Spannung',
           u'Dschungel',
           u'Kampfkunst',
           u'Mathematik und Naturwissenschaft',
           u'Arzt',
           u'Militär',
           u'Natur',
           u'Religion',
           u'Liebe',
           u'Satire/Parodie',
           u'Science-Fiction',
           u'Sport',
           u'Spionage',
           u'Superhelden',
           u'Heroische Fantasy',
           u'Jugendliche',
           u'Krieg',
           u'Western'],
    'el': [u'περιπέτεια',
           u'δραματικό',
           u'χιούμορ',
           u'όχι μυθοπλασίας',
           u'',
           u'ζώα',
           u'ανθρωπομορφικά ζώα',
           u'αεροπορικό',
           u'ιογραφικό',
           u'αυτοκίνητα',
           u'παιδικό',
           u'αστυνομικό',
           u'μυστήριο-νουάρ',
           u'οικιακό',
           u'ερωτικό',
           u'φαντασία',
           u'μόδα',
           u'ιστορική φαντασία',
           u'ιστορικό',
           u'τρόμος-σασπένς',
           u'ζούγκλα',
           u'πολεμικές τέχνες',
           u'φυσική και μαθηματικά',
           u'ιατρικό',
           u'στρατιωτικό',
           u'φύση',
           u'θρησκευτικό',
           u'αισθηματικό',
           u'σάτιρα-παρωδία',
           u'επιστημονική φαντασία',
           u'αθλητικό',
           u'κατασκοπίας',
           u'υπερηρωικό',
           u'ηρωική φαντασία',
           u'νεανικό',
           u'πολεμικό',
           u'γουέστερν'],
    'en': [u'adventure',
           u'drama',
           u'humor',
           u'non-fiction',
           u'advocacy',
           u'animal',
           u'anthropomorphic-funny animals',
           u'aviation',
           u'biography',
           u'car',
           u'children',
           u'crime',
           u'detective-mystery',
           u'domestic',
           u'erotica',
           u'fantasy',
           u'fashion',
           u'historical',
           u'history',
           u'horror-suspense',
           u'jungle',
           u'martial arts',
           u'math & science',
           u'medical',
           u'military',
           u'nature',
           u'religious',
           u'romance',
           u'satire-parody',
           u'science fiction',
           u'sports',
           u'spy',
           u'superhero',
           u'sword and sorcery',
           u'teen',
           u'war',
           u'western-frontier'],
    'es': [u'aventura',
           u'drama',
           u'humor',
           u'hechos',
           u'propaganda',
           u'animales',
           u'antropomorfo',
           u'aviación',
           u'biografía',
           u'autos',
           u'infantil',
           u'crimen',
           u'policíaco',
           u'doméstico',
           u'erótico',
           u'fantasía',
           u'moda',
           u'histórico',
           u'historia',
           u'terror-suspenso',
           u'jungla',
           u'artes marciales',
           u'científico',
           u'medicina',
           u'militar',
           u'naturaleza',
           u'religión',
           u'amoroso',
           u'sátira-parodia',
           u'ciencia ficción',
           u'deportes',
           u'espionaje',
           u'super-héroes',
           u'espada y brujería',
           u'juvenil',
           u'guerra',
           u'oeste'],
    'fr': [u'aventure',
           u'drame',
           u'humour',
           u'non fictif',
           u'juridique',
           u'animaux',
           u'animaux anthropomorphes drôles',
           u'aviation',
           u'biographique',
           u'automobile',
           u'enfants',
           u'criminel',
           u'polar; policier',
           u'domestique',
           u'érotique',
           u'fantasy',
           u'mode',
           u'historique',
           u'histoire',
           u'horreur-suspense',
           u'jungle',
           u'arts martiaux',
           u'mathématiques et sciences',
           u'médical',
           u'militaire',
           u'nature',
           u'religieux',
           u'roman d\'amour',
           u'satire/parodie',
           u'science-fiction',
           u'sport',
           u'espionnage',
           u'super-héros',
           u'heroic fantasy',
           u'adolescents',
           u'guerre',
           u'western'],
    'it': [u'avventura',
           u'',
           u'umoristico',
           u'documentale',
           u'',
           u'animali',
           u'',
           u'',
           u'biografico',
           u'',
           u'',
           u'nero',
           u'poliziesco',
           u'',
           u'erotico',
           u'fantastico',
           u'',
           u'storico',
           u'',
           u'orrore',
           u'giungla',
           u'',
           u'scienza',
           u'',
           u'',
           u'',
           u'religioso',
           u'romantico',
           u'satira-parodia',
           u'fantascienza',
           u'sportive',
           u'spionaggio',
           u'supereroe',
           u'',
           u'',
           u'guerra',
           u''],
    'nl': [u'avontuur',
           u'drama',
           u'humor',
           u'feit',
           u'voorspraak',
           u'dieren',
           u'antropomorfisch',
           u'vliegeniers',
           u'biografisch',
           u'voertuigen',
           u'kinderen',
           u'misdaad',
           u'detective',
           u'gezinsleven',
           u'erotika',
           u'fantasy',
           u'mode',
           u'historisch',
           u'geschiedenis',
           u'horror/spanning',
           u'jungle',
           u'vechtkunst',
           u'wetenschap',
           u'medisch',
           u'militair',
           u'natuur',
           u'religie',
           u'romantiek',
           u'satire/parodie',
           u'science-fiction',
           u'sport',
           u'spionage',
           u'superhelden',
           u'sword-and-sorcery',
           u'tiener',
           u'oorlog',
           u'wilde westen'],
    'no': [u'eventyr',
           u'drama',
           u'humor',
           u'fakta',
           u'',
           u'dyr',
           u'antropomorfisme-funny animals',
           u'fly',
           u'biografi',
           u'automobil',
           u'barn',
           u'krim',
           u'detektiv-mysterium',
           u'',
           u'erotikk',
           u'fantasy-overnaturlig',
           u'mote',
           u'historisk',
           u'historie',
           u'skrekk',
           u'jungel',
           u'kampsport',
           u'matematikk og vitenskap',
           u'legeroman',
           u'militær',
           u'natur',
           u'religion',
           u'romantikk',
           u'satire-parodi',
           u'science fiction',
           u'sport',
           u'spionasje',
           u'superhelt',
           u'sword and sorcery',
           u'ungdom',
           u'krig',
           u'western'],
    'pt': [u'aventura',
           u'drama',
           u'humor',
           u'não-ficção',
           u'direito',
           u'animal',
           u'antropomorfismo',
           u'aviação',
           u'biografia',
           u'automóvel',
           u'infantil',
           u'crime',
           u'detective-mistério',
           u'doméstico',
           u'erotismo',
           u'fantasia',
           u'moda',
           u'histórico',
           u'história',
           u'terror-suspense',
           u'selva',
           u'artes marciais',
           u'matemática e ciência',
           u'medicina',
           u'militar',
           u'natureza',
           u'religião',
           u'romance',
           u'sátira-paródia',
           u'ficção científica',
           u'desporto',
           u'espionagem',
           u'super-heróis',
           u'espada e feitiçaria',
           u'juvenil',
           u'guerra',
           u'velho oeste'],
}


def update_count(field, delta, language=None, country=None):
    '''
    updates statistics, for all, per language, and per country
    CountStats with language=None is for all languages
    '''
    stat = CountStats.objects.get(name=field, language=None, country=None)
    stat.count = F('count') + delta
    stat.save()

    if language:
        stat = CountStats.objects.filter(name=field, language=language)
        if stat.count():
            stat = stat[0]
            stat.count = F('count') + delta
            stat.save()
        else:
            CountStats.objects.init_stats(language=language)

    if country:
        stat = CountStats.objects.filter(name=field, country=country)
        if stat.count():
            stat = stat[0]
            stat.count = F('count') + delta
            stat.save()
        else:
            CountStats.objects.init_stats(country=country)


def set_series_first_last(series):
    '''
    set first_issue and last_issue for given series
    '''
    issues = series.active_issues().order_by('sort_code')
    if issues.count() == 0:
        series.first_issue = None
        series.last_issue = None
    else:
        series.first_issue = issues[0]
        series.last_issue = issues[len(issues) - 1]
    series.save()


def validated_isbn(entered_isbn):
    '''
    returns ISBN10 or ISBN13 if valid ISBN, empty string otherwiese
    '''
    isbns = entered_isbn.split(';')
    valid_isbns = True
    for num in isbns:
        valid_isbns &= isbn.is_valid(num)
    if valid_isbns and len(isbns) == 1:
        return isbn.compact(isbns[0])
    elif valid_isbns and len(isbns) == 2:
        compacted_isbns = [isbn.compact(isbn.to_isbn13(i)) for i in isbns]
        # if two ISBNs it must be corresponding ISBN10 and ISBN13
        if compacted_isbns[0] == compacted_isbns[1]:
            # always store ISBN13 if both exist
            return compacted_isbns[0]
    return ''


def remove_leading_article(name):
    '''
    returns the name with the leading article (separated by "'"
    or whitespace) removed
    '''
    article_match = re.match(r"\S?\w+['\s]\s*(.*)$", name, re.UNICODE)
    if article_match:
        return article_match.group(1)
    else:
        return name


def on_sale_date_as_string(issue):
    date = u''
    if issue.year_on_sale:
        date += u'{0:?<4d}'.format(issue.year_on_sale)
    elif issue.day_on_sale or issue.month_on_sale:
        date += u'????'
    if issue.month_on_sale:
        date += u'-{0:02d}'.format(issue.month_on_sale)
    elif issue.day_on_sale:
        date += u'-??'
    if issue.day_on_sale:
        date += u'-{0:02d}'.format(issue.day_on_sale)
    return date


def on_sale_date_fields(on_sale_date):
    year_string = on_sale_date[:4].strip('?')
    if year_string:
        year = int(year_string)
    else:
        year = None
    month = None
    day = None
    if len(on_sale_date) > 4:
        month_string = on_sale_date[5:7].strip('?')
        if month_string:
            month = int(month_string)
        if len(on_sale_date) > 7:
            day = int(on_sale_date[8:10].strip('?'))
    return year, month, day


def get_keywords(source):
    return u'; '.join(unicode(i) for i in source.keywords.all()
                                                .order_by('name'))


def save_keywords(revision, source):
    if revision.keywords:
        source.keywords.set(*[x.strip() for x in revision.keywords.split(';')])
        revision.keywords = u'; '.join(
            unicode(i) for i in source.keywords.all().order_by('name'))
        revision.save()
    else:
        source.keywords.set()


def _check_year(year):
    year = year.strip().strip('?')
    year_number = int(year)
    if len(year) != 4 or year_number < 0:
        raise forms.ValidationError('Enter valid years.')
    return year_number


class Changeset(models.Model):

    state = models.IntegerField(db_index=True)

    indexer = models.ForeignKey('auth.User', db_index=True,
                                related_name='changesets')
    along_with = models.ManyToManyField(User,
                                        related_name='changesets_assisting')
    on_behalf_of = models.ManyToManyField(User,
                                          related_name='changesets_source')

    # Changesets don't get an approver until late in the workflow,
    # and for legacy cases we don't know who they were.
    approver = models.ForeignKey('auth.User',  db_index=True,
                                 related_name='approved_%(class)s', null=True)

    # In production, change_type is a tinyint(2) due to the small value set.
    change_type = models.IntegerField(db_index=True)
    migrated = models.BooleanField(default=False, db_index=True)
    date_inferred = models.BooleanField(default=False)

    imps = models.IntegerField(default=0)

    created = models.DateTimeField(auto_now_add=True, db_index=True)
    modified = models.DateTimeField(auto_now=True, db_index=True)

    def __init__(self, *args, **kwargs):
        models.Model.__init__(self, *args, **kwargs)
        self._inline_revision = None

    def _revision_sets(self):
        if self.change_type in [CTYPES['issue'], CTYPES['variant_add'],
                                CTYPES['two_issues']]:
            return (self.issuerevisions.all(),
                    self.storyrevisions.all(), self.coverrevisions.all(),
                    self.reprintrevisions.all())

        if self.change_type in [CTYPES['issue_add'], CTYPES['issue_bulk']]:
            return (self.issuerevisions.all().select_related('issue',
                                                             'series'),)

        if self.change_type == CTYPES['cover']:
            return (self.coverrevisions.all(),
                    self.issuerevisions.all().select_related('issue',
                                                             'series'),
                    self.storyrevisions.all())

        if self.change_type == CTYPES['series']:
            return (self.seriesrevisions.all(),
                    self.issuerevisions.all().select_related('issue'),
                    self.storyrevisions.all())

        if self.change_type == CTYPES['series_bond']:
            return (self.seriesbondrevisions.all().select_related('series'),)

        if self.change_type == CTYPES['publisher']:
            return (self.publisherrevisions.all(), self.brandrevisions.all(),
                    self.indiciapublisherrevisions.all())

        if self.change_type == CTYPES['brand']:
            return (self.brandrevisions.all(), self.branduserevisions.all())

        if self.change_type == CTYPES['brand_group']:
            return (self.brandgrouprevisions.all(), self.brandrevisions.all(),
                    self.branduserevisions.all())

        if self.change_type == CTYPES['brand_use']:
            return (self.branduserevisions.all(),)

        if self.change_type == CTYPES['indicia_publisher']:
            return (self.indiciapublisherrevisions.all(),)

        if self.change_type == CTYPES['reprint']:
            return (self.reprintrevisions.all(),)

        if self.change_type == CTYPES['image']:
            return (self.imagerevisions.all(),)

        if self.change_type == CTYPES['creator']:
            return (self.creatorrevisions.all(),
                    self.datasourcerevisions.all(),
                    self.creatornamedetailrevisions.all())

        if self.change_type == CTYPES['creator_art_influence']:
            return (self.creatorartinfluencerevisions.all(),
                    self.datasourcerevisions.all())

        if self.change_type == CTYPES['creator_award']:
            return (self.creatorawardrevisions.all(),
                    self.datasourcerevisions.all())

        if self.change_type == CTYPES['creator_degree']:
            return (self.creatordegreerevisions.all(),
                    self.datasourcerevisions.all())

        if self.change_type == CTYPES['creator_membership']:
            return (self.creatormembershiprevisions.all(),
                    self.datasourcerevisions.all())

        if self.change_type == CTYPES['creator_non_comic_work']:
            return (self.creatornoncomicworkrevisions.all(),
                    self.datasourcerevisions.all())

        if self.change_type == CTYPES['creator_relation']:
            return (self.creatorrelationrevisions.all(),
                    self.datasourcerevisions.all())

        if self.change_type == CTYPES['creator_school']:
            return (self.creatorschoolrevisions.all(),
                    self.datasourcerevisions.all())

    @property
    def revisions(self):
        """
        Fake up an iterable (not actually a list) of all revisions,
        in canonical order.
        """
        return itertools.chain(*self._revision_sets())

    @property
    def cached_revisions(self):
        """
        Fake up an iterable (not actually a list) of all revisions,
        in canonical order.
        Revisions are cached, this is for the queue view speed-up.
        """
        if not hasattr(self, '_save_revisions'):
            self._save_revisions = self._revision_sets()
        return itertools.chain(*self._save_revisions)

    def revision_count(self):
        return reduce(operator.add,
                      map(lambda rs: rs.count(), self._revision_sets()))

    def inline(self):
        """
        If true, edit the revisions of the changeset inline in the changeset
        page.  Otherwise, render a page for the changeset that links to a
        separate edit page for each revision.
        """
        return self.change_type in CTYPES_INLINE

    def inline_revision(self, cache_safe=False):
        if self.inline():
            if self._inline_revision is None:
                if self.change_type == CTYPES['publisher']:
                    # to filter out all the imprints in a publisher deletion
                    # changeset, probably still need this for correct handling
                    # of old revisions in change history, approved, editor_log
                    if self.publisherrevisions.count() > 1:
                        self._inline_revision = \
                            self.publisherrevisions.filter(is_master=True)[0]
                    else:
                        self._inline_revision = \
                            self.publisherrevisions.get()
                else:
                    if cache_safe is True:
                        return self.cached_revisions.next()
                    else:
                        self._inline_revision = self.revisions.next()
        return self._inline_revision

    def deleted(self):
        if self.inline():
            # everything but issues
            return self.inline_revision().deleted
        elif self.change_type == CTYPES['issue']:
            # single issue deletions
            return self.issuerevisions.get().deleted
        else:
            # bulk issue deletions not supported
            return False

    def editable(self):
        """
        Used for conditionals in templates, as bulk issue adds and edits as
        well as deletes cannot be edited after submission.
        """
        return (
            # TODO check creators re inline
            self.inline() or
            self.change_type in [CTYPES['issue'],
                                 CTYPES['variant_add'],
                                 CTYPES['two_issues'],
                                 CTYPES['series_bond'],
                                 CTYPES['creator'],
                                 CTYPES['creator_membership'],
                                 CTYPES['creator_award'],
                                 CTYPES['creator_art_influence'],
                                 CTYPES['creator_non_comic_work']] or
            (
                self.change_type == CTYPES['issue_add'] and
                self.issuerevisions.count() == 1
            )
        ) and not self.deleted()

    def ordered_issue_revisions(self):
        """
        Used in the display.  Natural revision order must be by timestamp.
        """
        return self.issuerevisions.order_by('revision_sort_code', 'id')

    def queue_name(self):
        if self.change_type in CTYPES_BULK:
            ir_count = self.issuerevisions.count()
            if self.change_type == CTYPES['issue_bulk']:
                return unicode(u'%s and %d other issues' %
                               (self.issuerevisions.all()[0], ir_count - 1))
            if self.change_type == CTYPES['issue_add']:
                if ir_count == 1:
                    return unicode(self.issuerevisions.all()[0])
                elif ir_count > 1:
                    first = self.issuerevisions \
                                .order_by('revision_sort_code')[0]
                    last = self.issuerevisions \
                               .order_by('-revision_sort_code')[0]
                    return u'%s %s - %s' % (first.series,
                                            first.display_number,
                                            last.display_number)
            return u'Unknown State'
        elif self.change_type == CTYPES['issue']:
            return self.cached_revisions.next().queue_name()
        elif self.change_type == CTYPES['two_issues']:
            issuerevisions = self.issuerevisions.all()
            name = issuerevisions[0].queue_name() + " and "
            if issuerevisions[0].variant_of == issuerevisions[1].issue:
                name += "base issue"
            else:
                name += issuerevisions[1].queue_name()
            return name
        elif self.change_type == CTYPES['variant_add']:
            return self.issuerevisions \
                       .get(variant_of__isnull=False).queue_name()
        elif self.change_type == CTYPES['image']:
            return self.imagerevisions.get().queue_name()
        elif self.change_type == CTYPES['series_bond']:
            return self.seriesbondrevisions.get().queue_name()
        elif self.change_type == CTYPES['creator']:
            return self.creatorrevisions.get().queue_name()
        else:
            return self.inline_revision(cache_safe=True).queue_name()

    def queue_descriptor(self):
        if self.change_type == CTYPES['issue_add']:
            return u'[ADDED]'
        elif self.change_type == CTYPES['variant_add']:
            return u'[VARIANT + BASE]'
        return self.cached_revisions.next().queue_descriptor()

    def changeset_action(self):
        """
        Produce a human-readable description of whether we're adding, removing
        or modifying data with this changeset.
        """
        if self.change_type in [CTYPES['issue_add'], CTYPES['variant_add']]:
            return ACTION_ADD
        elif self.change_type == CTYPES['issue_bulk']:
            return ACTION_MODIFY

        revision = self.cached_revisions.next()
        if revision.deleted:
            return ACTION_DELETE
        # issue_adds are separate, avoid revision.previous
        elif self.change_type == CTYPES['issue']:
            return ACTION_MODIFY
        elif revision.previous() is None:
            return ACTION_ADD
        return ACTION_MODIFY

    def display_state(self):
        """
        Return the display text for the state.
        Makes it much easier to display state information in templates.
        """
        return states.DISPLAY_NAME[self.state]

    def _check_approver(self):
        """
        Check for a mentor, set to approver if necessary, and return the
        appropriate state for a submitted change.

        Set last issue even if we are part of a current series, because
        the is_current flag denotes that already and we may want to use the
        last issue to date sometimes.
        """
        if self.approver is None and (
                self.indexer.indexer.is_new and
                self.indexer.indexer.mentor is not None and
                self.change_type != CTYPES['cover']):
            self.approver = self.indexer.indexer.mentor

        new_state = states.PENDING
        if self.approver is not None:
            new_state = states.REVIEWING
        return new_state

    def submit(self, notes='', delete=False):
        """
        Submit changes for approval.
        If this is the first such submission or if the prior approver released
        the changes back to the general queue, then the changes go into the
        general approval queue.  If it is an edit in reply to a disapproval,
        then the changes go directly back into the approver's queue.
        """

        if (self.state != states.OPEN) and \
           not (delete and self.state == states.UNRESERVED):
            raise ValueError(
                "Only OPEN changes can be submitted for approval.")

        new_state = self._check_approver()

        self.comments.create(commenter=self.indexer,
                             text=notes,
                             old_state=self.state,
                             new_state=new_state)
        self.state = new_state

        # Since a submission is what puts the changeset in a non-editable
        # state, calculate the imps now.
        self.calculate_imps()
        self.save()

    def retract(self, notes=''):
        """
        Retract a submitted change.

        This can only be done if the change is not being examined.  Users
        should contact the examiner if they would like to further edit
        a change that is under examination.
        """

        if self.state != states.PENDING:
            raise ValueError("Only PENDING changes my be retracted.")
        if self.approver is not None:
            raise ValueError("Only changes with no approver may be retracted.")

        self.comments.create(commenter=self.indexer,
                             text=notes,
                             old_state=self.state,
                             new_state=states.OPEN)
        self.state = states.OPEN
        self.save()

    def discard(self, discarder, notes=''):
        """
        Discard a change without comitting it back to the data tables.

        This may be done either by the indexer, effectively releasign the
        reservation, or by an approver, effectively canceling it.
        """
        if self.state not in states.ACTIVE:
            raise ValueError("Only OPEN, PENDING, DISCUSSED, or REVIEWING "
                             "changes may be discarded.")

        self.comments.create(commenter=discarder,
                             text=notes,
                             old_state=self.state,
                             new_state=states.DISCARDED)

        self.state = states.DISCARDED
        self.save()
        for revision in self.revisions:
            if revision.source is not None:
                _free_revision_lock(revision.source)
                # maybe make a method to call on discard for special stuff ?
                if type(revision) in [ReprintRevision, SeriesBondRevision]:
                    revision.previous_revision = None
                    revision.save()

        if self.approver:
            self.approver.indexer.add_imps(IMP_APPROVER_VALUE)

    def assign(self, approver, notes=''):
        """
        Set an approver who will examine the changes in this pending revision.

        This causes the revision to move out of the general queue and into
        the examiner's approval queue.
        """
        if self.state != states.PENDING:
            raise ValueError("Only PENDING changes can be reviewed.")

        # TODO: check that the approver has approval priviliges.
        if not isinstance(approver, User):
            raise TypeError("Please supply a valid approver.")

        self.comments.create(commenter=approver,
                             text=notes,
                             old_state=self.state,
                             new_state=states.REVIEWING)
        self.approver = approver
        self.state = states.REVIEWING
        self.save()

    def release(self, notes=''):
        if self.state not in states.ACTIVE or \
           self.approver is None:
            raise ValueError(
                "Only changes with an approver may be unassigned.")

        if self.state in [states.DISCUSSED, states.REVIEWING]:
            new_state = states.PENDING
        else:
            new_state = self.state

        self.comments.create(commenter=self.approver,
                             text=notes,
                             old_state=self.state,
                             new_state=new_state)
        self.approver = None
        self.state = new_state
        self.save()

    def discuss(self, commenter, notes=''):
        if self.state not in [states.OPEN, states.REVIEWING] or \
           self.approver is None:
            raise ValueError("Only changes with an approver may be discussed.")

        self.comments.create(commenter=commenter,
                             text=notes,
                             old_state=self.state,
                             new_state=states.DISCUSSED)
        self.state = states.DISCUSSED
        self.save()

    def approve(self, notes=''):
        """
        Approve a pending index from an approver's queue into production.

        This moves the revision to approved and copies its data back to the
        production display table.
        """

        if self.state not in [states.DISCUSSED, states.REVIEWING] or \
           self.approver is None:
            raise ValueError(
                "Only REVIEWING changes with an approver can be approved.")

        issue_revision_count = self.issuerevisions.count()
        if self.change_type == CTYPES['issue_add'] and \
           issue_revision_count > 1:
            # Bulk add of skeletons is relatively complicated.
            # The first issue will have the "after" field set.  Later
            # issues will need the "after" field set to the issue that was
            # just created by the previous save.
            previous_revision = None
            for revision in self.issuerevisions.order_by('revision_sort_code'):
                if previous_revision is None:
                    revision.commit_to_display(
                        space_count=issue_revision_count)
                else:
                    revision.after = previous_revision.issue
                    revision.commit_to_display(space_count=0)
                previous_revision = revision
        else:
            for revision in self.revisions:
                # adds have a (created) source only after commit_to_display
                if revision.source:
                    _free_revision_lock(revision.source)
                # first free the lock, commit_to_display might delete source
                revision.commit_to_display()

        self.comments.create(commenter=self.approver,
                             text=notes,
                             old_state=self.state,
                             new_state=states.APPROVED)

        self.state = states.APPROVED
        self.save()
        self.indexer.indexer.add_imps(self.total_imps())
        self.approver.indexer.add_imps(IMP_APPROVER_VALUE)

        for revision in self.revisions:
            revision._post_commit_to_display()

    def disapprove(self, notes=''):
        """
        Send the change back to the indexer for more work.
        """
        # TODO: Should we validate that a non-empty reason is supplied
        # through the approver_notes field here or in the view layer?
        # Where should validation go in general?

        if self.state not in [states.DISCUSSED, states.REVIEWING] or \
           self.approver is None:
            raise ValueError(
                "Only REVIEWING changes with an approver can be disapproved.")
        self.comments.create(commenter=self.approver,
                             text=notes,
                             old_state=self.state,
                             new_state=states.OPEN)
        self.state = states.OPEN
        self.save()

    def calculate_imps(self):
        """
        Go through and add up the imps from the revisions, but don't commit
        to the database.
        """
        self.imps = 0
        if self.change_type in CTYPES_BULK:
            # Currently, bulk changes are only allowed when the changes
            # are uniform across all revisions in the change.  When we
            # allow non-uniform changes we may need to calculate all of
            # the imp revisions and take the maximum value or something.
            self.imps += self.revisions.next().calculate_imps()
        else:
            if self.change_type == CTYPES['cover']:
                # coverrevisions can have issuerevisions and storyrevisions
                # for variant uploads, but one shouldn't get imps for them
                revisions = self.coverrevisions.all()
            else:
                revisions = self.revisions

            for revision in revisions:
                # Deletions are a bit strange.  Essentially, you get one
                # point per button you press, however many objects that
                # button deletes.  Similar to bulk adds counting the same
                # as a single add.  Story objects are deleted one at a time,
                # and multiple of them can be deleted in a single changeset
                # without deleting the entire issue.  Issue and other objects,
                # however, are only deleted when the entire action of the
                # changeset is a deletion.  So they get one IMP_DELETE no
                # matter what else was in the changeset.

                if revision.deleted:
                    if isinstance(revision, StoryRevision) or \
                       isinstance(revision, ReprintRevision):
                        self.imps += IMP_DELETE
                    else:
                        self.imps = IMP_DELETE
                        return
                else:
                    self.imps += revision.calculate_imps()

    def magnitude(self):
        """
        A rough guide to the size of the change.  Currently implemented by
        examining the calculated imps, but may be switched to a changed field
        count of some sort if we change how imps work or decide that a
        different metric will work better as a size estimate.  For instance
        number of characters (as in letters, not the characters field) changed.
        """
        return self.imps

    def total_imps(self):
        """
        The total number of imps awarded for this changeset, including both
        field-calculated imps and bonuses such as the add bonus.
        """
        calculated = self.imps
        if self.change_type != CTYPES['cover'] and \
           self.change_type != CTYPES['image'] and \
           self.changeset_action() == ACTION_ADD:
            return calculated + IMP_BONUS_ADD
        return calculated

    def __unicode__(self):
        if self.inline():
            return unicode(self.inline_revision())
        if self.change_type in CTYPES_BULK:
            return self.queue_name()
        if self.change_type == CTYPES['issue']:
            return unicode(self.issuerevisions.all()[0])
        if self.change_type == CTYPES['two_issues']:
            return self.queue_name()
        if self.change_type == CTYPES['variant_add']:
            return self.queue_name() + u' [Variant]'
        return 'Changeset: %d' % self.id


class ChangesetComment(models.Model):
    """
    Comment class for revision management.

    We are not using Django's comments contrib package for several reasons:

    1.  Additional fields- we want to associate comments with state
        transitions, which also tells us who made the comment (since
        currently comments can only be made by the person changing the
        revision state, or by the indexer when saving intermediate edits.

        TODO: The whole bit where the indexer can end up tacking on a bunch
        of comments rather than having just one that they build up and edit
        and send in with the submission is not quite right.  Needs work still.

    2.  We don't need the anti-spam measures as these will not be accessible
        by the general public.  If we get a spammer with an account we'll have
        bigger problems than comments, and other ways to deal with them.

    3.  Unneeded fields.  This isn't really an obstacle to use, but the
        django comments system copies over a number of fields that we would
        not want copied in case they change (email, for instance).
    """
    class Meta:
        db_table = 'oi_changeset_comment'
        ordering = ['created']

    commenter = models.ForeignKey(User)
    text = models.TextField()

    changeset = models.ForeignKey(Changeset, related_name='comments')

    content_type = models.ForeignKey(ContentType, null=True)
    revision_id = models.IntegerField(db_index=True, null=True)
    revision = GenericForeignKey('content_type', 'revision_id')

    old_state = models.IntegerField()
    new_state = models.IntegerField()
    created = models.DateTimeField(auto_now_add=True, editable=False)

    def display_old_state(self):
        return states.DISPLAY_NAME[self.old_state]

    def display_new_state(self):
        return states.DISPLAY_NAME[self.new_state]


def _get_revision_lock(object, changeset=None):
    try:
        with transaction.atomic():
            revision_lock = RevisionLock.objects.create(locked_object=object,
                                                        changeset=changeset)
    except IntegrityError:
        revision_lock = None
    return revision_lock


def _free_revision_lock(object):
    revision_lock = RevisionLock.objects.get(
      object_id=object.id,
      content_type=ContentType.objects.get_for_model(object))
    revision_lock.delete()


class RevisionLock(models.Model):
    """
    Indicates that a particular Changeset has a particular row locked.

    In order to have an active Revision for a given row, a Changeset
    must hold a lock on it.  Rows in this table represent locks,
    and the unique_together constraint on the content type and object id
    ensure that only one Changeset can hold an object's lock at a time.
    Locks are released by deleting the row.

    A lock with a NULL changeset is used to check that the object can
    be locked before creating a Changeset that would not be used
    if the lock fails.

    TODO: cron job to periodically scan for stale locks?
    """
    class Meta:
        db_table = 'oi_revision_lock'
        unique_together = ('content_type', 'object_id')

    changeset = models.ForeignKey(Changeset, null=True,
                                  related_name='revision_locks')

    content_type = models.ForeignKey(ContentType)
    object_id = models.IntegerField(db_index=True)
    locked_object = GenericForeignKey('content_type', 'object_id')


class RevisionManager(models.Manager):
    """
    Custom manager base class for revisions.
    """

    def clone_revision(self, instance, instance_class,
                       changeset, check=True, **kwargs):
        """
        Given an existing instance, create a new revision based on it.

        This new revision will be where the edits are made.
        If there are no revisions, first save a baseline so that the pre-edit
        values are preserved.
        Entirely new publishers should be started by simply instantiating
        a new PublisherRevision directly.
        """
        if not isinstance(instance, instance_class):
            raise TypeError("Please supply a valid %s." % instance_class)

        revision = self._do_create_revision(instance,
                                            changeset=changeset,
                                            **kwargs)
        return revision

    def active(self):
        """
        For use on the revisions relation from display objects
        where reserved == True.
        Throws the DoesNotExist or MultipleObjectsReturned exceptions on
        the appropriate Revision subclass, as it calls get() underneath.
        """
        return self.get(changeset__state__in=states.ACTIVE)


class Revision(models.Model):
    """
    Abstract base class implementing the workflow of a revisable object.

    This holds the data while it is being edited, and remains in the table
    as a history of each given edit, including those that are discarded.

    A state column trackes the progress of the revision, which should
    eventually end in either the APPROVED or DISCARDED state.
    """
    class Meta:
        abstract = True

    changeset = models.ForeignKey(Changeset, related_name='%(class)ss')

    """
    If true, this revision deletes the object in question.  Other fields
    should not contain changes but should instead be a record of the object
    at the time of deletion and therefore match the previous revision.
    If changes are present, then they were never actually published and
    should be ignored in terms of history.
    """
    deleted = models.BooleanField(default=False, db_index=True)

    comments = GenericRelation(ChangesetComment,
                               content_type_field='content_type',
                               object_id_field='revision_id')

    created = models.DateTimeField(auto_now_add=True, db_index=True)
    modified = models.DateTimeField(auto_now=True, db_index=True)

    is_changed = False

    @property
    def source(self):
        """
        The thing of which this is a revision.
        Since this is different for each revision,
        the subclass must override this.
        """
        # Call separate method for polymorphism
        return self._get_source()

    def _get_source(self):
        raise NotImplementedError

    @property
    def source_name(self):
        """
        Used to key lookups in various shared view methods.
        """
        # Call separate method for polymorphism
        return self._get_source_name()

    def _get_source_name(self):
        raise NotImplementedError

    def _changed(self):
        """
        The dictionary of change information between this revision and the
        previous revision of the same source object.
        """
        pass

    def field_list(self):
        """
        Public field list interface, in case we ever decide we want
        to process child class field lists before returning them.
        """
        return self._field_list()

    def _field_list(self):
        """
        Default implementation for objects that have no fields (like covers).
        """
        return []

    def _get_blank_values(self):
        """
        Create a dictionary with the "blank" values for all of the fields
        of this type of revision.  This is used to determine the change
        value of newly added objects.  Blank values are often not allowed
        in the database (i.e. NOT NULL columns) so this cannot be done
        with a revision instance.  Blank values should be set.
        """
        raise NotImplementedError

    def previous(self):
        # We never spontaneously gain a previous revision during normal
        # operation, so it's safe to cache this.
        if hasattr(self, '_prev_rev'):
            return self._prev_rev

        # prev_rev stays None for additions
        self._prev_rev = None

        # TODO why not filter for states.APPROVED instead of
        # exclude STATES.DISCARDED
        # TODO why not use created instead of modified ?
        # Updating approved revisions via python scripts changes the
        # modified value. So either switch to created, or all python
        # scripts need to keep the modified value. But changes to older
        # revisions should normally not take place anyway, only field
        # creations and stuff which are done in mysql.
        if self.source is not None:
            prev_revs = self.source.revisions \
                .exclude(changeset__state=states.DISCARDED) \
                .filter(Q(modified__lt=self.modified) |
                        (Q(modified=self.modified) & Q(id__lt=self.id))) \
                .order_by('-modified', '-id')
            if prev_revs.count() > 0:
                self._prev_rev = prev_revs[0]
        elif type(self) == IssueRevision:  # only checked for adds
            if self.variant_of:  # for variant adds compare against base issue
                self._prev_rev = self.variant_of.revisions \
                    .filter(changeset__state=states.APPROVED) \
                    .latest('modified')
        return self._prev_rev

    def posterior(self):
        # This would be in the db cache anyway, but this way we
        # save db-calls in some cases.
        # During normal operation we cannot gain a new revision, so it's safe
        if hasattr(self, '_post_rev'):
            return self._post_rev

        # post_rev stays None if no newer revision is found
        self._post_rev = None
        if self.changeset.state == states.APPROVED:
            if hasattr(self, 'previous_revision'):
                if hasattr(self, 'next_revision'):
                    self._post_rev = self.next_revision
            else:
                post_revs = self.source.revisions \
                    .filter(changeset__state=states.APPROVED) \
                    .filter(Q(modified__gt=self.modified) |
                            (Q(modified=self.modified) & Q(id__gt=self.id))) \
                    .order_by('modified', 'id')
                if post_revs.count() > 0:
                    self._post_rev = post_revs[0]
        return self._post_rev

    def compare_changes(self):
        """
        Set up the 'changed' property so that it can be accessed conveniently
        from a template.  Template calling limitations prevent just
        using a parameter to compare one field at a time.
        """
        self.changed = {}
        self.is_changed = False

        if self.deleted:
            # deletion counts as changed to ease conditional for
            # collapsing sequences in bits/compare.html
            self.is_changed = True
            return

        prev_rev = self.previous()
        if prev_rev is None:
            self.is_changed = True
            prev_values = self._get_blank_values()
            get_prev_value = lambda field: prev_values[field]
        else:
            get_prev_value = lambda field: getattr(prev_rev, field)

        for field_name in self.field_list():
            old = get_prev_value(field_name)
            new = getattr(self, field_name)
            if type(new) == unicode:
                field_changed = old.strip() != new.strip()
            elif isinstance(old, Manager):
                old = old.all().values_list('id', flat=True)
                new = new.all().values_list('id', flat=True)
                field_changed = set(old) != set(new)
            elif isinstance(old, Date):
                old = unicode(old)
                new = unicode(new)
                field_changed = old != new
            else:
                field_changed = old != new
            self.changed[field_name] = field_changed
            self.is_changed |= field_changed
        if not self.is_changed and type(self) in [IssueRevision,
                                                  StoryRevision]:
            self.is_changed = self.has_reprint_revisions()

    def _start_imp_sum(self):
        """
        Hook for subclasses to initialize state for an IMP calculation.
        For instance, if a subclass is keeping track of whether either of a
        pair of fields that together represent an IMP have been seen, this
        hook can be used to clear that state before a new calculation begins.
        """
        pass

    def _imps_for(self, field_name):
        """
        Each revision subclass should override this and have it return the
        number of IMPs that a field should add to the total.  Note that this
        may be stateful as a change in one field may have already been
        accounted for due to a change in a related field.  Child classes may
        maintain state for this sort of tracking, and the _start_imp_sum hook
        should be overridden to clear any such state.
        """
        raise NotImplementedError

    def calculate_imps(self):
        """
        Calculate and return the number of Index Measurment Points that this
        revision is worth.  Relies on self.changed being set.
        """
        imps = 0
        self.compare_changes()
        if self.deleted or not self.is_changed:
            return imps

        other_imp = self._start_imp_sum()
        if other_imp:
            imps += other_imp
        for field_name in self.field_list():
            if field_name in self.changed and self.changed[field_name]:
                imps += self._imps_for(field_name)
        return imps

    def queue_name(self):
        """
        Long name form to display in queues.
        This allows revision objects to use their linked object's __unicode__
        method for compatibility in preview pages, but display a more
        verbose form in places like queues that need them.

        Derived classes should override _queue_name to supply a base string
        other than the standard unicode representation.
        """
        return self._queue_name()

    def _queue_name(self):
        return unicode(self)

    def queue_descriptor(self):
        """
        Display descriptor for queue name
        """
        if self.source is None:
            return u'[ADDED]'
        if self.deleted:
            return u'[DELETED]'
        return u''

    def save_added_revision(self, changeset, **kwargs):
        """
        Add the remaining arguments and many to many relations for an unsaved
        added revision produced by a model form.  The general workflow
        should be:

        revision = form.save(commit=False)
        revision.save_added_revision() # optionally with kwargs

        Since this prevents the form from adding any many to many
        relationships, the _do_save_added_revision method on each concrete
        revision class needs be certain to save any such relations that come
        from the form.
        """
        self.changeset = changeset
        self._do_complete_added_revision(**kwargs)
        self.save()

    def _do_complete_added_revision(self, **kwargs):
        """
        Hook for individual revisions to process additional parameters
        necessary to create a new revision representing an added record.
        By default no additional processing is done, so subclasses are
        free to override this method without calling it on the parent class.
        """
        pass

    def _create_dependent_revisions(self, delete=False, **kwargs):
        """
        Some Revisions have dependent objects, this locks the objects and
        creates the corresponding revisions.
        """
        return True

    def has_keywords(self):
        return self.keywords

    def _post_commit_to_display(self):
        """
        Hook for individual revisions to perform additional processing
        after it and all other revisions in the same changeset have been
        committed to the display.  For instance, this allows an issue to
        perform actions based on all attched stories having been committed.
        """
        pass


class OngoingReservation(models.Model):
    """
    Represents the ongoing revision on all new issues in a series.

    Whenever an issue is added to a series, if there is an ongoing reservation
    for that series the issue is immediately reserved to the ongoing
    reservation holder.
    """
    class Meta:
        db_table = 'oi_ongoing_reservation'

    indexer = models.ForeignKey(User, related_name='ongoing_reservations')
    series = models.OneToOneField(Series, related_name='ongoing_reservation')
    along_with = models.ManyToManyField(User, related_name='ongoing_assisting')
    on_behalf_of = models.ManyToManyField(User, related_name='ongoing_source')

    """
    The creation timestamp for this reservation.
    """
    created = models.DateTimeField(auto_now_add=True, db_index=True)

    def __unicode__(self):
        return u'%s reserved by %s' % (self.series, self.indexer.indexer)


class PublisherRevisionManagerBase(RevisionManager):
    def _base_field_kwargs(self, instance):
        return {
            'name': instance.name,
            'year_began': instance.year_began,
            'year_ended': instance.year_ended,
            'year_began_uncertain': instance.year_began_uncertain,
            'year_ended_uncertain': instance.year_ended_uncertain,
            'notes': instance.notes,
            'keywords': get_keywords(instance),
            'url': instance.url,
        }


class PublisherRevisionBase(Revision):
    class Meta:
        abstract = True

    name = models.CharField(max_length=255)

    year_began = models.IntegerField(null=True, blank=True)
    year_ended = models.IntegerField(null=True, blank=True)
    year_began_uncertain = models.BooleanField(default=False)
    year_ended_uncertain = models.BooleanField(default=False)

    notes = models.TextField(blank=True)
    keywords = models.TextField(blank=True, default='')
    url = models.URLField(blank=True)

    # order exactly as desired in compare page
    # use list instead of set to control order
    _base_field_list = ['name',
                        'year_began',
                        'year_began_uncertain',
                        'year_ended',
                        'year_ended_uncertain',
                        'url',
                        'notes',
                        'keywords']

    def _assign_base_fields(self, target):
        target.name = self.name
        target.year_began = self.year_began
        target.year_ended = self.year_ended
        target.year_began_uncertain = self.year_began_uncertain
        target.year_ended_uncertain = self.year_ended_uncertain
        target.notes = self.notes
        target.save()
        save_keywords(self, target)
        target.url = self.url

    def _field_list(self):
        return self._base_field_list

    def _start_imp_sum(self):
        self._seen_year_began = False
        self._seen_year_ended = False

    def _imps_for(self, field_name):
        if field_name in ('year_began', 'year_began_uncertain'):
            if not self._seen_year_began:
                self._seen_year_began = True
                return 1
        elif field_name in ('year_ended', 'year_ended_uncertain'):
            if not self._seen_year_ended:
                self._seen_year_ended = True
                return 1
        elif field_name in self._base_field_list:
            return 1
        return 0

    def __unicode__(self):
        if self.source is None:
            return self.name
        return unicode(self.source)


class PublisherRevisionManager(PublisherRevisionManagerBase):
    """
    Custom manager allowing the cloning of revisions from existing rows.
    """

    def clone_revision(self, publisher, changeset):
        """
        Create a new revision based on a Publisher instance.

        This new revision will be where the edits are made.
        Entirely new publishers should be started by simply instantiating
        a new PublisherRevision directly.
        """
        return PublisherRevisionManagerBase.clone_revision(
            self,
            instance=publisher,
            instance_class=Publisher,
            changeset=changeset)

    def _do_create_revision(self, publisher, changeset, **ignore):
        """
        Helper delegate to do the class-specific work of clone_revision.
        """
        kwargs = self._base_field_kwargs(publisher)

        revision = PublisherRevision(publisher=publisher,
                                     changeset=changeset,
                                     country=publisher.country,
                                     is_master=publisher.is_master,
                                     parent=publisher.parent,
                                     **kwargs)

        revision.save()
        return revision


class PublisherRevision(PublisherRevisionBase):
    class Meta:
        db_table = 'oi_publisher_revision'
        ordering = ['-created', '-id']

    objects = PublisherRevisionManager()

    publisher = models.ForeignKey('gcd.Publisher', null=True,
                                  related_name='revisions')

    country = models.ForeignKey('stddata.Country', db_index=True)

    # Deprecated fields about relating publishers/imprints to each other
    is_master = models.BooleanField(default=True, db_index=True)
    parent = models.ForeignKey('gcd.Publisher', default=None,
                               null=True, blank=True, db_index=True,
                               related_name='imprint_revisions')

    date_inferred = models.BooleanField(default=False)

    def _get_source(self):
        return self.publisher

    def _get_source_name(self):
        return 'publisher'

    def active_series(self):
        return self.series_set.exclude(deleted=True)

    @property
    def series_set(self):
        if self.publisher is None:
            return Series.objects.filter(pk__isnull=True)
        return self.publisher.series_set

    def _queue_name(self):
        return u'%s (%s, %s)' % (self.name, self.year_began,
                                 self.country.code.upper())

    def _field_list(self):
        fields = []
        fields.extend(PublisherRevisionBase._field_list(self))
        fields.insert(fields.index('url'), 'country')
        fields.extend(('is_master', 'parent'))
        return fields

    def _get_blank_values(self):
        return {
            'name': '',
            'country': None,
            'year_began': None,
            'year_ended': None,
            'year_began_uncertain': None,
            'year_ended_uncertain': None,
            'url': '',
            'notes': '',
            'keywords': '',
            'is_master': True,
            'parent': None,
        }

    def _imps_for(self, field_name):
        # We don't actually ever change parent and is_master since imprint
        # objects are hidden from direct access by the indexer.
        if field_name == 'country':
            return 1
        return PublisherRevisionBase._imps_for(self, field_name)

    def _create_dependent_revisions(self, delete=False):
        if delete:
            for brand_group in self.publisher.active_brands():
                # TODO check if brand_group is deletable ?
                brand_group_lock = _get_revision_lock(
                                   brand_group,
                                   changeset=self.changeset)
                if brand_group_lock is None:
                    raise IntegrityError("needed BrandGroup lock not possible")
                brand_revision = BrandGroupRevision.objects.clone_revision(
                                                    brand_group=brand_group,
                                                    changeset=self.changeset)
                brand_revision.deleted = True
                brand_revision.save()
            for indicia_publisher in self.publisher\
                                         .active_indicia_publishers():
                # indicia_publisher is deletable if publisher is deletable
                indicia_publishers_lock = _get_revision_lock(
                                          indicia_publisher,
                                          changeset=self.changeset)
                if indicia_publishers_lock is None:
                    raise IntegrityError("needed IndiciaPublisher lock not"
                                         " possible")
                indicia_publisher_revision =\
                  IndiciaPublisherRevision.objects.clone_revision(
                                          indicia_publisher=indicia_publisher,
                                          changeset=self.changeset)
                indicia_publisher_revision.deleted = True
                indicia_publisher_revision.save()
        return True

    def commit_to_display(self):
        pub = self.publisher
        if pub is None:
            pub = Publisher(imprint_count=0,
                            series_count=0,
                            issue_count=0)
            update_count('publishers', 1, country=self.country)
        elif self.deleted:
            update_count('publishers', -1, country=pub.country)
            pub.delete()
            return

        pub.country = self.country
        pub.is_master = self.is_master
        pub.parent = self.parent
        self._assign_base_fields(pub)

        pub.save()
        if self.publisher is None:
            self.publisher = pub
            self.save()

    @property
    def imprint_count(self):
        if self.source is None:
            return 0
        return self.source.imprint_count

    @property
    def indicia_publisher_count(self):
        if self.source is None:
            return 0
        return self.source.indicia_publisher_count

    @property
    def brand_count(self):
        if self.source is None:
            return 0
        return self.source.brand_count

    @property
    def series_count(self):
        if self.source is None:
            return 0
        return self.source.series_count

    @property
    def issue_count(self):
        if self.source is None:
            return 0
        return self.source.issue_count

    def get_absolute_url(self):
        if self.publisher is None:
            return "/publisher/revision/%i/preview" % self.id
        return self.publisher.get_absolute_url()

    def get_official_url(self):
        """
        TODO: See the apps.gcd.models.Publisher class for plans for removal
        of this method.
        """
        if self.url is None:
            return ''
        return self.url


class IndiciaPublisherRevisionManager(PublisherRevisionManagerBase):

    def clone_revision(self, indicia_publisher, changeset):
        """
        Create a new revision based on an IndiciaPublisher instance.

        This new revision will be where the edits are made.
        Entirely new publishers should be started by simply instantiating
        a new IndiciaPublisherRevision directly.
        """
        return PublisherRevisionManagerBase.clone_revision(
            self,
            instance=indicia_publisher,
            instance_class=IndiciaPublisher,
            changeset=changeset)

    def _do_create_revision(self, indicia_publisher, changeset, **ignore):
        """
        Helper delegate to do the class-specific work of clone_revision.
        """
        kwargs = self._base_field_kwargs(indicia_publisher)

        revision = IndiciaPublisherRevision(
            indicia_publisher=indicia_publisher,
            changeset=changeset,
            is_surrogate=indicia_publisher.is_surrogate,
            country=indicia_publisher.country,
            parent=indicia_publisher.parent,
            **kwargs)

        revision.save()
        return revision


class IndiciaPublisherRevision(PublisherRevisionBase):
    class Meta:
        db_table = 'oi_indicia_publisher_revision'
        ordering = ['-created', '-id']

    objects = IndiciaPublisherRevisionManager()

    indicia_publisher = models.ForeignKey('gcd.IndiciaPublisher', null=True,
                                          related_name='revisions')

    is_surrogate = models.BooleanField(default=False)

    country = models.ForeignKey('stddata.Country', db_index=True,
                                related_name='indicia_publishers_revisions')

    parent = models.ForeignKey('gcd.Publisher',
                               null=True, blank=True, db_index=True,
                               related_name='indicia_publisher_revisions')

    def _get_source(self):
        return self.indicia_publisher

    def _get_source_name(self):
        return 'indicia_publisher'

    def _field_list(self):
        fields = []
        fields.extend(PublisherRevisionBase._field_list(self))
        fields.insert(fields.index('url'), 'is_surrogate')
        fields.insert(fields.index('url'), 'country')
        fields.append(('parent'))
        return fields

    def _get_blank_values(self):
        return {
            'name': '',
            'country': None,
            'year_began': None,
            'year_ended': None,
            'year_began_uncertain': None,
            'year_ended_uncertain': None,
            'is_surrogate': None,
            'url': '',
            'notes': '',
            'keywords': '',
            'parent': None,
        }

    def _imps_for(self, field_name):
        if field_name in ['is_surrogate', 'parent', 'country']:
            return 1
        return PublisherRevisionBase._imps_for(self, field_name)

    def _queue_name(self):
        return u'%s: %s (%s, %s)' % (self.parent.name,
                                     self.name,
                                     self.year_began,
                                     self.country.code.upper())

    def active_issues(self):
        return self.issue_set.exclude(deleted=True)

    # Fake the issue sets for the preview page.
    @property
    def issue_set(self):
        if self.indicia_publisher is None:
            return Issue.objects.filter(pk__isnull=True)
        return self.indicia_publisher.issue_set

    @property
    def issue_count(self):
        if self.indicia_publisher is None:
            return 0
        return self.indicia_publisher.issue_count

    def _do_complete_added_revision(self, parent):
        """
        Do the necessary processing to complete the fields of a new
        series revision for adding a record before it can be saved.
        """
        self.parent = parent

    def commit_to_display(self):
        ipub = self.indicia_publisher
        if ipub is None:
            ipub = IndiciaPublisher()
            self.parent.indicia_publisher_count = \
                F('indicia_publisher_count') + 1
            self.parent.save()
            update_count('indicia publishers', 1, country=self.country)

        elif self.deleted:
            self.parent.indicia_publisher_count = \
                F('indicia_publisher_count') - 1
            self.parent.save()
            update_count('indicia publishers', -1, country=ipub.country)
            ipub.delete()
            return

        ipub.is_surrogate = self.is_surrogate
        ipub.country = self.country
        ipub.parent = self.parent
        self._assign_base_fields(ipub)

        ipub.save()
        if self.indicia_publisher is None:
            self.indicia_publisher = ipub
            self.save()

    def get_absolute_url(self):
        if self.indicia_publisher is None:
            return "/indicia_publisher/revision/%i/preview" % self.id
        return self.indicia_publisher.get_absolute_url()


class BrandGroupRevisionManager(PublisherRevisionManagerBase):

    def clone_revision(self, brand_group, changeset):
        """
        Create a new revision based on a BrandGroup instance.

        This new revision will be where the edits are made.
        Entirely new publishers should be started by simply instantiating
        a new BrandGroupRevision directly.
        """
        return PublisherRevisionManagerBase.clone_revision(
            self,
            instance=brand_group,
            instance_class=BrandGroup,
            changeset=changeset)

    def _do_create_revision(self, brand_group, changeset, **ignore):
        """
        Helper delegate to do the class-specific work of clone_revision.
        """
        kwargs = self._base_field_kwargs(brand_group)

        revision = BrandGroupRevision(brand_group=brand_group,
                                      changeset=changeset,
                                      parent=brand_group.parent,
                                      **kwargs)

        revision.save()
        return revision


class BrandGroupRevision(PublisherRevisionBase):
    class Meta:
        db_table = 'oi_brand_group_revision'
        ordering = ['-created', '-id']

    objects = BrandGroupRevisionManager()

    brand_group = models.ForeignKey('gcd.BrandGroup', null=True,
                                    related_name='revisions')

    parent = models.ForeignKey('gcd.Publisher',
                               null=True, blank=True, db_index=True,
                               related_name='brand_group_revisions')

    def _get_source(self):
        return self.brand_group

    def _get_source_name(self):
        return 'brand_group'

    def _field_list(self):
        fields = []
        fields.extend(PublisherRevisionBase._field_list(self))
        fields.append('parent')
        return fields

    def _get_blank_values(self):
        return {
            'name': '',
            'year_began': None,
            'year_ended': None,
            'year_began_uncertain': None,
            'year_ended_uncertain': None,
            'url': '',
            'notes': '',
            'keywords': '',
            'parent': None,
        }

    def _imps_for(self, field_name):
        if field_name == 'parent':
            return 1
        return PublisherRevisionBase._imps_for(self, field_name)

    def _queue_name(self):
        return u'%s: %s (%s)' % (self.parent.name, self.name, self.year_began)

    def active_issues(self):
        if self.brand_group is None:
            return Issue.objects.none()
        emblems_id = self.brand_group.active_emblems().values_list('id',
                                                                   flat=True)
        return Issue.objects.filter(brand__in=emblems_id,
                                    deleted=False)

    @property
    def issue_count(self):
        if self.brand_group is None:
            return 0
        return self.brand_group.issue_count

    def active_emblems(self):
        if self.brand_group is None:
            return Brand.objects.none()
        return self.brand_group.active_emblems()

    def _do_complete_added_revision(self, parent):
        """
        Do the necessary processing to complete the fields of a new
        series revision for adding a record before it can be saved.
        """
        self.parent = parent

    def commit_to_display(self):
        brand_group = self.brand_group
        # TODO global stats for brand groups ?
        if brand_group is None:
            brand_group = BrandGroup()
            self.parent.brand_count = F('brand_count') + 1
            self.parent.save()

        elif self.deleted:
            self.parent.brand_count = F('brand_count') - 1
            self.parent.save()
            brand_group.delete()
            return

        brand_group.parent = self.parent
        self._assign_base_fields(brand_group)

        brand_group.save()
        if self.brand_group is None:
            self.brand_group = brand_group
            self.save()
            brand_revision = BrandRevision(
                changeset=self.changeset,
                name=self.name,
                year_began=self.year_began,
                year_ended=self.year_ended,
                year_began_uncertain=self.year_began_uncertain,
                year_ended_uncertain=self.year_ended_uncertain)
            brand_revision.save()
            brand_revision.group.add(self.brand_group)
            brand_revision.commit_to_display()

    def get_absolute_url(self):
        if self.brand_group is None:
            return "/brand_group/revision/%i/preview" % self.id
        return self.brand_group.get_absolute_url()


class BrandRevisionManager(PublisherRevisionManagerBase):

    def clone_revision(self, brand, changeset):
        """
        Given an existing Brand instance, create a new revision based on it.

        This new revision will be where the edits are made.
        Entirely new brands should be started by simply instantiating
        a new BrandRevision directly.
        """
        return PublisherRevisionManagerBase.clone_revision(
            self,
            instance=brand,
            instance_class=Brand,
            changeset=changeset)

    def _do_create_revision(self, brand, changeset, **ignore):
        """
        Helper delegate to do the class-specific work of clone_revision.
        """
        kwargs = self._base_field_kwargs(brand)

        revision = BrandRevision(brand=brand, changeset=changeset, **kwargs)

        revision.save()
        if brand.group.count():
            revision.group.add(*list(brand.group.all().values_list('id',
                                                                   flat=True)))
        return revision


class BrandRevision(PublisherRevisionBase):
    class Meta:
        db_table = 'oi_brand_revision'
        ordering = ['-created', '-id']

    objects = BrandRevisionManager()

    brand = models.ForeignKey('gcd.Brand', null=True, related_name='revisions')
    # parent needs to be kept for old revisions
    parent = models.ForeignKey('gcd.Publisher',
                               null=True, blank=True, db_index=True,
                               related_name='brand_revisions')
    group = models.ManyToManyField('gcd.BrandGroup', blank=False,
                                   related_name='brand_revisions')

    def _get_source(self):
        return self.brand

    def _get_source_name(self):
        return 'brand'

    def _field_list(self):
        fields = []
        fields.extend(PublisherRevisionBase._field_list(self))
        fields.append('parent')
        fields.insert(fields.index('url'), 'group')
        return fields

    def _get_blank_values(self):
        return {
            'name': '',
            'year_began': None,
            'year_ended': None,
            'year_began_uncertain': None,
            'year_ended_uncertain': None,
            'url': '',
            'notes': '',
            'keywords': '',
            'parent': None,
            'group': None,
        }

    def _imps_for(self, field_name):
        if field_name == 'parent':
            return 1
        if field_name == 'group':
            return 1
        return PublisherRevisionBase._imps_for(self, field_name)

    def _queue_name(self):
        return u'%s: %s (%s)' % (self.group.all()[0].name, self.name,
                                 self.year_began)

    def active_issues(self):
        return self.issue_set.exclude(deleted=True)

    # Fake the in_use sets for the preview page.
    @property
    def in_use(self):
        if self.brand is None:
            return BrandUse.objects.none()
        return self.brand.in_use

    # Fake the issue sets for the preview page.
    @property
    def issue_set(self):
        if self.brand is None:
            return Issue.objects.filter(pk__isnull=True)
        return self.brand.issue_set

    @property
    def issue_count(self):
        if self.brand is None:
            return 0
        return self.brand.issue_count


    def _create_dependent_revisions(self, delete=False):
        if delete:
            for brand_use in self.brand.in_use.all():
                # brand_use can be reserved, so this can fail
                # TODO check if transaction rollback works
                brand_use_lock = _get_revision_lock(
                                brand_use,
                                changeset=self.changeset)
                if brand_use_lock is None:
                    return False

                use_revision = BrandUseRevision.objects.clone_revision(
                                                changeset=self.changeset,
                                                brand_use=brand_use)
                use_revision.deleted = True
                use_revision.save()
        return True


    def commit_to_display(self):
        brand = self.brand
        if brand is None:
            brand = Brand()
            update_count('brands', 1)

        elif self.deleted:
            update_count('brands', -1)
            brand.delete()
            return

        brand.parent = self.parent
        self._assign_base_fields(brand)

        brand_groups = brand.group.all().values_list('id', flat=True)
        revision_groups = self.group.all().values_list('id', flat=True)
        if set(brand_groups) != set(revision_groups):
            for group in brand.group.all():
                if group.id not in revision_groups:
                    group.issue_count = F('issue_count') - self.issue_count
                group.save()
            for group in self.group.all():
                if group.id not in brand_groups:
                    group.issue_count = F('issue_count') + self.issue_count
                group.save()

        brand.save()
        brand.group.clear()
        if self.group.count():
            brand.group.add(*list(self.group.all().values_list('id',
                                                               flat=True)))
        if self.brand is None:
            self.brand = brand
            self.save()

            if brand.group.count() != 1:
                raise NotImplementedError

            group = brand.group.get()
            use = BrandUseRevision(
                changeset=self.changeset,
                emblem=self.brand,
                publisher=group.parent,
                year_began=self.year_began,
                year_began_uncertain=self.year_began_uncertain,
                year_ended=self.year_ended,
                year_ended_uncertain=self.year_ended_uncertain)
            use.save()
            use.commit_to_display()

    def get_absolute_url(self):
        if self.brand is None:
            return "/brand/revision/%i/preview" % self.id
        return self.brand.get_absolute_url()


class BrandUseRevisionManager(RevisionManager):

    def clone_revision(self, brand_use, changeset):
        """
        Given an existing BrandUse instance, create a new revision based on it.

        This new revision will be where the edits are made.
        Entirely new publishers should be started by simply instantiating
        a new BrandUseRevision directly.
        """
        return RevisionManager.clone_revision(self,
                                              instance=brand_use,
                                              instance_class=BrandUse,
                                              changeset=changeset)

    def _do_create_revision(self, brand_use, changeset, **ignore):
        """
        Helper delegate to do the class-specific work of clone_revision.
        """
        revision = BrandUseRevision(
            # revision-specific fields:
            brand_use=brand_use,
            changeset=changeset,

            # copied fields:
            emblem=brand_use.emblem,
            publisher=brand_use.publisher,
            year_began=brand_use.year_began,
            year_ended=brand_use.year_ended,
            year_began_uncertain=brand_use.year_began_uncertain,
            year_ended_uncertain=brand_use.year_ended_uncertain,
            notes=brand_use.notes)

        revision.save()
        return revision


def get_brand_use_field_list():
    return ['year_began', 'year_began_uncertain',
            'year_ended', 'year_ended_uncertain', 'notes']


class BrandUseRevision(Revision):
    class Meta:
        db_table = 'oi_brand_use_revision'
        ordering = ['-created', '-id']

    objects = BrandUseRevisionManager()

    brand_use = models.ForeignKey('gcd.BrandUse', null=True,
                                  related_name='revisions')

    emblem = models.ForeignKey('gcd.Brand', null=True,
                               related_name='use_revisions')

    publisher = models.ForeignKey('gcd.Publisher', null=True, db_index=True,
                                  related_name='brand_use_revisions')

    year_began = models.IntegerField(db_index=True, null=True)
    year_ended = models.IntegerField(null=True)
    year_began_uncertain = models.BooleanField(default=False)
    year_ended_uncertain = models.BooleanField(default=False)
    notes = models.TextField(max_length=255, blank=True)

    def _get_source(self):
        return self.brand_use

    def _get_source_name(self):
        return 'brand_use'

    def _field_list(self):
        fields = get_brand_use_field_list()
        return fields

    def _get_blank_values(self):
        return {
            'publisher': None,
            'year_began': None,
            'year_ended': None,
            'year_began_uncertain': None,
            'year_ended_uncertain': None,
            'notes': ''
        }

    def _start_imp_sum(self):
        self._seen_year_began = False
        self._seen_year_ended = False

    def _imps_for(self, field_name):
        if field_name in ('year_began', 'year_began_uncertain'):
            if not self._seen_year_began:
                self._seen_year_began = True
                return 1
        elif field_name in ('year_ended', 'year_ended_uncertain'):
            if not self._seen_year_ended:
                self._seen_year_ended = True
                return 1
        else:
            return 1
        return 0

    def _queue_name(self):
        return u'%s at %s (%s)' % (self.emblem.name, self.publisher.name,
                                   self.year_began)

    def previous(self):
        if self.source:
            return super(BrandUseRevision, self).previous()
        elif self.deleted:
            # BrandUse is deleted, show content of this revision as deleted
            return self
        else:
            return None

    def posterior(self):
        if self.source:
            return super(BrandUseRevision, self).posterior()
        else:
            return None

    def active_issues(self):
        return self.emblem.issue_set.exclude(deleted=True)\
                          .filter(issue__series__publisher=self.publisher)

    @property
    def issue_count(self):
        if self.brand is None:
            return 0
        return self.brand.issue_count

    def _do_complete_added_revision(self, emblem, publisher):
        """
        Do the necessary processing to complete the fields of a new
        BrandUse revision for adding a record before it can be saved.
        """
        self.publisher = publisher
        self.emblem = emblem

    def commit_to_display(self):
        brand_use = self.brand_use
        if brand_use is None:
            brand_use = BrandUse()
            brand_use.emblem = self.emblem
        elif self.deleted:
            brand_use = self.brand_use
            for revision in brand_use.revisions.all():
                setattr(revision, 'brand_use', None)
                revision.save()
            brand_use.delete()
            return

        brand_use.publisher = self.publisher
        brand_use.year_began = self.year_began
        brand_use.year_ended = self.year_ended
        brand_use.year_began_uncertain = self.year_began_uncertain
        brand_use.year_ended_uncertain = self.year_ended_uncertain
        brand_use.notes = self.notes

        brand_use.save()
        if self.brand_use is None:
            self.brand_use = brand_use
            self.save()

    def __unicode__(self):
        return u'brand emblem %s used by %s.' % (self.emblem, self.publisher)


class CoverRevisionManager(RevisionManager):
    """
    Custom manager allowing the cloning of revisions from existing rows.
    """

    def clone_revision(self, cover, changeset):
        """
        Given an existing Cover instance, create a new revision based on it.

        This new revision will be where the replacement is stored.
        """
        return RevisionManager.clone_revision(self,
                                              instance=cover,
                                              instance_class=Cover,
                                              changeset=changeset)

    def _do_create_revision(self, cover, changeset, **ignore):
        """
        Helper delegate to do the class-specific work of clone_revision.
        """
        revision = CoverRevision(
            # revision-specific fields:
            cover=cover,
            changeset=changeset,

            # copied fields:
            issue=cover.issue)

        revision.save()
        return revision


class CoverRevision(Revision):
    class Meta:
        db_table = 'oi_cover_revision'
        ordering = ['-created', '-id']

    objects = CoverRevisionManager()

    cover = models.ForeignKey(Cover, null=True, related_name='revisions')
    issue = models.ForeignKey(Issue, related_name='cover_revisions')

    marked = models.BooleanField(default=False)
    is_replacement = models.BooleanField(default=False)
    is_wraparound = models.BooleanField(default=False)
    front_left = models.IntegerField(default=0, null=True)
    front_right = models.IntegerField(default=0, null=True)
    front_bottom = models.IntegerField(default=0, null=True)
    front_top = models.IntegerField(default=0, null=True)

    file_source = models.CharField(max_length=255, null=True)

    def _get_source(self):
        return self.cover

    def _get_source_name(self):
        return 'cover'

    def _get_blank_values(self):
        """
        Covers don't do field comparisons, so just return an empty
        dictionary so we don't throw an exception if code calls this.
        """
        return {}

    def calculate_imps(self, prev_rev=None):
        if self.changeset.change_type != CTYPES['cover']:
            return 1
        return IMP_COVER_VALUE

    def _imps_for(self, field_name):
        """
        Covers are done purely on a flat point model and don't really have
        fields.  We shouldn't get here, but just in case, return 0 to be safe.
        """
        return 0

    def commit_to_display(self):
        # the file handling is in the view/covers code
        cover = self.cover

        if cover is None:
            # check for variants having added issue records
            issue_revisions = self.changeset.issuerevisions.all()
            if len(issue_revisions) == 0:
                cover = Cover(issue=self.issue)
            elif len(issue_revisions) == 1:
                if not issue_revisions[0].issue:
                    issue_revisions[0].commit_to_display()
                cover = Cover(issue=issue_revisions[0].issue)
                self.issue = cover.issue
            else:
                raise NotImplementedError
            cover.save()
        elif self.deleted:
            cover.delete()
            cover.save()
            update_count('covers', -1,
                         language=cover.issue.series.language,
                         country=cover.issue.series.country)
            if cover.issue.series.scan_count() == 0:
                series = cover.issue.series
                series.has_gallery = False
                series.save()
            return

        if self.cover and self.is_replacement is False:
            # this is a move of a cover
            if self.changeset.change_type in [CTYPES['variant_add'],
                                              CTYPES['two_issues']]:
                old_issue = cover.issue
                issue_rev = self.changeset.issuerevisions\
                                          .exclude(issue=old_issue).get()
                cover.issue = issue_rev.issue
                cover.save()
                if issue_rev.series != old_issue.series:
                    if (issue_rev.series.language !=
                        old_issue.series.language) \
                       or (issue_rev.series.country !=
                           old_issue.series.country):
                        update_count('covers', -1,
                                     language=old_issue.series.language,
                                     country=old_issue.series.country)
                        update_count('covers', 1,
                                     language=issue_rev.series.language,
                                     country=issue_rev.series.country)
                    if not issue_rev.series.has_gallery:
                        issue_rev.series.has_gallery = True
                        issue_rev.series.save()
                    if old_issue.series.scan_count() == 0:
                        old_issue.series.has_gallery = False
                        old_issue.series.save()
            else:
                # implement in case we do different kind if cover moves
                raise NotImplementedError
        else:
            from apps.oi.covers import copy_approved_cover
            if self.cover is None:
                self.cover = cover
                self.save()
                update_count('covers', 1,
                             language=cover.issue.series.language,
                             country=cover.issue.series.country)
                if not cover.issue.series.has_gallery:
                    series = cover.issue.series
                    series.has_gallery = True
                    series.save()
            copy_approved_cover(self)
            cover.marked = self.marked
            cover.last_upload = self.changeset.comments \
                                    .latest('created').created
            cover.is_wraparound = self.is_wraparound
            cover.front_left = self.front_left
            cover.front_right = self.front_right
            cover.front_top = self.front_top
            cover.front_bottom = self.front_bottom
            cover.save()

    def base_dir(self):
        return (settings.MEDIA_ROOT + settings.NEW_COVERS_DIR +
                self.changeset.created.strftime('%B_%Y/').lower())

    def approved_file(self):
        if not settings.BETA:
            if (self.created > settings.NEW_SITE_COVER_CREATION_DATE and
                not (self.deleted and
                     (self.previous().created <
                      settings.NEW_SITE_COVER_CREATION_DATE))):
                if self.changeset.state == states.APPROVED or self.deleted:
                    if self.deleted:
                        suffix = "/uploads/%d_%s" % (
                            self.cover.id,
                            self.previous().changeset
                                           .created.strftime('%Y%m%d_%H%M%S'))
                    else:
                        suffix = "/uploads/%d_%s" % (
                            self.cover.id,
                            self.changeset.created.strftime('%Y%m%d_%H%M%S'))
                    return "%s%s%d%s%s" % (
                        settings.IMAGE_SERVER_URL,
                        settings.COVERS_DIR,
                        int(self.cover.id/1000),
                        suffix,
                        os.path.splitext(glob.glob(self.cover.base_dir() +
                                                   suffix + '*')[0])[1])
                else:
                    filename = "%s/%d" % (self.base_dir(), self.id)
                    return "%s%s%s%d%s" % (
                        settings.IMAGE_SERVER_URL,
                        settings.NEW_COVERS_DIR,
                        self.changeset.created.strftime('%B_%Y/').lower(),
                        self.id,
                        os.path.splitext(glob.glob(filename + '*')[0])[1])
            else:
                return "not supported for covers from the old site"
        else:
            return "not supported on BETA"

    def get_absolute_url(self):
        if self.cover is None:
            return "/cover/revision/%i/preview" % self.id
        return self.cover.get_absolute_url()

    def __unicode__(self):
        return unicode(self.issue)


class SeriesRevisionManager(RevisionManager):
    """
    Custom manager allowing the cloning of revisions from existing rows.
    """

    def clone_revision(self, series, changeset):
        """
        Given an existing Series instance, create a new revision based on it.

        This new revision will be where the edits are made.
        If there are no revisions, first save a baseline so that the pre-edit
        values are preserved.
        Entirely new series should be started by simply instantiating
        a new SeriesRevision directly.
        """
        return RevisionManager.clone_revision(self,
                                              instance=series,
                                              instance_class=Series,
                                              changeset=changeset)

    def _do_create_revision(self, series, changeset, **ignore):
        """
        Helper delegate to do the class-specific work of clone_revision.
        """
        revision = SeriesRevision(
            # revision-specific fields:
            series=series,
            changeset=changeset,

            # copied fields:
            name=series.name,
            leading_article=series.name != series.sort_name,
            format=series.format,
            color=series.color,
            dimensions=series.dimensions,
            paper_stock=series.paper_stock,
            binding=series.binding,
            publishing_format=series.publishing_format,
            publication_type=series.publication_type,
            is_singleton=series.is_singleton,
            notes=series.notes,
            keywords=get_keywords(series),
            year_began=series.year_began,
            year_ended=series.year_ended,
            year_began_uncertain=series.year_began_uncertain,
            year_ended_uncertain=series.year_ended_uncertain,
            is_current=series.is_current,

            publication_notes=series.publication_notes,
            tracking_notes=series.tracking_notes,

            has_barcode=series.has_barcode,
            has_indicia_frequency=series.has_indicia_frequency,
            has_isbn=series.has_isbn,
            has_volume=series.has_volume,
            has_issue_title=series.has_issue_title,
            has_rating=series.has_rating,
            is_comics_publication=series.is_comics_publication,

            country=series.country,
            language=series.language,
            publisher=series.publisher)

        revision.save()
        return revision


def get_series_field_list():
    return ['name', 'leading_article', 'imprint', 'format', 'color',
            'dimensions', 'paper_stock', 'binding', 'publishing_format',
            'publication_type', 'is_singleton', 'year_began',
            'year_began_uncertain', 'year_ended', 'year_ended_uncertain',
            'is_current', 'country', 'language', 'has_barcode',
            'has_indicia_frequency', 'has_isbn', 'has_issue_title',
            'has_volume', 'has_rating', 'is_comics_publication',
            'tracking_notes', 'notes', 'keywords']


class SeriesRevision(Revision):
    class Meta:
        db_table = 'oi_series_revision'
        ordering = ['-created', '-id']

    objects = SeriesRevisionManager()

    series = models.ForeignKey(Series, null=True, related_name='revisions')

    # When adding a series, this requests the ongoing reservation upon
    # approval of the new series.  The request will be granted unless the
    # indexer has reached their maximum number of ongoing reservations
    # at the time of approval.
    reservation_requested = models.BooleanField(default=False)

    name = models.CharField(max_length=255)
    leading_article = models.BooleanField(default=False)

    # The "format" field is a legacy field that is being split into
    # color, dimensions, paper_stock, binding, and publishing_format
    format = models.CharField(max_length=255, blank=True)
    color = models.CharField(max_length=255, blank=True)
    dimensions = models.CharField(max_length=255, blank=True)
    paper_stock = models.CharField(max_length=255, blank=True)
    binding = models.CharField(max_length=255, blank=True)
    publishing_format = models.CharField(max_length=255, blank=True)
    publication_type = models.ForeignKey(SeriesPublicationType,
                                         null=True, blank=True)

    year_began = models.IntegerField()
    year_ended = models.IntegerField(null=True, blank=True)
    year_began_uncertain = models.BooleanField(default=False)
    year_ended_uncertain = models.BooleanField(default=False)
    is_current = models.BooleanField(default=False)

    publication_notes = models.TextField(blank=True)

    # Fields for tracking relationships between series.
    # Crossref fields don't appear to really be used- nearly all null.
    tracking_notes = models.TextField(blank=True)

    # Fields for handling the presence of certain issue fields
    has_barcode = models.BooleanField(default=False)
    has_indicia_frequency = models.BooleanField(default=False)
    has_isbn = models.BooleanField(default=False)
    has_issue_title = models.BooleanField(default=False)
    has_volume = models.BooleanField(default=False)
    has_rating = models.BooleanField(default=False)

    is_comics_publication = models.BooleanField(default=False)
    is_singleton = models.BooleanField(default=False)

    notes = models.TextField(blank=True)
    keywords = models.TextField(blank=True, default='')

    # Country and Language info.
    country = models.ForeignKey(Country, related_name='series_revisions')
    language = models.ForeignKey(Language, related_name='series_revisions')

    # Fields related to the publishers table.
    publisher = models.ForeignKey(Publisher, related_name='series_revisions')
    imprint = models.ForeignKey(Publisher, null=True, blank=True, default=None,
                                related_name='imprint_series_revisions')
    date_inferred = models.BooleanField(default=False)

    @property
    def first_issue(self):
        if self.series is None:
            return None
        return self.series.first_issue

    @property
    def last_issue(self):
        if self.series is None:
            return None
        return self.series.last_issue

    @property
    def issue_count(self):
        if self.series is None:
            return 0
        return self.series.issue_count

    def display_publication_dates(self):
        if self.series is None:
            return unicode(self.year_began)
        else:
            return self.series.display_publication_dates()

    def ordered_brands(self):
        if self.series is None:
            return []
        return self.series.ordered_brands()

    def brand_info_counts(self):
        if self.series is None:
            return {'unknown': 0, 'no_brand': 0}
        return self.series.brand_info_counts()

    def ordered_indicia_publishers(self):
        if self.series is None:
            return []
        return self.series.ordered_indicia_publishers()

    def indicia_publisher_info_counts(self):
        if self.series is None:
            return {'unknown': 0}
        return self.series.indicia_publisher_info_counts()

    def _get_source(self):
        return self.series

    def _get_source_name(self):
        return 'series'

    def active_base_issues(self):
        return self.active_issues().exclude(variant_of__series=self)

    def active_issues(self):
        return self.issue_set.exclude(deleted=True)

    # Fake the issue and cover sets and a few other fields
    # for the preview page.
    @property
    def issue_set(self):
        if self.series is None:
            return Issue.objects.filter(pk__isnull=True)
        return self.series.active_issues()

    @property
    def has_gallery(self):
        if self.series is None:
            return False
        return self.series.has_gallery

    def has_tracking(self):
        if self.series is None:
            return self.tracking_notes
        return self.tracking_notes or self.series.has_series_bonds()

    def has_series_bonds(self):
        if self.series is None:
            return False
        else:
            return self.series.has_series_bonds()

    @property
    def to_series_bond(self):
        if self.series is None:
            return SeriesBond.objects.filter(pk__isnull=True)
        return self.series.to_series_bond.all()

    @property
    def from_series_bond(self):
        if self.series is None:
            return SeriesBond.objects.filter(pk__isnull=True)
        return self.series.from_series_bond.all()

    def get_ongoing_revision(self):
        if self.series is None:
            return None
        return self.series.get_ongoing_revision()

    def _field_list(self):
        fields = get_series_field_list()
        if self.previous() and (self.previous().publisher != self.publisher):
            fields = fields[0:2] + ['publisher'] + fields[2:]
        return fields + [u'publication_notes']

    def _get_blank_values(self):
        return {
            'name': '',
            'leading_article': False,
            'format': '',
            'color': '',
            'dimensions': '',
            'paper_stock': '',
            'binding': '',
            'publishing_format': '',
            'publication_type': None,
            'is_singleton': False,
            'notes': '',
            'keywords': '',
            'year_began': None,
            'year_ended': None,
            'year_began_uncertain': None,
            'year_ended_uncertain': None,
            'is_current': None,
            'publication_notes': '',
            'tracking_notes': '',
            'country': None,
            'language': None,
            'publisher': None,
            'imprint': None,
            'has_barcode': True,
            'has_indicia_frequency': False,
            'has_isbn': True,
            'has_issue_title': False,
            'has_volume': False,
            'has_rating': False,
            'is_comics_publication': True,
        }

    def _imps_for(self, field_name):
        """
        All current series fields are simple one point fields.
        """
        return 1

    def _do_complete_added_revision(self, publisher):
        """
        Do the necessary processing to complete the fields of a new
        series revision for adding a record before it can be saved.
        """
        self.publisher = publisher

    def commit_to_display(self):
        series = self.series
        if series is None:
            series = Series(issue_count=0)
            if self.is_comics_publication:
                self.publisher.series_count = F('series_count') + 1
                if not self.is_singleton:
                    # if save also happens in IssueRevision gets twice +1
                    self.publisher.save()
                update_count('series', 1, language=self.language,
                             country=self.country)
            if self.is_singleton:
                issue_revision = IssueRevision(
                    changeset=self.changeset,
                    after=None,
                    number='[nn]',
                    publication_date=self.year_began)
                if len(unicode(self.year_began)) == 4:
                    issue_revision.key_date = '%d-00-00' % self.year_began

        elif self.deleted:
            if series.is_comics_publication:
                self.publisher.series_count = F('series_count') - 1
                # TODO: implement when/if we allow series deletions along
                # with all their issues
                # self.publisher.issue_count -= series.issue_count
                self.publisher.save()
            series.delete()
            if series.is_comics_publication:
                update_count('series', -1, language=series.language,
                             country=series.country)
            reservation = self.source.get_ongoing_reservation()
            if reservation:
                reservation.delete()
            return
        else:
            if self.publisher != self.series.publisher and \
               series.is_comics_publication:
                self.publisher.issue_count = (F('issue_count') +
                                              series.issue_count)
                self.publisher.series_count = F('series_count') + 1
                self.publisher.save()
                self.series.publisher.issue_count = (F('issue_count') -
                                                     series.issue_count)
                self.series.publisher.series_count = F('series_count') - 1
                self.series.publisher.save()

        series.name = self.name
        if self.leading_article:
            series.sort_name = remove_leading_article(self.name)
        else:
            series.sort_name = self.name
        series.format = self.format
        series.color = self.color
        series.dimensions = self.dimensions
        series.paper_stock = self.paper_stock
        series.binding = self.binding
        series.publishing_format = self.publishing_format
        series.notes = self.notes
        series.is_singleton = self.is_singleton
        series.publication_type = self.publication_type

        series.year_began = self.year_began
        series.year_ended = self.year_ended
        series.year_began_uncertain = self.year_began_uncertain
        series.year_ended_uncertain = self.year_ended_uncertain
        series.is_current = self.is_current
        series.has_barcode = self.has_barcode
        series.has_indicia_frequency = self.has_indicia_frequency
        series.has_isbn = self.has_isbn
        series.has_issue_title = self.has_issue_title
        series.has_volume = self.has_volume
        series.has_rating = self.has_rating

        reservation = series.get_ongoing_reservation()
        if (not self.is_current and
                reservation and
                self.previous() and self.previous().is_current):
            reservation.delete()

        series.publication_notes = self.publication_notes
        series.tracking_notes = self.tracking_notes

        # a new series has language_id None
        if series.language_id is None:
            if series.issue_count:
                raise NotImplementedError("New series can't have issues!")

        else:
            if series.is_comics_publication != self.is_comics_publication:
                if series.is_comics_publication:
                    count = -1
                else:
                    count = +1
                update_count('series', count, language=series.language,
                             country=series.country)
                if series.issue_count:
                    update_count('issues', count*series.issue_count,
                                 language=series.language,
                                 country=series.country)
                variant_issues = Issue.objects \
                    .filter(series=series, deleted=False) \
                    .exclude(variant_of=None)\
                    .count()
                update_count('variant issues', count*variant_issues,
                             language=series.language, country=series.country)
                issue_indexes = Issue.objects \
                    .filter(series=series, deleted=False) \
                    .exclude(is_indexed=INDEXED['skeleton']) \
                    .count()
                update_count('issue indexes', count*issue_indexes,
                             language=series.language, country=series.country)

            if ((series.language != self.language or
                 series.country != self.country) and
                    self.is_comics_publication):
                update_count('series', -1,
                             language=series.language,
                             country=series.country)
                update_count('series', 1,
                             language=self.language,
                             country=self.country)
                if series.issue_count:
                    update_count('issues', -series.issue_count,
                                 language=series.language,
                                 country=series.country)
                    update_count('issues', series.issue_count,
                                 language=self.language,
                                 country=self.country)
                    variant_issues = Issue.objects \
                        .filter(series=series, deleted=False) \
                        .exclude(variant_of=None) \
                        .count()
                    update_count('variant issues', -variant_issues,
                                 language=series.language,
                                 country=series.country)
                    update_count('variant issues', variant_issues,
                                 language=self.language,
                                 country=self.country)
                    issue_indexes = \
                        Issue.objects.filter(series=series, deleted=False) \
                                     .exclude(is_indexed=INDEXED['skeleton']) \
                                     .count()
                    update_count('issue indexes', -issue_indexes,
                                 language=series.language,
                                 country=series.country)
                    update_count('issue indexes', issue_indexes,
                                 language=self.language,
                                 country=self.country)
                    story_count = Story.objects \
                                       .filter(issue__series=series,
                                               deleted=False) \
                                       .count()
                    update_count('stories', -story_count,
                                 language=series.language,
                                 country=series.country)
                    update_count('stories', story_count,
                                 language=self.language,
                                 country=self.country)
                    update_count('covers', -series.scan_count(),
                                 language=series.language,
                                 country=series.country)
                    update_count('covers', series.scan_count(),
                                 language=self.language, country=self.country)
        series.country = self.country
        series.language = self.language
        series.publisher = self.publisher
        if series.is_comics_publication != self.is_comics_publication:
            series.has_gallery = (self.is_comics_publication and
                                  series.scan_count())
        series.is_comics_publication = self.is_comics_publication

        series.save()
        save_keywords(self, series)
        series.save()
        if self.series is None:
            self.series = series
            self.save()
            if self.is_singleton:
                issue_revision.series = series
                issue_revision.save()
                issue_revision.commit_to_display()

    def get_absolute_url(self):
        if self.series is None:
            return "/series/revision/%i/preview" % self.id
        return self.series.get_absolute_url()

    def __unicode__(self):
        if self.series is None:
            return u'%s (%s series)' % (self.name, self.year_began)
        return unicode(self.series)


class SeriesBondRevisionManager(RevisionManager):

    def clone_revision(self, series_bond, changeset):
        """
        Create a new revision based on a SeriesBond instance.

        This new revision will be where the edits are made.
        """
        return RevisionManager.clone_revision(self,
                                              instance=series_bond,
                                              instance_class=SeriesBond,
                                              changeset=changeset)

    def _do_create_revision(self, series_bond, changeset):
        """
        Helper delegate to do the class-specific work of clone_revision.
        """
        revision = SeriesBondRevision(
            # revision-specific fields:
            series_bond=series_bond,
            changeset=changeset,

            # copied fields:
            origin=series_bond.origin,
            origin_issue=series_bond.origin_issue,
            target=series_bond.target,
            target_issue=series_bond.target_issue,
            bond_type=series_bond.bond_type,
            notes=series_bond.notes)

        revision.save()
        previous_revision = SeriesBondRevision.objects.get(
            series_bond=series_bond,
            next_revision=None,
            changeset__state=states.APPROVED)
        revision.previous_revision = previous_revision
        revision.save()
        return revision


def get_series_bond_field_list():
    return ['bond_type', 'notes']


class SeriesBondRevision(Revision):
    class Meta:
        db_table = 'oi_series_bond_revision'
        ordering = ['-created', '-id']
        get_latest_by = "created"

    objects = SeriesBondRevisionManager()

    series_bond = models.ForeignKey(SeriesBond, null=True,
                                    related_name='revisions')

    origin = models.ForeignKey(Series, null=True,
                               related_name='origin_bond_revisions')
    origin_issue = models.ForeignKey(
        Issue, null=True, related_name='origin_series_bond_revisions')
    target = models.ForeignKey(Series, null=True,
                               related_name='target_bond_revisions')
    target_issue = models.ForeignKey(
        Issue, null=True, related_name='target_series_bond_revisions')

    bond_type = models.ForeignKey(SeriesBondType, null=True,
                                  related_name='bond_revisions')
    notes = models.TextField(max_length=255, default='', blank=True)

    previous_revision = models.OneToOneField('self', null=True,
                                             related_name='next_revision')

    def previous(self):
        return self.previous_revision

    def _field_list(self):
        return (['origin', 'origin_issue', 'target', 'target_issue'] +
                get_series_bond_field_list())

    def _get_blank_values(self):
        return {
            'origin': None,
            'origin_issue': None,
            'target': None,
            'target_issue': None,
            'bond_type': None,
            'notes': '',
        }

    def _start_imp_sum(self):
        self._seen_origin = False
        self._seen_target = False

    def _imps_for(self, field_name):
        """
        Only one point per origin/target change
        """
        if field_name in ('origin', 'origin_issue'):
            if not self._seen_origin:
                self._seen_origin = True
                return 1
        if field_name in ('target',
                          'target_issue'):
            if not self._seen_target:
                self._seen_target = True
                return 1
        if field_name in get_series_bond_field_list():
            return 1
        return 0

    def _get_source(self):
        return self.series_bond

    def _get_source_name(self):
        return 'series_bond'

    def _queue_name(self):
        return u'%s continues at %s' % (self.origin, self.target)

    def commit_to_display(self):
        series_bond = self.series_bond
        if self.deleted:
            for revision in series_bond.revisions.all():
                setattr(revision, "series_bond_id", None)
                revision.save()
            series_bond.delete()
            return

        if series_bond is None:
            series_bond = SeriesBond()
        series_bond.origin = self.origin
        series_bond.origin_issue = self.origin_issue
        series_bond.target = self.target
        series_bond.target_issue = self.target_issue
        series_bond.notes = self.notes
        series_bond.bond_type = self.bond_type

        series_bond.save()
        if self.series_bond is None:
            self.series_bond = series_bond
            self.save()

    def __unicode__(self):
        if self.origin_issue:
            object_string = u'%s' % self.origin_issue
        else:
            object_string = u'%s' % self.origin
        if self.target_issue:
            object_string += u' continues at %s' % self.target_issue
        else:
            object_string += u' continues at %s' % self.target
        return object_string


class IssueRevisionManager(RevisionManager):

    def clone_revision(self, issue, changeset):
        """
        Given an existing Issue instance, create a new revision based on it.

        This new revision will be where the edits are made.
        If there are no revisions, first save a baseline so that the pre-edit
        values are preserved.
        Entirely new issues should be started by simply instantiating
        a new IssueRevision directly.
        """
        return RevisionManager.clone_revision(self,
                                              instance=issue,
                                              instance_class=Issue,
                                              changeset=changeset)

    def _do_create_revision(self, issue, changeset, **ignore):
        """
        Helper delegate to do the class-specific work of clone_revision.
        """
        revision = IssueRevision(
            # revision-specific fields:
            issue=issue,
            changeset=changeset,

            # copied fields:
            number=issue.number,
            title=issue.title,
            no_title=issue.no_title,
            volume=issue.volume,
            no_volume=issue.no_volume,
            volume_not_printed = issue.volume_not_printed,
            display_volume_with_number=issue.display_volume_with_number,
            publication_date=issue.publication_date,
            key_date=issue.key_date,
            on_sale_date_uncertain=issue.on_sale_date_uncertain,
            price=issue.price,
            indicia_frequency=issue.indicia_frequency,
            no_indicia_frequency=issue.no_indicia_frequency,
            series=issue.series,
            indicia_publisher=issue.indicia_publisher,
            indicia_pub_not_printed=issue.indicia_pub_not_printed,
            brand=issue.brand,
            no_brand=issue.no_brand,
            page_count=issue.page_count,
            page_count_uncertain=issue.page_count_uncertain,
            editing=issue.editing,
            no_editing=issue.no_editing,
            barcode=issue.barcode,
            no_barcode=issue.no_barcode,
            isbn=issue.isbn,
            no_isbn=issue.no_isbn,
            variant_of=issue.variant_of,
            variant_name=issue.variant_name,
            rating=issue.rating,
            no_rating=issue.no_rating,
            notes=issue.notes,
            keywords=get_keywords(issue))

        if issue.on_sale_date:
            (revision.year_on_sale,
             revision.month_on_sale,
             revision.day_on_sale) = on_sale_date_fields(issue.on_sale_date)

        revision.save()
        return revision


def get_issue_field_list():
    return ['number', 'title', 'no_title', 'volume',
            'no_volume', 'volume_not_printed', 'display_volume_with_number',
            'indicia_publisher', 'indicia_pub_not_printed',
            'brand', 'no_brand', 'publication_date', 'year_on_sale',
            'month_on_sale', 'day_on_sale', 'on_sale_date_uncertain',
            'key_date', 'indicia_frequency', 'no_indicia_frequency', 'price',
            'page_count', 'page_count_uncertain', 'editing', 'no_editing',
            'isbn', 'no_isbn', 'barcode', 'no_barcode', 'rating', 'no_rating',
            'notes', 'keywords']


class IssueRevision(Revision):
    class Meta:
        db_table = 'oi_issue_revision'
        ordering = ['-created', '-id']

    objects = IssueRevisionManager()

    issue = models.ForeignKey(Issue, null=True, related_name='revisions')

    # If not null, insert or move the issue after the given issue
    # when saving back the the DB. If null, place at the beginning of
    # the series.
    after = models.ForeignKey(
        Issue, null=True, blank=True, related_name='after_revisions')

    # This is used *only* for multiple issues within the same changeset.
    # It does NOT correspond directly to gcd_issue.sort_code, which must be
    # calculated at the time the revision is committed.
    revision_sort_code = models.IntegerField(null=True)

    # When adding an issue, this requests the reservation upon approval of
    # the new issue.  The request will be granted unless an ongoing reservation
    # is in place at the time of approval.
    reservation_requested = models.BooleanField(default=False)

    number = models.CharField(max_length=50)

    title = models.CharField(max_length=255, default='', blank=True)
    no_title = models.BooleanField(default=False)

    volume = models.CharField(max_length=50, blank=True, default='')
    no_volume = models.BooleanField(default=False)
    volume_not_printed = models.BooleanField(default=False)
    display_volume_with_number = models.BooleanField(default=False)
    variant_of = models.ForeignKey(Issue, null=True,
                                   related_name='variant_revisions')
    variant_name = models.CharField(max_length=255, blank=True, default='')

    publication_date = models.CharField(max_length=255, blank=True, default='')
    key_date = models.CharField(
        max_length=10, blank=True, default='',
        validators=[RegexValidator(
            r'^(17|18|19|20)\d{2}(\.|-)(0[0-9]|1[0-3])(\.|-)\d{2}$')])
    year_on_sale = models.IntegerField(db_index=True, null=True, blank=True)
    month_on_sale = models.IntegerField(db_index=True, null=True, blank=True)
    day_on_sale = models.IntegerField(db_index=True, null=True, blank=True)
    on_sale_date_uncertain = models.BooleanField(default=False)
    indicia_frequency = models.CharField(max_length=255, blank=True,
                                         default='')
    no_indicia_frequency = models.BooleanField(default=False)

    price = models.CharField(max_length=255, blank=True, default='')
    page_count = models.DecimalField(max_digits=10, decimal_places=3,
                                     null=True, blank=True, default=None)
    page_count_uncertain = models.BooleanField(default=False)

    editing = models.TextField(blank=True, default='')
    no_editing = models.BooleanField(default=False)
    notes = models.TextField(blank=True, default='')
    keywords = models.TextField(blank=True, default='')

    series = models.ForeignKey(Series, related_name='issue_revisions')
    indicia_publisher = models.ForeignKey(
        IndiciaPublisher, null=True, blank=True, default=None,
        related_name='issue_revisions')
    indicia_pub_not_printed = models.BooleanField(default=False)
    brand = models.ForeignKey(
        Brand, null=True, default=None, blank=True,
        related_name='issue_revisions')
    no_brand = models.BooleanField(default=False)

    isbn = models.CharField(max_length=32, blank=True, default='')
    no_isbn = models.BooleanField(default=False)

    barcode = models.CharField(max_length=38, blank=True, default='')
    no_barcode = models.BooleanField(default=False)

    rating = models.CharField(max_length=255, blank=True, default='')
    no_rating = models.BooleanField(default=False)

    date_inferred = models.BooleanField(default=False)

    @property
    def valid_isbn(self):
        return validated_isbn(self.isbn)

    @property
    def display_number(self):
        number = issue_descriptor(self)
        if number:
            return u'#' + number
        else:
            return u''

    @property
    def sort_code(self):
        if self.issue is None:
            return 0
        return self.issue.sort_code

    @property
    def on_sale_date(self):
        return on_sale_date_as_string(self)

    def active_covers(self):
        raise NotImplementedError

    def shown_covers(self):
        raise NotImplementedError

    @property
    def other_issue_revision(self):
        if self.changeset.change_type in [CTYPES['variant_add'],
                                          CTYPES['two_issues']]:
            if not hasattr(self, '_saved_other_issue'):
                self._saved_other_issue_revision = self.changeset\
                    .issuerevisions.exclude(issue=self.issue)[0]
            return self._saved_other_issue_revision
        else:
            raise ValueError

    def variant_covers(self):
        image_set = Cover.objects.none()
        if self.issue and not self.variant_of:
            if self.changeset.change_type in [CTYPES['variant_add'],
                                              CTYPES['two_issues']] \
                    and self.changeset.coverrevisions.count():
                image_set |= self.issue.variant_covers()
                if self.other_issue_revision.variant_of == self.issue:
                    # maybe a cover move from the variant issue
                    ids = list(self.changeset.coverrevisions
                                   .filter(issue=self.issue)
                                   .values_list('cover__id', flat=True))
                    image_set |= Cover.objects.filter(id__in=ids)
                    # maybe a cover move from the other issue for 'two_issues'
                    if self.changeset.change_type == CTYPES['two_issues']:
                        exclude_ids = list(self.changeset.coverrevisions
                                               .exclude(issue=self.issue)
                                               .values_list('cover__id',
                                                            flat=True))
                        image_set = image_set.exclude(id__in=exclude_ids)
            else:
                image_set |= self.issue.variant_covers()
        elif self.variant_of:
            if self.changeset.change_type in [CTYPES['variant_add'],
                                              CTYPES['two_issues']] \
               and self.changeset.coverrevisions.count():
                image_set |= self.variant_of.variant_covers()
                if self.issue:
                    # take out owns ones
                    image_set = image_set.exclude(issue=self.issue)
                    if self.variant_of == self.other_issue_revision.issue:
                        # maybe a cover move to the other issue
                        # for 'two_issues'
                        ids = list(self.changeset.coverrevisions
                                                 .filter(issue=self.issue)
                                                 .values_list('cover__id',
                                                              flat=True))
                        image_set |= Cover.objects.filter(id__in=ids)
                if self.variant_of == self.other_issue_revision.issue:
                    # maybe a cover move from the other issue to exclude
                    exclude_ids = list(self.changeset.coverrevisions
                                           .exclude(issue=self.issue)
                                           .values_list('cover__id',
                                                        flat=True))
                    image_set |= self.variant_of.active_covers()\
                                                .exclude(id__in=exclude_ids)
                else:
                    image_set |= self.variant_of.active_covers()
            elif self.issue:
                image_set |= self.issue.variant_covers()
            else:
                image_set |= self.variant_of.variant_covers()
                image_set |= self.variant_of.active_covers()
        return image_set

    def has_covers(self):
        if self.issue is None:
            return False
        return self.issue.has_covers()

    def has_reprints(self):
        if self.issue is None:
            return False
        return (self.from_reprints.count() or
                self.to_reprints.count() or
                self.from_issue_reprints.count() or
                self.to_issue_reprints.count())

    def can_add_reprints(self):
        if self.variant_of and self.ordered_story_revisions().count() > 0:
            return False
        return True

    # we need two checks if relevant reprint revisions exist:
    # 1) revisions which are active and link self.issue with a story/issue
    #    in the current direction under consideration
    # 2) existing reprints which are locked and which link self.issue
    #    with a story/issue in the current direction under consideration
    # if this is the case we return reprintrevisions and not reprint links
    # returned reprint links are three cases:
    # a) revisions in the current changeset which link self.issue with a
    #    story/issue in the current direction under consideration
    # b) newly added and active revisions in other changesets
    #    we do not need .exclude(changeset__id=self.changeset_id)\ the new
    #    ones from the current changeset we want anyway
    # c) for the current corresponding reprint links the latest revisions
    #    which are not in the current changeset, the latest can be fetched
    #    via next_revision=None, that way we get either approved or active ones

    def old_revisions_base(self):
        revs = ReprintRevision.objects \
                              .exclude(changeset__id=self.changeset_id)\
                              .exclude(changeset__state=states.DISCARDED)
        return revs

    def from_reprints_oi(self, preview=False):
        if self.issue is None:
            return ReprintToIssue.objects.none()
        from_reprints = self.issue.from_reprints.all()
        if self.issue.target_reprint_revisions\
               .filter(changeset__state__in=states.ACTIVE)\
               .filter(origin_issue=None).count() \
                or RevisionLock.objects.filter(
                  object_id__in=from_reprints.values_list(
                                              'id', flat=True)).exists():
            new_revisions = self.issue.target_reprint_revisions\
                                .filter(changeset__id=self.changeset_id)\
                                .filter(origin_issue=None)
            if not preview:
                new_revisions |= \
                    self.issue.target_reprint_revisions\
                        .filter(changeset__state__in=states.ACTIVE,
                                in_type=None)\
                        .filter(origin_issue=None)
            else:
                new_revisions = new_revisions.exclude(deleted=True)
            existing_reprints = from_reprints
            old_revisions = self.old_revisions_base()\
                                .filter(reprint_to_issue__in=existing_reprints,
                                        next_revision=None)
            return new_revisions | old_revisions
        else:
            return from_reprints

    @property
    def from_reprints(self):
        return self.from_reprints_oi(preview=True)

    def from_issue_reprints_oi(self, preview=False):
        if self.issue is None:
            return IssueReprint.objects.none()
        from_issue_reprints = self.issue.from_issue_reprints.all()
        if self.issue.target_reprint_revisions\
               .filter(changeset__state__in=states.ACTIVE)\
               .exclude(origin_issue=None).count() \
                or RevisionLock.objects.filter(
                  object_id__in=from_issue_reprints.values_list(
                                                    'id', flat=True)).exists():
            new_revisions = self.issue.target_reprint_revisions\
                                .filter(changeset__id=self.changeset_id)\
                                .exclude(origin_issue=None)
            if not preview:
                new_revisions |= \
                    self.issue.target_reprint_revisions\
                        .filter(changeset__state__in=states.ACTIVE,
                                in_type=None)\
                        .exclude(origin_issue=None)
            else:
                new_revisions = new_revisions.exclude(deleted=True)
            existing_reprints = from_issue_reprints
            old_revisions = self.old_revisions_base()\
                                .filter(issue_reprint__in=existing_reprints,
                                        next_revision=None)
            return new_revisions | old_revisions
        else:
            return from_issue_reprints

    @property
    def from_issue_reprints(self):
        return self.from_issue_reprints_oi(preview=True)

    def to_reprints_oi(self, preview=False):
        if self.issue is None:
            return ReprintFromIssue.objects.none()
        to_reprints = self.issue.to_reprints.all()
        if self.issue.origin_reprint_revisions\
               .filter(changeset__state__in=states.ACTIVE)\
               .filter(target_issue=None).count() \
                or RevisionLock.objects.filter(
                  object_id__in=to_reprints.values_list(
                                            'id', flat=True)).exists():
            new_revisions = self.issue.origin_reprint_revisions\
                                .filter(changeset__id=self.changeset_id)\
                                .filter(target_issue=None)
            if not preview:
                new_revisions |= \
                    self.issue.origin_reprint_revisions\
                        .filter(changeset__state__in=states.ACTIVE,
                                in_type=None)\
                        .filter(target_issue=None)
            else:
                new_revisions = new_revisions.exclude(deleted=True)
            existing_reprints = to_reprints
            old_revisions = \
                self.old_revisions_base()\
                    .filter(reprint_from_issue__in=existing_reprints,
                            next_revision=None)
            return new_revisions | old_revisions
        else:
            return to_reprints

    @property
    def to_reprints(self):
        return self.to_reprints_oi(preview=True)

    def to_issue_reprints_oi(self, preview=False):
        if self.issue is None:
            return IssueReprint.objects.none()
        to_issue_reprints = self.issue.to_issue_reprints.all()
        if self.issue.origin_reprint_revisions\
               .filter(changeset__state__in=states.ACTIVE)\
               .exclude(target_issue=None).count() \
                or RevisionLock.objects.filter(
                  object_id__in=to_issue_reprints.values_list(
                                                  'id', flat=True)).exists():
            new_revisions = self.issue.origin_reprint_revisions\
                                .filter(changeset__id=self.changeset_id)\
                                .exclude(target_issue=None)
            if not preview:
                new_revisions |= \
                    self.issue.origin_reprint_revisions\
                        .filter(changeset__state__in=states.ACTIVE,
                                in_type=None)\
                        .exclude(target_issue=None)
            else:
                new_revisions = new_revisions.exclude(deleted=True)
            existing_reprints = to_issue_reprints
            old_revisions = self.old_revisions_base()\
                                .filter(issue_reprint__in=existing_reprints,
                                        next_revision=None)
            return new_revisions | old_revisions
        else:
            return to_issue_reprints

    @property
    def to_issue_reprints(self):
        return self.to_issue_reprints_oi(preview=True)

    def has_reprint_revisions(self):
        if self.issue is None:
            if self.target_reprint_revisions\
                   .filter(changeset__id=self.changeset_id).count():
                return True
            elif self.origin_reprint_revisions\
                     .filter(changeset__id=self.changeset_id).count():
                return True
            else:
                return False
        if self.issue.target_reprint_revisions\
               .filter(changeset__id=self.changeset_id).count():
            return True
        elif self.issue.origin_reprint_revisions\
                 .filter(changeset__id=self.changeset_id).count():
            return True
        # TODO: before there was the reserved=True here in the filter, why ?
        if self.issue.to_reprints\
               .filter(revisions__changeset=self.changeset)\
               .count():
            return True
        if self.issue.from_reprints\
               .filter(revisions__changeset=self.changeset)\
               .count():
            return True
        if self.issue.to_issue_reprints\
               .filter(revisions__changeset=self.changeset)\
               .count():
            return True
        if self.issue.from_issue_reprints\
               .filter(revisions__changeset=self.changeset)\
               .count():
            return True
        if self.changeset.state == states.APPROVED:
            active = ReprintRevision.objects.\
                filter(next_revision__in=self.changeset.reprintrevisions.all())
            if active.filter(origin_issue=self.issue):
                return True
            if active.filter(target_issue=self.issue):
                return True
        return False

    def _empty_reprint_revisions(self):
        return ReprintRevision.objects.none()
    origin_reprint_revisions = property(_empty_reprint_revisions)
    target_reprint_revisions = property(_empty_reprint_revisions)

    def other_variants(self):
        if self.variant_of:
            variants = self.variant_of.variant_set.all()
            if self.issue:
                variants = variants.exclude(id=self.issue.id)
        else:
            variants = self.variant_set.all()
        variants = list(variants.exclude(deleted=True))

        if self.changeset.change_type == CTYPES['variant_add'] \
                and not self.variant_of:
            variants.extend(self.changeset.issuerevisions
                                          .exclude(issue=self.issue))

        return variants

    @property
    def variant_set(self):
        if self.issue is None:
            return Issue.objects.none()
        return self.issue.variant_set.all()

    def active_stories(self):
        return self.story_set.exclude(deleted=True)

    def shown_stories(self):
        if self.variant_of:
            if self.changeset.issuerevisions.filter(issue=self.variant_of)\
                                            .count():
                # if base_issue is part of the changeset use the storyrevisions
                base_issue = self.changeset.issuerevisions\
                                           .filter(issue=self.variant_of).get()
            else:
                base_issue = self.variant_of
            stories = list(base_issue.active_stories()
                                     .order_by('sequence_number')
                                     .select_related('type'))
        else:
            stories = list(self.active_stories().order_by('sequence_number')
                                                .select_related('type'))
        if self.series.is_comics_publication:
            if (len(stories) > 0):
                cover_story = stories.pop(0)
                if self.variant_of:
                    # can have only one sequence, the variant cover
                    own_stories = list(self.active_stories())
                    if own_stories:
                        cover_story = own_stories[0]
            elif self.variant_of and len(list(self.active_stories())):
                cover_story = self.active_stories()[0]
            else:
                cover_story = None
        else:
            cover_story = None
        return cover_story, stories

    @property
    def story_set(self):
        return self.ordered_story_revisions()

    @property
    def reservation_set(self):
        # Just totally fake this for now.
        # TODO delete this, I think
        return Reservation.objects.filter(pk__isnull=True)

    def get_prev_next_issue(self):
        if self.issue is not None:
            return self.issue.get_prev_next_issue()
        if self.after is not None:
            [p, n] = self.after.get_prev_next_issue()
            return [self.after, n]
        return [None, None]

    def _field_list(self):
        fields = get_issue_field_list()
        if self.changeset.change_type == CTYPES['issue_add'] or \
           self.changeset.change_type == CTYPES['variant_add'] and \
           self.variant_of:
            fields = ['after'] + fields
        if not self.series.has_barcode and \
           self.changeset.change_type != CTYPES['issue_bulk']:
            fields.remove('barcode')
            fields.remove('no_barcode')
        if not self.series.has_indicia_frequency and \
           self.changeset.change_type != CTYPES['issue_bulk']:
            fields.remove('indicia_frequency')
            fields.remove('no_indicia_frequency')
        if not self.series.has_isbn and \
           self.changeset.change_type != CTYPES['issue_bulk']:
            fields.remove('isbn')
            fields.remove('no_isbn')
        if not self.series.has_issue_title and \
           self.changeset.change_type != CTYPES['issue_bulk']:
            fields.remove('title')
            fields.remove('no_title')
        if not self.series.has_volume and \
           self.changeset.change_type != CTYPES['issue_bulk']:
            fields.remove('volume')
            fields.remove('no_volume')
            field.remove('volume_not_printed')
            fields.remove('display_volume_with_number')
        if self.variant_of or (self.issue and self.issue.variant_set.count()) \
           or self.changeset.change_type == CTYPES['variant_add']:
            fields = fields[0:1] + ['variant_name'] + fields[1:]
        if self.previous() and (self.previous().series != self.series):
            fields = ['series'] + fields
        return fields

    def _get_blank_values(self):
        return {
            'number': '',
            'title': '',
            'no_title': False,
            'volume': '',
            'no_volume': False,
            'volume_not_printed': False,
            'display_volume_with_number': None,
            'publication_date': '',
            'price': '',
            'key_date': '',
            'year_on_sale': None,
            'month_on_sale': None,
            'day_on_sale': None,
            'on_sale_date_uncertain': False,
            'indicia_frequency': '',
            'no_indicia_frequency': False,
            'series': None,
            'indicia_publisher': None,
            'indicia_pub_not_printed': False,
            'brand': None,
            'no_brand': False,
            'page_count': None,
            'page_count_uncertain': False,
            'editing': '',
            'no_editing': False,
            'isbn': '',
            'no_isbn': False,
            'barcode': '',
            'no_barcode': False,
            'rating': '',
            'no_rating': False,
            'notes': '',
            'sort_code': None,
            'after': None,
            'variant_name': '',
            'keywords': ''
        }

    def _start_imp_sum(self):
        self._seen_volume = False
        self._seen_title = False
        self._seen_indicia_publisher = False
        self._seen_indicia_frequency = False
        self._seen_brand = False
        self._seen_page_count = False
        self._seen_editing = False
        self._seen_isbn = False
        self._seen_barcode = False
        self._seen_rating = False
        self._seen_on_sale_date = False

    def _imps_for(self, field_name):
        if field_name in ('number', 'publication_date', 'key_date', 'series',
                          'price', 'notes', 'variant_name', 'keywords'):
            return 1
        if not self._seen_volume and \
           field_name in ('volume', 'no_volume', 'volume_not_printed',
                          'display_volume_with_number'):
            self._seen_volume = True
            return 1
        if not self._seen_title and field_name in ('title', 'no_title'):
            self._seen_title = True
            return 1
        if not self._seen_indicia_publisher and \
           field_name in ('indicia_publisher', 'indicia_pub_not_printed'):
            self._seen_indicia_publisher = True
            return 1
        if not self._seen_indicia_frequency and \
           field_name in ('indicia_frequency', 'no_indicia_frequency'):
            self._seen_indicia_frequency = True
            return 1
        if not self._seen_brand and field_name in ('brand', 'no_brand'):
            self._seen_brand = True
            return 1
        if not self._seen_page_count and \
           field_name in ('page_count', 'page_count_uncertain'):
            self._seen_page_count = True
            if field_name == 'page_count':
                return 1

            # checking the 'uncertain' box  without also at least guessing
            # the page count itself doesn't count as IMP-worthy information.
            if field_name == 'page_count_uncertain' and \
               self.page_count is not None:
                return 1
        if not self._seen_editing and field_name in ('editing', 'no_editing'):
            self._seen_editing = True
            return 1
        if not self._seen_isbn and field_name in ('isbn', 'no_isbn'):
            self._seen_isbn = True
            return 1
        if not self._seen_barcode and field_name in ('barcode', 'no_barcode'):
            self._seen_barcode = True
            return 1
        if not self._seen_rating and field_name in ('rating', 'no_rating'):
            self._seen_rating = True
            return 1
        if not self._seen_on_sale_date and \
           field_name in ('year_on_sale', 'month_on_sale',
                          'day_on_sale', 'on_sale_date_uncertain'):
            self._seen_on_sale_date = True
            if field_name in ('year_on_sale', 'month_on_sale', 'day_on_sale'):
                return 1

            if field_name == 'on_sale_date_uncertain':
                if self.year_on_sale or self.month_on_sale or self.day_on_sale:
                    return 1
        # Note, the "after" field does not directly contribute IMPs.
        return 0

    def _get_source(self):
        return self.issue

    def _get_source_name(self):
        return 'issue'

    def _do_complete_added_revision(self, series, variant_of=None):
        """
        Do the necessary processing to complete the fields of a new
        issue revision for adding a record before it can be saved.
        """
        self.series = series
        if variant_of:
            self.variant_of = variant_of

    def _create_dependent_revisions(self, delete=False):
        for story in self.issue.active_stories():
            # currently stories cannot be reserved without the issue, but
            # check anyway
            # TODO check if transaction rollback works
            story_lock = _get_revision_lock(story, changeset=self.changeset)
            if story_lock is None:
                raise IntegrityError("needed Story lock not possible")
            story_revision = StoryRevision.objects.clone_revision(
              story=story, changeset=self.changeset)
            if delete:
                story_revision.toggle_deleted()
        if delete:
            for cover in self.issue.active_covers():
                # cover can be reserved, so this can fail
                # TODO check if transaction rollback works
                cover_lock = _get_revision_lock(cover,
                                                changeset=self.changeset)
                if cover_lock is None:
                    raise IntegrityError("needed Cover lock not possible")
                # TODO change CoverRevision handling to normal one
                cover_revision = CoverRevision(changeset=self.changeset,
                                               issue=cover.issue,
                                               cover=cover, deleted=True)
                cover_revision.save()
        return True

    def _post_commit_to_display(self):
        if self.changeset.changeset_action() == ACTION_MODIFY and \
           self.issue.is_indexed != INDEXED['skeleton']:
            RecentIndexedIssue.objects.update_recents(self.issue)

    def _story_revisions(self):
        if self.source is None:
            return self.changeset.storyrevisions.filter(issue__isnull=True)\
                                 .select_related('changeset', 'type')
        return self.changeset.storyrevisions.filter(issue=self.source)\
                             .select_related('changeset', 'issue', 'type')

    def ordered_story_revisions(self):
        return self._story_revisions().order_by('sequence_number')

    def next_sequence_number(self):
        stories = self._story_revisions()
        if stories.count():
            return stories.order_by('-sequence_number')[0].sequence_number + 1
        return 0

    def commit_to_display(self, space_count=1):
        issue = self.issue
        check_series_order = None

        if issue is None:
            if self.after is None:
                after_code = -1
            else:
                after_code = self.after.sort_code

            # sort_codes tend to be sequential, so just always increment them
            # out of the way.
            later_issues = Issue.objects.filter(
                series=self.series,
                sort_code__gt=after_code).order_by('-sort_code')

            # Make space for the issue(s) being added.  The changeset will
            # pass a larger number or zero in order to make all necessary
            # space for a multiple add on the first pass, and then not
            # have to update this for the remaining issues.
            if space_count > 0:
                # Unique constraint prevents us from doing this:
                # later_issues.update(sort_code=F('sort_code') + space_count)
                # which is vastly more efficient.  TODO: revisit.
                for later_issue in later_issues:
                    later_issue.sort_code += space_count
                    later_issue.save()

            issue = Issue(sort_code=after_code + 1)
            if self.variant_of:
                if self.series.is_comics_publication:
                    update_count('variant issues', 1,
                                 language=self.series.language,
                                 country=self.series.country)
            else:
                self.series.issue_count = F('issue_count') + 1
                # do NOT save the series here, it gets saved later in
                # self._check_first_last(), if we save here as well
                # the issue_count goes up by 2
                if self.series.is_comics_publication:
                    self.series.publisher.issue_count = F('issue_count') + 1
                    self.series.publisher.save()
                    if self.brand:
                        self.brand.issue_count = F('issue_count') + 1
                        self.brand.save()
                        for group in self.brand.group.all():
                            group.issue_count = F('issue_count') + 1
                            group.save()
                    if self.indicia_publisher:
                        self.indicia_publisher.issue_count = \
                            F('issue_count') + 1
                        self.indicia_publisher.save()
                    update_count('issues', 1, language=self.series.language,
                                 country=self.series.country)

        elif self.deleted:
            if self.variant_of:
                if self.series.is_comics_publication:
                    update_count('variant issues', -1,
                                 language=self.series.language,
                                 country=self.series.country)
            else:
                self.series.issue_count = F('issue_count') - 1
                # do NOT save the series here, it gets saved later in
                # self._check_first_last(), if we save here as well
                # the issue_count goes down by 2
                if self.series.is_comics_publication:
                    self.series.publisher.issue_count = F('issue_count') - 1
                    self.series.publisher.save()
                    if self.brand:
                        self.brand.issue_count = F('issue_count') - 1
                        self.brand.save()
                        for group in self.brand.group.all():
                            group.issue_count = F('issue_count') - 1
                            group.save()
                    if self.indicia_publisher:
                        self.indicia_publisher.issue_count = \
                            F('issue_count') - 1
                        self.indicia_publisher.save()
                    update_count('issues', -1, language=issue.series.language,
                                 country=issue.series.country)
            issue.delete()
            self._check_first_last()
            return

        else:
            if not self.variant_of and self.series.is_comics_publication:
                if self.brand != issue.brand:
                    if self.brand:
                        self.brand.issue_count = F('issue_count') + 1
                        self.brand.save()
                        for group in self.brand.group.all():
                            group.issue_count = F('issue_count') + 1
                            group.save()
                    if issue.brand:
                        issue.brand.issue_count = F('issue_count') - 1
                        issue.brand.save()
                        for group in issue.brand.group.all():
                            group.issue_count = F('issue_count') - 1
                            group.save()
                if self.indicia_publisher != issue.indicia_publisher:
                    if self.indicia_publisher:
                        self.indicia_publisher.issue_count = \
                            F('issue_count') + 1
                        self.indicia_publisher.save()
                    if issue.indicia_publisher:
                        issue.indicia_publisher.issue_count = \
                            F('issue_count') - 1
                        issue.indicia_publisher.save()
            if self.series != issue.series:
                if self.series.issue_count:
                    # move to the end of the new series
                    issue.sort_code = (self.series.active_issues()
                                                  .latest('sort_code')
                                                  .sort_code) + 1
                else:
                    issue.sort_code = 0
                # update counts
                if self.variant_of:
                    if self.series.language != issue.series.language or \
                       self.series.country != issue.series.country:
                        if self.series.is_comics_publication:
                            update_count('variant issues', 1,
                                         language=self.series.language,
                                         country=self.series.country)
                        if issue.series.is_comics_publication:
                            update_count('variant issues', -1,
                                         language=issue.series.language,
                                         country=issue.series.country)
                else:
                    self.series.issue_count = F('issue_count') + 1
                    issue.series.issue_count = F('issue_count') - 1
                    if self.series.publisher != issue.series.publisher:
                        if self.series.is_comics_publication:
                            if self.series.publisher:
                                self.series.publisher.issue_count = \
                                    F('issue_count') + 1
                                self.series.publisher.save()
                        if issue.series.is_comics_publication:
                            if issue.series.publisher:
                                issue.series.publisher.issue_count = \
                                    F('issue_count') - 1
                                issue.series.publisher.save()
                    if self.series.language != issue.series.language or \
                       self.series.country != issue.series.country:
                        if self.series.is_comics_publication:
                            update_count('issues', 1,
                                         language=self.series.language,
                                         country=self.series.country)
                        if issue.series.is_comics_publication:
                            update_count('issues', -1,
                                         language=issue.series.language,
                                         country=issue.series.country)
                        story_count = self.issue.active_stories().count()
                        update_count('stories', story_count,
                                     language=self.series.language,
                                     country=self.series.country)
                        update_count('stories', -story_count,
                                     language=issue.series.language,
                                     country=issue.series.country)
                        cover_count = self.issue.active_covers().count()
                        update_count('covers', cover_count,
                                     language=self.series.language,
                                     country=self.series.country)
                        update_count('covers', -cover_count,
                                     language=issue.series.language,
                                     country=issue.series.country)

                check_series_order = issue.series
                # new series might have gallery after move
                # do NOT save the series here, it gets saved later
                if self.series.has_gallery is False:
                    if issue.active_covers().count():
                        self.series.has_gallery = True
                # old series might have lost gallery after move
                if issue.series.scan_count() == \
                   issue.active_covers().count():
                    issue.series.has_gallery = False

        issue.number = self.number
        # only if the series has_field is True write to issue
        if self.series.has_issue_title:
            issue.title = self.title
            issue.no_title = self.no_title
        # handle case when series has_field changes during lifetime
        # of issue changeset, then changeset resets to issue data
        else:
            self.title = issue.title
            self.no_title = issue.no_title
            self.save()

        if self.series.has_volume:
            issue.volume = self.volume
            issue.no_volume = self.no_volume
            issue.volume_not_printed = self.volume_not_printed
            issue.display_volume_with_number = self.display_volume_with_number
        else:
            self.volume = issue.volume
            self.no_volume = issue.no_volume
            self.volume_not_printed = issue.volume_not_printed
            self.display_volume_with_number = issue.display_volume_with_number
            self.save()

        issue.variant_of = self.variant_of
        issue.variant_name = self.variant_name

        issue.publication_date = self.publication_date
        issue.key_date = self.key_date
        issue.on_sale_date = on_sale_date_as_string(self)
        issue.on_sale_date_uncertain = self.on_sale_date_uncertain

        if self.series.has_indicia_frequency:
            issue.indicia_frequency = self.indicia_frequency
            issue.no_indicia_frequency = self.no_indicia_frequency
        else:
            self.indicia_frequency = issue.indicia_frequency
            self.no_indicia_frequency = issue.no_indicia_frequency
            self.save()

        issue.price = self.price
        issue.page_count = self.page_count
        issue.page_count_uncertain = self.page_count_uncertain

        issue.editing = self.editing
        issue.no_editing = self.no_editing
        issue.notes = self.notes
        issue.series = self.series
        issue.indicia_publisher = self.indicia_publisher
        issue.indicia_pub_not_printed = self.indicia_pub_not_printed
        issue.brand = self.brand
        issue.no_brand = self.no_brand

        if self.series.has_isbn:
            issue.isbn = self.isbn
            issue.no_isbn = self.no_isbn
            issue.valid_isbn = validated_isbn(issue.isbn)
        else:
            self.isbn = issue.isbn
            self.no_isbn = issue.no_isbn
            self.save()

        if self.series.has_barcode:
            issue.barcode = self.barcode
            issue.no_barcode = self.no_barcode
        else:
            self.barcode = issue.barcode
            self.no_barcode = issue.no_barcode
            self.save()

        if self.series.has_rating:
            issue.rating = self.rating
            issue.no_rating = self.no_rating
        else:
            self.rating = issue.rating
            self.no_rating = issue.no_rating
            self.save()

        issue.save()
        save_keywords(self, issue)
        issue.save()
        if self.issue is None:
            self.issue = issue
            self.save()
            self._check_first_last()
            for story in self.changeset.storyrevisions.filter(issue=None):
                story.issue = issue
                story.save()

        if check_series_order:
            set_series_first_last(check_series_order)
            self._check_first_last()

    def _check_first_last(self):
        set_series_first_last(self.series)

    def get_absolute_url(self):
        if self.issue is None:
            return "/issue/revision/%i/preview" % self.id
        return self.issue.get_absolute_url()

    def full_name(self):
        if self.variant_name:
            return u'%s %s [%s]' % (self.series.full_name(),
                                    self.display_number,
                                    self.variant_name)
        else:
            return u'%s %s' % (self.series.full_name(), self.display_number)

    def short_name(self):
        if self.variant_name:
            return u'%s %s [%s]' % (self.series.name,
                                    self.display_number,
                                    self.variant_name)
        else:
            return u'%s %s' % (self.series.name, self.display_number)

    def __unicode__(self):
        """
        Re-implement locally instead of using self.issue because it may change.
        """
        if self.variant_name:
            return u'%s %s [%s]' % (self.series, self.display_number,
                                    self.variant_name)
        elif self.display_number:
            return u'%s %s' % (self.series, self.display_number)
        else:
            return u'%s' % self.series


def get_story_field_list():
    return ['sequence_number', 'title', 'title_inferred', 'type',
            'feature', 'genre', 'job_number',
            'script', 'no_script', 'pencils', 'no_pencils', 'inks',
            'no_inks', 'colors', 'no_colors', 'letters', 'no_letters',
            'editing', 'no_editing', 'page_count', 'page_count_uncertain',
            'characters', 'synopsis', 'reprint_notes', 'notes', 'keywords']


class StoryRevisionManager(RevisionManager):

    def clone_revision(self, story, changeset):
        """
        Given an existing Story instance, create a new revision based on it.

        This new revision will be where the edits are made.
        If there are no revisions, first save a baseline so that the pre-edit
        values are preserved.
        Entirely new stories should be started by simply instantiating
        a new StoryRevision directly.
        """
        return RevisionManager.clone_revision(self,
                                              instance=story,
                                              instance_class=Story,
                                              changeset=changeset)

    def _do_create_revision(self, story, changeset, **ignore):
        """
        Helper delegate to do the class-specific work of clone_revision.
        """
        revision = StoryRevision(
            # revision-specific fields:
            story=story,
            changeset=changeset,

            # copied fields:
            title=story.title,
            title_inferred=story.title_inferred,
            feature=story.feature,
            page_count=story.page_count,
            page_count_uncertain=story.page_count_uncertain,

            script=story.script,
            pencils=story.pencils,
            inks=story.inks,
            colors=story.colors,
            letters=story.letters,
            editing=story.editing,

            no_script=story.no_script,
            no_pencils=story.no_pencils,
            no_inks=story.no_inks,
            no_colors=story.no_colors,
            no_letters=story.no_letters,
            no_editing=story.no_editing,

            notes=story.notes,
            keywords=get_keywords(story),
            synopsis=story.synopsis,
            characters=story.characters,
            reprint_notes=story.reprint_notes,
            genre=story.genre,
            type=story.type,
            job_number=story.job_number,
            sequence_number=story.sequence_number,

            issue=story.issue)

        revision.save()
        return revision


class StoryRevision(Revision):
    class Meta:
        db_table = 'oi_story_revision'
        ordering = ['-created', '-id']

    objects = StoryRevisionManager()

    story = models.ForeignKey(Story, null=True,
                              related_name='revisions')

    title = models.CharField(max_length=255, blank=True)
    title_inferred = models.BooleanField(default=False)
    feature = models.CharField(max_length=255, blank=True)
    type = models.ForeignKey(StoryType)
    sequence_number = models.IntegerField()

    page_count = models.DecimalField(max_digits=10, decimal_places=3,
                                     null=True, blank=True)
    page_count_uncertain = models.BooleanField(default=False)

    script = models.TextField(blank=True)
    pencils = models.TextField(blank=True)
    inks = models.TextField(blank=True)
    colors = models.TextField(blank=True)
    letters = models.TextField(blank=True)
    editing = models.TextField(blank=True)

    no_script = models.BooleanField(default=False)
    no_pencils = models.BooleanField(default=False)
    no_inks = models.BooleanField(default=False)
    no_colors = models.BooleanField(default=False)
    no_letters = models.BooleanField(default=False)
    no_editing = models.BooleanField(default=False)

    job_number = models.CharField(max_length=25, blank=True)
    genre = models.CharField(max_length=255, blank=True)
    characters = models.TextField(blank=True)
    synopsis = models.TextField(blank=True)
    reprint_notes = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    keywords = models.TextField(blank=True, default='')

    issue = models.ForeignKey(Issue, null=True, related_name='story_revisions')
    date_inferred = models.BooleanField(default=False)

    @property
    def my_issue_revision(self):
        if not hasattr(self, '_saved_my_issue_revision'):
            self._saved_my_issue_revision = \
                self.changeset.issuerevisions.filter(issue=self.issue)[0]
            return self._saved_my_issue_revision

    def toggle_deleted(self):
        """
        Mark this revision as deleted, meaning that instead of copying it
        back to the display table, the display table entry will be removed
        when the revision is committed.
        """
        self.deleted = not self.deleted
        self.save()

    def deletable(self):
        if self.changeset.reprintrevisions \
                         .filter(origin_story=self.story).count() \
                or self.changeset.reprintrevisions \
                                 .filter(target_story=self.story).count() \
                or (self.story and self.story.has_reprints(notes=False)):
            return False
        else:
            return True

    def moveable(self):
        """
        A story revision is moveable
        a) if it is not currently attached to an issue and is a revision of a
           previously existing story. Therefore it is a story which was moved
           to the version issue, this way it can be moved back.
        b) an issue version of mine in this changeset has no story attached and
           it is a cover sequence. Therefore one cover sequence can be moved
           from the base to the version issue.

        These conditions work for our current only case of a story move: i.e.
        issue versions.
        """
        if self.changeset.change_type == CTYPES['variant_add'] or \
           self.changeset.change_type == CTYPES['two_issues']:
            if self.issue is None:
                if self.story is None:
                    return False
                return True

            if self.deleted:
                return False

            if self.my_issue_revision.other_issue_revision.variant_of \
               is not None:
                # variants can only have one sequence, and it needs to be cover
                if self.changeset.storyrevisions \
                                 .exclude(issue=self.issue).count() \
                        or self.type != StoryType.objects.get(name='Cover'):
                    return False
                else:
                    return True
            return True
        else:
            return False

    def _field_list(self):
        fields = get_story_field_list()
        if self.previous() and (self.previous().issue_id != self.issue_id):
            fields = ['issue'] + fields
        return fields

    def _get_blank_values(self):
        return {
            'title': '',
            'title_inferred': '',
            'feature': '',
            'page_count': None,
            'page_count_uncertain': False,
            'script': '',
            'pencils': '',
            'inks': '',
            'colors': '',
            'letters': '',
            'editing': '',
            'no_script': False,
            'no_pencils': False,
            'no_inks': False,
            'no_colors': False,
            'no_letters': False,
            'no_editing': False,
            'notes': '',
            'keywords': '',
            'synopsis': '',
            'characters': '',
            'reprint_notes': '',
            'genre': '',
            'type': None,
            'job_number': '',
            'sequence_number': None,
            'issue': None,
        }

    def _start_imp_sum(self):
        self._seen_script = False
        self._seen_pencils = False
        self._seen_inks = False
        self._seen_colors = False
        self._seen_letters = False
        self._seen_editing = False
        self._seen_page_count = False
        self._seen_title = False

    def _imps_for(self, field_name):
        if field_name in ('sequence_number', 'type', 'feature', 'genre',
                          'characters', 'synopsis', 'job_number',
                          'reprint_notes', 'notes', 'keywords'):
            return 1
        if not self._seen_title and field_name in ('title', 'title_inferred'):
            self._seen_title = True
            return 1

        if not self._seen_page_count:
            self._seen_page_count = True
            if field_name == 'page_count':
                return 1

            # checking the 'uncertain' box  without also at least guessing
            # the page count itself doesn't count as IMP-worthy information.
            if field_name == 'page_count_uncertain' and \
               self.page_count is not None:
                return 1

        for name in ('script', 'pencils', 'inks', 'colors',
                     'letters', 'editing'):
            attr = '_seen_%s' % name
            no_name = 'no_%s' % name
            if not getattr(self, attr) and field_name in (name, no_name):
                setattr(self, attr, True)

                # Just putting in a question mark isn't worth an IMP.
                # Note that the input data is already whitespace-stripped.
                if field_name == name and getattr(self, field_name) == '?':
                    return 0
                return 1
        return 0

    def _get_source(self):
        return self.story

    def _get_source_name(self):
        return 'story'

    def _do_complete_added_revision(self, issue):
        """
        Do the necessary processing to complete the fields of a new
        story revision for adding a record before it can be saved.
        """
        self.issue = issue

    def _reset_values(self):
        if self.deleted:
            # users can edit story revisions before deleting them.
            # ensure that the final deleted revision matches the
            # final state of the story.
            self.title = self.story.title
            self.title_inferred = self.story.title_inferred
            self.feature = self.story.feature
            self.page_count = self.story.page_count
            self.page_count_uncertain = self.story.page_count_uncertain

            self.script = self.story.script
            self.pencils = self.story.pencils
            self.inks = self.story.inks
            self.colors = self.story.colors
            self.letters = self.story.letters
            self.editing = self.story.editing

            self.no_script = self.story.no_script
            self.no_pencils = self.story.no_pencils
            self.no_inks = self.story.no_inks
            self.no_colors = self.story.no_colors
            self.no_letters = self.story.no_letters
            self.no_editing = self.story.no_editing

            self.notes = self.story.notes
            self.synopsis = self.story.synopsis
            self.characters = self.story.characters
            self.reprint_notes = self.story.reprint_notes
            self.genre = self.story.genre
            self.type = self.story.type
            self.job_number = self.story.job_number
            self.sequence_number = self.story.sequence_number
            self.save()

    def commit_to_display(self):
        story = self.story
        if story is None:
            story = Story()
            update_count('stories', 1, language=self.issue.series.language,
                         country=self.issue.series.country)
        elif self.deleted:
            if self.issue.is_indexed != INDEXED['skeleton']:
                if self.issue.set_indexed_status() == INDEXED['skeleton'] and \
                   self.issue.series.is_comics_publication:
                    update_count('issue indexes', -1,
                                 language=story.issue.series.language,
                                 country=story.issue.series.country)
            update_count('stories', -1, language=story.issue.series.language,
                         country=story.issue.series.country)
            self._reset_values()
            story.delete()
            return

        story.title = self.title
        story.title_inferred = self.title_inferred
        story.feature = self.feature
        if hasattr(story, 'issue') and (story.issue != self.issue):
            if story.issue.series.language != self.issue.series.language or \
               story.issue.series.country != self.issue.series.country:
                update_count('stories', 1,
                             language=self.issue.series.language,
                             country=self.issue.series.country)
                update_count('stories', -1,
                             language=story.issue.series.language,
                             country=story.issue.series.country)
            old_issue = story.issue
            story.issue = self.issue
            if old_issue.set_indexed_status() is False:
                update_count('issue indexes', -1,
                             language=old_issue.series.language,
                             country=old_issue.series.country)
        else:
            story.issue = self.issue
        story.page_count = self.page_count
        story.page_count_uncertain = self.page_count_uncertain

        story.script = self.script
        story.pencils = self.pencils
        story.inks = self.inks
        story.colors = self.colors
        story.letters = self.letters
        story.editing = self.editing

        story.no_script = self.no_script
        story.no_pencils = self.no_pencils
        story.no_inks = self.no_inks
        story.no_colors = self.no_colors
        story.no_letters = self.no_letters
        story.no_editing = self.no_editing

        story.notes = self.notes
        story.synopsis = self.synopsis
        story.reprint_notes = self.reprint_notes
        story.characters = self.characters
        story.genre = self.genre
        story.type = self.type
        story.job_number = self.job_number
        story.sequence_number = self.sequence_number

        story.save()
        save_keywords(self, story)
        story.save()

        if self.story is None:
            self.story = story
            self.save()

        if self.issue.is_indexed == INDEXED['skeleton']:
            if self.issue.set_indexed_status() != INDEXED['skeleton'] and \
               self.issue.series.is_comics_publication:
                update_count('issue indexes', 1,
                             language=self.issue.series.language,
                             country=self.issue.series.country)
        else:
            if self.issue.set_indexed_status() == INDEXED['skeleton'] and \
               self.issue.series.is_comics_publication:
                update_count('issue indexes', -1,
                             language=self.issue.series.language,
                             country=self.issue.series.country)

    # we need two checks if relevant reprint revisions exist:
    # 1) revisions which are active and link self.story with a story/issue
    #    in the current direction under consideration
    # 2) existing reprints which are locked and which link self.story
    #    with a story/issue in the current direction under consideration
    # if this is the case we return reprintrevisions and not reprint links
    # returned reprint links are three cases:
    # a) revisions in the current changeset which link self.story with a
    #    story/issue in the current direction under consideration
    # b) newly added and active revisions in other changesets
    #    we do not need .exclude(changeset__id=self.changeset_id)\ the new
    #    ones from the current changeset we want anyway
    # c) for the current corresponding reprint links the latest revisions
    #    which are not in the current changeset, the latest can be fetched
    #    via next_revision=None, that way we get either approved or
    #    active ones

    # for newly added stories it is easy, just show reprintrevision which
    # point to the new story in the right ways

    def old_revisions_base(self):
        revs = ReprintRevision.objects \
                              .exclude(changeset__id=self.changeset_id)\
                              .exclude(changeset__state=states.DISCARDED)
        return revs

    def from_reprints_oi(self, preview=False):
        if self.story is None:
            return self.target_reprint_revisions\
                       .filter(changeset__id=self.changeset_id,
                               origin_issue=None)
        from_reprints = self.story.from_reprints.all()
        if self.story.target_reprint_revisions\
               .filter(changeset__state__in=states.ACTIVE)\
               .filter(origin_issue=None).count() \
                or RevisionLock.objects.filter(
                  object_id__in=from_reprints.values_list(
                                              'id', flat=True)).exists():
            new_revisions = self.story.target_reprint_revisions\
                                .filter(changeset__id=self.changeset_id)\
                                .filter(origin_issue=None)
            if not preview:
                new_revisions |= \
                    self.story.target_reprint_revisions\
                        .filter(changeset__state__in=states.ACTIVE,
                                in_type=None)\
                        .filter(origin_issue=None)
            else:
                new_revisions = new_revisions.exclude(deleted=True)
            existing_reprints = from_reprints
            old_revisions = self.old_revisions_base()\
                                .filter(reprint__in=existing_reprints,
                                        next_revision=None)
            return new_revisions | old_revisions
        else:
            return from_reprints

    @property
    def from_reprints(self):
        return self.from_reprints_oi(preview=True)

    def from_issue_reprints_oi(self, preview=False):
        if self.story is None:
            return self.target_reprint_revisions\
                       .filter(changeset__id=self.changeset_id)\
                       .exclude(origin_issue=None)
        from_issue_reprints = self.story.from_issue_reprints.all()
        if self.story.target_reprint_revisions\
               .filter(changeset__state__in=states.ACTIVE)\
               .exclude(origin_issue=None).count() \
                or RevisionLock.objects.filter(
                  object_id__in=from_issue_reprints.values_list(
                                                    'id', flat=True)).exists():
            new_revisions = self.story.target_reprint_revisions\
                                .filter(changeset__id=self.changeset_id)\
                                .exclude(origin_issue=None)
            if not preview:
                new_revisions |= \
                    self.story.target_reprint_revisions\
                        .filter(changeset__state__in=states.ACTIVE,
                                in_type=None)\
                        .exclude(origin_issue=None)
            else:
                new_revisions = new_revisions.exclude(deleted=True)
            existing_reprints = from_issue_reprints
            old_revisions = \
                self.old_revisions_base()\
                    .filter(reprint_from_issue__in=existing_reprints,
                            next_revision=None)
            return new_revisions | old_revisions
        else:
            return from_issue_reprints

    @property
    def from_issue_reprints(self):
        return self.from_issue_reprints_oi(preview=True)

    def to_reprints_oi(self, preview=False):
        if self.story is None:
            return self.origin_reprint_revisions\
                       .filter(changeset__id=self.changeset_id,
                               target_issue=None)

        to_reprints = self.story.to_reprints.all()
        if self.story.origin_reprint_revisions\
               .filter(changeset__state__in=states.ACTIVE)\
               .filter(target_issue=None).count() \
                or RevisionLock.objects.filter(
                  object_id__in=to_reprints.values_list(
                                            'id', flat=True)).exists():
            new_revisions = self.story.origin_reprint_revisions\
                                .filter(changeset__id=self.changeset_id)\
                                .filter(target_issue=None)
            if not preview:
                new_revisions |= \
                    self.story.origin_reprint_revisions\
                        .filter(changeset__state__in=states.ACTIVE,
                                in_type=None)\
                        .filter(target_issue=None)
            else:
                new_revisions = new_revisions.exclude(deleted=True)
            existing_reprints = to_reprints
            old_revisions = \
                self.old_revisions_base()\
                    .filter(reprint__in=existing_reprints, next_revision=None)
            return new_revisions | old_revisions
        else:
            return to_reprints

    @property
    def to_reprints(self):
        return self.to_reprints_oi(preview=True)

    def to_issue_reprints_oi(self, preview=False):
        if self.story is None:
            return self.origin_reprint_revisions\
                       .filter(changeset__id=self.changeset_id)\
                       .exclude(target_issue=None)
        to_issue_reprints = self.story.to_issue_reprints.all()
        if self.story.origin_reprint_revisions\
               .filter(changeset__state__in=states.ACTIVE)\
               .exclude(target_issue=None).count() \
                or RevisionLock.objects.filter(
                  object_id__in=to_issue_reprints.values_list(
                                                  'id', flat=True)).exists():
            new_revisions = \
                self.story.origin_reprint_revisions\
                    .filter(changeset__id=self.changeset_id)\
                    .exclude(target_issue=None)
            if not preview:
                new_revisions |= \
                    self.story.origin_reprint_revisions\
                        .filter(changeset__state__in=states.ACTIVE,
                                in_type=None)\
                        .exclude(target_issue=None)
            else:
                new_revisions = new_revisions.exclude(deleted=True)
            existing_reprints = to_issue_reprints
            old_revisions = \
                self.old_revisions_base()\
                    .filter(reprint_to_issue__in=existing_reprints,
                            next_revision=None)
            return new_revisions | old_revisions
        else:
            return to_issue_reprints

    @property
    def to_issue_reprints(self):
        return self.to_issue_reprints_oi(preview=True)

    @property
    def migration_status(self):
        if self.story is None or not hasattr(self.story, 'migration_status'):
            return MigrationStoryStatus.objects.none()
        return self.story.migration_status

    def has_reprint_revisions(self):
        if self.story is None:
            if self.target_reprint_revisions\
                   .filter(changeset__id=self.changeset_id).count():
                return True
            elif self.origin_reprint_revisions\
                     .filter(changeset__id=self.changeset_id).count():
                return True
            else:
                return False
        if self.story.target_reprint_revisions\
               .filter(changeset__id=self.changeset_id).count():
            return True
        if self.story.origin_reprint_revisions\
               .filter(changeset__id=self.changeset_id).count():
            return True
        # TODO: before there was the reserved=True here in the filter, why ?
        if self.story.to_reprints\
               .filter(revisions__changeset=self.changeset)\
               .count():
            return True
        if self.story.from_reprints\
               .filter(revisions__changeset=self.changeset)\
               .count():
            return True
        if self.story.to_issue_reprints\
               .filter(revisions__changeset=self.changeset)\
               .count():
            return True
        if self.story.from_issue_reprints\
               .filter(revisions__changeset=self.changeset)\
               .count():
            return True
        return False

    def has_credits(self):
        return (self.script or
                self.pencils or
                self.inks or
                self.colors or
                self.letters or
                self.editing or
                self.job_number)

    def has_content(self):
        return (self.genre or
                self.characters or
                self.synopsis or
                self.keywords or
                self.has_reprints())

    def has_reprints(self, notes=True):
        return ((notes and self.reprint_notes) or
                self.from_reprints.count() or
                self.to_reprints.count() or
                self.from_issue_reprints.count() or
                self.to_issue_reprints.count())

    @property
    def reprint_needs_inspection(self):
        if self.story:
            return self.story.reprint_needs_inspection
        else:
            return False

    @property
    def reprint_confirmed(self):
        if self.story:
            return self.story.reprint_confirmed
        else:
            return True

    def has_data(self):
        return self.has_credits() or self.has_content() or self.notes

    def get_absolute_url(self):
        if self.story is None:
            return "/issue/revision/%i/preview/#%i" % (
                self.my_issue_revision.id, self.id)
        return self.story.get_absolute_url()

    def __unicode__(self):
        """
        Re-implement locally instead of using self.story because it may change.
        """
        return u'%s (%s: %s)' % (self.feature, self.type, self.page_count)


class ReprintRevisionManager(RevisionManager):

    def clone_revision(self, reprint, changeset):
        """
        Given an existing Reprint instance, create a new revision based on it.

        This new revision will be where the edits are made.
        """
        return RevisionManager.clone_revision(self,
                                              instance=reprint,
                                              instance_class=type(reprint),
                                              changeset=changeset)

    def _do_create_revision(self, reprint, changeset):
        """
        Helper delegate to do the class-specific work of clone_revision.
        """
        if isinstance(reprint, Reprint):
            previous_revision = ReprintRevision.objects.get(
                reprint=reprint, next_revision=None,
                changeset__state=states.APPROVED)
            revision = ReprintRevision(
                # revision-specific fields:
                reprint=reprint,
                in_type=REPRINT_TYPES['story_to_story'],
                # copied fields:
                origin_story=reprint.origin,
                target_story=reprint.target,
            )
        if isinstance(reprint, ReprintFromIssue):
            previous_revision = ReprintRevision.objects.get(
                reprint_from_issue=reprint, next_revision=None,
                changeset__state=states.APPROVED)
            revision = ReprintRevision(
                # revision-specific fields:
                reprint_from_issue=reprint,
                in_type=REPRINT_TYPES['issue_to_story'],
                # copied fields:
                target_story=reprint.target,
                origin_issue=reprint.origin_issue,
            )
        if isinstance(reprint, ReprintToIssue):
            previous_revision = ReprintRevision.objects.get(
                reprint_to_issue=reprint, next_revision=None,
                changeset__state=states.APPROVED)
            revision = ReprintRevision(
                # revision-specific fields:
                reprint_to_issue=reprint,
                in_type=REPRINT_TYPES['story_to_issue'],
                # copied fields:
                origin_story=reprint.origin,
                target_issue=reprint.target_issue,
            )
        if isinstance(reprint, IssueReprint):
            previous_revision = ReprintRevision.objects.get(
                issue_reprint=reprint, next_revision=None,
                changeset__state=states.APPROVED)
            revision = ReprintRevision(
                # revision-specific fields:
                issue_reprint=reprint,
                in_type=REPRINT_TYPES['issue_to_issue'],
                # copied fields:
                origin_issue=reprint.origin_issue,
                target_issue=reprint.target_issue,
            )
        revision.previous_revision = previous_revision
        revision.changeset = changeset
        revision.notes = reprint.notes
        revision.save()
        return revision


def get_reprint_field_list():
    return ['notes']


class ReprintRevision(Revision):
    """
    One Revision Class for all four types of reprints.

    Otherwise we would have to generate reprint revisions while editing one
    link, e.g. changing an issue_to_story reprint to a story_to_story one, or
    changing reprint direction from issue_to_story to story_to_issue.
    """
    class Meta:
        db_table = 'oi_reprint_revision'
        ordering = ['-created', '-id']
        get_latest_by = "created"

    objects = ReprintRevisionManager()

    reprint = models.ForeignKey(Reprint, null=True,
                                related_name='revisions')
    reprint_from_issue = models.ForeignKey(ReprintFromIssue, null=True,
                                           related_name='revisions')
    reprint_to_issue = models.ForeignKey(ReprintToIssue, null=True,
                                         related_name='revisions')
    issue_reprint = models.ForeignKey(IssueReprint, null=True,
                                      related_name='revisions')

    origin_story = models.ForeignKey(Story, null=True,
                                     related_name='origin_reprint_revisions')
    origin_revision = models.ForeignKey(
        StoryRevision, null=True, related_name='origin_reprint_revisions')

    @property
    def origin(self):
        if self.origin_story:
            return self.origin_story
        elif self.origin_revision:
            return self.origin_revision
        else:
            raise AttributeError

    origin_issue = models.ForeignKey(
        Issue, null=True, related_name='origin_reprint_revisions')

    @property
    def origin_sort(self):
        if self.origin_issue:
            if self.origin_issue.key_date:
                sort = self.origin_issue.key_date
            else:
                sort = '9999-99-99'
            return "%s-%d-%d" % (sort, self.origin_issue.series.year_began,
                                 self.origin_issue.sort_code)
        else:
            if self.origin.issue.key_date:
                sort = self.origin.issue.key_date
            else:
                sort = '9999-99-99'
            return "%s-%d-%d" % (sort, self.origin.issue.series.year_began,
                                 self.origin.issue.sort_code)

    target_story = models.ForeignKey(Story, null=True,
                                     related_name='target_reprint_revisions')
    target_revision = models.ForeignKey(
        StoryRevision, null=True, related_name='target_reprint_revisions')

    @property
    def target(self):
        if self.target_story:
            return self.target_story
        elif self.target_revision:
            return self.target_revision
        else:
            raise AttributeError

    target_issue = models.ForeignKey(Issue, null=True,
                                     related_name='target_reprint_revisions')

    @property
    def target_sort(self):
        if self.target_issue:
            if self.target_issue.key_date:
                sort = self.target_issue.key_date
            else:
                sort = '9999-99-99'
            return "%s-%d-%d" % (sort, self.target_issue.series.year_began,
                                 self.target_issue.sort_code)
        else:
            if self.target.issue.key_date:
                sort = self.target.issue.key_date
            else:
                sort = '9999-99-99'
            return "%s-%d-%d" % (sort, self.target.issue.series.year_began,
                                 self.target.issue.sort_code)

    notes = models.TextField(max_length=255, default='')

    in_type = models.IntegerField(db_index=True, null=True)
    out_type = models.IntegerField(db_index=True, null=True)

    previous_revision = models.OneToOneField('self', null=True,
                                             related_name='next_revision')

    def previous(self):
        return self.previous_revision

    def _get_source(self):
        if self.deleted and self.changeset.state == states.APPROVED:
            return None
        if self.out_type is not None:
            reprint_type = self.out_type
        elif self.in_type is not None:
            reprint_type = self.in_type
        else:
            return None
        # reprint link objects can be deleted, so the source may be gone
        # could access source for change history, so catch it
        if reprint_type == REPRINT_TYPES['story_to_story'] and \
           self.reprint:
            return self.reprint
        if reprint_type == REPRINT_TYPES['issue_to_story'] and \
           self.reprint_from_issue:
            return self.reprint_from_issue
        if reprint_type == REPRINT_TYPES['story_to_issue'] and \
           self.reprint_to_issue:
            return self.reprint_to_issue
        if reprint_type == REPRINT_TYPES['issue_to_issue'] and \
           self.issue_reprint:
            return self.issue_reprint
        # TODO is None the right return ? Maybe placeholder object ?
        return None

    def _get_source_name(self):
        return 'reprint'

    def _field_list(self):
        return ['origin_story', 'origin_revision', 'origin_issue',
                'target_story', 'target_revision', 'target_issue',
                'notes']

    def _get_blank_values(self):
        return {
            'origin_story': None,
            'origin_revision': None,
            'origin_issue': None,
            'target_story': None,
            'target_revision': None,
            'target_issue': None,
            'notes': '',
        }

    def _start_imp_sum(self):
        self._seen_origin = False
        self._seen_target = False

    def _imps_for(self, field_name):
        """
        All current reprint fields are simple one point fields.
        Only one point for changing origin issue to origin story, etc.
        """
        if field_name in ('origin_story', 'origin_story_revision',
                          'origin_issue'):
            if not self._seen_origin:
                self._seen_origin = True
                return 1
        if field_name in ('target_story', 'target_story_revision',
                          'target_issue'):
            if not self._seen_target:
                self._seen_target = True
                return 1
        if field_name == 'notes':
            return 1
        return 0

    def commit_to_display(self):
        if self.deleted:
            deleted_link = self.source
            field_name = REPRINT_FIELD[self.in_type] + '_id'
            for revision in deleted_link.revisions.all():
                setattr(revision, field_name, None)
                revision.save()
            deleted_link.delete()
            return
        # first figure out which reprint out_type it is, it depends
        # on which fields are set
        if self.origin_story or self.origin_revision:
            if self.origin_revision:
                self.origin_story = self.origin_revision.story
                self.origin_revision = None
            origin = self.origin_story
            if self.target_story or self.target_revision:
                if self.target_revision:
                    self.target_story = self.target_revision.story
                    self.target_revision = None
                out_type = REPRINT_TYPES['story_to_story']
                target = self.target_story
            else:
                out_type = REPRINT_TYPES['story_to_issue']
                # TODO: The following line was present but flake8 notes
                #       that the local variable "target_issue" is unused.
                # target_issue = self.target_issue
        else:  # issue is source
            if self.target_story or self.target_revision:
                if self.target_revision:
                    self.target_story = self.target_revision.story
                    self.target_revision = None
                out_type = REPRINT_TYPES['issue_to_story']
                target = self.target_story
            else:
                out_type = REPRINT_TYPES['issue_to_issue']

        if self.in_type is not None and self.in_type != out_type:
            deleted_link = self.source
            field_name = REPRINT_FIELD[self.in_type] + '_id'
            for revision in deleted_link.revisions.all():
                setattr(revision, field_name, None)
                revision.save()
            setattr(self, field_name, None)
            deleted_link.delete()
        self.out_type = out_type

        # actual save of the data
        if out_type == REPRINT_TYPES['story_to_story']:
            if self.in_type != out_type:
                self.reprint = Reprint.objects.create(origin=origin,
                                                      target=target,
                                                      notes=self.notes)
            else:
                self.reprint.origin = origin
                self.reprint.target = target
                self.reprint.notes = self.notes
                self.reprint.save()
        elif out_type == REPRINT_TYPES['issue_to_story']:
            if self.in_type != out_type:
                self.reprint_from_issue = ReprintFromIssue.objects.create(
                    origin_issue=self.origin_issue,
                    target=target,
                    notes=self.notes)
            else:
                self.reprint_from_issue.origin_issue = self.origin_issue
                self.reprint_from_issue.target = target
                self.reprint_from_issue.notes = self.notes
                self.reprint_from_issue.save()
        elif out_type == REPRINT_TYPES['story_to_issue']:
            if self.in_type != out_type:
                self.reprint_to_issue = ReprintToIssue.objects.create(
                    origin=origin,
                    target_issue=self.target_issue,
                    notes=self.notes)
            else:
                self.reprint_to_issue.origin = origin
                self.reprint_to_issue.target_issue = self.target_issue
                self.reprint_to_issue.notes = self.notes
                self.reprint_to_issue.save()
        elif out_type == REPRINT_TYPES['issue_to_issue']:
            if self.in_type != out_type:
                self.issue_reprint = IssueReprint.objects.create(
                    origin_issue=self.origin_issue,
                    target_issue=self.target_issue,
                    notes=self.notes)
            else:
                self.issue_reprint.origin_issue = self.origin_issue
                self.issue_reprint.target_issue = self.target_issue
                self.issue_reprint.notes = self.notes
                self.issue_reprint.save()

        self.save()

    def get_compare_string(self, base_issue, do_compare=False):
        from apps.gcd.templatetags.credits import show_title
        moved = False
        if do_compare:
            self.compare_changes()
        if (self.origin_story and self.origin_story.issue == base_issue) \
                or (self.origin_revision and
                    self.origin_revision.issue == base_issue) \
                or self.origin_issue == base_issue:
            direction = 'in'
            if do_compare and self.previous_revision:
                if 'origin_issue' in self.changed and \
                        self.changed['origin_issue']:
                    if self.origin_issue and \
                            self.origin_issue == \
                            self.previous_revision.target_issue:
                        moved = False
                    else:
                        moved = True
                elif 'origin_story' in self.changed and \
                        self.changed['origin_story']:
                    if self.origin_story and \
                            self.origin_story == \
                            self.previous_revision.target_story:
                        moved = False
                    else:
                        moved = True
            if self.target_issue:
                story = None
                issue = self.target_issue
            else:
                if self.target_story:
                    story = self.target_story
                else:
                    story = self.target_revision
        else:
            direction = 'from'
            if do_compare and self.previous_revision:
                if 'target_issue' in self.changed and \
                        self.changed['target_issue']:
                    if self.target_issue and \
                            self.target_issue == \
                            self.previous_revision.origin_issue:
                        moved = False
                    else:
                        moved = True
                elif 'target_story' in self.changed and \
                        self.changed['target_story']:
                    if self.target_story and \
                            self.target_story == \
                            self.previous_revision.origin_story:
                        moved = False
                    else:
                        moved = True
            if self.origin_issue:
                story = None
                issue = self.origin_issue
            else:
                if self.origin_story:
                    story = self.origin_story
                else:
                    story = self.origin_revision
        if story:
            issue = story.issue
            reprint = u'%s %s <br><i>sequence</i> ' \
                      '<a target="_blank" href="%s#%d">%s %s</a>' % \
                      (direction, esc(issue.full_name()),
                       issue.get_absolute_url(), story.id, esc(story),
                       show_title(story))
        else:
            reprint = u'%s <a target="_blank" href="%s">%s</a>' % \
                      (direction, issue.get_absolute_url(),
                       esc(issue.full_name()))
        if self.notes:
            reprint = '%s [%s]' % (reprint, esc(self.notes))
        if moved:
            from apps.gcd.templatetags.display import show_story_short
            if self.previous_revision.target_issue == base_issue or \
               self.previous_revision.origin_issue == base_issue:
                reprint += '<br>reprint link was moved from issue'
            elif self.previous_revision.target_story and \
                    self.previous_revision.target_story.issue == base_issue:
                reprint += \
                    '<br>reprint link was moved from %s]' % \
                    show_story_short(self.previous_revision.target_story)
            else:
                reprint += \
                    '<br>reprint link was moved from %s]' % \
                    show_story_short(self.previous_revision.origin_story)
        return mark_safe(reprint)

    def __unicode__(self):
        from apps.gcd.templatetags.credits import show_title
        if self.origin_story or self.origin_revision:
            if self.origin_story:
                origin = self.origin_story
            else:
                origin = self.origin_revision
            reprint = u'%s %s of %s ' % (
                origin, show_title(origin), origin.issue)
        else:
            reprint = u'%s ' % (self.origin_issue)
        if self.target_story or self.target_revision:
            if self.target_story:
                target = self.target_story
            else:
                target = self.target_revision
            reprint += u'reprinted in %s %s of %s' % (
                target, show_title(target), target.issue)
        else:
            reprint += u'reprinted in %s' % (self.target_issue)
        if self.notes:
            reprint = '%s [%s]' % (reprint, esc(self.notes))
        if self.deleted:
            reprint += ' [DELETED]'
        return mark_safe(reprint)


class ImageRevisionManager(RevisionManager):

    def clone_revision(self, image, changeset):
        """
        Given an existing Image instance, create a new revision based on it.

        This new revision will be where the replacement is stored.
        """
        return RevisionManager.clone_revision(self,
                                              instance=image,
                                              instance_class=Image,
                                              changeset=changeset)

    def _do_create_revision(self, image, changeset, **ignore):
        """
        Helper delegate to do the class-specific work of clone_revision.
        """
        revision = ImageRevision(
            # revision-specific fields:
            image=image,
            changeset=changeset,

            # copied fields:
            content_type=image.content_type,
            object_id=image.object_id,
            type=image.type)

        revision.save()
        return revision


class ImageRevision(Revision):
    class Meta:
        db_table = 'oi_image_revision'
        ordering = ['created', '-id']

    objects = ImageRevisionManager()

    image = models.ForeignKey(Image, null=True, related_name='revisions')

    content_type = models.ForeignKey(ContentType, null=True)
    object_id = models.PositiveIntegerField(db_index=True, null=True)
    object = GenericForeignKey('content_type', 'object_id')

    type = models.ForeignKey(ImageType)

    image_file = models.ImageField(upload_to='%s/%%m_%%Y' %
                                             settings.NEW_GENERIC_IMAGE_DIR)
    scaled_image = ImageSpecField([ResizeToFit(width=400)],
                                  image_field='image_file',
                                  format='JPEG', options={'quality': 90})

    marked = models.BooleanField(default=False)
    is_replacement = models.BooleanField(default=False)

    def description(self):
        return u'%s for %s' % (self.type.description,
                               unicode(self.object.full_name()))

    def _get_source(self):
        return self.image

    def _get_source_name(self):
        return 'image'

    def _get_blank_values(self):
        """
        Images don't do field comparisons, so just return an empty
        dictionary so we don't throw an exception if code calls this.
        """
        return {}

    def calculate_imps(self, prev_rev=None):
        return IMP_IMAGE_VALUE

    def _imps_for(self, field_name):
        """
        Images are done purely on a flat point model and don't really have
        fields.  We shouldn't get here, but just in case, return 0 to be safe.
        """
        return 0

    def commit_to_display(self):
        image = self.image
        if self.is_replacement:
            prev_rev = self.previous()
            # copy replaced image back to revision
            prev_rev.image_file.save(str(prev_rev.id) + '.jpg',
                                     content=image.image_file)
            image.image_file.delete()
        elif self.deleted:
            image.delete()
            return
        elif image is None:
            if self.type.unique and not self.is_replacement:
                if Image.objects.filter(
                        content_type=ContentType.objects
                                                .get_for_model(self.object),
                        object_id=self.object.id,
                        type=self.type,
                        deleted=False).count():
                    raise ValueError(
                        '%s has an %s. Additional images cannot be uploaded, '
                        'only replacements are possible.' %
                        (self.object, self.type.description))

            # first generate instance
            image = Image(content_type=self.content_type,
                          object_id=self.object_id,
                          type=self.type,
                          marked=self.marked)
            image.save()

        # then add the uploaded file
        image.image_file.save(str(image.id) + '.jpg', content=self.image_file)
        self.image_file.delete()
        self.image = image
        self.save()

    def __unicode__(self):
        if self.source is None:
            return u'Image for %s' % unicode(self.object)
        return unicode(self.source)


class DataSourceRevisionManager(RevisionManager):
    def clone_revision(self, data_source, changeset, sourced_revision):
        """
        Given an existing DataSource instance, create a new revision
        based on it.

        This new revision will be where the replacement is stored.
        """
        return RevisionManager.clone_revision(self,
                                              instance=data_source,
                                              instance_class=DataSource,
                                              changeset=changeset,
                                              sourced_revision=sourced_revision)

    def _do_create_revision(self, data_source, changeset,
                            sourced_revision, **ignore):
        """
        Helper delegate to do the class-specific work of c  lone_revision.
        """
        revision = DataSourceRevision(
                # revision-specific fields:
                data_source=data_source,
                changeset=changeset,
                # copied fields:
                sourced_revision=sourced_revision,
                source_description=data_source.source_description,
                source_type=data_source.source_type,
                field=data_source.field
        )

        revision.save()
        return revision


class DataSourceRevision(Revision):
    """
    Indicates the various sources of data
    """

    class Meta:
        db_table = 'oi_data_source_revision'
        ordering = ['created', '-id']
        verbose_name_plural = 'Data Source Revisions'

    objects = DataSourceRevisionManager()
    content_type = models.ForeignKey(ContentType, null=True)
    revision_id = models.IntegerField(db_index=True, null=True)
    sourced_revision = GenericForeignKey('content_type', 'revision_id')

    data_source = models.ForeignKey('gcd.DataSource',
                                    related_name='revisions',
                                    null=True)
    source_type = models.ForeignKey('gcd.SourceType')
    source_description = models.TextField()
    field = models.CharField(max_length=256)

    def _get_blank_values(self):
        return {
            'data_source': None,
            'source_type': None,
            'source_description': '',
            'field': '',
        }

    def _get_source(self):
        return self.data_source

    def _field_list(self):
        field_list = ['source_description', 'source_type']
        return field_list

    def _imps_for(self, field_name):
        return 1

    def commit_to_display(self):
        # TODO add delete (and other stuff ?)
        data_source = self.data_source

        if data_source is None:
            data_source = DataSource(field=self.field)
        data_source.source_type = self.source_type
        data_source.source_description = self.source_description
        data_source.save()

        if self.data_source is None:
            source_object = self.sourced_revision.source
            source_object.data_source.add(data_source)
            self.data_source = data_source
            self.save()

    def __unicode__(self):
        return u'%s - %s' % (
            unicode(self.field), unicode(self.source_type.type))


def reserve_data_sources(data_sources, changeset, sourced_revision,
                         delete=False):
    for data_source in data_sources:
        data_source_lock = _get_revision_lock(data_source,
                                              changeset=changeset)
        if data_source_lock is None:
            raise IntegrityError("needed DataSource lock not possible")
        data_source = DataSourceRevision.objects.clone_revision(
          data_source, changeset=changeset, sourced_revision=sourced_revision)
        if delete:
            data_source.deleted = True
            data_source.save()


def _get_creator_sourced_fields():
    return {'birth_place': 'birth_city_uncertain',
            'death_place': 'death_city_uncertain',
            'bio': 'bio'}


def get_creator_field_list():
    return ['birth_date', 'birth_country', 'birth_country_uncertain',
            'birth_province', 'birth_province_uncertain',
            'birth_city', 'birth_city_uncertain',
            'death_date', 'death_country', 'death_country_uncertain',
            'death_province', 'death_province_uncertain',
            'death_city', 'death_city_uncertain',
            'whos_who', 'bio', 'notes'
            ]


class CreatorRevisionManager(RevisionManager):
    def _base_field_kwargs(self, instance):
        return {
            'gcd_official_name': instance.gcd_official_name,
            'whos_who': instance.whos_who,
            'birth_country': instance.birth_country,
            'birth_country_uncertain': instance.birth_country_uncertain,
            'birth_province': instance.birth_province,
            'birth_province_uncertain': instance.birth_province_uncertain,
            'birth_city': instance.birth_city,
            'birth_city_uncertain': instance.birth_city_uncertain,
            'death_country': instance.death_country,
            'death_country_uncertain': instance.death_country_uncertain,
            'death_province': instance.death_province,
            'death_province_uncertain': instance.death_province_uncertain,
            'death_city': instance.death_city,
            'death_city_uncertain': instance.death_city_uncertain,
            'bio': instance.bio,
            'notes': instance.notes,
        }

    def clone_revision(self, creator, changeset):
        """
        Given an existing Creator instance, create a new revision based on it.

        This new revision will be where the replacement is stored.
        """
        return RevisionManager.clone_revision(self,
                                              instance=creator,
                                              instance_class=Creator,
                                              changeset=changeset)

    def _do_create_revision(self, creator, changeset, **ignore):
        """
        Helper delegate to do the class-specific work of clone_revision.
        """
        kwargs = self._base_field_kwargs(creator)
        revision = CreatorRevision(
                # revision-specific fields:
                creator=creator,
                changeset=changeset,
                **kwargs)

        # clone date instances
        birth_date = creator.birth_date
        birth_date.pk = None
        birth_date.save()
        revision.birth_date = birth_date
        death_date = creator.death_date
        death_date.pk = None
        death_date.save()
        revision.death_date = death_date

        revision.save()
        return revision


class CreatorRevision(Revision):
    class Meta:
        db_table = 'oi_creator_revision'
        ordering = ['created', '-id']

    objects = CreatorRevisionManager()

    creator = models.ForeignKey('gcd.Creator',
                                null=True,
                                related_name='revisions')

    gcd_official_name = models.CharField(max_length=255, db_index=True)
    
    # TODO change from null=True
    birth_date = models.ForeignKey(Date, related_name='+', null=True, blank=True)
    death_date = models.ForeignKey(Date, related_name='+', null=True, blank=True)

    birth_country = models.ForeignKey('stddata.Country',
                                      related_name='cr_birth_country',
                                      null=True, blank=True)
    birth_country_uncertain = models.BooleanField(default=False)
    birth_province = models.CharField(max_length=50, blank=True)
    birth_province_uncertain = models.BooleanField(default=False)
    birth_city = models.CharField(max_length=200, blank=True)
    birth_city_uncertain = models.BooleanField(default=False)

    death_country = models.ForeignKey('stddata.Country',
                                      related_name='cr_death_country',
                                      null=True, blank=True)
    death_country_uncertain = models.BooleanField(default=False)
    death_province = models.CharField(max_length=50, blank=True)
    death_province_uncertain = models.BooleanField(default=False)
    death_city = models.CharField(max_length=200, blank=True)
    death_city_uncertain = models.BooleanField(default=False)

    whos_who = models.URLField(null=True, blank=True)
    bio = models.TextField(blank=True, null=True)

    data_source = models.ManyToManyField(DataSourceRevision,
                                         null=True,
                                         blank=True)
    notes = models.TextField(blank=True, null=True)

    def _field_list(self):
        return get_creator_field_list()

    def _get_blank_values(self):
        return {
            'gcd_official_name': '',
            'cr_creator_names': '',
            'birth_date': '',
            'death_date': '',
            'whos_who': '',
            'birth_country': None,
            'birth_country_uncertain': False,
            'birth_province': '',
            'birth_province_uncertain': False,
            'birth_city': '',
            'birth_city_uncertain': False,
            'death_country': None,
            'death_country_uncertain': False,
            'death_province': '',
            'death_province_uncertain': False,
            'death_city': '',
            'death_city_uncertain': False,
            'bio': '',
            'notes': '',
        }

    def active_names(self):
        return self.cr_creator_names.all()

    def display_birthday(self):
        return _display_day(self.birth_date)

    def display_birthplace(self):
        return _display_place(self, 'birth')

    def display_deathday(self):
        return _display_day(self.death_date)

    def display_deathplace(self):
        return _display_place(self, 'death')

    def has_death_info(self):
        if unicode(self.death_date) != '':
            return True
        else:
            return False

    def description(self):
        return '%s' % unicode(self.gcd_official_name)

    def _get_source(self):
        return self.creator

    def _get_source_name(self):
        return 'creator'

    def _start_imp_sum(self):
        self._seen_birth_country = False
        self._seen_birth_province = False
        self._seen_birth_city = False
        self._seen_death_country = False
        self._seen_death_province = False
        self._seen_death_city = False

    def _imps_for(self, field_name):
        if field_name in ('birth_country',
                          'birth_country_uncertain'):
            if not self._seen_birth_country:
                self._seen_birth_country = True
                return 1
        elif field_name in ('birth_province',
                            'birth_province_uncertain'):
            if not self._seen_birth_province:
                self._seen_birth_province = True
                return 1
        elif field_name in ('birth_city',
                            'birth_city_uncertain'):
            if not self._seen_birth_city:
                self._seen_birth_city = True
                return 1
        elif field_name in ('death_country',
                            'death_country_uncertain'):
            if not self._seen_death_country:
                self._seen_death_country = True
                return 1
        elif field_name in ('death_province',
                            'death_province_uncertain'):
            if not self._seen_death_province:
                self._seen_death_province = True
                return 1
        elif field_name in ('death_city',
                            'death_city_uncertain'):
            if not self._seen_death_city:
                self._seen_death_city = True
                return 1
        elif field_name in self._field_list():
            return 1
        return 0

    def _create_dependent_revisions(self, delete=False):
        name_details = self.creator.active_names()
        for name_detail in name_details:
            name_lock = _get_revision_lock(name_detail,
                                           changeset=self.changeset)
            if name_lock is None:
                raise IntegrityError("needed Name lock not possible")
            creator_name = CreatorNameDetailRevision.objects\
                           .clone_revision(name_detail, self.changeset, self)
            if delete:
                creator_name.deleted = True
                creator_name.save()

        # need a second loop, since otherwise all the needed
        # CreatorNameDetailRevision do not exist
        #for name_detail in name_details:
            #creator_relation_details = name_detail.to_name.all()
            #for creator_relation in creator_relation_details:
                #creator_relation_lock = _get_revision_lock(creator_relation,
                                     #changeset=self.changeset)
                #if creator_relation_lock is None:
                    #raise IntegrityError("needed CreatorRelation lock not possible")
                #creator_relation = CreatorRelationRevision.objects.clone_revision(
                                                     #creator_relation,
                                                     #changeset=self.changeset)
                #if delete:
                    #creator_relation.deleted = True
                    #creator_relation.save()

        data_sources = self.creator.data_source.all()
        reserve_data_sources(data_sources, self.changeset, self, delete)
            
        if delete:
            for creator_art_influence in self.creator.active_art_influences():
                influence_lock = _get_revision_lock(creator_art_influence,
                                                    changeset=self.changeset)
                if influence_lock is None:
                    raise IntegrityError("needed CreatorArtInfluence lock not"
                                         " possible")
                creator_art_influence_revison = \
                CreatorArtInfluenceRevision.objects.clone_revision(
                  creator_art_influence=creator_art_influence,
                  changeset=self.changeset)
                creator_art_influence_revison.deleted = True
                creator_art_influence_revison.save()

            for creator_award in self.creator.active_awards():
                award_lock = _get_revision_lock(creator_award,
                                                changeset=self.changeset)
                if award_lock is None:
                    raise IntegrityError("needed CreatorAward lock not possible")
                creator_award_revison = \
                CreatorAwardRevision.objects.clone_revision(
                    creator_award=creator_award, changeset=self.changeset)
                creator_award_revison.deleted = True
                creator_award_revison.save()

            for creator_degree in self.creator.active_degrees():
                school_lock = _get_revision_lock(creator_degree,
                                                 changeset=self.changeset)
                if degree_lock is None:
                    raise IntegrityError("needed CreatorDegree lock not possible")
                creator_degree_revison = \
                CreatorDegreeRevision.objects.clone_revision(
                    creator_degree=creator_degree, changeset=self.changeset)
                creator_degree_revison.deleted = True
                creator_degree_revison.save()

            for creator_membership in self.creator.active_memberships():
                membership_lock = _get_revision_lock(creator_membership,
                                                     changeset=self.changeset)
                if membership_lock is None:
                    raise IntegrityError("needed CreatorMembership lock not possible")
                creator_membership_revison = \
                CreatorMembershipRevision.objects.clone_revision(
                    creator_membership=creator_membership, changeset=self.changeset)
                creator_membership_revison.deleted = True
                creator_membership_revison.save()

            for creator_non_comic_work in self.creator.active_non_comic_works():
                noncomicwork_lock = _get_revision_lock(
                  creator_non_comic_work, changeset=self.changeset)
                if noncomicwork_lock is None:
                    raise IntegrityError("needed CreatorNonComicWork lock not"
                                         " possible")
                creator_non_comic_work_revison = \
                  CreatorNonComicWorkRevision.objects.clone_revision(
                    creator_non_comic_work=creator_non_comic_work,
                    changeset=self.changeset)
                creator_non_comic_work_revison.deleted = True
                creator_non_comic_work_revison.save()

            for creator_relation in self.creator.active_relations():
                relation_lock = _get_revision_lock(creator_relation,
                                                   changeset=self.changeset)
                if relation_lock is None:
                    raise IntegrityError("needed CreatorRelation lock not possible")
                creator_relation_revison = \
                CreatorRelationRevision.objects.clone_revision(
                    creator_relation=creator_relation, changeset=self.changeset)
                creator_relation_revison.deleted = True
                creator_relation_revison.save()

            for creator_school in self.creator.active_schools():
                school_lock = _get_revision_lock(creator_school,
                                                 changeset=self.changeset)
                if school_lock is None:
                    raise IntegrityError("needed CreatorSchool lock not possible")
                creator_school_revison = \
                CreatorSchoolRevision.objects.clone_revision(
                    creator_school=creator_school, changeset=self.changeset)
                creator_school_revison.deleted = True
                creator_school_revison.save()


        return True

    def commit_to_display(self, clear_reservation=True):

        ctr = self.creator
        if ctr is None:
            ctr = Creator()
        elif self.deleted:
            memberships = ctr.membership_set.exclude(deleted=True)
            for membership in memberships:
                membership.deleted = True
                membership.save()
            awards = ctr.award_set.exclude(deleted=True)
            for award in awards:
                award.deleted = True
                award.save()
            artinfluences = ctr.art_influence_set.exclude(deleted=True)
            for artinfluence in artinfluences:
                artinfluence.deleted = True
                artinfluence.save()
            noncomicworks = ctr.non_comic_work_set.exclude(deleted=True)
            for noncomicwork in noncomicworks:
                noncomicwork.deleted = True
                noncomicwork.save()

            ctr.reserved = False
            ctr.deleted = True
            ctr.save()
            return

        ctr.gcd_official_name = self.gcd_official_name
        ctr.whos_who = self.whos_who
        ctr.birth_country = self.birth_country
        ctr.birth_country_uncertain = self.birth_country_uncertain
        ctr.birth_province = self.birth_province
        ctr.birth_province_uncertain = self.birth_province_uncertain
        ctr.birth_city = self.birth_city
        ctr.birth_city_uncertain = self.birth_city_uncertain
        ctr.death_country = self.death_country
        ctr.death_country_uncertain = self.death_country_uncertain
        ctr.death_province = self.death_province
        ctr.death_province_uncertain = self.death_province_uncertain
        ctr.death_city = self.death_city
        ctr.death_city_uncertain = self.death_city_uncertain
        ctr.bio = self.bio
        ctr.notes = self.notes

        if clear_reservation:
            ctr.reserved = False
        ctr.save()

        if self.creator is None:
            self.creator = ctr
            # clone date instances
            birth_date = self.birth_date
            birth_date.pk = None
            birth_date.save()
            ctr.birth_date = birth_date
            death_date = self.death_date
            death_date.pk = None
            death_date.save()
            ctr.death_date = death_date
            ctr.save()
            self.save()
        else:
            ctr.birth_date.set(year=self.birth_date.year,
                               month=self.birth_date.month,
                               day=self.birth_date.day,
                               year_uncertain=self.birth_date.year_uncertain,
                               month_uncertain=self.birth_date.month_uncertain,
                               day_uncertain=self.birth_date.day_uncertain,
                               empty=True)
            ctr.birth_date.save()
            ctr.death_date.set(year=self.death_date.year,
                               month=self.death_date.month,
                               day=self.death_date.day,
                               year_uncertain=self.death_date.year_uncertain,
                               month_uncertain=self.death_date.month_uncertain,
                               day_uncertain=self.death_date.day_uncertain,
                               empty=True)
            ctr.death_date.save()

    def get_absolute_url(self):
        if self.creator is None:
            return "/creator/revision/%i/preview" % self.id
        return self.creator.get_absolute_url()

    def __unicode__(self):
        return u'%s' % unicode(self.gcd_official_name)


class CreatorRelationRevisionManager(RevisionManager):
    def clone_revision(self, creator_relation, changeset):
        """
        Given an existing CreatorRelation instance, create a new revision based
        on it.

        This new revision will be where the replacement is stored.
        """
        return RevisionManager.clone_revision(self,
                                              instance=creator_relation,
                                              instance_class=CreatorRelation,
                                              changeset=changeset,
                                              )

    def _do_create_revision(self, creator_relation, changeset, **ignore):
        """
        Helper delegate to do the class-specific work of clone_revision.
        """
        revision = CreatorRelationRevision(
            # revision-specific fields:
            creator_relation=creator_relation,
            changeset=changeset,
            # copied fields:
            to_creator=creator_relation.to_creator,
            from_creator=creator_relation.from_creator,
            relation_type=creator_relation.relation_type,
            notes=creator_relation.notes
        )
        revision.save()
        return revision


class CreatorRelationRevision(Revision):
    """
    Relations between creators to relate any GCD Official name to any other
    name.
    """

    class Meta:
        db_table = 'oi_creator_relation_revision'
        ordering = ('to_creator', 'relation_type', 'from_creator')
        verbose_name_plural = 'Creator Relation Revisions'

    objects = CreatorRelationRevisionManager()
    creator_relation = models.ForeignKey('gcd.CreatorRelation',
                                         null=True,
                                         related_name='revisions')

    to_creator = models.ForeignKey('gcd.Creator',
                                    related_name='to_creator_revisions')
    relation_type = models.ForeignKey('gcd.RelationType',
                                      related_name='revisions')
    from_creator = models.ForeignKey('gcd.Creator',
                                     related_name='from_creator_revisions')
    notes = models.TextField(blank=True)

    _base_field_list = ['from_creator', 'relation_type', 'to_creator', 'notes']
    
    def _field_list(self):
        field_list = self._base_field_list
        return field_list

    def _get_blank_values(self):
        return {
            'from_creator': None,
            'to_creator': None,
            'relation_type': None,
            'notes': ''
        }

    def _get_source(self):
        return self.creator_relation

    def _get_source_name(self):
        return 'creator_relation'

    def _imps_for(self, field_name):
        return 1

    def _create_dependent_revisions(self, delete=False):
        data_sources = self.creator_relation.data_source.all()
        reserve_data_sources(data_sources, self.changeset, self, delete)

    def commit_to_display(self):
        creator_relation = self.creator_relation

        if creator_relation is None:
            creator_relation = CreatorRelation()
        elif self.deleted:
            creator_relation.delete()
            return

        creator_relation.to_creator = self.to_creator
        creator_relation.from_creator = self.from_creator
        creator_relation.relation_type = self.relation_type
        creator_relation.notes = self.notes
        creator_relation.save()

        if self.creator_relation is None:
            self.creator_relation = creator_relation
            self.save()

    def __unicode__(self):
        return u'%s >%s< %s' % (unicode(self.from_creator),
                                unicode(self.relation_type),
                                unicode(self.to_creator)
                               )


class CreatorNameDetailRevisionManager(RevisionManager):
    def clone_revision(self, creator_name_detail, changeset, creator_revision):
        """
        Given an existing NameSource instance, create a new revision based on
        it.

        This new revision will be where the replacement is stored.
        """
        return RevisionManager.clone_revision(self,
                                              instance=creator_name_detail,
                                              instance_class=CreatorNameDetail,
                                              changeset=changeset,
                                              creator_revision=creator_revision)

    def _do_create_revision(self, creator_name_detail, changeset, 
                            creator_revision, **ignore):
        """
        Helper delegate to do the class-specific work of clone_revision.
        """
        #creator = creator_name_detail.creator.revisions.get(
                                                        #changeset=changeset)
        revision = CreatorNameDetailRevision(
                # revision-specific fields:
                creator_name_detail=creator_name_detail,
                changeset=changeset,
                creator=creator_revision,
                # copied fields:
                name=creator_name_detail.name,
                type=creator_name_detail.type,
        )
        revision.save()
        return revision


class CreatorNameDetailRevision(Revision):
    """
    record of the creator's name
    """

    class Meta:
        db_table = 'oi_creator_name_detail_revision'
        ordering = ['type__id', 'created', '-id']
        verbose_name_plural = 'Creator Name Detail Revisions'

    objects = CreatorNameDetailRevisionManager()
    creator_name_detail = models.ForeignKey('gcd.CreatorNameDetail',
                                            null=True,
                                            related_name='revisions')
    # TODO rename related_name
    creator = models.ForeignKey(CreatorRevision,
                                related_name='cr_creator_names')
    name = models.CharField(max_length=255, db_index=True)
    type = models.ForeignKey('gcd.NameType', related_name='cr_nametypes',
                             null=True, blank=True)

    def _field_list(self):
        field_list = ['name', 'type']
        return field_list

    def _get_blank_values(self):
        return {
            'name': '',
            'type': None,
        }

    #def active_relations(self):
        #return self.cr_to_name.exclude(deleted=True)

    def _get_source(self):
        return self.creator_name_detail

    def _get_source_name(self):
        return 'creator_name_detail'

    def _imps_for(self, field_name):
        if field_name in self._field_list():
            return 1
        return 0

    def commit_to_display(self):
        creator_name_detail = self.creator_name_detail
        if creator_name_detail is None:
            creator_name_detail = CreatorNameDetail()
        elif self.deleted:
            creator_name_detail.delete()
            return

        creator_name_detail.name = self.name
        creator_name_detail.type = self.type
        creator_name_detail.creator = self.creator.creator
        creator_name_detail.save()

        if self.creator_name_detail is None:
            self.creator_name_detail = creator_name_detail
            self.save()


    def __unicode__(self):
        return u'%s - %s (%s)' % (
            unicode(self.creator), unicode(self.name), unicode(self.type.type))


class CreatorSchoolRevisionManager(RevisionManager):
    def clone_revision(self, creator_school, changeset):
        """
        Given an existing CreatorSchool instance, create a new revision
        based on it.

        This new revision will be where the replacement is stored.
        """
        return RevisionManager.clone_revision(self,
                                              instance=creator_school,
                                              instance_class=CreatorSchool,
                                              changeset=changeset)

    def _do_create_revision(self, creator_school, changeset, **ignore):
        """
        Helper delegate to do the class-specific work of clone_revision.
        """
        revision = CreatorSchoolRevision(
                # revision-specific fields:
                creator_school=creator_school,
                changeset=changeset,
                # copied fields:
                creator=creator_school.creator,
                school=creator_school.school,
                school_year_began=creator_school.school_year_began,
                school_year_began_uncertain=
                                    creator_school.school_year_began_uncertain,
                school_year_ended=creator_school.school_year_ended,
                school_year_ended_uncertain=
                                    creator_school.school_year_ended_uncertain,
                notes=creator_school.notes
        )
        revision.save()

        #_create_data_source_revision(creator_school, changeset, revision)

        return revision


class CreatorSchoolRevision(Revision):
    """
    record the schools creators attended
    """

    class Meta:
        db_table = 'oi_creator_school_revision'
        ordering = ['created', '-id']
        verbose_name_plural = 'Creator School Revisions'

    objects = CreatorSchoolRevisionManager()
    creator_school = models.ForeignKey('gcd.CreatorSchool',
                                       null=True,
                                       related_name='revisions')
    creator = models.ForeignKey('gcd.Creator',
                                #related_name='membership_revisions')
    #creator = models.ForeignKey(CreatorRevision,
                                related_name='school_revisions')
    school = models.ForeignKey('gcd.School',
                               related_name='cr_schools')
    school_year_began = models.PositiveSmallIntegerField(null=True, blank=True)
    school_year_began_uncertain = models.BooleanField(default=False)
    school_year_ended = models.PositiveSmallIntegerField(null=True, blank=True)
    school_year_ended_uncertain = models.BooleanField(default=False)
    notes = models.TextField(blank=True)
    #school_source = models.ManyToManyField('gcd.SourceType',
                                           #related_name='cr_schoolsource',
                                           #null=True,
                                           #blank=True)
    def _do_complete_added_revision(self, creator):
        """
        Do the necessary processing to complete the fields of a new
        series revision for adding a record before it can be saved.
        """
        self.creator = creator

    _base_field_list = ['school',
                        'school_year_began', 'school_year_began_uncertain',
                        'school_year_ended', 'school_year_ended_uncertain',
                        'notes']

    def _field_list(self):
        return self._base_field_list

    def _get_blank_values(self):
        return {
            'school': None,
            'school_year_began': None,
            'school_year_began_uncertain': False,
            'school_year_ended': None,
            'school_year_ended_uncertain': False,
            'notes': ''
        }

    def _start_imp_sum(self):
        self._seen_year_began = False
        self._seen_year_ended = False

    def _imps_for(self, field_name):
        if field_name in ('school_year_began',
                          'school_year_began_uncertain'):
            if not self._seen_year_began:
                self._seen_year_began = True
                return 1
        elif field_name in ('school_year_ended',
                            'school_year_ended_uncertain'):
            if not self._seen_year_ended:
                self._seen_year_ended = True
                return 1
        elif field_name in self._base_field_list:
            return 1
        return 0

    def _get_source(self):
        return self.creator_school

    def _get_source_name(self):
        return 'creator_school'

    def _create_dependent_revisions(self, delete=False):
        data_sources = self.creator_school.data_source.all()
        reserve_data_sources(data_sources, self.changeset, self, delete)

    def commit_to_display(self):
        creator_school = self.creator_school
        if creator_school is None:
            creator_school = CreatorSchool()
        elif self.deleted:
            creator_school.delete()
            return

        creator_school.school = self.school
        creator_school.school_year_began = self.school_year_began
        creator_school.school_year_began_uncertain = \
                                            self.school_year_began_uncertain
        creator_school.school_year_ended = self.school_year_ended
        creator_school.school_year_ended_uncertain = \
                                            self.school_year_ended_uncertain
        creator_school.creator = self.creator
        creator_school.notes = self.notes

        creator_school.save()

        if self.creator_school is None:
            self.creator_school = creator_school
            self.save()

    def get_absolute_url(self):
        if self.creator_school is None:
            return "/creator_school/revision/%i/preview" % self.id
        return self.creator_school.get_absolute_url()

    def __unicode__(self):
        return u'%s - %s' % (
            unicode(self.creator), unicode(self.school.school_name))


class CreatorDegreeRevisionManager(RevisionManager):
    def clone_revision(self, creator_degree, changeset):
        """
        Given an existing CreatorDegree instance, create a new revision
        based on it.

        This new revision will be where the replacement is stored.
        """
        return RevisionManager.clone_revision(self,
                                              instance=creator_degree,
                                              instance_class=CreatorDegree,
                                              changeset=changeset)

    def _do_create_revision(self, creator_degree, changeset, **ignore):
        """
        Helper delegate to do the class-specific work of clone_revision.
        """
        #creator = creator_degree.creator.revisions.get(changeset=changeset)

        revision = CreatorDegreeRevision(
                # revision-specific fields:
                creator_degree=creator_degree,
                changeset=changeset,
                # copied fields:
                creator=creator_degree.creator,
                degree=creator_degree.degree,
                school=creator_degree.school,
                degree_year=creator_degree.degree_year,
                degree_year_uncertain=creator_degree.degree_year_uncertain,
                notes=creator_degree.notes
        )

        revision.save()
        
        #_create_data_source_revision(creator_degree, changeset, revision)

        return revision


class CreatorDegreeRevision(Revision):
    """
    record the degrees creators received
    """

    class Meta:
        db_table = 'oi_creator_degree_revision'
        ordering = ['created', '-id']
        verbose_name_plural = 'Creator Degree Revisions'

    objects = CreatorDegreeRevisionManager()
    creator_degree = models.ForeignKey('gcd.CreatorDegree',
                                       null=True,
                                       related_name='revisions')
    creator = models.ForeignKey('gcd.Creator',
                                related_name='degree_revisions')
    school = models.ForeignKey('gcd.School',
                               related_name='creator_degrees',
                               null=True)
    degree = models.ForeignKey('gcd.Degree',
                               related_name='creator_degrees')
    degree_year = models.PositiveSmallIntegerField(null=True, blank=True)
    degree_year_uncertain = models.BooleanField(default=False)
    notes = models.TextField(blank=True)

    _base_field_list = ['school', 'degree',
                        'degree_year', 'degree_year_uncertain', 'notes']

    def _do_complete_added_revision(self, creator):
        """
        Do the necessary processing to complete the fields of a new
        series revision for adding a record before it can be saved.
        """
        self.creator = creator

    def _field_list(self):
        return self._base_field_list

    def _get_blank_values(self):
        return {
            'school': None,
            'degree': None,
            'degree_year': None,
            'degree_year_uncertain': False,
            'notes': ''
        }

    def _start_imp_sum(self):
        self._seen_year = False

    def _imps_for(self, field_name):
        if field_name in ('degree_year',
                          'degree_year_uncertain'):
            if not self._seen_year:
                self._seen_year = True
                return 1
        elif field_name in self._base_field_list:
            return 1
        return 0

    def _get_source(self):
        return self.creator_degree

    def _get_source_name(self):
        return 'creator_degree'

    def _create_dependent_revisions(self, delete=False):
        data_sources = self.creator_degree.data_source.all()
        reserve_data_sources(data_sources, self.changeset, self, delete)

    def commit_to_display(self):
        creator_degree = self.creator_degree
        if creator_degree is None:
            creator_degree = CreatorDegree()
        elif self.deleted:
            creator_degree.delete()
            return

        creator_degree.school = self.school
        creator_degree.degree = self.degree
        creator_degree.degree_year = self.degree_year
        creator_degree.degree_year_uncertain = \
                                                    self.degree_year_uncertain
        creator_degree.creator = self.creator
        creator_degree.notes = self.notes
        creator_degree.save()

        if self.creator_degree is None:
            self.creator_degree = creator_degree
            self.save()

    def get_absolute_url(self):
        if self.creator_degree is None:
            return "/creator_degree/revision/%i/preview" % self.id
        return self.creator_degree.get_absolute_url()

    def __unicode__(self):
        return u'%s - %s' % (
            unicode(self.creator), unicode(self.degree.degree_name))


def _create_data_source_revision(instance, changeset, revision):
    data_sources = instance.data_source.all()
    for data_source in data_sources:
        DataSourceRevision.objects.clone_revision(
                                            data_source,
                                            changeset=changeset,
                                            sourced_revision=revision)


class CreatorMembershipRevisionManager(RevisionManager):
    def _base_field_kwargs(self, instance):
        return {
            'organization_name': instance.organization_name,
            'membership_type': instance.membership_type,
            'membership_year_began': instance.membership_year_began,
            'membership_year_began_uncertain':
                instance.membership_year_began_uncertain,
            'membership_year_ended': instance.membership_year_ended,
            'membership_year_ended_uncertain':
                instance.membership_year_ended_uncertain,
            'notes': instance.notes,                
        }

    def clone_revision(self, creator_membership, changeset):
        """
        Given an existing CreatorMembership instance, create a new revision
        based on it.

        This new revision will be where the replacement is stored.
        """
        return RevisionManager.clone_revision(self,
                                              instance=creator_membership,
                                              instance_class=CreatorMembership,
                                              changeset=changeset)

    def _do_create_revision(self, creator_membership, changeset, **ignore):
        """
        Helper delegate to do the class-specific work of clone_revision.
        """
        kwargs = self._base_field_kwargs(creator_membership)
        revision = CreatorMembershipRevision(
                # revision-specific fields:
                changeset=changeset,
                creator_membership=creator_membership,
                # copied fields:
                creator=creator_membership.creator,
                **kwargs
                )

        revision.save()

        #_create_data_source_revision(creator_membership, changeset, revision)

        return revision


class CreatorMembershipRevision(Revision):
    """
    record the membership of creator
    """

    class Meta:
        db_table = 'oi_creator_membership_revision'
        ordering = ['created', '-id']
        verbose_name_plural = 'Creator Membership Revisions'

    objects = CreatorMembershipRevisionManager()
    creator_membership = models.ForeignKey('gcd.CreatorMembership',
                                           null=True,
                                           related_name='revisions')
    creator = models.ForeignKey('gcd.Creator',
                                related_name='membership_revisions')
    organization_name = models.CharField(max_length=200)
    membership_type = models.ForeignKey('gcd.MembershipType',
                                        related_name='cr_membershiptype',
                                        null=True,
                                        blank=True)
    membership_year_began = models.PositiveSmallIntegerField(null=True,
                                                             blank=True)
    membership_year_began_uncertain = models.BooleanField(default=False)
    membership_year_ended = models.PositiveSmallIntegerField(null=True,
                                                             blank=True)
    membership_year_ended_uncertain = models.BooleanField(default=False)
    notes = models.TextField(blank=True)

    _base_field_list = ['organization_name',
                        'membership_type',
                        'membership_year_began',
                        'membership_year_began_uncertain',
                        'membership_year_ended',
                        'membership_year_ended_uncertain',
                        'notes',
                        ]

    def _field_list(self):
        return self._base_field_list

    def _do_complete_added_revision(self, creator):
        """
        Do the necessary processing to complete the fields of a new
        series revision for adding a record before it can be saved.
        """
        self.creator = creator

    def _get_blank_values(self):
        return {
            'organization_name': '',
            'membership_type': None,
            'membership_year_began': None,
            'membership_year_began_uncertain': False,
            'membership_year_ended': None,
            'membership_year_ended_uncertain': False,
            'notes': '',
        }

    def _get_source(self):
        return self.creator_membership

    def _get_source_name(self):
        return 'creator_membership'

    def _start_imp_sum(self):
        self._seen_year_began = False
        self._seen_year_ended = False

    def _imps_for(self, field_name):
        if field_name in ('membership_year_began',
                          'membership_year_began_uncertain'):
            if not self._seen_year_began:
                self._seen_year_began = True
                return 1
        elif field_name in ('membership_year_ended',
                            'membership_year_ended_uncertain'):
            if not self._seen_year_ended:
                self._seen_year_ended = True
                return 1
        elif field_name in self._base_field_list:
            return 1
        return 0

    def _create_dependent_revisions(self, delete=False):
        data_sources = self.creator_membership.data_source.all()
        reserve_data_sources(data_sources, self.changeset, self, delete)

    def commit_to_display(self, clear_reservation=True):
        ctm = self.creator_membership
        if ctm is None:
            ctm = CreatorMembership()

        elif self.deleted:
            ctm.reserved = False
            ctm.deleted = self.deleted
            ctm.save()
            return
        ctm.creator = self.creator
        ctm.organization_name = self.organization_name
        ctm.membership_type = self.membership_type
        ctm.membership_year_began = self.membership_year_began
        ctm.membership_year_began_uncertain = \
            self.membership_year_began_uncertain
        ctm.membership_year_ended = self.membership_year_ended
        ctm.membership_year_ended_uncertain = self.membership_year_ended_uncertain
        ctm.notes = self.notes

        if clear_reservation:
            ctm.reserved = False
        ctm.save()

        if self.creator_membership is None:
            self.creator_membership = ctm
            self.save()

    def get_absolute_url(self):
        if self.creator_membership is None:
            return "/creator_membership/revision/%i/preview" % self.id
        return self.creator_membership.get_absolute_url()

    def __unicode__(self):
        return u'%s: %s' % (self.creator, unicode(self.organization_name))


class CreatorAwardRevisionManager(RevisionManager):
    def _base_field_kwargs(self, instance):
        return {
            'award': instance.award,
            'award_name': instance.award_name,
            'no_award_name': instance.no_award_name,
            'award_year': instance.award_year,
            'award_year_uncertain': instance.award_year_uncertain,
            'notes': instance.notes,            
        }

    def clone_revision(self, creator_award, changeset):
        """
        Given an existing CreatorAward instance, create a new revision
        based on it.

        This new revision will be where the replacement is stored.
        """
        return RevisionManager.clone_revision(self,
                                              instance=creator_award,
                                              instance_class=CreatorAward,
                                              changeset=changeset)

    def _do_create_revision(self, creator_award, changeset, **ignore):
        """
        Helper delegate to do the class-specific work of clone_revision.
        """
        kwargs = self._base_field_kwargs(creator_award)
        revision = CreatorAwardRevision(
                # revision-specific fields:
                creator_award=creator_award,
                changeset=changeset,
                # copied fields:
                creator=creator_award.creator,
                **kwargs
        )

        revision.save()

        #_create_data_source_revision(creator_award, changeset, revision)

        return revision


class CreatorAwardRevision(Revision):
    """
    record the awards of creator
    """

    class Meta:
        db_table = 'oi_creator_award_revision'
        ordering = ['created', '-id']
        verbose_name_plural = 'Creator Award Revisions'

    objects = CreatorAwardRevisionManager()
    creator_award = models.ForeignKey('gcd.CreatorAward',
                                      null=True,
                                      related_name='revisions')
    creator = models.ForeignKey('gcd.Creator',
                                related_name='award_revisions')
    award = models.ForeignKey(Award, null=True, blank=True)
    award_name = models.CharField(max_length=255, blank=True)
    no_award_name = models.BooleanField(default=False)
    award_year = models.PositiveSmallIntegerField(null=True, blank=True)
    award_year_uncertain = models.BooleanField(default=False)
    notes = models.TextField(blank=True)

    def __unicode__(self):
        if self.award:
            name = u'%s - %s' % (self.award.name, self.award_name)
        else:
            name = u'%s' % (self.award_name)
        if self.award_year:
            return u'%s: %s (%d)' % (self.creator, name, self.award_year)
        else:
            return u'%s: %s' % (self.creator, name)

    _base_field_list = ['award',
                        'award_name',
                        'no_award_name',
                        'award_year',
                        'award_year_uncertain',
                        'notes',
                        ]

    def _field_list(self):
        return self._base_field_list

    def _do_complete_added_revision(self, creator):
        """
        Do the necessary processing to complete the fields of a new
        series revision for adding a record before it can be saved.
        """
        self.creator = creator

    def _get_blank_values(self):
        return {
            'award': '',
            'award_name': '',
            'no_award_name': False,
            'award_year': None,
            'award_year_uncertain': False,
            'notes': '',
        }

    def _get_source(self):
        return self.creator_award

    def _get_source_name(self):
        return 'creator_award'

    def _start_imp_sum(self):
        self._seen_year = False
        self._seen_award_name = False

    def _imps_for(self, field_name):
        if field_name in ('award_year',
                          'award_year_uncertain'):
            if not self._seen_year:
                self._seen_year = True
                return 1
        elif field_name in ('award_name',
                            'no_award_name'):
            if not self._seen_award_name:
                self._seen_award_name = True
                return 1
        elif field_name in self._base_field_list:
            return 1
        return 0

    def _create_dependent_revisions(self, delete=False):
        data_sources = self.creator_award.data_source.all()
        reserve_data_sources(data_sources, self.changeset, self, delete)

    def commit_to_display(self, clear_reservation=True):
        awd = self.creator_award
        if awd is None:
            awd = CreatorAward()

        elif self.deleted:
            awd.reserved = False
            awd.deleted = self.deleted
            awd.save()
            return
        awd.creator = self.creator
        awd.award = self.award
        awd.award_name = self.award_name
        awd.award_year = self.award_year
        awd.award_year_uncertain = self.award_year_uncertain
        awd.notes = self.notes

        if clear_reservation:
            awd.reserved = False
        awd.save()

        if self.creator_award is None:
            self.creator_award = awd
            self.save()

    def get_absolute_url(self):
        if self.creator_award is None:
            return "/creator_award/revision/%i/preview" % self.id
        return self.creator_award.get_absolute_url()


class CreatorArtInfluenceRevisionManager(RevisionManager):
    def _base_field_kwargs(self, instance):
        return {
            'influence_name': instance.influence_name,
            'influence_link': instance.influence_link,
            #'is_self_identify': instance.is_self_identify,
            'notes': instance.notes,
        }

    def clone_revision(self, creator_art_influence, changeset):
        """
        Given an existing CreatorArtInfluence instance, create a new revision
        based on it.

        This new revision will be where the replacement is stored.
        """
        return RevisionManager.clone_revision(self,
                                              instance=creator_art_influence,
                                              instance_class=CreatorArtInfluence,
                                              changeset=changeset)

    def _do_create_revision(self, creator_art_influence, changeset, **ignore):
        """
        Helper delegate to do the class-specific work of clone_revision.
        """
        kwargs = self._base_field_kwargs(creator_art_influence)
        revision = CreatorArtInfluenceRevision(
                # revision-specific fields:
                creator_art_influence=creator_art_influence,
                changeset=changeset,
                # copied fields:
                creator=creator_art_influence.creator,
                **kwargs
        )

        revision.save()

        return revision


class CreatorArtInfluenceRevision(Revision):
    """
    record the art influences of creator
    """

    class Meta:
        db_table = 'oi_creator_art_influence_revision'
        ordering = ['created', '-id']
        verbose_name_plural = 'Creator Art Influence Revisions'

    objects = CreatorArtInfluenceRevisionManager()
    creator_art_influence = models.ForeignKey('gcd.CreatorArtInfluence',
                                              null=True,
                                              related_name='revisions')
    creator = models.ForeignKey('gcd.Creator',
                                related_name='art_influence_revisions')
    influence_name = models.CharField(max_length=200, blank=True)
    influence_link = models.ForeignKey('gcd.Creator',
                                       null=True,
                                       blank=True,
                                       related_name='influenced_revisions')
    #is_self_identify = models.BooleanField(default=False)
    notes = models.TextField(blank=True)

    def __unicode__(self):
        if self.influence_name:
             influence = self.influence_name
        else:
             influence = self.influence_link

        return u'%s: %s' % (self.creator, influence)

    _base_field_list = ['influence_name',
                        'influence_link',
                        'notes',
                        ]

    def _field_list(self):
        return self._base_field_list

    def _do_complete_added_revision(self, creator):
        """
        Do the necessary processing to complete the fields of a new
        series revision for adding a record before it can be saved.
        """
        self.creator = creator

    def _get_blank_values(self):
        return {
            'influence_name': '',
            'influence_link': None,
            'notes': '',
        }

    def _get_source(self):
        return self.creator_art_influence

    def _get_source_name(self):
        return 'creator_art_influence'

    def _imps_for(self, field_name):
        if field_name in self._base_field_list:
            return 1
        return 0

    def _create_dependent_revisions(self, delete=False):
        data_sources = self.creator_art_influence.data_source.all()
        reserve_data_sources(data_sources, self.changeset, self, delete)

    def commit_to_display(self, clear_reservation=True):
        art = self.creator_art_influence
        if art is None:
            art = CreatorArtInfluence()

        elif self.deleted:
            art.reserved = Falsef
            art.deleted = self.deleted
            art.save()
            return

        art.creator = self.creator
        art.influence_name = self.influence_name
        art.influence_link = self.influence_link
        #art.is_self_identify = self.is_self_identify
        art.notes = self.notes

        if clear_reservation:
            art.reserved = False
        art.save()

        if self.creator_art_influence is None:
            self.creator_art_influence = art
            self.save()

    def get_absolute_url(self):
        if self.creator_art_influence is None:
            return "/creator_art_influence/revision/%i/preview" % self.id
        return self.creator_art_influence.get_absolute_url()


class MultiURLValidator(URLValidator):
    def __call__(self, value):
        for url in value.split('\n'):
            try:
                super(URLValidator, self).__call__(url.strip())
            except ValidationError as e:
                if e.message != 'Enter a valid URL.':
                    raise
                else:
                    raise ValidationError('Enter one or more valid URLs, one per line.')


class CreatorNonComicWorkRevisionManager(RevisionManager):
    def _base_field_kwargs(self, instance):
        return {
            'work_type': instance.work_type,
            'publication_title': instance.publication_title,
            'employer_name': instance.employer_name,
            'work_title': instance.work_title,
            'work_role': instance.work_role,
            'work_urls': instance.work_urls,
            'notes': instance.notes,
        }

    def clone_revision(self, creator_non_comic_work, changeset):
        """
        Given an existing CreatorNonComicWork instance, create a new revision
        based on it.

        This new revision will be where the replacement is stored.
        """
        return RevisionManager.clone_revision(self,
                                              instance=creator_non_comic_work,
                                              instance_class=CreatorNonComicWork,
                                              changeset=changeset)

    def _do_create_revision(self, creator_non_comic_work, changeset, **ignore):
        """
        Helper delegate to do the class-specific work of clone_revision.
        """
        kwargs = self._base_field_kwargs(creator_non_comic_work)
        revision = CreatorNonComicWorkRevision(
                # revision-specific fields:
                creator_non_comic_work=creator_non_comic_work,
                changeset=changeset,
                # copied fields:
                creator=creator_non_comic_work.creator,
                **kwargs
        )

        revision.work_years = creator_non_comic_work.display_years()
        revision.save()
        return revision


class CreatorNonComicWorkRevision(Revision):
    """
    record the non comic work of creator
    """

    class Meta:
        db_table = 'oi_creator_non_comic_work_revision'
        ordering = ['created', '-id']
        verbose_name_plural = 'Creator NonComicWork Revisions'

    objects = CreatorNonComicWorkRevisionManager()
    creator_non_comic_work = models.ForeignKey('gcd.CreatorNonComicWork',
                                             null=True,
                                             related_name='revisions')
    creator = models.ForeignKey('gcd.Creator',
                                related_name='non_comic_work_revisions')
    work_type = models.ForeignKey('gcd.NonComicWorkType',
                                  null=True,
                                  blank=True,
                                  related_name='cr_worktype')
    publication_title = models.CharField(max_length=200)
    employer_name = models.CharField(max_length=200, blank=True)
    work_title = models.CharField(max_length=255, blank=True)
    work_role = models.ForeignKey('gcd.NonComicWorkRole',
                                  null=True,
                                  blank=True,
                                  related_name='cr_workrole')
    work_years = models.TextField(blank=True)
    work_urls = models.TextField(blank=True, validators=[MultiURLValidator()])
    notes = models.TextField(blank=True)

    _base_field_list = ['work_type',
                        'publication_title',
                        'employer_name',
                        'work_title',
                        'work_role',
                        'work_years',
                        'work_urls',
                        'notes',
                        ]

    def _field_list(self):
        return self._base_field_list

    def _do_complete_added_revision(self, creator):
        """
        Do the necessary processing to complete the fields of a new
        series revision for adding a record before it can be saved.
        """
        self.creator = creator

    def _get_blank_values(self):
        return {
            'work_type': '',
            'publication_title': '',
            'employer_name': '',
            'work_title': '',
            'work_role': '',
            'work_years': '',
            'work_urls': '',
            'notes': '',
        }

    def _get_source(self):
        return self.creator_non_comic_work

    def _get_source_name(self):
        return 'creator_non_comic_work'

    def _imps_for(self, field_name):
        if field_name in self._base_field_list:
            return 1
        return 0

    def _create_dependent_revisions(self, delete=False):
        data_sources = self.creator_non_comic_work.data_source.all()
        reserve_data_sources(data_sources, self.changeset, self, delete)

    def commit_to_display(self, clear_reservation=True):
        ncw = self.creator_non_comic_work
        if ncw is None:
            ncw = CreatorNonComicWork()

        elif self.deleted:
            ncw.reserved = False
            ncw.deleted = self.deleted
            ncw.save()
            return

        ncw.creator = self.creator
        ncw.work_type = self.work_type
        ncw.publication_title = self.publication_title
        ncw.employer_name = self.employer_name
        ncw.work_title = self.work_title
        ncw.work_role = self.work_role
        ncw.work_urls = self.work_urls
        ncw.notes = self.notes

        if clear_reservation:
            ncw.reserved = False
        ncw.save()

        if self.creator_non_comic_work is None:
            self.creator_non_comic_work = ncw
            self.save()

        if self.work_years:
            existing_years = list(NonComicWorkYear.objects\
                .filter(non_comic_work=ncw).values_list('id', flat=True))
            for year in self.work_years.split(';'):
                range_split = year.split('-')
                if len(range_split) == 2:
                    year_began = _check_year(range_split[0])
                    year_end = _check_year(range_split[1])
                    if year_began > year_end:
                        raise ValueError
                    years_uncertain = False

                    ncw_year, created = NonComicWorkYear.objects\
                      .get_or_create(non_comic_work=ncw, work_year=year_began)
                    if '?' in range_split[0]:
                        ncw_year.work_year_uncertain = True
                    else:
                        ncw_year.work_year_uncertain = False
                    ncw_year.save()
                    if not created:
                        existing_years.remove(ncw_year.id)

                    ncw_year, created = NonComicWorkYear.objects\
                      .get_or_create(non_comic_work=ncw, work_year=year_end)
                    if '?' in range_split[1]:
                        ncw_year.work_year_uncertain = True
                        if '?' in range_split[0]:
                            years_uncertain = True
                    else:
                        ncw_year.work_year_uncertain = False
                    ncw_year.save()
                    if not created:
                        existing_years.remove(ncw_year.id)

                    for i in range(year_began+1, year_end):
                        ncw_year, created = NonComicWorkYear.objects\
                          .get_or_create(non_comic_work=ncw, work_year=i)
                        ncw_year.work_year_uncertain = years_uncertain
                        ncw_year.save()
                        if not created:
                            existing_years.remove(ncw_year.id)
                else:
                    year_number = _check_year(year)
                    ncw_year, created = NonComicWorkYear.objects\
                          .get_or_create(non_comic_work=ncw,
                                         work_year=year_number)
                    if '?' in year:
                        ncw_year.work_year_uncertain = True
                    else:
                        ncw_year.work_year_uncertain = False
                    ncw_year.save()
                    if not created:
                        existing_years.remove(ncw_year.id)
            # remove years which are not present in value anymore
            for i in existing_years:
                ncw_year = NonComicWorkYear.objects.get(id=i)
                ncw_year.delete()


    def get_absolute_url(self):
        if self.creator_non_comic_work is None:
            return "/creator_non_comic_work/revision/%i/preview" % self.id
        return self.creator_non_comic_work.get_absolute_url()

    def __unicode__(self):
        return u'%s: %s' % (unicode(self.creator),
                            unicode(self.publication_title))

