"""CLI: collect reviews from App Store RSS or Google Play into JSONL under data/phase2/."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from phase1.config import AppSettings, get_settings
from phase2.collectors.target_collect import (
    collect_app_store_until_target,
    collect_google_play_until_target,
    effective_target_count,
)


def _default_out_path(source: str) -> Path:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return Path(f"data/phase2/collected_{source}_{ts}.jsonl")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Collect public reviews (App Store RSS or Google Play scraper) and save JSONL. "
            "Respects REVIEW_PULSE_MAX_REVIEWS_PER_EXPORT as the ceiling; default target matches it. "
            "Applies min word count, then optional Phase 3 language + emoji filters."
        ),
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_as = sub.add_parser("app_store", help="Apple App Store (public RSS)")
    p_as.add_argument("--app-id", type=str, help="Numeric app id (or set REVIEW_PULSE_APP_STORE_APP_ID)")
    p_as.add_argument("--country", type=str, default="us", help="Storefront country code, e.g. us, gb, in")
    p_as.add_argument(
        "--target",
        type=int,
        default=None,
        help="Reviews to keep after all filters (capped by REVIEW_PULSE_MAX_REVIEWS_PER_EXPORT; default: that setting)",
    )
    p_as.add_argument(
        "--max-rss-pages",
        type=int,
        default=50,
        help="Safety cap on RSS pages to follow (Apple often allows ~10)",
    )
    p_as.add_argument("--out", type=Path, default=None, help="Output JSONL path")
    p_as.add_argument("--no-phase3", action="store_true", help="Skip language/emoji filters")

    p_gp = sub.add_parser("google_play", help="Google Play (unofficial scraper)")
    p_gp.add_argument("--package", type=str, help="Application id (or REVIEW_PULSE_GOOGLE_PLAY_PACKAGE)")
    p_gp.add_argument(
        "--target",
        type=int,
        default=None,
        help="Reviews to keep after all filters (capped by max export setting; default: that setting)",
    )
    p_gp.add_argument("--lang", type=str, default="en")
    p_gp.add_argument("--country", type=str, default="us")
    p_gp.add_argument("--out", type=Path, default=None)
    p_gp.add_argument("--no-phase3", action="store_true")

    args = parser.parse_args(argv)
    get_settings.cache_clear()
    settings = AppSettings()
    target = effective_target_count(settings, args.target)

    if args.command == "app_store":
        app_id = args.app_id or settings.app_store_app_id
        if not app_id:
            print("Error: provide --app-id or set REVIEW_PULSE_APP_STORE_APP_ID", file=sys.stderr)
            return 2
        normalized = collect_app_store_until_target(
            app_id,
            args.country,
            settings,
            target,
            apply_phase3=not args.no_phase3,
            max_rss_pages=args.max_rss_pages,
        )
        label = "app_store"
    else:
        package = args.package or settings.google_play_package
        if not package:
            print("Error: provide --package or set REVIEW_PULSE_GOOGLE_PLAY_PACKAGE", file=sys.stderr)
            return 2
        normalized = collect_google_play_until_target(
            package,
            settings,
            target,
            apply_phase3=not args.no_phase3,
            lang=args.lang,
            country=args.country,
        )
        label = "google_play"

    out_path = args.out or _default_out_path(label)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for r in normalized:
            f.write(json.dumps(r.model_dump(mode="json", by_alias=True), default=str) + "\n")

    print(
        f"Wrote {len(normalized)} reviews (target was {target}, "
        f"max_reviews_per_export={settings.max_reviews_per_export}) to {out_path.resolve()}",
    )
    if len(normalized) < target:
        print(
            "Warning: fewer reviews than target — RSS may have ended, Play Store exhausted, "
            "or filters (language/emoji/min words) removed many rows.",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
