"""Phase 3 sanitization tests: cleanup/dedupe/noise + PII redaction."""

from __future__ import annotations

import datetime

from phase1.config import AppSettings
from phase1.schemas import NormalizedReview, ReviewSource
from phase3.pipeline import apply_phase3_text_filters


def _mk(text: str) -> NormalizedReview:
    return NormalizedReview(
        source=ReviewSource.APP_STORE,
        rating=5,
        text=text,
        review_date=datetime.date(2026, 3, 22),
        week_bucket="2026-W12",
    )


def test_phase3_dedupes_and_normalizes_whitespace() -> None:
    rows = [
        _mk("Great   app with   useful features for daily use"),
        _mk("great app with useful features for daily use!!!"),
    ]
    s = AppSettings(
        _env_file=None,
        review_languages="en",
        strict_language_detection=False,
        drop_reviews_with_emojis=False,
    )
    out = apply_phase3_text_filters(rows, s)
    assert len(out) == 1
    assert "  " not in out[0].text


def test_phase3_redacts_email_phone_and_handle() -> None:
    row = _mk(
        "My email is user@example.com call me at +1 415 555 0123 and ping @john_doe for details please"
    )
    s = AppSettings(
        _env_file=None,
        review_languages="en",
        strict_language_detection=False,
        drop_reviews_with_emojis=False,
    )
    out = apply_phase3_text_filters([row], s)
    assert len(out) == 1
    t = out[0].text
    assert "[REDACTED_EMAIL]" in t
    assert "[REDACTED_PHONE]" in t
    assert "[REDACTED_HANDLE]" in t
