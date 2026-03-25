"""Compose Phase 3 sanitization + filtering after Phase 2 normalization."""

from __future__ import annotations

from phase1.config import AppSettings
from phase1.schemas.review import NormalizedReview
from phase3.emoji_filter import filter_reviews_without_emojis
from phase3.language_filter import (
    filter_reviews_by_language,
    parse_allowed_language_codes,
)
from phase3.pii_redaction import redact_review_pii
from phase3.text_cleanup import cleanup_and_dedupe_reviews


def apply_phase3_text_filters(
    reviews: list[NormalizedReview],
    settings: AppSettings,
) -> list[NormalizedReview]:
    """Apply full Phase 3 pipeline (cleanup, redaction, language, emoji)."""
    # Phase 3 preprocessing first: whitespace cleanup, duplicate elimination, noise removal.
    pre = cleanup_and_dedupe_reviews(reviews)
    # Redact common identity markers before any downstream LLM use.
    redacted = redact_review_pii(pre)

    allowed = parse_allowed_language_codes(settings.review_languages)
    r = filter_reviews_by_language(
        redacted,
        allowed,
        settings.strict_language_detection,
    )
    return filter_reviews_without_emojis(r, settings.drop_reviews_with_emojis)
