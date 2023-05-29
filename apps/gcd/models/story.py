from django.contrib.contenttypes.fields import GenericRelation
from django.db import models
import django.urls as urlresolvers
from django.utils.safestring import mark_safe
from django.utils.html import conditional_escape as esc
from django.utils.translation import ungettext

from taggit.managers import TaggableManager

import django_tables2 as tables

from .gcddata import GcdData
from .award import ReceivedAward
from .character import CharacterNameDetail, Group
from .creator import CreatorNameDetail, CreatorSignature
from .feature import Feature, FeatureLogo

STORY_TYPES = {
    'ad': 2,
    'cover': 6,
    'insert': 11,
    'letters_page': 12,
    'soo': 22,
    'blank': 24,
    'preview': 26,
    'about comics': 27,
    'comics-form ad': 28,
    'in-house column': 29
}

CREDIT_TYPES = {
    'script': 1,
    'pencils': 2,
    'inks': 3,
    'colors': 4,
    'letters': 5,
    'editing': 6,
}

OLD_TYPES = {
    '(unknown)',
    '(backcovers) *do not use* / *please fix*',
    'biography (nonfictional)'
}

# core sequence types: cartoon, (photo, text) story, cover (incl. reprint)
CORE_TYPES = [5, 6, 7, 13, 19, 21]
# ad sequence types: ad, promo, in-house column
AD_TYPES = [2, 16, 26, 28, 29]
# non-optional sequences: story, cover (incl. reprint)
NON_OPTIONAL_TYPES = [6, 7, 19]
# sequences types that cannot have a feature or genre
NO_FEATURE_TYPES = [8, 22, 24, 25]
NO_GENRE_TYPES = [8, 22, 24, 25]
DEPRECATED_TYPES = [3, 4, 23]


def show_feature(story, url=True):
    first = True
    features = ''
    for feature in story.feature_object.all():
        if first:
            first = False
        else:
            features += '; '
        if url:
            features += '<a href="%s">%s</a>' % (feature.get_absolute_url(),
                                                 esc(feature.name))
        else:
            features += '%s' % feature.name
    if story.feature:
        if url:
            text_feature = esc(story.feature)
        else:
            text_feature = story.feature
        if features:
            features += '; %s' % text_feature
        else:
            features = text_feature
    if url:
        return mark_safe(features)
    else:
        return features


def show_feature_as_text(story):
    return show_feature(story, url=False)


def character_notes(character):
    notes = []
    if character.is_flashback:
        notes.append('flashback')
    if character.is_death:
        notes.append('death')
    if character.is_origin:
        notes.append('origin')
    note = ", ".join(notes)
    if note:
        note = ' (%s)' % note

    if character.role:
        note += ' (%s)' % character.role

    if character.notes:
        note += ' (%s)' % character.notes

    return note


def get_civilian_identity(character, appearing_characters, url=True,
                          compare=False):
    civilian_identity = set(
        character.character.character.to_related_character
                 .filter(relation_type__id=2).values_list('to_character',
                                                          flat=True))\
                 .intersection(appearing_characters.values_list(
                               'character__character', flat=True))
    if civilian_identity:
        civilian_identity = appearing_characters.filter(
              character__character__id=civilian_identity.pop())
        characters = ' ['
        several = False
        for identity in civilian_identity:
            if several:
                characters += '; '
            if url:
                characters += '<a href="%s">%s</a>' % (
                    identity.character.get_absolute_url(),
                    esc(identity.character.name))
            else:
                characters += '%s' % identity.character.name
            if compare:
                return ' [%s]' % identity.character.character.disambiguated
            several = True
        characters += ']'
        return characters
    else:
        return ''


