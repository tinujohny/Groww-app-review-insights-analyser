"""Turn collected raw dicts into :class:`phase1.schemas.review.NormalizedReview`."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Optional

from dateutil import parser as date_parser
from pydantic import ValidationError

from phase1.config import AppSettings, get_settings
from phase1.schemas.enums import ReviewSource
from phase1.schemas.review import NormalizedReview
from phase1.text_utils import count_words
from phase2.date_utils import date_to_iso_week_bucket


def _to_date(value: Any) -> Optional[date]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    s = str(value).strip()
    if not s:
        return None
    try:
        return date_parser.parse(s).date()
    except (ValueError, TypeError, OverflowError):
        return None


def collected_to_normalized(
    rows: List[Dict[str, Any]],
    source: ReviewSource,
    *,
    settings: Optional[AppSettings] = None,
) -> List[NormalizedReview]:
    """Build validated normalized reviews; skips rows that fail word count or schema."""
    cfg = settings or get_settings()
    out: List[NormalizedReview] = []
    for row in rows:
        rating = row.get("rating")
        text = (row.get("text") or "").strip()
        if rating is None or not isinstance(rating, int) or not (1 <= rating <= 5):
            continue
        if count_words(text) < cfg.min_review_words:
            continue
        rd = _to_date(row.get("at") or row.get("date_raw"))
        if rd is None:
            continue
        week = date_to_iso_week_bucket(rd)
        try:
            out.append(
                NormalizedReview(
                    source=source,
                    rating=rating,
                    text=text,
                    review_date=rd,
                    week_bucket=week,
                )
            )
        except ValidationError:
            continue
    return out
