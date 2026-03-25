"""Text helpers for review signal quality (word counts, filtering)."""

from __future__ import annotations

from typing import Callable, Iterable, TypeVar

from phase1.constants import MIN_REVIEW_WORDS

T = TypeVar("T")


def count_words(text: str) -> int:
    """Count whitespace-separated words after stripping outer whitespace."""
    stripped = text.strip()
    if not stripped:
        return 0
    return len(stripped.split())


def has_min_words(text: str, min_words: int = MIN_REVIEW_WORDS) -> bool:
    """Return True if ``text`` has at least ``min_words`` words."""
    return count_words(text) >= min_words


def filter_by_min_words(
    items: Iterable[T],
    text_getter: Callable[[T], str],
    min_words: int = MIN_REVIEW_WORDS,
) -> list[T]:
    """Keep only items whose text (from ``text_getter``) has at least ``min_words`` words."""
    out: list[T] = []
    for item in items:
        text = text_getter(item)
        if has_min_words(text, min_words=min_words):
            out.append(item)
    return out
