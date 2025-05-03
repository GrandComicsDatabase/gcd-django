from django.contrib.contenttypes.fields import GenericRelation
from django.db import models
import django.urls as urlresolvers
from django.utils.safestring import mark_safe
from django.utils.html import conditional_escape as esc
from django.utils.translation import ngettext

from taggit.managers import TaggableManager

import django_tables2 as tables

from .gcddata import GcdData
from .award import ReceivedAward
from .character import CharacterNameDetail, Group, GroupNameDetail, \
                       Universe, Multiverse
from .creator import CreatorNameDetail, CreatorSignature
from .feature import Feature, FeatureLogo
from .support_tables import render_publisher

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


def show_title(story, use_first_line=False):
    """
    Return a properly formatted title.
    """
    if story.title == '':
        if use_first_line and story.first_line:
            return '["%s"]' % story.first_line
        else:
            return '[no title indexed]'
    if story.title_inferred:
        return '[%s]' % story.title
    return story.title


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


def _get_civilian_identity(character, appearing_characters):
    appearing_characters = appearing_characters.filter(
      universe=character.universe)
    civilian_identity = set(
        character.character.character.to_related_character
                 .filter(relation_type__id=2).values_list('to_character',
                                                          flat=True))\
                 .intersection(appearing_characters.values_list(
                               'character__character', flat=True))
    return civilian_identity


def get_civilian_identity(character, appearing_characters, url=True,
                          compare=False):
    civilian_identity = _get_civilian_identity(character, appearing_characters)

    if civilian_identity:
        civilian_identity = appearing_characters.filter(
              universe=character.universe,
              character__character__id__in=civilian_identity)
        characters = ' ['
        several = False
        compare_characters = ''
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
                if several:
                    compare_characters += '; '
                compare_characters += ' [%s' % identity.character.character\
                                                       .disambiguated
            several = True
        characters += ']'
        if compare:
            return compare_characters + ']'
        return characters
    else:
        return ''


def _get_reference_universe(story):
    reference_universe_id = None
    if story.universe.count() == 1:
        reference_universe_id = story.universe.get().id
    elif story.universe.count() == 2:
        reference_universe_id = -1
    else:
        if len(set(story.appearing_characters.exclude(universe__verse=None)
                   .values_list('universe__verse', flat=True))) == 1:
            mainstream_universe_id = set(story.appearing_characters.exclude(
              universe__verse=None).values_list('universe__verse', flat=True))\
              .pop()
            reference_universe_id = Multiverse.objects.get(
              id=mainstream_universe_id).mainstream_id
    return reference_universe_id


def _process_single_character(character, appearing_characters,
                              reference_universe_id):
    universe = None
    if reference_universe_id and character.universe:
        if character.universe_id != reference_universe_id:
            universe = character.universe
    civilian_identity = _get_civilian_identity(character,
                                               appearing_characters)
    if civilian_identity:
        civilian_identity = appearing_characters.filter(
          universe=character.universe,
          character__character__id__in=civilian_identity)
    return (character, civilian_identity, universe)


def process_appearing_characters(story):
    all_appearing_characters = story.active_characters
    in_group = all_appearing_characters.exclude(group_name=None)
    groups = story.active_groups

    reference_universe_id = _get_reference_universe(story)

    group_list = []
    processed_appearances_ids = []
    for group in groups:
        group_universe = None
        if reference_universe_id and group.universe:
            if group.universe_id != reference_universe_id:
                group_universe = group.universe
        character_list = []
        for member in in_group.filter(group_name=group.group_name_id,
                                      group_universe=group.universe_id):
            character_list.append(_process_single_character(
              member, all_appearing_characters, reference_universe_id))
            processed_appearances_ids.append(member.id)
        group_list.append((group, group_universe, character_list))
    appearing_characters = all_appearing_characters.exclude(
      id__in=processed_appearances_ids)

    character_list = []
    for character in appearing_characters:
        alias_identity = set(
          character.character.character.from_related_character
                   .filter(relation_type__id=2).values_list('from_character',
                                                            flat=True))\
                   .intersection(all_appearing_characters.filter(
                      universe=character.universe).values_list(
                      'character__character', flat=True))
        if alias_identity:
            continue
        character_list.append(_process_single_character(
          character, all_appearing_characters, reference_universe_id))
    return (group_list, character_list)


