"""Phase 5 weekly pulse generation tests."""

from phase5.compose import build_weekly_pulse


def test_build_weekly_pulse_shape_and_policy():
    phase2_rows = [
        {
            "reviewIdInternal": "r1",
            "text": "App performance improved and feels fast now",
            "weekBucket": "2026-W12",
            "rating": 5,
        },
        {
            "reviewIdInternal": "r2",
            "text": "Payment keeps failing on checkout for me",
            "weekBucket": "2026-W12",
            "rating": 1,
        },
        {
            "reviewIdInternal": "r3",
            "text": "Support team replied quickly and resolved issue",
            "weekBucket": "2026-W12",
            "rating": 4,
        },
    ]
    phase4_payload = {
        "themes": [
            {"name": "app_performance", "description": "Performance", "example_quote": "feels fast"},
            {"name": "payment_failures", "description": "Payments", "example_quote": "Payment keeps failing"},
            {"name": "support_experience", "description": "Support", "example_quote": "replied quickly"},
        ],
        "review_theme_map": [
            {"review_id_internal": "r1", "theme_name": "app_performance", "confidence": 0.9},
            {"review_id_internal": "r2", "theme_name": "payment_failures", "confidence": 0.8},
            {"review_id_internal": "r3", "theme_name": "support_experience", "confidence": 0.7},
        ],
    }
    out = build_weekly_pulse(phase4_payload, phase2_rows)
    assert out["week"] == "2026-W12"
    assert len(out["topThemes"]) == 3
    assert len(out["quotes"]) == 3
    assert len(out["actionIdeas"]) == 3
    assert out["policy"]["word_count_ok"] is True
    assert out["policy"]["unique_quotes_ok"] is True
    assert out["policy"]["quote_source_map_ok"] is True
