"""2026 posted signals: check 1D, true 3D and 18D bullish engulfing and entry/stop geometry."""
from __future__ import annotations
import json,math
from collections import defaultdict
from datetime import datetime
from zoneinfo import ZoneInfo
import numpy as np,pandas as pd
from config import DATA_DIR,BENCHMARK
from pipeline import load_universe
from yahoo_cache import update_symbol,to_symbol
from research_signal_samples import SAMPLES
from multi_day_candles import aggregate_bars,candle_test,latest_pair,rel_pct

def rd(z,k):
    try:
        v=z.get(k)
        return round(float(v),4) if v is not None and math.isfinite(float(v)) else None
    except:return None

def candle_record(previous,current,sample,verified):
    if current is None:return None
    d=candle_test(previous,current)
    return {"barDate":current["date"],"barStartDate":current.get("startDate",current["date"]),"barExpectedEnd":current.get("expectedEnd",current["date"]),"barComplete":verified,"open":rd(current,"open"),"high":rd(current,"high"),"low":rd(current,"low"),"close":rd(current,"close"),"prevOpen":rd(previous,"open") if previous else None,"prevHigh":rd(previous,"high") if previous else None,"prevLow":rd(previous,"low") if previous else None,"prevClose":rd(previous,"close") if previous else None,"candles":d,"entryVsHighPct":rel_pct(sample["entry"],current["high"]),"entryVsClosePct":rel_pct(sample["entry"],current["close"]),"stopVsLowPct":rel_pct(sample["stop"],current["low"]),"entryVsPrevHighPct":rel_pct(sample["entry"],previous["high"]) if previous else None,"stopVsPrevLowPct":rel_pct(sample["stop"],previous["low"]) if previous else None}

def trailing_daily(daily,asof):
    z=daily[daily.date.astype(str)<=asof].sort_values("date")
    if len(z)<2:return (None,None)
    return (z.iloc[-2].to_dict(),z.iloc[-1].to_dict())

