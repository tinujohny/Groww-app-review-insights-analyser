"""CLI: read Phase 2 filtered JSONL and run theme extraction (Groq with Gemini fallback)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from phase1.config import get_settings
from phase4.groq_theme_run import (
    run_review_assignment_with_fallback,
    run_theme_extraction_with_fallback,
    run_themes_merge_with_fallback,
)
from phase4.jsonl_reviews import load_review_dicts, reviews_to_corpus_chunks, reviews_to_corpus_text
from phase4.validation import validate_assignment_payload, validate_themes_payload


def _prepare_assignment_reviews(rows: List[Dict[str, Any]], max_reviews: int) -> List[Dict[str, str]]:
    out: List[Dict[str, str]] = []
    for r in rows:
        if len(out) >= max_reviews:
            break
        text = (r.get("text") or "").strip()
        if not text:
            continue
        rid = r.get("reviewIdInternal") or r.get("review_id_internal")
        if not rid:
            continue
        out.append({"review_id_internal": str(rid), "text": text, "rating": str(r.get("rating", ""))})
    return out


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Phase 4: send filtered reviews (Phase 2 JSONL, produced with Phase 1 settings + Phase 3 filters) "
            "to Groq using REVIEW_PULSE_GROQ_API_KEY; if Groq is exhausted, fallback to Gemini when configured."
        ),
    )
    parser.add_argument("--input", "-i", type=Path, required=True, help="Path to JSONL from review-pulse-collect or phase2 ingest")
    parser.add_argument("--out", "-o", type=Path, default=None, help="Write LLM JSON output (default: data/phase4/themes_<timestamp>.json)")
    parser.add_argument("--max-chars", type=int, default=80_000, help="Max corpus chars per Groq request")
    parser.add_argument("--max-reviews", type=int, default=500, help="Max review rows to include total")
    parser.add_argument("--max-retries", type=int, default=1, help="Schema retry count per LLM step")
    parser.add_argument("--chunked", action="store_true", help="Split reviews into multiple requests (each up to --max-chars); merge themes with a final LLM call")
    parser.add_argument("--no-merge", action="store_true", help="With --chunked: only run per-chunk theme extraction; skip merge")
    args = parser.parse_args(argv)

    get_settings.cache_clear()
    settings = get_settings()
    if not settings.groq_api_key:
        print("Error: set REVIEW_PULSE_GROQ_API_KEY in .env", file=sys.stderr)
        return 2

    rows = load_review_dicts(args.input)
    groq_key = settings.groq_api_key.get_secret_value()
    groq_model = settings.groq_model
    gemini_key = settings.gemini_api_key.get_secret_value() if settings.gemini_api_key else None
    gemini_model = settings.gemini_model

    out_path = args.out
    if out_path is None:
        from datetime import datetime, timezone

        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        out_path = Path(f"data/phase4/themes_{ts}.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    payload: Dict[str, Any] = {
        "input_review_count": len(rows),
        "primary_provider": "groq",
        "groq_model": groq_model,
        "gemini_fallback_configured": bool(gemini_key),
        "gemini_model": gemini_model,
        "mode": "chunked" if args.chunked else "single",
    }

    if args.chunked:
        chunks = reviews_to_corpus_chunks(rows, max_chars_per_chunk=args.max_chars, max_reviews=args.max_reviews)
        if not chunks:
            print("Error: no review text in input", file=sys.stderr)
            return 2
        batches: List[Dict[str, Any]] = []
        candidate_lists: List[Dict[str, Any]] = []
        for i, corpus in enumerate(chunks):
            parsed: Optional[Dict[str, Any]] = None
            provider = "groq"
            raw = ""
            for _attempt in range(args.max_retries + 1):
                raw, provider = run_theme_extraction_with_fallback(
                    corpus,
                    groq_api_key=groq_key,
                    groq_model=groq_model,
                    gemini_api_key=gemini_key,
                    gemini_model=gemini_model,
                )
                try:
                    parsed_obj = json.loads(raw)
                except json.JSONDecodeError:
                    parsed_obj = None
                parsed = validate_themes_payload(parsed_obj)
                if parsed:
                    break
            batches.append({"batch_index": i, "corpus_chars": len(corpus), "provider": provider, "raw_response": raw, "parsed": parsed})
            if parsed and isinstance(parsed.get("themes"), list):
                candidate_lists.append(parsed)

        payload["batches"] = batches
        payload["chunk_count"] = len(chunks)
        do_merge = not args.no_merge and len(candidate_lists) > 1
        if do_merge:
            merge_raw = ""
            merge_provider = "groq"
            merge_parsed: Optional[Dict[str, Any]] = None
            for _attempt in range(args.max_retries + 1):
                merge_raw, merge_provider = run_themes_merge_with_fallback(
                    candidate_lists,
                    groq_api_key=groq_key,
                    groq_model=groq_model,
                    gemini_api_key=gemini_key,
                    gemini_model=gemini_model,
                )
                try:
                    merge_obj = json.loads(merge_raw)
                except json.JSONDecodeError:
                    merge_obj = None
                merge_parsed = validate_themes_payload(merge_obj)
                if merge_parsed:
                    break
            payload["merge_provider"] = merge_provider
            payload["merge_raw_response"] = merge_raw
            payload["merge_parsed"] = merge_parsed
            payload["raw_response"] = merge_raw
            payload["parsed"] = payload.get("merge_parsed")
            payload["corpus_chars"] = sum(b["corpus_chars"] for b in batches)
        elif len(candidate_lists) == 1:
            p = candidate_lists[0]
            payload["raw_response"] = batches[0]["raw_response"]
            payload["parsed"] = p
            payload["corpus_chars"] = batches[0]["corpus_chars"]
        else:
            payload["raw_response"] = None
            payload["parsed"] = None
            payload["corpus_chars"] = sum(b["corpus_chars"] for b in batches)
    else:
        corpus = reviews_to_corpus_text(rows, max_chars=args.max_chars, max_reviews=args.max_reviews)
        if not corpus.strip():
            print("Error: no review text in input", file=sys.stderr)
            return 2
        raw = ""
        provider = "groq"
        parsed: Optional[Dict[str, Any]] = None
        for _attempt in range(args.max_retries + 1):
            raw, provider = run_theme_extraction_with_fallback(
                corpus,
                groq_api_key=groq_key,
                groq_model=groq_model,
                gemini_api_key=gemini_key,
                gemini_model=gemini_model,
            )
            try:
                parsed_obj = json.loads(raw)
            except json.JSONDecodeError:
                parsed_obj = None
            parsed = validate_themes_payload(parsed_obj)
            if parsed:
                break
        payload["corpus_chars"] = len(corpus)
        payload["provider"] = provider
        payload["raw_response"] = raw
        payload["parsed"] = parsed

    themes_payload = payload.get("parsed")
    if isinstance(themes_payload, dict) and themes_payload.get("themes"):
        assignment_reviews = _prepare_assignment_reviews(rows, args.max_reviews)
        if assignment_reviews:
            assign_raw = ""
            assign_provider = "groq"
            assign_parsed: Optional[Dict[str, Any]] = None
            for _attempt in range(args.max_retries + 1):
                assign_raw, assign_provider = run_review_assignment_with_fallback(
                    assignment_reviews,
                    themes_payload,
                    groq_api_key=groq_key,
                    groq_model=groq_model,
                    gemini_api_key=gemini_key,
                    gemini_model=gemini_model,
                )
                try:
                    assign_obj = json.loads(assign_raw)
                except json.JSONDecodeError:
                    assign_obj = None
                assign_parsed = validate_assignment_payload(assign_obj)
                if assign_parsed:
                    break
            payload["assignment_provider"] = assign_provider
            payload["assignment_raw_response"] = assign_raw
            payload["review_theme_map"] = (assign_parsed or {}).get("assignments", [])
            payload["themes"] = themes_payload.get("themes", [])
            if not payload["review_theme_map"]:
                raise RuntimeError(
                    "Phase 4 assignment produced an empty review_theme_map. Reduce --max-reviews or increase LLM response budget."
                )

    out_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {out_path.resolve()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
