# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.conf import settings
from django import forms
from django.utils.safestring import mark_safe
from django.utils.encoding import force_unicode
from django.utils.html import escape, conditional_escape
from django.forms.widgets import TextInput

from apps.gcd.models import Brand, SourceType
from apps.gcd.templatetags.credits import format_page_count


CREATOR_CREDIT_HELP = (
    'The %s and similar credits for this sequence, where multiple '
    'credits are separated with semicolons. If the credit applies to '
    'this sequence type but the creator is unknown, enter a question mark.')

NO_CREATOR_CREDIT_HELP = (
    'Check this box if %s does not apply to this sequence%s and leave the '
    '%s field blank. ')

GENERIC_ERROR_MESSAGE = (
    'Please correct the field errors.  Scroll down to see the specific error '
    'message(s) next to each field.')

DOC_URL = 'http://docs.comics.org/wiki/'

PUBLISHER_HELP_LINKS = {
    'name': 'Publisher_Name',
    'year_began': 'Years_of_Publication',
    'year_ended': 'Years_of_Publication',
    'year_began_uncertain': 'Years_of_Publication',
    'year_ended_uncertain': 'Years_of_Publication',
    'country': 'Country',
    'url': 'URL',
    'notes': 'Notes_%28on_Publisher_Screen%29',
    'keywords': 'Keywords',
    'comments': 'Comments '
}

BRAND_HELP_LINKS = {
    'name': 'Brand',
    'year_began': 'Years_of_Use_%28Brand%29',
    'year_ended': 'Years_of_Use_%28Brand%29',
    'year_began_uncertain': 'Years_of_Use_%28Brand%29',
    'year_ended_uncertain': 'Years_of_Use_%28Brand%29',
    'url': 'URL_%28Brand%29',
    'notes': 'Notes_%28Brand%29',
    'keywords': 'Keywords',
    'comments': 'Comments '
}

CREATOR_HELP_LINKS = {
    'gcd_official_name': 'Credits',
    'date': 'Year_/_Month_/_Date_Fields',
    'birth_country': 'Country_/_Province_/_City_Fields',
    'death_country': 'Country_/_Province_/_City_Fields',
    'birth_province': 'Country_/_Province_/_City_Fields',
    'death_province': 'Country_/_Province_/_City_Fields',
    'birth_city': 'Country_/_Province_/_City_Fields',
    'death_city': 'Country_/_Province_/_City_Fields',
    'bio': 'Biography',
    'whos_who': 'Biography',
    'notes': 'Notes_(Creators)'
}

CREATOR_ARTINFLUENCE_HELP_LINKS = {
    'influence_name': 'Influence_Name',
    'influence_link': 'Influence_Name',
    'notes': 'Notes_(Creator_Influences)',
}

CREATOR_AWARD_HELP_LINKS = {
    'award_name': 'Award_name',
    'award_year': 'Year_fields',
    'notes': 'Notes_(Creator_Awards)'
}

CREATOR_DEGREE_HELP_LINKS = {
    'school': 'School',
    'degree': 'Degree',
    'degree_year': 'Year_fields',
    'notes': 'Notes_(Creator_Degrees)'
}

CREATOR_MEMBERSHIP_HELP_LINKS = {
    'organization_name': 'Organization_name',
    'membership_type': 'Membership_type',
    'membership_year_began': 'Year_fields',
    'membership_year_ended': 'Year_fields',
    'notes': 'Notes_(Creator_Memberships)'
}

CREATOR_NONCOMICWORK_HELP_LINKS = {
    'work_type': 'Work_Type',
    'publication_title': 'Publication_Title',
    'employer_name': 'Employer_Name',
    'work_title': 'Work_Title',
    'work_role': 'Work_Role',
    'notes': 'Work_Notes_(Non_Comic_Work)',
}

CREATOR_SCHOOL_HELP_LINKS = {
    'school': 'School',
    'school_year_began': 'Year_fields',
    'school_year_ended': 'Year_fields',
    'notes': 'Notes_(Creator_Schools)'
}

