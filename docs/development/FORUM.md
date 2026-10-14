# Forum

`apps/forum` is a discussion forum served under `/forum/` with the site layout.
It replaces the GCD email lists described in the Email Lists FAQ and links each
topic to the GCD records it is about.

## Groups

The data migration `0002_default_groups` creates one group per email list, in
three sections: main, international and specialized. `gcd-contact` is not a
group: it stays an email address for people without an account.

The forum is for GCD users. Each group has a read access and a post access:
any GCD user or the group members, set in the admin; the admin can also open a
group to visitors without an account ("Anyone", read only), and none is open
by default (migration `0005_groups_for_gcd_users`):

| Group | Read | Post |
|---|---|---|
| gcd-editor | members | members |
| gcd-board | any user | members |
| gcd-error | members | any user |
| every other group | any user | any user |

In a group that a user can post to but not read, such as `gcd-error`, the user
sees only the topics they started. Staff and superusers read and post
everywhere.

## Topics and GCD records

A topic can be linked to any number of GCD records: the records whose pages
a message links to. At the bottom of every message box, "Link a GCD record"
searches a record by name and puts its link in the text at the cursor; pasted
links of record pages count too. The box shows the card of every record the
message links to, the same card the post will show, as soon as the link is
there.
The catalog is large (over 230,000 series and 2.6 million issues in the
development copy), so the search keeps few fields and narrows smartly:

- one text box, plus the record type and a language filter that defaults to
  the languages of the user's GCD profile, else to the language of the group;
- a year in the text keeps records active (or first published) that year
  (`Spider-Man 1983`); `#1500`, or a final number when searching issues, is
  the issue number (`Mickey Mouse #219`);
- names are compared without spaces, punctuation, case and accents, and also
  by their GCD sort name, which drops leading articles and puts surnames first,
  so `amazing spiderman` finds "The Amazing Spider-Man" and `kirby` finds
  "Jack Kirby";
- exact names come first, then names that start with the text, then the rest;
  within each, the best known first (issue count, or how many stories credit a
  creator or show a character or group);
- each result shows years, publisher, country, language and size, and more
  results load on demand;
- issues show their cover and series the cover of their first issue, at one
  cover query per result; other records show a person, building or book icon.
  The development database has almost no cover rows, so there most results
  show the icon.

Measured on the development database (2.6 million issues), a warm search
takes 0.03 s (publishers) to 0.6 s (series and issues, all languages). A query
of one or two characters is matched only at the start of names, which the
name indexes serve; from three characters it is also looked for anywhere in
the normalized names, a scan of the table. The box asks 600 ms after the last
key.

`records.parse_record_link` resolves pasted links with the site's own URL
routes (`show_<type>` with a `<type>_id` argument), so only live records of the
types in `records.RECORD_TYPES` are accepted. Links to comics.org record pages
written in a post also link the record to the topic, like cross-references on
GitHub.

Posts show a card for each record they link to, with the cover of issues and
series. Moderators add records without writing a message with "Edit title and
records", and unlink them with × on the topic page. While a new topic's title is typed, topics on
the same records or with the same words in the title are shown, like the
similar questions of Stack Overflow.

Signed-in users can follow a record from its forum page
(`/forum/records/<type>/<id>/`): every new topic about it brings a notification
and an email, if they can read the topic.

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

The "Moderation" page of the forum is the queue of the moderators of each
group (and staff):

- **New members' posts.** The first post of an account without approved
  changes to the database, from the web or by email, waits there until a
  moderator publishes or rejects it, like "approve post count" in Discourse
  and the moderation of new members in Google Groups. The moderators get a
  notification (staff, when the group has none). Members with an earlier post,
  also one imported from the list archives, moderators and indexers post
  directly. `FORUM_REVIEW_FIRST_POSTS = False` turns the review off.
- **Reports.** Moderators remove the reported content or dismiss the report.

A topic that is moved keeps `moved_from`, `moved_by` and `moved_at`, and the old
group keeps listing it as "Moved to …", like a shadow topic.

A `Suspension` (admin) revokes posting in one group, or in every group when the
group is empty, until an optional date. Suspended users can still read.

Against floods, from the web or by email, posting has daily limits that grow
with the work done on the database (see "Trust" below). Removed posts still
count.

## Database changes and experts

The forum reads, and never writes, the change history of the database
(`apps.oi`: changesets and the revision class of each record type).

- **Fixes.** A topic lists the changes (changesets) linked to it, with their
  state, and suggests the changes to its records made since the topic started.
  The topic author, group moderators, editors and staff link changes; an
  indexer links their own. When a linked change is approved, the topic is
  marked fixed and solved, and its followers get a notification. The check runs
  when the topic is viewed or a change is linked, and in `forum_mail` for the
  approvals that happen in between.
