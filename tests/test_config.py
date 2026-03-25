from phase1.config import AppSettings
from phase1.schemas.enums import Environment


def test_default_max_reviews_per_export_is_500(monkeypatch):
    monkeypatch.delenv("REVIEW_PULSE_MAX_REVIEWS_PER_EXPORT", raising=False)
    s = AppSettings(_env_file=None)
    assert s.max_reviews_per_export == 500


def test_max_reviews_override(monkeypatch):
    monkeypatch.setenv("REVIEW_PULSE_MAX_REVIEWS_PER_EXPORT", "5000")
    s = AppSettings(_env_file=None)
    assert s.max_reviews_per_export == 5000


def test_environment(monkeypatch):
    monkeypatch.setenv("REVIEW_PULSE_ENVIRONMENT", "staging")
    s = AppSettings(_env_file=None)
    assert s.environment == Environment.STAGING


def test_min_review_words_default(monkeypatch):
    monkeypatch.delenv("REVIEW_PULSE_MIN_REVIEW_WORDS", raising=False)
    s = AppSettings(_env_file=None)
    assert s.min_review_words == 5


def test_review_languages_default(monkeypatch):
    monkeypatch.delenv("REVIEW_PULSE_REVIEW_LANGUAGES", raising=False)
    s = AppSettings(_env_file=None)
    assert s.review_languages == "en"


def test_drop_reviews_with_emojis_default(monkeypatch):
    monkeypatch.delenv("REVIEW_PULSE_DROP_REVIEWS_WITH_EMOJIS", raising=False)
    s = AppSettings(_env_file=None)
    assert s.drop_reviews_with_emojis is True
