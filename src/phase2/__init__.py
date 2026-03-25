"""Phase 2 — CSV ingestion, remote collection (App Store RSS, Play scraper), normalization."""

from phase2.ingestion import (
    CsvIngestionService,
    IngestionStats,
    ingest_csv,
)

__all__ = [
    "CsvIngestionService",
    "IngestionStats",
    "ingest_csv",
]
