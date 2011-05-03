import sys

from django.db import transaction, connection
from django.db.models import F, Count

from apps.gcd.models import Publisher, Series
from apps.oi.models import check_delete_imprint
from apps.gcd.migration import migrate_reserve, do_auto_approve

def fix_stray_imprints():
    """
    Several rows ended up neither master publishers nor imprints,
    but they are in fact all associated with an existing master publisher.
    Set them up as imprints so that our auto-deletion code will find them.

    Note that we do not maintain change history for imprints, so they are
    just updated directly.
    """
    # Handle two stray Hyperion imprints that lost their parent.
    hyperion = Publisher.objects.get(name='Hyperion', is_master=True)
    Publisher.objects.filter(id=4353).update(parent=hyperion,
                                             name='Jump at the Sun [duplicate]')
    Publisher.objects.filter(id=3970).update(parent=hyperion)

    # Stuff the Pocket Books co-publishing "imprint" under Pocket Books
    pocket = Publisher.objects.get(name='Pocket Books', is_master=True)
    Publisher.objects.filter(id__in=(2345, 2346, 2347)).update(parent=pocket)

    # Four imprints ended up also flagged as Master Publishers.  Fix that.
    Publisher.objects.filter(id__in=(455, 746, 2499, 4775)).update(is_master=False)

    # One of these has an imprint which now needs to be re-parented.
    # Horror House Press should be under AC, not AC Comics.
    horror_house = Publisher.objects.get(id=3644)
    horror_house.parent = horror_house.parent.parent
    horror_house.save()

    changes = []
    errors = []

    # AC Comics is a special case- we just need to fix it to match the adjusted
    # state of the imprint that we re-parented above.
    s = Series.objects.get(publisher=455, imprint=3644)
    c = migrate_reserve(s, 'series', 'Current publisher is an imprint- fixing')
    if c is None:
        errors.append(s)
    else:
        sr = c.seriesrevisions.all()[0]
        sr.publisher = sr.imprint.parent
        sr.save()
        changes.append((sr, True))

    # For everything else, the series has no imprint, so bump the former
    # master publisher down to imprint, and set the master publisher to the
    # imprint's parent.
    for series_id in (24204, 25280, # MAGNECOM
                      13887, 22352, 22353, 22354, # Magazine Publishers, Inc.
                      35897): # PowerMark Productions
        s = Series.objects.get(pk=series_id)
        c = migrate_reserve(s, 'series', 'Current publisher is an imprint- fixing')
        if c is None:
            errors.append(s)
        else:
            sr = c.seriesrevisions.all()[0]
            pub = sr.publisher
            sr.imprint = pub
            sr.publisher = pub.parent
            sr.save()
            changes.append((sr, True))

    do_auto_approve(changes, 'Auto-approving imprint vs master publisher fix')
    return True

    if errors:
        print "The following series are reserved and could not be fixed:"
        for reserved_series in errors:
            print "\t%s" % reserved_series
        print "Exiting with changes not committed."
        sys.exit(-1)

@transaction.commit_on_success
def main():
    fix_stray_imprints()

    # Make certain the series counts are up to date, as they often are not.
    # This was in part because of the rows that were both master publisher
    # and imprint- the counts were for master publishers.
    cursor = connection.cursor()
    cursor.execute("""
        UPDATE gcd_publisher i SET i.series_count=
            (SELECT COUNT(*) FROM gcd_series s WHERE s.imprint_id = i.id)
            WHERE i.is_master = 0 AND i.parent_id IS NOT NULL;
        UPDATE gcd_publisher i SET i.issue_count=
            (SELECT SUM(s.issue_count) FROM gcd_series s WHERE s.imprint_id = i.id)
            WHERE i.is_master = 0 AND i.parent_id IS NOT NULL
                  AND i.series_count > 0;
        UPDATE gcd_publisher i SET i.issue_count=0
            WHERE i.is_master = 0 AND i.parent_id IS NOT NULL
                  AND i.series_count = 0;
                   """)
    cursor.close()

    # Reload the imprints, and get only the ones we think are empty.
    empty_imprints = Publisher.objects.filter(parent__isnull=False,
                                              is_master=False,
                                              series_count=0) \
                                      .select_related('parent')
    for imprint in empty_imprints:

        print "Checking imprint %s (%d) of publisher %s (%d)" %\
              (imprint.name, imprint.year_began,
               imprint.parent.name, imprint.parent.year_began)
        deleted = check_delete_imprint(imprint)
        if not deleted:
            print "...imprint %s deletion failed!" % imprint.name

if __name__ == '__main__':
    main()

