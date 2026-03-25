"""LLM theme generation helpers (Groq primary, Gemini fallback)."""

from __future__ import annotations

from typing import Optional, Tuple

THEME_SYSTEM = """You are a product analyst. Output only valid JSON, no markdown fences."""

THEME_USER_TEMPLATE = """Below are public app review snippets (rating and text). They are already filtered for language, emoji, and minimum length.

Propose between 3 and 5 distinct themes users talk about. For each theme return JSON objects with:
- "name": short snake_case identifier
- "description": one sentence
- "example_quote": a short verbatim substring from the corpus below (must appear exactly in the text)

Return exactly this JSON shape:
{{"themes":[{{"name":"...","description":"...","example_quote":"..."}},...]}}

Reviews:
---
{corpus}
---
"""


def run_theme_extraction(
    corpus_text: str,
    api_key: str,
    model: str,
) -> str:
    """Return raw model message content (expected JSON string)."""
    from groq import Groq  # noqa: PLC0415

    client = Groq(api_key=api_key)
    user = THEME_USER_TEMPLATE.format(corpus=corpus_text)
    chat = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": THEME_SYSTEM},
            {"role": "user", "content": user},
        ],
        temperature=0.3,
        max_tokens=2048,
    )
    choice = chat.choices[0].message.content
    if not choice:
        raise RuntimeError("Groq returned empty content")
    return choice.strip()


def _run_theme_extraction_gemini(
    corpus_text: str,
    api_key: str,
    model: str,
) -> str:
    import google.generativeai as genai  # noqa: PLC0415

    genai.configure(api_key=api_key)
    m = genai.GenerativeModel(model_name=model, system_instruction=THEME_SYSTEM)
    user = THEME_USER_TEMPLATE.format(corpus=corpus_text)
    resp = m.generate_content(user)
    txt = (resp.text or "").strip()
    if not txt:
        raise RuntimeError("Gemini returned empty content")
    return txt


MERGE_SYSTEM = """You are a product analyst. Output only valid JSON, no markdown fences."""

MERGE_USER_TEMPLATE = """Several batches of candidate themes were extracted from disjoint subsets of the same app's reviews (same week). Merge them into one list of 3 to 5 canonical themes.

Rules:
- Remove duplicate or overlapping themes; keep the clearest name and description.
- Prefer preserving distinct user intents if they are genuinely different.
- Each "example_quote" must be copied verbatim from the candidate themes below (do not invent quotes).

Return exactly this JSON shape:
{{"themes":[{{"name":"...","description":"...","example_quote":"..."}},...]}}

Candidate theme batches (JSON):
---
{candidates_json}
---
"""

ASSIGN_SYSTEM = """You are a product analyst. Output only valid JSON, no markdown fences."""

ASSIGN_USER_TEMPLATE = """Assign each review to exactly one theme with confidence between 0 and 1.

Allowed themes:
{themes_json}

Return exactly this JSON shape:
{{"assignments":[{{"review_id_internal":"...","theme_name":"...","confidence":0.0}}]}}

Rules:
- theme_name must exactly match one of the allowed theme names.
- Include every review id exactly once.
- confidence must be numeric in [0,1].

Reviews:
{reviews_json}
"""


def run_themes_merge(
    candidate_theme_lists: list[dict],
    api_key: str,
    model: str,
) -> str:
    """Merge theme lists from chunked extractions into one JSON string."""
    import json as _json

    from groq import Groq  # noqa: PLC0415

    client = Groq(api_key=api_key)
    user = MERGE_USER_TEMPLATE.format(candidates_json=_json.dumps(candidate_theme_lists, indent=2))
    chat = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": MERGE_SYSTEM},
            {"role": "user", "content": user},
        ],
        temperature=0.2,
        max_tokens=2048,
    )
    choice = chat.choices[0].message.content
    if not choice:
        raise RuntimeError("Groq returned empty content")
    return choice.strip()


def run_review_assignment(
    reviews_payload: list[dict],
    themes_payload: dict,
    api_key: str,
    model: str,
) -> str:
    """Assign each review to a theme with confidence."""
    import json as _json

    from groq import Groq  # noqa: PLC0415

    client = Groq(api_key=api_key)
    user = ASSIGN_USER_TEMPLATE.format(
        themes_json=_json.dumps(themes_payload, indent=2),
        reviews_json=_json.dumps(reviews_payload, indent=2),
    )
    chat = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": ASSIGN_SYSTEM},
            {"role": "user", "content": user},
        ],
        temperature=0.2,
        # Prompt C includes one assignment per review; for 100-150 reviews the
        # resulting JSON can be >4096 tokens. If truncated, schema validation
        # fails and downstream themes/quotes become empty.
        max_tokens=12000,
    )
    choice = chat.choices[0].message.content
    if not choice:
        raise RuntimeError("Groq returned empty content")
    return choice.strip()


