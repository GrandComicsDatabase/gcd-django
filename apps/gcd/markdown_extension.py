from django.shortcuts import get_object_or_404
from django.http import Http404

from markdown.extensions import Extension
from markdown.treeprocessors import Treeprocessor
from markdown.inlinepatterns import InlineProcessor
from xml.etree.ElementTree import Element

from apps.gcd.models import Issue, Story

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
                el.text = str(object.object_markdown_name())
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

    classes = {
        "p": "pt-4",
        "ul": "list-disc list-outside ps-8",
        "ol": "list-decimal list-outside ps-8",
    }

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
