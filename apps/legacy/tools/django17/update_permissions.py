import django
from django.contrib.contenttypes.models import ContentType


def update():
    for old_app, new_app, model in (('gcd', 'stddata', 'country'),
                                    ('gcd', 'stddata', 'language'),
                                    ('gcd', 'indexer', 'indexer'),
                                    ('gcd', 'indexer', 'impgrant'),
                                    ('gcd', 'indexer', 'error'),
                                    ('gcd', 'stats', 'countstats'),
                                    ('gcd', 'stats', 'recentindexedissue'),
                                    ('oi', 'stats', 'download'),
                                    ('gcd', 'legacy', 'indexcredit'),
                                    ('gcd', 'legacy', 'reservation'),
                                    ('gcd', 'legacy', 'migrationstorystatus')):
        print('Moving %s from %s to %s' % (model, old_app, new_app))
        try:
            old_type = ContentType.objects.get(app_label=old_app, model=model)
            old_type.app_label = new_app
            old_type.save()
        except ContentType.DoesNotExist:
            # If it's not there, we don't need to move it.
            print('   skipping...')


if __name__ == '__main__':
    django.setup()
    update()
