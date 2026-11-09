#!/usr/bin/env python3
"""Refresh a large source-linked, multi-decade US macro news RELEASE calendar.

Official BLS archived release links have the release date in their filename.
Official FOMC policy statement URLs have the announcement date in the filename.
No scheduled-only dates, inferred monthly dates, or news headline duplicates.

The collection is a *calendar*, not historical market-surprise training labels.
Transient upstream network failure retains previous verified events.
"""
from __future__ import annotations

import argparse
import json
import re
import time
from collections import Counter
from datetime import date, datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from history import read_json
from collect_alfred import RELEASES as ALFRED_RELEASES, ROOT as ALFRED_ROOT, parse_alfred_dates

CURATED = Path("tw-stock-dashboard/news-impact/official_events.json")
OUTPUT = Path("tw-stock-dashboard/news-impact/official_events_expanded.json")
BLS_ROOT = "https://www.bls.gov/bls/news-release/"
FED_CALENDAR = "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm"
FED_HISTORICAL = "https://www.federalreserve.gov/monetarypolicy/fomchistorical{}.htm"
# Collection breadth is source-defined. Each category is a separately dated
# statistical release with its own economic transmission channel.
BLS_SERIES = {
    "cpi": ("CPI", "消費者物價指數", "08:30"),
    "empsit": ("非農就業NFP", "就業情勢與非農薪資", "08:30"),
    "ppi": ("PPI", "生產者物價指數", "08:30"),
    "jolts": ("JOLTS", "職缺與勞動流動", "10:00"),
    "eci": ("ECI", "僱用成本指數", "08:30"),
    "prod": ("生產力", "勞動生產力與單位勞動成本", "08:30"),
    "ximpim": ("進出口物價", "美國進出口物價指數", "08:30"),
}
BLS_FILENAME_KEYS = {
    "cpi": "cpi", "empsit": "empsit", "ppi": "ppi", "jolts": "jolts",
    "eci": "eci", "prod": "prod2", "ximpim": "ximpim",
}
# Content URLs encode actual publication date as MMDDYYYY in BLS archives,
# in contrast with descriptions naming a reference month.
BLS_DATE_RE = re.compile(
    r"/news\.release/(?:archives|history)/([a-z0-9]+)_(\d{8})\.(htm|html|pdf|txt)$", re.I
)
FED_DATE_RE = re.compile(
    r"(?:monetary|fomcstatement_)(\d{8})a?\.htm$", re.I
)
FETCH_TIMEOUT = 18
USER_AGENT = "MarketEventResearch/1.1 (+https://github.com/jacky-168168/Tradingview-testing; public government archival index)"


class LinkParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links = []
        self._href = None
        self._parts = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self._href = dict(attrs).get("href")
            self._parts = []

    def handle_data(self, value):
        if self._href is not None:
            self._parts.append(value)

    def handle_endtag(self, tag):
        if tag == "a" and self._href is not None:
            self.links.append((self._href, "".join(self._parts).strip()))
            self._href = None
            self._parts = []


def valid_release_date(value, now):
    try:
        d = date.fromisoformat(value)
    except ValueError:
        return False
    # Ignore future hyperlinks, non-events, and obviously corrupt years.
    return date(1940, 1, 1) <= d <= now.date()


def parse_bls_index(html, series, now):
    if series not in BLS_SERIES:
        raise ValueError(f"unknown BLS archive series {series}")
    category, label, local_time = BLS_SERIES[series]
    parser = LinkParser()
    parser.feed(html)
    records = {}
    code = BLS_FILENAME_KEYS[series]
    for href, _anchor_text in parser.links:
        url = urljoin(BLS_ROOT, href)
        if urlparse(url).hostname != "www.bls.gov":
            continue
        match = BLS_DATE_RE.search(urlparse(url).path)
        if not match or match.group(1).lower() != code:
            continue
        stamp = match.group(2)
        try:
            released = datetime.strptime(stamp, "%m%d%Y").date().isoformat()
        except ValueError:
            continue
        if not valid_release_date(released, now):
            continue
        # HTML text releases are more accessible; do not duplicate its PDF.
        extension = match.group(3).lower()
        rank = {"htm": 3, "html": 3, "txt": 2, "pdf": 1}[extension]
        if released in records and records[released]["rank"] >= rank:
            continue
        records[released] = {"rank": rank, "event": {
            "id": f"bls-{series}-{released}",
            "category": category,
            "subtype": "官方經濟數據公布",
            "date": released,
            "timezone": "America/New_York",
            "localTime": local_time,
            "timeAccuracy": "scheduled_typical_time_not_individually_verified",
            "title": f"美國 {label} 官方公布",
            "source": "U.S. Bureau of Labor Statistics",
            "sourceUrl": url,
            "evidence": "Archived release URL filename encodes actual release date; release-time field is the usual schedule, not individually verified.",
            "directionKnown": False,
            "dataReferencePeriodNotReleaseDate": True,
        }}
    return [row["event"] for _, row in sorted(records.items())]


