from django.forms import ModelForm, Form, ChoiceField, Select, RadioSelect, \
                         ValidationError
from apps.mycomics.models import Collector, Collection, CollectionItem, \
                                 Location, PurchaseLocation, ConditionGrade


# TODO: Should not be reaching into OI form internals and importing an
#       internal (leading underscore) function.  Should move the function
#       if we need it more broadly.
from apps.oi.forms.support import _clean_keywords


class CollectorForm(ModelForm):
    class Meta:
        model = Collector
        exclude = ('user',)

    def __init__(self, collector, *args, **kwargs):
        kwargs['instance'] = collector
        super(CollectorForm, self).__init__(*args, **kwargs)
        collections = Collection.objects.filter(collector=collector)
        self.fields['default_have_collection'].queryset = collections
        self.fields['default_want_collection'].queryset = collections


class CollectionForm(ModelForm):
    class Meta:
        model = Collection
        exclude = ('collector',)
        widgets = {'own_default': RadioSelect(
          choices=((None, "---"),
                   (True, "I own this comic."),
                   (False, "I want this comic."))),
                   'for_sale_default': RadioSelect(
          choices=((True, "comic is for sale"),
                   (False, "comic is not for sale"))), }

    def __init__(self, *args, **kwargs):
        super(CollectionForm, self).__init__(*args, **kwargs)
        instance = kwargs['instance']
        self.fields['location_default'].queryset = \
            instance.collector.location_set.all()
        self.fields['purchase_location_default'].queryset = \
            instance.collector.purchaselocation_set.all()

    def clean(self):
        cd = self.cleaned_data
        if cd['own_default'] is not None and cd['own_used'] is False:
            raise ValidationError('To use "Default ownership status" the '
                                  '"Show own/want status" needs to be '
                                  'activated.')

        if cd['for_sale_default'] is True and cd['for_sale_used'] is False:
            raise ValidationError('To use "Default for sale status" the '
                                  '"Show for sale status" needs to be '
                                  'activated.')

        if cd['location_default'] is not None and cd['location_used'] is False:
            raise ValidationError('To use "Default location" the '
                                  '"Show location" needs to be '
                                  'activated.')

        if cd['purchase_location_default'] is not None and \
           cd['purchase_location_used'] is False:
            raise ValidationError('To use "Default purchase location" the '
                                  '"Show purchase location" needs to be '
                                  'activated.')


class LocationForm(ModelForm):
    class Meta:
        model = Location
        exclude = ('user',)


class PurchaseLocationForm(ModelForm):
    class Meta:
        model = PurchaseLocation
        exclude = ('user',)


class CollectionItemForm(ModelForm):
    class Meta:
        model = CollectionItem
        exclude = ('collections', 'issue', 'acquisition_date', 'sell_date')
        widgets = {'own': Select(choices=((None, "---"),
                                          (True, "I own this comic."),
                                          (False, "I want this comic."))), }

    def __init__(self, user, *args, **kwargs):
        super(CollectionItemForm, self).__init__(*args, **kwargs)
        instance = kwargs['instance']
        # This generates a query for each check. If problematic these can be
        # avoided by going to python for the checks on an evaluated collections
        collections = instance.collections.all()
        if not collections.filter(condition_used=True).exists():
            self.fields.pop('grade')
        else:
            self.fields['grade'].queryset = ConditionGrade.objects.filter(
                scale=user.grade_system)
        if not collections.filter(location_used=True).exists():
            self.fields.pop('location')
        else:
            self.fields['location'].queryset = \
                        Location.objects.filter(user=user)
        if not collections.filter(purchase_location_used=True).exists():
            self.fields.pop('purchase_location')
        else:
            self.fields['purchase_location'].queryset = \
                        PurchaseLocation.objects.filter(user=user)
        if not collections.filter(own_used=True).exists():
            self.fields.pop('own')
        if not collections.filter(was_read_used=True).exists():
            self.fields.pop('was_read')
        if not collections.filter(for_sale_used=True).exists():
            self.fields.pop('for_sale')
        if not collections.filter(signed_used=True).exists():
            self.fields.pop('signed')
        if not collections.filter(price_paid_used=True).exists():
            self.fields.pop('price_paid')
            self.fields.pop('price_paid_currency')
        if not collections.filter(market_value_used=True).exists():
            self.fields.pop('market_value')
            self.fields.pop('market_value_currency')
        if not collections.filter(sell_price_used=True).exists():
            self.fields.pop('sell_price')
            self.fields.pop('sell_price_currency')

    def clean_keywords(self):
        return _clean_keywords(self.cleaned_data)


class CollectionSelectForm(Form):
    collection = ChoiceField()

    def __init__(self, collector, excluded_collections=None, *args, **kwargs):
        super(CollectionSelectForm, self).__init__(*args, **kwargs)
        choices = [(collection.id, collection)
                   for collection in collector.ordered_collections()]
        if excluded_collections:
            choices[:] = [choice for choice in choices
                          if choice[1] not in excluded_collections]
        self.fields['collection'].choices = choices
