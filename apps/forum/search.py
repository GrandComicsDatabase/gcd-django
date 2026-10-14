"""Full-text search of topics and posts.

On MySQL the search uses the FULLTEXT indexes of migration 0004 in boolean mode:
every word is required, as a prefix ("spider" finds "Spider-Man"), and quoted
phrases must appear as they are. The index answers from its own word lists, so
the time does not grow with a scan of every post, as LIKE '%word%' does.

Filters in the query: by:Rossi or by:"Maria Rossi" (posts by the people so named),
after:YYYY-MM-DD and before:YYYY-MM-DD (posts in that period).
"""
import re
from datetime import date, datetime, time, timedelta

from django.contrib.auth import get_user_model
from django.db import connection
from django.db.models import Case, Exists, IntegerField, OuterRef, Q, Value, When
from django.db.models.functions import Concat
from django.utils import timezone
from django.utils.html import escape
from django.utils.safestring import mark_safe

from .models import Post

# Words the InnoDB index leaves out: shorter than innodb_ft_min_token_size (3) or in
# INFORMATION_SCHEMA.INNODB_FT_DEFAULT_STOPWORD. Requiring them would match nothing.
MIN_WORD = 3
STOPWORDS = {
    "a", "about", "an", "are", "as", "at", "be", "by", "com", "de", "en", "for", "from", "how", "i", "in",
    "is", "it", "la", "of", "on", "or", "that", "the", "this", "to", "was", "what", "when", "where", "who",
    "will", "with", "und", "www",
}
# Relevance is computed for the best POSTS matching posts and TOPICS matching titles;
# a search that needs more is too vague to read anyway.
POSTS = 2000
TOPICS = 500
TOKEN = re.compile(r'by:"([^"]*)"?|"([^"]*)"?|(\S+)', re.IGNORECASE)
WORD = re.compile(r"\w+")


class Query:
    """A search text parsed into words, quoted phrases and the by:, after: and before: filters."""

    def __init__(self, text, topics=None):
        """Parse the text. Unquoted words shorter than MIN_WORD or in STOPWORDS go to short, as the index
        has none of them. The words of every by: filter together name the authors among those with a
        published post in the topics searched (all topics when None): authors is the list of their ids, or
        False when none has that name (then nobody holds the name). after: and before: without a valid date
        go to ignored, so the page can say so."""
        self.words, self.phrases, self.authors, self.after, self.before = [], [], None, None, None
        self.short, self.ignored, self.nobody, names = [], [], "", []
        for name_phrase, phrase, token in TOKEN.findall(text):
            name, _, value = token.partition(":")
            if name_phrase or (name.lower() == "by" and value):
                names += (name_phrase or value).split()
            elif phrase:
                words = WORD.findall(phrase.lower())
                if words:
                    self.phrases.append(words)
            elif name.lower() in ("after", "before") and value:
                if _parse_date(value):
                    setattr(self, name.lower(), _parse_date(value))
                else:
                    self.ignored.append(token)
            else:
                for word in WORD.findall(token.lower()):
                    (self.words if len(word) >= MIN_WORD and word not in STOPWORDS else self.short).append(word)
        if names:
            self.authors = _authors(names, topics) or False
            if self.authors is False:
                self.nobody = " ".join(names)

    def notes(self):
        """What the search could not use, to show with the results: dates not understood and names nobody
        who posted in the topics searched has."""
        notes = [f"{token} was ignored: write dates as YYYY-MM-DD, for example after:2020-01-31."
                 for token in self.ignored]
        if self.nobody:
            notes.append(f"Nobody named “{self.nobody}” posted in the topics searched.")
        return notes

    @property
    def indexed(self):
        """Whether the query has a word the FULLTEXT index keeps, on its own or in a phrase."""
        return bool(self.words or any(_indexed(phrase) for phrase in self.phrases))

    @property
    def filtered(self):
        """Whether the query has a by:, after: or before: filter."""
        return self.authors is not None or self.after or self.before

    def boolean(self):
        """The boolean-mode search text: +word* for every word, +"phrase" for every indexed phrase."""
        terms = [f"+{word}*" for word in self.words]
        terms += ['+"%s"' % " ".join(phrase) for phrase in self.phrases if _indexed(phrase)]
        return " ".join(terms)

    def highlights(self):
        """All the query's words, from phrases and short ones too, for the substring search and excerpts."""
        return self.words + [word for phrase in self.phrases for word in phrase] + self.short


