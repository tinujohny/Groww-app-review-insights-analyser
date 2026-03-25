"""Apple App Store (App Store Connect style) public review CSV parser."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Dict, Iterator, List, TextIO

from phase2.columns import (
    APP_STORE_DATE_ALIASES,
    APP_STORE_RATING_ALIASES,
    APP_STORE_TEXT_ALIASES,
    get_mapped_row,
    resolve_column,
)


def read_app_store_rows(path: Path) -> Iterator[Dict[str, Any]]:
    """
    Yield one dict per data row with keys ``rating_raw``, ``text_raw``, ``date_raw`` (string values).
    """
    encoding = "utf-8-sig"
    with path.open(newline="", encoding=encoding) as f:
        yield from _iter_mapped_rows(f)


def _iter_mapped_rows(f: TextIO) -> Iterator[Dict[str, Any]]:
    reader = csv.DictReader(f)
    if reader.fieldnames is None:
        raise ValueError("CSV has no header row")
    headers: List[str] = [h or "" for h in reader.fieldnames]

    if resolve_column(headers, APP_STORE_RATING_ALIASES) is None:
        raise ValueError(
            "App Store CSV: could not find a rating column. "
            f"Expected one of: {APP_STORE_RATING_ALIASES}",
        )
    if resolve_column(headers, APP_STORE_TEXT_ALIASES) is None:
        raise ValueError(
            "App Store CSV: could not find review text column. "
            f"Expected one of: {APP_STORE_TEXT_ALIASES}",
        )
    if resolve_column(headers, APP_STORE_DATE_ALIASES) is None:
        raise ValueError(
            "App Store CSV: could not find date column. "
            f"Expected one of: {APP_STORE_DATE_ALIASES}",
        )

    for row in reader:
        if not row:
            continue
        rating_raw = get_mapped_row(row, headers, APP_STORE_RATING_ALIASES)
        text_raw = get_mapped_row(row, headers, APP_STORE_TEXT_ALIASES)
        date_raw = get_mapped_row(row, headers, APP_STORE_DATE_ALIASES)
        yield {
            "rating_raw": rating_raw,
            "text_raw": text_raw if text_raw is not None else "",
            "date_raw": date_raw,
        }
