# Django settings for gcd project.
from os.path import abspath, dirname, join
from os import environ # helps determine MEDIA_URL.

# disable on production!
DEBUG          = True
TEMPLATE_DEBUG = DEBUG

BETA = False

# Set to True to avoid hitting comics.org for every cover image.
# If True, the same cover image will be used for every issue.
FAKE_COVER_IMAGES = False

# absolute path to the directory that holds templates.
TEMPLATE_DIRS = ( abspath(join(dirname(__file__), 'templates')), )

# absolute path to the directory that holds media.
# URL that handles the media served from MEDIA_ROOT.
MEDIA_ROOT = abspath(join(dirname(__file__), 'media'))
MEDIA_URL = "/site_media/"

# Database settings. Override yours in a settings_local.py
# if you're not gonna stick with these development defaults.
DATABASE_ENGINE   = 'mysql'
DATABASE_NAME     = 'gcdonline'
DATABASE_USER     = 'gcdonline'
DATABASE_PASSWORD = ''
DATABASE_HOST     = ''
DATABASE_PORT     = ''

# middleware settings, LocalMiddleware is for internationalisation
MIDDLEWARE_CLASSES = (
   'django.contrib.csrf.middleware.CsrfMiddleware',
   'django.contrib.sessions.middleware.SessionMiddleware',
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
    'apps.gcd',
    'apps.oi',
)

# Used to provide a seed in secret-key hashing algorithms.
SECRET_KEY = 'th0lnu%wjs_8=r4u_km3shvogzd%1n)t-5eosi964g0ek+a4p+'

# Callables that know how to import templates from various sources.
TEMPLATE_LOADERS = (
    'django.template.loaders.filesystem.load_template_source',
    'django.template.loaders.app_directories.load_template_source',
)

TEMPLATE_CONTEXT_PROCESSORS = (
    'django.core.context_processors.auth',
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

# Corresponds to the django_site database table. As far
# as I know, we won't be using this for the GCD.
SITE_ID = 1

# Local time zone for this installation. Choices can be found here:
# http://www.postgresql.org/docs/8.1/static/datetime-keywords.html#DATETIME-TIMEZONE-SET-TABLE
TIME_ZONE = 'UTC'

DEFAULT_FROM_EMAIL = 'GCD Contact <gcd-contact@googlegroups.com>'
EMAIL_NEW_ACCOUNTS_FROM = 'GCD New Accounts <new.accounts@comics.org>'
EMAIL_EDITORS = 'gcd-editor@googlegroups.com'
EMAIL_CONTACT = 'gcd-contact@googlegroups.com'
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

SITE_URL = 'http://www.comics.org/'
SITE_NAME = 'Grand Comics Database'

# image directories
IMAGE_SERVER_URL = 'http://images.comics.org/'
COVERS_DIR = '/img/gcd/covers_by_id/'
NEW_COVERS_DIR = '/img/gcd/new_covers/'

BLOCKED_DOMAINS = ('mailinator.com', 'mintemail.com')

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
