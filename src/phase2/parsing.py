"""Parse rating and body text from raw CSV cell values."""

from __future__ import annotations

import re
from typing import Optional


def parse_star_rating(value: Optional[str]) -> Optional[int]:
    """Parse 1–5 star rating from export cell (integer or decimal string)."""
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    try:
        r = float(s.replace(",", "."))
    except ValueError:
        m = re.search(r"(\d+(?:\.\d+)?)", s)
        if not m:
            return None
        r = float(m.group(1))
    rounded = int(round(r))
    if 1 <= rounded <= 5:
        return rounded
    return None


def parse_body_text(value: Optional[str]) -> str:
    """Normalize review body; empty if missing."""
    if value is None:
        return ""
    return str(value).strip()
