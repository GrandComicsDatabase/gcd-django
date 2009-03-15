from django.db import models

class Creator(models.Model):
    class Meta:
        db_table = 'inducks_person'
        app_label = 'coa'

    class Admin:
        pass

    id = models.CharField(max_length = 100, primary_key = True, 
                          db_column = 'personcode')

    name = models.CharField(max_length = 1000, 
                            db_column = 'fullname')
