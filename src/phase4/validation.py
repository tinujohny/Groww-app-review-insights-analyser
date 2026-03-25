"""Schema validation helpers for Phase 4 LLM JSON outputs."""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def validate_themes_payload(obj: Any) -> Optional[Dict[str, Any]]:
    """Return normalized themes payload when valid, else None."""
    if not isinstance(obj, dict):
        return None
    themes = obj.get("themes")
    if not isinstance(themes, list):
        return None
    if not (3 <= len(themes) <= 5):
        return None
    out: List[Dict[str, str]] = []
    for t in themes:
        if not isinstance(t, dict):
            return None
        name = t.get("name")
        desc = t.get("description")
        quote = t.get("example_quote")
        if not all(isinstance(x, str) and x.strip() for x in (name, desc, quote)):
            return None
        out.append(
            {
                "name": name.strip(),
                "description": desc.strip(),
                "example_quote": quote.strip(),
            }
        )
    return {"themes": out}


def validate_assignment_payload(obj: Any) -> Optional[Dict[str, Any]]:
    """Return normalized assignment payload when valid, else None."""
    if not isinstance(obj, dict):
        return None
    items = obj.get("assignments")
    if not isinstance(items, list) or not items:
        return None
    out: List[Dict[str, Any]] = []
    for a in items:
        if not isinstance(a, dict):
            return None
        rid = a.get("review_id_internal")
        theme = a.get("theme_name")
        conf = a.get("confidence")
        if not isinstance(rid, str) or not rid.strip():
            return None
        if not isinstance(theme, str) or not theme.strip():
            return None
        try:
            c = float(conf)
        except (TypeError, ValueError):
            return None
        if c < 0.0 or c > 1.0:
            return None
        out.append(
            {
                "review_id_internal": rid.strip(),
                "theme_name": theme.strip(),
                "confidence": round(c, 4),
            }
        )
    return {"assignments": out}
