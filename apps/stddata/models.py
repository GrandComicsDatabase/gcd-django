from django.db import models

class CurrencyManager(models.Manager):
    def get_by_natural_key(self, code):
        return self.get(code=code)

class Currency(models.Model):
    """Class representing currency for prices."""
    class Meta:
        ordering = ('name',)
        verbose_name_plural = 'Currencies'

    objects = CurrencyManager()

    code = models.CharField(blank=False, null=False, max_length=3,
        unique=True)
    name = models.CharField(blank=False, null=False, max_length=100,
        db_index=True)
    is_decimal = models.BooleanField(default=True)

    def natural_key(self):
        return (self.code,)

    def __unicode__(self):
        return self.name

class Date(models.Model):
    """Class representing dates for gcd with the ability to store partial
    information. Blank field means that it's not important. Question marks mean
    that this part of a date is not known.
    Objects of this class should be deleted together with objects pointing to
    them."""
    class Meta:
        ordering = ('year','month','day',)
        verbose_name_plural = 'Dates'

    year = models.CharField(blank=True, null=False,  max_length=4,
        db_index=True)
    month = models.CharField(blank=True, null=False, max_length=2,
        db_index=True)
    day = models.CharField(blank=True, null=False, max_length=2,
        db_index=True)
    year_uncertain = models.BooleanField(default=False)
    month_uncertain = models.BooleanField(default=False)
    day_uncertain = models.BooleanField(default=False)

    #TODO it should be decided if complete validation should be done in __init__

    def __init__(self, year=None, month=None, day=None, year_uncertain=False,
                 month_uncertain=False, day_uncertain=False):
        self.year = year
        self.month = month
        self.day = day
        self.year_uncertain=year_uncertain or (year != None and '?' in year)
        self.month_uncertain=month_uncertain or (month != None and '?' in month)
        self.day_uncertain=day_uncertain or (day != None and '?' in day)

    def __unicode__(self):
        return self.year+u'-'+self.month+u'-'+self.day
