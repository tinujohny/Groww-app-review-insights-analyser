"""Fetch reviews from Google Play using the ``google-play-scraper`` library (public store pages)."""

from __future__ import annotations

from typing import Any, Dict, List

from google_play_scraper import Sort, reviews


def fetch_google_play_reviews(
    package_name: str,
    *,
    max_reviews: int = 200,
    lang: str = "en",
    country: str = "us",
) -> List[Dict[str, Any]]:
    """
    Return raw review dicts from Play Store (``content``, ``score``, ``at``, ``reviewId``, …).

    Uses an unofficial scraper; Google may rate-limit or change HTML layout.
    """
    collected: List[Dict[str, Any]] = []
    continuation = None
    remaining = max_reviews

    while remaining > 0:
        batch_size = min(200, remaining)
        batch, continuation = reviews(
            package_name,
            lang=lang,
            country=country,
            sort=Sort.NEWEST,
            count=batch_size,
            continuation_token=continuation,
        )
        if not batch:
            break
        for row in batch:
            collected.append(
                {
                    "source_format": "google_play_scraper",
                    "external_review_id": str(row.get("reviewId") or ""),
                    "rating": int(row.get("score") or 0),
                    "text": (row.get("content") or "").strip(),
                    "at": row.get("at"),
                }
            )
        remaining -= len(batch)
        if continuation is None:
            break

    return collected[:max_reviews]
