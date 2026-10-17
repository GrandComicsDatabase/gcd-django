from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from apps.forum.models import Category, Discussion, Post


# The review of new members' first posts has its own tests (test_review.py).
@override_settings(FORUM_REVIEW_FIRST_POSTS=False)
class ForumTestCase(TestCase):
    """Users and one topic in gcd-main; the groups come from the data migration."""

    def setUp(self):
        """Create the users author and other, and a topic by author in gcd-main with its first post."""
        users = get_user_model().objects
        self.author = users.create_user("author", password="test-password")
        self.other = users.create_user("other", password="test-password")
        self.main = Category.objects.get(slug="gcd-main")
        self.discussion = self.make_topic("A forum topic", self.main, self.author)
        self.post = self.discussion.posts.get()

    def make_topic(self, title, category, author, content="First post"):
        """Create a topic and its first post in the database: nobody follows it and nobody is notified."""
        discussion = Discussion.objects.create(
            title=title, category=category, author=author,
            created_by=author, updated_by=author, ip_address="127.0.0.1")
        Post.objects.create(
            discussion=discussion, author=author, content=content,
            created_by=author, updated_by=author, ip_address="127.0.0.1")
        return discussion

    def make_publisher(self, name="Forum publisher"):
        """Create a publisher of country zz, the unknown country loaded by stddata, made if missing."""
        from apps.gcd.models import Publisher
        from apps.stddata.models import Country

        country, _ = Country.objects.get_or_create(code="zz", defaults={"name": "Forum test"})
        return Publisher.objects.create(name=name, country=country)
