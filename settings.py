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

ALLOWED_HOSTS = [
    '.comics.org',
    '.comics.org.',  # Allow FQDN and subdomains.  Can be dropped in 1.7
]

# absolute path to the directory that holds templates.
TEMPLATE_DIRS = ( abspath(join(dirname(__file__), 'templates')),
                  abspath(join(dirname(__file__),
                               'apps', 'indexer', 'templates')),
                  abspath(join(dirname(__file__),
                               'apps', 'stats', 'templates')),
                  abspath(join(dirname(__file__),
                               'apps', 'voting', 'templates')),)

# absolute path to the directory that holds media.
# URL that handles the media served from MEDIA_ROOT.
MEDIA_ROOT = abspath(join(dirname(__file__), 'media'))
MEDIA_URL = '/media/'

# URL and absolute path to static file tree.
STATIC_URL = '/static/'
STATIC_ROOT = abspath(join(dirname(__file__), 'static_root'))

# Additional dirs from which to collect static files.
# Must not contain STATIC_ROOT, which is the destination.
STATICFILES_DIRS = (abspath(join(dirname(__file__), 'static')),)

# THe first two are the defaults, which need to be listed because
# we also need the django-compressor finder to be specified.
STATICFILES_FINDERS = (
    'django.contrib.staticfiles.finders.FileSystemFinder',
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
    'compressor.finders.CompressorFinder',
)

# Set up for translations.
LOCALE_PATHS = [abspath(join(dirname(__file__), 'locale'))]

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
   'django_mobile.middleware.MobileDetectionMiddleware',
   'django_mobile.middleware.SetFlavourMiddleware',
   'apps.gcd.locale_query.LocaleQueryMiddleware',
   'apps.middleware.errorhandling.ErrorHandlingMiddleware'
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
    'django.contrib.staticfiles',
    'django_mobile',
    'apps.indexer',
    'apps.gcd',
    'apps.stats',
    'apps.legacy',
    'apps.oi',
    'apps.voting',
    'apps.stddata',
    'apps.mycomics',
    'compressor',
    'templatesadmin',
    'taggit',
    'imagekit',
    'haystack',
    'elasticstack',
    'bootstrap3',
    'rest_framework',
)

# Used to provide a seed in secret-key hashing algorithms.
# Overridden in production via settings_local.py.
SECRET_KEY = 'th0lnu%wjs_8=r4u_km3shvogzd%1n)t-5eosi964g0ek+a4p+'

# Callables that know how to import templates from various sources.
TEMPLATE_LOADERS = (
    'django_mobile.loader.Loader',
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
    'django.core.context_processors.static',
    'django_mobile.context_processors.flavour',
    'apps.gcd.context_processors.gcd',
)