def show_characters(story, url=True, css_style=True, compare=False,
                    bare_value=False):
    first = True
    characters = ''
    disambiguation = ''

    all_appearing_characters = story.active_characters
    in_group = all_appearing_characters.exclude(group_name=None)
    groups = story.active_groups

    reference_universe_id = _get_reference_universe(story)
    for group in groups:
        first_member = True
        group_universe_name = ''
        if reference_universe_id and group.universe:
            if group.universe_id != reference_universe_id:
                group_universe_name = group.universe.universe_name()
        if url:
            characters += '<a href="%s"><b>%s</b></a>%s%s: ' \
                            % (group.group_name.group.get_absolute_url(),
                               esc(group.group_name.name),
                               ' <i>(%s)</i>' %
                               group_universe_name if
                               group_universe_name else '',
                               ' (%s)' %
                               group.notes if group.notes else '')
        else:
            characters += '%s%s%s [' % (group.group_name.name,
                                        ' (%s)' % group_universe_name if
                                        group_universe_name else '',
                                        ' (%s)' %
                                        group.notes if group.notes else '')
        for member in in_group.filter(group_name=group.group_name_id,
                                      group_universe=group.universe_id):
            if first_member:
                first_member = False
                if url:
                    characters += '<a href="%s">%s</a>' \
                                  % (member.character.get_absolute_url(),
                                     esc(member.character.name))
                else:
                    characters += '%s' % (member.character.name)
                if compare:
                    disambiguation += '%s%s: <br>&nbsp;&nbsp; %s' % (
                      group.group_name.group.disambiguated,
                      ' - %s' % group.universe.universe_name()
                      if group.universe else '',
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
            if compare:
                disambiguation += get_civilian_identity(
                  member, all_appearing_characters, url=url, compare=compare)
                if member.universe:
                    disambiguation += ' - %s' % member.universe
            if reference_universe_id and member.universe:
                if member.universe_id != reference_universe_id:
                    if url:
                        characters += ' (<i>%s</i>)' % member.universe\
                                                             .universe_name()
                    else:
                        characters += ' (%s)' % member.universe\
                                                      .universe_name()
            characters += character_notes(member)
        if first_member is True:
            characters = characters[:-2]
            if url:
                characters += '<br>'
                first_member = False
            else:
                characters += '; '
            if compare:
                disambiguation += '%s%s' % (
                  group.group_name.group.disambiguated,
                  ' - %s' % group.universe.universe_name()
                  if group.universe else '')
        else:
            if url:
                characters += '<br>'
            else:
                characters += ']; '
        if compare:
            disambiguation += '<br><br>'
    if groups and first_member is True:
        characters = characters[:-2]

    appearing_characters_ids = list(all_appearing_characters.exclude(
      character__id__in=in_group.values_list('character'),
      group_name__isnull=False).values_list('character', flat=True))
    # We do not give the QuerySet to the filter, but the IDs.
    # In get_civilian_identity we need to filter the appearing_characters
    # once more, which otherwise would still use the above exclude,
    # which for StoryCharacterRevision is somehow expensive.
    appearing_characters = all_appearing_characters.filter(
      character_id__in=appearing_characters_ids)

    for character in appearing_characters:
        alias_identity = set(
          character.character.character.from_related_character
                   .filter(relation_type__id=2).values_list('from_character',
                                                            flat=True))\
                   .intersection(all_appearing_characters.filter(
                      universe=character.universe).values_list(
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
        if compare:
            disambiguation += get_civilian_identity(character,
                                                    appearing_characters,
                                                    url=url,
                                                    compare=compare)
            if character.universe:
                disambiguation += ' - %s' % character.universe
        if reference_universe_id and character.universe:
            if character.universe_id != reference_universe_id:
                if url:
                    characters += ' <i>(%s)</i>' % character.universe\
                                                            .universe_name()
                else:
                    characters += ' (%s)' % character.universe\
                                                     .universe_name()
        characters += character_notes(character)

    if story.characters:
        if url:
            text_characters = esc(story.characters)
        else:
            text_characters = story.characters
        if characters:
            if first:
                characters += '%s' % text_characters
            else:
                characters += '; %s' % text_characters
        else:
            characters = text_characters

    if compare and disambiguation:
        universes = story.appearing_characters.exclude(universe=None)\
                         .order_by('universe')\
                         .values_list('universe', flat=True).distinct()
        if story.issue:
            key_date = story.issue.key_date
        else:
            key_date = None
        if universes.exists() and key_date:
            for universe_id in universes:
                universe = Universe.objects.get(id=universe_id)
                if universe.year_first_published and \
                   int(key_date[:4]) < universe.year_first_published:
                    disambiguation += '<br><br>Note: Universe "%s" used ' \
                      'before its year first published %d.' % (
                        universe, universe.year_first_published)

    if characters and url:
        if css_style:
            if bare_value:
                return mark_safe(characters)
            else:
                dt = '<dt class="credit_tag"><span class="credit_label">' \
                  'Characters</span></dt>'
                return mark_safe(
                  dt + '<dd class="credit_def"><span class="credit_value">'
                  + characters + '</span></dd>')
        else:
            if compare and disambiguation:
                return mark_safe(characters +
                                 '<br><br>For information, linked characters '
                                 'with disambiguation and universe:<br>' +
                                 disambiguation)
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

    def display_credit(self):
        return self.creator.display_credit(self)

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
    universe = models.ForeignKey(Universe, null=True,
                                 on_delete=models.CASCADE)
    story = models.ForeignKey('Story', on_delete=models.CASCADE,
                              related_name='appearing_characters')
    # TODO: remove group, rename group_name to group
    group = models.ManyToManyField(Group)
    group_name = models.ManyToManyField(GroupNameDetail)
    group_universe = models.ForeignKey(Universe, null=True,
                                       on_delete=models.CASCADE,
                                       related_name='story_character_in_group')
    role = models.ForeignKey(CharacterRole, null=True,
                             on_delete=models.CASCADE)
    is_flashback = models.BooleanField(default=False, db_index=True)
    is_origin = models.BooleanField(default=False, db_index=True)
    is_death = models.BooleanField(default=False, db_index=True)

    notes = models.TextField()

    def show_notes(self):
        return character_notes(self)

    def __str__(self):
        return "%s: %s" % (self.story, self.character)


class StoryGroup(GcdData):
    class Meta:
        app_label = 'gcd'
        db_table = 'gcd_group_character'
        ordering = ['group_name__sort_name']

    # TODO: rename group_name to group ?
    group_name = models.ForeignKey(GroupNameDetail,
                                   on_delete=models.CASCADE)
    universe = models.ForeignKey(Universe, null=True,
                                 on_delete=models.CASCADE)
    story = models.ForeignKey('Story', on_delete=models.CASCADE,
                              related_name='appearing_groups')
    notes = models.TextField()

    def __str__(self):
        return "%s: %s" % (self.story, self.group_name)


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


def check_credited_signed(first_credit, credit):
    if first_credit.is_credited == credit.is_credited and \
       first_credit.is_signed == credit.is_signed and \
       first_credit.signature == credit.signature and \
       first_credit.signed_as == credit.signed_as and \
       first_credit.credited_as == credit.credited_as and \
       first_credit.is_sourced == credit.is_sourced and \
       first_credit.sourced_by == credit.sourced_by and \
       first_credit.uncertain == credit.uncertain:
        return True
    else:
        return False


def extend_credit_roles(credit, added_type_name):
    credit_type_name = '%s, %s' % (credit.credit_type_name, added_type_name)
    if credit_type_name == 'pencils (painting), inks (painting), ' \
                           'colors (painting)':
        credit_type_name = 'painting'

    credit.credit_type_name = credit_type_name
    return credit


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
    universe = models.ManyToManyField(Universe)
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
    def creator_credits(self):
        credits = self.credits.exclude(deleted=True)\
                              .select_related('creator__creator',
                                              'creator__type')\
                              .order_by('credit_type__sort_code',
                                        'id')
        creator_credits = {}
        creator_doubled = {}
        if credits:
            for credit in credits:
                if credit.credit_name:
                    added_type_name = '%s (%s)' % (credit.credit_type.name,
                                                   credit.credit_name)
                    credit.credit_name = ''
                else:
                    added_type_name = credit.credit_type.name

                if credit.creator.id in creator_credits:
                    # TODO, we can use show_sources to turn off display
                    # of sourced in creator name display and add it after
                    # the credit type

                    if not check_credited_signed(creator_credits[
                                                 credit.creator.id], credit):
                        if credit.creator.id in creator_doubled:
                            if not check_credited_signed(
                               creator_doubled[credit.creator.id], credit):
                                credit.credit_type_name = added_type_name
                                creator_credits['%d-%d' % (credit.creator.id,
                                                           credit.id)] = credit
                            else:
                                extend_credit_roles(creator_doubled[
                                                    credit.creator.id],
                                                    added_type_name)
                        else:
                            credit.credit_type_name = added_type_name
                            creator_credits['%d-%d' % (credit.creator.id,
                                                       credit.id)] = credit
                            creator_doubled[credit.creator.id] = credit
                    else:
                        extend_credit_roles(creator_credits[credit.creator.id],
                                            added_type_name)
                    continue
                else:
                    credit.credit_type_name = added_type_name
                    creator_credits[credit.creator.id] = credit
        return creator_credits

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

    @property
    def active_groups(self):
        if not hasattr(self, '_active_groups'):
            self._active_groups = self.appearing_groups\
                                      .exclude(deleted=True)
        return self._active_groups

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
            self.has_characters() or \
            self.first_line or \
            self.synopsis or \
            self.has_keywords() or \
            self.has_reprints() or \
            self.feature_object.exclude(genre='').values('genre').exists() or \
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

    def has_reprints(self, notes=True, ignore=STORY_TYPES['preview']):
        if self.type_id not in [STORY_TYPES['preview'],
                                STORY_TYPES['comics-form ad']]:
            ignore = AD_TYPES
        else:
            ignore = []
        return ((notes and self.reprint_notes) or
                self.from_all_reprints.count() or
                self.to_all_reprints.exclude(target__type__id__in=ignore)
                                    .count())

    def reprint_count(self):
        if self.type_id not in [STORY_TYPES['preview'],
                                STORY_TYPES['comics-form ad']]:
            ignore = AD_TYPES
        else:
            ignore = []
        return (self.from_all_reprints.count() +
                self.to_all_reprints.exclude(target__type__id__in=ignore)
                                    .count())

    def has_data(self):
        """
        Simplifies UI checks for conditionals.  All non-heading fields
        """
        return self.has_credits() or self.has_content() or self.notes

    def active_awards(self):
        return self.awards.exclude(deleted=True)

    def process_appearing_characters(self):
        return process_appearing_characters(self)

    def _show_characters(cls, story, css_style=True, bare_value=False):
        return show_characters(story, css_style=css_style,
                               bare_value=bare_value)

    def show_characters(self, css_style=True):
        return self._show_characters(self, css_style=css_style)

    def show_characters_bare_value(self, css_style=True):
        return self._show_characters(self, css_style=css_style,
                                     bare_value=True)

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

    def show_universe(self):
        from apps.gcd.templatetags.display import absolute_url
        universes = ''
        for universe in self.universe.all():
            universes += absolute_url(universe) + '; '
        if universes:
            universes = universes[:-2]
        label = '<span class="field-name-label">Universe:</span>'
        return mark_safe(label + universes)

    def show_title(self, use_first_line=False):
        return show_title(self, use_first_line)

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
            p = p + ' ' + ngettext('page', 'pages', self.page_count)
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
                                       direction + 'issue__series__year_began',
                                       direction + 'issue__series_id',
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
                                       direction + 'issue__series__sort_name',
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
        return render_publisher(value)

    def value_publisher(self, value):
        return str(value)


class MatchedSearchStoryTable(StoryTable):
    matched_search = tables.Column(accessor='id', orderable=False,
                                   verbose_name='Matched Search')

    class Meta:
        model = Story
        fields = ('matched_search',)

    def __init__(self, *args, **kwargs):
        self.target = kwargs.pop('target')
        super(MatchedSearchStoryTable, self).__init__(*args, **kwargs)

    def render_matched_search(self, record):
        from apps.gcd.templatetags.credits import show_credit
        return mark_safe(show_credit(record, self.target,
                                     tailwind=True))


class HaystackStoryTable(tables.Table):
    story = tables.TemplateColumn(
      accessor='id', verbose_name='Story',
      template_name='gcd/bits/hs_sortable_sequence_entry.html')
    issue = tables.TemplateColumn(
      accessor='id', verbose_name='Issue',
      template_name='gcd/bits/hs_sortable_issue_entry.html')
    publisher = tables.Column(verbose_name='Publisher')
    publication_date = tables.Column(accessor='key_date',
                                     verbose_name='Publication Date',
                                     empty_values=('9999-99-99'))

    def order_publisher(self, query_set, is_descending):
        direction = '-' if is_descending else ''
        query_set = query_set.order_by(direction +
                                       'publisher',
                                       direction + 'sort_name',
                                       direction + 'sort_code')
        return (query_set, True)

    def order_issue(self, query_set, is_descending):
        direction = '-' if is_descending else ''
        query_set = query_set.order_by(direction + 'sort_name',
                                       direction + 'year',
                                       direction + 'sort_code',
                                       'sequence_number')
        return (query_set, True)

    def order_publication_date(self, query_set, is_descending):
        direction = '-' if is_descending else ''
        query_set = query_set.order_by(direction + 'key_date',
                                       direction + 'sort_name',
                                       direction + 'sort_code')
        return (query_set, True)

    def order_story(self, query_set, is_descending):
        direction = '-' if is_descending else ''
        query_set = query_set.order_by(direction + 'sort_title',
                                       direction + 'sort_name',
                                       direction + 'sort_code',
                                       direction + 'sequence_number')
        return (query_set, True)

    def render_country(self, record):
        from apps.gcd.templatetags.credits import show_country_info
        return mark_safe('<img ' +
                         show_country_info(record.object.issue.series.country)
                         + '>')

    def render_publication_date(self, record):
        return record.object.issue.publication_date

    def render_publisher(self, record):
        return render_publisher(record.object.issue.series.publisher)

    def value_country(self, value):
        return value

    def value_story(self, record):
        return str(record.object)

    def value_issue(self, record):
        return str(record.object.issue)

# TODO see if the two templates for sequence and issue can be combined or
# included from each other


class HaystackMatchedStoryTable(HaystackStoryTable):
    matched_search = tables.Column(accessor='id',
                                   verbose_name='Matched Search',
                                   orderable=False,
                                   exclude_from_export=True)

    class Meta:
        model = Story
        fields = ('matched_search',)

    def __init__(self, *args, **kwargs):
        self.target = kwargs.pop('target')
        super(HaystackMatchedStoryTable, self).__init__(*args, **kwargs)

    def value_matched_search(self, record):
        # TODO refactor render_method to use for both, maybe with
        # show_creator_credit_bare
        return ""

    def render_matched_search(self, record):
        from apps.gcd.templatetags.credits import show_credit
        if self.target.startswith('any:'):
            search_terms = self.target[4:].split()
            matched_credits = []
            for c in ['script', 'pencils', 'inks', 'colors', 'letters',
                      'editing']:
                credit = getattr(record, c, None)
                if credit:
                    credit = ' '.join(credit).lower()
                    found = True
                    for term in search_terms:
                        if not term.lower() in credit:
                            found = False
                    if found:
                        matched_credits.append(c)
            record.object.matched_credits = matched_credits
        if self.target.startswith('characters:'):
            search_terms = self.target[11:]
            if search_terms[0] == '"' and search_terms[-1] == '"':
                search_terms = [search_terms.strip('"'), ]
            else:
                search_terms = search_terms.split()
            matched_credits = []
            for c in ['characters', 'feature']:
                credit = getattr(record, c, None)
                if credit:
                    # credit is a multivalue field in the search index, join it
                    credit = ' '.join(credit).lower()
                    found = True
                    for term in search_terms:
                        if not term.lower() in credit:
                            found = False
                    if found:
                        matched_credits.append(c)
            record.object.matched_credits = matched_credits
        return mark_safe(show_credit(record.object, self.target,
                                     tailwind=True))