INDICIA_PUBLISHER_HELP_LINKS = {
    'name': 'Indicia_Publisher',
    'year_began': 'Years_of_Use_%28Indicia_publisher%29',
    'year_ended': 'Years_of_Use_%28Indicia_publisher%29',
    'year_began_uncertain': 'Years_of_Use_%28Indicia_publisher%29',
    'year_ended_uncertain': 'Years_of_Use_%28Indicia_publisher%29',
    'is_surrogate': 'Surrogate',
    'country': 'Country_%28Indicia_publisher%29',
    'url': 'URL_%28Indicia_publisher%29',
    'notes': 'Notes_%28Indicia_publisher%29',
    'keywords': 'Keywords',
    'comments': 'Comments '
}

ISSUE_HELP_LINKS = {
    'number': 'Issue_Numbers',
    'variant_name': 'Variant_Issues',
    'title': 'Issue_Title',
    'no_title': 'Issue_Title',
    'volume': 'Volume',
    'no_volume': 'Volume',
    'display_volume_with_number': 'Display_Volume_with_Issue_Number',
    'publication_date': 'Published_Date',
    'indicia_frequency': 'Indicia_frequency',
    'no_indicia_frequency': 'Indicia_frequency',
    'key_date': 'Keydate',
    'on_sale_date': 'On-sale_date',
    'year_on_sale': 'On-sale_date',
    'month_on_sale': 'On-sale_date',
    'day_on_sale': 'On-sale_date',
    'indicia_publisher': 'Indicia_publisher',
    'indicia_pub_not_printed': 'Indicia_publisher',
    'brand': 'Brand',
    'no_brand': 'Brand',
    'price': 'Cover_Price',
    'page_count': 'Page_Count',
    'page_count_uncertain': 'Page_Count',
    'editing': 'Editing',
    'no_editing': 'Editing',
    'isbn': 'ISBN',
    'no_isbn': 'ISBN',
    'barcode': 'Barcode',
    'no_barcode': 'Barcode',
    'rating': "Publisher's_Age_Guidelines",
    'no_rating': "Publisher's_Age_Guidelines",
    'notes': 'Notes_%28issue%29',
    'keywords': 'Keywords',
    'comments': 'Comments'
}

SEQUENCE_HELP_LINKS = {
    'type': 'Type',
    'title': 'Title',
    'title_inferred': 'Title',
    'feature': 'Feature',
    'page_count': 'Page_Count',
    'page_count_uncertain': 'Page_Count',
    'genre': 'Genre',
    'script': 'Script',
    'no_script': 'Script',
    'pencils': 'Pencils',
    'no_pencils': 'Pencils',
    'inks': 'Inks',
    'no_inks': 'Inks',
    'colors': 'Colors',
    'no_colors': 'Colors',
    'letters': 'Letters',
    'no_letters': 'Letters',
    'editing': 'Editing',
    'no_editing': 'Editing',
    'characters': 'Character_Appearances',
    'synopsis': 'Synopsis',
    'job_number': 'Job_Number',
    'reprint_notes': 'Reprints',
    'notes': 'Notes',
    'keywords': 'Keywords',
    'comments': 'Comments'
}

SERIES_HELP_LINKS = {
    'name': 'Book_Name',
    'leading_article': 'Book_Name',
    'year_began': 'Years_of_Publication',
    'year_began_uncertain': 'Years_of_Publication',
    'year_ended': 'Years_of_Publication',
    'year_ended_uncertain': 'Years_of_Publication',
    'is_current': 'Years_of_Publication',
    'country': 'Country',
    'language': 'Language',
    'tracking_notes': 'Tracking',
    'notes': 'Series_Notes',
    'keywords': 'Keywords',
    'format': 'Format',
    'color': 'Format',
    'dimensions': 'Format',
    'paper_stock': 'Format',
    'binding': 'Format',
    'publishing_format': 'Format',
    'is_comics_publication': 'Comics_Publication',
    'is_singleton': 'Is_Singleton',
    'publication_type': 'Publication_Type',
    'has_barcode': 'Barcode',
    'has_indicia_frequency': 'Indicia_frequency',
    'has_isbn': 'ISBN',
    'has_issue_title': 'Issue_Title',
    'has_rating': "Publisher's_Age_Guidelines",
    'has_volume': 'Volume',
    'comments': 'Comments'
}

