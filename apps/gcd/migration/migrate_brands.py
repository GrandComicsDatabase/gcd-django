import sys
import logging
import subprocess
import shlex
import os.path
import os
from optparse import OptionParser

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings")

# default is to run this script from gcd-django directory
usage = "usage: %prog -p PATH| --path=PATH"
parser = OptionParser(usage)
parser.add_option('-p', '--path', dest='path', metavar='PATH',
                  help="Location of gcd-django to use", default=".")
(options, args) = parser.parse_args()
sys.path.append(options.path)

from django.conf import settings
from django.db import models
from django.contrib.auth.models import User

from apps.gcd.models import Brand
from apps.oi.models import Changeset, BrandRevision, BrandGroupRevision, \
                           BrandUseRevision, CTYPES
from apps.oi import states

def main():
    if settings.DEBUG:
        raise ValueError('This script requires that debug be set to false!')

    brands = Brand.objects.filter(group=None, deleted=False)

    ANON_USER = User.objects.get(username=settings.ANON_USER_NAME)

    # create corresponding brand_group for each brand
    for brand in brands:
        # create BrandGroup
        changeset = Changeset(indexer=ANON_USER, approver=ANON_USER,
          state=states.REVIEWING, change_type=CTYPES['brand_group'])
        changeset.save()
        changeset.comments.create(commenter=ANON_USER,
            text='This is an automatically generated change '
                'for the creation of a brand group for a brand.',
            old_state=states.REVIEWING, new_state=states.REVIEWING)

        revision = BrandGroupRevision(changeset=changeset,
            name=brand.name,
            year_began=brand.year_began,
            year_began_uncertain=brand.year_began_uncertain,
            year_ended=brand.year_ended,
            year_ended_uncertain=brand.year_ended_uncertain,
            url=brand.url, notes=brand.notes, parent=brand.parent,
            # no keywords are copied, seemingly, only few and emblem specific
            keywords='')
        revision.save()
        changeset.approve(notes='Automatically approved.')
        brand_group = changeset.brandgrouprevisions.get().brand_group

        # assign BrandGroup to Brand
        changeset = Changeset(indexer=ANON_USER,
            approver=ANON_USER, state=states.REVIEWING, change_type=CTYPES['brand'])
        changeset.save()
        changeset.comments.create(commenter=ANON_USER,
            text='This is an automatically generated change for the '
                'assignment of a brand to its created brand group.',
            old_state=states.REVIEWING, new_state=states.REVIEWING)
        brand_revision = BrandRevision.objects.clone_revision(brand=brand,
            changeset=changeset)
        brand_revision.group.add(brand_group)
        brand_revision.save()
        changeset.approve(notes='Automatically approved.')

        # create BrandUse
        changeset = Changeset(indexer=ANON_USER, approver=ANON_USER,
                                state=states.REVIEWING, change_type=CTYPES['brand_use'])
        changeset.save()
        changeset.comments.create(commenter=ANON_USER,
            text='This is an automatically generated change '
                'for the creation of a brand use for a brand.',
            old_state=states.REVIEWING, new_state=states.REVIEWING)
        use = BrandUseRevision(changeset=changeset, emblem=brand,
            publisher=brand.parent,
            year_began=brand.year_began,
            year_began_uncertain=brand.year_began_uncertain,
            year_ended=brand.year_ended,
            year_ended_uncertain=brand.year_ended_uncertain)
        use.save()
        changeset.approve(notes='Automatically approved.')
        in_use = changeset.branduserevisions.get().brand_use
        in_use.save()

main()
