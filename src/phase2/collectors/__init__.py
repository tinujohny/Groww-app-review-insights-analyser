"""Fetch reviews from public App Store RSS and Google Play (unofficial scraper)."""

from phase2.collectors.app_store_rss import fetch_app_store_rss_pages
from phase2.collectors.google_play_scrape import fetch_google_play_reviews
from phase2.collectors.normalize_collected import collected_to_normalized
from phase2.collectors.target_collect import (
    collect_app_store_until_target,
    collect_google_play_until_target,
    effective_target_count,
)

__all__ = [
    "collect_app_store_until_target",
    "collect_google_play_until_target",
    "collected_to_normalized",
    "effective_target_count",
    "fetch_app_store_rss_pages",
    "fetch_google_play_reviews",
]