def _authors(names, topics=None):
    """Ids of the people with a published post in the topics (all topics when None) whose first or last
    name has a word starting with each of the names, ignoring case: "by:ross" finds Maria Rossi, "by:luca"
    finds Anna De Luca. Posts the searcher cannot read do not count, so the answer tells nothing about
    who posted in groups they cannot read."""
    full = Concat(Value(" "), "first_name", Value(" "), "last_name")
    match = Q()
    for name in names:
        match &= Q(full_name__icontains=f" {name}") | Q(full_name__icontains=f"-{name}")
    published = {"forum_posts__is_deleted": False, "forum_posts__awaiting_review": False}
    if topics is not None:
        published["forum_posts__discussion__in"] = topics
    return list(get_user_model().objects.filter(**published).annotate(full_name=full)
                .filter(match).values_list("pk", flat=True).distinct())


def _indexed(phrase):
    """Whether a phrase has a word the index keeps: MIN_WORD characters or more and not a stopword."""
    return any(len(word) >= MIN_WORD and word not in STOPWORDS for word in phrase)


def _parse_date(value):
    """The date of an ISO value such as 2024-05-31, or None when it is not a valid date."""
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _bounds(query):
    """Start of the after: day and end of the before: day, as aware datetimes in the current time zone."""
    zone = timezone.get_current_timezone()
    after = timezone.make_aware(datetime.combine(query.after, time.min), zone) if query.after else None
    before = (timezone.make_aware(datetime.combine(query.before + timedelta(days=1), time.min), zone)
              if query.before else None)
    return after, before


def _post_filters(query):
    """SQL conditions on forum_post, with their parameters, for the author and date filters of the query."""
    after, before = _bounds(query)
    sql, params = [], []
    if query.authors:
        sql.append("author_id IN (%s)" % ", ".join(["%s"] * len(query.authors)))
        params.extend(query.authors)
    if after:
        sql.append("created_at >= %s")
        params.append(after)
    if before:
        sql.append("created_at < %s")
        params.append(before)
    return sql, params


def _fulltext(query, queryset):
    """Scores of the best topics of the queryset (the user's topics, of one group or all): {topic id: (title
    score, post score, best post id)}. The queryset filters the rows before they are ranked and cut to
    POSTS and TOPICS, so topics the user cannot see never take the places of those they can."""
    against = query.boolean()
    where, params = _post_filters(query)
    topics_sql, topics_params = queryset.order_by().values("pk").query.sql_with_params()
    scores = {}
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT id, discussion_id, MATCH(content) AGAINST (%s IN BOOLEAN MODE) AS score FROM forum_post "
            "WHERE MATCH(content) AGAINST (%s IN BOOLEAN MODE) AND is_deleted = 0 AND awaiting_review = 0 "
            f"AND discussion_id IN ({topics_sql})"
            + "".join(f" AND {condition}" for condition in where)
            + f" ORDER BY score DESC, id DESC LIMIT {POSTS}", [against, against, *topics_params, *params])
        for post_id, topic_id, score in cursor.fetchall():
            if topic_id not in scores:
                scores[topic_id] = (0.0, float(score), post_id)
        if not query.filtered:
            cursor.execute(
                "SELECT id, MATCH(title) AGAINST (%s IN BOOLEAN MODE) AS score FROM forum_discussion "
                "WHERE MATCH(title) AGAINST (%s IN BOOLEAN MODE) AND is_deleted = 0 AND awaiting_review = 0 "
                f"AND id IN ({topics_sql}) "
                f"ORDER BY score DESC, id DESC LIMIT {TOPICS}", [against, against, *topics_params])
            for topic_id, score in cursor.fetchall():
                _, post_score, post_id = scores.get(topic_id, (0.0, 0.0, None))
                scores[topic_id] = (float(score), post_score, post_id)
    return scores


