"""FastAPI endpoints for triggering the weekly pipeline (Phase 7)."""

from __future__ import annotations

import json
import os
import threading
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel, ConfigDict, Field

from phase1.config import get_settings
from phase2.collectors.target_collect import collect_app_store_until_target, collect_google_play_until_target
from phase7.run_pipeline import FileRunTracker, run_weekly_pipeline
from phase7.google_doc_append import append_weekly_json_to_google_doc


def _mark_stale_run_if_needed(*, run_payload: Dict[str, Any], tracker: FileRunTracker) -> Dict[str, Any]:
    if run_payload.get("status") != "running":
        return run_payload
    started_at = run_payload.get("startedAt")
    if not isinstance(started_at, str) or not started_at.strip():
        return run_payload
    try:
        started_dt = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
    except Exception:
        return run_payload

    max_run_seconds = int(get_settings().max_run_seconds)
    age_seconds = (datetime.now(timezone.utc) - started_dt).total_seconds()
    if age_seconds <= max_run_seconds:
        return run_payload

    updated = dict(run_payload)
    updated["status"] = "failed"
    updated["error"] = f"Run marked stale after exceeding {max_run_seconds}s without completion."
    updated["endedAt"] = datetime.now(timezone.utc).isoformat()
    phase_status = updated.get("phaseStatus") or {}
    phase_status["phase_timeout"] = {
        "status": "failed",
        "reason": "stale_run_timeout",
        "max_run_seconds": max_run_seconds,
    }
    updated["phaseStatus"] = phase_status
    run_id = updated.get("runId")
    if isinstance(run_id, str) and run_id:
        tracker.set_run_payload(run_id, updated)
    return updated


def _default_phase2_jsonl_path() -> Path:
    p = Path("data/phase2")
    # Pick most recently modified collected_*.jsonl.
    candidates = sorted(p.glob("collected_*.jsonl"), key=lambda x: x.stat().st_mtime, reverse=True)
    if not candidates:
        raise FileNotFoundError("No Phase 2 JSONL found under data/phase2/collected_*.jsonl")
    return candidates[0]


def _start_pipeline_thread(**kwargs: Any) -> None:
    t = threading.Thread(target=run_weekly_pipeline, kwargs=kwargs, daemon=True)
    t.start()


def _collect_phase2_jsonl_best_effort(*, out_dir: Path, max_reviews: int) -> Optional[Path]:
    """Best-effort remote collection fallback for API runs.

    Returns a combined JSONL path when at least one source is configured and produced rows;
    otherwise returns None so caller can surface a clear 400 error.
    """
    settings = get_settings()
    if settings.disable_remote_collect:
        return None
    sources: list[str] = []
    if settings.app_store_app_id:
        sources.append("app_store")
    if settings.google_play_package:
        sources.append("google_play")
    if not sources:
        return None

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    tmp_dir = out_dir / "phase2_collect"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    out_path = tmp_dir / f"combined_{ts}.jsonl"

    per_source = max(1, max_reviews // len(sources))
    remainder = max_reviews - (per_source * len(sources))
    rows: list[dict] = []

    if "app_store" in sources:
        target = per_source + (1 if remainder > 0 else 0)
        remainder -= 1
        collected = collect_app_store_until_target(
            settings.app_store_app_id,
            "us",
            settings,
            target,
            apply_phase3=True,
        )
        rows.extend([r.model_dump(mode="json", by_alias=True) for r in collected])

    if "google_play" in sources:
        target = per_source + (1 if remainder > 0 else 0)
        remainder -= 1
        collected = collect_google_play_until_target(
            settings.google_play_package,
            settings,
            target,
            apply_phase3=True,
            lang="en",
            country="us",
        )
        rows.extend([r.model_dump(mode="json", by_alias=True) for r in collected])

    if not rows:
        return None

    with out_path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, default=str) + "\n")
    return out_path


class WeeklyRunRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    week_bucket: str = Field(..., alias="weekBucket", description="ISO week label, e.g. 2026-W11")
    trigger_type: str = Field(default="cli", alias="triggerType", description="scheduled|cli|ui|backfill")
    phase2_jsonl_path: Optional[Path] = Field(
        default=None,
        alias="phase2JsonlPath",
        description="Path to Phase 2 sanitized JSONL. If omitted, uses newest data/phase2/collected_*.jsonl.",
    )
    recipient_email: Optional[str] = Field(
        default=None, alias="recipientEmail", description="Recipient email for Phase 6 (frontend-provided)"
    )
    recipient_name: Optional[str] = Field(
        default=None,
        alias="recipientName",
        description="Recipient name for personalized greeting (frontend-provided)",
    )
    send_now: bool = Field(default=False, alias="sendNow", description="If true, send email immediately (gmail only in MVP)")
    max_reviews: int = Field(default=200, alias="maxReviews", ge=1, le=50_000)
    max_chars: int = Field(default=30_000, alias="maxChars", ge=1)
    chunked: bool = Field(default=True, alias="chunked")


