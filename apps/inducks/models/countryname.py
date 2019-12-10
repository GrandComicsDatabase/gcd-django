from django.db import models

from .country import Country
from .language import Language

class CountryName(models.Model):
    class Meta:
        db_table = 'inducks_countryname'
        app_label = 'coa'

    class Admin:
        pass

    country = models.ForeignKey(Country, primary_key = True, 
                                  db_column = 'countrycode')
    name = models.CharField(max_length = 20, db_column = 'countryname')
    language = models.ForeignKey(Language, primary_key = True, 
                                 db_column = 'languagecode')
    def __unicode__(self):
        return self.name
