"""PII redaction helpers for Phase 3 sanitization."""

from __future__ import annotations

import re
from typing import Iterable

from phase1.schemas.review import NormalizedReview

EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
PHONE_RE = re.compile(r"(?<!\w)(?:\+?\d[\s().-]?){8,}\d(?!\w)")
ORDER_ID_RE = re.compile(r"\b(?:order|ticket|txn|transaction|ref|reference|id)\s*[:#-]?\s*[A-Z0-9-]{5,}\b", re.IGNORECASE)
HANDLE_RE = re.compile(r"(?<!\w)@[A-Za-z0-9_]{2,30}\b")
NAME_HINT_RE = re.compile(
    r"\b(?:my name is|i am|this is)\s+([A-Z][a-z]{1,20})(?:\s+[A-Z][a-z]{1,20})?\b"
)


def redact_pii_text(text: str) -> str:
    """Mask common PII patterns from free-form review text."""
    t = text
    t = EMAIL_RE.sub("[REDACTED_EMAIL]", t)
    t = PHONE_RE.sub("[REDACTED_PHONE]", t)
    t = ORDER_ID_RE.sub("[REDACTED_ID]", t)
    t = HANDLE_RE.sub("[REDACTED_HANDLE]", t)
    t = NAME_HINT_RE.sub("[REDACTED_NAME]", t)
    return t


def redact_review_pii(reviews: Iterable[NormalizedReview]) -> list[NormalizedReview]:
    """Return copied review rows with text redacted."""
    return [r.model_copy(update={"text": redact_pii_text(r.text)}) for r in reviews]
