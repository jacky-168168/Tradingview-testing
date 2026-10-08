"""Multi-day OHLC for TW stock daily bars.
Fixed 3D/18D bars restart with the exchange session count at Jan 1, matching
TradingView's documented multi-day anchoring convention. Incomplete 2026 bars
are tagged forming, never treated as confirmed engulfing candles.
"""
from __future__ import annotations
import numpy as np,pandas as pd

def _getfloat(v):
    try:
        x=float(v)
        return x if np.isfinite(x) else None
    except (TypeError,ValueError):return None

def aggregate_bars(daily,exchange_dates,period):
    if period<1:raise ValueError("period must be >=1")
    if daily is None or daily.empty:return pd.DataFrame()
    cal=sorted(set(str(x)[:10] for x in exchange_dates))
    if not cal:return pd.DataFrame()
    mapping={};years={}
    for d in cal:years.setdefault(d[:4],[]).append(d)
    for year,dates in years.items():
        for i,d in enumerate(dates):mapping[d]=(int(year),i//period)
    z=daily.copy();z["date"]=z["date"].astype(str).str[:10]
    z=z[z["date"].isin(mapping)].sort_values("date").drop_duplicates("date",keep="last")
    if z.empty:return pd.DataFrame()
    z["group"]=z["date"].map(mapping)
    result=[]
    for (year,g),v in z.groupby("group",sort=True):
        ds=years[str(year)];start=g*period;end=min(start+period,len(ds))
        if start>=len(ds):continue
        observed_dates=set(v.date)
        expected=ds[start:end]
        complete=len(expected)==period and all(d in observed_dates for d in expected)
        # Dec 31 necessarily finalizes a short bar, unlike a still-running current year.
        if len(expected)<period and int(year)<max(int(y) for y in years):
            complete=all(d in observed_dates for d in expected)
        o=_getfloat(v.open.iloc[0]);c=_getfloat(v.close.iloc[-1]);h=_getfloat(pd.to_numeric(v.high,errors="coerce").max());l=_getfloat(pd.to_numeric(v.low,errors="coerce").min())
        if None in (o,c,h,l):continue
        result.append({"year":year,"group":g,"date":str(v.date.iloc[-1]),"startDate":expected[0],"expectedEnd":expected[-1],"open":o,"high":h,"low":l,"close":c,"volume":float(pd.to_numeric(v.volume,errors="coerce").fillna(0).sum()),"sessions":len(v),"expectedSessions":len(expected),"complete":bool(complete)})
    return pd.DataFrame(result).sort_values(["year","group"]).reset_index(drop=True)

def candle_test(previous,current):
    if previous is None or current is None:return None
    p0,p1=float(previous["open"]),float(previous["close"])
    c0,c1=float(current["open"]),float(current["close"])
    prev_red=p1<p0;now_green=c1>c0
    strict=bool(prev_red and now_green and c0<=p1 and c1>=p0)
    full=bool(prev_red and now_green and float(current["high"])>=float(previous["high"]) and float(current["low"])<=float(previous["low"]))
    reversal=bool(prev_red and now_green and c1>=(p0+p1)/2 and c1>p1)
    # In this market a 'red' bullish candle is close > open.
    return {"prevBear":bool(prev_red),"nowBull":bool(now_green),"bodyEngulf":strict,"rangeEngulf":full,"halfRecover":reversal,"lastBodyPct":round((c1/c0-1)*100,3) if c0 else None}

def latest_pair(bars,asof,require_complete=True):
    if bars is None or bars.empty:return (None,None)
    z=bars[bars["date"].astype(str)<=asof]
    if require_complete:z=z[z.complete]
    if len(z)<2:return (None,None)
    p=z.iloc[-2].to_dict();c=z.iloc[-1].to_dict()
    return p,c

def rel_pct(v,base):
    return round((float(v)/float(base)-1)*100,3) if base and float(base)!=0 else None
