from django import forms
from django.core.exceptions import ValidationError
from django.db import transaction

from .models import Discussion, DiscussionRecord, Post, Report
from .access import postable_categories, posting_limit
from .activity import follow
from .mail import queue_post
from .records import parse_record_link, record_content_type


INPUT_CLASS = "w-full border-gray-400"


class RecordLinksField(forms.CharField):
    """Links to GCD record pages, one per line, as (key, record) pairs."""

    widget = forms.Textarea(attrs={"rows": 3, "class": INPUT_CLASS,
                                   "placeholder": "https://www.comics.org/series/1234/"})

    def clean(self, value):
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


def save_records(discussion, records, user):
    for key, record in records:
        DiscussionRecord.objects.get_or_create(
            discussion=discussion, content_type=record_content_type(key),
            object_id=record.pk, defaults={"created_by": user})


class DiscussionForm(forms.ModelForm):
    content = forms.CharField(
        label="Message", help_text="Markdown is supported.",
        widget=forms.Textarea(attrs={"rows": 10, "class": INPUT_CLASS}),
    )
    records = RecordLinksField(
        label="GCD records", required=False,
        help_text="Paste the links of the GCD pages this topic is about, one per line.",
    )

    class Meta:
        model = Discussion
        fields = ("category", "title")
        widgets = {
            "title": forms.TextInput(attrs={"class": INPUT_CLASS, "maxlength": 200}),
            "category": forms.Select(attrs={"class": INPUT_CLASS}),
        }

    def __init__(self, *args, user=None, ip_address=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.ip_address = ip_address
        self.fields["category"].label = "Group"
        self.fields["category"].empty_label = None
        self.fields["category"].queryset = postable_categories(user)

    def clean(self):
        cleaned_data = super().clean()
        limit = posting_limit(self.user, new_topic=True)
        if limit:
            raise ValidationError(limit)
        return cleaned_data

    @transaction.atomic
    def save(self, commit=True):
        if not commit:
            raise ValueError("DiscussionForm must be saved with commit=True.")
        discussion = super().save(commit=False)
        discussion.author = self.user
        discussion.created_by = self.user
        discussion.updated_by = self.user
        discussion.ip_address = self.ip_address
        discussion.save()
        save_records(discussion, self.cleaned_data["records"], self.user)
        post = Post.objects.create(
            discussion=discussion,
            author=self.user,
            content=self.cleaned_data["content"],
            created_by=self.user,
            updated_by=self.user,
            ip_address=self.ip_address,
        )
        follow(self.user, discussion)
        queue_post(post)
        return discussion


class PostForm(forms.ModelForm):
    # A plain textarea: the markdownx editor needs scripts the forum pages don't load.
    content = forms.CharField(widget=forms.Textarea(attrs={"rows": 6, "class": INPUT_CLASS}))
    parent = forms.ModelChoiceField(
        queryset=Post.objects.none(), required=False, widget=forms.HiddenInput()
    )

    class Meta:
        model = Post
        fields = ("content", "parent")

    def __init__(self, *args, discussion=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.discussion = discussion
        if discussion:
            self.fields["parent"].queryset = Post.objects.filter(discussion=discussion)

    def clean_parent(self):
        parent = self.cleaned_data.get("parent")
        if parent and parent.discussion_id != self.discussion.pk:
            raise ValidationError("The parent post belongs to another discussion.")
        return parent


class DiscussionEditForm(forms.ModelForm):
    records = RecordLinksField(
        label="Add GCD records", required=False,
        help_text="Paste more links to GCD pages, one per line.",
    )

    class Meta:
        model = Discussion
        fields = ("title",)
        widgets = {"title": forms.TextInput(attrs={"class": INPUT_CLASS, "maxlength": 200})}

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

    @transaction.atomic
    def save(self, commit=True):
        discussion = super().save(commit=commit)
        save_records(discussion, self.cleaned_data["records"], self.user)
        return discussion


class MoveForm(forms.Form):
    category = forms.ModelChoiceField(
        label="Move to", queryset=None, empty_label=None,
        widget=forms.Select(attrs={"class": INPUT_CLASS}))

    def __init__(self, *args, user=None, discussion=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["category"].queryset = postable_categories(user).exclude(pk=discussion.category_id)


class PostEditForm(forms.ModelForm):
    content = forms.CharField(
        label="Message", help_text="Markdown is supported.",
        widget=forms.Textarea(attrs={"rows": 10, "class": INPUT_CLASS}))

    class Meta:
        model = Post
        fields = ("content",)


class ReportForm(forms.ModelForm):
    class Meta:
        model = Report
        fields = ("reason",)
        widgets = {
            "reason": forms.Textarea(attrs={"rows": 4, "class": INPUT_CLASS})
        }
