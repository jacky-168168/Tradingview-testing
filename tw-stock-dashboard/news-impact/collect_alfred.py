#!/usr/bin/env python3
"""ALFRED economic release DATE-VINTAGE index (no API key).

IMPORTANT: ALFRED's historical release date list is a list of dates on which
at least one series for a named release was updated/revised. It is NOT an
exhaustively authenticated schedule of the first release of each month's CPI,
NFP, GDP, etc. These must stay in separate categories from primary releases.
"""
from __future__ import annotations

import re
from datetime import date, datetime, timezone

ROOT = "https://alfred.stlouisfed.org/release/downloaddates?ff=txt&rid="
# IDs verified against the St. Louis Federal Reserve's public release pages.
RELEASES = {
    10: ("CPI資料更新", "消費者物價指數", "BLS"),
    50: ("非農就業資料更新", "就業情勢／非農", "BLS"),
    46: ("PPI資料更新", "生產者物價指數", "BLS"),
    192: ("JOLTS資料更新", "職缺與勞動流動", "BLS"),
    54: ("PCE資料更新", "個人所得與消費支出／PCE", "BEA"),
    53: ("GDP資料更新", "美國 GDP", "BEA"),
    9: ("零售銷售資料更新", "零售銷售", "Census"),
    13: ("工業生產資料更新", "工業生產與產能利用率", "Federal Reserve"),
}
DATE_LINE = re.compile(r"(?m)^\s*(\d{4}-\d{2}-\d{2})\s*$")
BEGIN = re.compile(r"(?im)^Release Dates:\s*\r?\n\s*-+\s*\r?\n")


def parse_alfred_dates(text, release_id, now=None):
    if release_id not in RELEASES:
        raise ValueError("ALFRED release ID is not approved for this collection")
    if not isinstance(text, str):
        raise ValueError("ALFRED release dates must be text")
    now = now or datetime.now(timezone.utc)
    mark = BEGIN.search(text)
    if not mark:
        raise ValueError("ALFRED text missing Release Dates section")
    category, label, agency = RELEASES[release_id]
    url = ROOT + str(release_id)
    result = {}
    for value in DATE_LINE.findall(text[mark.end():]):
        try:
            day = date.fromisoformat(value)
        except ValueError:
            continue
        if not date(1940, 1, 1) <= day <= now.date():
            continue
        result[value] = {
            "id": f"alfred-release-{release_id}-{value}",
            "category": category, "subtype": "歷史資料發布／修訂日期（未辨認首次公告）",
            "date": value, "timezone": "America/New_York",
            "localTime": None, "timeAccuracy": "date_only_vintage_or_revision",
            "title": f"美國 {label} 資料更新或修訂日（ALFRED）",
            "source": "ALFRED / Federal Reserve Bank of St. Louis",
            "sourceUrl": url, "publishedBy": agency,
            "evidence": "ALFRED download of release date history; may include later revised data. This date does not establish the main release, consensus surprise or any new information to the market.",
            "directionKnown": False,
            "primaryReleaseVerified": False,
            "calendarKind": "alfred_historical_vintage",
        }
    if not result:
        raise ValueError("ALFRED release had no valid historical dates")
    return [result[d] for d in sorted(result)]
