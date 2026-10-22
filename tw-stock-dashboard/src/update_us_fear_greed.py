#!/usr/bin/env python3
"""WantGoo Fear & Greed daily observations plus dated S&P 500 (display only).

Use public WantGoo page values for new observations. Existing CNN historical
observations before the cutover remain as explicitly labelled legacy history.
Never relabel legacy values, backfill missing scores, or use as TW Risk Score.
"""
from __future__ import annotations

import json
import math
import re
import urllib.request
from datetime import date, datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
SOURCE = "https://www.wantgoo.com/global/macroeconomics/fearandgreed"
LEGACY_SOURCE = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata/2022-01-01"
CUTOVER_DATE = "2026-10-15"
VERSION = "US_WANTGOO_FEAR_GREED_SPX_V1"
SPX = BASE / "docs/data/research/us_options/history.json"
OUT = BASE / "docs/data/research/us_fear_greed/history.json"
HEADERS = {
    "Accept": "text/html,application/xhtml+xml",
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
}

# Match the public dated table, not the undated current headline. S&P 500
# alongside each row prevents accidentally treating sidebar numbers as scores.
ROW = re.compile(
    r"(20\d{2}/\d{2}/\d{2})\s*"
    r"(極度恐懼|極度貪婪|恐懼|貪婪|中立)\s*"
    r"(\d{1,3}(?:\.\d+)?)\s*([\d,]+(?:\.\d+)?)"
)


class VisibleText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.hidden_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "noscript"}:
            self.hidden_depth += 1

    def handle_endtag(self, tag):
        if tag in {"script", "style", "noscript"} and self.hidden_depth:
            self.hidden_depth -= 1

    def handle_data(self, data):
        if not self.hidden_depth and data.strip():
            self.parts.append(data.strip())


def valid_score(value):
    if isinstance(value, bool):
        return None
    try:
        n = float(value)
    except (TypeError, ValueError):
        return None
    return round(n, 3) if math.isfinite(n) and 0 <= n <= 100 else None


def wantgoo_series(html):
    reader = VisibleText()
    reader.feed(html)
    text = " ".join(reader.parts)
    rows = {}
    for match in ROW.finditer(text):
        raw_date, label, score_raw, price_raw = match.groups()
        try:
            d = date.fromisoformat(raw_date.replace("/", "-")).isoformat()
            score = valid_score(score_raw)
            price = float(price_raw.replace(",", ""))
        except ValueError:
            continue
        if score is None or not math.isfinite(price) or price <= 100:
            continue
        # Reject contradictory duplicated rows instead of silently replacing.
        value = (score, round(price, 3))
        if d in rows and rows[d] != value:
            raise ValueError("WantGoo conflicting duplicate date: " + d)
        rows[d] = value
    if len(rows) < 2:
        raise ValueError("WantGoo public dated history table unavailable or too short")
    if max(rows) > datetime.now(timezone.utc).date().isoformat():
        raise ValueError("WantGoo has future dated observations")
    return rows


def spx_series(doc):
    if not isinstance(doc, dict) or doc.get("columns") != ["date", "spx", "dixPct", "gex"]:
        raise ValueError("Existing S&P500 historical data missing or schema changed")
    rows = {}
    for row in doc.get("rows", []):
        if not isinstance(row, list) or len(row) != 4:
            continue
        try:
            d = date.fromisoformat(str(row[0])).isoformat()
            price = float(row[1])
            if math.isfinite(price) and price > 100:
                rows[d] = round(price, 3)
        except (ValueError, TypeError):
            continue
    if len(rows) < 500:
        raise ValueError("S&P500 archive too short")
    return rows


