"""Phase 2 CLI entrypoints: CSV ingest and remote collection."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from phase1.config import AppSettings
from phase1.schemas.enums import ReviewSource
from phase2.collectors.target_collect import (
    collect_app_store_until_target,
    collect_google_play_until_target,
    effective_target_count,
)
from phase2.ingestion import ingest_csv


def main_ingest(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Phase 2: ingest Google Play or App Store review CSV into NormalizedReview rows.",
    )
    parser.add_argument("csv_path", type=Path, help="Path to the exported CSV file")
    parser.add_argument("--source", required=True, choices=["google_play", "app_store"])
    parser.add_argument("--no-phase3", action="store_true", help="Skip language and emoji filters")
    parser.add_argument("--json-out", type=Path, default=None)
    parser.add_argument("--stats-out", type=Path, default=None)
    args = parser.parse_args(argv)

    source = ReviewSource.GOOGLE_PLAY if args.source == "google_play" else ReviewSource.APP_STORE
    reviews, stats = ingest_csv(args.csv_path, source, apply_phase3_filters=not args.no_phase3)

    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        with args.json_out.open("w", encoding="utf-8") as f:
            for r in reviews:
                f.write(json.dumps(r.model_dump(mode="json", by_alias=True), default=str) + "\n")
    if args.stats_out:
        args.stats_out.parent.mkdir(parents=True, exist_ok=True)
        args.stats_out.write_text(json.dumps(stats.to_dict(), indent=2) + "\n", encoding="utf-8")

    print(f"Emitted {stats.rows_emitted} reviews ({stats.rows_read} rows read).")
    if stats.rows_dropped_phase3:
        print(f"Dropped {stats.rows_dropped_phase3} in Phase 3 filters.")
    return 0


def _default_out_path(source: str) -> Path:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return Path(f"data/phase2/collected_{source}_{ts}.jsonl")


def main_collect(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Collect public reviews and save JSONL.")
    sub = parser.add_subparsers(dest="command", required=True)
    p_as = sub.add_parser("app_store")
    p_as.add_argument("--app-id", type=str)
    p_as.add_argument("--country", type=str, default="us")
    p_as.add_argument("--target", type=int, default=None)
    p_as.add_argument("--max-rss-pages", type=int, default=50)
    p_as.add_argument("--out", type=Path, default=None)
    p_as.add_argument("--no-phase3", action="store_true")
    p_gp = sub.add_parser("google_play")
    p_gp.add_argument("--package", type=str)
    p_gp.add_argument("--target", type=int, default=None)
    p_gp.add_argument("--lang", type=str, default="en")
    p_gp.add_argument("--country", type=str, default="us")
    p_gp.add_argument("--out", type=Path, default=None)
    p_gp.add_argument("--no-phase3", action="store_true")
    args = parser.parse_args(argv)

    settings = AppSettings()
    target = effective_target_count(settings, args.target)
    if args.command == "app_store":
        app_id = args.app_id or settings.app_store_app_id
        if not app_id:
            raise SystemExit("Error: provide --app-id or set REVIEW_PULSE_APP_STORE_APP_ID")
        normalized = collect_app_store_until_target(
            app_id, args.country, settings, target, apply_phase3=not args.no_phase3, max_rss_pages=args.max_rss_pages
        )
        label = "app_store"
    else:
        package = args.package or settings.google_play_package
        if not package:
            raise SystemExit("Error: provide --package or set REVIEW_PULSE_GOOGLE_PLAY_PACKAGE")
        normalized = collect_google_play_until_target(
            package, settings, target, apply_phase3=not args.no_phase3, lang=args.lang, country=args.country
        )
        label = "google_play"

    out_path = args.out or _default_out_path(label)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for r in normalized:
            f.write(json.dumps(r.model_dump(mode="json", by_alias=True), default=str) + "\n")
    print(f"Wrote {len(normalized)} reviews to {out_path.resolve()}")
    return 0
