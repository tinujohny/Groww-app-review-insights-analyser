"""Phase 5 weekly insight generation from Phase 4 themes + assignments."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

from phase1.text_utils import count_words


def _review_id(row: Dict[str, Any]) -> str:
    return str(row.get("reviewIdInternal") or row.get("review_id_internal") or "")


def _week_bucket(rows: List[Dict[str, Any]]) -> str:
    for r in rows:
        w = r.get("weekBucket") or r.get("week_bucket")
        if isinstance(w, str) and w.strip():
            return w
    return datetime.now(timezone.utc).strftime("%Y-W%V")


def _top_three_themes(review_theme_map: List[Dict[str, Any]]) -> List[Tuple[str, int]]:
    c = Counter(str(x.get("theme_name") or "") for x in review_theme_map if x.get("theme_name"))
    return [(k, v) for k, v in c.most_common(3)]


def _pick_quotes(
    review_theme_map: List[Dict[str, Any]],
    reviews_by_id: Dict[str, Dict[str, Any]],
    top_themes: List[Tuple[str, int]],
) -> List[Dict[str, str]]:
    by_theme: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for x in review_theme_map:
        by_theme[str(x.get("theme_name") or "")].append(x)

    out: List[Dict[str, str]] = []
    seen_text: set[str] = set()
    for theme, _n in top_themes:
        candidates = sorted(
            by_theme.get(theme, []),
            key=lambda a: float(a.get("confidence") or 0.0),
            reverse=True,
        )
        for a in candidates:
            rid = str(a.get("review_id_internal") or "")
            row = reviews_by_id.get(rid)
            if not row:
                continue
            txt = str(row.get("text") or "").strip()
            if not txt or txt in seen_text:
                continue
            seen_text.add(txt)
            out.append({"review_id_internal": rid, "theme_name": theme, "quote": txt})
            break
    return out[:3]


def _actions(top_themes: List[Tuple[str, int]]) -> List[Dict[str, str]]:
    # Keep actions specific and testable while still deterministic.
    templates = [
        ("Add instrumentation and an A/B test focused on '{theme}' to reduce complaint volume by next sprint.", "M", "H"),
        ("Ship one UX/content fix for '{theme}' and monitor week-over-week rating delta.", "S", "M"),
        ("Create a support playbook update for '{theme}' and track resolution-time impact.", "S", "M"),
    ]
    out: List[Dict[str, str]] = []
    for i, (theme, _n) in enumerate(top_themes[:3]):
        t, effort, impact = templates[min(i, len(templates) - 1)]
        out.append({"theme_name": theme, "idea": t.format(theme=theme), "effort": effort, "impact": impact})
    return out


def _compose_note(top_themes: List[Tuple[str, int]], quotes: List[Dict[str, str]], actions: List[Dict[str, str]]) -> str:
    lines: List[str] = []
    lines.append("Top themes:")
    for t, n in top_themes:
        lines.append(f"- {t} ({n} reviews)")
    lines.append("Quotes:")
    for q in quotes:
        lines.append(f"- \"{q['quote']}\"")
    lines.append("Action ideas:")
    for a in actions:
        lines.append(f"- [{a['effort']}/{a['impact']}] {a['idea']}")
    note = "\n".join(lines)

    # Word-count guardrail <=250 words.
    if count_words(note) > 250:
        # Trim quotes first (they are often long), then fallback to first 250 words.
        short_lines = []
        for ln in lines:
            if ln.startswith('- "') and count_words(ln) > 20:
                words = ln.split()
                ln = " ".join(words[:20]) + "...\""
            short_lines.append(ln)
        note = "\n".join(short_lines)
        if count_words(note) > 250:
            note = " ".join(note.split()[:250])
    return note


def build_weekly_pulse(
    phase4_payload: Dict[str, Any],
    phase2_rows: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Build Phase 5 weekly pulse output with quality gates."""
    themes = phase4_payload.get("themes") or []
    review_theme_map = phase4_payload.get("review_theme_map") or []
    top_themes = _top_three_themes(review_theme_map)
    reviews_by_id = {_review_id(r): r for r in phase2_rows if _review_id(r)}
    quotes = _pick_quotes(review_theme_map, reviews_by_id, top_themes)
    actions = _actions(top_themes)
    note = _compose_note(top_themes, quotes, actions)

    # Hallucination check: every quote must map back to a source review id and exact text.
    quote_map_ok = all(q["review_id_internal"] in reviews_by_id and q["quote"] == str(reviews_by_id[q["review_id_internal"]].get("text") or "").strip() for q in quotes)
    unique_quotes = len({q["quote"] for q in quotes}) == len(quotes)

    return {
        "week": _week_bucket(phase2_rows),
        "topThemes": [{"name": t, "reviewCount": n} for t, n in top_themes],
        "quotes": quotes,
        "actionIdeas": actions,
        "wordCount": count_words(note),
        "noteText": note,
        "policy": {
            "word_count_ok": count_words(note) <= 250,
            "unique_quotes_ok": unique_quotes,
            "quote_source_map_ok": quote_map_ok,
            "max_themes_ok": len(themes) <= 5,
        },
    }
