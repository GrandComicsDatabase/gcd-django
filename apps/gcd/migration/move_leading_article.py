import sys

from django.db import transaction, connection

from apps.gcd.models import Series
from apps.gcd.migration import migrate_reserve, do_auto_approve

def move_leading_article(article):
    # english
    changes = []
    errors = []

    series = Series.objects.filter(name__endswith=", %s" % article, reserved=False)

    for s in series[:250]:
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
    for i in range(18):
        move_leading_article('The')
    move_leading_article('An')
    move_leading_article('A')
    move_leading_article('Die')
    move_leading_article('Der')
    move_leading_article('Ein')
    move_leading_article('Das')
    move_leading_article('Los')
    move_leading_article('La')
    move_leading_article('Le')
    move_leading_article('Lo')
    move_leading_article('Las')
    move_leading_article('Les')
    move_leading_article('El')
    move_leading_article('Un')
    move_leading_article('Una')
    move_leading_article('Unos')
    move_leading_article('Unas')
    move_leading_article('Il')
    move_leading_article('I')
    move_leading_article('Gli')
    move_leading_article('En')
    move_leading_article('Et')
    move_leading_article('Ett')
    move_leading_article('De')
    move_leading_article('Het')
    move_leading_article('Een')
    move_leading_article("'t")
    move_leading_article("'n")

if __name__ == '__main__':
    main()

#Spanish

#El
#La
#Lo
#Los
#Las
#Un
#Una
#Unos
#Unas


#Italian:

#il
#lo
#la
#i
#gli
#le

#Norwegian, Danish, Swedish

#En
#Et
#Ett

#Dutch:
#De
#Het
#Een
#D' (not sure if present in our db, but series exist)
#'t
#'n