"""Health check for the local development stack."""

import logging

from django.db import DatabaseError, connection
from django.http import JsonResponse


logger = logging.getLogger(__name__)


def health(request):
    """Confirm that Django can execute a query against its database."""
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
            cursor.fetchone()
    except DatabaseError:
        logger.exception('Database health check failed')
        return JsonResponse({'status': 'error'}, status=503)

    return JsonResponse({'status': 'ok'})
