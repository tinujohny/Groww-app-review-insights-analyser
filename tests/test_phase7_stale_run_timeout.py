"""Phase 7 stale run timeout tests."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from phase7.api import create_app


def test_get_run_marks_stale_running_run_as_failed(tmp_path: Path, monkeypatch: object) -> None:
    monkeypatch.setenv("REVIEW_PULSE_MAX_RUN_SECONDS", "60")
    app = create_app(api_base_dir=tmp_path)
    client = TestClient(app)

    run_id = "run-timeout-1"
    old_started = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
    run_payload = {
        "runId": run_id,
        "weekBucket": "2026-W12",
        "triggerType": "ui",
        "status": "running",
        "startedAt": old_started,
        "phaseStatus": {},
        "error": None,
    }
    p = tmp_path / "runs" / f"{run_id}.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(run_payload) + "\n", encoding="utf-8")

    resp = client.get(f"/runs/{run_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "failed"
    assert "stale" in (body.get("error") or "").lower()
    assert body.get("phaseStatus", {}).get("phase_timeout", {}).get("status") == "failed"
