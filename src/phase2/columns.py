"""Expected CSV column aliases for public review exports (case-insensitive header match)."""

from __future__ import annotations

from typing import Iterable, Mapping, Optional, Sequence

# Google Play Console — typical review export headers
GOOGLE_PLAY_RATING_ALIASES: tuple[str, ...] = (
    "star rating",
    "review star rating",
)
GOOGLE_PLAY_TEXT_ALIASES: tuple[str, ...] = (
    "review text",
    "text",
)
GOOGLE_PLAY_DATE_ALIASES: tuple[str, ...] = (
    "review last update date and time",
    "review submit date and time",
    "last updated",
)

# App Store Connect / similar exports
APP_STORE_RATING_ALIASES: tuple[str, ...] = (
    "rating",
    "star rating",
)
APP_STORE_TEXT_ALIASES: tuple[str, ...] = (
    "review",
    "review text",
    "comments",
    "body",
)
APP_STORE_DATE_ALIASES: tuple[str, ...] = (
    "date",
    "review date",
    "last modified",
    "created",
)


def normalize_header(name: str) -> str:
    return " ".join(name.strip().lower().split())


def resolve_column(headers: Sequence[str], aliases: Iterable[str]) -> Optional[str]:
    """Return the actual CSV header string that matches one of ``aliases``, or None."""
    lookup: dict[str, str] = {}
    for h in headers:
        if not h:
            continue
        lookup[normalize_header(h)] = h
    for a in aliases:
        key = normalize_header(a)
        if key in lookup:
            return lookup[key]
    return None


def get_mapped_row(row: Mapping[str, str], headers: Sequence[str], aliases: Iterable[str]) -> Optional[str]:
    """Get cell value for the first resolved column among ``aliases``."""
    col = resolve_column(headers, aliases)
    if col is None:
        return None
    v = row.get(col)
    return None if v is None else str(v)
