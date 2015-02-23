from django import template
from django.utils.safestring import mark_safe
from django.utils.html import conditional_escape as esc

register = template.Library()

def order_by(queryset, args):
    args = [x.strip() for x in args.split(',')]
    return queryset.order_by(*args)


def show_rank(option, user):
    rank = option.votes.get(voter=user).rank
    return rank

register.filter(order_by)
register.filter(show_rank)