"""CLI: Phase 6 email draft creation from Phase 5 weekly pulse."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from phase1.config import get_settings
from phase6.email_draft import (
    compose_body_html,
    compose_body_text,
    compose_subject,
    create_draft_with_settings,
    send_gmail_email_smtp,
)


def _default_out_path() -> Path:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return Path(f"data/phase6/email_draft_{ts}.json")


def _append_retry_job(retry_queue_path: Path, payload: Dict[str, Any]) -> None:
    retry_queue_path.parent.mkdir(parents=True, exist_ok=True)
    with retry_queue_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload) + "\n")


def _resolve_recipient(args_to: Optional[str], phase5_payload: Dict[str, Any], settings_default: Optional[str]) -> Optional[str]:
    from_payload = phase5_payload.get("recipientEmail")
    candidate = args_to or (str(from_payload).strip() if from_payload else None) or settings_default
    if not candidate:
        return None
    c = str(candidate).strip()
    if "@" not in c or "." not in c.split("@")[-1]:
        raise ValueError("Recipient email is invalid; pass --to-email user@example.com")
    return c


def _resolve_recipient_name(args_name: Optional[str], phase5_payload: Dict[str, Any]) -> Optional[str]:
    from_payload = phase5_payload.get("recipientName")
    candidate = args_name or (str(from_payload).strip() if from_payload else None)
    if not candidate:
        return None
    c = str(candidate).strip()
    return c or None


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Phase 6: build weekly email body and create mailbox draft. "
            "On failure, persist payload and enqueue retry metadata."
        )
    )
    parser.add_argument("--phase5", type=Path, required=True, help="Path to Phase 5 weekly pulse JSON")
    parser.add_argument("--to-email", type=str, default=None)
    parser.add_argument("--recipient-name", type=str, default=None)
    parser.add_argument("--out", "-o", type=Path, default=None, help="Output JSON path")
    parser.add_argument("--retry-queue", type=Path, default=Path("data/phase6/retry_queue.jsonl"))
    parser.add_argument("--send-now", action="store_true", help="Send immediately via provider (gmail supported)")
    args = parser.parse_args(argv)

    if not args.phase5.is_file():
        print(f"Error: missing phase5 file {args.phase5}", file=sys.stderr)
        return 2

    phase5_payload = json.loads(args.phase5.read_text(encoding="utf-8"))
    week = str(phase5_payload.get("week", "unknown-week"))
    recipient_name = _resolve_recipient_name(args.recipient_name, phase5_payload)
    if recipient_name:
        phase5_payload["recipientName"] = recipient_name

    subject = compose_subject(week)
    body_text = compose_body_text(phase5_payload)
    body_html = compose_body_html(body_text)

    get_settings.cache_clear()
    settings = get_settings()
    recipient_email = _resolve_recipient(args.to_email, phase5_payload, settings.email_draft_to)

    out_path = args.out or _default_out_path()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    base: Dict[str, Any] = {
        "week": week,
        "provider": settings.email_provider,
        "to_alias": recipient_email,
        "recipient_name": recipient_name,
        "subject": subject,
        "body_text": body_text,
        "body_html": body_html,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    try:
        if args.send_now:
            if settings.email_provider != "gmail":
                raise RuntimeError("--send-now currently supports only gmail provider")
            if not recipient_email:
                raise RuntimeError("--send-now requires recipient email")
            if not (settings.email_username and settings.email_password):
                raise RuntimeError("gmail send requires REVIEW_PULSE_EMAIL_USERNAME / REVIEW_PULSE_EMAIL_PASSWORD")
            send_id = send_gmail_email_smtp(
                username=settings.email_username,
                password=settings.email_password.get_secret_value(),
                to_email=recipient_email,
                subject=subject,
                body_text=body_text,
                body_html=body_html,
            )
            base.update({"status": "sent_provider", "send_provider_id": send_id, "retry_enqueued": False})
        else:
            res = create_draft_with_settings(
                settings,
                subject,
                body_text,
                body_html,
                local_store_dir=Path("data/phase6/provider_none_drafts"),
                recipient_email=recipient_email,
            )
            base.update({"status": res.status, "draft_provider_id": res.draft_provider_id, "retry_enqueued": False})
        out_path.write_text(json.dumps(base, indent=2) + "\n", encoding="utf-8")
        print(f"Wrote {out_path.resolve()}")
        return 0
    except Exception as exc:  # noqa: BLE001
        base.update({"status": "failed", "error": str(exc), "retry_enqueued": True})
        out_path.write_text(json.dumps(base, indent=2) + "\n", encoding="utf-8")
        _append_retry_job(
            args.retry_queue,
            {
                "queued_at": datetime.now(timezone.utc).isoformat(),
                "phase6_output_path": str(out_path),
                "week": week,
                "provider": settings.email_provider,
                "reason": str(exc),
            },
        )
        print(f"Wrote {out_path.resolve()} (failed; retry queued)", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
