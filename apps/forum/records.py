"""GCD records a discussion can be about, found from their page links."""
import re
from urllib.parse import urlsplit

from django.apps import apps
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.urls import Resolver404, resolve

# Record pages served as /<key>/<id>/ by the show_<key> route.
RECORD_TYPES = {
    "publisher": "Publisher",
    "indicia_publisher": "IndiciaPublisher",
    "brand_group": "BrandGroup",
    "brand": "Brand",
    "printer": "Printer",
    "indicia_printer": "IndiciaPrinter",
    "series": "Series",
    "issue": "Issue",
    "story_arc": "StoryArc",
    "creator": "Creator",
    "character": "Character",
    "group": "Group",
    "feature": "Feature",
    "universe": "Universe",
    "multiverse": "Multiverse",
    "award": "Award",
}


def record_model(key):
    """The model of a record type key, such as Series for "series"; None for an unknown key."""
    name = RECORD_TYPES.get(key)
    return apps.get_model("gcd", name) if name else None


def record_key(content_type):
    """The record type key of a gcd content type, such as "series"; None for any other content type."""
    for key, name in RECORD_TYPES.items():
        if content_type.app_label == "gcd" and content_type.model == name.lower():
            return key
    return None


def get_record(key, object_id):
    """Return the live record, or None for unknown types and deleted records."""
    model = record_model(key)
    if model is None:
        return None
    record = model._default_manager.filter(pk=object_id).first()
    if record is None or getattr(record, "deleted", False):
        return None
    return record


def parse_record_link(text):
    """Map a pasted GCD page link, or its path, to (key, record)."""
    try:
        path = urlsplit(text.strip()).path
    except ValueError:  # a host followed by full-width punctuation is invalid under NFKC
        return None
    if not path:
        return None
    if not path.endswith("/"):
        path += "/"
    try:
        match = resolve(path)
    except Resolver404:
        return None
    key = (match.url_name or "").removeprefix("show_")
    object_id = match.kwargs.get(f"{key}_id")
    if key not in RECORD_TYPES or object_id is None or len(match.kwargs) != 1:
        return None
    record = get_record(key, object_id)
    return (key, record) if record else None


def record_content_type(key):
    """The ContentType of a known record type key, as topic links to records and record follows store it."""
    return ContentType.objects.get_for_model(record_model(key))


# Issues and series show a cover: an issue its own, a series its first issue's.
COVER_TYPES = ("issue", "series")
# The icon of the other records: people, companies, or a book for anything else.
GLYPHS = {"creator": "person", "character": "person", "group": "person", "publisher": "building",
          "indicia_publisher": "building", "brand_group": "building", "brand": "building",
          "printer": "building", "indicia_printer": "building"}


def record_glyph(key):
    """The icon of a record type for records shown without a cover: "person", "building" or "book"."""
    return GLYPHS.get(key, "book")


def record_cover(key, record):
    """The small cover image of an issue, or of a series' first issue; "" when there is none."""
    from apps.gcd.models.cover import ZOOM_SMALL
    from apps.gcd.views.covers import get_image_tag

    issue = record if key == "issue" else record.first_issue if key == "series" else None
    cover = issue.active_covers().first() if issue is not None else None
    return get_image_tag(cover, str(issue), ZOOM_SMALL) if cover else ""


# Searching records by name ---------------------------------------------------
#
# The catalog is large (hundreds of thousands of series), so a search narrows by
# language and by what the query says: a year ("Spider-Man 1983") keeps records
# active or first published that year, and "#12" (or a final number for issues)
# is an issue number. Names are compared without spaces and punctuation, so
# "spiderman" finds "Spider-Man"; the database collation ignores case and accents.
# Exact names come first, then names that start with the query, then the rest,
# each by number of issues, as a measure of how well known a record is.

NAME_FIELDS = {"creator": "gcd_official_name"}
LANGUAGE_FIELDS = {"series": "language", "issue": "series__language", "story_arc": "language",
                   "character": "language", "group": "language", "feature": "language"}