class WeeklyRunResponse(BaseModel):
    runId: str
    status: str


class BackfillRequest(BaseModel):
    from_week: str
    to_week: str
    trigger_type: str = Field(default="backfill")


class GoogleDocAppendRequest(BaseModel):
    doc_id: Optional[str] = Field(default=None, alias="docId")


def create_app(*, api_base_dir: Path | None = None) -> FastAPI:
    app = FastAPI(title="ReviewPulse API (Phase 7)")
    cors_origins_raw = os.environ.get("REVIEW_PULSE_CORS_ORIGINS", "*")
    if cors_origins_raw.strip() == "*":
        allow_origins = ["*"]
    else:
        allow_origins = [x.strip() for x in cors_origins_raw.split(",") if x.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allow_origins or ["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    out_dir = api_base_dir or Path("data/phase7")
    tracker = FileRunTracker(out_dir)

    class _RunIdParam(BaseModel):
        runId: str

    @app.post("/runs/weekly", response_model=WeeklyRunResponse)
    def post_weekly_run(req: WeeklyRunRequest, background_tasks: BackgroundTasks) -> WeeklyRunResponse:
        phase2_path: Optional[Path] = req.phase2_jsonl_path
        if phase2_path is None:
            try:
                phase2_path = _default_phase2_jsonl_path()
            except Exception:
                phase2_path = _collect_phase2_jsonl_best_effort(out_dir=out_dir, max_reviews=req.max_reviews)
                if phase2_path is None:
                    raise HTTPException(
                        status_code=400,
                        detail=(
                            "No Phase 2 JSONL found under data/phase2/collected_*.jsonl and remote collection "
                            "is not configured/returned no rows (or REVIEW_PULSE_DISABLE_REMOTE_COLLECT is set). "
                            "Ingest CSV via review-pulse-phase2-ingest, set store IDs for collection, "
                            "or pass phase2JsonlPath."
                        ),
                    )

        run_id = tracker.create_run(week_bucket=req.week_bucket, trigger_type=req.trigger_type)

        _start_pipeline_thread(
            run_id=run_id,
            week_bucket=req.week_bucket,
            phase2_jsonl_path=phase2_path,
            trigger_type=req.trigger_type,
            send_now=req.send_now,
            recipient_email=req.recipient_email,
            recipient_name=req.recipient_name,
            max_reviews=req.max_reviews,
            max_chars=req.max_chars,
            chunked=req.chunked,
            output_dir=out_dir,
            tracker=tracker,
        )
        return WeeklyRunResponse(runId=run_id, status="running")

    @app.get("/ui")
    def simple_ui() -> HTMLResponse:
        # Minimal UI (no JS build tool) so it can be shown inside Cursor easily.
        html = """
<!doctype html>
<html>
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Review Pulse UI</title>
    <style>
      body { font-family: system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif; padding: 24px; }
      .card { max-width: 560px; display: grid; gap: 12px; }
      label { display: grid; gap: 4px; }
      input { padding: 8px 10px; border: 1px solid #ddd; border-radius: 8px; }
      button { padding: 10px 14px; border: 0; border-radius: 10px; background: #111; color: white; cursor: pointer; }
      pre { background: #f7f7f7; padding: 12px; border-radius: 10px; overflow: auto; }
    </style>
  </head>
  <body>
    <div class="card">
      <h2>Review Pulse</h2>
      <label>
        Week bucket
        <input id="weekBucket" value="2026-W12" />
      </label>
      <label>
        Recipient email
        <input id="recipientEmail" placeholder="you@example.com" />
      </label>
      <label>
        Recipient name
        <input id="recipientName" placeholder="e.g. Tinu" />
      </label>
      <label style="display:flex; gap:10px; align-items:center;">
        <input id="sendNow" type="checkbox" />
        Send immediately (gmail only in MVP)
      </label>
      <button id="startBtn">Generate & Create Draft/Send</button>
      <div>
        <div>Run ID: <span id="runId">-</span></div>
        <div>Status: <span id="status">idle</span></div>
        <div id="error"></div>
      </div>
    </div>

    <script>
      const API_BASE = "";
      const $ = (id) => document.getElementById(id);

      let timer = null;

      async function pollRun(runId) {
        timer = setInterval(async () => {
          try {
            const res = await fetch(`${API_BASE}/runs/${encodeURIComponent(runId)}`);
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const data = await res.json();
            $('status').textContent = data.status || '-';
            $('error').textContent = data.error || '';
            if (data.status === 'succeeded' || data.status === 'failed') {
              clearInterval(timer);
            }
          } catch (e) {
            $('status').textContent = 'failed';
            $('error').textContent = String(e);
            clearInterval(timer);
          }
        }, 1500);
      }

      $('startBtn').addEventListener('click', async () => {
        $('runId').textContent = '-';
        $('status').textContent = 'starting';
        $('error').textContent = '';

        const payload = {
          weekBucket: $('weekBucket').value,
          triggerType: 'ui',
          recipientEmail: $('recipientEmail').value || null,
          recipientName: $('recipientName').value || null,
          sendNow: $('sendNow').checked,
          chunked: false,
          maxReviews: 500,
          maxChars: 80000
        };

        const res = await fetch(`${API_BASE}/runs/weekly`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        if (!res.ok) {
          const txt = await res.text();
          $('status').textContent = 'failed';
          $('error').textContent = txt;
          return;
        }
        const data = await res.json();
        $('runId').textContent = data.runId;
        $('status').textContent = data.status || 'running';
        pollRun(data.runId);
      });
    </script>
  </body>
</html>
"""
        return HTMLResponse(html)

    @app.get("/")
    def redirect_root() -> RedirectResponse:
        return RedirectResponse(url="/ui")

    @app.get("/runs/{run_id}")
    def get_run(run_id: str) -> Dict[str, Any]:
        r = tracker.get_run(run_id)
        if not r:
            raise HTTPException(status_code=404, detail="Run not found")
        return _mark_stale_run_if_needed(run_payload=r, tracker=tracker)

    @app.get("/reports/weekly")
    def get_weekly_report(week: str) -> Dict[str, Any]:
        report_path = out_dir / "reports" / f"weekly_{week}.json"
        if not report_path.is_file():
            raise HTTPException(status_code=404, detail="Report not found")
        return json.loads(report_path.read_text(encoding="utf-8"))

    @app.post("/runs/backfill")
    def backfill_runs(
        from_week: str,
        to_week: str,
        background_tasks: BackgroundTasks,
        trigger_type: str = "backfill",
        phase2_jsonl_path: Optional[Path] = None,
        recipient_email: Optional[str] = None,
        recipient_name: Optional[str] = None,
        send_now: bool = False,
        max_reviews: int = 500,
        max_chars: int = 80_000,
        chunked: bool = False,
    ) -> Dict[str, Any]:
        def _parse_week(s: str) -> tuple[int, int]:
            s = s.strip()
            y_s, w_s = s.split("-W")
            return int(y_s), int(w_s)

        y1, w1 = _parse_week(from_week)
        y2, w2 = _parse_week(to_week)
        start = datetime.fromisocalendar(y1, w1, 1)
        end = datetime.fromisocalendar(y2, w2, 1)

        runs: list[WeeklyRunResponse] = []
        current = start
        while current <= end:
            bucket = f"{current.isocalendar().year}-W{current.isocalendar().week:02d}"
            run_id = tracker.create_run(week_bucket=bucket, trigger_type=trigger_type)
            phase2_path = phase2_jsonl_path or _default_phase2_jsonl_path()
            _start_pipeline_thread(
                run_id=run_id,
                week_bucket=bucket,
                phase2_jsonl_path=phase2_path,
                trigger_type=trigger_type,
                send_now=send_now,
                recipient_email=recipient_email,
                recipient_name=recipient_name,
                max_reviews=max_reviews,
                max_chars=max_chars,
                chunked=chunked,
                output_dir=out_dir,
                tracker=tracker,
            )
            runs.append(WeeklyRunResponse(runId=run_id, status="running"))
            current = current + timedelta(weeks=1)

        return {"runs": [r.model_dump() for r in runs]}

    @app.post("/runs/{run_id}/google-doc-append")
    def append_run_to_google_doc(run_id: str, req: GoogleDocAppendRequest) -> Dict[str, Any]:
        settings = get_settings()
        if not settings.enable_google_doc_append:
            raise HTTPException(status_code=400, detail="Google doc append is disabled by configuration")
        run_payload = tracker.get_run(run_id)
        if not run_payload:
            raise HTTPException(status_code=404, detail="Run not found")
        if run_payload.get("status") != "succeeded":
            raise HTTPException(status_code=400, detail="Run must be succeeded before google doc append")
        combined_path = out_dir / "runs" / run_id / "combined_payload.json"
        if not combined_path.is_file():
            raise HTTPException(status_code=404, detail="Combined payload not found for run")
        doc_id = (req.doc_id or settings.google_doc_default_id or "").strip()
        if not doc_id:
            raise HTTPException(status_code=400, detail="docId is required (or set REVIEW_PULSE_GOOGLE_DOC_DEFAULT_ID)")
        payload = json.loads(combined_path.read_text(encoding="utf-8"))
        try:
            res = append_weekly_json_to_google_doc(
                doc_id=doc_id,
                payload_json=payload,
                out_dir=out_dir / "google_docs",
                mcp_command=settings.google_mcp_append_command,
                timeout_seconds=settings.google_mcp_timeout_seconds,
            )
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=500, detail=f"google doc append failed: {exc}") from exc
        run_payload.setdefault("phaseStatus", {})
        run_payload["phaseStatus"]["google_doc_append"] = {
            "status": res.get("append_status", "appended"),
            "doc_id": doc_id,
            "appended_at": res.get("appended_at"),
            "storage_path": res.get("storage_path"),
        }
        tracker.set_run_payload(run_id, run_payload)
        return res

    return app


app = create_app()

