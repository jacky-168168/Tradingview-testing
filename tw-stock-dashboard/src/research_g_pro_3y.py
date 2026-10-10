"""Frozen G Pro strict subset versus unchanged G Top3 over verified 2023-2026 daily records.
G Pro uses only signals among G's genuine close-D Top3; no fallback to rank 4+.
No historical institution net series exists here, so no fictitious foreign-buy gate.
Parameters are predeclared before any new G Pro performance file is produced.
"""
from __future__ import annotations
import argparse,collections,json,math,time
from datetime import datetime,timedelta
from zoneinfo import ZoneInfo
import numpy as np
import pandas as pd
from config import DATA_DIR,BENCHMARK
from pipeline import load_universe
from yahoo_cache import update_many,update_symbol,to_symbol
from research_g_regime_3y import START,END,COST,make_g,get_risk,stock_ret,finite
OUT=DATA_DIR/"research"/"g_pro_3y"
HORIZONS=(1,5,10,20)
THRESHOLDS=(50,55,60,65,70,75,80)
BUY_FEE=0.001425
SELL_FEE=0.004425
SPLITS={"train":("2023-10-09","2024-12-31"),"validation":("2025-01-01","2025-12-31"),"holdout":("2026-01-01","2026-10-08")}
G_PRO_RULES={"ret20PercentileMin":75,"ma20SlopePercentileMin":80,"turnoverPercentileMin":75,"prior10DaysOriginalGTop20Min":2,"relativeVolumeVsPrevious20Min":1.3,"closeAboveEma20":True,"ema20AboveEma60":True,"maxCloseToEma20":1.15}
def build_daily_indicators(hist,symbols):
    indicators={}
    for sy in symbols:
        h=hist.get(sy)
        if h is None or h.empty:continue
        q=h.sort_values("date").drop_duplicates("date").copy()
        c=pd.to_numeric(q["close"],errors="coerce")
        v=pd.to_numeric(q["volume"],errors="coerce")
        e20=c.ewm(span=20,adjust=False,min_periods=60).mean()
        e60=c.ewm(span=60,adjust=False,min_periods=60).mean()
        volbase=v.shift(1).rolling(20,min_periods=20).mean()
        rv=v/volbase.replace(0,np.nan)
        indicators[sy]={str(d):{"ema20":finite(a),"ema60":finite(b),"rvol":finite(z)}
            for d,a,b,z in zip(q["date"].astype(str),e20,e60,rv)}
    return indicators
def pro_pass(stock,record):
    if record is None:return False,"missing_indicators"
    c=finite(stock.get("close"));m20=record.get("ema20");m60=record.get("ema60")
    if c is None or m20 is None or m60 is None or m20<=0 or m60<=0:return False,"missing_indicators"
    if finite(stock.get("ret20P")) is None or stock["ret20P"]<G_PRO_RULES["ret20PercentileMin"]:return False,"ret20"
    if finite(stock.get("slopeP")) is None or stock["slopeP"]<G_PRO_RULES["ma20SlopePercentileMin"]:return False,"ma20slope"
    if finite(stock.get("turnoverP")) is None or stock["turnoverP"]<G_PRO_RULES["turnoverPercentileMin"]:return False,"turnover"
    if int(stock.get("previousTop20") or 0)<G_PRO_RULES["prior10DaysOriginalGTop20Min"]:return False,"persistence"
    if (record.get("rvol") or 0)<G_PRO_RULES["relativeVolumeVsPrevious20Min"]:return False,"rvol"
    if not(c>m20>m60):return False,"ema_trend"
    if c/m20>G_PRO_RULES["maxCloseToEma20"]:return False,"overextended"
    return True,"passed"
def compact_stats(values):
    a=np.asarray([x for x in values if x is not None and math.isfinite(x)],dtype=float)
    return {"n":int(len(a)),"winPct":round(float((a>0).mean()*100),2) if len(a) else None,
            "meanNetPct":round(float(a.mean()*100),3) if len(a) else None,
            "medianNetPct":round(float(np.median(a)*100),3) if len(a) else None,
            "meanWinPct":round(float(a[a>0].mean()*100),3) if np.any(a>0) else None,
            "meanLossPct":round(float(a[a<0].mean()*100),3) if np.any(a<0) else None}
def daily_bar(prices,stock,date,col):
    p=prices.get(stock["sym"])
    if p is None or date not in p.index:return None
    row=p.loc[date]
    if isinstance(row,pd.DataFrame):row=row.iloc[-1]
    return finite(row[col])
