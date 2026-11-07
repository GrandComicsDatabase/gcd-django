from django import forms
from django.core.exceptions import ValidationError
from django.db import transaction
from django.forms.utils import ErrorList
from django.urls import reverse
from django.utils import timezone

from .models import Category, Discussion, DiscussionRecord, Poll, PollOption, Post, Report
from .access import needs_review, notify_review, postable_categories, posting_limit
from .attachments import ACCEPT, MAX_FILES, detect, max_size, save_attachments
from .records import parse_record_link, record_content_type


INPUT_CLASS = "w-full border-gray-400"
# The text of a message sits in the framed message box (_editor.html), which draws the border and the focus.
EDITOR_CLASS = "block w-full resize-y border-0 !px-3 !py-2 focus:ring-0"
WRITING_HELP = "Markdown is supported."
# Longest message, as on Discourse: every view renders the text again.
MAX_CONTENT = 32000


def editor_widget(rows, placeholder, draft=True):
    """The textarea of the message box; with draft, forum.js keeps the unsent text in the browser."""
    attrs = {"rows": rows, "class": EDITOR_CLASS, "placeholder": placeholder}
    if draft:
        attrs["data-draft"] = ""
    return forms.Textarea(attrs=attrs)


class ForumErrorList(ErrorList):
    """Django's error list in red-700, 6.5:1 on white; the site's .errorlist red is 2.8:1."""

    def __init__(self, initlist=None, error_class=None, renderer=None, field_id=None):
        """Add text-red-700 to the classes of the list, after any class Django passes."""
        super().__init__(initlist, " ".join(filter(None, [error_class, "text-red-700"])), renderer, field_id)


class ForumForm:
    """Mixin for the forum's forms: their errors render with ForumErrorList."""

    def __init__(self, *args, **kwargs):
        """Use ForumErrorList unless the caller passes another error_class."""
        kwargs.setdefault("error_class", ForumErrorList)
        super().__init__(*args, **kwargs)


class RecordLinksField(forms.CharField):
    """Links to GCD record pages, one per line, as (key, record) pairs."""

    widget = forms.Textarea(attrs={"rows": 3, "class": INPUT_CLASS,
                                   "placeholder": "https://www.comics.org/series/1234/"})

    def clean(self, value):
        """Return the records the lines link to, each once; any other non-blank line is an error."""
        value = super().clean(value)
        records, invalid, seen = [], [], set()
        for line in (value or "").splitlines():
            if not line.strip():
                continue
            found = parse_record_link(line)
            if found is None:
                invalid.append(line.strip())
            elif (found[0], found[1].pk) not in seen:
                seen.add((found[0], found[1].pk))
                records.append(found)
        if invalid:
            raise ValidationError(
                "Not a link to a GCD record page: %(links)s",
                params={"links": ", ".join(invalid)})
        return records


class MultipleFileInput(forms.ClearableFileInput):
    """A file input that takes several files and gives the field all of them, as a list."""

    allow_multiple_selected = True


def with_descriptions(form):
    """The checked files of the form's attachments with the description written for each in the message
    box ("attachment_description", one per file, in order), cut to 200 characters."""
    descriptions = form.data.getlist("attachment_description") if hasattr(form.data, "getlist") else []
    return [(*item, (descriptions[index] if index < len(descriptions) else "").strip()[:200])
            for index, item in enumerate(form.cleaned_data.get("attachments") or [])]


