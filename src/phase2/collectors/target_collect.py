"""Collect reviews until a target count, respecting ``max_reviews_per_export`` and Phase 3 filters."""

from __future__ import annotations

from typing import List, Optional

from google_play_scraper import Sort, reviews

from phase1.config import AppSettings
from phase1.schemas.enums import ReviewSource
from phase1.schemas.review import NormalizedReview
from phase2.collectors.app_store_rss import fetch_app_store_rss_url, next_rss_feed_url
from phase2.collectors.normalize_collected import collected_to_normalized
from phase3.pipeline import apply_phase3_text_filters


def effective_target_count(settings: AppSettings, requested: Optional[int]) -> int:
    """Cannot exceed ``max_reviews_per_export`` (architecture / operator cap)."""
    cap = settings.max_reviews_per_export
    want = requested if requested is not None else cap
    return max(1, min(int(want), cap))


def collect_app_store_until_target(
    app_id: str,
    country: str,
    settings: AppSettings,
    target: int,
    *,
    apply_phase3: bool,
    max_rss_pages: int = 50,
) -> List[NormalizedReview]:
    """
    Follow RSS ``next`` links until we have ``target`` reviews after normalization
    (and optional Phase 3), or pages run out.
    """
    results: List[NormalizedReview] = []
    seen_external: set[str] = set()
    cc = country.strip().lower()
    url: Optional[str] = (
        f"https://itunes.apple.com/{cc}/rss/customerreviews/id={app_id}/sortby=mostrecent/xml"
    )
    seen_urls: set[str] = set()
    pages = 0

    while len(results) < target and url and pages < max_rss_pages:
        if url in seen_urls:
            break
        seen_urls.add(url)
        root, rows = fetch_app_store_rss_url(url)
        pages += 1
        fresh: List[dict] = []
        for row in rows:
            rid = (row.get("external_review_id") or "").strip()
            key = rid or f"{row.get('date_raw')}|{row.get('text', '')[:80]}"
            if key in seen_external:
                continue
            seen_external.add(key)
            fresh.append(row)

        norm = collected_to_normalized(fresh, ReviewSource.APP_STORE, settings=settings)
        if apply_phase3:
            norm = apply_phase3_text_filters(norm, settings)
        results.extend(norm)

        url = next_rss_feed_url(root)

    return results[:target]


def collect_google_play_until_target(
    package_name: str,
    settings: AppSettings,
    target: int,
    *,
    apply_phase3: bool,
    lang: str = "en",
    country: str = "us",
    max_batches: int = 100,
) -> List[NormalizedReview]:
    """Paginate Play Store reviews until ``target`` normalized rows (after filters) or no more data."""
    results: List[NormalizedReview] = []
    seen_ids: set[str] = set()
    continuation = None
    batches = 0

    while len(results) < target and batches < max_batches:
        batch, continuation = reviews(
            package_name,
            lang=lang,
            country=country,
            sort=Sort.NEWEST,
            count=200,
            continuation_token=continuation,
        )
        batches += 1
        if not batch:
            break

        fresh: List[dict] = []
        for row in batch:
            rid = str(row.get("reviewId") or "")
            if rid and rid in seen_ids:
                continue
            if rid:
                seen_ids.add(rid)
            score = row.get("score")
            try:
                rating = int(round(float(score))) if score is not None else 0
            except (TypeError, ValueError):
                rating = 0
            fresh.append(
                {
                    "source_format": "google_play_scraper",
                    "external_review_id": rid,
                    "rating": rating,
                    "text": (row.get("content") or "").strip(),
                    "at": row.get("at"),
                }
            )

        norm = collected_to_normalized(fresh, ReviewSource.GOOGLE_PLAY, settings=settings)
        if apply_phase3:
            norm = apply_phase3_text_filters(norm, settings)
        results.extend(norm)

        if continuation is None:
            break

    return results[:target]
