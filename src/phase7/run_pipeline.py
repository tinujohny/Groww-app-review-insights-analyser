"""Orchestrate the weekly pipeline for the Web UI / API."""

from __future__ import annotations

import json
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from phase1.config import AppSettings, get_settings
from phase6.fee_explanation import build_fee_explanation, parse_source_links
from phase4.jsonl_reviews import load_review_dicts
from phase4.phase4 import main as phase4_main
from phase5.compose import build_weekly_pulse
from phase5.phase5 import main as phase5_main
from phase6.email_draft import (
    compose_body_html,
    compose_body_text,
    compose_subject,
    create_draft_with_settings,
    send_gmail_email_smtp,
)


WEEK_KEYS = ("weekBucket", "week_bucket")
RID_KEYS = ("reviewIdInternal", "review_id_internal")


def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _resolve_week_bucket(row: Dict[str, Any]) -> Optional[str]:
    for k in WEEK_KEYS:
        v = row.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return None


def _resolve_review_id(row: Dict[str, Any]) -> Optional[str]:
    for k in RID_KEYS:
        v = row.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return None


def filter_phase2_rows_for_week(rows: List[Dict[str, Any]], week_bucket: str) -> List[Dict[str, Any]]:
    week_bucket = week_bucket.strip()
    return [r for r in rows if _resolve_week_bucket(r) == week_bucket]


def _latest_available_week(rows: List[Dict[str, Any]]) -> Optional[str]:
    weeks = sorted({w for r in rows if (w := _resolve_week_bucket(r))})
    if not weeks:
        return None
    return weeks[-1]


def _write_jsonl(path: Path, rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, default=str) + "\n")


@dataclass
class PipelineResult:
    run_id: str
    status: str
    error: Optional[str]
    phase4_out: Optional[str]
    phase5_out: Optional[str]
    phase6_out: Optional[str]
    report_out: Optional[str]
    combined_out: Optional[str]