- **Who knows these records.** A topic shows the active users with the most
  approved changes to its records (for a series, its issues count too).
- **Trust.** Posting limits depend on the work done on the database: accounts
  without approved changes may start 3 topics and post 20 messages a day
  (`FORUM_NEW_MAX_TOPICS_PER_DAY`, `FORUM_NEW_MAX_POSTS_PER_DAY`), indexers 20
  and 100, and indexers with at least 100 approved changes, editors, staff and
  the moderators of a group have no limit.

## Agenda, ballots and consensus

Votes stay in the GCD voting system (`apps.voting`: agendas, ballots, quorum,
secret ballots, ranked choice). A group whose agenda has a mailing list with the
group's name (for example `gcd-policy@…`) shows its open agenda items and
ballots, each with its forum topic or a link to start it. Coordinators (the
group moderators) link a topic to its agenda item and ballot; the topic shows
the ballot deadline, the votes cast toward the quorum and the result.

The forum adds the consensus step of the Policy Procedures: after three days of
discussion a coordinator seeks consensus; members can object, and an objection
becomes a post and moves the item to a vote; with no objection in one week and
one day, a coordinator declares the item passed by consensus.

## Writing

Every message box, for a new topic, a reply or an edit, is the same framed box
(`_editor.html`), like the comment box of GitHub:

- Write and Preview tabs, with "Attach images or PDFs" beside them; Preview
  shows the text as the post will show it, in place of the text;
- the text, then the files to send as tiles with × and the cards of the
  linked GCD records;
- "Link a GCD record" at the bottom.

Files are added with Attach, by dropping them on the box or by pasting an image
(a screenshot) into the text; a second choice adds to the first. The box
refuses at once, with the server's words, a sixth file, a file over the size
limit or a file that is not an image or a PDF; the server checks every file
again. A reply sent back with an error keeps its files; a new topic sent back
with an error says to attach them again, since a page cannot refill a file
input. An edit has no Attach. Lines starting with `>` are quotes, as in email,
and a line with fewer `>` ends the quote, so answers written between quoted
lines stay outside them.

Each post shows ▲ and Reply; its ⋯ menu holds
Quote (the selected text of the post, or the whole post), Accept as the answer,
Edit, Remove and Report. The menu of the first post also holds the actions on
the topic: edit the title and records, move, pin, close, close as a duplicate,
remove, and report the topic. Unsent text is kept as a draft in the browser:
a reply's until it is posted, a new topic's until the next page shows it
published, so text sent into an error (a proxy refusing large files, a
timeout) is still there after Back.

People are named as on the rest of GCD, by the first and last name of their
indexer profile, never by the username, which GCD builds from the email
address: in posts, topic lists, emails (`From: Maria Rossi via GCD Forum`),
feeds and the structured data of public topics. There are no `@` mentions for
now; Reply and Quote name the person in the text only.

Posts can carry up to five images (JPEG, PNG, GIF, WebP) or PDFs of 10 MB each
(`FORUM_ATTACHMENT_MAX_SIZE`), such as scans of covers and indicia. A file is
accepted for its content, read by Pillow or starting as a PDF, never for its
name; SVG and HTML are refused. Files are stored in `FORUM_ATTACHMENTS_DIR`
(default: `forum_attachments` next to `MEDIA_ROOT`), outside the public media,
and served by the forum to those who can read the post, so the files of
members-only groups stay private. Images show under the post; PDFs download.
The web server must accept uploads of that size.

## Search

The search box finds topics by their title and the text of their posts, with
the MySQL FULLTEXT indexes of migration 0004 (boolean mode), so its time does
not grow with a scan of every post. Every word is required and also matches as
the start of a longer word (`spider` finds Spider-Man); `"quoted words"` must
appear as a phrase. Topics whose title matches come first, then by relevance;
each result shows the matching piece of the post, with the words marked, and
links to that post. Filters: `by:Rossi` or `by:"Maria Rossi"` (posts by the
people whose first or last name has words starting so),
`after:2020-01-31` and `before:2020-12-31`. Words of one or two letters and
MySQL stopwords are not indexed; a search of only such words looks at titles.
Inside a group page, the search covers that group.

## Reading long topics

Replies are nested one level deep, as in GitHub Discussions: a reply to a
reply stays under the top-level post and says whom it answers. Topics show 20
top-level posts per page; post links (`?post=<id>`) open the page that holds
the post. The topic page asks every 30 seconds, while it is visible, whether
others have replied, and offers a link to the new replies.

Next to author names the forum shows their roles: staff, board and editor
(from the site groups), moderator of the group, and new indexer. An edited post
links to its earlier versions, with the name of who edited them; IP addresses
stay in the admin.

## Polls

