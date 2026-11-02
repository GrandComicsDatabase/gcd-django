import os
import shutil
import tempfile
from email.message import EmailMessage as RawEmail
from io import BytesIO
from unittest import mock

from django.core.files.base import ContentFile
from django.core.files.storage import FileSystemStorage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth import get_user_model
from django.db import transaction
from django.test import Client, TransactionTestCase, override_settings
from django.urls import reverse
from PIL import Image

from apps.forum import mail as gateway
from apps.forum.attachments import (
    MAX_FILES, MAX_MEGAPIXELS, PREVIEW_SIZE, STORE_FAILED, detect, files_kept_if_committed, save_attachments,
)
from apps.forum.models import (
    Attachment, Category, ContentRevision, Discussion, IncomingEmail, Post, TopicSubscription,
)

from .base import ForumTestCase


def image_bytes(size=(40, 30), kind="PNG"):
    """The bytes of a red image of the given size, saved by Pillow in the given format."""
    buffer = BytesIO()
    Image.new("RGB", size, "red").save(buffer, kind)
    return buffer.getvalue()


PDF_BYTES = b"%PDF-1.4\n1 0 obj << >> endobj\ntrailer << >>\n%%EOF\n"


class AttachmentTests(ForumTestCase):
    """Images and PDFs sent with posts, from the web or by email: checks, display, access and emails."""

    def setUp(self):
        """Store attachments in a temporary folder, and set the forum email address and the site URL."""
        super().setUp()
        self.folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.folder, ignore_errors=True)
        override = override_settings(FORUM_ATTACHMENTS_DIR=self.folder, FORUM_EMAIL_ADDRESS="forum@comics.org",
                                     SITE_URL="https://www.comics.org/")
        override.enable()
        self.addCleanup(override.disable)
        # The field's storage is built when the model loads, so the setting alone would leave files in the checkout.
        for name in ("file", "preview"):
            storage = mock.patch.object(Attachment._meta.get_field(name), "storage",
                                        FileSystemStorage(location=self.folder))
            storage.start()
            self.addCleanup(storage.stop)

    def reply(self, *files, content="See the scan."):
        """Reply to the test topic as the other user, with the files attached."""
        self.client.force_login(self.other)
        return self.client.post(reverse("forum:reply", args=[self.discussion.slug]),
                                {"content": content, "attachments": list(files)})

    def test_images_and_pdfs_are_shown_with_the_post_and_served_to_readers(self):
        """An image and a PDF show with the post; the image is served as sent, the PDF as a download."""
        self.reply(SimpleUploadedFile("cover scan.png", image_bytes(), "image/png"),
                   SimpleUploadedFile("indicia.pdf", PDF_BYTES, "application/pdf"))
        image, pdf = Attachment.objects.order_by("pk")
        self.assertEqual((image.name, image.content_type, pdf.content_type),
                         ("cover_scan.png", "image/png", "application/pdf"))
        page = self.client.get(self.discussion.get_absolute_url())
        self.assertContains(page, f'src="{image.get_absolute_url()}"')
        self.assertContains(page, "indicia.pdf")
        response = self.client.get(image.get_absolute_url())
        self.assertEqual((response.status_code, response["Content-Type"], response["X-Content-Type-Options"]),
                         (200, "image/png", "nosniff"))
        self.assertEqual(b"".join(response.streaming_content), image_bytes())
        self.assertTrue(self.client.get(pdf.get_absolute_url())["Content-Disposition"].startswith("attachment"))

    def test_files_are_judged_by_their_content(self):
        """Files are typed by content: an SVG named .png is refused, a JPEG named .txt is saved as .jpg."""
        response = self.reply(SimpleUploadedFile("cover.png", b"<svg onload=alert(1)>", "image/png"))
        self.assertContains(response, "cover.png: not a JPEG, PNG, GIF or WebP image, or a PDF.", status_code=422)
        self.reply(SimpleUploadedFile("photo.txt", image_bytes(kind="JPEG"), "text/plain"))
        self.assertEqual(Attachment.objects.get().content_type, "image/jpeg")
        self.assertEqual(Attachment.objects.get().name, "photo.jpg")

    @override_settings(FORUM_ATTACHMENT_MAX_SIZE=100)
    def test_size_and_number_are_limited(self):
        """A file over the size limit, or more than MAX_FILES files, are refused with 422, and no attachment
        is saved."""
        response = self.reply(SimpleUploadedFile("big.png", image_bytes((400, 400)), "image/png"))
        self.assertContains(response, "big.png: larger than 0 MB.", status_code=422)
        files = [SimpleUploadedFile(f"scan{number}.png", image_bytes(), "image/png") for number in range(MAX_FILES + 1)]
        with override_settings(FORUM_ATTACHMENT_MAX_SIZE=10 * 1024 * 1024):
            response = self.reply(*files)
        self.assertContains(response, f"Attach at most {MAX_FILES} files.", status_code=422)
        self.assertFalse(Attachment.objects.exists())

    def test_attachments_of_members_only_groups_stay_private(self):
        """Attachments in a members-only group are for members: others get 404, visitors the sign-in page."""
        editors = Category.objects.get(slug="gcd-editor")
        editors.members.add(self.other)
        topic = self.make_topic("Editors only", editors, self.other)
        self.client.force_login(self.other)
        self.client.post(reverse("forum:reply", args=[topic.slug]), {
            "content": "Private scan", "attachments": [SimpleUploadedFile("a.png", image_bytes(), "image/png")]})
        url = Attachment.objects.get().get_absolute_url()
        self.assertEqual(self.client.get(url).status_code, 200)
        self.client.force_login(self.author)
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertContains(Client().get(url), "Sign in", status_code=403)

    def test_email_attachments_are_kept_but_not_signature_logos(self):
        """An emailed reply keeps its scan, notes the refused file in the post and drops the inline logo."""
        self.other.email = "other@example.com"
        self.other.save()
        message = RawEmail()
        message["From"] = "other@example.com"
        message["To"] = gateway.reply_address(self.other, self.discussion)
        message["Subject"] = "Re: A forum topic"
        message["Message-ID"] = "<scan@example.com>"
        message.set_content("Here is the scan.")
        message.add_attachment(image_bytes((600, 900), "JPEG"), maintype="image", subtype="jpeg",
                               filename="Topolino 1500.jpg")
        message.add_attachment(b"MZ fake program", maintype="application", subtype="octet-stream",
                               filename="virus.exe")
        logo = image_bytes((20, 20))
        message.add_attachment(logo, maintype="image", subtype="png", filename="logo.png",
                               disposition="inline", cid="<logo@example.com>")
        record = gateway.process_message(message.as_bytes())
        self.assertEqual([item.name for item in record.post.attachments.all()], ["Topolino_1500.jpg"])
        self.assertIn("“virus.exe” was not kept", record.post.content)

    def fail_storage_after(self, stored):
        """Let the storage write this many files, then fail like a full disk, leaving the file it was writing
        cut short."""
        storage = Attachment._meta.get_field("file").storage
        real_save, calls = storage.save, []

        def save(name, content, *args, **kwargs):
            """Store the first files; the next one is cut short and the write raises OSError."""
            calls.append(name)
            if len(calls) > stored:
                real_save(name, ContentFile(b"cut short"))
                raise OSError(28, "No space left on device")
            return real_save(name, content, *args, **kwargs)

        patcher = mock.patch.object(storage, "save", side_effect=save)
        patcher.start()
        self.addCleanup(patcher.stop)

    def stored_files(self):
        """The files in the attachments folder."""
        return [name for _, _, names in os.walk(self.folder) for name in names]

    def test_a_reply_whose_files_cannot_be_stored_is_not_posted_and_leaves_no_files(self):
        """When the second file cannot be stored, the reply comes back with a message, no post is saved
        and neither the first file nor the one cut short stays on disk."""
        self.fail_storage_after(1)
        with self.assertLogs("apps.forum.attachments", "ERROR"):
            response = self.reply(SimpleUploadedFile("a.png", image_bytes(), "image/png"),
                                  SimpleUploadedFile("b.png", image_bytes(), "image/png"))
        self.assertContains(response, STORE_FAILED, status_code=422)
        self.assertEqual(self.discussion.posts.count(), 1)
        self.assertFalse(Attachment.objects.exists())
        self.assertEqual(self.stored_files(), [])

    def test_a_topic_whose_files_cannot_be_stored_is_not_created(self):
        """A new topic whose file cannot be stored shows the form again with the message; nothing is saved."""
        self.fail_storage_after(0)
        self.client.force_login(self.other)
        with self.assertLogs("apps.forum.attachments", "ERROR"):
            response = self.client.post(reverse("forum:discussion-create"), {
                "category": self.main.pk, "title": "Scans", "content": "Two scans",
                "attachments": [SimpleUploadedFile("a.png", image_bytes(), "image/png")]})
        self.assertContains(response, STORE_FAILED)
        self.assertFalse(Discussion.all_objects.filter(title="Scans").exists())
        self.assertEqual(self.stored_files(), [])

    def test_an_email_whose_files_cannot_be_stored_is_rejected_with_the_reason(self):
        """An emailed reply whose file cannot be stored is not posted, and its record says why."""
        self.other.email = "other@example.com"
        self.other.save()
        message = RawEmail()
        message["From"] = "other@example.com"
        message["To"] = gateway.reply_address(self.other, self.discussion)
        message["Subject"] = "Re: A forum topic"
        message["Message-ID"] = "<full-disk@example.com>"
        message.set_content("Here is the scan.")
        message.add_attachment(image_bytes(kind="JPEG"), maintype="image", subtype="jpeg", filename="scan.jpg")
        self.fail_storage_after(0)
        with self.assertLogs("apps.forum.attachments", "ERROR"):
            record = gateway.process_message(message.as_bytes())
        self.assertEqual((record.status, record.reason), (
            IncomingEmail.Status.REJECTED, "the attached files could not be stored; send the message again later"))
        self.assertEqual(self.discussion.posts.count(), 1)
        self.assertEqual(self.stored_files(), [])

    def test_a_missing_file_gives_404_and_a_warning(self):
        """An attachment whose file is gone from the folder gives readers a 404 and logs a warning."""
        self.reply(SimpleUploadedFile("a.png", image_bytes(), "image/png"))
        attachment = Attachment.objects.get()
        os.remove(os.path.join(self.folder, attachment.file.name))
        with self.assertLogs("apps.forum.views", "WARNING") as logs:
            response = self.client.get(attachment.get_absolute_url())
        self.assertEqual(response.status_code, 404)
        self.assertIn(attachment.file.name, logs.output[0])

    def test_multi_picture_jpegs_and_pdfs_after_a_bom_are_accepted(self):
        """A camera's Multi-Picture JPEG is a JPEG, and a PDF whose header follows a BOM is a PDF."""
        buffer = BytesIO()
        Image.new("RGB", (40, 30), "red").save(buffer, "MPO", save_all=True,
                                               append_images=[Image.new("RGB", (40, 30), "blue")])
        self.assertEqual(detect(buffer.getvalue()), ("image/jpeg", ".jpg"))
        self.assertEqual(detect(b"\xef\xbb\xbf" + PDF_BYTES), ("application/pdf", ".pdf"))

    def test_images_over_the_pixel_limit_are_refused_with_the_reason(self):
        """An image of more than MAX_MEGAPIXELS is refused, saying to reduce the resolution."""
        side = int((MAX_MEGAPIXELS * 1_000_000) ** 0.5) + 10
        buffer = BytesIO()
        Image.new("1", (side, side)).save(buffer, "PNG")
        response = self.reply(SimpleUploadedFile("scan.png", buffer.getvalue(), "image/png"))
        self.assertContains(response, f"scan.png: more than {MAX_MEGAPIXELS} megapixels: reduce the resolution",
                            status_code=422)

    def test_large_and_animated_images_are_shown_as_still_previews(self):
        """A large image shows as a preview of at most PREVIEW_SIZE pixels that links to the full image; an
        animated GIF shows its first frame; a small still image shows as it is."""
        frames = [Image.new("RGB", (60, 40), color) for color in ("red", "blue")]
        animated = BytesIO()
        frames[0].save(animated, "GIF", save_all=True, append_images=frames[1:], loop=0)
        self.reply(SimpleUploadedFile("wide.png", image_bytes((PREVIEW_SIZE + 400, 900)), "image/png"),
                   SimpleUploadedFile("anim.gif", animated.getvalue(), "image/gif"),
                   SimpleUploadedFile("small.png", image_bytes(), "image/png"))
        wide, anim, small = Attachment.objects.order_by("pk")
        self.assertTrue(wide.preview and anim.preview)
        self.assertFalse(small.preview)
        page = self.client.get(self.discussion.get_absolute_url())
        self.assertContains(page, f'src="{wide.get_absolute_url()}?preview=1"')
        self.assertContains(page, f'src="{small.get_absolute_url()}"')
        response = self.client.get(wide.get_preview_url())
        with Image.open(BytesIO(b"".join(response.streaming_content))) as shown:
            expected = (PREVIEW_SIZE, 900 * PREVIEW_SIZE // (PREVIEW_SIZE + 400))
            self.assertEqual((response["Content-Type"], shown.size), ("image/jpeg", expected))
        with Image.open(BytesIO(b"".join(self.client.get(anim.get_preview_url()).streaming_content))) as still:
            self.assertFalse(getattr(still, "is_animated", False))

    def test_images_are_described_for_readers_who_cannot_see_them(self):
        """An image's description becomes its alt text; without one the alt text says whose image it is, not
        its file name."""
        self.client.force_login(self.other)
        self.client.post(reverse("forum:reply", args=[self.discussion.slug]), {
            "content": "Two scans", "attachment_description": ["Cover of Topolino 1500", ""],
            "attachments": [SimpleUploadedFile("IMG_2034.png", image_bytes(), "image/png"),
                            SimpleUploadedFile("IMG_2035.png", image_bytes(), "image/png")]})
        self.assertEqual(list(Attachment.objects.order_by("pk").values_list("description", flat=True)),
                         ["Cover of Topolino 1500", ""])
        page = self.client.get(self.discussion.get_absolute_url())
        self.assertContains(page, 'alt="Cover of Topolino 1500"')
        self.assertContains(page, f'alt="Image 2 attached by GCD user {self.other.pk}"')

    def test_readers_keep_a_file_for_a_day_and_shared_caches_never(self):
        """A file never changes: the reader's browser keeps it for a day, and no shared cache keeps it."""
        self.reply(SimpleUploadedFile("a.png", image_bytes(), "image/png"))
        response = self.client.get(Attachment.objects.get().get_absolute_url())
        self.assertEqual(response["Cache-Control"], "private, max-age=86400")

    def test_emails_to_subscribers_link_the_attachments(self):
        """The email that sends a post to a follower lists each attachment with its full link."""
        TopicSubscription.objects.create(user=self.author, discussion=self.discussion)
        self.author.email = "author@example.com"
        self.author.save()
        self.reply(SimpleUploadedFile("scan.png", image_bytes(), "image/png"))
        post = Post.objects.latest("pk")
        body = gateway.build_message(post, self.author).body
        self.assertIn(f"Attached: scan.png https://www.comics.org{post.attachments.get().get_absolute_url()}", body)


class PreviewTests(ForumTestCase):
    """Previews show what the file shows: turned upright, with grey tones and colour profiles kept."""

    def preview_of(self, image, kind, **options):
        """The preview Pillow opens of the image saved in that format with the options."""
        from apps.forum.attachments import preview

        buffer = BytesIO()
        image.save(buffer, kind, **options)
        data, _ = preview(buffer.getvalue(), f"image/{kind.lower()}")
        return Image.open(BytesIO(data))

    def test_previews_are_turned_as_the_camera_says(self):
        """A portrait photo stored on its side with orientation 6 previews upright."""
        image = Image.new("RGB", (PREVIEW_SIZE + 800, PREVIEW_SIZE), "white")
        exif = image.getexif()
        exif[0x0112] = 6
        shown = self.preview_of(image, "JPEG", exif=exif.tobytes())
        self.assertGreater(shown.size[1], shown.size[0])

    def test_16_bit_grey_previews_keep_their_tones(self):
        """A 16-bit grey scan previews in its greys, not white."""
        grey = Image.linear_gradient("L").resize((PREVIEW_SIZE + 400,) * 2).convert("I")
        shown = self.preview_of(grey.point(lambda value: value * 257).convert("I;16"), "PNG")
        self.assertEqual(shown.convert("L").getextrema(), (0, 255))

    def test_previews_keep_an_rgb_colour_profile(self):
        """A photo's RGB colour profile goes with its preview, so its colours do not shift."""
        from PIL import ImageCms

        profile = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
        shown = self.preview_of(Image.new("RGB", (PREVIEW_SIZE + 400, 900), "red"), "JPEG", icc_profile=profile)
        self.assertEqual(shown.info.get("icc_profile"), profile)


@override_settings(FORUM_REVIEW_FIRST_POSTS=False, FORUM_EMAIL_ADDRESS="forum@comics.org",
                   SITE_URL="https://www.comics.org/")
class RollbackTests(TransactionTestCase):
    """Files stored for a post whose transaction then rolls back are deleted with it; committed ones stay."""

    make_topic = ForumTestCase.make_topic

    def setUp(self):
        """Store attachments in a temporary folder, and make a topic by rollback-author in gcd-main."""
        self.folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.folder, ignore_errors=True)
        for name in ("file", "preview"):
            storage = mock.patch.object(Attachment._meta.get_field(name), "storage",
                                        FileSystemStorage(location=self.folder))
            storage.start()
            self.addCleanup(storage.stop)
        users = get_user_model().objects
        self.author = users.create_user("rollback-author", password="x")
        self.other = users.create_user("rollback-other", password="x", email="other@example.com")
        self.main = Category.objects.get(slug="gcd-main")
        self.discussion = self.make_topic("A forum topic", self.main, self.author)
        self.client = Client(raise_request_exception=False)
        self.client.force_login(self.other)

    def _fixture_teardown(self):
        """Delete what the test made instead of emptying every table, which would also remove the groups of
        the data migration that the other tests use."""
        users = get_user_model().objects.filter(username__startswith="rollback-")
        Post.all_objects.filter(author__in=users).hard_delete()
        Discussion.all_objects.filter(author__in=users).hard_delete()
        ContentRevision.objects.filter(actor__in=users).delete()
        IncomingEmail.objects.all().delete()
        users.delete()

    def stored_files(self):
        """The files in the attachments folder."""
        return [name for _, _, names in os.walk(self.folder) for name in names]

    def test_a_reply_that_fails_after_storing_its_files_leaves_none(self):
        """A reply whose publication fails once its files are stored (a database error while notifying) is
        rolled back, and its files are deleted."""
        with mock.patch("apps.forum.views.publish", side_effect=RuntimeError("database gone")), \
                self.assertLogs("apps.forum.attachments", "WARNING"):
            response = self.client.post(reverse("forum:reply", args=[self.discussion.slug]), {
                "content": "See the scan.",
                "attachments": [SimpleUploadedFile("scan.png", image_bytes((PREVIEW_SIZE + 10, 50)), "image/png")]})
        self.assertEqual(response.status_code, 500)
        self.assertEqual((Attachment.objects.count(), self.stored_files()), (0, []))

    def test_a_topic_that_fails_after_storing_its_files_leaves_none(self):
        """A new topic whose publication fails once its files are stored leaves no topic and no file."""
        with mock.patch("apps.forum.activity.publish", side_effect=RuntimeError("database gone")), \
                self.assertLogs("apps.forum.attachments", "WARNING"):
            response = self.client.post(reverse("forum:discussion-create"), {
                "category": self.main.pk, "title": "Scan of the cover", "content": "See the scan.",
                "attachments": [SimpleUploadedFile("scan.png", image_bytes(), "image/png")]})
        self.assertEqual(response.status_code, 500)
        self.assertFalse(Discussion.all_objects.filter(title="Scan of the cover").exists())
        self.assertEqual(self.stored_files(), [])

    def test_an_email_that_fails_after_storing_its_files_leaves_none(self):
        """An emailed reply rejected once its files are stored is rolled back, and its files are deleted."""
        from apps.forum.mail import Rejected

        message = RawEmail()
        message["From"] = "other@example.com"
        message["To"] = gateway.reply_address(self.other, self.discussion)
        message["Subject"] = "Re: A forum topic"
        message["Message-ID"] = "<rolled-back@example.com>"
        message.set_content("Here is the scan.")
        message.add_attachment(image_bytes(kind="JPEG"), maintype="image", subtype="jpeg", filename="scan.jpg")
        with mock.patch("apps.forum.activity.publish", side_effect=Rejected("test")), \
                self.assertLogs("apps.forum.attachments", "WARNING"):
            record = gateway.process_message(message.as_bytes())
        self.assertEqual(record.status, IncomingEmail.Status.REJECTED)
        self.assertEqual((Attachment.objects.count(), self.stored_files()), (0, []))

    def test_files_of_a_committed_reply_stay(self):
        """A reply that is saved keeps its file and its preview."""
        response = self.client.post(reverse("forum:reply", args=[self.discussion.slug]), {
            "content": "See the scan.",
            "attachments": [SimpleUploadedFile("scan.png", image_bytes((PREVIEW_SIZE + 10, 50)), "image/png")]})
        self.assertEqual(response.status_code, 302)
        attachment = Attachment.objects.get()
        self.assertEqual(sorted(self.stored_files()),
                         sorted(os.path.basename(name) for name in (attachment.file.name, attachment.preview.name)))

    def test_files_rolled_back_with_a_savepoint_are_deleted(self):
        """Files stored inside a savepoint that rolls back are deleted, though the outer transaction commits."""
        with self.assertLogs("apps.forum.attachments", "WARNING"):
            with files_kept_if_committed(), transaction.atomic():
                post = Post.objects.create(discussion=self.discussion, author=self.other, content="Kept",
                                           created_by=self.other, updated_by=self.other, ip_address="127.0.0.1")
                try:
                    with transaction.atomic():
                        save_attachments(post, [("scan.png", image_bytes(), ("image/png", ".png"))])
                        raise RuntimeError("undone")
                except RuntimeError:
                    pass
        self.assertTrue(Post.objects.filter(content="Kept").exists())
        self.assertEqual((Attachment.objects.count(), self.stored_files()), (0, []))
