from django.db import models

class Publisher(models.Model):
    class Meta:
        db_table = 'inducks_publisher'
        app_label = 'coa'

    class Admin:
        pass

    id = models.CharField(max_length = 100, primary_key = True, 
                           db_column = 'publisherid')
    name = models.CharField(max_length = 1000, db_column = 'publishername', 
                            null = True)
