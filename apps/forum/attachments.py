"""Images and PDFs sent with posts, from the web or by email.

A file is accepted for what its content is, never for its name or declared type:
Pillow must read it as a JPEG, PNG, GIF or WebP image, or it must start as a PDF.
SVG and HTML are refused, since a browser runs their scripts.

Images of more than MAX_MEGAPIXELS are refused, and a large or animated image gets a still preview of at
most PREVIEW_SIZE pixels a side, which the post shows, as Discourse shows optimized images: readers'
browsers decode the full image only when they open it.

Files are written while the post's transaction is open, so a full disk is told to the writer. Inside
files_kept_if_committed, the files whose rows the transaction did not commit are deleted when it ends.
"""
import logging
import re
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps
from io import BytesIO
from os.path import basename, splitext

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.db import transaction
from PIL import Image, ImageOps

from .models import Attachment

logger = logging.getLogger(__name__)

# The files written inside files_kept_if_committed whose rows are not committed yet, by path.
_uncommitted = ContextVar("forum_uncommitted_files", default=None)


@contextmanager
def files_kept_if_committed():
    """Around a whole transaction that may store attachments (a request, an email): when it has ended, the
    files written inside it whose rows were not committed are deleted. Their rows were rolled back, by an
    error after the files were written (a database error while notifying) or with a savepoint, so nothing
    would point to them. A file counts as committed when its on_commit callback runs. When the block ends
    while an outer transaction is still open (a test, a caller's transaction), that outcome is not known
    yet, and the files stay."""
    uncommitted = {}
    token = _uncommitted.set(uncommitted)
    try:
        yield
    finally:
        _uncommitted.reset(token)
        if uncommitted and not transaction.get_connection().in_atomic_block:
            storage = Attachment._meta.get_field("file").storage
            for path in list(uncommitted):
                try:
                    storage.delete(path)
                except OSError:
                    logger.exception("Forum: %s, stored for a post that was rolled back, could not be deleted",
                                     path)
            logger.warning("Forum: %s attachment files of rolled back posts deleted", len(uncommitted))


def files_follow_transaction(view):
    """Run the view in one transaction, as ATOMIC_REQUESTS does, inside files_kept_if_committed, so the
    files it stores are deleted when the transaction rolls back. The view is marked non_atomic_requests:
    the transaction is this one, opened inside the files' block."""
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        """The view, its transaction and the files it stores."""
        with files_kept_if_committed(), transaction.atomic():
            return view(request, *args, **kwargs)
    return transaction.non_atomic_requests(wrapper)


def _written(path):
    """Note a stored file as uncommitted until its transaction commits (inside files_kept_if_committed)."""
    uncommitted = _uncommitted.get()
    if uncommitted is not None:
        uncommitted[path] = True
        transaction.on_commit(lambda: uncommitted.pop(path, None))


def _forget(path):
    """A stored file deleted again: nothing to delete at the end of the transaction."""
    uncommitted = _uncommitted.get()
    if uncommitted is not None:
        uncommitted.pop(path, None)

IMAGE_FORMATS = {
    "JPEG": ("image/jpeg", ".jpg"),
    # Multi-Picture JPEGs of cameras and phones: browsers show their first picture.
    "MPO": ("image/jpeg", ".jpg"),
    "PNG": ("image/png", ".png"),
    "GIF": ("image/gif", ".gif"),
    "WEBP": ("image/webp", ".webp"),
}
PDF = ("application/pdf", ".pdf")
ACCEPT = ",".join(dict.fromkeys([kind for kind, _ in IMAGE_FORMATS.values()] + [PDF[0]]))
MAX_FILES = 5
# A 600 dpi scan of a comic page is about 25 megapixels; a spread about 50.
MAX_MEGAPIXELS = 50
PREVIEW_SIZE = 1600


def max_size():
    """FORUM_ATTACHMENT_MAX_SIZE, the largest file accepted in bytes, by default 10 MB."""
    return getattr(settings, "FORUM_ATTACHMENT_MAX_SIZE", 10 * 1024 * 1024)


def detect(data):
    """Return the (content type, extension) of an accepted file, or raise ValidationError."""
    if len(data) > max_size():
        raise ValidationError(f"larger than {max_size() // (1024 * 1024)} MB")
    # PDF readers find the header anywhere in the first 1024 bytes (some files start with a BOM).
    if b"%PDF-" in data[:1024]:
        return PDF
    too_many = f"more than {MAX_MEGAPIXELS} megapixels: reduce the resolution"
    try:
        with Image.open(BytesIO(data)) as image:
            if image.width * image.height > MAX_MEGAPIXELS * 1_000_000:
                raise ValidationError(too_many)
            image.verify()
            kind = IMAGE_FORMATS.get(image.format)
    except Image.DecompressionBombError:
        raise ValidationError(too_many) from None
    except (OSError, SyntaxError, ValueError):
        kind = None
    if kind is None:
        raise ValidationError("not a JPEG, PNG, GIF or WebP image, or a PDF")
    return kind


