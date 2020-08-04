# -*- coding: utf-8 -*-
from django.core.exceptions import ValidationError
from django.forms import ModelForm, CharField
from apps.stddata.models import Date
from django.utils.translation import ugettext as _


class DateForm(ModelForm):
    class Meta:
        model = Date
        exclude = ('year', 'month', 'day', 'year_uncertain', 'month_uncertain',
                   'day_uncertain')

    date = CharField(max_length=13, required=False,
                     help_text='Enter date as YYYY-MM-DD. A ? can be used in '
                               'each part to indicate uncertainty.')

    def __init__(self, *args, **kwargs):
        super(DateForm, self).__init__(*args, **kwargs)
        if self.instance:
            self.initial['date'] = str(self.instance)

    def clean_date(self):
        date = self.cleaned_data['date']
        if not date:
            if self.instance:
                self.instance.set(year='', month='', day='',
                                  year_uncertain=False,
                                  month_uncertain=False,
                                  day_uncertain=False,
                                  empty=True)
            return None
        dparts = date.split('-')

        verror = ValidationError(_('Date given in a wrong format'))
        #We accept entering only year or only year and month.
        if len(dparts) < 1 or len(dparts) > 3:
            raise verror
        if not self.instance:
            self.instance = Date()
        month = day = ''
        month_uncertain = day_uncertain = None

        #The general format is YYYY-MM-DD but each part can end with '?'
        if not (4 <= len(dparts[0]) <= 5):
            raise verror
        year = dparts[0][:4]
        year_uncertain = dparts[0].endswith('?')

        if len(year.strip('?')) > 0:
            try:
                int(year.strip('?'))
            except:
                raise verror

        if len(dparts) > 1:
            if not (1 <= len(dparts[1]) <= 3):
                raise verror
            month = (dparts[1][:2]).strip('?')
            month_uncertain = dparts[1].endswith('?')

            if len(month) > 0:
                try:
                    int(month)
                except:
                    raise verror
                if not (1 <= int(month) <=12):
                    raise ValidationError(_('Month is not between 1 and 12.'))

        if len(dparts) > 2:
            if not (1 <= len(dparts[2]) <= 3):
                raise verror
            day = (dparts[2][:2]).strip('?')
            day_uncertain = dparts[2].endswith('?')
            if len(day) > 0:
                try:
                    int(day)
                except:
                    raise verror
                if not (1 <= int(day) <=31):
                    raise ValidationError(_('Day is not between 1 and 31.'))

        self.instance.set(year=year, month=month, day=day,
                          year_uncertain=year_uncertain,
                          month_uncertain=month_uncertain,
                          day_uncertain=day_uncertain, empty=True)
        return date
