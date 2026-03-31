"""Google doc append adapter (MCP command bridge)."""

from __future__ import annotations

import json
import shlex
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict


def _append_via_mcp_command(
    *,
    doc_id: str,
    payload_json: Dict[str, Any],
    mcp_command: str,
    timeout_seconds: int,
) -> Dict[str, Any]:
    """Run an MCP command template to append payload to Google Docs.

    Template placeholders:
    - {doc_id}
    - {payload_path}
    """
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".json", delete=False) as tf:
        tf.write(json.dumps(payload_json, indent=2))
        payload_path = Path(tf.name)

    cmd_text = mcp_command.replace("{doc_id}", doc_id).replace("{payload_path}", str(payload_path))
    cmd = shlex.split(cmd_text)
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"MCP command failed (exit={proc.returncode}): {proc.stderr.strip() or proc.stdout.strip()}"
        )
    now = datetime.now(timezone.utc).isoformat()
    parsed: Dict[str, Any] = {}
    stdout = (proc.stdout or "").strip()
    if stdout:
        try:
            obj = json.loads(stdout)
            if isinstance(obj, dict):
                parsed = obj
        except Exception:
            parsed = {}
    return {
        "doc_id": doc_id,
        "append_status": str(parsed.get("append_status") or "appended"),
        "appended_at": str(parsed.get("appended_at") or now),
        "mcp_command": cmd_text,
        "mcp_stdout": stdout[:5000],
    }


def append_weekly_json_to_google_doc(
    *,
    doc_id: str,
    payload_json: Dict[str, Any],
    out_dir: Path,
    mcp_command: str | None = None,
    timeout_seconds: int = 30,
) -> Dict[str, Any]:
    """Append combined JSON to Google Docs using MCP command bridge."""
    if not doc_id.strip():
        raise ValueError("doc_id is required")
    if not (mcp_command and mcp_command.strip()):
        raise RuntimeError(
            "REVIEW_PULSE_GOOGLE_MCP_APPEND_COMMAND is required for Google Docs integration."
        )
    # Keep output directory creation for parity with caller expectations/logs.
    out_dir.mkdir(parents=True, exist_ok=True)
    return _append_via_mcp_command(
        doc_id=doc_id,
        payload_json=payload_json,
        mcp_command=mcp_command.strip(),
        timeout_seconds=timeout_seconds,
    )

