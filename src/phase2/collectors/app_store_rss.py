"""Fetch recent reviews from Apple's public iTunes customer-reviews RSS (no App Store login)."""

from __future__ import annotations

import re
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional

ATOM_NS = "http://www.w3.org/2005/Atom"
IM_NS = "http://itunes.apple.com/rss"


def _ae(tag: str) -> str:
    return f"{{{ATOM_NS}}}{tag}"


def _ie(tag: str) -> str:
    return f"{{{IM_NS}}}{tag}"


def _strip_html(raw: str) -> str:
    text = re.sub(r"<[^>]+>", " ", raw)
    return " ".join(text.split())


def _entry_body(entry: ET.Element) -> str:
    text_plain = ""
    html_parts: List[str] = []
    for c in entry.findall(_ae("content")):
        ct = c.get("type") or ""
        if ct == "text":
            text_plain = (c.text or "").strip()
            if text_plain:
                return text_plain
        if ct == "html":
            raw = "".join(c.itertext()) if list(c.iter()) else (c.text or "")
            if raw:
                html_parts.append(raw)
    if html_parts:
        return _strip_html(" ".join(html_parts))
    return ""


def _parse_entry(entry: ET.Element) -> Optional[Dict[str, Any]]:
    eid_el = entry.find(_ae("id"))
    rid = (eid_el.text or "").strip() if eid_el is not None else ""

    updated_el = entry.find(_ae("updated"))
    updated = (updated_el.text or "").strip() if updated_el is not None else ""

    rating_el = entry.find(_ie("rating"))
    rating_s = (rating_el.text or "").strip() if rating_el is not None else ""
    try:
        rating = int(rating_s) if rating_s else None
    except ValueError:
        rating = None

    body = _entry_body(entry)
    if not body or rating is None or not updated:
        return None
    return {
        "source_format": "app_store_rss",
        "external_review_id": rid,
        "rating": rating,
        "text": body,
        "date_raw": updated,
    }


def next_rss_feed_url(root: ET.Element) -> Optional[str]:
    """Href of ``rel=next`` in the feed, if present."""
    for link in root.findall(_ae("link")):
        if (link.get("rel") or "") == "next":
            return link.get("href")
    return None


def parse_feed_xml(data: bytes) -> tuple[ET.Element, List[Dict[str, Any]]]:
    root = ET.fromstring(data)
    rows: List[Dict[str, Any]] = []
    for entry in root.findall(_ae("entry")):
        parsed = _parse_entry(entry)
        if parsed:
            rows.append(parsed)
    return root, rows


def fetch_app_store_rss_url(url: str) -> tuple[ET.Element, List[Dict[str, Any]]]:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "ReviewPulse/1.0 (+https://example.local)"},
    )
    with urllib.request.urlopen(req, timeout=90) as resp:
        data = resp.read()
    return parse_feed_xml(data)


def fetch_app_store_rss_pages(
    app_id: str,
    country: str = "us",
    max_pages: int = 1,
) -> List[Dict[str, Any]]:
    """
    Pull up to ``max_pages`` RSS pages (typically ~50 reviews per page, varies).

    RSS URL pattern is documented by Apple for public app review feeds.
    """
    out: List[Dict[str, Any]] = []
    cc = country.strip().lower()
    url: Optional[str] = (
        f"https://itunes.apple.com/{cc}/rss/customerreviews/id={app_id}/sortby=mostrecent/xml"
    )
    seen_urls: set[str] = set()

    while url and max_pages > 0:
        if url in seen_urls:
            break
        seen_urls.add(url)
        try:
            root, rows = fetch_app_store_rss_url(url)
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"App Store RSS HTTP {e.code} for {url}") from e
        except urllib.error.URLError as e:
            raise RuntimeError(f"App Store RSS fetch failed: {e}") from e
        out.extend(rows)
        max_pages -= 1
        if max_pages <= 0:
            break
        url = next_rss_feed_url(root)

    return out
