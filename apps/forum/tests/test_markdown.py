from django.test import SimpleTestCase

from apps.forum.templatetags.forum_tags import safe_markdown


class MarkdownSafetyTests(SimpleTestCase):
    """Safety of safe_markdown against raw HTML and unsafe links."""

    def test_raw_html_and_unsafe_link_are_sanitized(self):
        """A <script> tag comes out as escaped text, and a javascript: link loses its address."""
        rendered = str(safe_markdown('<script>alert(1)</script> [bad](javascript:alert(1))'))
        self.assertNotIn("<script", rendered)
        self.assertNotIn("javascript:", rendered)
        self.assertIn("&lt;script&gt;", rendered)