def parse_fomc_statements(html, now, parent_url=FED_CALENDAR):
    parser = LinkParser()
    parser.feed(html)
    records = {}
    for href, label in parser.links:
        url = urljoin(parent_url, href)
        if urlparse(url).hostname not in ("www.federalreserve.gov", "federalreserve.gov"):
            continue
        match = FED_DATE_RE.search(urlparse(url).path)
        if not match:
            continue
        if not ("statement" in label.lower() or
                re.search(r"/newsevents/pressreleases/monetary\d{8}a\.htm$", urlparse(url).path, re.I)):
            continue
        try:
            released = datetime.strptime(match.group(1), "%Y%m%d").date().isoformat()
        except ValueError:
            continue
        if not valid_release_date(released, now):
            continue
        records[released] = {
            "id": f"fomc-statement-{released}",
            "category": "FOMC",
            "subtype": "政策聲明（升降息未分類）",
            "date": released,
            "timezone": "America/New_York",
            "localTime": None,
            "timeAccuracy": "date_only_release_link",
            "title": "FOMC 政策聲明公告（含維持利率的會議）",
            "source": "Federal Reserve",
            "sourceUrl": url,
            "evidence": "Federal Reserve original FOMC statement link; first release time not individually confirmed.",
            "directionKnown": False,
        }
    return [records[d] for d in sorted(records)]


def merge_events(curated, recovered, fetched):
    """Deduplicate one release per category/date, prefer original source links.

    FOMC curated hike/cut metadata may be kept if a real policy statement is
    found for the same decision date, preserving subtype and bps as annotation.
    Never merge different categories occurring on the same date.
    """
    store = {}
    for origin, events in (("curated", curated), ("previous_verified", recovered), ("fresh_archive", fetched)):
        for event in events:
            if not isinstance(event, dict):
                continue
            category = event.get("category")
            stamp = event.get("date")
            if not category or not stamp or not str(event.get("sourceUrl", "")).startswith("https://"):
                continue
            try:
                date.fromisoformat(stamp)
            except (TypeError, ValueError):
                continue
            key = (category, stamp)
            if key not in store:
                store[key] = dict(event)
                store[key]["catalogOrigin"] = origin
                continue
            current = store[key]
            if origin == "fresh_archive":
                # Preserve known/manual rate-change facts but replace the
                # prior inferred announcement with a directly linked statement.
                if category == "FOMC" and isinstance(current.get("bps"), int):
                    next_event = {**event, "bps": current["bps"],
                                  "subtype": current["subtype"],
                                  "effectiveDate": current.get("effectiveDate"),
                                  "directionKnown": current.get("directionKnown", False)}
                else:
                    next_event = dict(event)
                next_event["catalogOrigin"] = origin
                store[key] = next_event
            elif origin == "curated":
                store[key] = dict(event)
                store[key]["catalogOrigin"] = origin
    return sorted(store.values(), key=lambda e: (e["date"], e["category"], e["id"]))


def fetch(url):
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml",
                                    "Accept-Language": "en-US,en;q=0.9"})
    with urlopen(request, timeout=FETCH_TIMEOUT) as resp:
        body = resp.read(5_000_000)
        if len(body) >= 5_000_000:
            raise ValueError("html source exceeds 5 MB bound")
        encoding = resp.headers.get_content_charset() or "utf-8"
    return body.decode(encoding, errors="replace")


