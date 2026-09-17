"""Health check for the local development stack."""

from django.db import connection
from django.http import JsonResponse


def health(request):
    """Confirm that Django can execute a query against its database."""
    with connection.cursor() as cursor:
        cursor.execute('SELECT 1')
        cursor.fetchone()

    return JsonResponse({'status': 'ok'})
