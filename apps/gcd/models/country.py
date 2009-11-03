from django.db import models

class Country(models.Model):
    class Meta:
        app_label = 'gcd'

    class Admin:
        pass

    code = models.CharField(max_length=10)
    name = models.CharField(max_length=255)

    def __unicode__(self):
        return self.name

