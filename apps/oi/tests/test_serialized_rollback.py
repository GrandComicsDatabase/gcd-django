import pytest
from django.db import connection

# the test models are registered once their module is imported, as in a
# run of the whole suite
from apps.oi.tests import dummy_models  # noqa: F401


@pytest.mark.django_db
def test_the_database_serializes_with_the_test_models_registered():
    """
    A transactional test with serialized_rollback makes the setup of the
    database read every table that it can migrate.
    """
    assert connection.creation.serialize_db_to_string()