CREATOR_HELP_TEXTS = {
    'bio':
        "A short biography (1-4 paragraphs) noting highlights of the career "
        "of the creator, which might include a list of characters created.",
    'whos_who':
         "Link to the old Who’s Who, if available.",
}

CREATOR_MEMBERSHIP_HELP_TEXTS = {
    'organization_name':
        "Name of society or other organization, related to an artistic "
        "profession, that the creator holds or held a membership in.",
}

CREATOR_ARTINFLUENCE_HELP_TEXTS = {
    'influence_name':
        "Name of an artistic influence of the creator. We only document "
        "influences self-identified by the creator.",
    'influence_link':
        "If the influence is a creator in our database, link to the creator "
        "record instead of entering the name above.",
}

CREATOR_NONCOMICWORK_HELP_TEXTS = {
    'publication_title':
        "Record the publication title if a physical publication, the title of "
        "a play, movie, television, radio, or live show series, the name or "
        "client of an advertising campaign, name of a fine art piece or "
        "internet site, or feature of a web comic.",
    'employer_name':
        "The name of the entity that paid for the work.",
    'work_title':
        "The title of the individual work, such as the title of an article "
        "or web comic story, episode of a show, illustration in an "
        "ad campaign, or blog entry.",
    'work_years':
        "The years of the work. Separate by ';', use year-year for ranges",
    'work_urls':
        "Links to either the work or more information about the work, such as"
        " the person's entry in the IMDb, a WorldCat search for a creator, or"
        " a link to a web comic site. One URL per line."
}

PUBLISHER_HELP_TEXTS = {
    'year_began':
        'The first year in which the publisher was active.',
    'year_ended':
        'The last year in which the publisher was active. '
        'Leave blank if the publisher is still active.',
    'year_began_uncertain':
        'Check if you are not certain of the beginning year.',
    'year_ended_uncertain':
        'Check if you are not certain of the ending year, or if you '
        'are not certain whether the publisher is still active.',
    'notes':
        "Anything that doesn't fit in other fields.  These notes are part "
        "of the regular display.",
    'keywords':
        'Significant objects, locations, or themes (NOT characters) depicted '
        'in the content, such as "Phantom Zone", "red kryptonite", "Vietnam". '
        'or "time travel".  Multiple entries are to be separated by '
        'semi-colons.',
    'url':
        'The official web site of the publisher.  Must include "http://" or '
        '"https://", for example "https://www.example.com" not '
        '"www.example.com"',
}

