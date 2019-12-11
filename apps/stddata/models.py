from django.db import models


class CountryManager(models.Manager):
    def get_by_natural_key(self, code):
        return self.get(code=code)


class Country(models.Model):
    class Meta:
        ordering = ('name',)
        verbose_name_plural = 'Countries'

    objects = CountryManager()

    code = models.CharField(max_length=10, unique=True)
    name = models.CharField(max_length=255, db_index=True)

    def natural_key(self):
        """
        Note that this natural key is not technically guaranteed to be unique.
        However, it probably is and our use of the natural key concept is
        sufficiently limited that this is acceptable.
        """
        return (self.code,)

    def __str__(self):
        return self.name


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

    def __str__(self):
        return str(self.code) + " - " + str(self.name)


class Date(models.Model):
    """Class representing dates for gcd with the ability to store partial
    information. Blank field means that it's not important. Question marks mean
    that this part of a date is not known.
    Objects of this class should be deleted together with objects pointing to
    them."""
    class Meta:
        ordering = ('year', 'month', 'day',)
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

    def set(self, year=None, month=None, day=None, year_uncertain=False,
            month_uncertain=False, day_uncertain=False, empty=False):
        self.year = year
        self.month = month
        self.day = day
        self.year_uncertain = year_uncertain or (not year and not empty) \
                                             or (year is not None
                                                 and '?' in year)
        self.month_uncertain = month_uncertain or (not month and not empty) \
                                               or (month is not None and
                                                   '?' in month)
        self.day_uncertain = day_uncertain or (not day and not empty) \
                                           or (day is not None and '?' in day)

    def __str__(self):
        year = self.year or ''
        if self.year_uncertain and '?' not in year:
            year += '?'
        month = self.month or ''
        if self.month_uncertain and '?' not in month:
            month += '?'
        day = self.day or ''
        if self.day_uncertain and '?' not in day:
            day += '?'
        if day:
            return year+'-'+month+'-'+day
        elif month:
            return year+'-'+month
        elif year:
            return year
        else:
            return ''


class LanguageManager(models.Manager):
    def get_by_natural_key(self, code):
        return self.get(code=code)


class Language(models.Model):
    class Meta:
        ordering = ('name',)

    objects = LanguageManager()

    code = models.CharField(max_length=10, unique=True)
    name = models.CharField(max_length=255, db_index=True)
    native_name = models.CharField(max_length=255, blank=True)

    def natural_key(self):
        """
        Note that this natural key is not technically guaranteed to be unique.
        However, it probably is and our use of the natural key concept is
        sufficiently limited that this is acceptable.
        """
        return (self.code,)

    def get_native_name(self):
        if self.native_name:
            return self.native_name
        else:
            return self.name

    def __str__(self):
        return self.name


class Script(models.Model):
    LATIN_PK = 37
    class Meta:
        ordering = ('name',)

    code = models.CharField(max_length=4, unique=True)
    number = models.PositiveSmallIntegerField(unique=True)
    name = models.CharField(max_length=64)

    def __unicode__(self):
        return self.name
