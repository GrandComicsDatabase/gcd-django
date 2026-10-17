from datetime import timedelta
from io import StringIO

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from apps.forum.access import posting_limit
from apps.forum.database import parse_changeset, record_experts, trust_level
from apps.forum.models import (
    Category, Discussion, DiscussionChange, DiscussionRecord, Notification, RecordSubscription, TopicSubscription,
)
from apps.forum.records import record_content_type
from apps.oi import states
from apps.oi.models import CTYPES, Changeset, PublisherRevision

from .base import ForumTestCase


class DatabaseTestCase(ForumTestCase):
    """The test topic linked to a publisher, with helpers that make database changes and users."""

    def setUp(self):
        """Link the test topic to a new publisher."""
        super().setUp()
        self.publisher = self.make_publisher()
        self.link = DiscussionRecord.objects.create(
            discussion=self.discussion, content_type=record_content_type("publisher"),
            object_id=self.publisher.pk, created_by=self.author)

    def make_change(self, indexer, state=states.PENDING, publisher=None):
        """Create a changeset by the indexer in the given state, revising the linked or given publisher."""
        changeset = Changeset.objects.create(indexer=indexer, state=state, change_type=CTYPES["publisher"])
        PublisherRevision.objects.create(changeset=changeset, publisher=publisher or self.publisher,
                                         name="Forum publisher", country=self.publisher.country)
        return changeset

    def make_user(self, name):
        """Create a user with this username and the password x."""
        return get_user_model().objects.create_user(name, password="x")


class ErrorLoopTests(DatabaseTestCase):
    """Database changes linked to topics, from a reported error to the topic marked fixed."""

    def test_changes_to_linked_records_are_suggested_and_the_indexer_links_their_own(self):
        """Changes to the topic's records are suggested on its page, and their indexer can link them to it."""
        change = self.make_change(self.other)
        self.client.force_login(self.other)
        response = self.client.get(self.discussion.get_absolute_url())
        self.assertEqual([item.pk for item in response.context["suggested_changes"]], [change.pk])
        self.client.post(reverse("forum:change-link", args=[self.discussion.slug]), {"changeset": change.pk})
        self.assertTrue(DiscussionChange.objects.filter(discussion=self.discussion, changeset=change).exists())

    def test_others_cannot_link_changes_they_did_not_make(self):
        """A user without rights on the topic cannot link a change made by someone else."""
        change = self.make_change(self.author)
        stranger = self.make_user("stranger")
        self.client.force_login(stranger)
        response = self.client.post(reverse("forum:change-link", args=[self.discussion.slug]),
                                    {"changeset": f"/changeset/{change.pk}/compare/"})
        self.assertEqual(response.status_code, 403)

    def test_approved_change_marks_the_topic_fixed_once_and_tells_followers(self):
        """The forum_mail command marks the topic fixed after its change is approved, and tells followers."""
        TopicSubscription.objects.create(user=self.other, discussion=self.discussion)
        change = self.make_change(self.other)
        DiscussionChange.objects.create(discussion=self.discussion, changeset=change, linked_by=self.author)
        call_command("forum_mail", "--no-fetch", "--no-send", stdout=StringIO())
        self.assertIsNone(Discussion.objects.get(pk=self.discussion.pk).fixed_by_id)
        Changeset.objects.filter(pk=change.pk).update(state=states.APPROVED)
        call_command("forum_mail", "--no-fetch", "--no-send", stdout=StringIO())
        topic = Discussion.objects.get(pk=self.discussion.pk)
        self.assertEqual((topic.fixed_by_id, topic.status), (change.pk, Discussion.Status.RESOLVED))
        self.assertEqual(Notification.objects.filter(user=self.other, kind="fixed").count(), 1)
        self.client.force_login(self.other)
        response = self.client.get(topic.get_absolute_url())
        self.assertContains(response, "Fixed in the database by")

    def test_indexers_link_only_their_changes_to_the_topic_records(self):
        """An indexer cannot link their own change to a topic whose records it does not touch."""
        elsewhere = self.make_change(self.other, states.APPROVED, publisher=self.make_publisher("Elsewhere"))
        self.client.force_login(self.other)
        response = self.client.post(reverse("forum:change-link", args=[self.discussion.slug]),
                                    {"changeset": elsewhere.pk})
        self.assertEqual(response.status_code, 403)
        self.assertIsNone(Discussion.objects.get(pk=self.discussion.pk).fixed_by_id)

    def test_unlinking_the_fixing_change_reopens_the_topic(self):
        """Unlinking the change that marked the topic fixed clears the mark and reopens the topic."""
        change = self.make_change(self.other, states.APPROVED)
        self.client.force_login(self.author)
        self.client.post(reverse("forum:change-link", args=[self.discussion.slug]), {"changeset": change.pk})
        topic = Discussion.objects.get(pk=self.discussion.pk)
        self.assertEqual((topic.fixed_by_id, topic.status), (change.pk, Discussion.Status.RESOLVED))
        link = DiscussionChange.objects.get(discussion=topic)
        self.client.post(reverse("forum:change-unlink", args=[topic.slug, link.pk]))
        topic.refresh_from_db()
        self.assertEqual((topic.fixed_by_id, topic.status), (None, Discussion.Status.OPEN))

    def test_changes_parse_from_numbers_and_links(self):
        """A change is found by its number or by a link to its pages; a link to another page finds none."""
        change = self.make_change(self.other)
        self.assertEqual(parse_changeset(str(change.pk)), change)
        self.assertEqual(parse_changeset(f"https://www.comics.org/changeset/{change.pk}/compare/"), change)
        self.assertIsNone(parse_changeset("https://www.comics.org/series/1/"))


