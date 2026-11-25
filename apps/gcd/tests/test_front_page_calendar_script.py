"""The script of the creators calendar needs the calendar on the page."""

import pytest


@pytest.mark.django_db
def test_no_calendar_script_on_a_page_without_the_calendar(client, settings):
    settings.USE_TEMPLATESADMIN = False

    response = client.get('/')

    assert response.status_code == 200
    html = response.content.decode()
    assert 'id="daily_creators"' not in html
    assert 'getElementById("daily_creators")' not in html
