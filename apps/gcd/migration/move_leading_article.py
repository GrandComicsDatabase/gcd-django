import sys

from django.db import transaction, connection

from apps.gcd.models import Series
from apps.gcd.migration import migrate_reserve, do_auto_approve

def move_leading_article(article):
    # english
    changes = []
    errors = []

    series = Series.objects.filter(name__endswith=", %s" % article, reserved=False)

    for s in series[:200]:
        c = migrate_reserve(s, 'series', 'for moving ", %s" to the beginning of the series name' % article)
        if c:
            sr = c.seriesrevisions.all()[0]
            sr.name = "%s %s" % (article, sr.name[:-(len(article)+2)])
            sr.leading_article = True
            sr.save()
            changes.append((c, True))
    do_auto_approve(changes, 'move of leading article')
    return True

@transaction.commit_on_success
def main():
    move_leading_article('The')
    move_leading_article('An')
    move_leading_article('A')
    move_leading_article('Die')

if __name__ == '__main__':
    main()

