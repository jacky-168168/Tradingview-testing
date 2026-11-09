#!/usr/bin/env python3
"""Forward-locked rule scorecard, not a causal/tradable strategy backtest.

Uses only frozen predictions recorded before the first eligible later daily
baseline, and realized 1/5/20-day returns from the headline archive.
Never reclassifies historical headlines after seeing their market outcomes.
"""
from __future__ import annotations

import json
import math
from collections import defaultdict
from datetime import date, datetime, time, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from history import SYMBOLS, HORIZONS, read_json

ROOT = Path("tw-stock-dashboard/docs/data/news_impact")
PREDICTIONS = ROOT / "predictions.json"
HISTORY = ROOT / "history.json"
OUT = ROOT / "scorecard.json"
LEDGER_DIR = ROOT / "outcome_ledger"
MIN_N = 30
MIN_DAYS = 20


def wilson_bounds(wins, losses, z=1.96):
    n = wins + losses
    if not n:
        return None
    p = wins / n
    d = 1 + z * z / n
    center = p + z * z / (2 * n)
    h = z * math.sqrt((p * (1 - p) / n) + (z * z / (4 * n * n)))
    return [round(max(0, 100 * (center - h) / d), 2),
            round(min(100, 100 * (center + h) / d), 2)]


def before_baseline(record, asset, baseline):
    """Conservative: freeze before the first eligible baseline LOCAL DATE.

    If a score is only recorded after the first candidate baseline started,
    exclude it, rather than assume the model predicted price formation.
    """
    try:
        timestamp = datetime.fromisoformat(str(record["frozenAt"]).replace("Z", "+00:00"))
        if timestamp.tzinfo is None:
            return False
        first_date = date.fromisoformat(str(baseline))
        local = timestamp.astimezone(ZoneInfo(SYMBOLS[asset][1]))
        return local.date() < first_date
    except (KeyError, TypeError, ValueError):
        return False


def get_outcomes(predictions, archived, known_keys=None):
    known_keys = known_keys or set()
    archived_by_id = {e.get("id"): e for e in archived.get("events", []) if isinstance(e, dict)}
    observations, pending, excluded = [], 0, 0
    tracked = 0
    for record in predictions.get("records", []):
        historic = archived_by_id.get(record.get("id"))
        for signal in record.get("signals", []):
            asset = signal.get("asset")
            direction = signal.get("direction")
            if asset not in SYMBOLS or direction not in (-1, 1):
                continue
            tracked += 1
            if not historic or asset not in historic.get("baseline", {}):
                pending += sum(1 for horizon in HORIZONS if
                               (record["id"], asset, f"{horizon}D") not in known_keys)
                continue
            baseline = historic["baseline"][asset]
            if not before_baseline(record, asset, baseline):
                excluded += len(HORIZONS)
                continue
            result = historic.get("realized", {}).get(asset, {})
            for horizon in HORIZONS:
                key = f"{horizon}D"
                value = result.get(key)
                if not isinstance(value, (int, float)) or not math.isfinite(value):
                    if (record["id"], asset, key) not in known_keys:
                        pending += 1
                    continue
                outcome = 0 if value == 0 else (1 if value * direction > 0 else -1)
                observations.append({
                    "id": record["id"],
                    "group": record.get("group") or record["id"],
                    "asset": asset,
                    "horizon": key,
                    "ruleIds": signal.get("ruleIds", []),
                    "publishedAt": record.get("publishedAt"),
                    "frozenAt": record.get("frozenAt"),
                    "realizedPct": value,
                    "outcome": outcome
                })
    return observations, {"trackedEventAssetSignals": tracked,
                          "maturedObservationCount": len(observations),
                          "pendingHorizonCount": pending,
                          "excludedLateHorizonCount": excluded}


def observation_key(row):
    """One frozen event/asset/horizon has exactly one immutable outcome."""
    return (str(row.get("id")), str(row.get("asset")), str(row.get("horizon")))


def merge_immutable_observations(previous, current):
    """Preserve first valid observed result across future headline-archive trims.

    Corrections in price provider data must not silently rewrite previously
    counted wins/losses. They need a separately versioned research exercise.
    """
    by_key = {}
    for source in (previous, current):
        for row in source:
            if not isinstance(row, dict) or row.get("outcome") not in (-1, 0, 1):
                continue
            if not isinstance(row.get("realizedPct"), (int, float)) or not math.isfinite(row["realizedPct"]):
                continue
            if row.get("asset") not in SYMBOLS or row.get("horizon") not in [f"{n}D" for n in HORIZONS]:
                continue
            if not row.get("id") or not row.get("frozenAt"):
                continue
            key = observation_key(row)
            if key not in by_key:
                by_key[key] = row.copy()
    return sorted(by_key.values(), key=lambda x: (
        str(x.get("publishedAt") or ""), str(x.get("id")), x["asset"], x["horizon"]))


def read_ledger(folder=LEDGER_DIR):
    if not folder.exists():
        return []
    rows = []
    for path in sorted(folder.glob("*.json")):
        block = read_json(path, {})
        if block.get("schema") == 1 and isinstance(block.get("observations"), list):
            rows.extend(block["observations"])
    return merge_immutable_observations([], rows)


def write_ledger(rows, folder=LEDGER_DIR):
    if not rows:
        return
    folder.mkdir(parents=True, exist_ok=True)
    by_year = defaultdict(list)
    for row in rows:
        timestamp = str(row.get("frozenAt", ""))
        year = timestamp[:4] if len(timestamp) >= 4 and timestamp[:4].isdigit() else "unknown"
        by_year[year].append(row)
    for year, observations in by_year.items():
        target = folder / f"{year}.json"
        payload = {"schema": 1, "year": year, "count": len(observations),
                   "definition": "First-confirmed forward-locked directional outcomes; immutable after first capture.",
                   "observations": observations}
        tmp = target.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
        tmp.replace(target)


