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

    date = CharField(max_length=13, required=False)

    def __init__(self, *args, **kwargs):
        super(DateForm, self).__init__(*args, **kwargs)
        if self.instance:
            self.initial['date'] = unicode(self.instance)

    def clean_date(self):
        date = self.cleaned_data['date']
        if not date:
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

        if len(dparts) > 1:
            if not (1 <= len(dparts[1]) <= 3):
                raise verror
            month = dparts[1][:2]
            month_uncertain = dparts[1].endswith('?')

        if len(dparts) > 2:
            if not (1 <= len(dparts[2]) <= 3):
                raise verror
            day = dparts[2][:2]
            day_uncertain = dparts[2].endswith('?')

        self.instance.set(year=year, month=month, day=day,
                          year_uncertain=year_uncertain,
                          month_uncertain=month_uncertain,
                          day_uncertain=day_uncertain)
        return date
