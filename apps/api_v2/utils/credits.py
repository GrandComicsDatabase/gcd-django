# SPDX-FileCopyrightText: Grand Comics Database contributors
# SPDX-License-Identifier: GPL-3.0-only

"""Credit helpers for the v2 API."""

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


def _credit_sort_key(credit):
    """Return the stable public ordering key for normalized credits."""
    return (credit.credit_type.sort_code, credit.id)


def _story_credits(obj, *, prefetched_attr):
    """Return active normalized story credits in public display order."""
    credits = getattr(obj, prefetched_attr, None)
    if credits is None:
        return (
            obj.credits.filter(deleted=False)
            .select_related(
                'creator__creator',
                'credit_type',
            )
            .order_by(
                'credit_type__sort_code',
                'id',
            )
        )
    return sorted(
        (credit for credit in credits if not credit.deleted),
        key=_credit_sort_key,
    )


def collect_story_credit_entries(obj, *, prefetched_attr):
    """Return structured story credits for direct story responses.

    The public baseline contract is intentionally narrow: creator reference
    plus role. Legacy text fields are not included because they do not carry a
    stable creator id.
    """
    return [
        {
            'creator': {
                'id': credit.creator.creator_id,
                'name': credit.creator.name,
            },
            'role': credit.credit_type.name,
        }
        for credit in _story_credits(obj, prefetched_attr=prefetched_attr)
    ]
