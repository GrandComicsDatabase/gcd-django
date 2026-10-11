from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.decorators import login_required
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.db.models import Count, Exists, F, OuterRef, Prefetch, Q
from django.http import Http404, HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods, require_POST, require_safe
from django.views.generic import CreateView, UpdateView

from .forms import (
    DiscussionEditForm,
    DiscussionForm,
    MoveForm,
    PostEditForm,
    PostForm,
    RecordLinksField,
    ReportForm,
)
from .models import (
    Category, Discussion, DiscussionRecord, GroupEmailSubscription, Notification, Post, PostVote,
    Report, TopicSubscription,
)
from .access import (
    accessible_discussions, accessible_posts, postable_categories, posting_limit, visible_categories,
)
from .records import get_record, record_content_type
from .activity import follow, mark_read, notify_followers, unread_notifications, with_unread
from .mail import queue_post, valid_unsubscribe
from .utils import can_moderate, get_client_ip

PAGE_SIZE = 25


def _is_htmx(request):
    return request.headers.get("HX-Request") == "true"


def _records_prefetch():
    return Prefetch("records", queryset=DiscussionRecord.objects.select_related("content_type"))


def _topics(user):
    return (accessible_discussions(user).select_related("author", "category", "moved_from")
            .prefetch_related(_records_prefetch()))


def _add_unread(topics, user):
    """Unread counts for the topics of one page only, so lists stay fast."""
    if not user.is_authenticated:
        return
    unread = {row["pk"]: row for row in with_unread(
        Discussion.objects.filter(pk__in=[topic.pk for topic in topics]), user
    ).values("pk", "last_read_post_id", "unread_count", "first_unread_id")}
    for topic in topics:
        row = unread.get(topic.pk, {})
        topic.last_read_post_id = row.get("last_read_post_id")
        topic.unread_count = row.get("unread_count", 0)
        topic.first_unread_id = row.get("first_unread_id")


def _topic_page(request, queryset):
    """Filter, order and paginate a topic list from the query string."""
    query = request.GET.get("q", "").strip()[:200]
    if query:
        queryset = queryset.annotate(matching_post=Exists(Post.objects.filter(
            discussion_id=OuterRef("pk"), content__icontains=query
        ))).filter(Q(title__icontains=query) | Q(matching_post=True))
    feed = request.GET.get("feed", "latest")
    if feed in ("mine", "following") and not request.user.is_authenticated:
        feed = "latest"
    if feed == "unanswered":
        queryset = queryset.filter(post_count__lte=1)
    elif feed == "mine":
        queryset = queryset.filter(Exists(Post.objects.filter(
            discussion_id=OuterRef("pk"), author=request.user)))
    elif feed == "following":
        queryset = queryset.filter(Exists(TopicSubscription.objects.filter(
            discussion_id=OuterRef("pk"), user=request.user)))
    ordering = ("-created_at",) if feed == "new" else ("-last_activity", "-created_at")
    page = Paginator(queryset.order_by("-is_pinned", *ordering, "-pk"), PAGE_SIZE).get_page(
        request.GET.get("page"))
    page.object_list = list(page.object_list)
    _add_unread(page.object_list, request.user)
    return {"page_obj": page, "discussions": page.object_list, "search_query": query,
            "active_feed": feed}


def group_sections(categories):
    """Group categories under their Email Lists FAQ section, in section order."""
    sections = []
    for value, title in Category.Section.choices:
        groups = [category for category in categories if category.section == value]
        if groups:
            sections.append({"title": title, "groups": groups})
    return sections


def _sidebar(user):
    categories = list(visible_categories(user).annotate(
        topic_count=Count("discussions", filter=Q(discussions__is_deleted=False), distinct=True)))
    return {"sections": group_sections(categories),
            "notification_count": unread_notifications(user).count() if user.is_authenticated else 0}


@require_safe
def index(request):
    context = _sidebar(request.user)
    context.update(_topic_page(request, _topics(request.user)))
    return render(request, "forum/index.html", context)


