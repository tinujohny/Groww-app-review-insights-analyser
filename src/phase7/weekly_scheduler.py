"""Scheduler for weekly pulses.

This is used to generate weekly pulse outputs (Phase 4 -> Phase 5 -> Phase 6).
It supports local testing schedules (e.g. every 5 minutes) and logs to a separate file.
"""

from __future__ import annotations

import argparse
import logging
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

import json

from phase1.config import get_settings
from phase2.collectors.target_collect import collect_app_store_until_target, collect_google_play_until_target
from phase4.jsonl_reviews import load_review_dicts
from phase7.run_pipeline import FileRunTracker, filter_phase2_rows_for_week, run_weekly_pipeline
from phase7.weekly_run_cli import week_bucket_from_day


def _local_now_date() -> datetime.date:
    return datetime.now().date()


def _today_weekday_abbrev() -> str:
    # CronTrigger expects values like "mon|tue|...|sun"
    # datetime.isocalendar().weekday is 1=Mon ... 7=Sun
    iso = datetime.now().isocalendar()
    days = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
    return days[int(iso.weekday) - 1]


def _monday_of_iso_week(d: datetime.date) -> datetime.date:
    iso = d.isocalendar()
    return datetime.fromisocalendar(iso.year, iso.week, 1).date()


def week_buckets_last_n_weeks(*, end_date: datetime.date, weeks: int) -> List[str]:
    """Return ISO week buckets for `weeks` ending at the ISO week containing `end_date`."""
    if weeks <= 0:
        return []
    end_monday = _monday_of_iso_week(end_date)
    start_monday = end_monday - timedelta(weeks=weeks - 1)
    out: List[str] = []
    for i in range(weeks):
        d = start_monday + timedelta(weeks=i)
        out.append(week_bucket_from_day(d))
    return out


def _default_phase2_jsonl_path() -> Path:
    p = Path("data/phase2")
    candidates = sorted(p.glob("collected_*.jsonl"), key=lambda x: x.stat().st_mtime, reverse=True)
    if not candidates:
        raise FileNotFoundError("No Phase 2 JSONL found under data/phase2/collected_*.jsonl")
    return candidates[0]


