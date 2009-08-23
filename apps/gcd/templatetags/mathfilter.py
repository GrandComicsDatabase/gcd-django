# -*- coding: utf-8 -*-
from django import template

register = template.Library()

def sub_int(value_1, value_2):
    return int(value_1) - int(value_2)

register.filter(sub_int)
