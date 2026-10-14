"""Atom feeds of the lists anyone can read, for feed readers and list archives."""
from django.contrib.auth.models import AnonymousUser
from django.contrib.syndication.views import Feed
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils.feedgenerator import Atom1Feed

from .access import accessible_discussions, readable_categories
from .models import Post
from .templatetags.forum_tags import safe_markdown
from .utils import display_name

FEED_ITEMS = 30


class LatestTopicsFeed(Feed):
    """The newest topics of the groups anyone can read, as an Atom feed."""

    feed_type = Atom1Feed
    title = "GCD Forum: new topics"
    subtitle = "New topics in the public lists of the GCD forum."

    def link(self):
        """The web page of the feed: the forum home."""
        return reverse("forum:index")

    def items(self):
        """The FEED_ITEMS newest topics that visitors can read."""
        return (accessible_discussions(AnonymousUser()).select_related("author__indexer", "category")
                .order_by("-created_at")[:FEED_ITEMS])

    def item_title(self, item):
        """The group name in brackets, then the topic title, as in the subjects of the forum's emails."""
        return f"[{item.category.name}] {item.title}"

    def item_description(self, item):
        """The text of the topic's first published post, rendered as on the forum; empty if there is none."""
        first = item.posts.order_by("pk").first()
        return safe_markdown(first.content) if first else ""

    def item_author_name(self, item):
        """The name of the topic's author."""
        return display_name(item.author)

    def item_pubdate(self, item):
        """When the topic was started."""
        return item.created_at


class GroupPostsFeed(Feed):
    """The newest posts of one group anyone can read, as an Atom feed."""

    feed_type = Atom1Feed

    def get_object(self, request, slug):
        """The group, among those visitors can read; any other slug is a 404."""
        return get_object_or_404(readable_categories(AnonymousUser()), slug=slug)

    def title(self, obj):
        """The feed title: "GCD Forum:" and the group name."""
        return f"GCD Forum: {obj.name}"

    def subtitle(self, obj):
        """A line saying the feed carries every new post of the group."""
        return f"Every new post in {obj.name}."

    def link(self, obj):
        """The web page of the feed: the group's page."""
        return obj.get_absolute_url()

    def items(self, obj):
        """The FEED_ITEMS newest published posts in the group's topics."""
        return (Post.objects.filter(discussion__in=accessible_discussions(AnonymousUser()).filter(category=obj))
                .select_related("author__indexer", "discussion").order_by("-created_at")[:FEED_ITEMS])

    def item_title(self, item):
        """The topic title for its first post, and "Re: " before it for the replies."""
        first = item.discussion.posts.order_by("pk").values_list("pk", flat=True).first()
        return item.discussion.title if item.pk == first else f"Re: {item.discussion.title}"

    def item_description(self, item):
        """The text of the post, rendered as on the forum."""
        return safe_markdown(item.content)

    def item_author_name(self, item):
        """The name of the post's author."""
        return display_name(item.author)

    def item_pubdate(self, item):
        """When the post was written."""
        return item.created_at
