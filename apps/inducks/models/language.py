from django.db import models

class Language(models.Model):
    class Meta:
        db_table = 'inducks_language'
        app_label = 'coa'

    class Admin:
        pass

    code = models.CharField(primary_key = True, 
                            db_column = 'languagecode', 
                            max_length = 100)
    name = models.CharField(db_column = 'languagename', 
                            max_length = 100, null = True)
    class Admin:
        pass

    def __str__(self):
        return self.name + " (" + self.code + ")"
