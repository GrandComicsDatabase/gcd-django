from django.db import models

from series import Series
from issue import Issue

class Story(models.Model):
    class Meta:
        app_label = 'gcd'
        ordering = ['sequence_number']

    # Core story fields.
    feature = models.CharField(max_length=255, null=True)
    page_count = models.DecimalField(max_digits=10, decimal_places=4,
                                     null=True, db_index=True)
    page_count_uncertain = models.BooleanField(default=0, db_index=True)

    characters = models.TextField(null=True)

    script = models.TextField(max_length=255, null=True)
    pencils = models.TextField(max_length=255, null=True)
    inks = models.TextField(max_length=255, null=True)
    colors = models.TextField(max_length=255, null=True)
    letters = models.TextField(max_length=255, null=True)

    no_script = models.BooleanField(default=0, db_index=True)
    no_pencils = models.BooleanField(default=0, db_index=True)
    no_inks = models.BooleanField(default=0, db_index=True)
    no_colors = models.BooleanField(default=0, db_index=True)
    no_letters = models.BooleanField(default=0, db_index=True)

    title = models.CharField(max_length=255, null=True)
    editor = models.TextField(max_length=255, db_column='editing', null=True)
    notes = models.TextField(max_length=255, null=True)
    synopsis = models.TextField(max_length=255, null=True)
    reprints = models.TextField(max_length=255, db_column='reprint_notes',
                                null=True)
    genre = models.CharField(max_length=255, null=True)
    type = models.CharField(max_length=255, null=True)
    sequence_number = models.IntegerField(null=True, db_index=True)
    job_number = models.CharField(max_length=25, null=True, db_index=True)

    # Fields from issue.
    issue = models.ForeignKey(Issue)

    # Fields related to change management.
    reserved = models.BooleanField(default=0, db_index=True)
    created = models.DateTimeField(auto_now_add=True, null=True)
    modified = models.DateTimeField(auto_now=True, null=True)

    def has_credits(self):
        """Simplifies UI checks for conditionals.  Credit fields.
        Note that the editor field does not apply to the special cover story."""
        return self.script or \
               self.pencils or \
               self.inks or \
               self.colors or \
               self.letters or \
               (self.editor and (self.sequence_number > 0))

    def has_content(self):
        """Simplifies UI checks for conditionals.  Content fields"""
        return self.genre or \
               self.characters or \
               self.synopsis or \
               self.reprints or \
               self.job_number

    def has_data(self):
        """Simplifies UI checks for conditionals.  All non-heading fields"""
        return self.has_credits() or self.has_content() or self.notes

    def __unicode__(self):
        return u'%s (%s: %s)' % (self.feature, self.type, self.page_count)

