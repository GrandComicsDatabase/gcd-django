"""GCD records a discussion can be about, found from their page links."""
from urllib.parse import urlsplit

from django.apps import apps
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
    name = RECORD_TYPES.get(key)
    return apps.get_model("gcd", name) if name else None


def record_key(content_type):
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
    path = urlsplit(text.strip()).path
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
    return ContentType.objects.get_for_model(record_model(key))
