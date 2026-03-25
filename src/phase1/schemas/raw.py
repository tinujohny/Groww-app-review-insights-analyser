"""Raw review row aligned with `reviews_raw` (persisted after Phase 2 ingestion)."""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from phase1.schemas.enums import ReviewSource


class ReviewRaw(BaseModel):
    """Ingested row before normalization. Store title is not modeled — only review body text."""

    id: UUID = Field(default_factory=uuid4)
    source: ReviewSource
    external_review_id: Optional[str] = None
    rating: Annotated[int, Field(ge=1, le=5)]
    text_raw: str = ""
    review_date: date
    ingested_at: datetime
    batch_id: UUID
