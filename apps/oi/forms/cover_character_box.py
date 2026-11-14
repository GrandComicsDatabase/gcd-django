# -*- coding: utf-8 -*-
"""
Forms of the page marking the characters of a cover sequence on a cover.
"""
import math

from django import forms
from django.core.exceptions import ValidationError

from apps.oi.models import StoryCharacterRevision

# The three stored corners of a box, in affine coordinates of the front:
# x in 1/10000 of its width, y in 1/10000 of its height.
BOX_CORNER_FIELDS = ('top_left_x', 'top_left_y', 'top_right_x',
                     'top_right_y', 'bottom_left_x', 'bottom_left_y')

# The fields the script of the page writes when a box is drawn.
BOX_DRAWN_FIELDS = BOX_CORNER_FIELDS + ('scan_aspect',)

# The range of a signed SmallIntegerField, as the corners are stored.
SMALL_INTEGER_MIN = -32768
SMALL_INTEGER_MAX = 32767

# The largest value of a PositiveIntegerField, as scan_aspect is stored.
POSITIVE_INTEGER_MAX = 2147483647


def _corner_field():
    """
    A hidden corner coordinate, empty while the character is not marked.
    """
    too_far = 'A corner of the box is too far from the cover, draw it ' \
              'again.'
    return forms.IntegerField(
      required=False, min_value=SMALL_INTEGER_MIN,
      max_value=SMALL_INTEGER_MAX, widget=forms.HiddenInput,
      error_messages={'min_value': too_far, 'max_value': too_far,
                      'invalid': 'The box is not valid, draw it again.'})


class CoverCharacterBoxForm(forms.Form):
    """
    The box of one character appearance on the cover shown on the page.

    The corners and scan_aspect are written by the script of the page and
    are all empty while the character is not marked.  scan_date is written
    by the server: the last upload of the scan shown on the page, so that a
    scan replaced while the page was open is noticed before saving.
    """
    appearance = forms.ModelChoiceField(
      queryset=StoryCharacterRevision.objects.none(),
      widget=forms.HiddenInput)
    top_left_x = _corner_field()
    top_left_y = _corner_field()
    top_right_x = _corner_field()
    top_right_y = _corner_field()
    bottom_left_x = _corner_field()
    bottom_left_y = _corner_field()
    scan_aspect = forms.IntegerField(
      required=False, min_value=1, max_value=POSITIVE_INTEGER_MAX,
      widget=forms.HiddenInput,
      error_messages={
        name: 'The proportions of the scan are not valid, draw the box '
              'again.'
        for name in ('invalid', 'min_value', 'max_value')})
    scan_date = forms.DateTimeField(required=False, widget=forms.HiddenInput)

    def __init__(self, *args, appearances=None, cover=None, **kwargs):
        """
        Limits the rows to the given appearances of the cover sequence and
        keeps the cover the boxes are marked on.
        """
        super().__init__(*args, **kwargs)
        if appearances is not None:
            self.fields['appearance'].queryset = appearances
        self.cover = cover

    def clean(self):
        """
        Checks a drawn box: all its values are given, its centre is on
        the front, both sides are at least 1 long, the corners keep the
        order of the drawing, and it was drawn on the scan the cover has
        now.
        """
        cleaned_data = super().clean()
        if self.errors:
            return cleaned_data
        values = [cleaned_data.get(name) for name in BOX_DRAWN_FIELDS]
        if all(value is None for value in values):
            return cleaned_data
        if any(value is None for value in values):
            raise ValidationError('The box is incomplete, draw it again.')

        (top_left_x, top_left_y, top_right_x, top_right_y,
         bottom_left_x, bottom_left_y, scan_aspect) = values
        # The centre is halfway between the top right and the bottom left
        # corner.
        if not (0 <= top_right_x + bottom_left_x <= 20000
                and 0 <= top_right_y + bottom_left_y <= 20000):
            raise ValidationError(
              'The centre of the box is not on the cover, draw it again.')
        # The sides measured in x units: a y unit is scan_aspect / 10000 of
        # them on the scan.
        y_unit = scan_aspect / 10000
        across = (top_right_x - top_left_x,
                  (top_right_y - top_left_y) * y_unit)
        down = (bottom_left_x - top_left_x,
                (bottom_left_y - top_left_y) * y_unit)
        if math.hypot(*across) < 1 or math.hypot(*down) < 1:
            raise ValidationError(
              'A side of the box is shorter than 1, draw it again.')
        # Going from the top side to the left side turns clockwise on the
        # scan, as in any rectangle drawn on the turned cover.  The y unit
        # scales both terms, so the integers give the exact sign.
        if ((top_right_x - top_left_x) * (bottom_left_y - top_left_y)
                - (top_right_y - top_left_y) * (bottom_left_x - top_left_x)
                <= 0):
            raise ValidationError(
              'The corners of the box are not in order, draw it again.')
        if self.cover is not None and \
           cleaned_data.get('scan_date') != self.cover.last_upload:
            raise ValidationError(
              'The cover scan was replaced after this page was opened: check '
              'the box on the new scan and save again.')
        return cleaned_data


class BaseCoverCharacterBoxFormSet(forms.BaseFormSet):
    """
    One box form for each character appearance of the cover sequence.
    """
    def clean(self):
        """
        Checks that no appearance has more than one row.
        """
        if any(self.errors):
            return
        appearances = set()
        for form in self.forms:
            appearance = form.cleaned_data.get('appearance')
            if appearance is None:
                continue
            if appearance in appearances:
                raise ValidationError(
                  'A character is listed twice, reload the page.')
            appearances.add(appearance)


CoverCharacterBoxFormSet = forms.formset_factory(
  CoverCharacterBoxForm, formset=BaseCoverCharacterBoxFormSet,
  extra=0, can_delete=True)
