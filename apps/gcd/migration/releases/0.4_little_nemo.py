import sys
import logging
import subprocess
import shlex
import os.path

from django.conf import settings
from django.db.models import Count

from apps.gcd.models import Language, CountStats

def main():
    if settings.DEBUG:
        raise ValueError('This script requies that debug be set to false!')

    logging.basicConfig(level=logging.NOTSET,
                        stream=sys.stdout,
                        format='%(asctime)s %(levelname)s: %(message)s')

    logging.info('Ensuring recent language, country and type entries are present.')
    try:
        undetermined_language = Language.objects.get(code='und')
    except Language.DoesNotExist:
        undetermined_language = Language(code='und', name='(undetermined)')
        undetermined_language.save()
    try:
        unknown_story_type = StoryType.objects.get(name='(unknown)')
    except StoryType.DoesNotExist:
        unknown_story_type = StoryType(name='(unknown)', sort_code=100)
        unknown_story_type.save()
        unknown_story_type.sort_code = models.F('id')
        unknown_story_type.save()

    basic_args = ' -u%s' % settings.DATABASE_USER
    if settings.DATABASE_PASSWORD:
        basic_args += ' -p%s' % settings.DATABASE_PASSWORD
    if settings.DATABASE_HOST:
        basic_args += ' -h%s' % settings.DATABASE_HOST
    basic_args += ' ' + settings.DATABASE_NAME

    mysql = shlex.split('mysql' + basic_args)
    mysqldump = shlex.split('mysqldump' + basic_args)

    sdir = os.path.join(settings.DATABASE_SCRIPT_DIR, '0.4_little_nemo')

    logging.info("Backing up the database...")
    backup = open(os.path.join(sdir, 'pre-nemo-backup.sql'), 'w')
    subprocess.check_call(mysqldump, stdout=backup)
    backup.close()

    logging.info("Loading the prepared log tables...")
    prepared_logs = open(os.path.join(sdir, 'prepared_logs.sql'))
    subprocess.check_call(mysql, stdin=prepared_logs)
    prepared_logs.close()

    logging.info("Running syncdp... this may prompt!")
    subprocess.check_call(('python', 'manage.py', 'syncdb'))

    # 20 gives us room to squeeze in one more script without having to update this.
    for n in range(1, 20):
        script = os.path.join(sdir, 'migrate-%d.sql' % n)
        if os.path.isfile(script):
            open_script = open(script)
            logging.info("Running '%s'..." % script)
            subprocess.check_call(mysql, stdin=open_script)
            open_script.close()

    languages = Language.objects.annotate(count_series=Count('series')) \
                                .exclude(count_series=0)
    for lang in languages:
        CountStats.objects.init_stats(lang)
    CountStats.objects.init(None)
        
    logging.info("Saving a post-schema, pre-changes migration dump...")
    pre_changeset = open(os.path.join(sdir, 'pre-changesets-backup.sql'), 'w')
    subprocess.check_call(mysqldump, stdout=pre_changeset)
    pre_changeset.close()

    logging.info("Done with basic schema migration!")

main()