SERIES_HELP_TEXTS = {
    'name':
        'Series name as it appears in the indicia (or cover only if there '
        'is no indicia).',
    'leading_article':
        'Check if the name starts with an article.',
    'color':
        'What sort of color is used in the printing.  Common '
        'values include Color, Four Color, Painted, '
        'Two Color, Duotone, and Black and White. '
        'This may change over the life of the series.',
    'dimensions':
        'The size of the comic, such as Standard Golden Age U.S.'
        '(or Silver or Modern), A4, A5, Tabloid, Digest, 8.5" x 11", '
        '21cm x 28cm.  This may change over the life of the series.',
    'paper_stock':
        'Type of paper used for the interior pages, such as '
        'Newsprint, Glossy, Bond, Mando, Baxter, etc.  Information '
        'about cover paper stock may also be noted. This may change '
        'over the life of the series.',
    'binding':
        'Binding type, such as Saddle-stitched (stapled in the spine, '
        'like most U.S. monthly comics), stapled (from front cover '
        'through to back cover, near the spine), Bound, Squarebound, '
        'Perfect Bound, Hardcover, Trade Paperback, Mass Market '
        'Paperback. This may change over the life of the series.',
    'publishing_format':
        'Indicates the nature of this publication as a series (or '
        'non-series), such as Ongoing Series, Limited Series, '
        'Miniseries, Maxiseries, One-Shot, Graphic Novel.  '
        '"Was Ongoing Series" may be used if it has ceased '
        'publication.',
    'publication_type':
        "Describe the publication format for user reference.",
    'year_began':
        'Year first issue published.',
    'year_ended':
        'Leave blank if the series is still producing new issues.',
    'year_began_uncertain':
        'Check if you are not certain of the beginning year.',
    'year_ended_uncertain':
        'Check if you are not certain of the ending year.',
    'is_current':
        'Check if new issues are still being produced for this '
        'series. Only uncheck after the last issue is approved '
        'and in our database.',
    'tracking_notes':
        'Field to track numbering from one series to another.',
    'has_barcode':
        "Barcodes are present for issues of this series.",
    'has_indicia_frequency':
        "Indicia frequencies are present for issues of this series.",
    'has_isbn':
        "ISBNs are present for issues of this series.",
    'has_issue_title':
        "Titles are present for issues of this series.",
    'has_volume':
        "Volume numbers are present for issues of this series.",
    'has_rating':
        "Publisher's age guidelines are present for issues of this "
        "series.",
    'is_comics_publication':
        "Publications in this series are mostly comics publications.",
    'is_singleton':
        "Series consists of one and only one issue by design. "
        "Note that for series adds an issue with no issue number will"
        " be created upon approval.",
    'keywords':
        'Significant objects, locations, or themes (NOT characters) '
        'depicted in the content, such as "Phantom Zone", '
        '"red kryptonite", "Vietnam". or "time travel".  Multiple '
        'entries are to be separated by semi-colons.',
}

ISSUE_LABELS = {
    'indicia_publisher': 'Indicia/colophon publisher',
    'indicia_pub_not_printed': 'Indicia/colophon pub. not printed',
    'isbn': 'ISBN',
    'no_isbn': 'No ISBN',
    'rating': "Publisher's age guidelines",
    'no_rating': "No publisher's age guidelines",
    'brand': 'Brand emblem',
    'no_brand': 'No brand emblem',
}