def build():
    uni={str(x["code"]):x for x in load_universe()}
    _,market,ie=update_symbol(BENCHMARK,datetime(2025,1,1),datetime(2026,10,8))
    if ie or market is None or market.empty:raise RuntimeError(f"market unavailable: {ie}")
    market_dates=sorted(set(market.date.astype(str)))
    samples=[];errors={}
    for s in SAMPLES:
        info=uni.get(s["code"])
        if info is None:
            samples.append({**s,"error":"not in universe"});continue
        sy=to_symbol(s["code"],info["market"])
        _,daily,e=update_symbol(sy,datetime(2025,1,1),datetime(2026,10,8))
        if e or daily is None or daily.empty:
            errors[sy]=e or "no OHLC";samples.append({**s,"error":errors[sy]});continue
        anchors=[d for d in market_dates if d<s["date"]]
        if not anchors:continue
        anchor=anchors[-1]
        daily=daily.sort_values("date").reset_index(drop=True)
        last_d=trailing_daily(daily,anchor)
        out={**s,"name":info["name"],"market":info["market"],"anchorDate":anchor,"anchorPolicy":"last completed exchange session before post date"}
        out["D"]=candle_record(*last_d,s,True)
        for n in (3,18):
            bars=aggregate_bars(daily[daily.date.astype(str)<=anchor],market_dates,n)
            cp,cc=latest_pair(bars,anchor,True)
            fp,fc=latest_pair(bars,anchor,False)
            out[f"{n}DConfirmed"]=candle_record(cp,cc,s,True)
            out[f"{n}DLatest"]=candle_record(fp,fc,s,bool(fc and fc["complete"]))
            out[f"{n}DLatestIsForming"]=bool(fc and not fc["complete"])
            out[f"{n}DLastCompleteDate"]=cc["date"] if cc else None
            out[f"{n}DGreenTrend"]=bool(cp and cc and cc["close"]>cp["close"])
        samples.append(out)
    fields=["D","3DConfirmed","3DLatest","18DConfirmed","18DLatest"]
    summary={}
    for k in fields:
        v=[x[k] for x in samples if x.get(k) is not None]
        cnt=lambda test:sum(bool(test(x)) for x in v)
        entry_near=lambda d:cnt(lambda x:x.get("entryVsHighPct") is not None and abs(x["entryVsHighPct"])<=d)
        summary[k]={"n":len(v),"bullEngulfBody":cnt(lambda x:(x.get("candles") or {}).get("bodyEngulf")),"bullEngulfRange":cnt(lambda x:(x.get("candles") or {}).get("rangeEngulf")),"bullHalfRecover":cnt(lambda x:(x.get("candles") or {}).get("halfRecover")),"green":cnt(lambda x:(x.get("candles") or {}).get("nowBull")),"entryWithin2pctHigh":entry_near(2),"entryWithin5pctHigh":entry_near(5),"entryAboveHigh":cnt(lambda x:x.get("entryVsHighPct") is not None and x["entryVsHighPct"]>=0),"entryAbovePrevHigh":cnt(lambda x:x.get("entryVsPrevHighPct") is not None and x["entryVsPrevHighPct"]>=0)}
    summary["combo"]={"threeDConfirmedBodyAnd18DTrend":sum(bool(x.get("3DConfirmed") and (x["3DConfirmed"].get("candles") or {}).get("bodyEngulf") and x.get("18DGreenTrend")) for x in samples),"threeDLatestBodyAnd18DTrend":sum(bool(x.get("3DLatest") and (x["3DLatest"].get("candles") or {}).get("bodyEngulf") and x.get("18DGreenTrend")) for x in samples),"threeDConfirmedBodyOr18DConfirmedBody":sum(bool((x.get("3DConfirmed") and (x["3DConfirmed"].get("candles") or {}).get("bodyEngulf")) or (x.get("18DConfirmed") and (x["18DConfirmed"].get("candles") or {}).get("bodyEngulf"))) for x in samples),"threeDForming":sum(bool(x.get("3DLatestIsForming")) for x in samples),"eighteenDForming":sum(bool(x.get("18DLatestIsForming")) for x in samples)}
    out={"version":"G-3D-18D-ENGULF-RESEARCH-2026-V1","generatedAt":datetime.now(ZoneInfo("Asia/Taipei")).isoformat(timespec="seconds"),"method":{"alignment":"TradingView-like year-reset non-overlapping N exchange sessions; single-symbol suspended days marked non-complete","dataCut":"last completed trading day strictly prior to posted date; no post intraday OHLC, no future bars","redEngulf":"bullish candle real body fully wraps previous bearish candle real body","fullRangeEngulf":"bullish candle high >= previous high AND low <= previous low AND previous bearish","formingBars":"displayed only as provisional, NEVER confirmed before all N sessions close","caveat":"Yahoo 1D aggregation approximates TradingView 3D/18D, session differences and corporate adjustments possible"},"samples":samples,"summary":summary,"historyErrors":errors}
    p=DATA_DIR/"research";p.mkdir(parents=True,exist_ok=True)
    (p/"g_multiday_2026.json").write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding="utf-8")
    rows=[]
    for x in samples:
        row={"code":x["code"],"name":x.get("name"),"postDate":x["date"],"postTime":x.get("time"),"anchorDate":x.get("anchorDate"),"entry":x["entry"],"stop":x["stop"]}
        for k in fields:
            q=x.get(k) or {};flags=q.get("candles") or {}
            for f in ("barDate","barComplete","high","low","entryVsHighPct","entryVsPrevHighPct"):row[f"{k}_{f}"]=q.get(f)
            for f in ("nowBull","bodyEngulf","rangeEngulf","halfRecover"):row[f"{k}_{f}"]=flags.get(f)
        rows.append(row)
    pd.DataFrame(rows).to_csv(p/"g_multiday_2026.csv",index=False,encoding="utf-8-sig")
    print(json.dumps({"n":len(samples),"summary":summary,"errors":errors},ensure_ascii=False),flush=True)
    return out
if __name__=="__main__":build()
