#!/usr/bin/env python3
"""Guard against publishing yesterday's margin ratio as today's completed result.

The separate full-market daily snapshot establishes whether today's exchange
session has actually been observed; weekday alone is not a trading calendar.
"""
import json
from datetime import datetime, time
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
TZ = ZoneInfo("Asia/Taipei")
CUTOFF = time(19, 15)


def validate(retail, market, now):
    local = now.astimezone(TZ)
    today = local.date().isoformat()
    rows = retail.get("rows") or []
    if not rows or retail.get("asOf") != rows[-1].get("date"):
        raise RuntimeError("Retail margin asOf disagrees with the latest observation")
    asof = retail["asOf"]
    if asof > today:
        raise RuntimeError("Retail margin snapshot has a future data date")
    # Only require today's ratio when an independent *same-day* formal market
    # snapshot exists, and enough post-close time has elapsed for source reports.
    if local.time() >= CUTOFF and market.get("dataDate") == today:
        if asof != today:
            raise RuntimeError(
                f"Retail margin stale after close: official market={today}, margin={asof}"
            )
        if not isinstance(rows[-1].get("overall"), (int, float)):
            raise RuntimeError("Same-day all-market margin ratio missing; TPEx may be unavailable")
    return asof


def main():
    retail = json.loads((ROOT / "docs/data/retail_survival/latest.json").read_text("utf-8"))
    market = json.loads((ROOT / "docs/data/latest.json").read_text("utf-8"))
    asof = validate(retail, market, datetime.now(TZ))
    print("RET_SURVIVAL_FRESHNESS_OK", asof, "market", market.get("dataDate"))


if __name__ == "__main__":
    main()
