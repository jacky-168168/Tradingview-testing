#!/usr/bin/env python3
"""Archive public headline events and measure post-publication price follow-through.

This is descriptive research, NOT proof of news causality. Only Yahoo Finance
daily close data are used; no unobserved future bar may enter an output.
"""
from __future__ import annotations

import argparse
import json
import math
from datetime import datetime, timezone, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

SYMBOLS = {
    "美股S&P500": ("^GSPC", "America/New_York"),
    "NASDAQ": ("^IXIC", "America/New_York"),
    "台股": ("^TWII", "Asia/Taipei"),
    "黃金": ("GC=F", "America/New_York"),
    "白銀": ("SI=F", "America/New_York"),
    "WTI原油": ("CL=F", "America/New_York"),
    "美元": ("DX-Y.NYB", "America/New_York"),
    "美債殖利率": ("^TNX", "America/New_York"),
    "銅": ("HG=F", "America/New_York"),
}
HORIZONS = (1, 5, 20)
MAX_EVENTS = 2400


def read_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def parse_published(value: str):
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            return None
        return dt.astimezone(timezone.utc)
    except (ValueError, TypeError):
        return None


def is_public_news(item: dict) -> bool:
    return (isinstance(item, dict) and item.get("type") == "news"
            and bool(item.get("title")) and bool(item.get("url"))
            and str(item.get("url")).startswith("https://")
            and parse_published(item.get("publishedAt", "")) is not None)


def archive_events(existing: list, incoming: list, now: datetime):
    by_id = {e["id"]: e for e in existing
             if isinstance(e, dict) and isinstance(e.get("id"), str)
             and parse_published(e.get("publishedAt", ""))}
    for item in incoming:
        if not is_public_news(item):
            continue
        published = parse_published(item["publishedAt"])
        if published > now + timedelta(minutes=5):
            continue
        event_id = str(item.get("id") or item["url"])[:240]
        if not event_id:
            continue
        if event_id not in by_id:
            by_id[event_id] = {
                "id": event_id,
                "title": str(item["title"])[:500],
                "source": str(item.get("source") or "")[:100],
                "category": str(item.get("category") or "")[:100],
                "publishedAt": item["publishedAt"],
                "originType": item.get("originType"),
                "url": item["url"],
                "realized": {},
            }
    result = sorted(by_id.values(), key=lambda e: e["publishedAt"], reverse=True)
    return result[:MAX_EVENTS]


def fetch_prices(now: datetime, period: str = "9mo"):
    """Returns completed daily closes and explicit fetch errors, never made-up prices."""
    try:
        import yfinance as yf
    except ImportError:
        return {}, {"dependency": "yfinance not installed"}
    data, errors = {}, {}
    for asset, (ticker, tz) in SYMBOLS.items():
        try:
            frame = yf.Ticker(ticker).history(period=period, interval="1d", auto_adjust=True)
            if frame is None or frame.empty or "Close" not in frame:
                raise ValueError("No daily Close")
            current_local_date = now.astimezone(ZoneInfo(tz)).date()
            bars = []
            for idx, row in frame.iterrows():
                # Exclude a possible unfinished 'today' daily candle.
                date = idx.date()
                close = float(row["Close"])
                if date >= current_local_date or not math.isfinite(close) or close <= 0:
                    continue
                bars.append((date, close))
            if len(bars) < 25:
                raise ValueError("Fewer than 25 completed bars")
            data[asset] = sorted(dict(bars).items())
        except Exception as exc:
            errors[asset] = type(exc).__name__ + ": " + str(exc)[:120]
    return data, errors


def follow_through(published_at: str, dates_and_closes, asset_timezone: str):
    """First *later session's* close is baseline; forward n closed sessions.
    This intentionally misses the initial event-day reaction (anti-look-ahead).
    """
    dt = parse_published(published_at)
    if dt is None:
        return {}, None
    event_date = dt.astimezone(ZoneInfo(asset_timezone)).date()
    base_idx = next((i for i, (d, _) in enumerate(dates_and_closes) if d > event_date), None)
    if base_idx is None:
        return {}, None
    base_date, base = dates_and_closes[base_idx]
    returns = {}
    for horizon in HORIZONS:
        target = base_idx + horizon
        if target < len(dates_and_closes):
            ret = (dates_and_closes[target][1] / base - 1) * 100
            if math.isfinite(ret):
                returns[f"{horizon}D"] = round(ret, 3)
    return returns, str(base_date)


def generate(news_path: Path, output_path: Path):
    now = datetime.now(timezone.utc)
    news = read_json(news_path, {})
    if not isinstance(news.get("items"), list) or news.get("schema") != 1:
        raise RuntimeError(f"Missing valid current headline source: {news_path}")
    previous = read_json(output_path, {})
    events = archive_events(previous.get("events", []), news["items"], now)
    price_data, price_errors = fetch_prices(now)
    for event in events:
        if "realized" not in event or not isinstance(event["realized"], dict):
            event["realized"] = {}
        if "baseline" not in event or not isinstance(event["baseline"], dict):
            event["baseline"] = {}
        for asset, closes in price_data.items():
            _, tz = SYMBOLS[asset]
            result, baseline = follow_through(event["publishedAt"], closes, tz)
            if result:
                # Keep previous maturities if the current provider has a short outage.
                event["realized"][asset] = {**event["realized"].get(asset, {}), **result}
                event["baseline"][asset] = baseline
    published = {
        "schema": 1,
        "generatedAt": now.astimezone(ZoneInfo("Asia/Taipei")).isoformat(timespec="seconds"),
        "sourceNewsGeneratedAt": news.get("generatedAt"),
        "method": "Daily close: first trading session strictly after local publication date is baseline; 1/5/20 later completed sessions, no event-day move included.",
        "isCausal": False,
        "isBacktest": False,
        "priceProvider": "Yahoo Finance via yfinance (adjusted daily closes); futures proxies may have roll effects.",
        "status": "ok" if len(price_data) == len(SYMBOLS) else ("partial" if price_data else "price_unavailable"),
        "priceSymbolsOk": list(price_data),
        "priceErrors": price_errors,
        "symbols": {a: t for a, (t, _) in SYMBOLS.items()},
        "events": events,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = output_path.with_suffix(".tmp")
    tmp.write_text(json.dumps(published, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(output_path)
    print(f"archive={len(events)} prices={len(price_data)}/{len(SYMBOLS)} output={output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--news", type=Path, default=Path("tw-stock-dashboard/docs/data/market_events/latest.json"))
    parser.add_argument("--out", type=Path, default=Path("tw-stock-dashboard/docs/data/news_impact/history.json"))
    args = parser.parse_args()
    generate(args.news, args.out)
