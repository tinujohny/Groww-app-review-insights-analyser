"""Load ``NormalizedReview`` JSONL written by Phase 2 collection."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List


def load_review_dicts(path: Path | str) -> List[Dict[str, Any]]:
    """One JSON object per line (``NormalizedReview.model_dump`` shape)."""
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(str(p))
    out: List[Dict[str, Any]] = []
    with p.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            out.append(json.loads(line))
    return out


def reviews_to_corpus_text(
    rows: List[Dict[str, Any]],
    *,
    max_chars: int = 80_000,
    max_reviews: int = 500,
) -> str:
    """Concatenate review bodies for the LLM (rating + text), bounded by size."""
    parts: List[str] = []
    n = 0
    for i, r in enumerate(rows[:max_reviews]):
        text = (r.get("text") or "").strip()
        if not text:
            continue
        rating = r.get("rating", "")
        line = f"[{rating}/5] {text}\n"
        if n + len(line) > max_chars:
            break
        parts.append(line)
        n += len(line)
    return "".join(parts)


def reviews_to_corpus_chunks(
    rows: List[Dict[str, Any]],
    *,
    max_chars_per_chunk: int = 80_000,
    max_reviews: int = 500,
) -> List[str]:
    """Split reviews into several corpus strings for multiple LLM requests.

    Each chunk is at most ``max_chars_per_chunk`` (except a single huge review may
    exceed it alone). Stops after ``max_reviews`` non-empty reviews total.
    """
    chunks: List[str] = []
    parts: List[str] = []
    n = 0
    used = 0

    def flush() -> None:
        nonlocal parts, n
        if parts:
            chunks.append("".join(parts))
            parts = []
            n = 0

    for r in rows:
        if used >= max_reviews:
            break
        text = (r.get("text") or "").strip()
        if not text:
            continue
        used += 1
        rating = r.get("rating", "")
        line = f"[{rating}/5] {text}\n"
        if n > 0 and n + len(line) > max_chars_per_chunk:
            flush()
        parts.append(line)
        n += len(line)
        if n >= max_chars_per_chunk:
            flush()

    flush()
    return [c for c in chunks if c.strip()]
