import datetime

from phase1.schemas import NormalizedReview, ReviewSource
from phase3.emoji_filter import (
    filter_reviews_without_emojis,
    text_contains_emoji,
)

_BODY_OK = (
    "This review has enough words in English and absolutely no pictographs at all "
    "so it should pass both word count and emoji checks in the test suite."
)
_BODY_EMOJI = _BODY_OK + " 😀"


def test_text_contains_emoji():
    assert not text_contains_emoji("plain ascii words only here enough")
    assert text_contains_emoji("smile 😀 here with more words added for length")


def test_filter_reviews_without_emojis():
    r_ok = NormalizedReview(
        source=ReviewSource.APP_STORE,
        rating=5,
        text=_BODY_OK,
        review_date=datetime.date(2026, 3, 22),
        week_bucket="2026-W12",
    )
    r_bad = NormalizedReview(
        source=ReviewSource.APP_STORE,
        rating=4,
        text=_BODY_EMOJI,
        review_date=datetime.date(2026, 3, 22),
        week_bucket="2026-W12",
    )
    kept = filter_reviews_without_emojis([r_ok, r_bad], drop_if_contains_emoji=True)
    assert len(kept) == 1
    assert kept[0].text == _BODY_OK


def test_filter_reviews_without_emojis_disabled():
    r_bad = NormalizedReview(
        source=ReviewSource.APP_STORE,
        rating=4,
        text=_BODY_EMOJI,
        review_date=datetime.date(2026, 3, 22),
        week_bucket="2026-W12",
    )
    kept = filter_reviews_without_emojis([r_bad], drop_if_contains_emoji=False)
    assert len(kept) == 1