def _collect_phase2_for_scheduler(
    *,
    out_dir: Path,
    max_reviews_total: int,
) -> Path:
    """Collect a combined Phase 2 JSONL (best-effort) capped by `max_reviews_total`."""
    settings = get_settings()

    sources: List[str] = []
    if settings.app_store_app_id:
        sources.append("app_store")
    if settings.google_play_package:
        sources.append("google_play")

    if not sources:
        return _default_phase2_jsonl_path()

    ts = datetime.now().strftime("%Y%m%dT%H%M%SZ")
    out_path = out_dir / "phase2_collect" / f"combined_{ts}.jsonl"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    per_source = max(1, max_reviews_total // len(sources))
    remainder = max_reviews_total - (per_source * len(sources))

    all_normalized: List[dict] = []

    if "app_store" in sources:
        target = per_source + (1 if remainder > 0 else 0)
        remainder -= 1
        normalized = collect_app_store_until_target(
            settings.app_store_app_id,
            "us",
            settings,
            target,
            apply_phase3=True,
        )
        all_normalized.extend([r.model_dump(mode="json", by_alias=True) for r in normalized])

    if "google_play" in sources:
        target = per_source + (1 if remainder > 0 else 0)
        remainder -= 1
        normalized = collect_google_play_until_target(
            settings.google_play_package,
            settings,
            target,
            apply_phase3=True,
            lang="en",
            country="us",
        )
        all_normalized.extend([r.model_dump(mode="json", by_alias=True) for r in normalized])

    with out_path.open("w", encoding="utf-8") as f:
        for row in all_normalized:
            f.write(json.dumps(row, default=str) + "\n")

    return out_path


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Scheduler to generate weekly pulse(s) via CLI pipeline.",
    )
    parser.add_argument(
        "--mode",
        type=str,
        default="interval",
        choices=["interval", "weekly"],
        help="interval=every 5 minutes (local debug), weekly=once per week at 15:35 Monday",
    )
    parser.add_argument("--day-of-week", type=str, default="*", help="cron day_of_week: mon|tue|...|sun|*")
    parser.add_argument("--hour", type=int, default=15, help="Hour in local time (default 15)")
    # Scheduling controls:
    # - Weekly mode: set --minute (default 35)
    # - Local interval mode: set --minute-start and --minute-step (e.g. 40 and 5 => 15:40,15:45,...)
    parser.add_argument("--minute", type=int, default=35, help="Minute in local time for weekly mode (default 35)")
    parser.add_argument("--minute-start", type=int, default=40, help="Minute start for interval mode (default 40)")
    parser.add_argument("--minute-step", type=int, default=5, help="Minute step for interval mode (default 5)")
    parser.add_argument("--log-file", type=str, default="data/phase7/scheduler.log", help="Scheduler log file path")
    parser.add_argument(
        "--recipient-email",
        type=str,
        default="johnytinu18@gmail.com",
        help="Fixed receipt email for scheduler",
    )
    parser.add_argument("--recipient-name", type=str, default="tinu", help="Greeting name for recipient")
    parser.add_argument("--send-now", action="store_true", default=False, help="Send email now (gmail only in MVP)")
    parser.add_argument("--chunked", action="store_true", help="Use chunked theme extraction")
    parser.add_argument("--max-reviews", type=int, default=1000, help="Max total reviews to download")
    parser.add_argument(
        "--weeks-back",
        type=int,
        default=12,
        help="Generate pulse for last N weeks (stakeholder window is often 8–12; default 12)",
    )
    parser.add_argument("--max-chars", type=int, default=80_000)
    parser.add_argument("--output-dir", type=str, default="data/phase7", help="Output dir (runs/phase artifacts)")
    parser.add_argument("--run-once", action="store_true", help="Run one weekly pulse immediately and exit")
    args = parser.parse_args(argv)

    logger = logging.getLogger("review_pulse_scheduler")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    log_path = Path(args.log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    fh = logging.FileHandler(log_path, encoding="utf-8")
    fh.setLevel(logging.INFO)
    fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logger.addHandler(fh)

    if args.run_once:
        _job(
            recipient_email=args.recipient_email,
            recipient_name=args.recipient_name,
            send_now=args.send_now,
            chunked=args.chunked,
            max_reviews=args.max_reviews,
            max_chars=args.max_chars,
            output_dir=args.output_dir,
            weeks_back=args.weeks_back,
            log_file=args.log_file,
        )
        return 0

    day_of_week = args.day_of_week
    if args.mode == "weekly" and day_of_week in ("*", "any", "all"):
        day_of_week = "mon"
    if args.mode == "interval" and day_of_week in ("*", "any", "all"):
        day_of_week = _today_weekday_abbrev()

    scheduler = BackgroundScheduler()
    # Build cron minute expression.
    if args.mode == "interval":
        minute_expr: str | int = f"{args.minute_start}-59/{args.minute_step}"
    else:
        minute_expr = int(args.minute)

    scheduler.add_job(
        func=_job,
        trigger=CronTrigger(day_of_week=day_of_week, hour=args.hour, minute=minute_expr),
        kwargs={
            "recipient_email": args.recipient_email,
            "recipient_name": args.recipient_name,
            "send_now": args.send_now,
            "chunked": args.chunked,
            "max_reviews": args.max_reviews,
            "max_chars": args.max_chars,
            "output_dir": args.output_dir,
            "weeks_back": args.weeks_back,
            "log_file": args.log_file,
        },
        id="weekly_pulse_job",
        replace_existing=True,
        misfire_grace_time=60 * 10,
        coalesce=True,
        max_instances=1,
    )

    scheduler.start()
    logging.getLogger("review_pulse_scheduler").info(
        "Scheduler started: day=%s hour=%02d minute=%s local time",
        args.day_of_week,
        args.hour,
        str(minute_expr),
    )
    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        scheduler.shutdown()
    return 0


def _job(
    *,
    recipient_email: str,
    recipient_name: str,
    send_now: bool,
    chunked: bool,
    max_reviews: int,
    max_chars: int,
    output_dir: str,
    weeks_back: int,
    log_file: str,
) -> None:
    logger = logging.getLogger("review_pulse_scheduler")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(log_path, encoding="utf-8")
        fh.setLevel(logging.INFO)
        fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
        logger.addHandler(fh)

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    tracker = FileRunTracker(out_dir)

    # Collect once, then generate weekly pulses for the last N weeks.
    logger.info("Scheduler tick: collecting up to %s reviews (weeks_back=%s)", max_reviews, weeks_back)
    phase2_path = _collect_phase2_for_scheduler(out_dir=out_dir, max_reviews_total=max_reviews)
    buckets = week_buckets_last_n_weeks(end_date=_local_now_date(), weeks=weeks_back)

    for bucket in buckets:
        report_out = out_dir / "reports" / f"weekly_{bucket}.json"
        if report_out.is_file():
            logger.info("Skipping %s: report already exists (%s)", bucket, report_out)
            continue

        run_id = tracker.create_run(week_bucket=bucket, trigger_type="scheduler")
        logger.info("Running pipeline for week=%s (run_id=%s)", bucket, run_id)
        result = run_weekly_pipeline(
            run_id=run_id,
            week_bucket=bucket,
            phase2_jsonl_path=phase2_path,
            trigger_type="scheduler",
            send_now=send_now,
            recipient_email=recipient_email,
            recipient_name=recipient_name,
            max_reviews=max_reviews,
            max_chars=max_chars,
            chunked=chunked,
            output_dir=out_dir,
            tracker=tracker,
        )
        if result.status != "succeeded":
            logger.error("Weekly pulse failed for %s (run_id=%s): %s", bucket, run_id, result.error)
        else:
            logger.info("Weekly pulse succeeded for %s (run_id=%s)", bucket, run_id)

