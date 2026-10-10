"""Pure as-of-close consolidation-to-early-breakout screener.
Candidate FIRST; ranking SECOND. Does NOT inherit original G momentum gate.
All reference ranges/volume baselines shifted >=1 trading session, and
market-index RS uses its same-date historic index close, never future data.
Four locked ideas, intentionally not post-hoc optimized on 2026 results.
"""
from __future__ import annotations
import math
import numpy as np,pandas as pd
from yahoo_cache import to_symbol
FAMILIES=("Box15 Breakout","Box10 Tight Breakout","Box20 Prebreak","Squeeze Release")
RULES={
 "Box15 Breakout":{"priorBox":"15D","maxPriorRangePct":18,"maxPrior5RangePct":10,"minimumRVOL":1.25,"maxBreakoutPct":3.5,"maxAboveMA20Pct":13,"minRS20Pct":0},
 "Box10 Tight Breakout":{"priorBox":"10D","maxPriorRangePct":12,"maxPrior5RangePct":7,"minimumRVOL":1.5,"maxBreakoutPct":4,"maxAboveMA20Pct":11,"minRS20Pct":0},
 "Box20 Prebreak":{"priorBox":"20D","maxPriorRangePct":18,"maxPrior5RangePct":10,"minimumRVOL":1.30,"rangeToHigh":[-2.5,1],"maxAboveMA20Pct":11,"minRS20Pct":0},
 "Squeeze Release":{"priorBox":"20D","maxPriorRangePct":24,"maxPrior5RangePct":10,"minimumRVOL":1.40,"maxBreakoutPct":4,"maxAboveMA20Pct":14,"minRS20Pct":-2}}
def asof_features(hist,market_20d_returns):
    """Vectorized features; each row uses only values through its own date.
    Pre-signal ranges and volume compare against dates strictly BEFORE row D.
    market_20d_returns are date keyed index returns calculated using <=D.
    """
    q=hist.sort_values("date").drop_duplicates("date",keep="last").copy()
    if len(q)<70:return pd.DataFrame()
    for col in ("open","high","low","close","volume"):q[col]=pd.to_numeric(q[col],errors="coerce")
    c=q.close;v=q.volume;hi=q.high;lo=q.low;prevhi=hi.shift(1);prevlo=lo.shift(1)
    q["dayPct"]=(c/c.shift(1)-1)*100
    q["ret20Pct"]=(c/c.shift(20)-1)*100
    q["index20Pct"]=q.date.astype(str).map(market_20d_returns)
    q["rs20"]=q.ret20Pct-q.index20Pct
    ma10=c.rolling(10,min_periods=10).mean();ma20=c.rolling(20,min_periods=20).mean()
    q["ma10"]=ma10;q["ma20"]=ma20;q["aboveMa20Pct"]=(c/ma20-1)*100
    q["vol20Prior"]=v.shift(1).rolling(20,min_periods=20).mean()
    q["rvol"]=v/q.vol20Prior.replace(0,np.nan)
    q["turnoverB"]=c*v/1e8
    q["prev5RangePct"]=(prevhi.rolling(5,min_periods=5).max()/prevlo.rolling(5,min_periods=5).min()-1)*100
    for n in (10,15,20):
        q[f"prev{n}High"]=prevhi.rolling(n,min_periods=n).max()
        q[f"prev{n}Low"]=prevlo.rolling(n,min_periods=n).min()
        q[f"prev{n}RangePct"]=(q[f"prev{n}High"]/q[f"prev{n}Low"]-1)*100
        q[f"break{n}Pct"]=(c/q[f"prev{n}High"]-1)*100
    q["wasBelowPrior15High"]=c.shift(1)<=hi.shift(2).rolling(15,min_periods=15).max()*1.005
    q["wasBelowPrior10High"]=c.shift(1)<=hi.shift(2).rolling(10,min_periods=10).max()*1.005
    q["wasBelowPrior20High"]=c.shift(1)<=hi.shift(2).rolling(20,min_periods=20).max()*1.005
    return q
