from django.db import models

class Language(models.Model):
    code = models.CharField(max_length = 10, null = True)
    name = models.CharField(db_column = 'language', max_length = 255,
                            null = True)
    id = models.AutoField(primary_key = True, db_column = 'ID')

    class Meta:
        db_table = 'Languages'
        app_label = 'gcd'

    def __unicode__(self):
        return self.language + " (" + self.code + ")"