def collect(curated_path=CURATED, output_path=OUTPUT, fetcher=fetch, now=None):
    now = now or datetime.now(timezone.utc)
    curated = read_json(curated_path, {})
    if curated.get("schema") != 1 or not isinstance(curated.get("events"), list):
        raise ValueError("The existing curated official event catalog is required.")
    old = read_json(output_path, {})
    recovered = old.get("events", []) if isinstance(old.get("events"), list) else []
    fetched = []
    statuses, failures = {}, {}
    sources = {f"BLS:{series}": BLS_ROOT + series + ".htm" for series in BLS_SERIES}
    sources["FOMC:recent"] = FED_CALENDAR
    # St. Louis Fed ALFRED is a second public data source; these vintage
    # dates are deliberately separate categories, never mislabeled as verified
    # CPI/NFP/PPI original announcements.
    for release_id in ALFRED_RELEASES:
        sources[f"ALFRED:{release_id}"] = ALFRED_ROOT + str(release_id)
    # Historical annual pages have source-linked statements, including the
    # pre-2021 era omitted from the current calendar.
    for year in range(2000, 2021):
        sources[f"FOMC:{year}"] = FED_HISTORICAL.format(year)
    for name, url in sources.items():
        try:
            html = fetcher(url)
            if name.startswith("BLS:"):
                items = parse_bls_index(html, name.split(":")[1], now)
            elif name.startswith("ALFRED:"):
                items = parse_alfred_dates(html, int(name.split(":")[1]), now)
            else:
                items = parse_fomc_statements(html, now, url)
            # A silently redesigned source index with zero recognizable links
            # is not a successful fetch.
            if not items:
                raise ValueError("no matching official release links parsed")
            fetched.extend(items)
            statuses[name] = {"status": "ok", "parsed": len(items), "url": url}
        except (ValueError, TypeError, HTTPError, URLError, OSError) as exc:
            failures[name] = type(exc).__name__ + ": " + str(exc)[:160]
            statuses[name] = {"status": "failed", "parsed": 0, "url": url}
        # Stay under source request budgets. Each page is retrieved only once
        # per collection, then reused to build every event in that category.
        if fetcher is fetch:
            time.sleep(0.25)
    merged = merge_events(curated["events"], recovered, fetched)
    counts = dict(sorted(Counter(x["category"] for x in merged).items()))
    result = {
        "schema": 1,
        "generatedAt": now.astimezone(ZoneInfo("Asia/Taipei")).isoformat(timespec="seconds"),
        "status": "ok" if not failures else ("partial" if fetched else "sources_unavailable"),
        "sourceIndexStatus": statuses, "sourceErrors": failures,
        "fetchTotal": len(fetched), "sourceCount": len(sources),
        "count": len(merged), "countsByCategory": counts,
        "method": "Source-linked BLS archived releases and Fed policy statements; ALFRED historical date vintages separately categorized because they include revisions. Deduplicated by category and date; no consensus surprise measured.",
        "limitations": [
            "BLS filenames carry publication dates, not reference-month dates. Typical 08:30/10:00 ET times are not verified individually.",
            "Unscheduled events and unindexed historic releases are not guaranteed to be present.",
            "Historical FOMC source links confirm statement dates but are not independently classified as hikes/cuts.",
            "Archived releases may have revisions. Release calendars are not market predictions or price labels.",
            "ALFRED historical date vintages may include revised data, which are kept separate from confirmed BLS original release dates.",
            "When government websites fail, previously verified entries are retained and source errors surfaced."
        ],
        "events": merged,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = output_path.with_suffix(".tmp")
    tmp.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(output_path)
    print(f"official_calendar={len(merged)} new_archive_records={len(fetched)} "
          f"ok_sources={len(sources)-len(failures)}/{len(sources)} "
          f"error_types={dict(Counter(v.split(':')[0] for v in failures.values()))}")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--curated", type=Path, default=CURATED)
    parser.add_argument("--out", type=Path, default=OUTPUT)
    args = parser.parse_args()
    collect(args.curated, args.out)
