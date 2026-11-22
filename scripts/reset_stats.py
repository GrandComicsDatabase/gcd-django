from django.db.models import Q, F, Count, Case, When

from apps.stats.models import CountStats
from apps.gcd.models import Publisher, Series, Issue
from apps.stddata.models import Language, Country


def main():
    CountStats.objects.all().delete()
    CountStats.objects.init_stats()

    for i in Language.objects.all():
        if Series.objects.filter(language=i).exists():
            CountStats.objects.init_stats(language=i)

    for i in Country.objects.all():
        if Series.objects.filter(country=i).exists():
            CountStats.objects.init_stats(country=i)

def reset_series_issue_count_cache():
    # -------------------------------------------------------------------------
    # Rebuild Series.issue_count Caches
    # -------------------------------------------------------------------------
    # An issue contributes +1 to a Series count if:
    #   (a) It is a standard base issue (variant_of is NULL)
    #   (b) It is a cross-series variant (its series differs from its base issue's series)
    # Standard variants within the same series do not count, preventing inflation.
    #
    # This bulk aggregation MUST remain synchronized with the real-time Python
    # logic in `apps.gcd.models.issue.Issue.stat_counts()`.

    from django.db.models import Subquery, OuterRef
    from django.db.models.functions import Coalesce

    subquery = Issue.objects.filter(
        deleted=False,
        series_id=OuterRef('pk')
    ).filter(
        Q(variant_of__isnull=True) | ~Q(series_id=F('variant_of__series_id'))
    ).values('series_id').annotate(c=Count('id')).values('c').order_by()

    Series.objects.update(issue_count=Coalesce(Subquery(subquery), 0))


def reset_publisher_series_issue_count_cache():
    """
    Recount Publisher.series_count and Publisher.issue_count.

    Approvals change these counts by steps: Publisher.update_cached_counts()
    adds the deltas of Series.stat_counts() and Issue.stat_counts().
    This recount gives the totals of those steps:

    - series_count: the series that are not deleted, comics
      publications or not ('series' and 'publisher series');
    - issue_count: the issues that are not deleted and not variants,
      in series that are not deleted and are comics publications.

    Unlike Series.issue_count, a variant whose base issue is in another
    series is not counted.
    """
    from django.db.models import Subquery, OuterRef
    from django.db.models.functions import Coalesce

    series = Series.objects.filter(
        deleted=False, publisher_id=OuterRef('pk'),
    ).values('publisher_id').annotate(
        c=Count('id')).values('c').order_by()

    issues = Issue.objects.filter(
        deleted=False, variant_of__isnull=True, series__deleted=False,
        series__is_comics_publication=True,
        series__publisher_id=OuterRef('pk'),
    ).values('series__publisher_id').annotate(
        c=Count('id')).values('c').order_by()

    Publisher.objects.update(
        series_count=Coalesce(Subquery(series), 0),
        issue_count=Coalesce(Subquery(issues), 0))


def run():
    main()
    # only reset the series issue count cache if explicitly requested
    # reset_series_issue_count_cache()
    # only recount the publishers if explicitly requested
    # reset_publisher_series_issue_count_cache()
