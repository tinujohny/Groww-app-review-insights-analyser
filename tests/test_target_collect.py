from phase1.config import AppSettings
from phase2.collectors.target_collect import effective_target_count


def test_effective_target_respects_max_export(monkeypatch):
    monkeypatch.setenv("REVIEW_PULSE_MAX_REVIEWS_PER_EXPORT", "500")
    s = AppSettings(_env_file=None)
    assert effective_target_count(s, None) == 500
    assert effective_target_count(s, 800) == 500
    assert effective_target_count(s, 100) == 100


def test_effective_target_default_from_settings(monkeypatch):
    monkeypatch.setenv("REVIEW_PULSE_MAX_REVIEWS_PER_EXPORT", "5000")
    s = AppSettings(_env_file=None)
    assert effective_target_count(s, None) == 5000
