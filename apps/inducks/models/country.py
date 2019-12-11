from django.db import models

class Country(models.Model):
    class Meta:
        db_table = 'inducks_country'
        app_label = 'coa'

    class Admin:
        pass

    code = models.CharField(primary_key = True, 
                            db_column = 'countrycode', 
                            max_length = 100)
    name = models.CharField(db_column = 'countryname', 
                            max_length = 100, null = True)
    language = models.CharField(db_column = 'defaultlanguage',
                                max_length = 100, null = True)

    def __str__(self):
        return self.name
