"""Fee explanation scenario helpers for Phase 6 mail enrichment."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List


def parse_source_links(raw_links: str) -> List[str]:
    return [x.strip() for x in (raw_links or "").split(",") if x.strip()]


def build_fee_explanation(*, scenario: str, source_links: List[str]) -> Dict[str, object]:
    """Return canonical fee scenario payload used in mail/report append."""
    bullets = [
        "Exit load is a fee charged when units are redeemed before the scheme's specified holding period.",
        "The exact percentage and holding window vary by fund and are disclosed in scheme documents.",
        "Always check current scheme terms before redeeming to avoid unexpected deduction on proceeds.",
    ]
    return {
        "fee_scenario": scenario,
        "explanation_bullets": bullets,
        "source_links": source_links,
        "last_checked": datetime.now(timezone.utc).date().isoformat(),
    }

