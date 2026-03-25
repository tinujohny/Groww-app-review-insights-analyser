"""Language filter: deterministic seed for langdetect in tests."""

import datetime

import pytest
from langdetect import DetectorFactory

from phase1.schemas import NormalizedReview, ReviewSource
from phase3.language_filter import (
    filter_reviews_by_language,
    parse_allowed_language_codes,
    text_allowed_for_languages,
)


@pytest.fixture(autouse=True)
def langdetect_seed():
    DetectorFactory.seed = 0
    yield


_EN = (
    "This is a longer English language app store review that has enough words "
    "for reliable language detection in our test suite without ambiguity."
)
_FR = (
    "Ceci est un commentaire plus long en français dans le magasin dapplications "
    "avec suffisamment de mots pour la détection fiable de la langue en test."
)


def test_parse_allowed_language_codes():
    assert parse_allowed_language_codes("en") == frozenset({"en"})
    assert parse_allowed_language_codes("en, fr") == frozenset({"en", "fr"})


def test_english_kept_french_dropped_when_en_only():
    allowed = frozenset({"en"})
    assert text_allowed_for_languages(_EN, allowed, strict_on_detection_failure=False)
    assert not text_allowed_for_languages(_FR, allowed, strict_on_detection_failure=False)


def test_filter_reviews_by_language():
    r_en = NormalizedReview(
        source=ReviewSource.APP_STORE,
        rating=5,
        text=_EN,
        review_date=datetime.date(2026, 3, 22),
        week_bucket="2026-W12",
    )
    r_fr = NormalizedReview(
        source=ReviewSource.APP_STORE,
        rating=4,
        text=_FR,
        review_date=datetime.date(2026, 3, 22),
        week_bucket="2026-W12",
    )
    kept = filter_reviews_by_language(
        [r_en, r_fr],
        frozenset({"en"}),
        strict_on_detection_failure=False,
    )
    assert len(kept) == 1
    assert kept[0].text == _EN