def classify_frame(q):
    """Return 4 boolean masks for distinct setups. Thresholds are frozen."""
    if q.empty:return {name:pd.Series(dtype=bool) for name in FAMILIES}
    # Keep enough turnover to trade roughly 200k tickets; don't chase a daily
    # near-limit-up candle. All information is visible at D close.
    common=(q.close>=10)&(q.turnoverB>=.8)&(q.volume>0)&(q.rvol.notna())&q.rs20.notna()
    common&=q.dayPct.between(.3,7.8)&q.ret20Pct.between(-10,20)
    common&=(q.close>q.ma10)&(q.close>q.ma20)&(q.rs20>=-2)
    b15=(common&(q.prev15RangePct.between(2,18))&(q.prev5RangePct<=10)&
         (q.rvol>=1.25)&(q.rs20>=0)&q.break15Pct.between(.05,3.5)&
         (q.aboveMa20Pct<=13)&q.wasBelowPrior15High)
    b10=(common&(q.prev10RangePct.between(1,12))&(q.prev5RangePct<=7)&
         (q.rvol>=1.5)&(q.rs20>=0)&q.break10Pct.between(.05,4)&
         (q.aboveMa20Pct<=11)&q.wasBelowPrior10High)
    near20=(common&(q.prev20RangePct.between(2,18))&(q.prev5RangePct<=10)&
         (q.rvol>=1.3)&(q.rs20>=0)&q.break20Pct.between(-2.5,1)&
         (q.aboveMa20Pct<=11)&(q.dayPct>=1)&q.wasBelowPrior20High)
    squeeze=(common&(q.prev20RangePct.between(4,24))&(q.prev5RangePct<=10)&
         (q.prev5RangePct<=q.prev20RangePct*.55)&(q.rvol>=1.4)&
         q.break10Pct.between(.05,4)&(q.aboveMa20Pct<=14)&
         q.wasBelowPrior10High)
    return {"Box15 Breakout":b15.fillna(False),"Box10 Tight Breakout":b10.fillna(False),
            "Box20 Prebreak":near20.fillna(False),"Squeeze Release":squeeze.fillna(False)}
def rank_stock(row,family):
    """Only target known-at-close features, NOT future target-hit labels."""
    rvol=float(row["rvol"]);rs=float(row["rs20"]);box=float(row["boxRangePct"])
    amplitude=float(row["breakoutPct"]);d=float(row["dayPct"])
    # 30% early volume ignition, 25% relative-market strength, 20% tightness,
    # 15% appropriate early break position, 10% trading liquidity.
    vol=min(max((rvol-1)/2,0),1)*30
    rel=min(max((rs+2)/14,0),1)*25
    tight=max(0,1-box/(18 if family!="Box10 Tight Breakout" else 12))*20
    if family=="Box20 Prebreak":
        price=max(0,1-abs(amplitude+0.25)/3)*15
    else:price=max(0,1-abs(amplitude-1.0)/4)*15
    turnover=min(math.log1p(max(float(row["turnoverB"]),0))/math.log1p(15),1)*10
    return round(vol+rel+tight+price+turnover,4)
def historical_candidates(hist,universe,market_returns,dates):
    """Independent full-universe scan. Returns ranked eligible Top1 per family,
    small per-day Top3 audit and counts. No original-G eligibility prefilter.
    """
    collect={k:{} for k in FAMILIES};counts={k:0 for k in FAMILIES}
    date_set=set(dates);valid_symbols=0
    for i,info in enumerate(universe,1):
        sy=to_symbol(info["code"],info["market"]);data=hist.get(sy)
        if data is None or data.empty:continue
        f=asof_features(data,market_returns)
        if f.empty:continue
        valid_symbols+=1
        flags=classify_frame(f)
        for family,mask in flags.items():
            picked=f[mask&(f.date.astype(str).isin(date_set))]
            if picked.empty:continue
            n=20 if family in ("Box15 Breakout","Squeeze Release") else 10 if family=="Box10 Tight Breakout" else 20
            for z in picked.itertuples(index=False):
                d=str(z.date);row={"date":d,"sym":sy,"code":str(info["code"]),"name":str(info["name"]),"market":str(info["market"]),
                    "close":float(z.close),"rvol":round(float(z.rvol),3),"rs20":round(float(z.rs20),3),
                    "dayPct":round(float(z.dayPct),3),"ret20Pct":round(float(z.ret20Pct),3),
                    "boxRangePct":round(float(getattr(z,f"prev{n}RangePct")),3),
                    "breakoutPct":round(float(getattr(z,f"break{n}Pct")),3),
                    "turnoverB":round(float(z.turnoverB),3)}
                row["score"]=rank_stock(row,family)
                collect[family].setdefault(d,[]).append(row)
                counts[family]+=1
        if i%450==0:print("EARLY_SETUP_SCAN",i,"/",len(universe),"symbolsValid",valid_symbols,flush=True)
    top1={};audits={}
    for family in FAMILIES:
        top1[family]={};audits[family]={}
        for d in dates:
            ranked=sorted(collect[family].get(d,[]),key=lambda x:(-x["score"],x["code"]))
            top1[family][d]=[ranked[0]] if ranked else []
            audits[family][d]=ranked[:3]
    return top1,audits,{"symbolsScanned":valid_symbols,"candidateStockDays":counts,
                       "daysWithSignals":{k:sum(bool(x) for x in v.values()) for k,v in top1.items()}}
