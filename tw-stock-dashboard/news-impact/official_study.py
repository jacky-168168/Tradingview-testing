#!/usr/bin/env python3
"""Descriptive historical event study from source-linked dates, with no fabricated results.

Event outcomes measure completed market sessions; CPI consensus/actual surprise
is NOT in the event catalog, so CPI event returns must not be interpreted as
positive/negative surprises. Never treats headlines as independent observations.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from bisect import bisect_left
import statistics
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from history import HORIZONS, SYMBOLS, fetch_prices, read_json

CATALOG = Path("tw-stock-dashboard/news-impact/official_events_expanded.json")
OUTPUT = Path("tw-stock-dashboard/docs/data/news_impact/official_study.json")
EQUITY_CUTOFF = {"美股S&P500": time(16, 0), "NASDAQ": time(16, 0), "台股": time(13, 30)}
MIN_SAMPLE = 20


def event_timestamp(event):
    """Return aware published timestamp only if an official time exists."""
    if not event.get("localTime"):
        return None
    try:
        hh, mm = map(int, event["localTime"].split(":"))
        return datetime.combine(date.fromisoformat(event["date"]), time(hh, mm),
                                tzinfo=ZoneInfo(event["timezone"]))
    except (ValueError, KeyError):
        return None


def eligible_session(event, asset, bars):
    """First daily bar definitely closed after publication / dated decision.

    Known releases: same local exchange date is eligible for *equities* only
    if the known release time preceded that market's normal session close.
    All futures/index proxies and time-unknown events use a later date.
    """
    if not bars:
        return None
    timestamp = event_timestamp(event)
    tz = ZoneInfo(SYMBOLS[asset][1])
    if timestamp and asset in EQUITY_CUTOFF:
        local = timestamp.astimezone(tz)
        earliest = local.date() if local.time() < EQUITY_CUTOFF[asset] else local.date() + timedelta(days=1)
    else:
        # For no exact announcement time, date-only is conservative. Some
        # Asian assets may already have reacted to an earlier date's news.
        if timestamp:
            earliest = timestamp.astimezone(tz).date() + timedelta(days=1)
        else:
            earliest = date.fromisoformat(event["date"]) + timedelta(days=1)
    # Date/close tuples are already sorted. Binary search is necessary for
    # decades of prices * thousands of archived releases.
    idx = bisect_left(bars, (earliest, float('-inf')))
    return idx if 0 < idx < len(bars) else None


def event_returns(event, asset, bars):
    idx = eligible_session(event, asset, bars)
    if idx is None:
        return None
    previous_day, baseline = bars[idx - 1]
    if baseline <= 0:
        return None
    returns = {}
    for horizon in HORIZONS:
        future = idx + horizon - 1
        if future >= len(bars):
            continue
        outcome = (bars[future][1] / baseline - 1) * 100
        if math.isfinite(outcome):
            returns[f"{horizon}D"] = round(outcome, 4)
    if not returns:
        return None
    return {"asset": asset, "baselineDate": str(previous_day),
            "firstEligibleDate": str(bars[idx][0]),
            "results": returns,
            "method": "equity_event_session" if event_timestamp(event) and asset in EQUITY_CUTOFF else "next_local_date_proxy"}


def summary_stats(values, controls):
    values = sorted(v for v in values if isinstance(v, (int, float)) and math.isfinite(v))
    if not values:
        return {"n": 0, "status": "no_mature_observations"}
    positive = sum(1 for v in values if v > 0)
    mean = statistics.fmean(values)
    median = statistics.median(values)
    control_mean = statistics.fmean(controls) if controls else None
    return {"n": len(values), "status": "descriptive" if len(values) >= MIN_SAMPLE else "small_sample",
            "meanPct": round(mean, 3), "medianPct": round(median, 3),
            "positivePct": round(100 * positive / len(values), 1),
            "minPct": round(values[0], 3), "maxPct": round(values[-1], 3),
            "p25Pct": round(values[(len(values) - 1) // 4], 3),
            "p75Pct": round(values[((len(values) - 1) * 3) // 4], 3),
            "allWindowMeanPct": round(control_mean, 3) if control_mean is not None else None,
            "vsUnconditionalPct": round(mean - control_mean, 3) if control_mean is not None else None}


def rolling_controls(bars, horizon, start_day):
    """Unconditional same-asset rolling daily forward returns; not causal control."""
    out = []
    for i in range(1, len(bars) - horizon + 1):
        if bars[i][0] < start_day:
            continue
        baseline = bars[i - 1][1]
        if baseline <= 0:
            continue
        value = (bars[i + horizon - 1][1] / baseline - 1) * 100
        if math.isfinite(value):
            out.append(value)
    return out


def validate_catalog(catalog):
    if catalog.get("schema") != 1 or not isinstance(catalog.get("events"), list):
        raise ValueError("official event catalog missing valid schema")
    ids = set()
    for event in catalog["events"]:
        if not all(event.get(x) for x in ("id", "category", "date", "source", "sourceUrl", "title")):
            raise ValueError("missing event metadata")
        if not str(event["sourceUrl"]).startswith("https://"):
            raise ValueError("event source must be https")
        if event["id"] in ids:
            raise ValueError("duplicate event ID " + str(event["id"]))
        ids.add(event["id"])
        date.fromisoformat(event["date"])
        ZoneInfo(event["timezone"])
        event_timestamp(event)


def build_study(catalog, prices, errors, now=None):
    now = now or datetime.now(timezone.utc)
    validate_catalog(catalog)
    raw_events = catalog["events"]
    rows = []
    for event in raw_events:
        # Date-only event may mean a future announcement; do not look ahead.
        if date.fromisoformat(event["date"]) > now.date():
            continue
        outcomes = {}
        for asset, bars in prices.items():
            if asset not in SYMBOLS:
                continue
            observation = event_returns(event, asset, bars)
            if observation:
                outcomes[asset] = observation
        rows.append({k: v for k, v in event.items() if k not in ("evidence",)} | {"outcomes": outcomes})
    categories = sorted(set(e["category"] for e in rows))
    # FOMC hikes and cuts must not be aggregated into an implied direction.
    groups = [{"key": c, "label": c, "kind": "category"} for c in categories]
    groups += [{"key": "FOMC:"+direction, "label": "FOMC "+direction, "kind": "subtype"}
               for direction in ("升息", "降息") if any(e["category"] == "FOMC" and e["subtype"] == direction for e in rows)]
    controls = {}
    min_date = min((date.fromisoformat(e["date"]) for e in rows), default=now.date())
    for asset, bars in prices.items():
        for horizon in HORIZONS:
            controls[(asset, horizon)] = rolling_controls(bars, horizon, min_date)
    stats = []
    for g in groups:
        filtered = [e for e in rows if
                    e["category"] == g["key"] or (g["kind"] == "subtype" and
                    e["category"] == "FOMC" and e.get("subtype") == g["key"].split(":")[1])]
        for asset in SYMBOLS:
            for horizon in HORIZONS:
                key = f"{horizon}D"
                observations = [e["outcomes"][asset]["results"][key] for e in filtered
                                if asset in e["outcomes"] and key in e["outcomes"][asset]["results"]]
                stats.append({"group": g["key"], "asset": asset, "horizon": key,
                              **summary_stats(observations, controls.get((asset, horizon), []))})
    return {
        "schema": 1,
        "generatedAt": now.astimezone(ZoneInfo("Asia/Taipei")).isoformat(timespec="seconds"),
        "catalogCount": len(raw_events), "eventCount": len(rows),
        "catalogCountsByCategory": catalog.get("countsByCategory", {}),
        "catalogSourceStatus": catalog.get("status", "curated_only"),
        "catalogSourceErrors": catalog.get("sourceErrors", {}),
        "catalogEarliest": min((e["date"] for e in rows), default=None),
        "catalogLatest": max((e["date"] for e in rows), default=None),
        "eventsWithPriceData": sum(bool(e["outcomes"]) for e in rows),
        "groups": groups,
        "minSample": MIN_SAMPLE,
        "status": "ok" if len(prices) == len(SYMBOLS) else ("partial" if prices else "unavailable"),
        "priceSymbolsOk": list(prices), "priceErrors": errors,
        "method": "Historical observed return from close before first eligible post-publication equity session (or next-date proxy for futures/unknown time) to close of session 1/5/20; excludes incomplete daily candles.",
        "comparison": "Unconditional mean of all available same-asset rolling 1/5/20 session returns since oldest catalog event; NOT risk-adjusted, NOT causal or randomized controls.",
        "limitations": [
            "CPI release dates do not include consensus, actual-value surprise, or direction.",
            "Fed effective dates mapped to prior day 14:00 ET as approximate regular meeting announcements; exceptions are possible.",
            "OPEC and election date-only events use the following local-date session proxy, not actual first announcement time.",
            "Futures close timestamps and continuous-contract roll behavior are not exchange-verified; apparent daily returns are proxies.",
            "Historical events can overlap; samples are not independent and small-n positive fraction is not a predictive hit rate.",
            "BLS historical archives provide release date (not contemporaneous forecast); typical release times are assumed and not individually audited.",
            "FOMC archive dates include hold decisions but do not establish surprise direction; incomplete old ticker history reduces realized counts.",
            "Yahoo Finance daily data may be corrected or incomplete, returns are descriptive rather than evidence of causation."
        ],
        "stats": stats, "events": rows,
    }


def generate(catalog_path=CATALOG, output_path=OUTPUT):
    now = datetime.now(timezone.utc)
    catalog = read_json(catalog_path, {})
    # Request the maximum supported daily-history depth for each Yahoo symbol. Previous news archive uses short-term prices.
    prices, errors = fetch_prices(now, period="max")
    # If full provider outage occurs, preserve previous valid results rather
    # than overwrite verified historical stats with empty rows.
    if not prices and output_path.exists():
        print("all market sources failed; keeping prior historical snapshot", errors)
        return
    result = build_study(catalog, prices, errors, now)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    # Mobile page must not download multi-megabyte all-asset/all-event history.
    # Publish a small summary plus one independently readable JSON shard per
    # (event category, asset). The UI fetches just its current selection.
    shards = output_path.parent / "official_details"
    shards.mkdir(parents=True, exist_ok=True)
    categories = sorted({e["category"] for e in result["events"]})
    details = {}
    for category in categories:
        slug = hashlib.sha256(category.encode("utf-8")).hexdigest()[:16]
        details[category] = {}
        relevant = [e for e in result["events"] if e["category"] == category]
        for index, asset in enumerate(SYMBOLS):
            filename = f"{slug}-{index}.json"
            payload = {
                "schema": 1, "generatedAt": result["generatedAt"],
                "category": category, "asset": asset,
                "eventCount": len(relevant),
                "events": [{
                    "id": e["id"], "category": e["category"],
                    "subtype": e.get("subtype"), "date": e["date"],
                    "title": e["title"], "source": e["source"],
                    "sourceUrl": e["sourceUrl"],
                    "timeAccuracy": e.get("timeAccuracy"),
                    "primaryReleaseVerified": e.get("primaryReleaseVerified"),
                    "outcomes": {asset: e["outcomes"][asset]} if asset in e["outcomes"] else {}
                } for e in relevant],
            }
            target = shards / filename
            temp_shard = target.with_suffix(".tmp")
            temp_shard.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
            temp_shard.replace(target)
            details[category][asset] = f"./data/news_impact/official_details/{filename}"
    summary = {k: v for k, v in result.items() if k != "events"}
    summary["detailMode"] = "category_asset_shards"
    summary["detailFiles"] = details
    summary["detailFileCount"] = sum(map(len, details.values()))
    temp = output_path.with_suffix(".tmp")
    temp.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(output_path)
    nonempty = sum(s["n"] > 0 for s in result["stats"])
    print(f"official events {result['eventCount']}; realized event dates {result['eventsWithPriceData']}; "
          f"price symbols {len(prices)}/{len(SYMBOLS)}; nonempty stats {nonempty}; "
          f"detail shards {summary['detailFileCount']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog", type=Path, default=CATALOG)
    parser.add_argument("--out", type=Path, default=OUTPUT)
    args = parser.parse_args()
    generate(args.catalog, args.out)