def show_characters(story, url=True, css_style=True, compare=False):
    first = True
    characters = ''
    disambiguation = ''

    all_appearing_characters = story.active_characters
    in_group = all_appearing_characters.exclude(group=None)
    groups = Group.objects.filter(id__in=in_group.values_list('group'))
    for group in groups:
        first = False
        first_member = True
        for member in in_group.filter(group=group):
            if first_member:
                first_member = False
                if url:
                    characters += '<a href="%s">%s</a> [<a href="%s">%s</a>' \
                                  % (group.get_absolute_url(), esc(group.name),
                                     member.character.get_absolute_url(),
                                     esc(member.character.name))
                else:
                    characters += '%s [%s' % (group.name,
                                              member.character.name)
                if compare:
                    disambiguation += '%s [<br>&nbsp;&nbsp; %s' % (
                      group.disambiguated,
                      member.character.character.disambiguated)
            else:
                characters += '; '
                if compare:
                    disambiguation += '<br>'
                if url:
                    characters += '<a href="%s">%s</a>' \
                                  % (member.character.get_absolute_url(),
                                     esc(member.character.name))
                else:
                    characters += '%s' % member.character.name
                if compare:
                    disambiguation += '&nbsp;&nbsp; %s' % \
                                      member.character.character.disambiguated
            characters += get_civilian_identity(member,
                                                all_appearing_characters,
                                                url=url)
            characters += character_notes(member)
            if compare:
                disambiguation += get_civilian_identity(
                  member, all_appearing_characters, url=url, compare=compare)
        characters += ']; '
        if compare:
            disambiguation += ']<br>'
    characters = characters[:-2]

    appearing_characters = all_appearing_characters.exclude(
      character__id__in=in_group.values_list('character'), group__isnull=False)
    for character in appearing_characters:
        alias_identity = set(
          character.character.character.from_related_character
                   .filter(relation_type__id=2).values_list('from_character',
                                                            flat=True))\
                   .intersection(all_appearing_characters.values_list(
                                 'character__character', flat=True))
        if alias_identity:
            continue
        if first:
            first = False
        else:
            characters += '; '
            if compare:
                disambiguation += '<br>'
        if url:
            characters += '<a href="%s">%s</a>' % (
              character.character.get_absolute_url(),
              esc(character.character.name))
        else:
            characters += '%s' % character.character.name
        if compare:
            disambiguation += \
              '%s' % character.character.character.disambiguated

        characters += get_civilian_identity(character,
                                            appearing_characters,
                                            url=url)
        characters += character_notes(character)
        if compare:
            disambiguation += get_civilian_identity(character,
                                                    appearing_characters,
                                                    url=url,
                                                    compare=compare)
    if story.characters:
        if url:
            text_characters = esc(story.characters)
        else:
            text_characters = story.characters
        if characters:
            characters += '; %s' % text_characters
        else:
            characters = text_characters

    if characters and url:
        if css_style:
            dt = '<dt class="credit_tag"><span class="credit_label">' \
                 'Characters</span></dt>'
            return mark_safe(
              dt + '<dd class="credit_def"><span class="credit_value">'
              + characters + '</span></dd>')
        else:
            if compare and disambiguation:
                return mark_safe(characters +
                                 '<br>For information, linked characters '
                                 'with disambiguation:<br>' + disambiguation)
            else:
                return mark_safe(characters)
    else:
        return characters


class CreditType(models.Model):
    class Meta:
        app_label = 'gcd'
        db_table = 'gcd_credit_type'
        ordering = ['sort_code']

    name = models.CharField(max_length=50, db_index=True, unique=True)
    sort_code = models.IntegerField(unique=True)

    def __str__(self):
        return self.name