class AttachmentsField(forms.FileField):
    """Up to MAX_FILES images or PDFs, as (name, data, (content type, extension)) once checked."""

    def __init__(self, **kwargs):
        """Default to an optional multi-file input, the label "Images or PDFs" and the limits as help text."""
        kwargs.setdefault("label", "Images or PDFs")
        kwargs.setdefault("required", False)
        kwargs.setdefault("help_text", f"Up to {MAX_FILES} files: JPEG, PNG, GIF or WebP images and PDFs, "
                                       f"{max_size() // (1024 * 1024)} MB each.")
        kwargs.setdefault("widget", MultipleFileInput(attrs={"accept": ACCEPT, "class": "text-sm"}))
        super().__init__(**kwargs)

    # The limits the message box checks before sending; the server checks every file again.
    @property
    def max_files(self):
        """The most files per message, passed to the message box as data-max-files."""
        return MAX_FILES

    @property
    def max_bytes(self):
        """The largest file in bytes, passed to the message box as data-max-bytes."""
        return max_size()

    def clean(self, data, initial=None):
        """Check the number of files, then each one's size and type, read from its content, not its name."""
        uploads = [upload for upload in (data if isinstance(data, (list, tuple)) else [data]) if upload]
        if len(uploads) > MAX_FILES:
            raise ValidationError(f"Attach at most {MAX_FILES} files.")
        checked = []
        for upload in uploads:
            upload = super().clean(upload, initial)
            if upload.size > max_size():
                raise ValidationError(f"{upload.name}: larger than {max_size() // (1024 * 1024)} MB.")
            content = upload.read()
            try:
                kind = detect(content)
            except ValidationError as error:
                raise ValidationError(f"{upload.name}: {error.message}.")
            checked.append((upload.name, content, kind))
        return checked


def save_records(discussion, records, user):
    """Link the records to the topic; return the links that are new."""
    created_links = []
    for key, record in records:
        link, created = DiscussionRecord.objects.get_or_create(
            discussion=discussion, content_type=record_content_type(key),
            object_id=record.pk, defaults={"created_by": user})
        if created:
            created_links.append(link)
    return created_links


