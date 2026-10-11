from django.test import SimpleTestCase

from apps.forum.templatetags.forum_tags import safe_markdown


class MarkdownSafetyTests(SimpleTestCase):
    def test_raw_html_and_unsafe_link_are_sanitized(self):
        rendered = str(safe_markdown('<script>alert(1)</script> [bad](javascript:alert(1))'))
        self.assertNotIn("<script", rendered)
        self.assertNotIn("javascript:", rendered)
        self.assertIn("&lt;script&gt;", rendered)
