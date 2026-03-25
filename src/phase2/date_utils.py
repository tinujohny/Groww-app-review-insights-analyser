"""Parse export date strings and compute ISO week buckets."""

from __future__ import annotations

from datetime import date, datetime

from dateutil import parser as date_parser


def parse_review_date(value: str) -> date:
    """Parse a storefront export date/time string to a calendar date."""
    if value is None or not str(value).strip():
        raise ValueError("empty date")
    dt = date_parser.parse(str(value).strip(), dayfirst=False)
    return dt.date()


def date_to_iso_week_bucket(d: date) -> str:
    """Return ISO week label ``YYYY-Www`` (e.g. ``2026-W11``)."""
    y, w, _ = d.isocalendar()
    return f"{y}-W{w:02d}"
