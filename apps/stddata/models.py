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
    name = models.CharField(blank=False, null=False, max_length=40,
        db_index=True)
    is_decimal = models.BooleanField(blank=False, default=True)

    def natural_key(self):
        """
        Note that this natural key is not technically guaranteed to be unique.
        However, it probably is and our use of the natural key concept is
        sufficiently limited that this is acceptable.
        """
        return (self.code,)

    def __unicode__(self):
        return self.name

class Date(models.Model):
    """Class representing dates for gcd. With the ability to store partial
    information - when one of the fields is empty, it means it is not known.
    Objects of this class should be deleted together with objects pointing to
    them."""
    class Meta:
        ordering = ('date',)
        verbose_name_plural = 'Dates'

    date = models.CharField(blank=False, max_length=10, db_index=True)
    is_year_uncertain = models.BooleanField(default=False)
    is_month_uncertain = models.BooleanField(default=False)
    is_day_uncertain = models.BooleanField(default=False)

    def __init__(self, year=None, month=None, day=None):
        self.date = u''
        if year:
            self.date += u'{0:?<4d}'.format(year)
        elif day or month:
            self.date += u'????'
        if month:
            self.date += u'-{0:02d}'.format(month)
        elif day:
            self.date += u'-??'
        if day:
            self.date += u'-{0:02d}'.format(day)

    def get_year(self):
        #TODO should return year part
        pass

    def get_month(self):
        #TODO should return month part
        pass

    def get_day(self):
        #TODO should return day part
        pass