def _run_themes_merge_gemini(
    candidate_theme_lists: list[dict],
    api_key: str,
    model: str,
) -> str:
    import json as _json

    import google.generativeai as genai  # noqa: PLC0415

    genai.configure(api_key=api_key)
    m = genai.GenerativeModel(model_name=model, system_instruction=MERGE_SYSTEM)
    user = MERGE_USER_TEMPLATE.format(candidates_json=_json.dumps(candidate_theme_lists, indent=2))
    resp = m.generate_content(user)
    txt = (resp.text or "").strip()
    if not txt:
        raise RuntimeError("Gemini returned empty content")
    return txt


def _run_review_assignment_gemini(
    reviews_payload: list[dict],
    themes_payload: dict,
    api_key: str,
    model: str,
) -> str:
    import json as _json

    import google.generativeai as genai  # noqa: PLC0415

    genai.configure(api_key=api_key)
    m = genai.GenerativeModel(model_name=model, system_instruction=ASSIGN_SYSTEM)
    user = ASSIGN_USER_TEMPLATE.format(
        themes_json=_json.dumps(themes_payload, indent=2),
        reviews_json=_json.dumps(reviews_payload, indent=2),
    )
    resp = m.generate_content(user)
    txt = (resp.text or "").strip()
    if not txt:
        raise RuntimeError("Gemini returned empty content")
    return txt


def is_groq_exhausted_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    markers = (
        "rate limit",
        "quota",
        "exhaust",
        "429",
        "too many requests",
        "credit",
        "insufficient balance",
        # Treat common connectivity/proxy failures as "Groq not usable" so we can
        # fall back to Gemini in constrained/offline environments.
        "403 forbidden",
        "forbidden",
        "proxyerror",
        "proxy",
        "connection error",
        "apiconnectionerror",
        "timed out",
    )
    return any(m in msg for m in markers)


def run_theme_extraction_with_fallback(
    corpus_text: str,
    *,
    groq_api_key: str,
    groq_model: str,
    gemini_api_key: Optional[str],
    gemini_model: str,
) -> Tuple[str, str]:
    """Return ``(raw_response, provider)``; fallback to Gemini on Groq quota/rate exhaustion."""
    try:
        return run_theme_extraction(corpus_text, api_key=groq_api_key, model=groq_model), "groq"
    except Exception as exc:  # noqa: BLE001
        if not gemini_api_key or not is_groq_exhausted_error(exc):
            raise
        raw = _run_theme_extraction_gemini(corpus_text, api_key=gemini_api_key, model=gemini_model)
        return raw, "gemini"


def run_themes_merge_with_fallback(
    candidate_theme_lists: list[dict],
    *,
    groq_api_key: str,
    groq_model: str,
    gemini_api_key: Optional[str],
    gemini_model: str,
) -> Tuple[str, str]:
    """Return ``(raw_response, provider)``; fallback to Gemini on Groq quota/rate exhaustion."""
    try:
        return run_themes_merge(candidate_theme_lists, api_key=groq_api_key, model=groq_model), "groq"
    except Exception as exc:  # noqa: BLE001
        if not gemini_api_key or not is_groq_exhausted_error(exc):
            raise
        raw = _run_themes_merge_gemini(
            candidate_theme_lists,
            api_key=gemini_api_key,
            model=gemini_model,
        )
        return raw, "gemini"


def run_review_assignment_with_fallback(
    reviews_payload: list[dict],
    themes_payload: dict,
    *,
    groq_api_key: str,
    groq_model: str,
    gemini_api_key: Optional[str],
    gemini_model: str,
) -> Tuple[str, str]:
    """Return ``(raw_response, provider)`` for Prompt C assignment."""
    try:
        return (
            run_review_assignment(
                reviews_payload,
                themes_payload,
                api_key=groq_api_key,
                model=groq_model,
            ),
            "groq",
        )
    except Exception as exc:  # noqa: BLE001
        if not gemini_api_key or not is_groq_exhausted_error(exc):
            raise
        raw = _run_review_assignment_gemini(
            reviews_payload,
            themes_payload,
            api_key=gemini_api_key,
            model=gemini_model,
        )
        return raw, "gemini"
