"""Phase 6 email draft service implementations."""

from __future__ import annotations

import json
import imaplib
import smtplib
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path
from typing import Optional
from uuid import uuid4

from phase1.config import AppSettings
from review_pulse.contracts import EmailDraftPort


@dataclass
class DraftResult:
    provider: str
    status: str
    draft_provider_id: Optional[str]
    to_alias: Optional[str]


class LocalEmailDraftService(EmailDraftPort):
    """Local file-backed draft creator used for provider=`none` and test/dev flows."""

    def __init__(self, out_dir: Path) -> None:
        self.out_dir = out_dir

    def create_draft(self, subject: str, body_text: str, body_html: Optional[str]) -> str:
        self.out_dir.mkdir(parents=True, exist_ok=True)
        did = f"local-{uuid4()}"
        p = self.out_dir / f"{did}.json"
        p.write_text(
            json.dumps(
                {
                    "draft_provider_id": did,
                    "subject": subject,
                    "body_text": body_text,
                    "body_html": body_html,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        return did


def compose_subject(week_bucket: str) -> str:
    return f"Groww Weekly Review Pulse - {week_bucket}"


def compose_body_text(phase5_payload: dict) -> str:
    week = phase5_payload.get("week", "unknown-week")
    recipient_name = str(phase5_payload.get("recipientName") or "").strip()
    note = str(phase5_payload.get("noteText", "")).strip()
    top = phase5_payload.get("topThemes") or []
    n_reviews = sum(int(t.get("reviewCount", 0)) for t in top if isinstance(t, dict))
    footer = (
        "\n\n---\n"
        f"Metadata\n"
        f"week_range: {week}\n"
        f"review_count: {n_reviews}\n"
        f"generated_at_utc: {datetime.now(timezone.utc).isoformat()}\n"
    )
    greeting = f"Hi {recipient_name}," if recipient_name else "Hi,"
    return f"{greeting}\n\n{note}{footer}".strip()


def compose_body_html(body_text: str) -> str:
    escaped = (
        body_text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("\n", "<br/>\n")
    )
    return f"<html><body><p>{escaped}</p></body></html>"


def _create_gmail_draft_imap(
    *,
    username: str,
    password: str,
    to_email: str,
    subject: str,
    body_text: str,
    body_html: Optional[str],
) -> str:
    """Create a Gmail draft via IMAP APPEND to the Drafts mailbox."""
    msg = EmailMessage()
    msg["From"] = username
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content(body_text)
    if body_html:
        msg.add_alternative(body_html, subtype="html")

    # Gmail IMAP over SSL. App password is expected for auth.
    m = imaplib.IMAP4_SSL("imap.gmail.com", 993)
    try:
        m.login(username, password)
        # Try standard Gmail drafts mailbox first; fallback to generic Drafts.
        mailbox = "[Gmail]/Drafts"
        typ, data = m.append(mailbox, "\\Draft", imaplib.Time2Internaldate(time.time()), msg.as_bytes())
        if typ != "OK":
            typ2, data2 = m.append("Drafts", "\\Draft", imaplib.Time2Internaldate(time.time()), msg.as_bytes())
            if typ2 != "OK":
                raise RuntimeError(f"IMAP append failed for Gmail drafts: {data2 or data}")
            data = data2
        # Return provider draft token if server response includes it.
        token = ""
        if data and isinstance(data[0], bytes):
            token = data[0].decode(errors="ignore").strip()
        return token or f"gmail-imap-{uuid4()}"
    finally:
        try:
            m.logout()
        except Exception:
            pass


def send_gmail_email_smtp(
    *,
    username: str,
    password: str,
    to_email: str,
    subject: str,
    body_text: str,
    body_html: Optional[str],
) -> str:
    """Send email via Gmail SMTP and return a local send token."""
    msg = EmailMessage()
    msg["From"] = username
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content(body_text)
    if body_html:
        msg.add_alternative(body_html, subtype="html")

    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=60) as s:
        s.login(username, password)
        s.send_message(msg)
    return f"gmail-smtp-{uuid4()}"


def create_draft_with_settings(
    settings: AppSettings,
    subject: str,
    body_text: str,
    body_html: Optional[str],
    *,
    local_store_dir: Path,
    recipient_email: Optional[str] = None,
) -> DraftResult:
    provider = settings.email_provider
    to_alias = recipient_email or settings.email_draft_to

    if provider == "none":
        svc = LocalEmailDraftService(local_store_dir)
        did = svc.create_draft(subject, body_text, body_html)
        return DraftResult(provider="none", status="created_local", draft_provider_id=did, to_alias=to_alias)

    if provider == "sendgrid":
        # Minimal implementation: treat "sendgrid" the same way as "none" by creating
        # a local draft artifact, so the pipeline can run end-to-end without crashing.
        # (A real SendGrid "draft" concept is not a 1:1 match; API send integration is out of scope here.)
        if not local_store_dir:
            raise RuntimeError("sendgrid provider requires local_store_dir")
        svc = LocalEmailDraftService(local_store_dir)
        did = svc.create_draft(subject, body_text, body_html)
        return DraftResult(provider="sendgrid", status="created_local", draft_provider_id=did, to_alias=to_alias)

    if provider == "gmail":
        if not (settings.email_username and settings.email_password):
            raise RuntimeError(
                "gmail provider selected but REVIEW_PULSE_EMAIL_USERNAME / "
                "REVIEW_PULSE_EMAIL_PASSWORD are not set"
            )
        if not to_alias:
            raise RuntimeError("gmail provider requires recipient email (set --to-email or REVIEW_PULSE_EMAIL_DRAFT_TO)")
        did = _create_gmail_draft_imap(
            username=settings.email_username,
            password=settings.email_password.get_secret_value(),
            to_email=to_alias,
            subject=subject,
            body_text=body_text,
            body_html=body_html,
        )
        return DraftResult(provider="gmail", status="created_provider", draft_provider_id=did, to_alias=to_alias)

    raise RuntimeError(f"Unsupported email provider: {provider}")
