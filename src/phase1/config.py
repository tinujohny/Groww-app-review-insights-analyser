"""Environment-specific settings and export limits (e.g. 500 vs 5000 reviews per download)."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal, Optional

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from phase1.constants import MIN_REVIEW_WORDS
from phase1.schemas.enums import Environment


class AppSettings(BaseSettings):
    """Application configuration; secrets use SecretStr so they are not logged by default."""

    model_config = SettingsConfigDict(
        env_prefix="REVIEW_PULSE_",
        env_file=(".env",),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: Environment = Field(
        default=Environment.DEV,
        description="Runtime environment: dev, staging, or prod.",
    )

    max_reviews_per_export: int = Field(
        default=500,
        ge=1,
        le=50_000,
        description=(
            "Maximum reviews expected from a single storefront export or download. "
            "Many UIs cap at ~500 rows per export; raise toward 5000 when the source allows "
            "(e.g. multiple exports, higher API limits, or vendor change)."
        ),
    )

    min_review_words: int = Field(
        default=MIN_REVIEW_WORDS,
        ge=1,
        le=500,
        description="Minimum word count for review body text; shorter reviews are excluded.",
    )

    review_languages: str = Field(
        default="en",
        description=(
            "Comma-separated ISO 639-1 codes (e.g. `en` or `en,de`). "
            "Reviews whose detected language is not in this set are dropped (Phase 3)."
        ),
    )

    strict_language_detection: bool = Field(
        default=False,
        description=(
            "If True, drop a review when language detection fails. "
            "If False, keep the review when detection is inconclusive."
        ),
    )

    drop_reviews_with_emojis: bool = Field(
        default=True,
        description=(
            "If True, exclude reviews whose body text contains emoji (Phase 3 emoji filter)."
        ),
    )

    groq_api_key: Optional[SecretStr] = Field(
        default=None,
        description="Groq API key for theme generation and weekly pulse (Phase 4+).",
    )
    groq_model: str = Field(
        default="llama-3.3-70b-versatile",
        description="Groq chat model id for theme / pulse generation.",
    )
    gemini_api_key: Optional[SecretStr] = Field(
        default=None,
        description="Gemini API key used as fallback when Groq is exhausted/rate-limited.",
    )
    gemini_model: str = Field(
        default="gemini-1.5-flash",
        description="Gemini model id for fallback theme / pulse generation.",
    )

    email_provider: Literal["gmail", "sendgrid", "none"] = Field(
        default="none",
        description="Email integration target for draft creation (Phase 6+).",
    )
    email_api_key: Optional[SecretStr] = Field(
        default=None,
        description="Provider API key or token (meaning depends on email_provider).",
    )
    email_username: Optional[str] = Field(
        default=None,
        description="Email username/login for provider auth (Phase 6).",
    )
    email_password: Optional[SecretStr] = Field(
        default=None,
        description="Email password/app-password for provider auth (Phase 6).",
    )
    email_oauth_client_id: Optional[SecretStr] = Field(
        default=None,
        description="Optional OAuth client id for mailbox draft APIs.",
    )
    email_oauth_client_secret: Optional[SecretStr] = Field(
        default=None,
        description="Optional OAuth client secret for mailbox draft APIs.",
    )
    email_draft_to: Optional[str] = Field(
        default=None,
        description="Default recipient alias for weekly draft emails.",
    )

    app_store_app_id: Optional[str] = Field(
        default="1404871703",
        description="Numeric App Store app id for RSS collection (see App Store URL id=…).",
    )
    google_play_package: Optional[str] = Field(
        default="com.nextbillion.groww",
        description="Android applicationId / package name for Play Store review collection.",
    )

    disable_remote_collect: bool = Field(
        default=False,
        description=(
            "If True, Phase 7 API will not fall back to App Store RSS / Play scraping when no local "
            "Phase 2 JSONL exists (CSV-ingest-only / compliance mode)."
        ),
    )
    enable_fee_explanation: bool = Field(
        default=True,
        description="If True, include fee explanation scenario block in Phase 6 mail output.",
    )
    fee_scenario: str = Field(
        default="Mutual Fund Exit Load",
        description="Fee explanation scenario label appended to weekly mail.",
    )
    fee_source_links: str = Field(
        default="https://groww.in/mutual-funds/amc",
        description="Comma-separated reference URLs used for fee explanation context.",
    )
    enable_google_doc_append: bool = Field(
        default=True,
        description="If True, allow Phase 7 endpoint to append combined JSON payload to Google doc via MCP adapter.",
    )
    google_doc_default_id: Optional[str] = Field(
        default=None,
        description="Default Google doc id for combined JSON append endpoint when caller omits docId.",
    )
    google_mcp_append_command: Optional[str] = Field(
        default=None,
        description=(
            "Command template to append combined JSON to Google Doc via MCP. "
            "Supports placeholders: {doc_id} and {payload_path}."
        ),
    )
    google_mcp_timeout_seconds: int = Field(
        default=30,
        ge=1,
        le=300,
        description="Timeout for the MCP append command execution.",
    )


@lru_cache
def get_settings() -> AppSettings:
    """Cached settings singleton for workers and API processes."""
    return AppSettings()