def stats(rows):
    # Do not treat exact repost duplicates as extra independent results.
    seen = set()
    unique = []
    for row in rows:
        key = (row["group"], row["asset"], row["horizon"])
        if key not in seen:
            seen.add(key)
            unique.append(row)
    wins = sum(row["outcome"] > 0 for row in unique)
    losses = sum(row["outcome"] < 0 for row in unique)
    flats = sum(row["outcome"] == 0 for row in unique)
    days = {str(row.get("publishedAt") or "")[:10] for row in unique if row.get("publishedAt")}
    n = wins + losses
    validated = n >= MIN_N and len(days) >= MIN_DAYS
    return {
        "n": n, "wins": wins, "losses": losses, "flat": flats,
        "uniquePublishingDates": len(days),
        "status": "descriptive_only" if validated else "insufficient_independent_dates_or_n",
        # Keep counts transparent, but do not label a handful of events "win rate".
        "winRatePct": round(100 * wins / n, 2) if validated else None,
        "wilson95Pct": wilson_bounds(wins, losses) if validated else None,
    }


def build(predictions, archived, now=None, ledger=None):
    now = now or datetime.now(timezone.utc)
    if predictions.get("schema") != 1 or archived.get("schema") != 1:
        raise ValueError("Missing valid immutable predictions or historical headline archive")
    prior = merge_immutable_observations(ledger or [], [])
    known_keys = {observation_key(row) for row in prior}
    fresh, audit = get_outcomes(predictions, archived, known_keys)
    observations = merge_immutable_observations(prior, fresh)
    ledger_count = len(prior)
    audit["currentArchiveMaturedCount"] = audit["maturedObservationCount"]
    audit["maturedObservationCount"] = len(observations)
    fresh_keys = {observation_key(row) for row in fresh}
    audit["retainedOlderObservationCount"] = sum(observation_key(row) not in fresh_keys for row in observations)
    audit["newObservationCount"] = len(observations) - ledger_count
    by_rule = defaultdict(list)
    for o in observations:
        for rid in set(o["ruleIds"]):
            by_rule[(rid, o["asset"], o["horizon"])].append(o)
    per_asset = [
        {"asset": asset, "horizon": f"{h}D", **stats([o for o in observations
              if o["asset"] == asset and o["horizon"] == f"{h}D"])}
        for asset in SYMBOLS for h in HORIZONS
    ]
    rule_rows = [
        {"ruleId": rule, "asset": asset, "horizon": horizon, **stats(rows)}
        for (rule, asset, horizon), rows in sorted(by_rule.items())
    ]
    all_by_horizon = [
        {"horizon": f"{h}D", **stats([o for o in observations if o["horizon"] == f"{h}D"])}
        for h in HORIZONS
    ]
    return {
        "schema": 1,
        "generatedAt": now.astimezone(ZoneInfo("Asia/Taipei")).isoformat(timespec="seconds"),
        "status": "descriptive" if any(r["winRatePct"] is not None for r in per_asset) else "insufficient_matured_signals",
        "predictionRecords": len(predictions.get("records", [])),
        "historyEventRecords": len(archived.get("events", [])),
        "predictionVersionCurrent": predictions.get("classifierVersionCurrent"),
        "minN": MIN_N, "minIndependentPublishingDates": MIN_DAYS,
        "method": "Freeze a direction before the first later market baseline; use close-to-close 1D/5D/20D follow-through; direction-sign hit only, ignoring flat returns in win/loss denominator.",
        "notTradingBacktest": True, "notCausal": True,
        "outcomeLedgerMode": "frozen_first_result_by_year",
        "limitations": [
            "Rule-score magnitude is not an estimated return or probability; outcomes cannot assess calibration.",
            "Outcomes use later completed market daily closes, not immediate news release price moves.",
            "Same news may appear under different wording across sources; cross-media event clustering remains imperfect.",
            "Asset returns can be correlated; the all-assets row is NOT independent evidence.",
            "No fees, funding, slippage, volatility adjustment, benchmark control or trade execution simulated.",
            "Live news is a short history beginning Nov 2026; historic economic release revision dates carry no frozen forecasts.",
            "No hindsight relabeling: frozen signals cannot be updated using future prices. Ineligible late snapshots are excluded.",
            "Only the first matured result for each frozen news-asset-horizon is kept; older verified outcomes survive news archive trimming.",
            "Confidence bounds assume independent trials but event correlations can make them too narrow; read as descriptive uncertainty only."
        ],
        "audit": audit, "byAsset": per_asset, "byRule": rule_rows, "allAssetCrossCount": all_by_horizon
    }


def generate(predictions_path=PREDICTIONS, history_path=HISTORY, output_path=OUT):
    predictions = read_json(predictions_path, {})
    archived = read_json(history_path, {})
    previous = read_ledger(output_path.parent / "outcome_ledger")
    result = build(predictions, archived, ledger=previous)
    fresh, _audit = get_outcomes(predictions, archived, {observation_key(row) for row in previous})
    merged = merge_immutable_observations(previous, fresh)
    write_ledger(merged, output_path.parent / "outcome_ledger")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_suffix(".tmp")
    temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(output_path)
    print(f"frozen={result['predictionRecords']} matured={result['audit']['maturedObservationCount']} "
          f"pending={result['audit']['pendingHorizonCount']} excluded_late={result['audit']['excludedLateHorizonCount']}")


if __name__ == "__main__":
    generate()