def simulate_cash(dates,picks,prices,risk,thresh,h):
    """One fully funded basket at a time; fractional units, no leverage, no overlapping capital.
    Signals known at D close; next-session open; daily adjusted-close mark-to-market.
    Each basket exits at D+h close (delayed when price is unquoted).
    A missing daily quote is carried forward and disclosed, never interpolated for a new trade.
    """
    cash=1_000_000.;positions=[];pending=None;peak=cash;mdd=0.;curve=[];deals=[]
    skipped=collections.Counter();staleMarks=0;deferredExits=0
    for i,d in enumerate(dates):
        if pending and pending["buyIndex"]==i:
            rows=pending["stocks"];p=pending;pending=None
            openings=[daily_bar(prices,s,d,"adjOpen") for s in rows]
            if positions or len(openings)!=len(rows) or not rows or any(x is None or x<=0 for x in openings):
                skipped["missing_open_or_busy"]+=1
            else:
                capital=cash/len(rows)
                positions=[{"stock":s,"units":capital/(op*(1+BUY_FEE)),"invested":capital,
                            "entry":d,"signalDate":p["signalDate"],"exitIndex":p["exitIndex"],
                            "lastPrice":op,"entryOpen":op} for s,op in zip(rows,openings)]
                cash=0.
        remaining=[]
        for pos in positions:
            px=daily_bar(prices,pos["stock"],d,"adjClose")
            if px is None or px<=0:
                px=pos["lastPrice"];staleMarks+=1
                if i>=pos["exitIndex"]:deferredExits+=1
                remaining.append(pos);continue
            pos["lastPrice"]=px
            if i>=pos["exitIndex"]:
                proceeds=pos["units"]*px*(1-SELL_FEE)
                cash+=proceeds
                deals.append({"signalDate":pos["signalDate"],"buy":pos["entry"],"sell":d,
                              "code":pos["stock"]["code"],"netPct":round(100*(proceeds/pos["invested"]-1),4)})
            else:remaining.append(pos)
        positions=remaining
        equity=cash+sum(p["units"]*p["lastPrice"] for p in positions)
        peak=max(peak,equity);mdd=min(mdd,equity/peak-1.)
        curve.append({"date":d,"equity":round(equity,2),"cash":round(cash,2),"positions":len(positions)})
        if not positions and i+h<len(dates) and risk.get(d,0)>=thresh:
            sig=picks.get(d) or []
            if sig:pending={"signalDate":d,"buyIndex":i+1,"exitIndex":i+h,"stocks":sig}
    final=curve[-1]["equity"] if curve else cash
    return {"initialCapital":1_000_000,"finalEquity":final,
            "netReturnPct":round((final/1_000_000-1)*100,3),
            "dailyMaxDrawdownPct":round(mdd*100,3),
            "closedStockTrades":len(deals),"unclosedStockPositions":len(positions),
            "staleDailyMarks":staleMarks,"deferredExitDays":deferredExits,
            "skippedOrders":dict(skipped)},curve,deals
def evaluate(dates,picks,prices,risk,variant,threshold,h):
    rows=[];qualified=0
    for i,d in enumerate(dates):
        if i+h>=len(dates) or i+1>=len(dates) or risk.get(d,0)<threshold:continue
        group=picks.get(d) or []
        if not group:continue
        qualified+=1;buy=dates[i+1];sell=dates[i+h]
        returns=[stock_ret(prices,s,buy,sell) for s in group]
        if any(x is None for x in returns):continue
        net=(1+float(np.mean(returns)))*(1-COST)-1
        rows.append({"signalDate":d,"buy":buy,"sell":sell,"codes":[s["code"] for s in group],
                     "stockCount":len(group),"net":round(net,8)})
    portfolio,curve,deals=simulate_cash(dates,picks,prices,risk,threshold,h)
    splits={}
    for key,(lo,hi) in SPLITS.items():
        sample=[x["net"] for x in rows if lo<=x["signalDate"]<=hi and x["sell"]<=hi]
        splits[key]=compact_stats(sample)
    return {"model":variant,"threshold":threshold,"horizon":h,
            "qualifiedSignalDays":qualified,"executedSignalDays":len(rows),
            "signalStats":compact_stats([x["net"] for x in rows]),"byPeriod":splits,
            "portfolio":portfolio},rows,curve,deals
