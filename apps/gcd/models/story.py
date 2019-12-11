from django.db import models
from django.contrib.contenttypes.fields import GenericRelation
from django.core import urlresolvers
from django.utils.safestring import mark_safe
from django.utils.html import conditional_escape as esc

from taggit.managers import TaggableManager

from .gcddata import GcdData
from .award import ReceivedAward
from .creator import CreatorNameDetail
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
}

CREDIT_TYPES = {
    'script': '1',
    'pencils': '2',
    'inks': '3',
    'colors': '4',
    'letters': '5',
    'editing': '6',
}

OLD_TYPES = {
    '(unknown)',
    '(backcovers) *do not use* / *please fix*',
    'biography (nonfictional)'
}

# core sequence types: (photo, text) story, cover (incl. reprint)
CORE_TYPES = [6, 7, 13, 19, 21]
# ad sequence types: ad, promo
AD_TYPES = [2, 16, 26]
# non-optional sequences: story, cover (incl. reprint)
NON_OPTIONAL_TYPES = [6, 7, 19]


def show_feature(story):
    first = True
    features = ''
    for feature in story.feature_object.all():
        if first:
            first = False
        else:
            features += '; '
        features += '<a href="%s">%s</a>' % (feature.get_absolute_url(),
                                              esc(feature.name))
    if story.feature:
        if features:
            features += '; %s' % esc(story.feature)
        else:
            features = esc(story.feature)
    return mark_safe(features)


class CreditType(models.Model):
    class Meta:
        app_label = 'gcd'
        db_table = 'gcd_credit_type'
        ordering = ['sort_code']

    name = models.CharField(max_length=50, db_index=True, unique=True)
    sort_code = models.IntegerField(unique=True)

    def __unicode__(self):
        return self.name


class StoryCredit(GcdData):
    class Meta:
        app_label = 'gcd'
        db_table = 'gcd_story_credit'

    creator = models.ForeignKey(CreatorNameDetail)
    credit_type = models.ForeignKey(CreditType)
    story = models.ForeignKey('Story', related_name='credits')

    is_credited = models.BooleanField(default=False, db_index=True)
    is_signed = models.BooleanField(default=False, db_index=True)

    uncertain = models.BooleanField(default=False, db_index=True)

    signed_as = models.CharField(max_length=255)
    credited_as = models.CharField(max_length=255)

    # record for a wider range of creative work types, or how it is credited
    credit_name = models.CharField(max_length=255)

    def __unicode__(self):
        return "%s: %s (%s)" % (self.story, self.creator, self.credit_type)


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
    type = models.ForeignKey(StoryType)
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
    issue = models.ForeignKey('Issue')

    _update_stats = True

    @property
    def active_credits(self):
        return self.credits.exclude(deleted=True)

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
               self.characters or \
               self.first_line or \
               self.synopsis or \
               self.has_keywords() or \
               self.has_reprints() or \
               self.feature_logo.count() or \
               self.active_awards().count()

    def has_feature(self):
        """
        UI check for features.

        feature_logo entry automatically results in corresponding
        feature_object entry, therefore no check needed
        """
        return self.feature or self.feature_object.count()

    def has_reprints(self, notes=True):
        return (notes and self.reprint_notes) or \
               self.from_reprints.count() or \
               self.to_reprints.count() or \
               self.from_issue_reprints.count() or \
               self.to_issue_reprints.count()

    def has_data(self):
        """
        Simplifies UI checks for conditionals.  All non-heading fields
        """
        return self.has_credits() or self.has_content() or self.notes

    def active_awards(self):
        return self.awards.exclude(deleted=True)

    def _show_feature(cls, story):
        return show_feature(story)

    def show_feature(self):
        return self._show_feature(self)

    def show_feature_as_text(self):
        first = True
        features = ''
        for feature in self.feature_object.all():
            if first:
                first = False
            else:
                features += '; '
            features += '%s' % feature.name
        if self.feature:
            if features:
                features += '; %s' % self.feature
            else:
                features = self.feature
        return features

    def _show_feature_logo(self, story):
        return "; ".join(story.feature_logo.all().values_list('name',
                                                              flat=True))

    def show_feature_logo(self):
        return self._show_feature_logo(self)

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