def previous_series(old):
    if not isinstance(old, dict) or old.get("version") not in (
        "US_CNN_FEAR_GREED_SPX_V1", VERSION
    ):
        raise ValueError("Existing Fear & Greed archive format not recognized")
    if old.get("columns") != ["date", "fearGreed", "spx"]:
        raise ValueError("Existing Fear & Greed archive columns changed")
    legacy, observed = {}, {}
    for row in old.get("rows", []):
        if not isinstance(row, list) or len(row) != 3:
            continue
        try:
            d = date.fromisoformat(str(row[0])).isoformat()
            score = valid_score(row[1])
            if score is None:
                continue
            if d < CUTOVER_DATE:
                legacy[d] = score
            elif old["version"] == VERSION:
                observed[d] = score
        except (TypeError, ValueError):
            continue
    if len(legacy) < 150:
        raise ValueError("Legacy CNN history missing; cannot silently erase history")
    return legacy, observed


def to_archive(wantgoo, spx_doc, old):
    us = spx_series(spx_doc)
    legacy, observed = previous_series(old)
    incoming = {d: val for d, val in wantgoo.items() if d >= CUTOVER_DATE}
    if len(incoming) < 2:
        raise ValueError("WantGoo has insufficient observations after cutover")
    # Check independently provided prices for the same market date.
    for d, (_, wantgoo_spx) in incoming.items():
        if d in us and abs(wantgoo_spx - us[d]) > 5:
            raise ValueError("WantGoo vs S&P500 close differs materially: " + d)
    observed.update({d: v[0] for d, v in incoming.items()})
    latest_wantgoo = max(incoming)
    latest_spx = max(us)
    if latest_wantgoo != latest_spx:
        raise ValueError("US_MARKET_DATE_NOT_ALIGNED: WantGoo=" + latest_wantgoo +
                         " SPX=" + latest_spx)
    points = {**legacy, **observed}
    common = sorted(set(points) & set(us))
    if len(common) < 150 or common[-1] != latest_wantgoo:
        raise ValueError("WantGoo / S&P500 verified history too short or stale")
    return {
        "version": VERSION,
        "source": SOURCE,
        "sourceLink": SOURCE,
        "legacySource": LEGACY_SOURCE,
        "legacyUntil": max(legacy),
        "wantgooFrom": min(observed),
        "spxSource": "SqueezeMetrics DIX.csv / indexed S&P 500 settlement (display only)",
        "updatedAt": datetime.now(timezone.utc).isoformat(),
        "wantgooHistoricalLast": latest_wantgoo,
        "spxLast": latest_spx,
        "asOf": common[-1],
        "columns": ["date", "fearGreed", "spx"],
        "rows": [[d, points[d], us[d]] for d in common],
        "legacyCount": sum(d < CUTOVER_DATE for d in common),
        "wantgooCount": sum(d >= CUTOVER_DATE for d in common),
        "components": {},
        "disclaimer": "WantGoo observations since 2026-10-15; older historical scores came from CNN. "
                      "Display only; no trading gate, no interpolation, no future fill.",
    }


def fetch_wantgoo():
    request = urllib.request.Request(SOURCE, headers=HEADERS, method="GET")
    with urllib.request.urlopen(request, timeout=40) as response:
        if response.status != 200:
            raise RuntimeError("WantGoo HTTP " + str(response.status))
        body = response.read(4_000_001)
        encoding = response.headers.get_content_charset() or "utf-8"
    if len(body) > 4_000_000:
        raise ValueError("WantGoo response unexpectedly large")
    return body.decode(encoding, errors="strict")


def main():
    html = fetch_wantgoo()
    wantgoo = wantgoo_series(html)
    spx = json.loads(SPX.read_text(encoding="utf-8"))
    previous = json.loads(OUT.read_text(encoding="utf-8"))
    result = to_archive(wantgoo, spx, previous)
    # Atomic on-disk replace: an HTML/layout/schema change must not destroy
    # the last verified archive.
    import os
    temp = OUT.with_suffix(".json.tmp")
    try:
        temp.write_text(json.dumps(result, ensure_ascii=False, separators=(",", ":")) + "\n",
                        encoding="utf-8")
        os.replace(temp, OUT)
    finally:
        if temp.exists():
            temp.unlink()
    print("US WantGoo Fear & Greed verified", len(result["rows"]), "sessions",
          "asOf", result["asOf"], "WantGoo", result["wantgooHistoricalLast"],
          "SPX", result["spxLast"], "legacy", result["legacyCount"])


if __name__ == "__main__":
    main()
