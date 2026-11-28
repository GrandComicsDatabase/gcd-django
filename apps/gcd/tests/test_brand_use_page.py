"""The page of a brand use names its own record."""

from urllib.parse import quote

import pytest

from apps.gcd.models import Brand, BrandUse, Publisher
from apps.gcd.templatetags.display import absolute_url
from apps.stddata.models import Country


@pytest.fixture
def use(db):
    """An emblem in use at a publisher, with no issue."""
    country = Country.objects.get_or_create(
        code='zz-use', defaults={'name': 'Testland'})[0]
    publisher = Publisher.objects.create(name='Test Publisher',
                                         country=country, year_began=1965)
    emblem = Brand.objects.create(name='Test Emblem', year_began=1965)
    return BrandUse.objects.create(publisher=publisher, emblem=emblem,
                                   year_began=1965)


def _page(client, use):
    """Return the page of `use` as a visitor sees it."""
    response = client.get(use.get_absolute_url())
    assert response.status_code == 200
    return response.content.decode()


def test_the_bottom_bar_repeats_the_header(client, use):
    """The bar under the list names the emblem and the publisher."""
    header = '%s at %s' % (absolute_url(use.emblem),
                           absolute_url(use.publisher))
    # A browser shows any run of spaces and line breaks as one space.
    text = ' '.join(_page(client, use).split())

    assert text.count(header) == 2


def test_the_error_report_is_about_the_brand_use(client, use):
    """The "let us know" link gives the brand use as the subject."""
    page = _page(client, use)

    assert '&amp;short_desc=%s"' % quote(str(use)) in page
