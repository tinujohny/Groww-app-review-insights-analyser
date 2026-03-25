"""Drop reviews whose body text contains emoji characters (using the ``emoji`` package)."""

from __future__ import annotations

from typing import Iterable

import emoji

from phase1.schemas.review import NormalizedReview


def text_contains_emoji(text: str) -> bool:
    """Return True if ``text`` contains at least one emoji."""
    return emoji.emoji_count(text) > 0


def filter_reviews_without_emojis(
    reviews: Iterable[NormalizedReview],
    drop_if_contains_emoji: bool,
) -> list[NormalizedReview]:
    """If ``drop_if_contains_emoji``, remove reviews with any emoji in ``text``; else pass through."""
    rows = list(reviews)
    if not drop_if_contains_emoji:
        return rows
    return [r for r in rows if not text_contains_emoji(r.text)]
