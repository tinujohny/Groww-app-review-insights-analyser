from phase1.text_utils import count_words, filter_by_min_words, has_min_words


def test_count_words():
    assert count_words("  a  b  c  ") == 3
    assert count_words("") == 0


def test_has_min_words():
    assert has_min_words("one two three four five", min_words=5)
    assert not has_min_words("one two three four", min_words=5)


def test_filter_by_min_words():
    rows = [
        {"id": 1, "t": "one two three four five"},
        {"id": 2, "t": "short"},
    ]
    kept = filter_by_min_words(rows, lambda r: r["t"], min_words=5)
    assert [r["id"] for r in kept] == [1]