@require_safe
def group(request, slug):
    category = get_object_or_404(visible_categories(request.user), slug=slug)
    # Topics moved away stay listed in their old group, pointing to the new one.
    topics = _topics(request.user).filter(Q(category=category) | Q(moved_from=category))
    context = _sidebar(request.user)
    context.update(_topic_page(request, topics))
    context.update(category=category, can_post=category.can_post(request.user),
                   can_read=category.can_read(request.user),
                   email_member=request.user.is_authenticated and GroupEmailSubscription.objects.filter(
                       user=request.user, category=category).exists())
    return render(request, "forum/index.html", context)


@require_safe
def record(request, key, object_id):
    found = get_record(key, object_id)
    if found is None:
        raise Http404
    topics = _topics(request.user).filter(
        records__content_type=record_content_type(key), records__object_id=object_id)
    context = _sidebar(request.user)
    context.update(_topic_page(request, topics))
    context.update(record=found, record_key=key)
    return render(request, "forum/index.html", context)


@require_safe
def record_preview(request):
    """Show which pasted links point to GCD records, before posting."""
    field = RecordLinksField(required=False)
    found, invalid = [], []
    for line in request.GET.get("records", "").splitlines():
        if line.strip():
            try:
                found.extend(field.clean(line))
            except ValidationError:
                invalid.append(line.strip())
    return render(request, "forum/_record_preview.html", {"found": found, "invalid": invalid})


class DiscussionCreateView(LoginRequiredMixin, CreateView):
    form_class = DiscussionForm
    template_name = "forum/form.html"

    def get_initial(self):
        initial = super().get_initial()
        category = postable_categories(self.request.user).filter(
            slug=self.request.GET.get("category", "")).first()
        if category:
            initial["category"] = category.pk
        key, _, object_id = self.request.GET.get("record", "").partition(":")
        found = get_record(key, object_id) if object_id.isdigit() else None
        if found:
            initial["records"] = self.request.build_absolute_uri(found.get_absolute_url())
        return initial

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs.update(user=self.request.user, ip_address=get_client_ip(self.request))
        return kwargs


def _post_tree(discussion):
    posts = list(
        Post.all_objects.filter(discussion=discussion)
        .select_related("author")
        .annotate(vote_count=Count("votes"))
        .order_by("created_at")
    )
    by_id = {post.pk: post for post in posts}
    roots = []
    for post in posts:
        post.tree_children = []
        post.user_has_voted = False
    for post in posts:
        parent = by_id.get(post.parent_id)
        if parent:
            parent.tree_children.append(post)
        else:
            roots.append(post)
    return roots, posts


def _can_reply(user, discussion):
    return (not discussion.is_locked and discussion.status != Discussion.Status.ARCHIVED
            and discussion.category.can_post(user))


@require_safe
def discussion_detail(request, slug):
    discussion = get_object_or_404(
        accessible_discussions(request.user).select_related(
            "author", "category", "moved_from", "moved_by", "answer__author", "duplicate_of"
        ).prefetch_related(_records_prefetch()),
        slug=slug,
    )
    signed_in = request.user.is_authenticated
    last_read_post_id = mark_read(request.user, discussion) if signed_in else None
    view_key = f"forum-viewed-{discussion.pk}"
    if not request.session.get(view_key):
        Discussion.objects.filter(pk=discussion.pk).update(views_count=F("views_count") + 1)
        request.session[view_key] = True
        discussion.refresh_from_db(fields=("views_count",))

    roots, posts = _post_tree(discussion)
    voted_ids = set(PostVote.objects.filter(user=request.user, post__in=posts)
                    .values_list("post_id", flat=True)) if signed_in else set()
    first_unread = None
    for post in posts:
        post.user_has_voted = post.pk in voted_ids
        post.is_unread = bool(last_read_post_id is not None and post.pk > last_read_post_id
                              and post.author_id != request.user.pk)
        if post.is_unread and first_unread is None:
            first_unread = post
    moderator = can_moderate(request.user, discussion)
    return render(request, "forum/discussion_detail.html", {
        "discussion": discussion,
        "post_roots": roots,
        "reply_form": PostForm(discussion=discussion),
        "can_reply": _can_reply(request.user, discussion),
        "can_moderate": moderator,
        "group_moderator": discussion.category.is_moderator(request.user),
        "can_accept": _can_accept(request.user, discussion),
        "first_post_id": posts[0].pk if posts else None,
        "first_unread": first_unread,
        "following": signed_in and TopicSubscription.objects.filter(
            user=request.user, discussion=discussion).exists(),
        "move_form": MoveForm(user=request.user, discussion=discussion) if moderator else None,
    })


