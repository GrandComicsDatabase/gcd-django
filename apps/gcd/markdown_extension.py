from html import escape
from html.parser import HTMLParser

from django.shortcuts import get_object_or_404
from django.http import Http404

from markdown.extensions import Extension
from markdown.treeprocessors import Treeprocessor
from markdown.inlinepatterns import InlineProcessor
from markdown.postprocessors import Postprocessor
from xml.etree.ElementTree import Element

import markdown
import nh3

from django.conf import settings
from django.utils.safestring import mark_safe


MARKDOWN_CLASSES = {
    'p': 'pt-4',
    'ul': 'list-disc list-outside ps-8',
    'ol': 'list-decimal list-outside ps-8',
}
BLOCK_TAGS = {
    'blockquote', 'dd', 'div', 'dl', 'dt', 'h1', 'h2', 'h3', 'h4', 'h5',
    'h6', 'hr', 'li', 'ol', 'p', 'pre', 'ul', 'table', 'thead', 'tbody',
    'tfoot', 'tr', 'td', 'th', 'caption',
}
HTML_CLEANER = nh3.Cleaner(
    tags=BLOCK_TAGS | {'a', 'abbr', 'b', 'br', 'code', 'del', 'em', 'i',
                       'img', 's', 'span', 'strong', 'sub', 'sup'},
    attributes={'a': {'href', 'title'}, 'abbr': {'title'},
                'img': {'src', 'alt', 'title', 'width', 'height'},
                'td': {'colspan', 'rowspan'},
                'th': {'colspan', 'rowspan', 'scope'}},
    allowed_classes={tag: set(classes.split())
                     for tag, classes in MARKDOWN_CLASSES.items()},
    url_schemes={'http', 'https', 'mailto'})


def render_markdown(value):
    """Return safe block HTML without changing stored or exported source."""
    if not value:
        return ''
    html = markdown.markdown(
        str(value), extensions=settings.MARKDOWNX_MARKDOWN_EXTENSIONS,
        extension_configs=getattr(
            settings, 'MARKDOWNX_MARKDOWN_EXTENSION_CONFIGS', {}))
    # Safety must not depend on a deployment retaining the preview extension.
    return mark_safe(HTML_CLEANER.clean(html))


