from django.contrib.auth.models import Group
from django.urls import reverse

from apps.forum.models import Post
from apps.forum.views import ROOTS_PER_PAGE

from .base import ForumTestCase


class EarlyReplyTests(ForumTestCase):
    """Replies dated before the post they answer, such as one sent with a wrong clock."""

    def test_a_reply_dated_before_its_parent_shows_under_it(self):
        """A reply dated before the post it answers is shown under it."""
        from datetime import timedelta

        reply = Post.objects.create(discussion=self.discussion, author=self.other, parent=self.post,
                                    content="Sent with a wrong clock", created_by=self.other,
                                    updated_by=self.other, ip_address="127.0.0.1")
        Post.all_objects.filter(pk=reply.pk).update(created_at=self.post.created_at - timedelta(hours=1))
        self.client.force_login(self.other)
        response = self.client.get(self.discussion.get_absolute_url())
        self.assertContains(response, "Sent with a wrong clock")
        self.assertContains(response, f'id="children-{self.post.pk}"')


class ThreadTests(ForumTestCase):
    """Posts of a topic: threads one level deep, pages, new reply notices, author roles and edit history."""

    def setUp(self):
        """Sign in as other."""
        super().setUp()
        self.client.force_login(self.other)

    def add_post(self, author, content, parent=None):
        """Add a post by the author to the topic, answering parent if given; return it."""
        return Post.objects.create(discussion=self.discussion, author=author, content=content, parent=parent,
                                   created_by=author, updated_by=author, ip_address="127.0.0.1")

    def test_replies_to_replies_stay_one_level_deep(self):
        """Replies to replies are listed one level deep, under the top-level post of their thread.

        Only a post answering a post below the top level says whom it answers.
        """
        reply = self.add_post(self.other, "Reply")
        deeper = self.add_post(self.author, "Deeper", parent=reply)
        deepest = self.add_post(self.other, "Deepest", parent=deeper)
        roots = self.client.get(self.discussion.get_absolute_url()).context["post_roots"]
        self.assertEqual([root.pk for root in roots], [self.post.pk, reply.pk])
        self.assertEqual([child.pk for child in roots[1].tree_children], [deeper.pk, deepest.pk])
        self.assertIsNone(roots[1].tree_children[0].reply_to)
        self.assertEqual(roots[1].tree_children[1].reply_to.pk, deeper.pk)

    def test_long_topics_are_paged_and_a_post_link_opens_its_page(self):
        """A long topic is paged; a post's link opens the page holding it, whose URL is the canonical one."""
        posts = [self.add_post(self.other, f"Reply {number}") for number in range(ROOTS_PER_PAGE + 5)]
        response = self.client.get(self.discussion.get_absolute_url())
        self.assertEqual(len(response.context["post_roots"]), ROOTS_PER_PAGE)
        self.assertContains(response, "Page 1 of 2")
        response = self.client.get(posts[-1].get_absolute_url())
        self.assertEqual(response.context["page_obj"].number, 2)
        self.assertContains(response, f'id="post-{posts[-1].pk}"')
        canonical = f"http://testserver{self.discussion.get_absolute_url()}?page=2"
        self.assertContains(response, f'<link rel="canonical" href="{canonical}">')

    def test_reader_hears_about_replies_from_others_only(self):
        """Polling for updates tells the reader about another user's reply, not about their own posts; the
        answer with news is a 286, which stops the polling."""
        url = reverse("forum:discussion-updates", args=[self.discussion.slug])
        self.client.force_login(self.author)
        self.assertEqual(self.client.get(url, {"after": self.post.pk}).content, b"")
        self.add_post(self.author, "Mine")
        self.assertEqual(self.client.get(url, {"after": self.post.pk}).content, b"")
        reply = self.add_post(self.other, "Theirs")
        response = self.client.get(url, {"after": self.post.pk})
        self.assertContains(response, "1 new reply", status_code=286)
        self.assertContains(response, reply.get_absolute_url(), status_code=286)

    def test_roles_are_shown_next_to_names(self):
        """Posts show their author's roles: Board for a board member, Moderator for a group moderator."""
        Group.objects.get_or_create(name="board")[0].user_set.add(self.author)
        self.main.moderators.add(self.other)
        self.add_post(self.other, "Reply")
        response = self.client.get(self.discussion.get_absolute_url())
        badges = {post.author.username: post.badges for post in response.context["post_roots"]}
        self.assertEqual(badges, {"author": ["Board"], "other": ["Moderator"]})

    def test_edited_post_shows_its_earlier_versions(self):
        """The history of an edited post shows its author both versions and the editor's name, but no IP
        address."""
        self.client.force_login(self.author)
        self.client.post(reverse("forum:post-edit", args=[self.post.pk]), {"content": "Second version"})
        response = self.client.get(reverse("forum:post-history", args=[self.post.pk]))
        self.assertContains(response, "Second version")
        self.assertContains(response, "First post")
        self.assertContains(response, f"edited by GCD user {self.author.pk}")
        self.assertNotContains(response, "127.0.0.1")

    def test_quote_and_reply_buttons_point_to_the_top_level_post(self):
        """The Quote button of a nested reply answers it within the thread of its top-level post."""
        reply = self.add_post(self.other, "Reply")
        deeper = self.add_post(self.other, "Deeper", parent=reply)
        self.client.force_login(self.author)
        response = self.client.get(self.discussion.get_absolute_url())
        self.assertContains(response, f"quotePost({deeper.pk}, {reply.pk}, 'GCD user {self.other.pk}')")
