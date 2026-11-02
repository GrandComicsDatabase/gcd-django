# Importing an email list archive

`forum_import_mbox` posts the messages of one mbox file into one forum group.
It has not yet been run on an export from Google Groups (see "Not yet
checked" at the end of this guide).

```sh
python manage.py forum_import_mbox <file>.mbox --group <slug> --archive-user <username> --dry-run
python manage.py forum_import_mbox <file>.mbox --group <slug> --archive-user <username>
```

The group and the archive user must exist. The command reads the dates of all
messages first, then imports them in date order, threaded by `Message-ID`,
`In-Reply-To` and `References`; a parent must be a post of the same group. A
message that looks like a reply (it has references, or a reply or forward
prefix such as `Re:` or `Fwd:`) but whose parent is not in the group joins the
latest imported topic with the same title, or starts one. Titles lose the
`[<slug>]` tag and those prefixes. The original dates are kept. The text after
a quote header such as "On … wrote:", trailing quoted lines, and everything
from a `-- ` or `--` line on (the signature) are removed. In the copies
delivered to members that were checked (golang-nuts@googlegroups.com, October
2026; TECHWR-L, October 2025), Google's footer, and a group's own footer,
follow a `-- ` line, so they go with the signature. Imported posts are
published at once, without review, and nobody is notified or emailed.

A message from the address of exactly one active GCD account is posted by that
account. Other messages are posted by the archive user and start with
`*<name> wrote on the email list:*`, where the name is the sender's display
name, or `Unknown sender`. The address is not added, but some mail programs
use the address as display name, and then it shows. The address stays in
`IncomingEmail`, which only the admin shows. Every imported or empty message
is logged there with its `Message-ID`; a message whose `Message-ID` is already
logged, in any group or by the email gateway (also when rejected), is skipped,
so each message is imported once. Messages without `Message-ID`, without a
readable `Date`, or copied from the forum (`X-GCD-Forum-Post`) are skipped.

`--dry-run` runs the whole import in one database transaction and rolls it
back. It prints this line, where N + M + K is the number of messages in the
file:

```text
Would import N topics and M replies; skipped K messages (repeated, empty or undated).
```

## Getting the archive

Google lets only the owners of a group download its messages ("Only owners
can download a group's messages and membership",
[Google Account Help](https://support.google.com/accounts/answer/3024190)).
Their export holds the group's "Archived threads and messages with Google
Groups-specific labels", its "Pending messages", its members, and group
information that includes the subject prefix and the footer text
([Google Groups Help](https://support.google.com/groups/answer/9975859)).
Google does not name the file format. Deleted data is not exported, and posts
sent while the group's conversation history was off are not in its history.
A deleted group cannot be restored: keep each Google group, closed to
posting, until its import has been checked.

The owner uses Google Takeout, as the Google Account Help page above
describes. At takeout.google.com, uncheck every product except Groups and
select Next step. Choose "Send download link via email", a one-time archive,
zip and the 50 GB size, which lowers the chance that the archive is split,
then Create export. The link comes in minutes to days. The archive expires in
about 7 days and can be downloaded 5 times; its `archive_browser.html`
describes the files. If an export fails, Google suggests creating another one.

Work or school accounts may miss some data, and their administrator can block
Takeout. The lists linked from the Email Lists FAQ are googlegroups.com
groups, except mycomics-users, which is on the comics.org domain. For a group
on that domain, whose mail Google handles, a super administrator can also use
the Admin console data export, which holds the same data as Takeout plus the
data of ownerless groups; Google adds that "Data created by users in consumer
groups is available only to those users". It needs a super administrator
account at least 30 days old with 2-Step Verification on, and Google Cloud
turned on to reach the export, which is ready after at least 48 hours and is
deleted 60 days after it starts. Workspace editions with Vault, which Google
Workspace for Nonprofits lacks, export group messages as mbox or PST files.

If no owner export holds the messages, the Google Account Help page above
points members to their own mail: "if you get messages delivered to your
email, you can download your history of messages from your email archive."
That holds only what the member received one message at a time ("Each email"
delivery; a digest bundles up to 25 messages) and kept: Gmail empties Trash
and Spam after 30 days. Gmail keeps the member's own posts in Sent Mail, not
in the inbox. In Gmail on a computer:

1. Turn conversation view off (Settings, See all settings, Conversation View),
   so that a label goes only on the messages selected.
2. Search `{list:<list address> to:<list address> cc:<list address>}`, select
   all the results (the Select box, then the link in the notification above
   them) and apply a new label. This also labels the member's own posts and
   the copies sent to the member directly with the list in `To` or `Cc`;
   keep them.
3. Search `label:<label> -to:<list address> -cc:<list address>`: it shows the
   labelled messages that do not name the list in `To` or `Cc`. Take the
   label off digests and Google Groups notices: the import posts every
   message of the file.
4. In Takeout, export only Mail, limited to that label. Takeout keeps each
   message's labels in an `X-Gmail-Labels` header.

## Checking the file

Unzip the archive in a new, empty folder outside the repository, read its
`archive_browser.html`, and find the file of the archived messages; pending
messages must stay out of the import. The files hold members' addresses. On a
development checkout, copy the file to `.cache/forum-import/` (create it with
`mkdir -p .cache/forum-import`; git ignores `.cache`, and the web container
sees the checkout as `/workspace`), and delete it after the import.

This reads the file with the parser the command uses:

```sh
docker compose exec -T web python - .cache/forum-import/<list>.mbox <list address> <<'EOF'
import mailbox, sys
from collections import Counter
from datetime import timezone
from email import message_from_bytes, policy
from email.utils import getaddresses, parseaddr, parsedate_to_datetime

box, address = mailbox.mbox(sys.argv[1], create=False), sys.argv[2].lower()
counts, senders, dates = Counter(), Counter(), []
for key in box.iterkeys():
    message = message_from_bytes(box.get_bytes(key), policy=policy.default)
    counts["messages"] += 1
    counts["without Message-ID"] += not str(message.get("Message-ID", "")).strip()
    try:
        date = parsedate_to_datetime(str(message.get("Date", "")))
        dates.append(date.replace(tzinfo=timezone.utc) if date.tzinfo is None else date)
    except (TypeError, ValueError):
        counts["without a readable Date"] += 1
    sender = parseaddr(str(message.get("From", "")))[1].lower()
    senders[sender] += 1
    counts["sent as the list address"] += sender == address
    to_cc = getaddresses([str(value) for name in ("To", "Cc") for value in message.get_all(name, [])])
    counts["list address not in To or Cc"] += address not in {a.lower() for _, a in to_cc}
    counts["with attachments"] += any(part.is_attachment() or part.get_content_maintype() not in ("text", "multipart")
                                      for part in message.walk())
    body = message.get_body(preferencelist=("plain", "html"))
    counts["HTML only"] += body is not None and body.get_content_type() == "text/html"
    try:
        if body is not None:
            body.get_content()
    except LookupError:
        counts["unknown charset"] += 1
for name in ("messages", "without Message-ID", "without a readable Date", "sent as the list address",
             "list address not in To or Cc", "with attachments", "HTML only", "unknown charset"):
    print(f"{counts[name]:>7}  {name}")
print("dates:", min(dates, default=None), "to", max(dates, default=None))
print("senders:", senders.most_common(10))
EOF
```

What the counts mean for the import:

- 0 messages: the file is empty or not an mbox.
- Messages without `Message-ID` or a readable `Date` are skipped.
- Sent as the list address: Google rewrites the sender as
  `'Name' via <group>`, with the group's address, when the sender's domain
  has a DMARC quarantine or reject policy. The archive user posts these
  messages, under the name `'Name' via <group>`. GitHub's notifications are
  among them: github.com has a quarantine policy.
- A message that names the list in neither `To` nor `Cc` may be a private
  reply, mostly in a member's export.
- Attachments are dropped, and the paragraphs of HTML-only messages run
  together. The import stops at the first unknown charset; the messages
  before it stay imported, and a new run stops at the same message.
- The date range helps the checks after the import.
- The most frequent senders can include mail that tools send to the lists,
  which becomes topics too: the site's new-account notices
  (`new.accounts@comics.org`, to gcd-editor), the voting app's "Open:", "GCD
  Ballot Open:" and "GCD Vote Result:" mails (`voting@comics.org`, seen on
  gcd-board) and GitHub's notifications (under the list address, seen on
  gcd-tech). Look for spam too: the public mycomics-users archive holds four
  conversations, sent "via gcd-italia", that look like spam. Nothing filters
  these messages. Moderators can remove the topics after the import, and a
  new run does not bring them back, since their `Message-ID` stays logged.
- A body line that starts with `From ` and was not escaped as `>From ` splits
  a message: the first part loses the rest of its text, and the tail counts
  as a message without `Message-ID` and `Date`.

Dates are sorted within one run only, so join the files of one list, for
example the exports of several members, into a new file first:

```sh
docker compose exec -T web python - .cache/forum-import/<list>.mbox .cache/forum-import/<part-1>.mbox .cache/forum-import/<part-2>.mbox <<'EOF'
import mailbox, os, sys
if os.path.exists(sys.argv[1]):
    sys.exit(f"{sys.argv[1]} exists: give the name of a new file")
out = mailbox.mbox(sys.argv[1])
for path in sys.argv[2:]:
    box = mailbox.mbox(path, create=False)
    for key in box.iterkeys():
        out.add(box.get_bytes(key))
out.close()
print(len(mailbox.mbox(sys.argv[1], create=False)), "messages in", sys.argv[1])
EOF
```

A message found in two files is imported once: with equal dates, the copy
from the file listed first.

## Trying it on a development copy

A list without a group from migration 0002, such as a committee list, needs a
group created in the admin (`/admin/forum/category/`). If the list has a
subject prefix such as `[<list name>]`, use the text between the brackets as
slug: the import removes only a `[<slug>]` tag, in upper or lower case. A new
group is readable and writable by any GCD user: where the list was closed, set
Read access and Post access to "Group members" and add the members.

The archive user should be an account of its own that nobody signs in to.
Create it in the admin (Add user, with "Password-based authentication" set to
Disabled), not through the site's registration: registration also creates an
indexer profile marked new, and the "New indexer" badge would show on every
imported post. It should not be staff, a moderator or in any site group: its
role badges show on every post it authors, and it can edit them all.

```sh
docker compose exec -T web python manage.py forum_import_mbox .cache/forum-import/<list>.mbox --group <slug> --archive-user <username> --dry-run
```

Topics, replies and skipped messages must add up to the messages counted
above. A `LookupError` instead of the summary means an unknown charset. Then
import without `--dry-run`, and check:

- the admin's Incoming emails (`/admin/forum/incomingemail/`): imported
  messages have the reason `mbox import`; `empty message (mbox import)` means
  that no text was left, as happens to a reply written below "On … wrote:";
- some topics against the list archive on Google Groups: titles, threads,
  dates, names, quotes and footers, accented letters, and Markdown: a line
  that starts with `#12` becomes a heading, and a paragraph that starts with
  `1984.` a numbered list;
- that the same command run again imports 0 topics and 0 replies.

The development database has local accounts only, so most messages go to the
archive user there. Before the production import, check in the admin that the
most frequent senders have one active account each.

## Importing into production

Use the same commands without `docker compose exec -T web`, with the path of
the file on the server, on an export taken when the list stops; a later export
of the same list adds only the new messages. Keep dry runs on a development
copy: a dry run writes everything in one transaction before rolling it back.
Before importing, check that:

- the production database holds no test import: a `Message-ID` already logged
  is skipped in every group;
- the forum tables use `utf8mb4`: in `SHOW TABLE STATUS LIKE 'forum%'`, every
  Collation starts with `utf8mb4`. MySQL's `utf8mb3`, shown as `utf8` in older
  versions, cannot store emoji;
- the group's read access is the one decided for this list's archive, and its
  members are set, since imported posts are visible at once. The Email Lists
  FAQ, [as archived on 3 March 2024](https://web.archive.org/web/20240303200848/https://docs.comics.org/wiki/Email_Lists_FAQ),
  says that only members can view the archives of the lists other than
  gcd-board and gcd-tech; in the forum, every group seeded by 0002 except
  gcd-editor and gcd-error is readable by any GCD user;
- the forum tables are backed up: the command has no undo, and a new run
  repairs nothing (messages logged as empty stay skipped, imported posts are
  not updated).

A reply imported in a later run than its parent is attached to it even when
its date is earlier; the topic page shows it under its parent. A message sent
to two lists goes only to the group imported first.

## What the import leaves out

- Attachments: images and PDFs of archived messages are dropped without a
  note, and a message with only an attachment is skipped as empty. The Email
  Lists FAQ says that the main lists allow attachments.
- Filtering: every message of the file is posted, pending messages too if
  they are in it, digests, notifications and spam; nothing checks that a
  message was sent to the list.
- Record links: comics.org links in imported posts do not link their topic to
  the records.
- Text:
  - quotes mixed into the answer stay, and so do quotes under a header that
    the import does not know, such as Outlook's `From:` … `Sent:` … block;
    of a `* Name [date]:` quote, the header line stays;
  - HTML-only messages lose their line breaks and show entities such as
    `&quot;`;
  - 8-bit text in a message that declares no charset, or `us-ascii`, and
    8-bit headers that are not UTF-8 lose their accented letters (shown as
    `�`);
  - only a `[<slug>]` subject tag is removed: another list prefix, or the
    `[GrandComicsDatabase/gcd-django]` of GitHub's notifications, stays in
    the title.

Not yet checked with a real Google Groups export: the format and names of the
owner's files (Google lists what an owner can export, not the format), the
Takeout screens for Groups, whether pending messages come in a separate file,
whether senders keep their own address, whether the archived messages carry
footers (Google says that members do not see the footer in the Google Groups
conversation view, in Gmail's Sent folder, or when they are in `Cc`), and
whether `From ` lines in bodies are escaped. In 2022 two group owners reported
Takeout exports without the messages: one got only the member list
([Google Groups Help thread](https://support.google.com/groups/thread/181378162)),
the other one pending message as an mbox file, with the error "We weren't able
to fetch all the data you requested", and similar errors from the Admin
console data export; on 15 October 2022 the second wrote that a new Takeout
export "worked fine"
([got-your-back group](https://groups.google.com/g/got-your-back/c/7vZ_4hhJtN4)).
These are community reports, not Google documentation. For a member's Gmail
export: how Takeout limits Mail to one label, what digests and Google Groups
notices look like, and whether every member's copy of a post has the same
`Message-ID`.
