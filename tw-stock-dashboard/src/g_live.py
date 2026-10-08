"""Daily G_DOUBLE_PERSIST dashboard selection, matching 2026 G backtest structures.
- Cross-sectional percentiles are computed across ALL active listed/OTC shares.
- The candidate pool is strong-momentum G (not D and no 500B cap).
- 3D and 18D high breaks use COMPLETE year-anchored bars only.
- Persistence is computed using original double-break Top20 lists for PREVIOUS
  exchange sessions; today cannot boost itself or generate future leakage.
- G is a daily close watchlist, not an intraday triggered trading system.
"""
from __future__ import annotations
import bisect,json
from datetime import datetime
import numpy as np,pandas as pd
from config import DATA_DIR,MIN_PRICE,TOP_N
from scoring import calc_metrics
from yahoo_cache import to_symbol
from multi_day_candles import aggregate_bars,candle_test
from g_persistence import persistence_features,pocket_snapshot
from g_target import eligible as g_eligible

G_MODEL="G_DOUBLE_PERSIST"
FEATURES=("ret20","ma20Slope","atrPct","range20Pct","turnoverB")
PCTS=("ret20P","slopeP","atrP","range20P","turnoverP")
def g_score(x):
    near=max(0.,min(100.,100.+float(x["breakoutPct"])/18.*100.))
    return round((30*x["ret20P"]+25*x["slopeP"]+10*x["atrP"]+15*x["range20P"]+15*x["turnoverP"]+5*near)/100,4)

def _float(v):
    try:
        n=float(v)
        return n if np.isfinite(n) else None
    except (TypeError,ValueError):return None

def _previous_structure(bars,day,close):
    if bars.empty:return {"bull":False,"eng":False,"break":False,"priorHigh":None}
    completed=bars[bars.complete & (bars.date.astype(str)<=day)]
    if completed.empty:return {"bull":False,"eng":False,"break":False,"priorHigh":None}
    latest=completed.iloc[-1].to_dict()
    previous=completed.iloc[-2].to_dict() if len(completed)>=2 else None
    # At a completed HTF close, comparison is with the preceding HTF high.
    # During a forming bar, comparison is with the latest CONFIRMED bar high.
    reference=previous if latest["date"]==day else latest
    engulf=candle_test(previous,latest) if previous else None
    return {"bull":bool(latest["close"]>latest["open"]),"eng":bool(engulf and engulf["bodyEngulf"]),
            "break":bool(reference and close>float(reference["high"])),
            "priorHigh":round(float(reference["high"]),4) if reference else None}

def latest_structure(df,year_calendar,day,close):
    year=df[df.date.astype(str).str.startswith(day[:4])].copy()
    if year.empty:return {"bull3":False,"eng3":False,"break3":False,"bull18":False,"eng18":False,"break18":False}
    result={}
    for n in (3,18):
        bars=aggregate_bars(year,year_calendar,n)
        state=_previous_structure(bars,day,close)
        result.update({f"bull{n}":state["bull"],f"eng{n}":state["eng"],f"break{n}":state["break"],f"prior{n}High":state["priorHigh"]})
    return result

def prior_pockets(data_dir,year_calendar,day,lookback=10):
    """Only previous exchange sessions. Missing snapshots count as empty, not recency-compressed."""
    prev=[d for d in year_calendar if d<day][-lookback:]
    out=[];found=0
    for d in prev:
        p=data_dir/"daily"/f"{d}.json"
        try:
            snapshot=json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
            rows=snapshot.get("gPocketBaseline")
            if not isinstance(rows,list):out.append({});continue
            daymap={}
            for row in rows:
                code=str(row.get("code") or "");rank=row.get("rank");score=row.get("baselineScore")
                if code and rank is not None and score is not None and code not in daymap:
                    daymap[code]={"rank":int(rank),"score":float(score)}
            out.append(daymap);found+=1
        except (ValueError,TypeError,OSError):out.append({})
    return out,found