class ExpertTests(DatabaseTestCase):
    """The users with the most approved changes to a topic's records, shown as experts."""

    def test_indexers_with_most_approved_changes_are_suggested(self):
        """Indexers rank by approved changes to the records; pending ones and excluded users are left out."""
        busy, occasional = self.make_user("busy"), self.make_user("occasional")
        for _ in range(3):
            self.make_change(busy, states.APPROVED)
        self.make_change(occasional, states.APPROVED)
        self.make_change(occasional, states.PENDING)
        experts = record_experts([self.link])
        self.assertEqual([(item["user"].username, item["changes"]) for item in experts],
                         [("busy", 3), ("occasional", 1)])
        self.assertEqual(record_experts([self.link], exclude=[busy.pk])[0]["user"], occasional)

    def test_topic_page_lists_the_experts_by_name(self):
        """The topic page lists the experts by name, with no button that would claim to ask them."""
        busy = self.make_user("busy")
        self.make_change(busy, states.APPROVED)
        self.client.force_login(self.other)
        response = self.client.get(self.discussion.get_absolute_url())
        self.assertContains(response, "Who knows these records")
        self.assertContains(response, f"<span>GCD user {busy.pk}</span>")
        self.assertNotContains(response, "Ask them")


class RecordFollowTests(DatabaseTestCase):
    """Following a GCD record to hear about new topics about it."""

    def test_followers_of_a_record_hear_about_new_topics(self):
        """A new topic that links a followed record notifies the record's followers."""
        self.client.force_login(self.other)
        self.client.post(reverse("forum:record-follow", args=["publisher", self.publisher.pk]), {"follow": "1"})
        self.assertTrue(RecordSubscription.objects.filter(user=self.other).exists())
        self.client.force_login(self.author)
        self.client.post(reverse("forum:discussion-create"), {
            "category": self.main.pk, "title": "Another about it",
            "content": f"About https://www.comics.org/publisher/{self.publisher.pk}/"})
        note = Notification.objects.get(user=self.other)
        self.assertEqual((note.kind, note.post.discussion.title), ("record", "Another about it"))

    def test_a_follow_sent_twice_still_follows(self):
        """A second Follow sent before the page reloads keeps the record followed; Unfollow stops it."""
        url = reverse("forum:record-follow", args=["publisher", self.publisher.pk])
        self.client.force_login(self.other)
        self.client.post(url, {"follow": "1"})
        self.client.post(url, {"follow": "1"})
        self.assertEqual(RecordSubscription.objects.filter(user=self.other).count(), 1)
        self.client.post(url, {"follow": "0"})
        self.assertFalse(RecordSubscription.objects.filter(user=self.other).exists())
        self.assertEqual(self.client.post(url).status_code, 400)

    def test_followers_who_cannot_read_are_not_told(self):
        """Followers of a record are not told about a new topic on it in a group they cannot read."""
        RecordSubscription.objects.create(user=self.other, content_type=record_content_type("publisher"),
                                          object_id=self.publisher.pk)
        editor = Category.objects.get(slug="gcd-editor")
        editor.members.add(self.author)
        self.client.force_login(self.author)
        self.client.post(reverse("forum:discussion-create"), {
            "category": editor.pk, "title": "Editors about it",
            "content": f"About https://www.comics.org/publisher/{self.publisher.pk}/"})
        self.assertFalse(Notification.objects.filter(user=self.other).exists())