# TODO should StoryCredit be a GcdData or a Gcd Link-object ?
# Unlikely that we need a change history or other access to individual
# credits, these all go via the issue of the story and that change history.
# So what is the reason to keep these in the database after a delete ?
# A GcdLink avoids filtering for active-status, which for example would
# allow a prefetch_related for all credits of an issue.
class StoryCredit(GcdData):
    class Meta:
        app_label = 'gcd'
        db_table = 'gcd_story_credit'

    creator = models.ForeignKey(CreatorNameDetail, on_delete=models.CASCADE)
    credit_type = models.ForeignKey(CreditType, on_delete=models.CASCADE)
    story = models.ForeignKey('Story', on_delete=models.CASCADE,
                              related_name='credits')

    is_credited = models.BooleanField(default=False, db_index=True)
    is_signed = models.BooleanField(default=False, db_index=True)
    signature = models.ForeignKey(CreatorSignature, on_delete=models.CASCADE,
                                  related_name='credits', db_index=True,
                                  null=True)

    uncertain = models.BooleanField(default=False, db_index=True)

    signed_as = models.CharField(max_length=255)
    credited_as = models.CharField(max_length=255)

    is_sourced = models.BooleanField(default=False, db_index=True)
    sourced_by = models.CharField(max_length=255)

    # record for a wider range of creative work types, or how it is credited
    credit_name = models.CharField(max_length=255)

    def __str__(self):
        return "%s: %s (%s)" % (self.story, self.creator, self.credit_type)


class CharacterRole(models.Model):
    class Meta:
        app_label = 'gcd'
        db_table = 'gcd_character_role'
        ordering = ['sort_code']

    name = models.CharField(max_length=50, db_index=True, unique=True)
    sort_code = models.IntegerField(unique=True)

    def __str__(self):
        return self.name


class StoryCharacter(GcdData):
    class Meta:
        app_label = 'gcd'
        db_table = 'gcd_story_character'
        ordering = ['character__sort_name']

    character = models.ForeignKey(CharacterNameDetail,
                                  on_delete=models.CASCADE)
    story = models.ForeignKey('Story', on_delete=models.CASCADE,
                              related_name='appearing_characters')
    group = models.ManyToManyField(Group)
    role = models.ForeignKey(CharacterRole, null=True,
                             on_delete=models.CASCADE)
    is_flashback = models.BooleanField(default=False, db_index=True)
    is_origin = models.BooleanField(default=False, db_index=True)
    is_death = models.BooleanField(default=False, db_index=True)

    notes = models.TextField()

    def __str__(self):
        return "%s: %s" % (self.story, self.character)


class StoryTypeManager(models.Manager):
    def get_by_natural_key(self, name):
        return self.get(name=name)


class StoryType(models.Model):
    class Meta:
        app_label = 'gcd'
        db_table = 'gcd_story_type'
        ordering = ['sort_code']

    objects = StoryTypeManager()

    name = models.CharField(max_length=50, db_index=True, unique=True)
    sort_code = models.IntegerField(unique=True)

    def natural_key(self):
        return (self.name,)

    def __str__(self):
        return self.name


