import re
from html import escape, unescape
from html.parser import HTMLParser
from urllib.parse import urlsplit

from django import template
from django.utils.safestring import mark_safe
from markdownx.utils import markdownify

from ..utils import display_name as person_name, to_id

register = template.Library()

ALLOWED_TAGS = {
    "a",
    "blockquote",
    "br",
    "code",
    "em",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "hr",
    "li",
    "ol",
    "p",
    "pre",
    "strong",
    "ul",
}
VOID_TAGS = {"br", "hr"}


def _safe_href(value):
    """Whether a link may stay: relative, or http, https or mailto, and without C0 control characters."""
    value = value.strip()
    if any(ord(char) < 32 for char in value):
        return False
    try:
        parsed = urlsplit(value)
    except ValueError:
        return False
    return not parsed.scheme or parsed.scheme.lower() in {"http", "https", "mailto"}


class MarkdownSanitizer(HTMLParser):
    """Rebuild rendered Markdown with the allowed tags only; links keep just a safe href and their title."""

    def __init__(self):
        """Start an empty output, outside code; character references reach handle_data already decoded."""
        super().__init__(convert_charrefs=True)
        self.output = []
        self.code = 0

    def handle_starttag(self, tag, attrs):
        """Copy an allowed tag without attributes; links keep a safe href and title and open in a new tab."""
        if tag not in ALLOWED_TAGS:
            return
        self.code += tag == "code"
        rendered_attrs = []
        if tag == "a":
            for name, value in attrs:
                if name == "href" and value and _safe_href(value):
                    rendered_attrs.append(f'href="{escape(value, quote=True)}"')
                elif name == "title" and value:
                    rendered_attrs.append(f'title="{escape(value, quote=True)}"')
            rendered_attrs.extend(['rel="nofollow ugc noopener"', 'target="_blank"'])
        suffix = f" {' '.join(rendered_attrs)}" if rendered_attrs else ""
        self.output.append(f"<{tag}{suffix}>")

    def handle_startendtag(self, tag, attrs):
        """Treat a self-closing tag, such as <br />, as a start tag without an end tag."""
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag):
        """Close an allowed tag, except the void br and hr, and note when a <code> element ends."""
        if tag in ALLOWED_TAGS and tag not in VOID_TAGS:
            self.code = max(self.code - (tag == "code"), 0)
            self.output.append(f"</{tag}>")

    def handle_data(self, data):
        """Escape the text; in code, unescape it once more first, as Markdown escaped it a second time."""
        # Markdown escapes code once more, but the text was escaped before Markdown already.
        self.output.append(escape(unescape(data) if self.code else data))


QUOTE_DEPTH = re.compile(r"^((?:[ ]{0,3}>[ ]?)*)")
# "<https://…>", as mail programs write links: the brackets are not part of the address.
ANGLE_URL = re.compile(r"&lt;(https?://[^\s<>]+)>")


def close_quotes(text):
    """End a quote at a line with fewer ">", as email does; Markdown would carry the quote on."""
    lines, previous = [], 0
    for line in text.split("\n"):
        depth = QUOTE_DEPTH.match(line).group(1).count(">") if line.strip() else -1
        if 0 <= depth < previous:
            lines.append("> " * depth)
        lines.append(line)
        previous = max(depth, 0)
    return "\n".join(lines)


# Python-Markdown looks for the closing bracket from every "[", up to its "]", or through the rest of the
# text when it has none: 300 unclosed ones at the start of a long post take seconds. Past this many
# characters read in all (a few hundredths of a second) the brackets are plain text.
MAX_BRACKET_WORK = 300_000
BRACKET = re.compile(r"[\[\]]")


def bracket_work(text):
    """Characters Python-Markdown reads to match the brackets of the text: from each "[" to its "]", or to
    the end of the text when it has none."""
    opened, work = [], 0
    for match in BRACKET.finditer(text):
        if match.group() == "[":
            opened.append(match.start())
        elif opened:
            work += match.start() - opened.pop()
    return work + sum(len(text) - start for start in opened)


@register.filter
def safe_markdown(value):
    """Render Markdown and allow only a small, safe subset of generated HTML."""
    # "<" and "&" stay escaped, so the text cannot make tags; ">" starts quotes, as in email.
    text = escape((value or "").replace("\r\n", "\n"), quote=False).replace("&gt;", ">")
    if bracket_work(text) > MAX_BRACKET_WORK:
        # Past the bound the brackets are plain text: links in brackets are not made, bare links still are.
        text = text.replace("[", "&#91;")
    sanitizer = MarkdownSanitizer()
    sanitizer.feed(str(markdownify(close_quotes(ANGLE_URL.sub(r"\1", text)))))
    sanitizer.close()
    return mark_safe("".join(sanitizer.output))


@register.filter
def display_name(user):
    """The person's name as the forum shows it (utils.display_name), never the username."""
    return person_name(user)


@register.filter
def reply_count(post_count):
    """Replies in a topic: its post count less the first post; 0 when the count is not a number."""
    try:
        return max(int(post_count) - 1, 0)
    except (TypeError, ValueError):
        return 0


@register.filter
def record_type(value):
    """Type name of a GCD record, or of the record a DiscussionRecord points to."""
    model = value.content_type.model_class() if hasattr(value, "content_type_id") else type(value)
    return model._meta.verbose_name.title() if model else ""


