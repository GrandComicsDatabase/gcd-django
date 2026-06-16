from django.db.models import Q, F, Count, Case, When

from apps.stats.models import CountStats
from apps.gcd.models import Series, Issue
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
    ).values('series_id').annotate(c=Count('id')).values('c')

    Series.objects.update(issue_count=Coalesce(Subquery(subquery), 0))


def run():
    main()

