"""Phase 1: emit a fresh manifest of effective config and schema contracts (no secrets)."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import SecretStr

from phase1 import constants
from phase1.config import AppSettings, get_settings
from phase1.schemas import NormalizedReview, ReviewSource
from phase3.language_filter import parse_allowed_language_codes


def _secret_status(value: Optional[SecretStr]) -> str:
    if value is None:
        return "not_set"
    return "set"


def phase1_manifest_dict() -> Dict[str, Any]:
    """Build manifest; reloads settings from env / .env (clears settings cache first)."""
    get_settings.cache_clear()
    settings = AppSettings()

    example = NormalizedReview(
        review_id_internal=UUID("00000000-0000-4000-8000-000000000001"),
        source=ReviewSource.GOOGLE_PLAY,
        rating=5,
        text="one two three four five example review body text",
        review_date=dt.date(2026, 3, 22),
        week_bucket="2026-W12",
    )

    try:
        pkg_ver = version("review-pulse")
    except PackageNotFoundError:
        pkg_ver = "0.0.0"

    allowed_langs = parse_allowed_language_codes(settings.review_languages)

    return {
        "phase": 1,
        "package_version": pkg_ver,
        "generated_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "settings": {
            "environment": settings.environment.value,
            "max_reviews_per_export": settings.max_reviews_per_export,
            "min_review_words": settings.min_review_words,
            "review_languages": settings.review_languages,
            "allowed_language_codes": sorted(allowed_langs),
            "strict_language_detection": settings.strict_language_detection,
            "drop_reviews_with_emojis": settings.drop_reviews_with_emojis,
            "groq_api_key": _secret_status(settings.groq_api_key),
            "email_provider": settings.email_provider,
            "email_api_key": _secret_status(settings.email_api_key),
            "email_oauth_client_id": _secret_status(settings.email_oauth_client_id),
            "email_oauth_client_secret": _secret_status(settings.email_oauth_client_secret),
            "email_draft_to": settings.email_draft_to,
        },
        "constants": {
            "TYPICAL_SINGLE_EXPORT_ROW_LIMIT": constants.TYPICAL_SINGLE_EXPORT_ROW_LIMIT,
            "MIN_REVIEW_WORDS": constants.MIN_REVIEW_WORDS,
        },
        "phase3_language_filter": {
            "description": "Non-matching languages are removed using langdetect on review body text.",
            "allowed_codes": sorted(allowed_langs),
            "strict_detection": settings.strict_language_detection,
        },
        "phase3_emoji_filter": {
            "description": "Reviews containing emoji in body text are removed when enabled.",
            "drop_reviews_with_emojis": settings.drop_reviews_with_emojis,
            "library": "emoji",
        },
        "normalized_review_example": example.model_dump(mode="json"),
        "normalized_review_json_schema": NormalizedReview.model_json_schema(),
    }


def write_phase1_manifest(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = phase1_manifest_dict()
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run Phase 1: write redacted config + schema manifest JSON.",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=Path("data/phase1/phase1_manifest.json"),
        help="Output path (default: data/phase1/phase1_manifest.json)",
    )
    args = parser.parse_args(argv)
    write_phase1_manifest(args.output)
    print(f"Wrote Phase 1 manifest: {args.output.resolve()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