A new topic can carry a poll: from 2 to 20 options, one or more choices, and
an optional closing date. Everyone who can post in the group votes and can
change their vote until the poll closes; in `gcd-board` only members vote. The
topic author or a moderator can close the poll. Results show after voting,
when the poll is closed, and to people who cannot vote; votes are not shown by
name.

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
  topic and for the members who chose "Every post" by email in the group.
  Members who chose "Weekly summary" get one email a week with the topics that
  had new posts.
  Messages carry `Message-ID`, `In-Reply-To` and `References` (threading in mail
  clients), `List-Id`, and `List-Unsubscribe` with one-click unsubscribe
  (RFC 2369, RFC 8058); the link stops what brought the email: the group's
  "Every post", the topic, or the followed record. Each queued email is checked
  again just before sending: a post removed or held since, or a topic moved
  where the recipient cannot read it, is withdrawn, not sent.
- **Incoming.** Replies go to `forum+r-<user>-<topic>-<signature>@…`, an
  address valid for one user and one topic; the sender must be that user. New
  topics go to `forum+g-<group>@…`; the sender must be the only active GCD
  account with that address and the receiving server must report `dmarc=pass`
  in `Authentication-Results`. Quoted text and the `-- ` signature are removed.
  Automatic messages (`Auto-Submitted`, RFC 3834) are ignored, and every
  `Message-ID` is processed once. Each message is logged in `IncomingEmail`.
  Unknown senders that pass DMARC get one notice; forged senders get nothing.
  Images and PDFs attached to the email are kept with the post, under the same
  checks as on the web; small inline images, such as signature logos, are left
  out, and the post says which attachments were not kept and why. Outgoing
  emails link the attachments of the post.

Run the gateway from cron, for example every minute; it also sends the weekly
summaries that are due. A run that starts while the previous one is still
working stops at once (MySQL `GET_LOCK`), so no email goes out twice. Each step
(mailbox, fixed topics, sending) runs on its own: a mailbox that cannot be read
does not stop the sending; the failed step is logged and the command exits
with an error. Mail servers that stop answering fail the step after 60
seconds.

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
python manage.py forum_import_mbox <file>.mbox --group <slug> --archive-user <username> --dry-run
python manage.py forum_import_mbox <file>.mbox --group <slug> --archive-user <username>
```

The command posts the messages of an mbox file into a group, threaded and with
their original dates, and imports each `Message-ID` once. It has not yet run
on an export from Google Groups. [FORUM_IMPORT.md](FORUM_IMPORT.md) describes
how to get the archive from Google, check the file, try the import on a
development copy and import into production, and what the import leaves out.

## Feeds and search engines

Only groups the admin opens to visitors have Atom feeds: `/forum/feed/` (new
topics) and `/forum/groups/<group>/feed/` (every post); their topic pages carry a
canonical link and schema.org `DiscussionForumPosting` data. With no open group,
as by default, there are no feeds and search engines see only the sign-in page.

## Access and accountability

Reading, posting and every other action need an active GCD account. Visitors
get a page with sign-in and registration links on every forum page, also when
they open a link to a topic or an attachment, for example from an email; after
signing in they land on that page. On record pages they see "Forum
discussions" without a count. The unsubscribe link of the emails works without
signing in.

Topics and posts keep author, editor, dates and the creation IP address; posts
that arrive by email store `0.0.0.0`, since they have no client IP. `ContentRevision` stores before and after values of
every save and soft delete, with actor and request IP; the IPs are visible only in
the admin, and earlier versions of a post only to its author and the group's
moderators. The IP comes from `REMOTE_ADDR`. Behind Cloudflare, have the web
server set `REMOTE_ADDR` from `CF-Connecting-IP` for Cloudflare's address
ranges only (Cloudflare's "Restoring original visitor IPs") and leave
`FORUM_TRUST_X_FORWARDED_FOR` off. Set it to the number of proxies in front of
the site only when they all append to `X-Forwarded-For`: the forum then takes
the entry the farthest one added, counted from the right, never the
client-written entries on the left.

## Performance

`Discussion.post_count` and `Discussion.last_activity` are updated by every
`Post.save`, so topic lists are ordered with an index instead of counting
posts; unread counts are computed only for the topics of the page. Measured on
the development database with 20,000 topics and 200,000 posts: list pages
take 0.1 to 0.5 s and topic pages 0.15 s. With 200,000 posts written from real
GCD series and creator names, a search page takes 0.3 to 0.75 s (the FULLTEXT
queries 0.08 to 0.47 s, the slowest for words found in nearly every post),
where the earlier `LIKE` search took up to 1.4 s for the query alone and grows
with the number of posts.

## Development

```sh
docker compose exec -T web python manage.py migrate forum
docker compose exec -T web python -m pytest apps/forum -q
```

The forum templates use the main Tailwind build: their paths are listed in
`tailwind.config.js`.
