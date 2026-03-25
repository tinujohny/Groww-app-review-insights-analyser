from phase1.phase1_run import phase1_manifest_dict


def test_phase1_manifest_shape():
    m = phase1_manifest_dict()
    assert m["phase"] == 1
    assert "settings" in m
    assert m["settings"]["groq_api_key"] in ("set", "not_set")
    assert "normalized_review_example" in m
    assert m["normalized_review_example"]["text"]
    assert "phase3_language_filter" in m
    assert "phase3_emoji_filter" in m
    assert m["phase3_emoji_filter"]["drop_reviews_with_emojis"] is True
    assert "en" in m["settings"]["allowed_language_codes"]
