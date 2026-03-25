"""Stable interfaces for later phases; implementations live in service modules."""

from __future__ import annotations

from typing import Optional, Protocol, runtime_checkable

from phase1.schemas import NormalizedReview, PipelineRunTrigger
from phase1.schemas.enums import ReviewSource


@runtime_checkable
class IngestionPort(Protocol):
    """Phase 2: import public CSV exports and emit normalized rows."""

    def import_from_export(self, source: ReviewSource, path: str) -> list[NormalizedReview]: ...


@runtime_checkable
class WeeklyRunPort(Protocol):
    """Orchestrates end-to-end weekly pipeline for a week bucket."""

    def run_weekly(
        self,
        week_bucket: str,
        trigger: PipelineRunTrigger,
    ) -> str: ...


@runtime_checkable
class EmailDraftPort(Protocol):
    """Phase 6: create provider mailbox draft."""

    def create_draft(self, subject: str, body_text: str, body_html: Optional[str]) -> str: ...
