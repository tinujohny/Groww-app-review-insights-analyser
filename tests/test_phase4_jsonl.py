"""Phase 4 helpers: JSONL load and corpus truncation."""

from __future__ import annotations

import json
from pathlib import Path

from phase4.jsonl_reviews import (
    load_review_dicts,
    reviews_to_corpus_chunks,
    reviews_to_corpus_text,
)


def test_load_review_dicts(tmp_path: Path) -> None:
    p = tmp_path / "r.jsonl"
    p.write_text(
        json.dumps({"text": "one two three four five", "rating": 5}) + "\n"
        + json.dumps({"text": "a b c d e", "rating": 4}) + "\n",
        encoding="utf-8",
    )
    rows = load_review_dicts(p)
    assert len(rows) == 2
    assert rows[0]["rating"] == 5


def test_reviews_to_corpus_text_max_chars() -> None:
    rows = [{"text": "x" * 100, "rating": 5} for _ in range(10)]
    out = reviews_to_corpus_text(rows, max_chars=250, max_reviews=10)
    assert len(out) <= 250 + 20  # bracket prefix per line


def test_reviews_to_corpus_chunks_splits() -> None:
    rows = [{"text": "word " * 20, "rating": 5} for _ in range(30)]
    chunks = reviews_to_corpus_chunks(rows, max_chars_per_chunk=120, max_reviews=100)
    assert len(chunks) >= 2
    assert all(len(c) <= 200 for c in chunks)  # loose bound; each chunk bounded
