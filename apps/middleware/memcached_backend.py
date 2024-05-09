from pickle import HIGHEST_PROTOCOL

from django.core.cache.backends.memcached import BaseMemcachedCache


class MemcachedCache(BaseMemcachedCache):
    """An implementation of a cache binding using python-memcached."""

    def __init__(self, server, params):
        import memcache
        super().__init__(
          server,
          params,
          library=memcache,
          value_not_found_exception=ValueError
        )
        self._options = {"pickleProtocol": HIGHEST_PROTOCOL} | self._options