def select(universe,histories,market_days,asof,inst=None,previous_pockets=None,known_metrics=None,market_ret20=0.):
    """Returns (top20, original_top20_snapshot, metadata). Never substitutes D for G."""
    days=sorted(set(str(d)[:10] for d in market_days if str(d)[:4]==asof[:4] and str(d)[:10]<=asof))
    if not days or days[-1]!=asof:raise ValueError("G benchmark calendar does not contain selected market date")
    inst=inst or {};known_metrics=known_metrics or {};rows=[];frames={}
    for s in universe:
        sy=to_symbol(s["code"],s["market"]);h=histories.get(sy)
        if h is None or len(h)<60:continue
        h=h.sort_values("date").drop_duplicates("date",keep="last")
        if str(h.date.iloc[-1])[:10]!=asof:continue
        m=known_metrics.get(sy)
        if m is None:m=calc_metrics(h.tail(75))
        if m is None:continue
        close=_float(m.get("close"));volume=_float(m.get("volume"));ret20=_float(m.get("ret20"));slope=_float(m.get("ma20Slope"));atr=_float(m.get("atrPct"));br=_float(m.get("breakoutPct"))
        low=_float(pd.to_numeric(h.low.iloc[-20:],errors="coerce").min());high=_float(pd.to_numeric(h.high.iloc[-20:],errors="coerce").max())
        if any(z is None for z in (close,volume,ret20,slope,atr,br,low,high)) or close<=0 or volume<=0 or low<=0:continue
        cap=_float(s.get("capitalB")) or 0.
        if cap<=0:continue
        turn=close*volume/100_000_000
        ii=inst.get(f'{s["market"]}_{s["code"]}',{})
        rows.append({"code":s["code"],"name":s["name"],"market":s["market"],"industry":s.get("industry",""),
                     "capitalB":cap,"close":close,"currentPrice":None,"currentPct":None,
                     "ret20":ret20,"ret5":_float(m.get("ret5")) or 0.,"ma20Slope":slope,
                     "atrPct":atr,"range20Pct":(high/low-1)*100,"turnoverB":turn,
                     "breakoutPct":br,"volume":volume,"rvol":_float(m.get("rvol")) or 0.,
                     "rvol10":_float(m.get("rvol10")) or 0.,"mom10Pct":_float(m.get("mom10Pct")) or 0.,
                     "dayRet":_float(m.get("dayRet")) or 0.,"volD":_float(m.get("volD")) or 0.,
                     "foreignToday":round(float(ii.get("foreign",0) or 0)/1000,1),
                     "trustToday":round(float(ii.get("trust",0) or 0)/1000,1)})
        frames[sy]=h
    if not rows:raise RuntimeError("G has no valid same-day market candles; refuse stale/synthetic pocket")
    df=pd.DataFrame(rows)
    for raw,percentile in zip(FEATURES,PCTS):df[percentile]=df[raw].rank(pct=True,method="average")*100
    strong=[]
    for r in df.to_dict("records"):
        if not g_eligible(r):continue
        r["baselineScore"]=g_score(r)
        strong.append(r)
    qualified=[]
    for r in strong:
        sy=to_symbol(r["code"],r["market"])
        f=latest_structure(frames[sy],days,asof,float(r["close"]))
        if not (f["break3"] and f["break18"]):continue
        r["gFlags"]=f
        qualified.append(r)
    qualified.sort(key=lambda x:(-x["baselineScore"],x["code"]))
    old_snapshot=[{"code":x["code"],"rank":i+1,"baselineScore":x["baselineScore"]} for i,x in enumerate(qualified[:TOP_N])]
    old_snapshot_codes={x["code"] for x in old_snapshot}
    if previous_pockets is None:previous_pockets=[]
    ranked=[]
    for r in qualified:
        persistence=persistence_features(r["code"],previous_pockets,r["baselineScore"])
        total=round(r["baselineScore"]+persistence["bonus"],4)
        signal="🔥 G雙突破持續強勢" if persistence["past10Top20"]>=4 else "🚀 G雙突破開始轉強" if persistence["past10Top20"]>=1 else "🆕 G雙突破新入選"
        ranked.append({**r,"model":"G","gVariant":G_MODEL,"total":total,"persistence":persistence,
                       "gScore":r["baselineScore"],"gExtra":persistence["bonus"],
                       "gPast10":persistence["past10Top20"],"gPast5Top3":persistence["past5Top3"],"gStreak":persistence["priorStreak"],
                       "gBreak3":bool(r["gFlags"]["break3"]),"gBreak18":bool(r["gFlags"]["break18"]),
                       "sarBonus":0,"sarText":"尚未計算","strictPass":True,"candidateTier":"G雙突破","signal":signal,
                       "rs20":r["ret20"]-market_ret20,"theme":r["industry"]})
    ranked.sort(key=lambda x:(-x["total"],-x["gScore"],x["code"]))
    return ranked[:TOP_N],old_snapshot,{"variant":G_MODEL,"source":"live-year-anchored-market-OHLC",
           "dataDate":asof,"percentileUniverse":len(rows),"strongCandidates":len(strong),"doubleBreakCandidates":len(qualified),
           "pocketPreviousDays":len(previous_pockets),"note":"每日完整收盤 G 雙突破＋持續度；所有入選分數使用截至資料日的 K 線，持續度只使用先前交易日的原始 G 雙突破 Top20。無盤中 BOTTOM／TOP 觸發。"}
