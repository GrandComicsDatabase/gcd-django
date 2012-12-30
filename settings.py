# -*- coding: utf-8 -*-
# Django settings for gcd project.
import datetime
from os.path import abspath, dirname, join
from os import environ # helps determine MEDIA_URL.

"""
This is the main settings file.  It should not be changed unless the change
is meant to apply to all installations, development and production, of the project.
In order to make local changes for your particular environment, create
a file called "settings_local.py" in the same directory.  You can override
the contents of any variable.  Go through the comments in this file to see
which variables you can or must override.
"""

#################################################################################
# Standard Django settings
#################################################################################

# disable on production!
DEBUG          = True
TEMPLATE_DEBUG = DEBUG

# absolute path to the directory that holds templates.
TEMPLATE_DIRS = ( abspath(join(dirname(__file__), 'templates')),
                  abspath(join(dirname(__file__), 'apps', 'voting', 'templates')),)

# absolute path to the directory that holds media.
# URL that handles the media served from MEDIA_ROOT.
MEDIA_ROOT = abspath(join(dirname(__file__), 'media'))
MEDIA_URL = '/site_media/'

# We're not using django.contrib.staticfiles yet, but the admin site
# is happier with a STATIC_URL.
STATIC_URL = MEDIA_URL

# Database settings. Override yours in a settings_local.py
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME':  'gcdonline',
        'USER': 'gcdonline',
        'PASSWORD': '',
        'HOST': '',
        'PORT': '',
    },
}

# middleware settings, LocalMiddleware is for internationalisation
MIDDLEWARE_CLASSES = (
   'django.middleware.csrf.CsrfViewMiddleware',
   'django.middleware.clickjacking.XFrameOptionsMiddleware',
   'django.contrib.sessions.middleware.SessionMiddleware',
   'django.contrib.messages.middleware.MessageMiddleware',
   'django.contrib.auth.middleware.AuthenticationMiddleware',
   'django.middleware.common.CommonMiddleware',
   'django.middleware.transaction.TransactionMiddleware',
   'apps.gcd.locale_query.LocaleQueryMiddleware'
)

LANGUAGES = (
  ('de', 'German'),
  ('en', 'English'),
)

# The router where all our site URLs is defined.
ROOT_URLCONF = 'urls'

# Email these if there's a site exception and debug isn't on.
ADMINS = (
    ('GCD Admins', 'sysadmin@comics.org'),
)
MANAGERS = ADMINS

# All enabled apps for this install.
INSTALLED_APPS = (
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.admin',
    'django.contrib.humanize',
    'django.contrib.sites',
    'django.contrib.messages',
    'apps.gcd',
    'apps.oi',
    'apps.voting',
    'compressor',
    'templatesadmin',
    'taggit',
    'imagekit',
    'south',
)

# Used to provide a seed in secret-key hashing algorithms.
# Overridden in production via settings_local.py.
SECRET_KEY = 'th0lnu%wjs_8=r4u_km3shvogzd%1n)t-5eosi964g0ek+a4p+'

# Callables that know how to import templates from various sources.
TEMPLATE_LOADERS = (
    'django.template.loaders.filesystem.Loader',
    'django.template.loaders.app_directories.Loader',
)

TEMPLATE_CONTEXT_PROCESSORS = (
    'django.contrib.auth.context_processors.auth',
    'django.contrib.messages.context_processors.messages',
    'django.core.context_processors.debug',
    'django.core.context_processors.i18n',
    'django.core.context_processors.media',
    'django.core.context_processors.request',
    'apps.gcd.context_processors.gcd',
)

AUTH_PROFILE_MODULE = 'gcd.Indexer'
AUTHENTICATION_BACKENDS = (
    'apps.gcd.backends.EmailBackend',
    'django.contrib.auth.backends.ModelBackend',
)

ABSOLUTE_URL_OVERRIDES = {
    'auth.user': lambda o: "/accounts/profile/%d/" % o.id,
}

# for local installations, who don't have memcached, put this:
#CACHES = {
#    'default': {
#        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
#        'LOCATION': 'unique-snowflake'
#    }
#}
# in your settings_local.py as an override.
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.memcached.MemcachedCache',
        'LOCATION': '127.0.0.1:11211',
    }
}

# have two choices for caches, this one has persistent, cached session data
SESSION_ENGINE = 'django.contrib.sessions.backends.cached_db'

# Corresponds to the django_site database table. As far
# as I know, we won't be using this for the GCD.
SITE_ID = 1

# Local time zone for this installation. Choices can be found here:
# http://www.postgresql.org/docs/8.1/static/datetime-keywords.html#DATETIME-TIMEZONE-SET-TABLE
TIME_ZONE = 'UTC'

