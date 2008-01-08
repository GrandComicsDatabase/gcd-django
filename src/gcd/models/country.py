from django.db import models

class Country(models.Model):
    code = models.CharField(max_length = 10, null = True)
    country = models.CharField(max_length = 255, null = True)
    id = models.AutoField(primary_key = True, db_column = 'ID')

    class Meta:
        db_table = 'Countries'

    def __str__(self):
        return self.country + " (" + self.code + ")"

