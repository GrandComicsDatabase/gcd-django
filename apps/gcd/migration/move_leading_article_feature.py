import sys

from django.db import transaction, connection

from apps.gcd.models import Issue
from apps.gcd.migration import migrate_reserve, do_auto_approve

def move_leading_article(article):
    changes = []

    issues = Issue.objects.filter(story__feature__endswith=", %s" % article, reserved=False, deleted=False).distinct().exclude(story__feature='Spider-Man and Human Torch, The')
    issues = issues.distinct()
    # limit the number processed at a time, there are some odd problems if not
    for i in issues[:250]:
        stories = i.active_stories().filter(feature__endswith=", %s" % article)
        c = migrate_reserve(i, 'issue', 'for moving ", %s" to the beginning of the feature' % article)
        if c:
            sr = c.storyrevisions.filter(feature__endswith=", %s" % article)
            for s in sr:
                s.feature = "%s %s" % (article, s.feature[:-(len(article)+2)])
                print s.feature
                s.save()
            changes.append((c, True))
    do_auto_approve(changes, 'move of leading article in feature')
    return True

@transaction.commit_on_success
def main():
    move_leading_article('The')

if __name__ == '__main__':
    main()
