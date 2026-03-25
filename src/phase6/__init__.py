"""Phase 6 — email drafting."""

from phase6.email_draft import (
    DraftResult,
    compose_body_html,
    compose_body_text,
    compose_subject,
    create_draft_with_settings,
)

__all__ = [
    "DraftResult",
    "compose_subject",
    "compose_body_text",
    "compose_body_html",
    "create_draft_with_settings",
]
