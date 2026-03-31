"""Phase 7 Google doc append endpoint tests."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from phase7.api import create_app
from phase7.google_doc_append import append_weekly_json_to_google_doc


def test_append_run_to_google_doc_success(tmp_path: Path, monkeypatch: object) -> None:
    monkeypatch.setenv("REVIEW_PULSE_ENABLE_GOOGLE_DOC_APPEND", "true")
    monkeypatch.setenv(
        "REVIEW_PULSE_GOOGLE_MCP_APPEND_COMMAND",
        "python3 -c \"import json; print(json.dumps({'append_status':'appended'}))\"",
    )
    app = create_app(api_base_dir=tmp_path)
    client = TestClient(app)

    run_id = "run-123"
    run_payload = {
        "runId": run_id,
        "weekBucket": "2026-W12",
        "triggerType": "ui",
        "status": "succeeded",
        "phaseStatus": {},
        "error": None,
    }
    run_path = tmp_path / "runs" / f"{run_id}.json"
    run_path.parent.mkdir(parents=True, exist_ok=True)
    run_path.write_text(json.dumps(run_payload) + "\n", encoding="utf-8")

    combined = {
        "date": "2026-03-15",
        "weekly_pulse": {
            "themes": ["Theme 1", "Theme 2", "Theme 3"],
            "quotes": ["Quote 1", "Quote 2", "Quote 3"],
            "action_ideas": ["Action 1", "Action 2", "Action 3"],
        },
        "fee_scenario": "Mutual Fund Exit Load",
        "explanation_bullets": ["Fact 1", "Fact 2", "Fact 3"],
        "source_links": ["https://groww.in/mutual-funds/amc"],
        "last_checked": "2026-03-15",
    }
    combined_path = tmp_path / "runs" / run_id / "combined_payload.json"
    combined_path.parent.mkdir(parents=True, exist_ok=True)
    combined_path.write_text(json.dumps(combined) + "\n", encoding="utf-8")

    resp = client.post(f"/runs/{run_id}/google-doc-append", json={"docId": "doc-abc"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["append_status"] == "appended"
    assert body["doc_id"] == "doc-abc"


def test_append_via_mcp_command_bridge(tmp_path: Path) -> None:
    payload = {"hello": "world"}
    cmd = (
        "python3 -c \"import json; print(json.dumps("
        "{'append_status':'appended','appended_at':'2026-03-15T00:00:00Z'}))\""
    )
    res = append_weekly_json_to_google_doc(
        doc_id="doc-xyz",
        payload_json=payload,
        out_dir=tmp_path / "google_docs",
        mcp_command=cmd,
        timeout_seconds=10,
    )
    assert res["append_status"] == "appended"
    assert res["doc_id"] == "doc-xyz"
    assert "mcp_command" in res


def test_append_requires_mcp_command(tmp_path: Path) -> None:
    try:
        append_weekly_json_to_google_doc(
            doc_id="doc-xyz",
            payload_json={"x": 1},
            out_dir=tmp_path / "google_docs",
            mcp_command=None,
            timeout_seconds=5,
        )
        assert False, "expected RuntimeError"
    except RuntimeError as exc:
        assert "GOOGLE_MCP_APPEND_COMMAND" in str(exc)