ISSUE_HELP_TEXTS = {
    'number':
        'The issue number (or other label) as it appears in the indicia. '
        'If there is no indicia the cover number may be used. '
        'Series that number by year (mostly European series) should write '
        'the year after a slash: "4/2009" for issue #4 in publication '
        'year 2009.  Place brackets around an issue number if there is an '
        'indicia but the number does not appear in it.  Use "[nn]" or the '
        'next logical number in brackets like "[2]" if '
        'there is no number printed anywhere on the issue.',

    'title':
        'The title of the issue. Refer to the wiki for the '
        'cases when an issue can have a title.',
    'no_title':
        'Check if there is no title.',

    'volume':
        'Volume number (only if listed on the item). For collections '
        'or other items that only have a volume or book number, '
        'put the same number in both this field and the issue number '
        'and do *not* check "Display volume with number". ',
    'no_volume':
        'If there is no volume, check this box and leave the volume field '
        'blank. This lets us distinguish between confirmed no-volume '
        'issues and issues indexed before we started tracking volume.',
    'display_volume_with_number':
        'Check to cause the site to display the volume as part of the '
        'issue number.  For example with a volume of "2" and an issue '
        'number of "1", checking this box will display "v2#1" instead '
        'of just "1" in the status grids and issues lists for the series.',
    'publication_date':
        'The publicaton date as printed on the comic, except with the '
        'name of the month (if any) spelled out.  Any part of the date '
        'that is not printed on the comic but is known should be put '
        'in square brackets, such as "[January] 2009". ',
    'key_date':
        'Keydate is a translation of the publication date, possibly '
        'supplemented by the on-sale date, into numeric '
        'form for chronological ordering and searches. It is in the '
        'format YYYY-MM-DD, where the parts of the date not given are '
        'filled up with 00. For comics dated only by year, the keydate '
        'is YYYY-00-00. For comics only dated by month the day (DD) '
        'is 00. For the month (MM) on quarterlies, use 04 for Spring, '
        '07 for Summer, 10 for Fall and 01 or 12 for Winter (in the '
        'northern hemisphere, shift accordingly in the southern).',
    'on_sale_date_uncertain':
        'The uncertain flag only relates to the actual entered data, '
        'therefore if e.g. no day is entered, but the month and year are '
        'certain, the uncertain flag is not set.',
    'indicia_frequency':
        'If relevant, the frequency of publication specified in the '
        'indicia, which may not match the actual publication schedule. '
        'This is most often found on ongoing magazine series.',
    'no_indicia_frequency':
        'Check this box if there is no publication frequency printed '
        'on the comic.',

    'price':
        'Price in ISO format ("0.50 USD" for 50 cents (U.S.), '
        '"2.99 CAD" for $2.99 Canadian.  Use a format like '
        '"2/6 [0-2-6 GBP]" for pre-decimal British pounds. '
        'Use "0.00 FREE" for free issues. '
        'Separate multiple prices with a semicolon.  Use parentheses '
        'after the currency code for notes: "2.99 USD; 3.99 USD '
        '(newsstand)" Use country codes after the currency code if more '
        'than one price uses the same currency: '
        '"3.99 EUR DE; 3.50 EUR AT; 1.50 EUR FR"',
    'page_count':
        "Count of all pages in the issue, including the covers but "
        "excluding dust jackets and inserts.  A single sheet of paper "
        "folded in half would count as 4 pages.",
    'page_count_uncertain':
        "Check if you do not know or aren't sure about the page count.",

    'editing':
        'The editor and any similar credits for the whole issue.  If no '
        'overall editor is known put a question mark in the field.',
    'no_editing':
        'Check if there is no editor or similar credit (such as '
        'publisher) for the issue as a whole.',
    'keywords':
        'Significant objects, locations, or themes (NOT characters) '
        'depicted in the content, such as "Phantom Zone", '
        '"red kryptonite", "Vietnam". or "time travel".  Multiple '
        'entries are to be separated by semi-colons.',

    'indicia_publisher':
        'The exact corporation listed as the publisher in the '
        'indicia or colophon, if any.  If there is none, the copyright '
        'holder (if any) may be used, with a comment in the notes field',
    'indicia_pub_not_printed':
        "Check this box if no publisher name is listed "
        "in the indicia or colophon.",
    'brand':
        "The publisher's logo or tagline on the cover of the comic, "
        "if any. If no matching brand emblem exists, it either "
        " needs to be added to the database, or information for the "
        "years used of an existing one needs to be changed.",
    'no_brand':
        "Some comics do not have any identifiable brand marks. Check "
        "this box if there is no publisher's logo or tagline.",

    'isbn':
        'The ISBN as printed on the item. Do not use this field for '
        'numbering systems other than ISBN. If both ISBN 10 and '
        'ISBN 13 are listed, separate them with a semi-colon. '
        ' Example: "978-0-307-29063-2; 0-307-29063-8".',
    'no_isbn':
        "Check this box if there is no ISBN.",

    'barcode':
        'The barcode as printed on the item with no spaces. In case '
        'two barcodes are present, separate them with a semi-colon.',
    'no_barcode':
        'Check this box if there is no barcode.',

    'rating':
        "The publisher's age guidelines as printed on the item.",
    'no_rating':
        "Check this box if there are no publisher's age guidelines.",
}

VARIANT_NAME_HELP_TEXT = (
    'Name of this variant. Examples are: "Cover A" (if listed as such in '
    'the issue), "2nd printing", "newsstand", "direct", or the name of '
    'the artist if different from the base issue.')


def _set_help_labels(self, help_links):
    for field in self.fields:
        if field in help_links:
            if not self.fields[field].label:
                label = forms.forms.pretty_name(field)
            else:
                label = self.fields[field].label
            self.fields[field].label = mark_safe(
                label +
                u' <a href="%s%s" target=_blank>[?]</a>' %
                (DOC_URL, help_links[field]))


def _init_no_isbn(series, revision):
    """
    Set nice defaults for the no_isbn flag if we can figure out when this is.
    """
    if revision is not None and revision.issue is not None:
        return revision.issue.no_isbn

    if series.year_ended and series.year_ended < 1970:
        return True

    return False


