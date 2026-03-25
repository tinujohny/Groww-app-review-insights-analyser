"""Unified review record after ingestion and normalization (Phase 2 will populate)."""

import re
from datetime import date, datetime, timezone
from typing import Annotated
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator

from phase1.schemas.enums import ReviewSource
from phase1.text_utils import count_words

_ISO_WEEK_PATTERN = re.compile(r"^\d{4}-W(0[1-9]|[1-4][0-9]|5[0-3])$")


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class NormalizedReview(BaseModel):
    """Normalized public review row aligned with ARCHITECTURE Phase 2 contract.

    Review **title** is intentionally omitted (not used). Only **text** body is stored.
    """

    review_id_internal: UUID = Field(default_factory=uuid4, alias="reviewIdInternal")
    source: ReviewSource
    rating: Annotated[int, Field(ge=1, le=5)]
    text: str = Field(default="", max_length=50_000)
    review_date: date = Field(alias="reviewDate")
    ingested_at: datetime = Field(default_factory=_utc_now, alias="ingestedAt")
    week_bucket: str = Field(
        ...,
        description="ISO week label, e.g. 2026-W11",
        alias="weekBucket",
    )

    @field_validator("week_bucket")
    @classmethod
    def iso_week_format(cls, v: str) -> str:
        if not _ISO_WEEK_PATTERN.match(v):
            raise ValueError(
                "week_bucket must match YYYY-Www with ww in 01-53, e.g. 2026-W11",
            )
        return v

    @field_validator("text")
    @classmethod
    def text_min_words_and_strip(cls, v: str) -> str:
        from phase1.config import get_settings

        stripped = v.strip()
        min_w = get_settings().min_review_words
        if count_words(stripped) < min_w:
            raise ValueError(
                f"text must contain at least {min_w} words (titles are not used; body only)",
            )
        return stripped

    model_config = ConfigDict(frozen=False, str_strip_whitespace=True, populate_by_name=True)
