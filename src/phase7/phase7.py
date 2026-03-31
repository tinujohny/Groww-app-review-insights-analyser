"""Canonical Phase 7 entrypoints (single file for phase runners)."""

from __future__ import annotations

import os

import uvicorn

from phase7.api import create_app
from phase7.weekly_run_cli import main as main_run_weekly
from phase7.weekly_scheduler import main as main_scheduler


def main_api(*, host: str = "0.0.0.0", port: int | None = None) -> None:
    if port is None:
        port = int(os.environ.get("PORT", "8000"))
    uvicorn.run(
        create_app(),
        host=host,
        port=port,
        log_level=os.environ.get("LOG_LEVEL", "info"),
    )


__all__ = ["main_api", "main_run_weekly", "main_scheduler"]
