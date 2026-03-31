"""Phase 6 email draft tests."""

from __future__ import annotations

from phase1.config import AppSettings
import phase6.email_draft as email_draft
from phase6.email_draft import compose_body_text, compose_subject, create_draft_with_settings
from phase6.phase6 import _resolve_recipient, _resolve_recipient_name


def test_subject_format():
    assert compose_subject("2026-W12") == "Groww Weekly Review Pulse - 2026-W12"


def test_body_footer_has_metadata():
    p = {
        "week": "2026-W12",
        "noteText": "Top themes:\n- app_performance",
        "topThemes": [{"name": "app_performance", "reviewCount": 7}],
    }
    body = compose_body_text(p)
    assert "Metadata" in body
    assert "week_range: 2026-W12" in body
    assert "review_count: 7" in body
    assert body.startswith("Hi,")


def test_body_has_personalized_greeting():
    p = {
        "week": "2026-W12",
        "recipientName": "Aisha",
        "noteText": "Pulse body",
        "topThemes": [{"name": "x", "reviewCount": 1}],
    }
    body = compose_body_text(p)
    assert body.startswith("Hi Aisha,")


def test_body_includes_fee_explanation_block():
    p = {
        "week": "2026-W12",
        "noteText": "Pulse body",
        "topThemes": [{"name": "x", "reviewCount": 1}],
        "fee_scenario": "Mutual Fund Exit Load",
        "explanation_bullets": ["Bullet 1", "Bullet 2", "Bullet 3"],
        "source_links": ["https://groww.in/mutual-funds/amc"],
    }
    body = compose_body_text(p)
    assert "Fee Explanation: Mutual Fund Exit Load" in body
    assert "- Bullet 1" in body
    assert "Source links:" in body


def test_provider_none_creates_local_draft(tmp_path):
    s = AppSettings(_env_file=None, email_provider="none", email_draft_to="me@example.com")
    res = create_draft_with_settings(
        s,
        "Groww Weekly Review Pulse - 2026-W12",
        "hello",
        "<p>hello</p>",
        local_store_dir=tmp_path,
    )
    assert res.status == "created_local"
    assert res.draft_provider_id and res.draft_provider_id.startswith("local-")


def test_provider_sendgrid_creates_local_draft(tmp_path):
    s = AppSettings(_env_file=None, email_provider="sendgrid", email_draft_to="me@example.com")
    res = create_draft_with_settings(
        s,
        "Groww Weekly Review Pulse - 2026-W12",
        "hello",
        "<p>hello</p>",
        local_store_dir=tmp_path,
    )
    assert res.status == "created_local"
    assert res.provider == "sendgrid"
    assert res.draft_provider_id and res.draft_provider_id.startswith("local-")


def test_recipient_resolution_prefers_cli_then_payload_then_settings():
    payload = {"recipientEmail": "payload@example.com"}
    assert _resolve_recipient("cli@example.com", payload, "env@example.com") == "cli@example.com"
    assert _resolve_recipient(None, payload, "env@example.com") == "payload@example.com"
    assert _resolve_recipient(None, {}, "env@example.com") == "env@example.com"


def test_gmail_requires_username_password():
    s = AppSettings(_env_file=None, email_provider="gmail")
    try:
        create_draft_with_settings(
            s,
            "Groww Weekly Review Pulse - 2026-W12",
            "body",
            "<p>body</p>",
            local_store_dir=None,  # unused due to early validation error
        )
        assert False, "expected RuntimeError"
    except RuntimeError as exc:
        assert "EMAIL_USERNAME" in str(exc)


def test_gmail_creates_provider_draft_with_mocked_imap(monkeypatch):
    class FakeImap:
        def __init__(self, host, port):
            self.host = host
            self.port = port

        def login(self, user, pwd):
            return "OK", [b"logged in"]

        def append(self, mailbox, flags, when, msg_bytes):
            return "OK", [b"[APPENDUID 9 99]"]

        def logout(self):
            return "BYE", [b"done"]

    monkeypatch.setattr(email_draft.imaplib, "IMAP4_SSL", FakeImap)
    s = AppSettings(
        _env_file=None,
        email_provider="gmail",
        email_username="u@example.com",
        email_password="app-password-1234",
    )
    res = create_draft_with_settings(
        s,
        "Groww Weekly Review Pulse - 2026-W12",
        "body",
        "<p>body</p>",
        local_store_dir=None,  # unused for gmail
        recipient_email="to@example.com",
    )
    assert res.status == "created_provider"
    assert res.provider == "gmail"
    assert res.draft_provider_id


def test_recipient_name_resolution_prefers_cli_then_payload():
    payload = {"recipientName": "Payload Name"}
    assert _resolve_recipient_name("CLI Name", payload) == "CLI Name"
    assert _resolve_recipient_name(None, payload) == "Payload Name"
    assert _resolve_recipient_name(None, {}) is None


def test_send_gmail_email_smtp_mock(monkeypatch):
    class FakeSMTP:
        def __init__(self, host, port, timeout=None):
            self.host = host
            self.port = port
            self.timeout = timeout
            self.logged_in = False
            self.sent = False

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def login(self, user, pwd):
            self.logged_in = True

        def send_message(self, msg):
            self.sent = True

    monkeypatch.setattr(email_draft.smtplib, "SMTP_SSL", FakeSMTP)
    token = email_draft.send_gmail_email_smtp(
        username="u@example.com",
        password="app-pass",
        to_email="to@example.com",
        subject="s",
        body_text="b",
        body_html="<p>b</p>",
    )
    assert token.startswith("gmail-smtp-")
