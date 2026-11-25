from django.db.models import Count, Sum
from django.db.models import F
from django.utils.html import format_html

import django_tables2 as tables

# from apps.stddata.models import Country, Language
from apps.gcd.models import Publisher, Issue, StoryType, Series, Story, Creator
from apps.gcd.models.series import SeriesPublisherTable
from apps.gcd.templatetags.credits import get_country_flag
from apps.gcd.views import paginate_response
from apps.gcd.views.details import generic_sortable_list, \
                                   TW_SORT_TABLE_TEMPLATE
from apps.projects.forms import IssuesWithCoversForm
from apps.select.views import filter_series


def issues_with_several_covers(request):
    """
    This project is geared towards moving variant covers into variant issues.
    For this we need a list of such issues that can be filtered and sorted
    by a few basic attributes.
    """

    issues=Issue.objects.annotate(covers=Count('cover'))
    issues=issues.annotate(covers_deleted=Sum('cover__deleted'))
    issues=issues.filter(covers__gt=1+F('covers_deleted'), deleted=False)

    qargs = {'deleted': False}
    qorder = ['series__name', 'series__year_began', 'number']

    vars = {
        'heading': 'Issues',
        'search_item': 'with several covers',
        'item_name': 'issue',
        'plural_suffix': 's',
    }

    if (request.GET):
        form = IssuesWithCoversForm(request.GET)
        form.is_valid()
        if form.is_valid():
            data = form.cleaned_data

            # Extra filters
            if data['publisher']:
                qargs['series__publisher__id'] = data['publisher']

        get_copy = request.GET.copy()
        get_copy.pop('page', None)
        vars['query_string'] = get_copy.urlencode()
    else:
        form = IssuesWithCoversForm()
        issues = issues.filter(series__publisher__id=709) #need to keep #issues smaller
        # for the pagination bar and select box
        vars['query_string'] = 'publisher=709'
        get_copy = request.GET.copy()
        get_copy['items'] = [('publisher', 709),]
        request.GET = get_copy
    issues = issues.filter(**qargs).order_by(*qorder)
    vars['form'] = form
    vars['advanced_search'] = True

    return paginate_response(request, issues,
                             'projects/issues_with_several_covers.html', vars, per_page=50)


class CountryColumn(tables.Column):
    """A country shown with its flag and its name."""

    def render(self, value):
        """Return the flag and the name of the country."""
        return format_html('{} {}', get_country_flag(value), value.name)

    def value(self, value):
        """Return the name of the country for the downloads."""
        return value.name


class SeriesWithOtherCountryTable(SeriesPublisherTable):
    """Series with their country next to the country of their publisher."""
    country = CountryColumn(verbose_name='Country',
                            order_by=('country__name', 'sort_name'))
    publisher_country = CountryColumn(
      accessor='publisher__country', verbose_name="Publisher's Country",
      order_by=('publisher__country__name', 'sort_name'))
    covers = None
    published = None

    class Meta:
        model = Series
        fields = ('name', 'year_began', 'country', 'publisher',
                  'publisher_country', 'issue_count')
        sequence = fields


def series_with_other_country(request):
    """
    Clean-up list of the series whose country is not the country of their
    publisher, sortable and filtered by country, language and publisher.
    """
    series = Series.objects.filter(deleted=False)\
                           .exclude(country=F('publisher__country'))\
                           .select_related('country', 'publisher__country',
                                           'publication_type')
    series_filter = filter_series(request, series)
    series = series_filter.qs
    context = {
        'item_name': 'series',
        'plural_suffix': '',
        'heading': 'whose country is not the country of their publisher',
        'filter_form': series_filter.form,
    }
    table = SeriesWithOtherCountryTable(series,
                                        template_name=TW_SORT_TABLE_TEMPLATE,
                                        order_by=('name'))
    return generic_sortable_list(request, series, table,
                                 'gcd/search/tw_list_sortable.html', context)
