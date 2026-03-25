"""Phase 2 CSV ingestion tests."""

from pathlib import Path

import pytest

from phase1.schemas.enums import ReviewSource
from phase2.ingestion import CsvIngestionService, ingest_csv

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def test_ingest_google_play_sample_no_phase3(monkeypatch):
    monkeypatch.setenv("REVIEW_PULSE_REVIEW_LANGUAGES", "en")
    reviews, stats = ingest_csv(
        FIXTURES / "google_play_sample.csv",
        ReviewSource.GOOGLE_PLAY,
        apply_phase3_filters=False,
    )
    assert stats.rows_read == 3
    assert stats.rows_skipped_validation >= 1
    assert stats.rows_normalized == 2
    assert len(reviews) == 2
    assert all(r.source == ReviewSource.GOOGLE_PLAY for r in reviews)
    assert reviews[0].rating == 5


def test_ingest_app_store_sample_no_phase3(monkeypatch):
    monkeypatch.setenv("REVIEW_PULSE_REVIEW_LANGUAGES", "en")
    reviews, stats = ingest_csv(
        FIXTURES / "app_store_sample.csv",
        ReviewSource.APP_STORE,
        apply_phase3_filters=False,
    )
    assert stats.rows_read == 2
    assert len(reviews) == 1
    assert reviews[0].source == ReviewSource.APP_STORE


def test_csv_ingestion_service_protocol():
    svc = CsvIngestionService()
    out = svc.import_from_export(
        ReviewSource.GOOGLE_PLAY,
        str(FIXTURES / "google_play_sample.csv"),
    )
    assert isinstance(out, list)


def test_google_play_bad_header(tmp_path):
    p = tmp_path / "bad.csv"
    p.write_text("Wrong,Columns,Here\n1,2,3\n", encoding="utf-8")
    with pytest.raises(ValueError, match="rating column"):
        ingest_csv(p, ReviewSource.GOOGLE_PLAY, apply_phase3_filters=False)