SEPARATORS = ("-", " ", ".", "'", ":", ",")
YEAR = re.compile(r"^(18|19|20)\d\d$")
SEARCH_LIMIT = 10
SERIES_FOR_ISSUES = 50
POOL = 60
WIDE_POOL = 500
# Shorter queries are matched only at the start of the name, which the name indexes serve; the scan for
# the query anywhere in the normalized name reads the whole table, so it waits for a third character.
MIN_CONTAINS = 3
# GCD sort names drop leading articles and put surnames first ("Avengers, The", "Kirby, Jack"),
# so a query also matches the start of the sort name.
SORT_FIELD = "sort_name"
# How often a record without an issue count appears in stories, to rank the well known first.
POPULARITY = {"creator": "creator_names__storycredit", "character": "character_names__storycharacter",
              "group": "group_names__storygroup"}


# "More results" pages through the first records only, so no request can rank the whole catalog.
MAX_OFFSET = WIDE_POOL


def has_language(key):
    """Whether the record search can filter records of the type by language (an issue by its series')."""
    return key in LANGUAGE_FIELDS


def normalize(text):
    """The text as the search compares it: no separators, no case, no accents. Lowercase, not casefold:
    casefold spells "ß" as "ss", and the database compares the names one character at a time."""
    import unicodedata

    text = "".join(char for char in unicodedata.normalize("NFKD", text) if not unicodedata.combining(char))
    for separator in SEPARATORS:
        text = text.replace(separator, "")
    return text.lower()


def _normalized(field):
    """The field as a database expression without separators, so "spiderman" matches "Spider-Man"."""
    from django.db.models import F, Value
    from django.db.models.functions import Replace

    expression = F(field)
    for separator in SEPARATORS:
        expression = Replace(expression, Value(separator), Value(""))
    return expression


def parse_query(query):
    """Split a query into name, year and issue number."""
    words, year, number = [], None, None
    tokens = query.split()
    for token in tokens:
        if token.startswith("#") and len(token) > 1:
            number = token[1:]
        elif year is None and len(tokens) > 1 and YEAR.match(token):
            year = int(token)
        else:
            words.append(token)
    return " ".join(words)[:100], year, number


def _field_names(model):
    """Names of the model's fields and relations, to check what a record type has before using it."""
    return {field.name for field in model._meta.get_fields()}


def _ranked(key, text, languages, year, count):
    """Up to count records of one type matching the name, best first."""
    from django.db.models import Count, Q

    model = record_model(key)
    field = NAME_FIELDS.get(key, "name")
    names = _field_names(model)
    queryset = model.objects.filter(deleted=False)
    if languages and key in LANGUAGE_FIELDS:
        queryset = queryset.filter(**{f"{LANGUAGE_FIELDS[key]}__code__in": languages})
    if year and "year_began" in names:
        queryset = queryset.filter(Q(year_ended__gte=year) | Q(year_ended=None), year_began__lte=year)
    elif year and "year_first_published" in names:
        queryset = queryset.filter(year_first_published=year)
    # Records with an issue count are taken best known first; the others are counted below.
    order = ("-issue_count", "pk") if "issue_count" in names else ("pk",)
    pool = max(count, POOL if "issue_count" in names else WIDE_POOL)
    needle = normalize(text)
    starts = Q(**{f"{field}__istartswith": text})
    if SORT_FIELD in names:
        starts |= Q(**{f"{SORT_FIELD}__istartswith": text})
    ids = list(queryset.filter(starts).order_by(*order).values_list("pk", flat=True)[:pool])
    if len(needle) >= MIN_CONTAINS:
        ids += list(queryset.annotate(normalized_name=_normalized(field)).filter(normalized_name__icontains=needle)
                    .exclude(pk__in=ids).order_by(*order).values_list("pk", flat=True)[:pool])
    related = [name for name in ("publisher", "country", "language") if name in names]
    records = model.objects.filter(pk__in=ids).select_related(*related)
    if key in POPULARITY:
        records = records.annotate(popularity=Count(POPULARITY[key]))

    def rank(record):
        """Sort key: exact name, then name starting with the query, then the rest (the sort name counts too);
        within a tier, the most issues or story appearances first, then the earliest year, then the name."""
        name = normalize(getattr(record, field))
        tier = 0 if name == needle else 1 if name.startswith(needle) else 2
        if SORT_FIELD in names:
            # The part before the comma: "Avengers" of "Avengers, The", "Kirby" of "Kirby, Jack".
            sort_name = normalize(getattr(record, SORT_FIELD).split(",")[0])
            tier = min(tier, 0 if sort_name == needle else 1 if sort_name.startswith(needle) else 2)
        weight = getattr(record, "issue_count", None) or getattr(record, "popularity", 0) or 0
        return (tier, -weight, getattr(record, "year_began", None) or 9999, name)

    return sorted(records, key=rank)[:count]


