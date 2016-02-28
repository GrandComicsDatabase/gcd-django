# -*- coding: utf-8 -*-

import re
from stdnum import isbn

from apps.gcd.models import CountStats


def update_count(field, delta, language=None, country=None):
    '''
    Forwards to CountStats.objects.update_count() until no longer needed.
    '''
    CountStats.objects.update_count(field, delta,
                                    language=language, country=country)


def validated_isbn(entered_isbn):
    '''
    returns ISBN10 or ISBN13 if valid ISBN, empty string otherwiese
    '''
    isbns = entered_isbn.split(';')
    valid_isbns = True
    for num in isbns:
        valid_isbns &= isbn.is_valid(num)
    if valid_isbns and len(isbns) == 1:
        return isbn.compact(isbns[0])
    elif valid_isbns and len(isbns) == 2:
        compacted_isbns = [isbn.compact(isbn.to_isbn13(i)) for i in isbns]
        # if two ISBNs it must be corresponding ISBN10 and ISBN13
        if compacted_isbns[0] == compacted_isbns[1]:
            # always store ISBN13 if both exist
            return compacted_isbns[0]
    return ''


def remove_leading_article(name):
    '''
    returns the name with the leading article (separated by "'"
    or whitespace) removed
    '''
    article_match = re.match(r"\S?\w+['\s]\s*(.*)$", name, re.UNICODE)
    if article_match:
        return article_match.group(1)
    else:
        return name


def on_sale_date_as_string(issue):
    date = u''
    if issue.year_on_sale:
        date += u'{0:?<4d}'.format(issue.year_on_sale)
    elif issue.day_on_sale or issue.month_on_sale:
        date += u'????'
    if issue.month_on_sale:
        date += u'-{0:02d}'.format(issue.month_on_sale)
    elif issue.day_on_sale:
        date += u'-??'
    if issue.day_on_sale:
        date += u'-{0:02d}'.format(issue.day_on_sale)
    return date


def on_sale_date_fields(on_sale_date):
    year_string = on_sale_date[:4].strip('?')
    if year_string:
        year = int(year_string)
    else:
        year = None
    month = None
    day = None
    if len(on_sale_date) > 4:
        month_string = on_sale_date[5:7].strip('?')
        if month_string:
            month = int(month_string)
        if len(on_sale_date) > 7:
            day = int(on_sale_date[8:10].strip('?'))
    return year, month, day


def get_keywords(source):
    return u'; '.join(unicode(i) for i in source.keywords.all()
                                                .order_by('name'))


def save_keywords(revision, source):
    if revision.keywords:
        source.keywords.set(*[x.strip() for x in revision.keywords.split(';')])
        revision.keywords = u'; '.join(
            unicode(i) for i in source.keywords.all().order_by('name'))
        revision.save()
    else:
        source.keywords.set()


def get_brand_use_field_list():
    return ['year_began', 'year_began_uncertain',
            'year_ended', 'year_ended_uncertain', 'notes']


def get_series_field_list():
    return ['name', 'leading_article', 'imprint', 'format', 'color',
            'dimensions', 'paper_stock', 'binding', 'publishing_format',
            'publication_type', 'is_singleton', 'year_began',
            'year_began_uncertain', 'year_ended', 'year_ended_uncertain',
            'is_current', 'country', 'language', 'has_barcode',
            'has_indicia_frequency', 'has_isbn', 'has_issue_title',
            'has_volume', 'has_rating', 'is_comics_publication',
            'tracking_notes', 'notes', 'keywords']


def get_series_bond_field_list():
    return ['bond_type', 'notes']


def get_issue_field_list():
    return ['number', 'title', 'no_title',
            'volume', 'no_volume', 'display_volume_with_number',
            'indicia_publisher', 'indicia_pub_not_printed',
            'brand', 'no_brand', 'publication_date', 'year_on_sale',
            'month_on_sale', 'day_on_sale', 'on_sale_date_uncertain',
            'key_date', 'indicia_frequency', 'no_indicia_frequency', 'price',
            'page_count', 'page_count_uncertain', 'editing', 'no_editing',
            'isbn', 'no_isbn', 'barcode', 'no_barcode', 'rating', 'no_rating',
            'notes', 'keywords']


def get_story_field_list():
    return ['sequence_number', 'title', 'title_inferred', 'type',
            'feature', 'genre', 'job_number',
            'script', 'no_script', 'pencils', 'no_pencils', 'inks',
            'no_inks', 'colors', 'no_colors', 'letters', 'no_letters',
            'editing', 'no_editing', 'page_count', 'page_count_uncertain',
            'characters', 'synopsis', 'reprint_notes', 'notes', 'keywords']


def get_reprint_field_list():
    return ['notes']
