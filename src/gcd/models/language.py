from django.db import models

class Language(models.Model):
    code = models.CharField(max_length = 10, null = True)
    language = models.CharField(max_length = 255, null = True)
    id = models.AutoField(primary_key = True, db_column = 'ID')

    class Meta:
        db_table = 'Languages'

    def __str__(self):
        return self.language + " (" + self.code + ")"