class Story(GcdData):
    class Meta:
        app_label = 'gcd'
        ordering = ['sequence_number']

    # Core story fields.
    title = models.CharField(max_length=255)
    title_inferred = models.BooleanField(default=False, db_index=True)
    first_line = models.CharField(max_length=255, default='')
    feature = models.CharField(max_length=255)
    feature_object = models.ManyToManyField(Feature)
    feature_logo = models.ManyToManyField(FeatureLogo)
    type = models.ForeignKey(StoryType, on_delete=models.CASCADE)
    sequence_number = models.IntegerField()

    page_count = models.DecimalField(max_digits=10, decimal_places=3,
                                     null=True, db_index=True)
    page_count_uncertain = models.BooleanField(default=False, db_index=True)

    script = models.TextField()
    pencils = models.TextField()
    inks = models.TextField()
    colors = models.TextField()
    letters = models.TextField()
    editing = models.TextField()

    no_script = models.BooleanField(default=False, db_index=True)
    no_pencils = models.BooleanField(default=False, db_index=True)
    no_inks = models.BooleanField(default=False, db_index=True)
    no_colors = models.BooleanField(default=False, db_index=True)
    no_letters = models.BooleanField(default=False, db_index=True)
    no_editing = models.BooleanField(default=False, db_index=True)

    job_number = models.CharField(max_length=25)
    genre = models.CharField(max_length=255)
    characters = models.TextField()
    synopsis = models.TextField()
    reprint_notes = models.TextField()
    notes = models.TextField()
    keywords = TaggableManager()

    awards = GenericRelation(ReceivedAward)

    # Fields from issue.
    issue = models.ForeignKey('Issue', on_delete=models.CASCADE)

    @property
    def from_reprints(self):
        return self.from_all_reprints.all()

    @property
    def from_story_reprints(self):
        return self.from_reprints.exclude(origin=None)

    @property
    def from_issue_reprints(self):
        return self.from_reprints.filter(origin=None)

    @property
    def to_reprints(self):
        return self.to_all_reprints.all()

    @property
    def to_story_reprints(self):
        return self.to_reprints.exclude(target=None)

    @property
    def to_issue_reprints(self):
        return self.to_reprints.filter(target=None)

    @property
    def active_credits(self):
        if not hasattr(self, '_active_credits'):
            # the exclude prevents a prefetch_related for the whole story
            # so one query per story and credit
            self._active_credits = self.credits.exclude(deleted=True)\
                                       .select_related('creator__creator',
                                                       'creator__type')
        return self._active_credits

    @property
    def active_characters(self):
        if not hasattr(self, '_active_characters'):
            self._active_characters = self.appearing_characters\
                                      .exclude(deleted=True)\
                                      .select_related('character__character')
        return self._active_characters

    _update_stats = True

    def stat_counts(self):
        if self.deleted:
            return {}

        return {
            'stories': 1,
        }

    def has_credits(self):
        """
        Simplifies UI checks for conditionals.  Credit fields.
        """
        return self.script or \
            self.pencils or \
            self.inks or \
            self.colors or \
            self.letters or \
            self.editing or \
            self.active_credits.exists()

    def has_content(self):
        """
        Simplifies UI checks for conditionals.  Content fields
        """
        return self.job_number or \
            self.genre or \
            self.has_characters or \
            self.first_line or \
            self.synopsis or \
            self.has_keywords() or \
            self.feature_object.values('genre') or \
            self.has_reprints() or \
            self.feature_logo.count() or \
            self.active_awards().count()

    def has_characters(self):
        """
        UI check for characters.
        """
        return self.characters or self.appearing_characters.count()

    def has_feature(self):
        """
        UI check for features.

        feature_logo entry automatically results in corresponding
        feature_object entry, therefore no check needed
        """
        return self.feature or self.feature_object.count()

    def has_reprints(self, notes=True):
        return (notes and self.reprint_notes) or \
               self.from_all_reprints.count() or \
               self.to_all_reprints.count()

    def has_data(self):
        """
        Simplifies UI checks for conditionals.  All non-heading fields
        """
        return self.has_credits() or self.has_content() or self.notes

    def active_awards(self):
        return self.awards.exclude(deleted=True)

    def _show_characters(cls, story):
        return show_characters(story)

    def show_characters(self):
        return self._show_characters(self)

    def show_characters_as_text(self):
        return show_characters(self, url=False)

    def _show_feature(cls, story):
        return show_feature(story)

    def show_feature(self):
        return self._show_feature(self)

    def show_feature_as_text(self):
        return show_feature_as_text(self)

    def _show_feature_logo(self, story):
        from apps.gcd.templatetags.display import absolute_url
        first = True
        features = ''
        for feature in story.feature_logo.all():
            if first:
                first = False
            else:
                features += '; '
            features += absolute_url(feature, feature.logo)
        return mark_safe(features)

    def show_feature_logo(self):
        return self._show_feature_logo(self)

    def show_title(self, use_first_line=False):
        """
        Return a properly formatted title.
        """
        if self.title == '':
            if use_first_line and self.first_line:
                return '["%s"]' % self.first_line
            else:
                return '[no title indexed]'
        if self.title_inferred:
            return '[%s]' % self.title
        return self.title

    def show_page_count(self, show_page=False):
        """
        Return a properly formatted page count, with "?" as needed.
        """
        if self.page_count is None:
            if self.page_count_uncertain:
                return '?'
            return ''

        p = f'{float(self.page_count):.3g}'
        if self.page_count_uncertain:
            p = '%s ?' % p
        if show_page:
            p = p + ' ' + ungettext('page', 'pages', self.page_count)
        return p

    def get_absolute_url(self):
        return urlresolvers.reverse(
            'show_issue',
            kwargs={'issue_id': self.issue_id}) + "#%d" % self.id

    def __str__(self):
        from apps.gcd.templatetags.display import show_story_short
        return show_story_short(self, no_number=True, markup=False)