# International DateTime string format
DATETIME_FORMAT = 'Y-m-d H:i:s'

#################################################################################
# 3rd-party app settings
#################################################################################

COMPRESS_CSS_FILTERS = ['compressor.filters.css_default.CssAbsoluteFilter',
                        'compressor.filters.csstidy.CSSTidyFilter']

# for front page editing
TEMPLATESADMIN_TEMPLATE_DIRS = [abspath(join(dirname(__file__),
                                'templates/gcd/front_page/')),]
TEMPLATESADMIN_GROUP = 'prteam'

#################################################################################
# GCD site settings
#################################################################################

###
# Debugging and development environment settings
BETA = False

ADVERTISING = True
CALENDAR = True

# Set to True to avoid hitting comics.org for every cover image.
# If True, the same cover image will be used for every issue.
FAKE_COVER_IMAGES = False

# site management defaults- change these in settings_local.py as needed.
SITE_DOWN = False
SITE_DOWN_MESSAGE = ''
SITE_BACK_UP_AT = ''
READ_ONLY = False
NO_OI = False

###
# General GCD site settings

DEFAULT_FROM_EMAIL = 'GCD Contact <contact@comics.org>'
EMAIL_NEW_ACCOUNTS_FROM = 'GCD New Accounts <new.accounts@comics.org>'
EMAIL_EDITORS = 'gcd-editor@googlegroups.com'
EMAIL_CONTACT = 'contact@comics.org'
EMAIL_INDEXING = 'GCD Online Indexing <no-reply@comics.org>'

# Number of days for which a registraton confirmation token is valid.
REGISTRATION_EXPIRATION_DELTA = 2

# These will do for new users only until the Board finishes setting the policy.
# Pre-Vieux Bois users have very high numbers set via migration script.
RESERVE_MAX_INITIAL = 1
RESERVE_MAX_PROBATION = 6 # half-year monthly miniseries
RESERVE_MAX_DEFAULT = 12 # full year of a monthly
RESERVE_MAX_ONGOING_INITIAL = 0
RESERVE_MAX_ONGOING_PROBATION = 2
RESERVE_MAX_ONGOING_DEFAULT = 4

MEMBERSHIP_IMPS = 4000

LIMIT_SYNOPSIS_LENGTH = 600

RECENTS_COUNT = 5

SITE_URL = 'http://www.comics.org/'
SITE_NAME = 'Grand Comics Database'

# image directories
IMAGE_SERVER_URL = 'http://images.comics.org/'
COVERS_DIR = '/img/gcd/covers_by_id/'
NEW_COVERS_DIR = '/img/gcd/new_covers/'
GENERIC_IMAGE_DIR = 'img/gcd/generic_images/'
NEW_GENERIC_IMAGE_DIR = 'img/gcd/new_generic_images/'

# Name of the directory in the gcd/icons tree under the media root
# to use for icons within the app.
ICON_SET = "gnome"

BLOCKED_DOMAINS = ('mailinator.com', 'mintemail.com', 'trash-mail.com')

ANON_USER_NAME = 'anon'

# Date taken from Ray's press release.
# These were primarily used for migrating change history and filling in blanks.
OLD_SITE_CREATION_DATE = datetime.date(2002, 11, 13)
NEW_SITE_CREATION_DATE = datetime.date(2009, 12, 1)
NEW_SITE_COVER_CREATION_DATE = datetime.datetime(2009,10,2,14,0,0)

###
# Voting app settings

EMAIL_VOTING_FROM = 'GCD Voting <voting@comics.org>'
EMAIL_VOTING_ADMIN = EMAIL_CONTACT

# absolute path to the directory that holds election files.
VOTING_DIR = abspath(join(dirname(__file__), 'voting'))

###
# Data dump settings

# data dump directories, relative to MEDIA_ROOT
DUMP_DIR = 'dumps'
MYSQL_DUMP = 'current.zip'
POSTGRES_DUMP = 'pg-current.zip'

# Amount of time that must pass before a user can download the same
# dump (or similar) file again, in minutes.
DOWNLOAD_DELTA = 5

#################################################################################
# settings_local usage
#################################################################################

# get local settings, will override settings from here
try:
    from settings_local import *
except ImportError, exp:
    pass
try:
    import more_settings
    more_settings.modify(globals())
except ImportError:
    pass

#################################################################################
# Code dependent on debug or maintenance flag states.
#################################################################################

if READ_ONLY or NO_OI:
    MIDDLEWARE_CLASSES += \
      ('apps.middleware.read_only.ReadOnlyMiddleware',)

