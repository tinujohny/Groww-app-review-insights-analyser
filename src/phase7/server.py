"""FastAPI server entrypoint for the Web UI."""

from __future__ import annotations

import os
from typing import Optional

import uvicorn

from phase7.api import create_app


def main(*, host: str = "127.0.0.1", port: int | None = None) -> None:
    if port is None:
        port = int(os.environ.get("PORT", "8000"))
    uvicorn.run(
        create_app(),
        host=host,
        port=port,
        log_level=os.environ.get("LOG_LEVEL", "info"),
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    host = os.environ.get("HOST", "127.0.0.1")
    main(host=host, port=port)

