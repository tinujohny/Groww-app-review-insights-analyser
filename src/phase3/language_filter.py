"""Drop reviews whose body text is not in the configured language set (ISO 639-1 via langdetect)."""

from __future__ import annotations

from typing import Iterable, Optional

from langdetect import detect
from langdetect.lang_detect_exception import LangDetectException

from phase1.schemas.review import NormalizedReview


def parse_allowed_language_codes(setting_value: str) -> frozenset[str]:
    """Parse comma-separated ISO 639-1 codes from settings (e.g. ``en`` or ``en, de``)."""
    return frozenset(
        part.strip().lower()
        for part in setting_value.split(",")
        if part.strip()
    )


def detect_language_code(text: str) -> Optional[str]:
    """Return detected language code, or None if detection fails."""
    try:
        return detect(text)
    except LangDetectException:
        return None


def text_allowed_for_languages(
    text: str,
    allowed: frozenset[str],
    strict_on_detection_failure: bool,
) -> bool:
    """
    Return True if the text should be kept.

    If detection fails: keep when ``not strict_on_detection_failure``, else drop.
    """
    code = detect_language_code(text)
    if code is None:
        return not strict_on_detection_failure
    return code.lower() in allowed


def filter_reviews_by_language(
    reviews: Iterable[NormalizedReview],
    allowed: frozenset[str],
    strict_on_detection_failure: bool,
) -> list[NormalizedReview]:
    """Remove reviews whose detected language is not in ``allowed``."""
    return [
        r
        for r in reviews
        if text_allowed_for_languages(r.text, allowed, strict_on_detection_failure)
    ]
