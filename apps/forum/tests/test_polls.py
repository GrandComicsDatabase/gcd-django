from datetime import timedelta
from unittest import mock

from django.urls import reverse
from django.utils import timezone

from apps.forum.models import Category, Discussion, Poll, PollVote

from .base import ForumTestCase


class PollTests(ForumTestCase):
    """Polls in topics: their options, who may vote, one vote each, and closing them."""

    def create_topic(self, category=None, **poll):
        """As author, start "Which cover?" with a poll and any extra form fields, in gcd-main by default."""
        self.client.force_login(self.author)
        data = {"category": (category or self.main).pk, "title": "Which cover?", "content": "Vote please",
                "poll_question": "Which cover is best?", "poll_options": "Cover A\nCover B\nCover A\n"}
        data.update(poll)
        self.client.post(reverse("forum:discussion-create"), data)
        return Discussion.objects.get(title="Which cover?")

    def vote(self, user, topic, *options):
        """Vote for these options of the topic's poll as the user; return the response."""
        self.client.force_login(user)
        return self.client.post(reverse("forum:poll-vote", args=[topic.slug]),
                                {"option": [option.pk for option in options]})

    def test_topic_with_a_poll_and_one_vote_per_user(self):
        """Repeated options show once; a user's new vote replaces the old one, and two at once are refused."""
        topic = self.create_topic()
        a, b = topic.poll.options.all()
        self.assertEqual((a.text, b.text), ("Cover A", "Cover B"))
        self.vote(self.other, topic, a)
        self.vote(self.other, topic, b)
        self.assertEqual(list(PollVote.objects.values_list("option__text", flat=True)), ["Cover B"])
        self.assertEqual(self.vote(self.other, topic, a, b).status_code, 302)
        self.assertEqual(PollVote.objects.count(), 1)
        response = self.client.get(topic.get_absolute_url())
        self.assertContains(response, "1 voter")
        self.assertContains(response, "Change my vote")

    def test_a_poll_needs_two_options(self):
        """A poll with a single option is refused: the form asks for 2 to 20, and no poll is saved."""
        self.client.force_login(self.author)
        response = self.client.post(reverse("forum:discussion-create"), {
            "category": self.main.pk, "title": "Bad poll", "content": "x",
            "poll_question": "Yes?", "poll_options": "Only one"})
        self.assertContains(response, "A poll needs from 2 to 20 different options.")
        self.assertFalse(Poll.objects.exists())

    def test_only_members_vote_in_a_board_poll(self):
        """A user outside gcd-board gets 403 voting in its poll, which says that only members vote."""
        board = Category.objects.get(slug="gcd-board")
        board.members.add(self.author)
        topic = self.create_topic(board)
        option = topic.poll.options.first()
        self.assertEqual(self.vote(self.other, topic, option).status_code, 403)
        response = self.client.get(topic.get_absolute_url())
        self.assertContains(response, "Only members of gcd-board vote in this poll.")

    def test_closed_poll_takes_no_votes(self):
        """A vote on a poll past its closing time, or closed by the topic's author, comes back to the topic
        with a message, and is not counted."""
        topic = self.create_topic()
        Poll.objects.filter(discussion=topic).update(closes_at=timezone.now() - timedelta(minutes=1))
        response = self.vote(self.other, topic, topic.poll.options.first())
        self.assertContains(self.client.get(response.url), "The poll closed before your vote arrived.")
        Poll.objects.filter(discussion=topic).update(closes_at=None)
        self.client.force_login(self.author)
        self.client.post(reverse("forum:poll-close", args=[topic.slug]))
        self.vote(self.other, topic, topic.poll.options.first())
        self.assertFalse(PollVote.objects.exists())

    def test_closing_time_is_utc_and_in_the_future(self):
        """The form says the closing time is UTC, and refuses one in the past."""
        self.client.force_login(self.author)
        self.assertContains(self.client.get(reverse("forum:discussion-create")), "Closes on (UTC)")
        past = (timezone.now() - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M")
        response = self.client.post(reverse("forum:discussion-create"), {
            "category": self.main.pk, "title": "Late poll", "content": "Vote", "poll_question": "Which?",
            "poll_options": "A\nB", "poll_closes_at": past})
        self.assertContains(response, "Choose a closing time in the future (UTC).")
        self.assertFalse(Discussion.objects.filter(title="Late poll").exists())

    def test_a_vote_that_arrives_after_the_poll_closed_is_not_counted(self):
        """A vote checked while the poll was open, but locked in after it closed, is refused with a message."""
        topic = self.create_topic()
        with mock.patch.object(Poll, "is_open", side_effect=[True, False]):
            response = self.vote(self.other, topic, topic.poll.options.first())
        self.assertFalse(PollVote.objects.exists())
        self.assertContains(self.client.get(response.url), "The poll closed before your vote arrived.")

    def test_others_cannot_close_the_poll(self):
        """Another user, not the topic's author, gets 403 closing its poll."""
        topic = self.create_topic()
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(reverse("forum:poll-close", args=[topic.slug])).status_code, 403)
