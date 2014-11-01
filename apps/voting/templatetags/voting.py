from django import template
from django.utils.safestring import mark_safe
from django.utils.html import conditional_escape as esc

register = template.Library()

def show_rank(option, user):
    rank = option.votes.get(voter=user).rank
    return rank

register.filter(show_rank)