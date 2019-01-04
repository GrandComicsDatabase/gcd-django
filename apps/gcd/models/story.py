from django.db import models
from django.contrib.contenttypes.fields import GenericRelation
from django.core import urlresolvers

from taggit.managers import TaggableManager

from .gcddata import GcdData
from .award import ReceivedAward

STORY_TYPES = {
    'cover': 6,
    'insert': 11,
    'soo': 22,
    'blank': 24,
    'preview': 26,
    'about comics': 27,
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

    def __unicode__(self):
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
               self.editing

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
               self.awards.all().count()
               
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

    def get_absolute_url(self):
        return urlresolvers.reverse(
            'show_issue',
            kwargs={'issue_id': self.issue_id } ) + "#%d" % self.id

    def __unicode__(self):
        return u'%s (%s: %s)' % (self.feature, self.type, self.page_count)


class BiblioEntry(Story):
    class Meta:
        app_label = 'gcd'
        db_table = 'gcd_biblio_entry'

    page_began = models.IntegerField(null=True)
    page_ended = models.IntegerField(null=True)
    abstract = models.TextField()
    doi = models.TextField()