AUTHENTICATION_BACKENDS = (
    'apps.indexer.backends.EmailBackend',
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

# we would like to move the default JSONSerializer, but currently that
# causes problems (see issue #102 on GitHub).  This is a workaround
# to retain the Django 1.5 and earlier behavior.
SESSION_SERIALIZER = 'django.contrib.sessions.serializers.PickleSerializer'

# Corresponds to the django_site database table. As far
# as I know, we won't be using this for the GCD.
SITE_ID = 1

# Local time zone for this installation. Choices can be found here:
# http://www.postgresql.org/docs/8.1/static/datetime-keywords.html#DATETIME-TIMEZONE-SET-TABLE
TIME_ZONE = 'UTC'

# International DateTime string format
DATETIME_FORMAT = 'Y-m-d H:i:s'

# Even though we are using pytest-django and don't use a Django test runner,
# Django 1.7 and 1.8 will emit warnings every time manage.py is run unless
# this line is here.  The false positive warning is removed in Django 1.9.
TEST_RUNNER = 'django.test.runner.DiscoverRunner'

#################################################################################
# 3rd-party app settings
#################################################################################

COMPRESS_CSS_FILTERS = ['compressor.filters.css_default.CssAbsoluteFilter',
                        'compressor.filters.csstidy.CSSTidyFilter']

# for front page editing and policy and other messages to indexers/editors
TEMPLATESADMIN_TEMPLATE_DIRS = [abspath(join(dirname(__file__),
                                       'templates/managed_content/')),]
TEMPLATESADMIN_GROUP = 'prteam'

#################################################################################
# Haystack and search
#################################################################################
HAYSTACK_CONNECTIONS = {
    'default': {
        'ENGINE': 'elasticstack.backends.ConfigurableElasticSearchEngine',
        'URL': 'http://127.0.0.1:9200/',
        'INDEX_NAME': 'haystack',
        'INCLUDE_SPELLING': True,
    },
}

ELASTICSEARCH_INDEX_SETTINGS = {
    # index settings
    'settings': {
        "analysis": {
            "analyzer": {
                "default": {
                    "type": "custom",
                    "tokenizer": "standard",
                    "filter": ["standard", "lowercase", "stop", "asciifolding"]
                }
            }
        }
    }
}

ELASTICSEARCH_DEFAULT_ANALYZER = 'default'

USE_ELASTICSEARCH = False

#################################################################################
# REST-API
#################################################################################
REST_FRAMEWORK = {

    'DEFAULT_PARSER_CLASSES': (
        'rest_framework_yaml.parsers.YAMLParser',
    ),

    'DEFAULT_RENDERER_CLASSES': (
        'rest_framework.renderers.BrowsableAPIRenderer',
        'rest_framework.renderers.JSONRenderer',
        'rest_framework_yaml.renderers.YAMLRenderer',
    ),
    # Use Django's standard `django.contrib.auth` permissions, 
    # or allow read-only access for unauthenticated users.
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.DjangoModelPermissionsOrAnonReadOnly',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 10
}

#################################################################################
# GCD site settings
#################################################################################

###
# Debugging and development environment settings
BETA = False

# Requires the gcd-managed-content repo to be checked out under
# templates/managed_content
USE_TEMPLATESADMIN = False

ADVERTISING = True
CALENDAR = True

# Set to True to avoid hitting comics.org for every cover image.
# If True, the same cover image will be used for every issue.
FAKE_IMAGES = False

# site management defaults- change these in settings_local.py as needed.
SITE_DOWN = False
SITE_DOWN_MESSAGE = ''
SITE_BACK_UP_AT = ''
READ_ONLY = False
NO_OI = False

###
# General GCD site settings

FRONT_PAGE_LANGUAGES = ('en', 'de', 'nl', 'sv')

DEFAULT_FROM_EMAIL = 'GCD Contact <contact@comics.org>'
EMAIL_NEW_ACCOUNTS_FROM = 'GCD New Accounts <new.accounts@comics.org>'
EMAIL_EDITORS = 'gcd-editor@googlegroups.com'
EMAIL_PRTEAM = 'pr-team@comics.org'
EMAIL_CONTACT = 'contact@comics.org'
EMAIL_INDEXING = 'GCD Online Indexing <no-reply@comics.org>'
CHAIRMAN = 'Daniel Nauschuetz'
EMAIL_CHAIRMAN = '%s <chair@comics.org>' % CHAIRMAN

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
RESERVE_NON_ISSUE_DAYS = 7
RESERVE_ISSUE_WEEKS = 3
RESERVE_ISSUE_INITIAL_WEEKS = 6

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

###
# My.comics.org settings

MYCOMICS = False

# Twitter Bootstrap
BOOTSTRAP3 = {
    'jquery_url': STATIC_URL + 'jquery/js/jquery.min.js',
    'base_url': STATIC_URL + 'bootstrap/',
    }

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
    import settings_local
    if hasattr(settings_local, '_modify'):
        settings_local._modify(globals())
except ImportError:
    pass

#################################################################################
# Code dependent on debug or maintenance flag states.
#################################################################################

if READ_ONLY or NO_OI:
    MIDDLEWARE_CLASSES += \
      ('apps.middleware.read_only.ReadOnlyMiddleware',)

