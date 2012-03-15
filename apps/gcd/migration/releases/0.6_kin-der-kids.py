import sys
import logging
import subprocess
import shlex
import os.path

from django.conf import settings
from django.db import models
from django.db.models import Count

def main():
    if settings.DEBUG:
        raise ValueError('This script requires that debug be set to false!')

    logging.basicConfig(level=logging.NOTSET,
                        stream=sys.stdout,
                        format='%(asctime)s %(levelname)s: %(message)s')

    basic_args = ' -u%s' % settings.DATABASE_USER
    if settings.DATABASE_PASSWORD:
        basic_args += ' -p%s' % settings.DATABASE_PASSWORD
    if settings.DATABASE_HOST:
        basic_args += ' -h%s' % settings.DATABASE_HOST
    basic_args += ' ' + settings.DATABASE_NAME

    mysql = shlex.split('mysql' + basic_args)
    mysqldump = shlex.split('mysqldump' + basic_args)

    sdir = os.path.join(settings.DATABASE_SCRIPT_DIR, '0.6_kin_der_kids')

    logging.info("Backing up the database...")
    backup = open(os.path.join(sdir, 'pre-kin-der-kids-backup.sql'), 'w')
    subprocess.check_call(mysqldump, stdout=backup)
    backup.close()

    logging.info("Running syncdb... this may prompt!")
    subprocess.check_call(('python', 'manage.py', 'syncdb'))

    # 20 gives us room to squeeze in one more script without having to update this.
    for n in range(1, 20):
        script = os.path.join(sdir, 'migrate-%d.sql' % n)
        if os.path.isfile(script):
            open_script = open(script)
            logging.info("Running '%s'..." % script)
            subprocess.check_call(mysql, stdin=open_script)
            open_script.close()

    logging.info("Saving a post-schema, pre-changes migration dump...")
    pre_changeset = open(os.path.join(sdir, 'pre-changesets-backup.sql'), 'w')
    subprocess.check_call(mysqldump, stdout=pre_changeset)
    pre_changeset.close()

    logging.info("Done with basic schema migration!")

main()

