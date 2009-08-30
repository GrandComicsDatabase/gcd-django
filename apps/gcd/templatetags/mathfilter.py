# -*- coding: utf-8 -*-
from django import template
import math

register = template.Library()

def sub_int(value_1, value_2):
    return int(value_1) - int(value_2)

def ceil(value):
    return math.ceil(float(value))

register.filter(sub_int)
register.filter(ceil)