class InlineMarkdownParser(HTMLParser):
    """Keep link/formatting markup, with line boundaries instead of blocks."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.lists = []

    def boundary(self):
        if self.parts and self.parts[-1] != '<br>':
            self.parts.append('<br>')

    def handle_starttag(self, tag, attrs):
        if tag in BLOCK_TAGS:
            self.boundary()
            if tag in {'ol', 'ul'}:
                self.lists.append(0 if tag == 'ol' else None)
            if tag == 'li':
                if self.lists and self.lists[-1] is not None:
                    self.lists[-1] += 1
                    self.parts.append('%s. ' % self.lists[-1])
                else:
                    self.parts.append('• ')
        else:
            self.parts.append(self.get_starttag_text())

    def handle_endtag(self, tag):
        if tag in BLOCK_TAGS:
            self.boundary()
            if tag in {'ol', 'ul'} and self.lists:
                self.lists.pop()
        else:
            self.parts.append('</%s>' % tag)

    def handle_data(self, data):
        # Markdown's HTML formatting newlines are not additional visual breaks.
        if data.strip() or '\n' not in data:
            self.parts.append(escape(data))


def render_markdown_inline(value):
    """Render an annotation inside phrasing content, never block elements.

    Full detail views use render_markdown. Compact annotations retain links
    and emphasis, but represent paragraphs and list items as separate lines.
    """
    parser = InlineMarkdownParser()
    parser.feed(render_markdown(value))
    parser.close()
    while parser.parts and parser.parts[-1] == '<br>':
        parser.parts.pop()
    return mark_safe(''.join(parser.parts))


class SafeHTMLExtension(Extension):
    """Sanitize after Markdown has restored raw HTML and generated links."""

    def extendMarkdown(self, md):
        md.postprocessors.register(SafeHTMLPostprocessor(md), 'safe_html', 0)


class SafeHTMLPostprocessor(Postprocessor):
    def run(self, text):
        return HTML_CLEANER.clean(text)


GCD_REFERENCE_RE = r'\[gcd_link_([^\]]+)\]\((\d+)\)'
GCD_REFERENCE_LINK_NAME_RE = r'\[gcd_link_name_([^\]]+)\]\((\d+)\)\{([^\}]+)\}'

# Regular expression for matching URLs
URL_RE = r'(?<!\]\()(https?:\/\/[^\s\)\]\}]+)'


class URLInlineProcessor(InlineProcessor):
    """Process URLs and convert them to links."""
    def handleMatch(self, m, data):
        url = m.group(1)
        el = Element('a')
        el.set('href', url)
        el.text = url
        return el, m.start(0), m.end(0)


class URLExtension(Extension):
    """Add support for auto-converting URLs to links."""
    def extendMarkdown(self, md):
        md.inlinePatterns.register(
            URLInlineProcessor(URL_RE, md),
            'autolink_urls', 180)


class GCDReferenceInlineProcessor(InlineProcessor):
    """Process [gcd_link_object](id) references and convert to links."""
    def handleMatch(self, m, data):
        from apps.gcd.models import Issue, Story
        from apps.oi.views import DISPLAY_CLASSES
        # Check if the regex match has two or three groups
        if len(m.groups()) == 3:
            ref_type = m.group(1)   # The object type
            ref_id = m.group(2)     # The ID
            link_name = m.group(3)  # Custom link text
        else:
            ref_type = m.group(1)   # The object type
            ref_id = m.group(2)     # The ID
            link_name = None

        el = Element('a')

        if ref_type in ['issue', 'issue_with_date']:
            try:
                issue = get_object_or_404(Issue, id=ref_id)
            except Http404:
                # If the issue is not found, return the text
                if ref_type == 'issue_with_date':
                    ref_type = 'issue'
                el.text = f"No corresponding GCD object found: {ref_type}" \
                          f" with id {ref_id}"
                return el, m.start(0), m.end(0)
            url = issue.get_absolute_url()
            if link_name:
                el.text = link_name
            else:
                el.text = str(issue.full_name())
            if ref_type == 'issue_with_date' and issue.publication_date:
                # append the publication date to the text
                el.text += f" ({issue.publication_date})"
        elif ref_type in ['story', 'story_with_date']:
            try:
                story = get_object_or_404(Story, id=ref_id)
            except Http404:
                # If the story is not found, return the text
                if ref_type == 'story_with_date':
                    ref_type = 'story'
                el.text = f"No corresponding GCD object found: {ref_type}" \
                          f" with id {ref_id}"
                return el, m.start(0), m.end(0)
            url = story.get_absolute_url()
            if link_name:
                el.text = link_name
            else:
                el.text = str(story.issue.full_name())
            if ref_type == 'story_with_date' and story.issue.publication_date:
                # append the publication date to the text
                el.text += f" ({story.issue.publication_date})"
        elif ref_type in DISPLAY_CLASSES:
            try:
                object = get_object_or_404(DISPLAY_CLASSES[ref_type],
                                           id=ref_id)
            except Http404:
                # If the object is not found, return the text
                el.text = f"No corresponding GCD object found: {ref_type}" \
                          f" with id {ref_id}"
                return el, m.start(0), m.end(0)
            url = object.get_absolute_url()
            if link_name:
                el.text = link_name
            else:
                try:
                    el.text = str(object.object_markdown_name())
                except AttributeError:
                    url = ''
                    el.text = f'Type {ref_type.capitalize()} not supported.'
        else:
            # Return original text if ref_type is not recognized
            url = "#"  # Set a placeholder URL for unrecognized types
            el.text = f"Not a recognized GCD object: {ref_type}"

        el.set('href', url)
        return el, m.start(0), m.end(0)


class GCDFieldExtension(Extension):
    """Add support for [gcd_link_object](id) references."""

    def extendMarkdown(self, md):
        md.inlinePatterns.register(
            GCDReferenceInlineProcessor(GCD_REFERENCE_RE, md),
            'object_and_id', 175)


class GCDFieldLinkNameExtension(Extension):
    """Add support for [gcd_link_name_object](id){link_name} references."""

    def extendMarkdown(self, md):
        md.inlinePatterns.register(
            GCDReferenceInlineProcessor(GCD_REFERENCE_LINK_NAME_RE, md),
            'object_and_name_and_id', 175)


class TailwindExtension(Extension):
    """Add tailwind classes to certain tags"""

    def extendMarkdown(self, md):
        md.treeprocessors.register(
            TailwindTreeProcessor(md), "tailwind", 20)


class TailwindTreeProcessor(Treeprocessor):
    """Walk the root node and modify any discovered tag"""

    classes = MARKDOWN_CLASSES

    def run(self, root):
        # Keep track of which tags we've already seen
        seen_tags = set()

        for node in root.iter():
            # Only apply classes if this is not the first appearance of the tag
            tag_classes = self.classes.get(node.tag)
            if tag_classes:
                # Skip the first occurrence of this tag type
                if node.tag == 'p' and node.tag not in seen_tags:
                    seen_tags.add(node.tag)
                    continue

                # Apply classes to subsequent occurrences
                node.attrib["class"] = tag_classes
