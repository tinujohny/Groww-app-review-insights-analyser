"""CSV ingestion → ``NormalizedReview`` list (Phase 2)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Union

from pydantic import ValidationError

from phase1.config import AppSettings, get_settings
from phase1.schemas.enums import ReviewSource
from phase1.schemas.review import NormalizedReview
from phase1.text_utils import count_words
from phase2.app_store import read_app_store_rows
from phase2.date_utils import date_to_iso_week_bucket, parse_review_date
from phase2.google_play import read_google_play_rows
from phase2.parsing import parse_body_text, parse_star_rating
from phase3.pipeline import apply_phase3_text_filters


@dataclass
class IngestionStats:
    """Counts for one CSV import run."""

    rows_read: int = 0
    rows_skipped_no_rating: int = 0
    rows_skipped_bad_date: int = 0
    rows_skipped_validation: int = 0
    rows_normalized: int = 0
    rows_dropped_phase3: int = 0
    rows_emitted: int = 0

    def to_dict(self) -> Dict[str, int]:
        return {
            "rows_read": self.rows_read,
            "rows_skipped_no_rating": self.rows_skipped_no_rating,
            "rows_skipped_bad_date": self.rows_skipped_bad_date,
            "rows_skipped_validation": self.rows_skipped_validation,
            "rows_normalized": self.rows_normalized,
            "rows_dropped_phase3": self.rows_dropped_phase3,
            "rows_emitted": self.rows_emitted,
        }


def _row_iterator(source: ReviewSource, path: Path) -> Iterator[Dict[str, Any]]:
    if source == ReviewSource.GOOGLE_PLAY:
        yield from read_google_play_rows(path)
    elif source == ReviewSource.APP_STORE:
        yield from read_app_store_rows(path)
    else:
        raise ValueError(f"Unsupported source: {source}")


def ingest_csv(
    path: Union[Path, str],
    source: ReviewSource,
    *,
    settings: Optional[AppSettings] = None,
    apply_phase3_filters: bool = True,
) -> tuple[list[NormalizedReview], IngestionStats]:
    """
    Parse a public export CSV and return normalized reviews.

    Rows are skipped if rating/date is invalid or if ``NormalizedReview`` validation fails
    (e.g. below minimum word count). When ``apply_phase3_filters`` is True, language and
    emoji filters from ``settings`` are applied.
    """
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(str(p))

    cfg = settings or get_settings()
    stats = IngestionStats()
    out: List[NormalizedReview] = []

    for raw in _row_iterator(source, p):
        stats.rows_read += 1
        rating = parse_star_rating(raw.get("rating_raw"))
        text = parse_body_text(raw.get("text_raw"))
        date_raw = raw.get("date_raw")

        if rating is None:
            stats.rows_skipped_no_rating += 1
            continue

        if not date_raw or not str(date_raw).strip():
            stats.rows_skipped_bad_date += 1
            continue

        try:
            review_date = parse_review_date(str(date_raw))
        except (ValueError, TypeError, OverflowError):
            stats.rows_skipped_bad_date += 1
            continue

        # Early skip for short text (avoids ValidationError noise)
        if count_words(text) < cfg.min_review_words:
            stats.rows_skipped_validation += 1
            continue

        week_bucket = date_to_iso_week_bucket(review_date)

        try:
            review = NormalizedReview(
                source=source,
                rating=rating,
                text=text,
                review_date=review_date,
                week_bucket=week_bucket,
            )
        except ValidationError:
            stats.rows_skipped_validation += 1
            continue

        out.append(review)
        stats.rows_normalized += 1

    if apply_phase3_filters:
        before = len(out)
        out = apply_phase3_text_filters(out, cfg)
        stats.rows_dropped_phase3 = before - len(out)
    stats.rows_emitted = len(out)

    return out, stats


class CsvIngestionService:
    """Implements :class:`review_pulse.contracts.IngestionPort` for local CSV files."""

    def import_from_export(self, source: ReviewSource, path: str) -> list[NormalizedReview]:
        reviews, _stats = ingest_csv(path, source, apply_phase3_filters=True)
        return reviews