class DiscussionForm(ForumForm, forms.ModelForm):
    """A new topic: group, title, first message with any files, and optionally a poll and an agenda item."""

    content = forms.CharField(
        label="Message", help_text=WRITING_HELP, max_length=MAX_CONTENT,
        widget=editor_widget(10, "Write your message. Link GCD records with the search below."))
    attachments = AttachmentsField()
    poll_question = forms.CharField(
        label="Poll question", required=False, max_length=200,
        widget=forms.TextInput(attrs={"class": INPUT_CLASS}))
    poll_options = forms.CharField(
        label="Options", required=False, help_text="One per line, from 2 to 20.",
        widget=forms.Textarea(attrs={"rows": 4, "class": INPUT_CLASS}))
    poll_multiple = forms.BooleanField(label="Voters can choose more than one option", required=False)
    # Set by "Start the discussion" on an agenda item of the group page.
    agenda_item = forms.ModelChoiceField(queryset=None, required=False, widget=forms.HiddenInput(), error_messages={
        "invalid_choice": "This agenda item is closed or no longer exists: open New topic again from the group page."})
    poll_closes_at = forms.DateTimeField(
        label="Closes on (UTC)", required=False,
        help_text="UTC, the time of the GCD servers. Leave empty to close the poll by hand.",
        widget=forms.DateTimeInput(attrs={"type": "datetime-local", "class": INPUT_CLASS}))

    class Meta:
        """Edit a Discussion's category and title as forum inputs, the title of at most 200 characters."""

        model = Discussion
        fields = ("category", "title")
        widgets = {
            "title": forms.TextInput(attrs={"class": INPUT_CLASS, "maxlength": 200}),
            "category": forms.Select(attrs={"class": INPUT_CLASS}),
        }

    def __init__(self, *args, user=None, ip_address=None, **kwargs):
        """Keep the user and IP address; offer only the groups the user can post in and the agenda items not
        closed, and look up similar topics while the title is typed."""
        super().__init__(*args, **kwargs)
        self.user = user
        self.ip_address = ip_address
        self.fields["category"].label = "Group"
        self.fields["category"].empty_label = None
        self.fields["category"].queryset = postable_categories(user)
        from apps.voting.models import AgendaItem

        self.fields["agenda_item"].queryset = AgendaItem.objects.exclude(state=False)
        # While the title is typed, similar topics are shown, like similar questions on Stack Overflow.
        self.fields["title"].widget.attrs.update({
            "hx-get": reverse("forum:similar"), "hx-trigger": "input changed delay:600ms",
            # Only the links of the message, which find the topics about the same records: the whole text
            # in the URL would be refused as too long by the proxies.
            "hx-vals": 'js:{content: forumLinkText("id_content")}', "hx-target": "#similar-topics",
            "hx-sync": "this:replace",
            "autocomplete": "off"})

    def clean(self):
        """Refuse a topic over the daily limits; a poll needs a question and 2 to 20 different options."""
        cleaned_data = super().clean()
        limit = posting_limit(self.user, new_topic=True)
        if limit:
            raise ValidationError(limit)
        options = list(dict.fromkeys(
            line.strip()[:200] for line in cleaned_data.get("poll_options", "").splitlines() if line.strip()))
        if cleaned_data.get("poll_question") and not 2 <= len(options) <= 20:
            self.add_error("poll_options", "A poll needs from 2 to 20 different options.")
        elif options and not cleaned_data.get("poll_question"):
            self.add_error("poll_question", "Write the question of the poll.")
        closes_at = cleaned_data.get("poll_closes_at")
        if closes_at and cleaned_data.get("poll_question") and closes_at <= timezone.now():
            self.add_error("poll_closes_at", "Choose a closing time in the future (UTC).")
        cleaned_data["poll_options"] = options
        item, category = cleaned_data.get("agenda_item"), cleaned_data.get("category")
        if item and category:
            from .procedure import agenda_items_for

            if not agenda_items_for(category).filter(pk=item.pk).exists():
                self.add_error("agenda_item", "This agenda item is not on the agenda of the chosen group: "
                                              "start its discussion from its group's page.")
            elif Discussion.all_objects.filter(agenda_item=item, is_deleted=False).exists():
                self.add_error("agenda_item", "This agenda item already has a discussion: reply there.")
        return cleaned_data

    @transaction.atomic
    def save(self, commit=True):
        """In one transaction, create the topic, its poll if any, its first post and files, then publish the
        post or ask for its review; commit must be True."""
        if not commit:
            raise ValueError("DiscussionForm must be saved with commit=True.")
        discussion = super().save(commit=False)
        discussion.author = self.user
        discussion.created_by = self.user
        discussion.updated_by = self.user
        discussion.ip_address = self.ip_address
        discussion.agenda_item = self.cleaned_data.get("agenda_item")
        discussion.awaiting_review = needs_review(self.user, discussion.category)
        discussion.save()
        if self.cleaned_data.get("poll_question"):
            poll = Poll.objects.create(
                discussion=discussion, question=self.cleaned_data["poll_question"],
                multiple=self.cleaned_data["poll_multiple"], closes_at=self.cleaned_data["poll_closes_at"])
            PollOption.objects.bulk_create([
                PollOption(poll=poll, text=text, position=position)
                for position, text in enumerate(self.cleaned_data["poll_options"])])
        post = Post.objects.create(
            discussion=discussion,
            author=self.user,
            content=self.cleaned_data["content"],
            created_by=self.user,
            updated_by=self.user,
            ip_address=self.ip_address,
            awaiting_review=discussion.awaiting_review,
        )
        save_attachments(post, with_descriptions(self))
        if post.awaiting_review:
            notify_review(post)
        else:
            from .activity import publish

            # publish links the topic to the GCD records the message links to.
            publish(post)
        return discussion