class SimilarTopicTests(DatabaseTestCase):
    """Topics similar to the one being written, by records and title words."""

    def test_topics_on_the_same_record_and_with_title_words_are_shown(self):
        """Topics on the same records or sharing title words are shown, and an unrelated title finds none."""
        self.make_topic("Wrong publication dates for Forum publisher", self.main, self.author)
        self.client.force_login(self.other)
        response = self.client.get(reverse("forum:similar"), {"title": "Publication dates wrong?"})
        self.assertContains(response, "Wrong publication dates for Forum publisher")
        response = self.client.get(reverse("forum:similar"),
                                   {"title": "x", "content": f"https://www.comics.org/publisher/{self.publisher.pk}/"})
        self.assertContains(response, self.discussion.title)
        self.assertNotContains(self.client.get(reverse("forum:similar"), {"title": "Nothing alike"}), "<li>")


class TrustTests(DatabaseTestCase):
    """Trust levels from approved changes and roles, and the posting limits they set."""

    def test_trust_grows_with_approved_changes(self):
        """Trust is 0 without approved changes and 1 after the first; editors and group moderators get 2."""
        self.assertEqual(trust_level(self.other), 0)
        self.make_change(self.other, states.APPROVED)
        self.assertEqual(trust_level(self.other), 1)
        Group.objects.get_or_create(name="editor")[0].user_set.add(self.author)
        self.assertEqual(trust_level(self.author), 2)
        coordinator = self.make_user("coordinator")
        self.main.moderators.add(coordinator)
        self.assertEqual(trust_level(coordinator), 2)

    @override_settings(FORUM_NEW_MAX_POSTS_PER_DAY=1, FORUM_MAX_POSTS_PER_DAY=5)
    def test_new_accounts_have_lower_limits(self):
        """A new account reaches its lower daily post limit, which its first approved change raises."""
        self.make_topic("Mine", self.main, self.other)
        self.assertIn("first approved change", posting_limit(self.other))
        self.make_change(self.other, states.APPROVED)
        self.assertIsNone(posting_limit(self.other))


class CardTests(DatabaseTestCase):
    """Cards of the GCD records that a post links to."""

    def test_links_to_records_in_a_post_become_cards(self):
        """A link to a record page in a reply shows the record as a card in the post."""
        self.client.force_login(self.other)
        self.client.post(reverse("forum:reply", args=[self.discussion.slug]), {
            "content": f"Look at https://www.comics.org/publisher/{self.publisher.pk}/"})
        response = self.client.get(self.discussion.get_absolute_url())
        self.assertContains(response, 'aria-label="GCD records in this post"')


