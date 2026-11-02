import os
import shutil
import tempfile
import time

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import RequestFactory, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from apps.forum.access import accessible_discussions, readers
from apps.forum.models import Category, DiscussionRecord, Suspension, attachment_storage
from apps.forum.records import record_content_type, search_records
from apps.forum.templatetags.forum_tags import forum_static
from apps.forum.utils import get_client_ip

from .base import ForumTestCase


class ProductionTests(ForumTestCase):
    """Costs and settings that matter on www.comics.org: queries per page, access checks, proxies, files."""

    def test_readers_match_the_access_rules_for_many_users_at_once(self):
        """readers gives, in a few queries, the users accessible_discussions lets read a topic: members of a
        members-only group and staff, and the author of a report in a write-only group, even suspended
        from another group but not from this one; inactive users never."""
        users = get_user_model().objects
        member = users.create_user("member", password="x")
        staff = users.create_user("staff", password="x", is_staff=True)
        gone = users.create_user("gone", password="x", is_active=False)
        editor = Category.objects.get(slug="gcd-editor")
        editor.members.add(member, gone)
        error = Category.objects.get(slug="gcd-error")
        topics = [self.discussion, self.make_topic("Editors", editor, member),
                  self.make_topic("My report", error, self.other)]
        Suspension.objects.create(user=self.other, category=self.main, reason="x", created_by=staff)
        everyone = [self.author, self.other, member, staff, gone]
        for topic in topics:
            expected = {user.pk for user in everyone
                        if user.is_active and accessible_discussions(user).filter(pk=topic.pk).exists()}
            with CaptureQueriesContext(connection) as queries:
                found = readers(topic, [user.pk for user in everyone])
            self.assertEqual(found, expected, topic.title)
            self.assertLessEqual(len(queries), 8)

    def test_topic_lists_load_linked_records_per_type(self):
        """A topic list takes as many queries with eleven topics linked to records as with one."""
        def link(topic):
            """Link the topic to a new publisher."""
            DiscussionRecord.objects.create(discussion=topic, content_type=record_content_type("publisher"),
                                            object_id=self.make_publisher(f"Publisher {topic.pk}").pk,
                                            created_by=self.author)

        link(self.discussion)
        self.client.force_login(self.other)
        self.client.get(reverse("forum:index"))
        with CaptureQueriesContext(connection) as one_topic:
            self.client.get(reverse("forum:index"))
        for number in range(10):
            link(self.make_topic(f"Topic {number}", self.main, self.author))
        with self.assertNumQueries(len(one_topic)):
            self.client.get(reverse("forum:index"))

    def test_short_record_queries_do_not_scan_the_catalog(self):
        """A query of two letters is matched at the start of names only, without the scan of whole tables."""
        with CaptureQueriesContext(connection) as queries:
            search_records("series", "xq")
        self.assertFalse(any("REPLACE(" in query["sql"] for query in queries))

    def test_similar_topics_send_only_the_links_of_the_message(self):
        """The title box asks for similar topics with the message's links, not the whole message."""
        self.client.force_login(self.other)
        import re

        page = self.client.get(reverse("forum:discussion-create")).content.decode()
        title = re.search(r'<input[^>]*id="id_title"[^>]*>', page).group(0)
        self.assertIn('hx-vals="js:{content: forumLinkText(&quot;id_content&quot;)}"', title)
        self.assertNotIn("hx-include", title)

    def test_client_address_behind_proxies_is_counted_from_the_right(self):
        """With two trusted proxies, the address is the second entry from the right, never the client's own."""
        request = RequestFactory().get("/", REMOTE_ADDR="127.0.0.1",
                                       HTTP_X_FORWARDED_FOR="203.0.113.9, 198.51.100.7, 162.158.1.1")
        with override_settings(FORUM_TRUST_X_FORWARDED_FOR=2):
            self.assertEqual(get_client_ip(request), "198.51.100.7")
        with override_settings(FORUM_TRUST_X_FORWARDED_FOR=False):
            self.assertEqual(get_client_ip(request), "127.0.0.1")

    def test_static_version_follows_the_served_file(self):
        """The version of forum.js comes from the collected copy when STATIC_ROOT holds one."""
        folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, folder, ignore_errors=True)
        os.makedirs(os.path.join(folder, "forum"))
        collected = os.path.join(folder, "forum", "forum.js")
        with open(collected, "w") as handle:
            handle.write("// collected")
        stamp = int(time.time()) - 3600
        os.utime(collected, (stamp, stamp))
        with override_settings(STATIC_ROOT=folder):
            self.assertTrue(forum_static("forum/forum.js").endswith(f"?v={stamp}"))

    @override_settings(MEDIA_ROOT="/srv/gcd/media/")
    def test_default_attachments_folder_is_beside_the_media(self):
        """With MEDIA_ROOT ending in "/", the default attachments folder is next to it, not inside it."""
        from django.conf import settings

        if hasattr(settings, "FORUM_ATTACHMENTS_DIR"):
            with override_settings():
                del settings.FORUM_ATTACHMENTS_DIR
                self.assertEqual(attachment_storage().location, "/srv/gcd/forum_attachments")
        else:
            self.assertEqual(attachment_storage().location, "/srv/gcd/forum_attachments")
