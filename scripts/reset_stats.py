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
    issue_qs = Issue.objects.filter(deleted=False).filter(
        Q(variant_of__isnull=True) | ~Q(series=F('variant_of__series'))
    ).values('series').annotate(c=Count('id'))

    whens = [When(pk=entry['series'], then=entry['c']) for entry in issue_qs]
    if whens:
        Series.objects.update(issue_count=Case(*whens, default=0))
    else:
        Series.objects.update(issue_count=0)


def run():
    main()

