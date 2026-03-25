"""FastAPI endpoints for triggering the weekly pipeline (Phase 7)."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel, ConfigDict, Field

from phase7.run_pipeline import FileRunTracker, run_weekly_pipeline


def _default_phase2_jsonl_path() -> Path:
    p = Path("data/phase2")
    # Pick most recently modified collected_*.jsonl.
    candidates = sorted(p.glob("collected_*.jsonl"), key=lambda x: x.stat().st_mtime, reverse=True)
    if not candidates:
        raise FileNotFoundError("No Phase 2 JSONL found under data/phase2/collected_*.jsonl")
    return candidates[0]


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
    max_reviews: int = Field(default=500, alias="maxReviews", ge=1, le=50_000)
    max_chars: int = Field(default=80_000, alias="maxChars", ge=1)
    chunked: bool = Field(default=False, alias="chunked")


class WeeklyRunResponse(BaseModel):
    runId: str
    status: str


class BackfillRequest(BaseModel):
    from_week: str
    to_week: str
    trigger_type: str = Field(default="backfill")


def create_app(*, api_base_dir: Path | None = None) -> FastAPI:
    app = FastAPI(title="ReviewPulse API (Phase 7)")
    out_dir = api_base_dir or Path("data/phase7")
    tracker = FileRunTracker(out_dir)

    class _RunIdParam(BaseModel):
        runId: str

    @app.post("/runs/weekly", response_model=WeeklyRunResponse)
    def post_weekly_run(req: WeeklyRunRequest, background_tasks: BackgroundTasks) -> WeeklyRunResponse:
        try:
            phase2_path = req.phase2_jsonl_path or _default_phase2_jsonl_path()
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc))

        run_id = tracker.create_run(week_bucket=req.week_bucket, trigger_type=req.trigger_type)

        background_tasks.add_task(
            run_weekly_pipeline,
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
        return r

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
            background_tasks.add_task(
                run_weekly_pipeline,
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

    return app


app = create_app()

