"""Read-only overlap study for existing G backtest trades; never rewrites cash ledger.

Filtered trade sums are NOT a capital-account strategy backtest: capital recycling,
compounding, rebalance timing and selection may materially change final results.
"""
from __future__ import annotations
import bisect
import json
import math
import statistics
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

def compute_g_overlay(catalog, taiex_prices, trades_file, executive_file, horizon=20):
    selected=json.loads(Path(executive_file).read_text(encoding="utf-8"))["selectedModel"]["id"]
    source=json.loads(Path(trades_file).read_text(encoding="utf-8"))
    models=source.get("auditedModels") or {}
    data=models.get(selected) or {}
    all_run=data.get("all") or {}
    trades=all_run.get("trades") or []
    if not trades:
        return {"status":"unavailable","reason":"Selected original G trades were not found",
                "model":selected}
    sessions=[d for d,_ in taiex_prices]
    period_start=sessions[0];period_end=sessions[-1]
    family_results={}
    for family,body in (catalog.get("studyFamilies") or {}).items():
        if not body.get("events"):continue
        windows=[]
        for event in body["events"]:
            utc=datetime.fromisoformat(event["exactUtc"].replace("Z","+00:00"))
            local=utc.astimezone(ZoneInfo("Asia/Taipei")).date()
            start=bisect.bisect_right(sessions,local)
            if start+horizon>=len(sessions):continue
            if sessions[start+horizon]<period_start or sessions[start]>period_end:continue
            windows.append((sessions[start],sessions[start+horizon]))
        if not windows:continue
        on=[];off=[]
        for trade in trades:
            try:
                day=date.fromisoformat(trade["buyDate"])
                net=float(trade["netPct"])
            except (ValueError,KeyError,TypeError):continue
            if not math.isfinite(net):continue
            if any(a<=day<=b for a,b in windows):on.append(net)
            else:off.append(net)
        enough=len(on)>=20 and len(windows)>=5
        family_results[family]={"status":"exploratory" if enough else "insufficient",
           "availableEventWindows":len(windows),
           "gTradesInsideEventWindow":len(on),"gTradesOutsideWindow":len(off),
           "meanGTradeNetPctInside":statistics.mean(on) if enough else None,
           "meanGTradeNetPctOutside":statistics.mean(off) if enough and off else None,
           "winRateInside":sum(x>0 for x in on)/len(on) if enough else None,
           "sampleWarning":"This is only a subgroup of archived trades. No re-execution, capital ledger or OOS test."}
    return {"status":"observational_only","sourceModel":selected,
       "sourceVersion":source.get("version"),
       "sourceFiles":["g_compound_3y/trades.json","g_compound_3y/executive.json"],
       "periodStart":period_start.isoformat(),"periodEnd":period_end.isoformat(),
       "eventHorizonTradingSessions":horizon,"modelNotModified":True,
       "sampleOutOfSample":"none; pre-existing G backtest may be model selected",
       "noTradingSignal":True,"families":family_results,
       "warning":"Do not compare subgroup mean ticket profit with fully invested portfolio CAGR. To verify a G+astrology filter, rerun full G cash-ledger execution with predeclared chronological OOS."}