class PostForm(ForumForm, forms.ModelForm):
    """A reply in a topic: text, any files and, when it answers a post, that post."""

    # A plain textarea: the markdownx editor needs scripts the forum pages don't load.
    content = forms.CharField(help_text=WRITING_HELP, max_length=MAX_CONTENT,
                              widget=editor_widget(6, "Write your reply. Link GCD records with the search below."))
    parent = forms.ModelChoiceField(
        queryset=Post.objects.none(), required=False, widget=forms.HiddenInput(), error_messages={
            "invalid_choice": "The post you were answering was removed: use “Reply to the topic instead” "
                              "and send again."})
    attachments = AttachmentsField()

    class Meta:
        """Edit a Post's content and parent."""

        model = Post
        fields = ("content", "parent")

    def __init__(self, *args, discussion=None, **kwargs):
        """Accept as parent only the published posts of the topic."""
        super().__init__(*args, **kwargs)
        self.discussion = discussion
        if discussion:
            self.fields["parent"].queryset = Post.objects.filter(discussion=discussion)

    def clean_parent(self):
        """Refuse a parent post of another topic."""
        parent = self.cleaned_data.get("parent")
        if parent and parent.discussion_id != self.discussion.pk:
            raise ValidationError("The parent post belongs to another discussion.")
        return parent


class DiscussionEditForm(ForumForm, forms.ModelForm):
    """Change a topic's title and link it to more GCD records."""

    # Filled by the record search; shown only when a line is not a record link, so it can be fixed.
    records = RecordLinksField(label="Link GCD records", required=False,
                               widget=forms.Textarea(attrs={"class": INPUT_CLASS, "rows": 3}))

    class Meta:
        """Edit a Discussion's title as a forum input of at most 200 characters."""

        model = Discussion
        fields = ("title",)
        widgets = {"title": forms.TextInput(attrs={"class": INPUT_CLASS, "maxlength": 200})}

    def __init__(self, *args, user=None, **kwargs):
        """Keep the user, who is recorded as linking the records."""
        super().__init__(*args, **kwargs)
        self.user = user

    @transaction.atomic
    def save(self, commit=True):
        """Save the title and link the records atomically, notifying the followers of newly linked ones."""
        from .activity import notify_record_followers

        discussion = super().save(commit=False)
        # Only the title and its editor: a move, a close or a removal made meanwhile stays.
        discussion.save(update_fields=("title", "updated_by", "updated_at"))
        new_links = save_records(discussion, self.cleaned_data["records"], self.user)
        first = discussion.posts.order_by("pk").first()
        if first is not None:
            notify_record_followers(first, new_links)
        return discussion


class MoveForm(ForumForm, forms.Form):
    """Move a topic to another group the user can post in; authors never widen who reads it."""

    category = forms.ModelChoiceField(
        label="Move to", queryset=None, empty_label=None,
        widget=forms.Select(attrs={"class": INPUT_CLASS}))

    def __init__(self, *args, user=None, discussion=None, **kwargs):
        """Offer the groups the user can post in, except the topic's current group. Moderators of the group
        move a topic anywhere; its author cannot move it out of a members-only group, and from a group
        for GCD users only to groups not open to visitors, so replies are never shown to wider readers."""
        super().__init__(*args, **kwargs)
        groups = postable_categories(user).exclude(pk=discussion.category_id)
        current = discussion.category
        if not current.is_moderator(user):
            if current.read_access == Category.Access.MEMBERS:
                groups = groups.none()
            elif current.read_access == Category.Access.USERS:
                groups = groups.exclude(read_access=Category.Access.PUBLIC)
        self.fields["category"].queryset = groups


class PostEditForm(ForumForm, forms.ModelForm):
    """Edit the text of a post; edits take no files and keep no draft in the browser."""

    content = forms.CharField(label="Message", help_text=WRITING_HELP, max_length=MAX_CONTENT, widget=editor_widget(
        10, "Write your message. Link GCD records with the search below.", draft=False))

    class Meta:
        """Edit a Post's content only."""

        model = Post
        fields = ("content",)


class ReportForm(ForumForm, forms.ModelForm):
    """The reason for reporting a topic or a post to the moderators."""

    class Meta:
        """Edit a Report's reason in a four-row text area styled as a forum input."""

        model = Report
        fields = ("reason",)
        widgets = {
            "reason": forms.Textarea(attrs={"rows": 4, "class": INPUT_CLASS})
        }
