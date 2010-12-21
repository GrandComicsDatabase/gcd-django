from django.db import models

class CountryManager(models.Manager):
    def get_by_natural_key(self, code):
        return self.get(code=code)

class Country(models.Model):
    class Meta:
        app_label = 'gcd'
        ordering = ('name',)
        verbose_name_plural = 'Countries'

    objects = CountryManager()

    code = models.CharField(max_length=10)
    name = models.CharField(max_length=255)

    def natural_key(self):
        """
        Note that this natural key is not technically guaranteed to be unique.
        However, it probably is and our use of the natural key concept is
        sufficiently limited that this is acceptable.
        """
        return self.get(code=code)

    def __unicode__(self):
        return self.name