@register.filter
def group_address(category):
    """Email address that starts a topic in the group."""
    from ..mail import group_address as address

    return address(category)


@register.inclusion_tag("forum/_record_discussions.html", takes_context=True)
def record_discussions(context, model_name, record):
    """Link from a GCD record page to the forum topics about the record."""
    from django.urls import NoReverseMatch, reverse

    from ..access import accessible_discussions, readable_categories
    from ..records import RECORD_TYPES, record_content_type

    user = context.get("user")
    if model_name not in RECORD_TYPES or not record or user is None:
        return {"show": False}
    # Record pages are also served where the forum is not mounted: with NO_OI and on my.comics.org.
    try:
        reverse("forum:index")
    except NoReverseMatch:
        return {"show": False}
    count = None
    # Visitors read no group unless the admin opened one: a count of 0 would not be true.
    if user.is_authenticated or readable_categories(user).exists():
        count = accessible_discussions(user).filter(
            records__content_type=record_content_type(model_name),
            records__object_id=record.pk).distinct().count()
    return {"show": True, "count": count, "key": model_name, "record": record}


@register.simple_tag
def record_type_choices():
    """Record types a topic can link to, for the record search."""
    from ..records import RECORD_TYPES, has_language, record_model

    choices = [(key, record_model(key)._meta.verbose_name.capitalize(), has_language(key)) for key in RECORD_TYPES]
    return sorted(choices, key=lambda choice: choice[1])


# Typography of rendered Markdown: posts, previews and earlier versions look the same.
PROSE_CLASSES = (
    "px-2 py-1 break-words [&_p]:mb-2 [&_ul]:list-disc [&_ul]:pl-5 [&_ol]:list-decimal [&_ol]:pl-5 "
    "[&_blockquote]:border-l-4 [&_blockquote]:border-gray-300 [&_blockquote]:pl-2 [&_blockquote]:text-gray-700 "
    "[&_pre]:overflow-x-auto [&_pre]:bg-stone-200 [&_pre]:p-2"
)


@register.simple_tag
def prose_classes():
    """The Tailwind classes of rendered Markdown, so posts, previews and earlier versions look the same."""
    return PROSE_CLASSES


@register.simple_tag(takes_context=True)
def record_search_languages(context):
    """Language filter of the record search: the user's GCD languages, else the group's language."""
    from apps.stddata.models import Language

    from ..models import Category
    from ..views import user_languages

    mine = user_languages(context["user"])
    form = context.get("form")
    category_id = form["category"].value() if form is not None and "category" in form.fields else None
    group_language = Category.objects.filter(pk=category_id).values_list("language", flat=True).first() \
        if to_id(category_id) is not None else ""
    if not group_language and context.get("discussion") is not None:
        group_language = context["discussion"].category.language
    default = "mine" if mine else group_language or ""
    return {"choices": list(Language.objects.order_by("name").values_list("code", "name")),
            "mine": mine, "default": default}


MAX_CARDS = 6


# What a card shows, loaded for all the cards at once: each card then costs one query, for its cover.
CARD_RELATED = {
    "series": ("publisher", "country", "language", "first_issue__series", "first_issue__variant_of__series"),
    "issue": ("series__publisher", "series__country", "series__language", "variant_of__series"),
}


def record_card_list(pairs):
    """Cards for (key, record) pairs, with the cover of issues and series."""
    from django.db.models import prefetch_related_objects

    from ..records import record_cover, record_details

    pairs = list(pairs)
    for key, lookups in CARD_RELATED.items():
        prefetch_related_objects([found for kind, found in pairs if kind == key], *lookups)
    return [{"record": found, "type": record_type(found), "details": record_details(key, found),
             "cover": record_cover(key, found)} for key, found in pairs]


@register.inclusion_tag("forum/_record_cards.html")
def record_cards(post):
    """Cards for the GCD records a post links to."""
    from ..records import records_in_text

    return {"cards": record_card_list(records_in_text(post.content, max_found=MAX_CARDS))}


@register.simple_tag
def forum_static(path):
    """The URL of a forum static file with its modification time, so browsers load a changed file at once.
    The time is the served file's: the collected copy in STATIC_ROOT when there is one (production), else
    the source the development server serves."""
    from os.path import exists, getmtime

    from django.conf import settings
    from django.contrib.staticfiles import finders
    from django.contrib.staticfiles.storage import staticfiles_storage
    from django.templatetags.static import static

    served = None
    if getattr(settings, "STATIC_ROOT", None):
        try:
            served = staticfiles_storage.path(path)
        except NotImplementedError:
            served = None
    found = served if served and exists(served) else finders.find(path)
    return f"{static(path)}?v={int(getmtime(found)) if found else 0}"


@register.simple_tag(takes_context=True)
def draft_published(context):
    """"1" once after a new topic was published (DiscussionCreateView sets the session flag), else "": the
    page then tells forum.js to drop the topic's draft. Any other page leaves the draft, so a post that
    failed or was cut short keeps its text."""
    request = context.get("request")
    session = getattr(request, "session", None)
    return "1" if session is not None and session.pop("forum_draft_published", False) else ""
