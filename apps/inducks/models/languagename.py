from django.db import models

from .language import Language

class LanguageName(models.Model):
    class Meta:
        db_table = 'inducks_languagename'
        app_label = 'coa'

    class Admin:
        pass

    out_language = models.CharField(max_length = 20, primary_key = True, 
                                  db_column = 'desclanguagecode')
    name = models.CharField(max_length = 20, db_column = 'languagename')
    language = models.ForeignKey(Language, 
                                 db_column = 'languagecode')
    def __str__(self):
        return self.name
