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
    subprocess.check_call(('python26', 'manage.py', 'syncdb'))

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
    logging.info("Website can be activated in READONLY mode!")

    logging.info("Now fixing known problems in reprint notes!")
    # calling these inside this script doesn't seem to save the changes for some reason
    subprocess.check_call(('python26', 'apps/gcd/migration/fix_reprint_notes.py'))
    subprocess.check_call(('python26', 'apps/gcd/migration/fix_italian_reprint_notes.py'))
    logging.info("Done with fixing reprint notes for preparation of reprint migration !")
    subprocess.check_call(('python26', 'apps/gcd/migration/reprints/migrate_reprints.py', '1'))
    logging.info("Migrated Lars!")
    subprocess.check_call(('python26', 'apps/gcd/migration/reprints/migrate_reprints.py', '2'))
    logging.info("Standard Migration Done!")
    subprocess.check_call(('python26', 'apps/gcd/migration/reprints/migrate_reprints.py', '3'))
    logging.info("Greedy Migration Done! ")
    subprocess.check_call(('python26', 'apps/gcd/migration/reprints/migrate_reprints.py', '4'))
    logging.info("Check Double Links Done!")
    subprocess.check_call(('python26', 'apps/gcd/migration/reprints/migrate_reprints.py', '5'))
    logging.info("Merge Cover Return Links Done!")
    subprocess.check_call(('python26', 'apps/gcd/migration/reprints/migrate_reprints.py', '6'))
    logging.info("Merge Links Story Done!")
    script = os.path.join(sdir, 'post-reprint-migrate-1.sql')
    open_script = open(script)
    logging.info("Running '%s'..." % script)
    subprocess.check_call(mysql, stdin=open_script)
    open_script.close()
    logging.info("Done with reprint migration!")

main()

