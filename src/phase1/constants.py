"""Operational constants referenced across phases."""

# Many storefront review export UIs return at most ~500 rows per file. When your source
# supports more (e.g. ~5000), raise REVIEW_PULSE_MAX_REVIEWS_PER_EXPORT accordingly.
TYPICAL_SINGLE_EXPORT_ROW_LIMIT = 500

# Reviews with fewer words than this are treated as noise and dropped (body text only; titles are not used).
MIN_REVIEW_WORDS = 5
