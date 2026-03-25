"""CLI + helper: run the full weekly pipeline for one ISO week bucket."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from phase1.config import get_settings
from phase2.collectors.target_collect import collect_app_store_until_target, collect_google_play_until_target
from phase7.run_pipeline import FileRunTracker, run_weekly_pipeline


def week_bucket_from_day(d: date) -> str:
    y, w, _ = d.isocalendar()
    return f"{y}-W{w:02d}"


def default_week_bucket() -> str:
    return week_bucket_from_day(date.today())


def _default_phase2_jsonl_path() -> Path:
    p = Path("data/phase2")
    candidates = sorted(p.glob("collected_*.jsonl"), key=lambda x: x.stat().st_mtime, reverse=True)
    if not candidates:
        raise FileNotFoundError("No Phase 2 JSONL found under data/phase2/collected_*.jsonl")
    return candidates[0]


def _combine_phase2_jsonl_files(files: List[Path], out_path: Path) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f_out:
        for fp in files:
            with fp.open("r", encoding="utf-8") as f_in:
                for line in f_in:
                    if line.strip():
                        f_out.write(line)
    return out_path


def run_weekly_once(
    *,
    week_bucket: str,
    phase2_jsonl: Optional[Path],
    recipient_email: str,
    recipient_name: Optional[str],
    send_now: bool,
    chunked: bool,
    max_reviews: int,
    max_chars: int,
    output_dir: Path,
    trigger_type: str = "scheduler",
) -> bool:
    """Run one full weekly pulse. Returns True on success."""
    output_dir.mkdir(parents=True, exist_ok=True)
    tracker = FileRunTracker(output_dir)
    run_id = tracker.create_run(week_bucket=week_bucket, trigger_type=trigger_type)

    # Phase 2 input: either provided file or best-effort remote collection.
    if phase2_jsonl:
        phase2_path = phase2_jsonl
    else:
        settings = get_settings()
        phase2_files: List[Path] = []
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        tmp_dir = output_dir / "phase2_collect"

        if settings.app_store_app_id:
            out = tmp_dir / f"app_store_{ts}.jsonl"
            normalized = collect_app_store_until_target(
                settings.app_store_app_id,
                "us",
                settings,
                max_reviews,
                apply_phase3=True,
            )
            out.parent.mkdir(parents=True, exist_ok=True)
            with out.open("w", encoding="utf-8") as f:
                for r in normalized:
                    f.write(json.dumps(r.model_dump(mode="json", by_alias=True), default=str) + "\n")
            phase2_files.append(out)

        if settings.google_play_package:
            out = tmp_dir / f"google_play_{ts}.jsonl"
            normalized = collect_google_play_until_target(
                settings.google_play_package,
                settings,
                max_reviews,
                apply_phase3=True,
            )
            out.parent.mkdir(parents=True, exist_ok=True)
            with out.open("w", encoding="utf-8") as f:
                for r in normalized:
                    f.write(json.dumps(r.model_dump(mode="json", by_alias=True), default=str) + "\n")
            phase2_files.append(out)

        if phase2_files:
            phase2_path = tmp_dir / f"combined_{ts}.jsonl"
            _combine_phase2_jsonl_files(phase2_files, phase2_path)
        else:
            phase2_path = _default_phase2_jsonl_path()

    result = run_weekly_pipeline(
        run_id=run_id,
        week_bucket=week_bucket,
        phase2_jsonl_path=phase2_path,
        trigger_type=trigger_type,
        send_now=send_now,
        recipient_email=recipient_email,
        recipient_name=recipient_name,
        max_reviews=max_reviews,
        max_chars=max_chars,
        chunked=chunked,
        output_dir=output_dir,
        tracker=tracker,
    )
    return result.status == "succeeded"


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Run weekly pulse for one ISO week bucket.")
    parser.add_argument("--week-bucket", type=str, default=None, help="e.g. 2026-W11 (default: current local week)")
    parser.add_argument(
        "--phase2-jsonl",
        type=Path,
        default=None,
        help="Path to Phase 2 JSONL. If omitted, scheduler uses a collection step when possible, else newest collected_*.jsonl.",
    )
    parser.add_argument(
        "--recipient-email",
        type=str,
        default="johnytinu18@gmail.com",
        help="Fixed receipt email for scheduler (default matches your request).",
    )
    parser.add_argument("--recipient-name", type=str, default="tinu", help="Used for greeting: Hi <name>,")
    parser.add_argument("--send-now", action="store_true", help="Send email immediately (gmail only in this MVP).")
    parser.add_argument("--chunked", action="store_true", help="Use chunked theme extraction (cost controls)")
    parser.add_argument("--max-reviews", type=int, default=500)
    parser.add_argument("--max-chars", type=int, default=80_000)
    parser.add_argument("--output-dir", type=Path, default=Path("data/phase7"))
    args = parser.parse_args(argv)

    get_settings.cache_clear()
    if not args.week_bucket:
        args.week_bucket = default_week_bucket()
    ok = run_weekly_once(
        week_bucket=args.week_bucket,
        phase2_jsonl=args.phase2_jsonl,
        recipient_email=args.recipient_email,
        recipient_name=args.recipient_name,
        send_now=args.send_now,
        chunked=args.chunked,
        max_reviews=args.max_reviews,
        max_chars=args.max_chars,
        output_dir=args.output_dir,
        trigger_type="cli",
    )
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