class ConsensusTests(ForumTestCase):
    """The procedure of gcd-policy topics: agenda items, ballots and the consensus step."""

    def setUp(self):
        """Create a gcd-policy coordinator, agenda item, open ballot and a topic started four days ago."""
        super().setUp()
        from apps.voting.models import Agenda, AgendaItem, AgendaMailingList, MailingList, Topic, VoteType
        from django.contrib.auth.models import Permission

        self.policy = Category.objects.get(slug="gcd-policy")
        self.coordinator = get_user_model().objects.create_user("coordinator", password="x")
        self.policy.moderators.add(self.coordinator)
        permission = Permission.objects.get(codename="can_vote")
        self.agenda = Agenda.objects.create(name="Policy", permission=permission, quorum=2)
        mailing_list = MailingList.objects.create(address="gcd-policy@googlegroups.com")
        AgendaMailingList.objects.create(agenda=self.agenda, mailing_list=mailing_list)
        self.item = AgendaItem.objects.create(name="Story types", agenda=self.agenda, state=True)
        vote_type = VoteType.objects.first() or VoteType.objects.create(name="Pass / Fail")
        self.ballot = Topic.objects.create(name="Ballot on story types", agenda=self.agenda, vote_type=vote_type,
                                           author=self.coordinator, deadline=timezone.now() + timedelta(days=8),
                                           open=True)
        self.topic = self.make_topic("Story types", self.policy, self.author)
        Discussion.all_objects.filter(pk=self.topic.pk).update(created_at=timezone.now() - timedelta(days=4))
        self.topic.refresh_from_db()

    def test_group_page_lists_the_agenda_with_its_discussion(self):
        """The group page lists the open ballot and the agenda item, with a link to start its discussion."""
        self.client.force_login(self.other)
        response = self.client.get(self.policy.get_absolute_url())
        self.assertContains(response, "Story types")
        self.assertContains(response, f"agenda_item={self.item.pk}")
        self.assertContains(response, "Ballot on story types")

    def test_coordinator_links_the_ballot_and_readers_see_the_quorum(self):
        """A coordinator links the agenda item and ballot; the topic page shows the votes for the quorum."""
        self.client.force_login(self.coordinator)
        self.client.post(reverse("forum:agenda-link", args=[self.topic.slug]),
                         {"agenda_item": self.item.pk, "ballot": f"/voting/ballot/{self.ballot.pk}/"})
        self.topic.refresh_from_db()
        self.assertEqual((self.topic.agenda_item, self.topic.ballot), (self.item, self.ballot))
        response = self.client.get(self.topic.get_absolute_url())
        self.assertContains(response, "0 of 2 votes for the quorum")

    def test_a_closed_agenda_item_stays_linked_and_unknown_ones_are_refused(self):
        """Saving the ballot keeps a linked agenda item that has closed; an item off the group's agenda is
        refused with a message, and the link stays."""
        from apps.voting.models import AgendaItem

        Discussion.all_objects.filter(pk=self.topic.pk).update(agenda_item=self.item)
        AgendaItem.objects.filter(pk=self.item.pk).update(state=False)
        self.client.force_login(self.coordinator)
        page = self.client.get(self.topic.get_absolute_url())
        self.assertContains(page, f'<option value="{self.item.pk}" selected>')
        url = reverse("forum:agenda-link", args=[self.topic.slug])
        self.client.post(url, {"agenda_item": self.item.pk, "ballot": f"/voting/ballot/{self.ballot.pk}/"})
        self.topic.refresh_from_db()
        self.assertEqual((self.topic.agenda_item, self.topic.ballot), (self.item, self.ballot))
        response = self.client.post(url, {"agenda_item": 999999, "ballot": ""}, follow=True)
        self.assertContains(response, "Choose one of the group&#x27;s open agenda items.")
        self.assertEqual(Discussion.objects.get(pk=self.topic.pk).agenda_item, self.item)

    def test_consensus_passes_without_objections_and_an_objection_moves_to_a_vote(self):
        """Consensus is declared one week and one day after it is sought, not before, and the item passes."""
        self.client.force_login(self.coordinator)
        self.client.post(reverse("forum:consensus-seek", args=[self.topic.slug]))
        self.topic.refresh_from_db()
        self.assertIsNotNone(self.topic.consensus_sought_at)
        response = self.client.post(reverse("forum:consensus-declare", args=[self.topic.slug]))
        self.assertEqual(response.status_code, 400)
        Discussion.all_objects.filter(pk=self.topic.pk).update(
            consensus_sought_at=timezone.now() - timedelta(days=9))
        self.client.post(reverse("forum:consensus-declare", args=[self.topic.slug]))
        self.topic.refresh_from_db()
        self.assertEqual(self.topic.status, Discussion.Status.RESOLVED)
        self.assertContains(self.client.get(self.topic.get_absolute_url()), "Passed by consensus on")

    def test_objection_becomes_a_post_and_blocks_consensus(self):
        """An objection becomes a post and blocks consensus; the page says the item moves to a vote."""
        Discussion.all_objects.filter(pk=self.topic.pk).update(
            consensus_sought_at=timezone.now() - timedelta(days=9), consensus_sought_by=self.coordinator)
        self.client.force_login(self.other)
        self.client.post(reverse("forum:consensus-object", args=[self.topic.slug]), {"reason": "Too strict."})
        self.assertTrue(self.topic.posts.filter(content="**Objection:** Too strict.").exists())
        self.client.force_login(self.coordinator)
        response = self.client.post(reverse("forum:consensus-declare", args=[self.topic.slug]))
        self.assertEqual(response.status_code, 400)
        self.assertContains(self.client.get(self.topic.get_absolute_url()), "the item moves to a vote")

    def test_repeated_consensus_steps_post_once(self):
        """Seeking, objecting and declaring sent twice post once: the second request finds the step done."""
        self.client.force_login(self.coordinator)
        seek = reverse("forum:consensus-seek", args=[self.topic.slug])
        self.client.post(seek)
        self.assertEqual(self.client.post(seek).status_code, 400)
        Discussion.all_objects.filter(pk=self.topic.pk).update(
            consensus_sought_at=timezone.now() - timedelta(days=9))
        declare = reverse("forum:consensus-declare", args=[self.topic.slug])
        self.client.post(declare)
        self.assertEqual(self.client.post(declare).status_code, 400)
        self.assertEqual(self.topic.posts.filter(content__startswith="**Seeking consensus.**").count(), 1)
        self.assertEqual(self.topic.posts.filter(content="**Passed by consensus.**").count(), 1)
        other = self.make_topic("Another item", self.policy, self.author)
        Discussion.all_objects.filter(pk=other.pk).update(
            consensus_sought_at=timezone.now() - timedelta(days=1), consensus_sought_by=self.coordinator)
        self.client.force_login(self.other)
        for _ in range(2):
            self.client.post(reverse("forum:consensus-object", args=[other.slug]), {"reason": "Too strict."})
        self.assertEqual(other.posts.filter(content="**Objection:** Too strict.").count(), 1)

    @override_settings(FORUM_REVIEW_FIRST_POSTS=True)
    def test_objections_pass_the_review_and_the_limits(self):
        """A new member, whose first post a moderator reads, cannot object at once; nor can anyone over the
        daily posting limit. Neither objection is posted nor stops the consensus."""
        Discussion.all_objects.filter(pk=self.topic.pk).update(
            consensus_sought_at=timezone.now() - timedelta(days=1), consensus_sought_by=self.coordinator)
        newcomer = get_user_model().objects.create_user("newcomer", password="x")
        self.client.force_login(newcomer)
        url = reverse("forum:consensus-object", args=[self.topic.slug])
        self.client.post(url, {"reason": "Spam https://example.com"})
        self.assertFalse(self.topic.posts.filter(author=newcomer).exists())
        self.assertContains(self.client.get(self.topic.get_absolute_url()),
                            "first message is read by a moderator first")
        with override_settings(FORUM_REVIEW_FIRST_POSTS=False, FORUM_NEW_MAX_POSTS_PER_DAY=0):
            self.client.force_login(self.other)
            self.client.post(url, {"reason": "Too strict."})
        self.assertFalse(self.topic.objections.exists())

    def test_consensus_waits_three_days_and_only_coordinators_seek_it(self):
        """Only coordinators seek consensus, and only after three days of discussion."""
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(reverse("forum:consensus-seek", args=[self.topic.slug])).status_code, 403)
        fresh = self.make_topic("Fresh item", self.policy, self.author)
        self.client.force_login(self.coordinator)
        self.assertEqual(self.client.post(reverse("forum:consensus-seek", args=[fresh.slug])).status_code, 400)


    def test_an_agenda_item_keeps_one_discussion(self):
        """Linking a topic to an agenda item that already has a discussion is refused with a message."""
        Discussion.all_objects.filter(pk=self.topic.pk).update(agenda_item=self.item)
        other = self.make_topic("Story types again", self.policy, self.author)
        self.client.force_login(self.coordinator)
        response = self.client.post(reverse("forum:agenda-link", args=[other.slug]),
                                    {"agenda_item": self.item.pk, "ballot": ""}, follow=True)
        self.assertContains(response, "That agenda item already has a discussion")
        self.assertIsNone(Discussion.objects.get(pk=other.pk).agenda_item)
