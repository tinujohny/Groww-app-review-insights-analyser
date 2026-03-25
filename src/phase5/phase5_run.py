"""CLI: Phase 5 weekly note generation from Phase 4 output."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List, Optional

from phase4.jsonl_reviews import load_review_dicts
from phase5.compose import build_weekly_pulse


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Phase 5: generate weekly pulse <=250 words from Phase 4 themes/review map and "
            "Phase 2 sanitized review corpus."
        )
    )
    parser.add_argument("--phase4", type=Path, required=True, help="Path to Phase 4 JSON artifact")
    parser.add_argument("--phase2", type=Path, required=True, help="Path to Phase 2 JSONL (sanitized)")
    parser.add_argument(
        "--out",
        "-o",
        type=Path,
        default=None,
        help="Output JSON path (default: data/phase5/weekly_pulse_<timestamp>.json)",
    )
    args = parser.parse_args(argv)

    if not args.phase4.is_file():
        print(f"Error: missing phase4 file {args.phase4}", file=sys.stderr)
        return 2
    phase4_payload = json.loads(args.phase4.read_text(encoding="utf-8"))
    phase2_rows = load_review_dicts(args.phase2)

    out = build_weekly_pulse(phase4_payload, phase2_rows)
    if args.out is None:
        from datetime import datetime, timezone

        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        out_path = Path(f"data/phase5/weekly_pulse_{ts}.json")
    else:
        out_path = args.out
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {out_path.resolve()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
