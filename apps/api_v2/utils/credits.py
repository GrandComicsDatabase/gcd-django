# SPDX-FileCopyrightText: Grand Comics Database contributors
# SPDX-License-Identifier: GPL-3.0-only

"""Plain-text credit helpers for the v2 API."""

from apps.gcd.models import CREDIT_TYPES


def _split_legacy_values(value):
    """Return semicolon-delimited legacy credit text as a clean list."""
    if not value:
        return []
    return [part.strip() for part in value.split(';') if part.strip()]


def collect_credit_strings(obj, credit_type, *, prefetched_attr):
    """Return plain-text credits for ``credit_type`` on ``obj``.

    v2 avoids the old template helpers and returns JSON-safe plain text.
    Normalized credit rows are preferred when present; the legacy raw text
    field is appended so older data remains visible.
    """
    credit_type_id = CREDIT_TYPES[credit_type]
    credits = getattr(obj, prefetched_attr, None)
    if credits is None:
        credits = obj.credits.filter(deleted=False).select_related(
            'creator',
            'credit_type',
        )

    entries = [
        credit.creator.name
        for credit in credits
        if credit.credit_type_id == credit_type_id and not credit.deleted
    ]
    entries.extend(_split_legacy_values(getattr(obj, credit_type, '')))
    return entries
