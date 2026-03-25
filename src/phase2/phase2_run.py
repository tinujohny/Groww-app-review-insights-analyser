"""CLI: ingest a public review CSV and optionally write JSONL output + stats."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List, Optional

from phase1.schemas.enums import ReviewSource
from phase2.ingestion import ingest_csv


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Phase 2: ingest Google Play or App Store review CSV into NormalizedReview rows.",
    )
    parser.add_argument(
        "csv_path",
        type=Path,
        help="Path to the exported CSV file",
    )
    parser.add_argument(
        "--source",
        required=True,
        choices=["google_play", "app_store"],
        help="Which storefront format the file uses",
    )
    parser.add_argument(
        "--no-phase3",
        action="store_true",
        help="Skip language and emoji filters (only min-word + schema validation)",
    )
    parser.add_argument(
        "--json-out",
        type=Path,
        default=None,
        help="Write one JSON object per line (NormalizedReview as JSON)",
    )
    parser.add_argument(
        "--stats-out",
        type=Path,
        default=None,
        help="Write ingestion counters as JSON",
    )
    args = parser.parse_args(argv)

    source = ReviewSource.GOOGLE_PLAY if args.source == "google_play" else ReviewSource.APP_STORE
    reviews, stats = ingest_csv(
        args.csv_path,
        source,
        apply_phase3_filters=not args.no_phase3,
    )

    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        with args.json_out.open("w", encoding="utf-8") as f:
            for r in reviews:
                f.write(json.dumps(r.model_dump(mode="json", by_alias=True), default=str) + "\n")

    if args.stats_out:
        args.stats_out.parent.mkdir(parents=True, exist_ok=True)
        args.stats_out.write_text(
            json.dumps(stats.to_dict(), indent=2) + "\n",
            encoding="utf-8",
        )

    print(f"Emitted {stats.rows_emitted} reviews ({stats.rows_read} rows read).")
    if stats.rows_dropped_phase3:
        print(f"Dropped {stats.rows_dropped_phase3} in Phase 3 filters.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
