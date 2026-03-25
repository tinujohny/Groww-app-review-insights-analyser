"""Phase 4 schema validation tests."""

from phase4.validation import validate_assignment_payload, validate_themes_payload


def test_validate_themes_payload_ok():
    obj = {
        "themes": [
            {"name": "a", "description": "d1", "example_quote": "q1"},
            {"name": "b", "description": "d2", "example_quote": "q2"},
            {"name": "c", "description": "d3", "example_quote": "q3"},
        ]
    }
    out = validate_themes_payload(obj)
    assert out is not None
    assert len(out["themes"]) == 3


def test_validate_themes_payload_rejects_count():
    obj = {"themes": [{"name": "a", "description": "d", "example_quote": "q"}]}
    assert validate_themes_payload(obj) is None


def test_validate_assignment_payload_ok():
    obj = {
        "assignments": [
            {"review_id_internal": "r1", "theme_name": "a", "confidence": 0.9},
            {"review_id_internal": "r2", "theme_name": "b", "confidence": 0.2},
        ]
    }
    out = validate_assignment_payload(obj)
    assert out is not None
    assert out["assignments"][0]["confidence"] == 0.9


def test_validate_assignment_payload_rejects_confidence():
    obj = {"assignments": [{"review_id_internal": "r1", "theme_name": "a", "confidence": 1.5}]}
    assert validate_assignment_payload(obj) is None
