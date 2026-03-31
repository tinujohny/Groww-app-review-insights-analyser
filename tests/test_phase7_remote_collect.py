"""Phase 7 API remote-collect guard."""

from __future__ import annotations

from pathlib import Path


def test_collect_phase2_skipped_when_disable_remote_collect(monkeypatch: object, tmp_path: Path) -> None:
    from phase1 import config

    monkeypatch.setenv("REVIEW_PULSE_DISABLE_REMOTE_COLLECT", "true")
    config.get_settings.cache_clear()
    try:
        from phase7.api import _collect_phase2_jsonl_best_effort

        assert _collect_phase2_jsonl_best_effort(out_dir=tmp_path, max_reviews=100) is None
    finally:
        monkeypatch.delenv("REVIEW_PULSE_DISABLE_REMOTE_COLLECT", raising=False)
        config.get_settings.cache_clear()