def clean_name(name, extension):
    """The attachment's name: the upload's stem with each run of characters other than letters, digits, "_"
    and "-" replaced by "_", trimmed of "_" at the ends and cut to 100 characters ("attachment" if empty),
    plus the extension of the detected type."""
    stem = re.sub(r"[^\w-]+", "_", splitext(basename(name or ""))[0]).strip("_")[:100]
    return (stem or "attachment") + extension


class StoreFailed(Exception):
    """The files of a post could not be stored; its message tells the writer what to do."""

    pass


STORE_FAILED = "The files could not be stored. Try again later, or send the message without them."


def preview(data, content_type):
    """A still preview of an image, as (bytes, extension), when the image is animated or larger than
    PREVIEW_SIZE a side; None when it can be shown as it is. Photos become JPEG; images with transparency
    or few colors, PNG."""
    if not content_type.startswith("image/"):
        return None
    with Image.open(BytesIO(data)) as image:
        if not getattr(image, "is_animated", False) and max(image.size) <= PREVIEW_SIZE:
            return None
        # JPEG decodes straight to a smaller scale, so a large photo never fills memory at full size.
        image.draft("RGB", (PREVIEW_SIZE, PREVIEW_SIZE))
        image.seek(0)
        still = image.copy()
    # Turned as the camera's orientation tag says, as browsers show the file itself.
    ImageOps.exif_transpose(still, in_place=True)
    if still.mode.startswith("I"):
        # 16-bit grey, scaled to 8 bits: convert() alone would turn every value above 255 white.
        still = still.convert("I").point(lambda value: value * (1 / 256)).convert("L")
    still.thumbnail((PREVIEW_SIZE, PREVIEW_SIZE))
    # An RGB colour profile still describes the preview's pixels; a CMYK or grey one no longer does.
    profile = still.info.get("icc_profile") if still.mode in ("RGB", "RGBA", "P", "PA") else None
    buffer = BytesIO()
    if content_type == "image/jpeg" or still.mode in ("RGB", "L", "CMYK"):
        still.convert("RGB").save(buffer, "JPEG", quality=85, optimize=True, icc_profile=profile)
        return buffer.getvalue(), ".jpg"
    still.convert("RGBA").save(buffer, "PNG", optimize=True, icc_profile=profile)
    return buffer.getvalue(), ".png"


def save_attachments(post, files):
    """Store the checked files, as (name, data, (content type, extension)) or with a description as a
    fourth item, with the post, and a preview of each large or animated image.

    If storing fails (a full disk, a folder the site cannot write), the error is logged, the files already
    written for the post are deleted and StoreFailed is raised: the caller rolls the post back and tells the
    writer. A file name is fixed before writing, so a file cut short by the failure is deleted too. Inside
    files_kept_if_committed, each stored file waits for its transaction's commit.
    """
    storage = Attachment._meta.get_field("file").storage
    written = []
    try:
        for name, data, (content_type, extension), *description in files:
            attachment = Attachment(post=post, name=clean_name(name, extension), content_type=content_type,
                                    size=len(data), description=(description or [""])[0][:200])
            path = attachment.file.field.generate_filename(attachment, attachment.name)
            written.append(path)
            attachment.file.name = written[-1] = storage.save(path, ContentFile(data))
            _written(written[-1])
            try:
                still = preview(data, content_type)
            except (OSError, SyntaxError, ValueError, Image.DecompressionBombError):
                # Pillow verified the image but cannot decode all of it: the post shows the file itself.
                logger.warning("Forum: no preview for %s of post %s", attachment.name, post.pk, exc_info=True)
                still = None
            if still is not None:
                path = attachment.preview.field.generate_filename(attachment, "preview" + still[1])
                written.append(path)
                attachment.preview.name = written[-1] = storage.save(path, ContentFile(still[0]))
                _written(written[-1])
            attachment.save()
    except Exception as error:
        for path in written:
            _forget(path)
            try:
                storage.delete(path)
            except OSError:
                logger.exception("Forum: %s could not be deleted after a failed post", path)
        if not isinstance(error, OSError):
            raise
        logger.error("Forum: the files of post %s could not be stored", post.pk, exc_info=error)
        raise StoreFailed(STORE_FAILED) from error