class BiblioEntry(Story):
    class Meta:
        app_label = 'gcd'
        db_table = 'gcd_biblio_entry'

    page_began = models.IntegerField(null=True)
    page_ended = models.IntegerField(null=True)
    abstract = models.TextField()
    doi = models.TextField()

##############################################################################
# Tables with Sorting
##############################################################################


class StoryColumn(tables.TemplateColumn):
    def order(self, query_set, is_descending):
        direction = '-' if is_descending else ''
        query_set = query_set.order_by(direction + 'title',
                                       direction + 'issue__series__sort_name',
                                       direction + 'issue__sort_code',
                                       direction + 'sequence_number')
        return (query_set, True)

    def value(self, record):
        return str(record)


# keep similar to issue.py, but here is record.issue and not record
class IssueColumn(tables.TemplateColumn):
    def order(self, query_set, is_descending):
        direction = '-' if is_descending else ''
        query_set = query_set.order_by(direction + 'issue__series__sort_name',
                                       direction + 'issue__sort_code',
                                       'sequence_number')
        return (query_set, True)

    def value(self, record):
        return str(record.issue)


class StoryTable(tables.Table):
    story = StoryColumn(accessor='id', verbose_name='Story',
                        template_name='gcd/bits/sortable_sequence_entry.html')
    issue = IssueColumn(accessor='issue__id', verbose_name='Issue',
                        template_name='gcd/bits/sortable_issue_entry.html')
    publisher = tables.Column(accessor='issue__series__publisher',
                              verbose_name='Publisher')
    publication_date = tables.Column(accessor='issue__publication_date',
                                     verbose_name='Publication Date')
    on_sale_date = tables.Column(accessor='issue__on_sale_date',
                                 verbose_name='On-sale Date')

    class Meta:
        model = Story
        fields = ('story',)
        attrs = {'th': {'class': "non_visited"}}

    def order_publication_date(self, query_set, is_descending):
        direction = '-' if is_descending else ''
        query_set = query_set.order_by(direction + 'issue__key_date',
                                       direction + 'issue__series__sort_name',
                                       direction + 'issue__sort_code')
        return (query_set, True)

    def order_on_sale_date(self, query_set, is_descending):
        direction = '-' if is_descending else ''
        query_set = query_set.order_by(direction + 'issue__on_sale_date',
                                       direction + 'issue__key_date',
                                       direction + 'issue__series_name',
                                       direction + 'issue__sort_code')
        return (query_set, True)

    def order_publisher(self, query_set, is_descending):
        direction = '-' if is_descending else ''
        query_set = query_set.order_by(direction +
                                       'issue__series__publisher__name',
                                       direction + 'issue__series__sort_name',
                                       direction + 'issue__sort_code')
        return (query_set, True)

    def render_publisher(self, value):
        from apps.gcd.templatetags.display import absolute_url
        from apps.gcd.templatetags.credits import show_country_info
        display_publisher = "<img %s>" % (show_country_info(value.country))
        return mark_safe(display_publisher) + absolute_url(value)

    def value_publisher(self, value):
        return str(value)