def search(queryset, text):
    """Filter the topics to those matching the query; return (queryset, best post by topic, query)."""
    query = Query(text, queryset)
    if query.authors is False:
        return queryset.none(), {}, query
    if connection.vendor == "mysql" and query.indexed:
        scores = _fulltext(query, queryset)
        # Topics whose title matches come first, then by relevance.
        ranked = sorted(scores, key=lambda pk: (scores[pk][0] == 0, -(scores[pk][0] + scores[pk][1]), -pk))
        ranked = ranked[:TOPICS]
        queryset = queryset.filter(pk__in=ranked).order_by(Case(
            *[When(pk=pk, then=Value(position)) for position, pk in enumerate(ranked)],
            output_field=IntegerField()))
        return queryset, {pk: scores[pk][2] for pk in ranked if scores[pk][2]}, query
    words = query.highlights()
    posts = Post.objects.filter(discussion_id=OuterRef("pk"))
    after, before = _bounds(query)
    if query.authors:
        posts = posts.filter(author__in=query.authors)
    if after:
        posts = posts.filter(created_at__gte=after)
    if before:
        posts = posts.filter(created_at__lt=before)
    title = Q()
    for word in words:
        title &= Q(title__icontains=word)
    if connection.vendor == "mysql":
        # Only short words: the index has none of them, and a LIKE over every post is too slow.
        match = title & Q(Exists(posts)) if query.filtered else title
    else:
        for word in words:
            posts = posts.filter(content__icontains=word)
        match = Q(Exists(posts)) if query.filtered or not words else Q(Exists(posts)) | title
    return queryset.filter(match), {}, query


# Markdown marks; "#" only starts a heading, elsewhere it is an issue number.
# Bounded groups: unbounded ones backtrack to the end of the text from every "[". Only spaces and tabs
# before "#" or ">": \s would also take line breaks, and a run of empty lines would be read again from each.
MARKUP = re.compile(r"!?\[([^\]\n]{0,200})\]\([^)\n]{0,500}\)|[*_`~|]+|(?m:^[ \t]*[#>]+)|https?://\S+")


def excerpt(content, query, length=220):
    """A piece of the post around the first searched word, with the words marked."""
    text = re.sub(r"\s+", " ", MARKUP.sub(lambda match: match.group(1) or " ", content)).strip()
    words = sorted(set(query.highlights()), key=len, reverse=True)
    if not words:
        return escape(text[:length])
    pattern = re.compile("|".join(re.escape(word) for word in words), re.IGNORECASE)
    first = pattern.search(text)
    start = max(0, (first.start() if first else 0) - length // 3)
    piece = text[start:start + length]
    marked = []
    position = 0
    for match in pattern.finditer(piece):
        marked += [escape(piece[position:match.start()]), f"<mark>{escape(match.group())}</mark>"]
        position = match.end()
    marked.append(escape(piece[position:]))
    return mark_safe(("…" if start else "") + "".join(marked) + ("…" if start + length < len(text) else ""))


def add_excerpts(topics, best_posts, query):
    """Give each topic of the page the post that matched, with an excerpt."""
    contents = dict(Post.objects.filter(pk__in=[best_posts[topic.pk] for topic in topics if topic.pk in best_posts])
                    .values_list("pk", "content"))
    for topic in topics:
        post_id = best_posts.get(topic.pk)
        if post_id in contents:
            topic.search_post_id = post_id
            topic.search_excerpt = excerpt(contents[post_id], query)