def main(start=START,end=END):
    now=datetime.now(ZoneInfo("Asia/Taipei"))
    if end>now.date().isoformat():raise RuntimeError("Refuse future end date")
    if (start,end)!=(START,END):raise RuntimeError("Frozen three-year period; no ad hoc changes to selection window")
    begin=time.time();OUT.mkdir(parents=True,exist_ok=True)
    universe=[x for x in load_universe() if finite(x.get("capitalB")) and float(x["capitalB"])>0]
    pullfrom=datetime.fromisoformat(start)-timedelta(days=430)
    pullto=datetime.fromisoformat(end)+timedelta(days=35)
    hist,errors=update_many([(x["code"],x["market"]) for x in universe],pullfrom,pullto)
    _,index,indexerr=update_symbol(BENCHMARK,pullfrom,pullto)
    if indexerr or index is None or index.empty:raise RuntimeError("TWII index data unavailable: "+str(indexerr))
    index=index.sort_values("date").drop_duplicates("date").reset_index(drop=True)
    dates=[d for d in index["date"].astype(str) if start<=d<=end]
    if len(dates)!=728:raise RuntimeError("Market calendar incomplete: "+str(len(dates)))
    risk,_=get_risk(index,dates)
    gpicks,prices,audit=make_g(dates,index,universe,hist)
    inds=build_daily_indicators(hist,{s["sym"] for grp in gpicks.values() for s in grp})
    ppicks={};rejections=collections.Counter()
    for d,g in gpicks.items():
        passed=[]
        for s in g:
            ok,why=pro_pass(s,inds.get(s["sym"],{}).get(d))
            rejections[why]+=1
            if ok:passed.append(s)
        ppicks[d]=passed
    if not any(ppicks.values()):raise RuntimeError("G Pro produced zero candidate days; publish no false backtest")
    summary={"version":"G_PRO_FROZEN_G_TOP3_STRICT_V1","createdAt":now.isoformat(),
             "period":{"start":start,"end":end},"riskScoredDays":len(risk),
             "rawGSignalDays":sum(bool(v) for v in gpicks.values()),
             "gProSignalDays":sum(bool(v) for v in ppicks.values()),
             "universeNow":len(universe),"stockDataErrors":len(errors),
             "originalGAudit":audit,"rules":G_PRO_RULES,"rejectionCount":dict(rejections),
             "limitations":["G Pro filters only the original G Top3, never substitutes rank4+.",
                            "Current listed universe and capital are survivorship/capital-history biased.",
                            "Historical stock prices use Yahoo adjusted-price data.",
                            "No verified per-stock historic foreign/trust series; no institutional buying gate.",
                            "TX futures night history has 0 validated coverage in the baseline and is excluded.",
                            "Daily cash portfolio uses fractional shares and no explicit market-impact/slippage.",
                            "Non-quoted held positions carry the last valuation, disclosed by staleDailyMarks.",
                            "Horizon-specific signals near each calendar-fold end excluded from fold stats.",
                            "G Pro is predeclared; do not tune using the 2026 holdout."],
             "models":[]}
    trades={"period":summary["period"],"models":[]};curves={"period":summary["period"],"models":[]}
    for h in HORIZONS:
        for threshold in THRESHOLDS:
            for variant,picks in (("G",gpicks),("G Pro",ppicks)):
                m,samples,curve,deals=evaluate(dates,picks,prices,risk,variant,threshold,h)
                summary["models"].append(m)
                trades["models"].append({"model":variant,"threshold":threshold,"horizon":h,"signals":samples,"closedStockTrades":deals})
                curves["models"].append({"model":variant,"threshold":threshold,"horizon":h,"dailyEquity":curve})
        print("G_PRO_HORIZON_DONE",h,flush=True)
    for name,obj in (("summary.json",summary),("trades.json",trades),("equity.json",curves)):
        (OUT/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2 if name=="summary.json" else None),encoding="utf-8")
    print("G_PRO_THREE_YEAR_DONE",json.dumps({"GDays":summary["rawGSignalDays"],"GProDays":summary["gProSignalDays"],"riskDays":len(risk),"elapsedSec":int(time.time()-begin)},ensure_ascii=False),flush=True)
if __name__=="__main__":
    ap=argparse.ArgumentParser();ap.add_argument("--start",default=START);ap.add_argument("--end",default=END)
    a=ap.parse_args();main(a.start,a.end)
