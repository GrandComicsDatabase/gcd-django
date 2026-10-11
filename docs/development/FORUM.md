# Forum

`apps/forum` is a discussion forum served under `/forum/` with the site layout.
It replaces the GCD email lists described in the Email Lists FAQ and links each
topic to the GCD records it is about.

## Groups

The data migration `0002_default_groups` creates one group per email list, in
three sections: main, international and specialized. `gcd-contact` is not a
group: it stays an email address for people without an account.

Each group has a read access and a post access: anyone (read only, also
without an account), any GCD user, or the group members (set in the admin):

| Group | Read | Post |
|---|---|---|
| gcd-editor | members | members |
| gcd-board | anyone | members |
| gcd-error | members | any user |
| every other group | anyone | any user |

In a group that a user can post to but not read, such as `gcd-error`, the user
sees only the topics they started. Staff and superusers read and post
everywhere.

## Topics and GCD records

A topic can be linked to any number of GCD records. Users paste the links of
the record pages; `records.parse_record_link` resolves them with the site's
own URL routes (`show_<type>` with a `<type>_id` argument), so only live
records of the types in `records.RECORD_TYPES` are accepted.

Every record page built on `gcd/tw_object_base.html` shows a "Forum
discussions (N)" button. It opens `/forum/records/<type>/<id>/`, the topics
about that record in every group the visitor can read.

Record pages also offer "Report an error on the forum": a new topic in
`gcd-error` with the record already linked.

## Moderation

Each group has moderators (for example the coordinators of the list) set in the
admin. Moderators and staff pin, close and reopen topics, close a topic as a
duplicate of another one, and edit, move or remove any content of the group.
Authors can edit, move and remove their own content.

A topic that is moved keeps `moved_from`, `moved_by` and `moved_at`, and the old
group keeps listing it as "Moved to …", like a shadow topic.

A `Suspension` (admin) revokes posting in one group, or in every group when the
group is empty, until an optional date. Suspended users can still read.

Against floods, from the web or by email, a user can start at most
`FORUM_MAX_TOPICS_PER_DAY` topics (default 20) and post at most
`FORUM_MAX_POSTS_PER_DAY` messages (default 100) in 24 hours, a daily limit
like "max topics per day" in Discourse. Removed posts still count; staff have
no limit.

## Following, unread posts and answers

Creating a topic or replying follows it; "Follow" toggles it. Followers get a
notification, and an email, for every reply by someone else, if they can still
read the topic. Lists show "N new" with a link to the first post the user has
not seen (tracked by post id in `TopicRead`), and the topic marks those posts.

The topic author or a moderator can mark a reply as the accepted answer, which
marks the topic solved and links the answer from the top of the topic.

## Email gateway

Each group also works as a mailing list, so members can keep using email.

- **Outgoing.** A new post is queued in `OutgoingEmail` for the followers of the
  topic and for the members who chose "Get every post by email" in the group.
  Messages carry `Message-ID`, `In-Reply-To` and `References` (threading in mail
  clients), `List-Id`, and `List-Unsubscribe` with one-click unsubscribe
  (RFC 2369, RFC 8058).
- **Incoming.** Replies go to `forum+r-<user>-<topic>-<signature>@…`, an
  address valid for one user and one topic; the sender must be that user. New
  topics go to `forum+g-<group>@…`; the sender must be the only active GCD
  account with that address and the receiving server must report `dmarc=pass`
  in `Authentication-Results`. Quoted text and the `-- ` signature are removed.
  Automatic messages (`Auto-Submitted`, RFC 3834) are ignored, and every
  `Message-ID` is processed once. Each message is logged in `IncomingEmail`.
  Unknown senders that pass DMARC get one notice; forged senders get nothing.

Run the gateway from cron, for example every minute:

```sh
python manage.py forum_mail
```

Settings (in `settings_local.py`):

| Setting | Default | Meaning |
|---|---|---|
| `FORUM_EMAIL_ADDRESS` | `forum@comics.org` | Mailbox; plus addressing must deliver `forum+…@` to it |
| `FORUM_EMAIL_IMAP` | not set (no fetching) | `{"host", "port", "ssl", "user", "password", "folder"}` |
| `FORUM_EMAIL_REQUIRE_DMARC` | `True` | Require `dmarc=pass` for new topics by email |
| `FORUM_EMAIL_AUTHSERV_ID` | empty | Trust only the `Authentication-Results` header of this server |

Outgoing mail uses the normal Django email settings.

Not yet checked against the comics.org mail server: that it delivers
`forum+…@` addresses to the `FORUM_EMAIL_ADDRESS` mailbox, and the name it
writes at the start of `Authentication-Results` (the value for
`FORUM_EMAIL_AUTHSERV_ID`).

## Importing an email list archive

```sh
python manage.py forum_import_mbox gcd-main.mbox --group gcd-main --archive-user <username> --dry-run
python manage.py forum_import_mbox gcd-main.mbox --group gcd-main --archive-user <username>
```

The command reads an mbox file, for example a Gmail label exported with Google
Takeout by a member who kept the list mail. Messages are imported in date
order and threaded by `Message-ID`, `In-Reply-To` and `References`; a reply
whose parent is missing joins the imported topic with the same subject. The
original dates are kept, quoted text is removed, and nobody is notified.

A message from the address of a single active GCD account is posted by that
account. Other messages are posted by the archive user and start with the
sender's name, never the address. Every `Message-ID` is logged in
`IncomingEmail`, so running the command again on a newer export adds only the
new messages, and copies of forum posts (`X-GCD-Forum-Post`) are skipped.

## Access and accountability

The main, international and board lists are readable without an account
(read access "Anyone"); posting and every other action need an active GCD
account, and visitors get a page with sign-in and registration links.

Topics and posts keep author, editor, dates and the creation IP address; posts
that arrive by email store `0.0.0.0`, since they have no client IP. `ContentRevision` stores before and after values of
every save and soft delete, with actor and request IP, and is visible only in
the admin. By default the IP comes from `REMOTE_ADDR`; enable
`FORUM_TRUST_X_FORWARDED_FOR` only behind a trusted proxy.

## Performance

`Discussion.post_count` and `Discussion.last_activity` are updated by every
`Post.save`, so topic lists are ordered with an index instead of counting
posts; unread counts are computed only for the topics of the page. Measured on
the development database with 20,000 topics and 200,000 posts: list pages
take 0.1 to 0.5 s and topic pages 0.15 s. Searching (`?q=`) scans post text
with `LIKE` and took 0.4 to 0.7 s.

## Development

```sh
docker compose exec -T web python manage.py migrate forum
docker compose exec -T web python -m pytest apps/forum -q
```

The forum templates use the main Tailwind build: their paths are listed in
`tailwind.config.js`.
