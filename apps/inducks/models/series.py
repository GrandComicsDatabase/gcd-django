from django.db import models

from .country import Country
from .language import Language
#from publisher import Publisher

class Series(models.Model):

    class Meta:
        db_table = 'inducks_publication'
        app_label = 'coa'
        ordering = ['name']
    
    class Admin:
        list_display = ('name')

    id = models.CharField(max_length = 20, primary_key = True, 
                          db_column = 'publicationcode')

    # Core series fields.
    name = models.CharField(max_length = 255, db_column = 'title',
                            null = True)
    format = models.CharField(max_length = 255, db_column = 'size',
                              null = True)
    notes = models.TextField(db_column = 'publicationcomment', null = True)
    country_code = models.ForeignKey(Country, db_column = 'countrycode',
                                    null = True)
    # hmm, I think this should be a ForeignKey, but somehow doesn't work
    language_code = models.CharField(max_length = 3, db_column = 'languagecode',
                                     null = True)

    # Fields related to the publishers table.
    # publisher_name is redundant, and currently not used(?) by lasso version.
    #publisher = models.ForeignKey(Publisher, db_column = 'PubID', null = True)
    #publisher_name = models.CharField(max_length = 255, db_column = 'Pub_Name',
                                      #null = True)

    def get_absolute_url(self):
        return "/gcd/series/%i/" % self.id

    def __unicode__(self):
        return self.name