class FileRunTracker:
    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir
        self._lock = threading.Lock()

    def _run_path(self, run_id: str) -> Path:
        return self.base_dir / "runs" / f"{run_id}.json"

    def create_run(self, *, week_bucket: str, trigger_type: str) -> str:
        run_id = str(uuid.uuid4())
        payload = {
            "runId": run_id,
            "weekBucket": week_bucket,
            "triggerType": trigger_type,
            "status": "running",
            "startedAt": _now_utc_iso(),
            "phaseStatus": {},
            "error": None,
        }
        self.set_run_payload(run_id, payload)
        return run_id

    def get_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        p = self._run_path(run_id)
        if not p.is_file():
            return None
        return json.loads(p.read_text(encoding="utf-8"))

    def set_run_payload(self, run_id: str, payload: Dict[str, Any]) -> None:
        with self._lock:
            p = self._run_path(run_id)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def run_weekly_pipeline(
    *,
    run_id: str,
    week_bucket: str,
    phase2_jsonl_path: Path,
    trigger_type: str,
    send_now: bool,
    recipient_email: Optional[str],
    recipient_name: Optional[str],
    max_reviews: int,
    max_chars: int,
    chunked: bool,
    output_dir: Path,
    tracker: FileRunTracker,
) -> PipelineResult:
    settings: AppSettings = get_settings()

    # Prepare paths
    run_dir = output_dir / "runs" / run_id
    phase4_out = run_dir / "phase4.json"
    phase5_out = run_dir / "phase5.json"
    phase6_out = run_dir / "phase6.json"
    report_out = output_dir / "reports" / f"weekly_{week_bucket}.json"
    combined_out = run_dir / "combined_payload.json"

    tracker_payload = tracker.get_run(run_id) or {}
    tracker_payload["phaseStatus"] = tracker_payload.get("phaseStatus") or {}

    try:
        # Phase 2: load and filter by week
        phase2_rows = load_review_dicts(phase2_jsonl_path)
        week_rows = filter_phase2_rows_for_week(phase2_rows, week_bucket)
        if not week_rows:
            latest_week = _latest_available_week(phase2_rows)
            if not latest_week:
                raise RuntimeError(
                    f"No Phase 2 reviews found for week {week_bucket} in {phase2_jsonl_path}"
                )
            week_rows = filter_phase2_rows_for_week(phase2_rows, latest_week)
            tracker_payload["phaseStatus"]["phase2_week_fallback"] = {
                "status": "fallback",
                "requested_week": week_bucket,
                "used_week": latest_week,
            }
            week_bucket = latest_week

        filtered_phase2_path = run_dir / "phase2_week.jsonl"
        _write_jsonl(filtered_phase2_path, week_rows)

        tracker_payload["phaseStatus"]["phase2"] = {"status": "ok", "rows": len(week_rows)}
        tracker.set_run_payload(run_id, tracker_payload)

        # Phase 4: themes + review_theme_map
        phase4_argv: List[str] = [
            "--input",
            str(filtered_phase2_path),
            "--out",
            str(phase4_out),
            "--max-reviews",
            str(max_reviews),
            "--max-chars",
            str(max_chars),
        ]
        if chunked:
            phase4_argv.append("--chunked")
        phase4_main(phase4_argv)

        tracker_payload["phaseStatus"]["phase4"] = {"status": "ok", "out": str(phase4_out)}
        tracker.set_run_payload(run_id, tracker_payload)

        phase4_payload = json.loads(phase4_out.read_text(encoding="utf-8"))

        # Phase 5: compose weekly pulse note
        phase5_payload = build_weekly_pulse(phase4_payload, week_rows)
        phase5_out.parent.mkdir(parents=True, exist_ok=True)
        phase5_out.write_text(json.dumps(phase5_payload, indent=2) + "\n", encoding="utf-8")

        tracker_payload["phaseStatus"]["phase5"] = {"status": "ok", "out": str(phase5_out)}
        tracker.set_run_payload(run_id, tracker_payload)

        # Phase 6: draft or send
        # Inject recipientName for personalized greeting
        phase5_payload_for_email = dict(phase5_payload)
        if recipient_name:
            phase5_payload_for_email["recipientName"] = recipient_name
        if settings.enable_fee_explanation:
            fee_payload = build_fee_explanation(
                scenario=settings.fee_scenario,
                source_links=parse_source_links(settings.fee_source_links),
            )
            phase5_payload_for_email.update(fee_payload)

        subject = compose_subject(week_bucket)
        body_text = compose_body_text(phase5_payload_for_email)
        body_html = compose_body_html(body_text)

        if send_now:
            if settings.email_provider != "gmail":
                raise RuntimeError("send_now is supported for gmail provider only in this MVP")
            if not recipient_email:
                raise RuntimeError("--to-email/recipient_email is required for send_now")
            if not (settings.email_username and settings.email_password):
                raise RuntimeError("gmail sending requires REVIEW_PULSE_EMAIL_USERNAME and REVIEW_PULSE_EMAIL_PASSWORD")

            send_id = send_gmail_email_smtp(
                username=settings.email_username,
                password=settings.email_password.get_secret_value(),
                to_email=recipient_email,
                subject=subject,
                body_text=body_text,
                body_html=body_html,
            )
            phase6_out.write_text(
                json.dumps(
                    {
                        "status": "sent_provider",
                        "provider": "gmail",
                        "send_provider_id": send_id,
                        "to_alias": recipient_email,
                        "recipient_name": recipient_name,
                        "subject": subject,
                        "created_at": _now_utc_iso(),
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
        else:
            res = create_draft_with_settings(
                settings,
                subject,
                body_text,
                body_html,
                local_store_dir=run_dir / "provider_none_drafts",
                recipient_email=recipient_email,
            )
            phase6_out.write_text(
                json.dumps(
                    {
                        "status": res.status,
                        "provider": res.provider,
                        "draft_provider_id": res.draft_provider_id,
                        "to_alias": res.to_alias,
                        "recipient_name": recipient_name,
                        "subject": subject,
                        "created_at": _now_utc_iso(),
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )

        tracker_payload["phaseStatus"]["phase6"] = {"status": "ok", "out": str(phase6_out)}

        combined_payload = {
            "date": datetime.now(timezone.utc).date().isoformat(),
            "weekly_pulse": {
                "themes": [t.get("name") for t in (phase5_payload.get("topThemes") or []) if isinstance(t, dict)],
                "quotes": [q.get("quote") for q in (phase5_payload.get("quotes") or []) if isinstance(q, dict)],
                "action_ideas": [a.get("idea") for a in (phase5_payload.get("actionIdeas") or []) if isinstance(a, dict)],
            },
            "fee_scenario": phase5_payload_for_email.get("fee_scenario") or settings.fee_scenario,
            "explanation_bullets": phase5_payload_for_email.get("explanation_bullets") or [],
            "source_links": phase5_payload_for_email.get("source_links") or [],
            "last_checked": phase5_payload_for_email.get("last_checked")
            or datetime.now(timezone.utc).date().isoformat(),
        }
        combined_out.parent.mkdir(parents=True, exist_ok=True)
        combined_out.write_text(json.dumps(combined_payload, indent=2) + "\n", encoding="utf-8")
        tracker_payload["phaseStatus"]["combined_json"] = {"status": "ok", "out": str(combined_out)}
        tracker_payload["status"] = "succeeded"
        tracker_payload["error"] = None
        tracker_payload["endedAt"] = _now_utc_iso()
        tracker.set_run_payload(run_id, tracker_payload)

        # Emit report (web UI consumes this)
        report_out.parent.mkdir(parents=True, exist_ok=True)
        report_out.write_text(
            json.dumps(
                {
                    "week": week_bucket,
                    "topThemes": phase5_payload.get("topThemes"),
                    "quotes": phase5_payload.get("quotes"),
                    "actionIdeas": phase5_payload.get("actionIdeas"),
                    "noteText": phase5_payload.get("noteText"),
                    "wordCount": phase5_payload.get("wordCount"),
                    "phase4": {"out": str(phase4_out)},
                    "phase6": {"out": str(phase6_out)},
                    "combinedJson": {"out": str(combined_out)},
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        return PipelineResult(
            run_id=run_id,
            status="succeeded",
            error=None,
            phase4_out=str(phase4_out),
            phase5_out=str(phase5_out),
            phase6_out=str(phase6_out),
            report_out=str(report_out),
            combined_out=str(combined_out),
        )

    except Exception as exc:  # noqa: BLE001
        tracker_payload["phaseStatus"]["phase_all"] = {"status": "failed", "reason": str(exc)}
        tracker_payload["status"] = "failed"
        tracker_payload["error"] = str(exc)
        tracker_payload["endedAt"] = _now_utc_iso()
        tracker.set_run_payload(run_id, tracker_payload)

        return PipelineResult(
            run_id=run_id,
            status="failed",
            error=str(exc),
            phase4_out=str(phase4_out),
            phase5_out=str(phase5_out),
            phase6_out=str(phase6_out),
            report_out=str(report_out),
            combined_out=str(combined_out),
        )

