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
    # This bulk aggregation MUST remain synchronized with the real-time Python
    # logic in `apps.gcd.models.issue.Issue.stat_counts()`.
    #
    # Recompute per-series cached `issue_count` to match Issue.stat_counts()
    # Rule: an issue counts for its series if it's not a variant, OR it is a
    # variant whose base issue is in a different series (cross-series variant).
    # Inside scripts/reset_stats.py
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

