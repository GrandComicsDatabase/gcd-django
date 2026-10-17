"""Shared settings for supported development and CI environments."""

from os import environ

from settings import *  # noqa: F401,F403


ALLOWED_HOSTS = [
    '127.0.0.1',
    'localhost',
    '[::1]',
]

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': environ.get('MYSQL_DATABASE', 'gcd_dev'),
        'USER': environ.get('MYSQL_USER', 'gcd_dev'),
        'PASSWORD': environ.get('MYSQL_PASSWORD', 'gcd_dev'),
        'HOST': environ.get('MYSQL_HOST', '127.0.0.1'),
        'PORT': environ.get('MYSQL_PORT', '3306'),
        'ATOMIC_REQUESTS': True,
        'CONN_MAX_AGE': 0,
        'OPTIONS': {
            'charset': 'utf8mb4',
        },
    },
}

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'gcd-development',
    },
}

EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
FAKE_IMAGES = True
USE_ELASTICSEARCH = environ.get('USE_ELASTICSEARCH', 'false').lower() in {
    '1', 'true', 'yes', 'on'
}

HAYSTACK_CONNECTIONS['default']['URL'] = environ.get(  # noqa: F405
    'ELASTICSEARCH_URL', 'http://127.0.0.1:9200/'
)
RQ_QUEUES['default'].update({  # noqa: F405
    'HOST': environ.get('REDIS_HOST', 'localhost'),
    'PORT': int(environ.get('REDIS_PORT', '6379')),
    'PASSWORD': None,
})

if USE_ELASTICSEARCH:
    if 'django_rq' not in INSTALLED_APPS:  # noqa: F405
        INSTALLED_APPS += ('django_rq',)  # noqa: F405
    HAYSTACK_SIGNAL_PROCESSOR = (
        'haystack_rqueue.signals.RQueueSignalProcessor'
    )

SILENCED_SYSTEM_CHECKS = [
    'django_recaptcha.recaptcha_test_key_error',
    'fields.W903',
    'models.E025',
]
