"""Text cleanup and duplicate/noise filtering for Phase 3."""

from __future__ import annotations

import re
from typing import Iterable

from phase1.schemas.review import NormalizedReview
from phase1.text_utils import count_words

_WS_RE = re.compile(r"\s+")
_PUNCT_RE = re.compile(r"[^\w\s]+", flags=re.UNICODE)


def normalize_whitespace(text: str) -> str:
    """Collapse repeated whitespace into single spaces."""
    return _WS_RE.sub(" ", text).strip()


def dedupe_key(text: str) -> str:
    """Case-insensitive canonical key used for duplicate detection."""
    compact = normalize_whitespace(text).lower()
    compact = _PUNCT_RE.sub("", compact)
    return compact


def is_noise_text(text: str) -> bool:
    """Heuristic filter for empty / near-empty low-signal review bodies."""
    t = normalize_whitespace(text)
    if not t:
        return True
    if len(t) < 3:
        return True
    if count_words(t) < 2:
        return True
    alnum = sum(ch.isalnum() for ch in t)
    if alnum == 0:
        return True
    alpha = sum(ch.isalpha() for ch in t)
    if alpha < 2:
        return True
    return False


def cleanup_and_dedupe_reviews(reviews: Iterable[NormalizedReview]) -> list[NormalizedReview]:
    """Normalize text, drop noise rows, and remove duplicates by canonical body text."""
    out: list[NormalizedReview] = []
    seen: set[str] = set()
    for row in reviews:
        cleaned = normalize_whitespace(row.text)
        if is_noise_text(cleaned):
            continue
        k = dedupe_key(cleaned)
        if k in seen:
            continue
        seen.add(k)
        out.append(row.model_copy(update={"text": cleaned}))
    return out
