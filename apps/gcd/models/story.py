from django.db import models

from series import Series
from issue import Issue

class StoryType(models.Model):
    class Meta:
        app_label = 'gcd'
        db_table = 'gcd_story_type'
        ordering = ['id']
    name = models.CharField(max_length=50, db_index=True, unique=True)

    def __unicode__(self):
        return self.name

class Story(models.Model):
    class Meta:
        app_label = 'gcd'
        ordering = ['sequence_number']

    # Core story fields.
    title = models.CharField(max_length=255)
    title_inferred = models.BooleanField(default=0, db_index=True)
    feature = models.CharField(max_length=255)
    type = models.ForeignKey(StoryType)
    sequence_number = models.IntegerField()

    page_count = models.DecimalField(max_digits=10, decimal_places=3,
                                     null=True, db_index=True)
    page_count_uncertain = models.BooleanField(default=0, db_index=True)

    script = models.TextField()
    pencils = models.TextField()
    inks = models.TextField()
    colors = models.TextField()
    letters = models.TextField()
    editing = models.TextField()

    no_script = models.BooleanField(default=0, db_index=True)
    no_pencils = models.BooleanField(default=0, db_index=True)
    no_inks = models.BooleanField(default=0, db_index=True)
    no_colors = models.BooleanField(default=0, db_index=True)
    no_letters = models.BooleanField(default=0, db_index=True)
    no_editing = models.BooleanField(default=0, db_index=True)

    job_number = models.CharField(max_length=25)
    genre = models.CharField(max_length=255)
    characters = models.TextField()
    synopsis = models.TextField()
    reprint_notes = models.TextField()
    notes = models.TextField()

    # Fields from issue.
    issue = models.ForeignKey(Issue)

    # Fields related to change management.
    reserved = models.BooleanField(default=0, db_index=True)
    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)

    def has_credits(self):
        """Simplifies UI checks for conditionals.  Credit fields.
        Note that the editor field does not apply to the special cover story."""
        return self.script or \
               self.pencils or \
               self.inks or \
               self.colors or \
               self.letters or \
               self.editing

    def has_content(self):
        """Simplifies UI checks for conditionals.  Content fields"""
        return self.genre or \
               self.characters or \
               self.synopsis or \
               self.reprint_notes or \
               self.job_number

    def has_data(self):
        """Simplifies UI checks for conditionals.  All non-heading fields"""
        return self.has_credits() or self.has_content() or self.notes

    def __unicode__(self):
        return u'%s (%s: %s)' % (self.feature, self.type, self.page_count)