@login_required
@require_POST
def reply(request, slug):
    discussion = get_object_or_404(
        accessible_discussions(request.user).select_related("category"), slug=slug)
    if not _can_reply(request.user, discussion):
        return HttpResponse("You cannot reply to this discussion.", status=403)
    form = PostForm(request.POST, discussion=discussion)
    limit = posting_limit(request.user)
    if limit:
        form.add_error(None, limit)
    if not form.is_valid():
        response = render(request, "forum/_reply_form.html",
                          {"discussion": discussion, "reply_form": form}, status=422)
        response["HX-Retarget"] = "#reply-form-container"
        response["HX-Reswap"] = "outerHTML"
        return response

    post = form.save(commit=False)
    post.discussion = discussion
    post.author = request.user
    post.created_by = request.user
    post.updated_by = request.user
    post.ip_address = get_client_ip(request)
    post.save()
    follow(request.user, discussion)
    notify_followers(post)
    queue_post(post)
    if _is_htmx(request):
        post.vote_count = 0
        post.user_has_voted = False
        post.tree_children = []
        return render(request, "forum/_post.html",
                      {"post": post, "discussion": discussion, "can_reply": True})
    return redirect(f"{discussion.get_absolute_url()}#post-{post.pk}")


@login_required
@require_POST
def toggle_vote(request, pk):
    post = get_object_or_404(accessible_posts(request.user).select_related("discussion"), pk=pk)
    with transaction.atomic():
        vote, created = PostVote.objects.get_or_create(post=post, user=request.user)
        if not created:
            vote.delete()
    post.vote_count = PostVote.objects.filter(post=post).count()
    post.user_has_voted = created
    if _is_htmx(request):
        return render(request, "forum/_vote_button.html", {"post": post})
    return redirect(post.discussion.get_absolute_url())


@login_required
@require_POST
def move_discussion(request, slug):
    discussion = get_object_or_404(accessible_discussions(request.user), slug=slug)
    if not can_moderate(request.user, discussion):
        return HttpResponse(status=403)
    form = MoveForm(request.POST, user=request.user, discussion=discussion)
    if not form.is_valid():
        return HttpResponseBadRequest("Choose a group you can post in.")
    discussion.moved_from = discussion.category
    discussion.category = form.cleaned_data["category"]
    discussion.moved_by = request.user
    discussion.moved_at = timezone.now()
    discussion.updated_by = request.user
    discussion.save()
    messages.success(request, f"Moved to {discussion.category}.")
    return redirect(discussion.get_absolute_url())


@login_required
@require_POST
def toggle_follow(request, slug):
    discussion = get_object_or_404(accessible_discussions(request.user), slug=slug)
    subscription = TopicSubscription.objects.filter(user=request.user, discussion=discussion)
    if subscription.exists():
        subscription.delete()
    else:
        follow(request.user, discussion)
    if _is_htmx(request):
        return render(request, "forum/_follow_button.html", {
            "discussion": discussion, "following": subscription.exists()})
    return redirect(discussion.get_absolute_url())


@login_required
@require_POST
def toggle_group_email(request, slug):
    """Receive every post of the group by email, like a mailing list member."""
    from .access import readable_categories

    category = get_object_or_404(readable_categories(request.user), slug=slug)
    subscription = GroupEmailSubscription.objects.filter(user=request.user, category=category)
    if subscription.exists():
        subscription.delete()
        messages.success(request, f"You no longer get {category.name} by email.")
    else:
        GroupEmailSubscription.objects.create(user=request.user, category=category)
        messages.success(request, f"You get every new post of {category.name} at {request.user.email}.")
    return redirect(category.get_absolute_url())


