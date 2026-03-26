#!/usr/bin/env python3
"""Basic smoke test for deployed Review Pulse backend API."""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, Tuple


def _request(method: str, url: str, payload: Dict[str, Any] | None = None) -> Tuple[int, str]:
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url=url, method=method, data=data, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            return int(resp.getcode()), body
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        return int(exc.code), body


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke test deployed backend API")
    parser.add_argument(
        "--base-url",
        default="https://web-production-628ea.up.railway.app",
        help="Backend base URL",
    )
    parser.add_argument("--week-bucket", default="2026-W12", help="Week bucket for /runs/weekly test")
    args = parser.parse_args()

    base = args.base_url.rstrip("/")
    checks: list[tuple[str, bool, str]] = []

    # Check 1: UI endpoint should be reachable.
    code, body = _request("GET", f"{base}/ui")
    ok = code == 200 and "<html" in body.lower()
    checks.append(("GET /ui", ok, f"status={code}"))

    # Check 2: Try to start one run.
    payload = {
        "weekBucket": args.week_bucket,
        "triggerType": "ui",
        "sendNow": False,
        "chunked": True,
        "maxReviews": 50,
        "maxChars": 5000,
    }
    code, body = _request("POST", f"{base}/runs/weekly", payload=payload)
    known_missing_phase2 = code == 400 and "No Phase 2 JSONL found under data/phase2/collected_*.jsonl" in body
    run_ok = code in (200, 202) or known_missing_phase2
    detail = f"status={code}"
    run_id = None
    if run_ok:
        try:
            parsed = json.loads(body)
            run_id = parsed.get("runId")
            detail = f"status={code}, runId={run_id}"
        except Exception:
            detail = f"status={code}, invalid json"
    else:
        # 400/500 still useful for smoke debugging.
        detail = f"status={code}, body={body[:180]}"
    if known_missing_phase2:
        detail = (
            f"status={code}, backend reachable but no Phase 2 data in Railway container "
            "(configure collection env vars or provide phase2JsonlPath)"
        )
    checks.append(("POST /runs/weekly", run_ok, detail))

    # Check 3: If run started, poll run status once.
    if run_id:
        code, body = _request("GET", f"{base}/runs/{urllib.parse.quote(str(run_id))}")
        ok = code == 200
        checks.append((f"GET /runs/{run_id}", ok, f"status={code}, body={body[:180]}"))

    print("Backend smoke test results")
    print("=" * 26)
    failures = 0
    for name, ok, detail in checks:
        status = "PASS" if ok else "FAIL"
        print(f"[{status}] {name} -> {detail}")
        if not ok:
            failures += 1
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