def _init_no_barcode(series, revision):
    """
    Set nice defaults for no_barcode if we can figure out when this is.
    """
    if revision is not None and revision.issue is not None:
        return revision.issue.no_barcode

    if series.year_ended and series.year_ended < 1974:
        return True

    return False


class HiddenInputWithHelp(forms.TextInput):
    input_type = 'hidden'

    def __init__(self, *args, **kwargs):
        super(HiddenInputWithHelp, self).__init__(*args, **kwargs)
        self.attrs = kwargs.get('attrs', {})
        self.key = self.attrs.get('key', False)

    @property
    def is_hidden(self):
        # As of Django 1.7 this is tied to whether input_type is 'hidden',
        # which then means that it is not rendered in line with the
        # non-hidden fields.  Override this so that we can get the
        # help text to appear in the appropriate order among the regular
        # form fields.
        return False

    def render(self, name, value, *args, **kwargs):
        return mark_safe(super(HiddenInputWithHelp, self).render(name, value,
                                                                 self.attrs))


def _get_comments_form_field():
    return forms.CharField(
        widget=forms.Textarea, required=False,
        help_text='Comments about the change. These are part of the change '
                  'history, but not part of the regular display.')


def _clean_keywords(cleaned_data):
    keywords = cleaned_data['keywords']
    if keywords is not None:
        not_allowed = False
        for c in ['<', '>', '{', '}', ':', '/', '\\', '|', '@', ',']:
            if c in keywords:
                not_allowed = True
                break
        if not_allowed:
            raise forms.ValidationError(
                'The following characters are not allowed in a keyword: '
                '< > { } : / \ | @ ,')

    return keywords


def init_data_source_fields(field_name, revision, fields):
    data_source_revision = revision.changeset.creatordatasourcerevisions\
                                             .filter(field=field_name)
    if data_source_revision:
        # TODO we want to be able to support more than one revision
        data_source_revision = data_source_revision[0]
        fields['%s_source_description' % field_name].initial = \
                                    data_source_revision.source_description
        fields['%s_source_type' % field_name].initial = \
                                    data_source_revision.source_type


def add_data_source_fields(form, field_name):
    form.fields['%s_source_description' % field_name] = forms.CharField(
                                    widget=forms.Textarea, required=False)
    form.fields['%s_source_type' % field_name] = forms.ModelChoiceField(
                        queryset=SourceType.objects.all(), required=False)


def insert_data_source_fields(field_name, ordering, fields, insert_after):
    index = ordering.index(insert_after)

    ordering.insert(index+1, '%s_source_description' % field_name)
    fields.update({'%s_source_description' % field_name: forms.CharField(
                                    widget=forms.Textarea, required=False)})

    ordering.insert(index+2, '%s_source_type' % field_name)
    fields.update({'%s_source_type' % field_name: forms.ModelChoiceField(
                        queryset=SourceType.objects.all(), required=False)})


class PageCountInput(TextInput):
    def render(self, name, value, attrs=None):
        value = format_page_count(value)
        return super(PageCountInput, self).render(name, value, attrs)


class BrandEmblemSelect(forms.Select):
    def render_option(self, selected_choices, option_value, option_label):
        url = ''
        if option_value:
            brand = Brand.objects.get(id=option_value)
            if brand.emblem and not settings.FAKE_IMAGES:
                url = brand.emblem.icon.url
        option_value = force_unicode(option_value)
        if option_value in selected_choices:
            selected_html = u' selected="selected"'
            if not self.allow_multiple_selected:
                # Only allow for a single selection.
                selected_choices.remove(option_value)
        else:
            selected_html = ''
        if url:
            return (u'<option value="%s"%s data-image="%s" '
                    'image-width="%d">%s</option>') % (
                escape(option_value),
                selected_html,
                url,
                brand.emblem.icon.width,
                conditional_escape(force_unicode(option_label)))
        else:
            return u'<option value="%s"%s>%s</option>' % (
                escape(option_value),
                selected_html,
                conditional_escape(force_unicode(option_label)))
