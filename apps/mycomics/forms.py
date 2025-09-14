from django.forms import ModelForm, Form, ChoiceField, Select, RadioSelect, \
                         ValidationError
from apps.mycomics.models import Collector, Collection, CollectionItem, \
                                 Location, PurchaseLocation, ConditionGrade, \
                                 ReadingOrder, ReadingOrderItem
from apps.gcd.models.story import STORY_TYPES


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
        if not collections.filter(digital_used=True).exists():
            self.fields.pop('is_digital')
        if not collections.filter(rating_used=True).exists():
            self.fields.pop('rating')
        if not collections.filter(price_paid_used=True).exists():
            self.fields.pop('price_paid')
            self.fields.pop('price_paid_currency')
        if not collections.filter(market_value_used=True).exists():
            self.fields.pop('market_value')
            self.fields.pop('market_value_currency')
        if not collections.filter(sell_price_used=True).exists():
            self.fields.pop('sell_price')
            self.fields.pop('sell_price_currency')


class CollectionItemsForm(ModelForm):
    class Meta:
        model = CollectionItem
        exclude = ('collections', 'issue', 'acquisition_date', 'sell_date')
        widgets = {'own': Select(choices=((None, "---"),
                                          (True, "I own this comic."),
                                          (False, "I want this comic."))), }

    def set_initial_field_if_common(self, items, field_name):
        values = set(items.values_list(field_name, flat=True))
        if len(values) == 1:
            value = values.pop()
            if value is not None and field_name in self.fields:
                self.fields[field_name].initial = value

    def __init__(self, user, *args, **kwargs):
        collection = kwargs['collection']
        kwargs.pop('collection')
        items = kwargs['items']
        kwargs.pop('items')
        super(CollectionItemsForm, self).__init__(*args, **kwargs)
        self.set_initial_field_if_common(items, 'notes')
        self.fields.pop('keywords')

        if collection.condition_used is not True:
            self.fields.pop('grade')
        else:
            self.fields['grade'].queryset = ConditionGrade.objects.filter(
              scale=user.grade_system)
            self.set_initial_field_if_common(items, 'grade')
        if collection.location_used is not True:
            self.fields.pop('location')
        else:
            self.fields['location'].queryset = \
                        Location.objects.filter(user=user)
            self.set_initial_field_if_common(items, 'location')
        if collection.purchase_location_used is not True:
            self.fields.pop('purchase_location')
        else:
            self.fields['purchase_location'].queryset = \
                        PurchaseLocation.objects.filter(user=user)
            self.set_initial_field_if_common(items, 'purchase_location')
        if collection.own_used is not True:
            self.fields.pop('own')
        else:
            self.set_initial_field_if_common(items, 'own')
        if collection.was_read_used is not True:
            self.fields.pop('was_read')
        else:
            self.set_initial_field_if_common(items, 'was_read')
        if collection.for_sale_used is not True:
            self.fields.pop('for_sale')
        else:
            self.set_initial_field_if_common(items, 'for_sale')
        if collection.signed_used is not True:
            self.fields.pop('signed')
        else:
            self.set_initial_field_if_common(items, 'signed')
        if collection.digital_used is not True:
            self.fields.pop('is_digital')
        else:
            self.set_initial_field_if_common(items, 'is_digital')
        if collection.rating_used is not True:
            self.fields.pop('rating')
        else:
            self.set_initial_field_if_common(items, 'rating')
        if collection.price_paid_used is not True:
            self.fields.pop('price_paid')
            self.fields.pop('price_paid_currency')
        else:
            self.set_initial_field_if_common(items, 'price_paid')
            self.set_initial_field_if_common(items, 'price_paid_currency')
        if collection.market_value_used is not True:
            self.fields.pop('market_value')
            self.fields.pop('market_value_currency')
        else:
            self.set_initial_field_if_common(items, 'market_value')
            self.set_initial_field_if_common(items, 'market_value_currency')
        if collection.sell_price_used is not True:
            self.fields.pop('sell_price')
            self.fields.pop('sell_price_currency')
        else:
            self.set_initial_field_if_common(items, 'sell_price')
            self.set_initial_field_if_common(items, 'sell_price_currency')


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


class ReadingOrderForm(ModelForm):
    class Meta:
        model = ReadingOrder
        exclude = ('collector',)


class ReadingOrderItemForm(ModelForm):
    class Meta:
        model = ReadingOrderItem
        exclude = ('reading_order', 'issue',)

    def __init__(self, *args, **kwargs):
        super(ReadingOrderItemForm, self).__init__(*args, **kwargs)
        issue = kwargs['instance'].issue
        choices = [(story.id, story)
                   for story in issue.active_stories().filter(
                     type__id=STORY_TYPES['comic story'])]
        self.fields['story'].choices = [(None, "---")] + choices
