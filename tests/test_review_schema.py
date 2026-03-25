import datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from phase1.schemas import NormalizedReview, ReviewSource

_BODY_5 = "one two three four five words here"


def test_normalized_review_valid():
    r = NormalizedReview(
        source=ReviewSource.GOOGLE_PLAY,
        rating=5,
        text=" Works well enough for five words total ",
        review_date=datetime.date(2026, 3, 1),
        week_bucket="2026-W09",
    )
    assert "five" in r.text


@pytest.mark.parametrize("bad", ["2026-W0", "2026-W54", "26-W09", "2026-09"])
def test_week_bucket_invalid(bad: str):
    with pytest.raises(ValidationError):
        NormalizedReview(
            source=ReviewSource.APP_STORE,
            rating=3,
            text=_BODY_5,
            review_date=datetime.date(2026, 3, 1),
            week_bucket=bad,
        )


def test_rating_bounds():
    with pytest.raises(ValidationError):
        NormalizedReview(
            source=ReviewSource.APP_STORE,
            rating=6,
            text=_BODY_5,
            review_date=datetime.date(2026, 3, 1),
            week_bucket="2026-W09",
        )


def test_text_too_few_words():
    with pytest.raises(ValidationError) as exc:
        NormalizedReview(
            source=ReviewSource.GOOGLE_PLAY,
            rating=5,
            text="only four words here",
            review_date=datetime.date(2026, 3, 1),
            week_bucket="2026-W09",
        )
    assert "at least" in str(exc.value).lower()


def test_min_words_respects_settings(monkeypatch):
    monkeypatch.setenv("REVIEW_PULSE_MIN_REVIEW_WORDS", "3")
    NormalizedReview(
        source=ReviewSource.APP_STORE,
        rating=4,
        text="just three words",
        review_date=datetime.date(2026, 3, 1),
        week_bucket="2026-W09",
    )


def test_review_raw_batch():
    from phase1.schemas.raw import ReviewRaw

    bid = uuid4()
    rr = ReviewRaw(
        source=ReviewSource.GOOGLE_PLAY,
        rating=2,
        text_raw="y",
        review_date=datetime.date(2026, 1, 1),
        ingested_at=datetime.datetime.now(datetime.timezone.utc),
        batch_id=bid,
    )
    assert rr.batch_id == bid