@csrf_exempt
@require_http_methods(["GET", "POST"])
def email_unsubscribe(request, user_id, kind, object_id, signature):
    """Unsubscribe link of the emails; POST also serves one-click unsubscribe (RFC 8058).

    No session is needed: the signed link identifies the user, so CSRF does not apply.
    """
    if kind not in ("group", "topic") or not valid_unsubscribe(user_id, kind, object_id, signature):
        raise Http404
    if kind == "group":
        subscriptions = GroupEmailSubscription.objects.filter(user_id=user_id, category_id=object_id)
        target = Category.objects.filter(pk=object_id).first()
        about = f"every post of {target.name}" if target else "this group"
    else:
        subscriptions = TopicSubscription.objects.filter(user_id=user_id, discussion_id=object_id)
        target = Discussion.objects.filter(pk=object_id).first()
        about = f'replies to "{target.title}"' if target else "this topic"
    if request.method == "POST":
        subscriptions.delete()
    return render(request, "forum/unsubscribed.html", {"done": request.method == "POST", "about": about})


@require_safe
def notifications(request):
    """The user's notifications, newest first; reading a topic marks its ones read."""
    items = Paginator(
        Notification.objects.filter(user=request.user, post__discussion__in=accessible_discussions(request.user))
        .select_related("post__author", "post__discussion__category"), PAGE_SIZE,
    ).get_page(request.GET.get("page"))
    context = _sidebar(request.user)
    context.update(page_obj=items, notifications=items.object_list, active_page="notifications")
    return render(request, "forum/notifications.html", context)


@login_required
@require_POST
def notifications_read(request):
    unread_notifications(request.user).update(read_at=timezone.now())
    return redirect("forum:notifications")


def _can_accept(user, discussion):
    return discussion.author_id == user.pk or discussion.category.is_moderator(user)


@login_required
@require_POST
def accept_answer(request, pk):
    """Mark a reply as the answer, or unmark it: topic author or group moderators."""
    post = get_object_or_404(accessible_posts(request.user).select_related("discussion__category"), pk=pk)
    discussion = post.discussion
    first_post_id = discussion.posts.order_by("pk").values_list("pk", flat=True).first()
    if not _can_accept(request.user, discussion) or post.pk == first_post_id:
        return HttpResponse(status=403)
    if discussion.answer_id == post.pk:
        discussion.answer, discussion.status = None, Discussion.Status.OPEN
    else:
        discussion.answer, discussion.status = post, Discussion.Status.RESOLVED
    discussion.updated_by = request.user
    discussion.save()
    return redirect(f"{discussion.get_absolute_url()}#post-{post.pk}")


@login_required
@require_POST
def mark_duplicate(request, slug):
    """Close a topic as a duplicate of another one: group moderators only."""
    from urllib.parse import urlsplit

    from django.urls import Resolver404, resolve

    discussion = get_object_or_404(accessible_discussions(request.user).select_related("category"), slug=slug)
    if not discussion.category.is_moderator(request.user):
        return HttpResponse(status=403)
    try:
        match = resolve(urlsplit(request.POST.get("original", "").strip()).path)
    except Resolver404:
        match = None
    original = None
    if match and match.view_name == "forum:discussion-detail":
        original = accessible_discussions(request.user).exclude(pk=discussion.pk).filter(
            slug=match.kwargs["slug"]).first()
    if original is None:
        messages.error(request, "Paste the link of another topic you can read.")
        return redirect(discussion.get_absolute_url())
    discussion.duplicate_of, discussion.is_locked = original, True
    discussion.updated_by = request.user
    discussion.save()
    return redirect(discussion.get_absolute_url())


