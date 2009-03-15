from django.db import models

class Character(models.Model):
    class Meta:
        db_table = 'inducks_character'
        app_label = 'coa'

    class Admin:
        pass

    character = models.CharField(max_length = 20, primary_key = True, 
                               db_column = 'charactercode')
    name = models.CharField(max_length = 20, db_column = 'charactername')
