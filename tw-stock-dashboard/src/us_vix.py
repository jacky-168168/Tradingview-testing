#!/usr/bin/env python3
"""Fetch public daily closing VIX-family indices from Cboe; never fabricate values.

Usage: python src/us_vix.py
Generated output: docs/data/research/us_vix/history.json
Cboe indices are copyright Cboe Global Markets; source URLs and dates retained.
This is daily closing data, NOT intraday market data.
"""
from __future__ import annotations
import csv
import io
import json
import os
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "docs/data/research/us_vix/history.json"
SYMBOLS = ("VIX", "VIX9D", "VIX3M", "VVIX")
URLS = {k: tuple("https://" + host + "/api/global/us_indices/daily_prices/" + k + "_History.csv" for host in ("cdn-api.cboe.com", "cdn.cboe.com")) for k in SYMBOLS}
MAX_BYTES = 6_000_000

def parse_csv(raw: bytes) -> list[list[object]]:
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig", errors="replace")))
    if not reader.fieldnames:
        raise ValueError("missing CSV header")
    names = {x.strip().lower().replace(" ", "").replace("_", ""): x for x in reader.fieldnames if x}
    date_col = names.get("date")
    close_col = names.get("close") or names.get("vixclose") or names.get("vvix")
    if not date_col or not close_col:
        raise ValueError("expected DATE and CLOSE CSV fields, got " + repr(reader.fieldnames))
    dates = {}
    today = datetime.now(timezone.utc).date()
    for row in reader:
        s = (row.get(date_col) or "").strip()
        raw_close = (row.get(close_col) or "").strip().replace(",", "")
        try:
            parsed = None
            for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%m/%d/%y"):
                try:
                    parsed = datetime.strptime(s, fmt).date()
                    break
                except ValueError:
                    continue
            if not parsed or parsed > today:
                continue
            value = float(raw_close)
            if not (0 < value < 1000):
                continue
            dates[parsed.isoformat()] = round(value, 3)
        except (TypeError, ValueError):
            continue
    result = [[d, dates[d]] for d in sorted(dates)]
    if len(result) < 30:
        raise ValueError(f"too few valid observations: {len(result)}")
    if (today - date.fromisoformat(result[-1][0])).days > 12:
        raise ValueError(f"latest source observation is stale: {result[-1][0]}")
    return result

def fetch(name: str) -> tuple[list[list[object]], str]:
    errors = []
    for url in URLS[name]:
        try:
            req = Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; Tradingview-testing-VIX/1.0)", "Accept": "text/csv,text/plain,*/*"})
            with urlopen(req, timeout=25) as resp:
                raw = resp.read(MAX_BYTES + 1)
                if len(raw) > MAX_BYTES:
                    raise ValueError("oversized source file")
            return parse_csv(raw), url
        except (HTTPError, URLError, OSError, TimeoutError, ValueError, UnicodeError) as exc:
            errors.append(f"{url}: {type(exc).__name__} {str(exc)[:160]}")
    raise RuntimeError(" / ".join(errors))

def main() -> None:
    old = {}
    if DEST.exists():
        try:
            old = json.loads(DEST.read_text("utf-8"))
        except (OSError, ValueError):
            pass
    prior = old.get("series", {}) if isinstance(old, dict) else {}
    series = {}
    errors = {}
    for name in SYMBOLS:
        try:
            rows, url = fetch(name)
            series[name] = {"lastDate": rows[-1][0], "source": url, "rows": rows}
            print(f"{name}: {len(rows)} observations to {rows[-1][0]}")
        except Exception as exc:
            errors[name] = str(exc)[:400]
            saved = prior.get(name) if isinstance(prior, dict) else None
            if isinstance(saved, dict) and isinstance(saved.get("rows"), list) and len(saved["rows"]) >= 30:
                series[name] = saved
                print(f"{name}: fetch failed, retained last verified series ({saved.get('lastDate')})")
            else:
                print(f"{name}: unavailable ({errors[name]})")
    if "VIX" not in series:
        raise RuntimeError("VIX official data unavailable; cannot publish an empty or invented chart")
    today = datetime.now(timezone.utc)
    payload = {"version": "CBOE_VIX_DAILY_V1", "frequency": "daily_close", "source": "Cboe Global Markets",
               "sourcePage": "https://www.cboe.com/tradable-products/vix/vix-historical-data/",
               "updatedAt": today.isoformat(timespec="seconds"),
               "copyright": "Cboe Global Markets. Daily closing values are not real-time quotes.",
               "series": series, "errors": errors}
    DEST.parent.mkdir(parents=True, exist_ok=True)
    tmp = DEST.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    os.replace(tmp, DEST)
    print(f"Saved {DEST} ({DEST.stat().st_size} bytes); missing: {list(errors)}")

if __name__ == "__main__":
    main()