MODERATION_ACTIONS = {
    "pin": ("is_pinned", True, "Topic pinned."),
    "unpin": ("is_pinned", False, "Topic unpinned."),
    "close": ("is_locked", True, "Topic closed to new replies."),
    "reopen": ("is_locked", False, "Topic reopened."),
}


@login_required
@require_POST
def moderate_discussion(request, slug):
    """Pin or close a topic: group moderators and staff only."""
    discussion = get_object_or_404(accessible_discussions(request.user).select_related("category"), slug=slug)
    if not discussion.category.is_moderator(request.user):
        return HttpResponse(status=403)
    action = MODERATION_ACTIONS.get(request.POST.get("action"))
    if action is None:
        return HttpResponseBadRequest("Unknown action.")
    field, value, message = action
    setattr(discussion, field, value)
    discussion.updated_by = request.user
    discussion.save()
    messages.success(request, message)
    return redirect(discussion.get_absolute_url())


@login_required
@require_POST
def remove_record(request, slug, pk):
    discussion = get_object_or_404(accessible_discussions(request.user), slug=slug)
    if not can_moderate(request.user, discussion):
        return HttpResponse(status=403)
    DiscussionRecord.objects.filter(discussion=discussion, pk=pk).delete()
    return redirect(discussion.get_absolute_url())


class AuthorOrStaffMixin(LoginRequiredMixin, UserPassesTestMixin):
    raise_exception = True

    def test_func(self):
        return can_moderate(self.request.user, self.get_object())


class DiscussionUpdateView(AuthorOrStaffMixin, UpdateView):
    model = Discussion
    form_class = DiscussionEditForm
    slug_field = "slug"
    template_name = "forum/form.html"

    def get_queryset(self):
        return accessible_discussions(self.request.user)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        form.instance.updated_by = self.request.user
        return super().form_valid(form)


class PostUpdateView(AuthorOrStaffMixin, UpdateView):
    model = Post
    form_class = PostEditForm
    template_name = "forum/form.html"

    def get_queryset(self):
        return accessible_posts(self.request.user)

    def form_valid(self, form):
        form.instance.updated_by = self.request.user
        return super().form_valid(form)

    def get_success_url(self):
        return f"{self.object.discussion.get_absolute_url()}#post-{self.object.pk}"


@login_required
@require_POST
def delete_discussion(request, slug):
    discussion = get_object_or_404(accessible_discussions(request.user), slug=slug)
    if not can_moderate(request.user, discussion):
        return HttpResponse(status=403)
    discussion.updated_by = request.user
    discussion.save(update_fields=("updated_by", "updated_at"))
    discussion.delete()
    messages.success(request, "Discussion removed.")
    return redirect("forum:index")


@login_required
@require_POST
def delete_post(request, pk):
    post = get_object_or_404(accessible_posts(request.user).select_related("discussion"), pk=pk)
    if not can_moderate(request.user, post):
        return HttpResponse(status=403)
    post.updated_by = request.user
    post.save(update_fields=("updated_by", "updated_at"))
    post.delete()
    if _is_htmx(request):
        response = HttpResponse()
        response["HX-Redirect"] = post.discussion.get_absolute_url()
        return response
    return redirect(post.discussion.get_absolute_url())


@login_required
@require_POST
def report_content(request, kind, pk):
    model = {"discussion": Discussion, "post": Post}.get(kind)
    if model is None:
        raise Http404
    queryset = accessible_posts(request.user) if model is Post else accessible_discussions(request.user)
    content = get_object_or_404(queryset, pk=pk)
    form = ReportForm(request.POST)
    if not form.is_valid():
        return HttpResponseBadRequest("A reason is required (maximum 1000 characters).")
    try:
        with transaction.atomic():
            Report.objects.create(
                reporter=request.user,
                content_type=ContentType.objects.get_for_model(content),
                object_id=content.pk,
                reason=form.cleaned_data["reason"],
            )
    except IntegrityError:
        pass
    messages.success(request, "Thank you. Your report was sent to the moderators.")
    return redirect(content.get_absolute_url() if kind == "discussion"
                    else content.discussion.get_absolute_url())
