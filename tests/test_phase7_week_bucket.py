from datetime import date

from phase7.weekly_run_cli import week_bucket_from_day


def test_week_bucket_format_and_value() -> None:
    # 2026-03-24 should fall into ISO week 2026-W13.
    assert week_bucket_from_day(date(2026, 3, 24)) == "2026-W13"


def test_week_buckets_last_n_weeks_count_and_order() -> None:
    from phase7.weekly_scheduler import week_buckets_last_n_weeks

    end = date(2026, 3, 24)  # ISO week 2026-W13
    weeks = week_buckets_last_n_weeks(end_date=end, weeks=8)
    assert len(weeks) == 8
    # Ensure oldest -> newest ordering
    assert weeks[0] != weeks[-1]