def search_records(key, query, languages=(), limit=SEARCH_LIMIT, offset=0):
    """A page of records of one type for a query; returns (records, more)."""
    model = record_model(key)
    text, year, number = parse_query(" ".join(query.split()))
    if key == "issue" and number is None:
        rest, _, last = text.rpartition(" ")
        if rest and any(char.isdigit() for char in last):
            text, number = rest, last
    if model is None or offset >= MAX_OFFSET or len(normalize(text)) < 2 or (key == "issue" and not number):
        return [], False
    if key == "issue":
        series = _ranked("series", text, languages, year, SERIES_FOR_ISSUES)
        order = {record.pk: position for position, record in enumerate(series)}
        issues = sorted(model.objects.filter(deleted=False, series_id__in=order, number=number)
                        .select_related("series__publisher", "series__country", "series__language",
                                        "variant_of__series"),
                        key=lambda issue: (order[issue.series_id], issue.sort_code))
        return issues[offset:offset + limit], len(issues) > offset + limit and offset + limit < MAX_OFFSET
    found = _ranked(key, text, languages, year, offset + limit + 1)
    return found[offset:offset + limit], len(found) > offset + limit and offset + limit < MAX_OFFSET


def record_details(key, record):
    """What tells apart records with the same name: years, publisher, country, language, size."""
    source = record.series if key == "issue" else record
    details = []
    if getattr(source, "year_began", None):
        details.append(f"{source.year_began}–{source.year_ended or ''}")
    elif getattr(source, "year_first_published", None):
        details.append(f"first published {source.year_first_published}")
    if getattr(source, "disambiguation", ""):
        details.append(source.disambiguation)
    if getattr(source, "publisher_id", None):
        details.append(str(source.publisher))
    if getattr(source, "country_id", None):
        details.append(source.country.code.upper())
    if getattr(source, "language_id", None):
        details.append(source.language.name)
    if key != "issue" and getattr(source, "issue_count", None):
        details.append(f"{source.issue_count} issues")
    return " · ".join(details)


LINK = re.compile(r"https?://[^\s<>()\[\]\"']+")


# Distinct GCD links read in one message: each costs a lookup, so a post costs the same whatever its length.
MAX_LINKS = 50


def records_in_text(text, limit=MAX_LINKS, max_found=None):
    """GCD records whose page links appear in a message, as (key, record) pairs, from its first `limit` GCD
    links, and at most max_found of them when given (other GCD links, such as changes, do not count)."""
    # comics.org and the hosts this site answers to (localhost in development).
    hosts = {"comics.org", "www.comics.org", urlsplit(settings.SITE_URL).hostname}
    hosts |= {host for host in settings.ALLOWED_HOSTS if host and "*" not in host and not host.startswith(".")}
    found, seen, read = [], set(), 0
    for link in dict.fromkeys(LINK.findall(text or "")):
        try:
            host = urlsplit(link).hostname or ""
        except ValueError:  # a host followed by full-width punctuation is invalid under NFKC
            continue
        if host not in hosts:
            continue
        read += 1
        if read > limit:
            break
        record = parse_record_link(link.rstrip(".,;:!?"))
        if record and (record[0], record[1].pk) not in seen:
            seen.add((record[0], record[1].pk))
            found.append(record)
            if len(found) == max_found:
                break
    return found


# Words too common to tell topics apart when looking for similar titles.
STOP_WORDS = {
    "about", "after", "also", "been", "does", "from", "have", "into", "issue", "issues", "more", "some",
    "that", "their", "there", "these", "they", "this", "what", "when", "where", "which", "with", "would",
    "series", "comic", "comics", "question", "please", "thanks",
}
