"""H2 research-only 2026 event study: no A/D/F/G signals or ranks read.
Precommitted criteria are in h_v2.py; no tuning or reruns after inspecting outcomes.
"""
from __future__ import annotations
import json,time
from datetime import datetime,timedelta
from pathlib import Path
from collections import defaultdict
from zoneinfo import ZoneInfo
import numpy as np,pandas as pd
from config import DATA_DIR
from pipeline import load_universe
from yahoo_cache import update_many,update_symbol,to_symbol
from h_v2 import indicators,exit_trade,SPEC
START="2026-01-01";END="2026-10-07";HORIZONS=(1,3,5,10,20);TOP_N=3
def stats(vals):
    xs=[float(x) for x in vals if x is not None and np.isfinite(float(x))]
    good=[x for x in xs if x>0];bad=[x for x in xs if x<0]
    return {"n":len(xs),"average":round(float(np.mean(xs)),3) if xs else None,
            "median":round(float(np.median(xs)),3) if xs else None,
            "winPct":round(sum(x>0 for x in xs)/len(xs)*100,2) if xs else None,
            "positiveN":len(good),"positiveAvg":round(float(np.mean(good)),3) if good else None,
            "negativeN":len(bad),"negativeAvg":round(float(np.mean(bad)),3) if bad else None}
def build_signals(hist,universe,signal_dates):
    pool=defaultdict(list)
    cov={"stockUniverse":len(universe),"validCapital":0,"validHistory":0,"stockSignalEvents":0,"signalsDays":0,"maxCandidates":0,"meanCandidates":0}
    for i,x in enumerate(universe):
        c=float(x.get("capitalB") or 0)
        if c<=0:continue
        cov["validCapital"]+=1
        sym=to_symbol(x["code"],x["market"]);df=hist.get(sym)
        if df is None or len(df)<95:continue
        cov["validHistory"]+=1
        selected=indicators(df,c)
        if selected.empty:continue
        selected=selected[(selected.date.astype(str)>=START)&(selected.date.astype(str)<=END)]
        for _,row in selected.iterrows():
            d=str(row["date"])
            if d not in signal_dates:continue
            r={"code":str(x["code"]),"name":str(x["name"]),"market":str(x["market"]),"score":float(row.HScore),
               "signalClose":round(float(row.close),3),"turnoverProxyPct":round(float(row.turnoverProxyPct),3),
               "turnoverAvg5":round(float(row.turnoverAvg5),3),"volumeRatio10":round(float(row.volumeRatio10),3),
               "near120High":round(float(row.near120High),4),"prior8RangePct":round(float(row.prior8RangePct),3),
               "breakout8Pct":round(float(row.breakout8Pct),3)}
            pool[d].append(r);cov["stockSignalEvents"]+=1
        if (i+1)%300==0:print("H2 features",i+1,"/",len(universe),flush=True)
    ranking={}
    for d in sorted(signal_dates):
        rows=sorted(pool.get(d,[]),key=lambda x:(-x["score"],-x["turnoverAvg5"],-x["turnoverProxyPct"],x["code"]))
        ranking[d]=[{**r,"rank":j+1} for j,r in enumerate(rows[:TOP_N])]
    cov["signalsDays"]=sum(bool(rows) for rows in pool.values())
    cov["daysAtLeast3"]=sum(len(rows)>=3 for rows in pool.values())
    cov["meanCandidates"]=round(sum(len(pool.get(d,[])) for d in signal_dates)/max(len(signal_dates),1),3)
    cov["maxCandidates"]=max([len(v) for v in pool.values()] or [0])
    return ranking,cov
def execute_one(signal,dates,pos,h,prices):
    d=signal["date"];i=pos[d]
    if i+h>=len(dates):return None
    end=dates[i+h]
    if end>END:return None
    entry=dates[i+1]
    rows=[]
    for item in signal["rows"]:
        px=prices.get(to_symbol(item["code"],item["market"]))
        out=exit_trade(px,entry,end,item["signalClose"])
        rows.append({"signalDate":d,"entryDate":entry,"maxExitDate":end,"horizon":h,**item,**(out or {"status":"missing"})})
    return rows
def evaluate(signals,dates,px):
    pos={d:i for i,d in enumerate(dates)}
    signal_dates=[d for d in dates if START<=d<=END]
    flattened={d:{"date":d,"rows":signals.get(d,[])} for d in signal_dates}
    summary={};detail5=[];curves={}
    for horizon in HORIZONS:
        per_day={};trades=[];counts={"filled":0,"gap_skip":0,"missing":0}
        for d in signal_dates:
            trade_rows=execute_one(flattened[d],dates,pos,horizon,px)
            if trade_rows is None:continue
            valid=[x for x in trade_rows if x["status"]=="filled"]
            for x in trade_rows:counts[x["status"]]+=1
            trades.extend(trade_rows)
            per_day[d]=sum(x["netPct"] for x in valid)/TOP_N
        fills=[t for t in trades if t["status"]=="filled"]
        net=[t["netPct"] for t in fills]
        tp=sum(t["reason"].startswith("tp") for t in fills)
        stop=sum(t["reason"].startswith("stop") for t in fills)
        profits=sum(max(0,r) for r in net);losses=sum(max(0,-r) for r in net)
        portfolio=1.;peak=1.;mdd=0.;curve=[];participated=0
        eligible=[d for d in signal_dates if pos[d]+horizon<len(dates) and dates[pos[d]+horizon]<=END]
        for offset in range(0,len(eligible),horizon):
            d=eligible[offset]
            value=per_day.get(d,0)
            if any(x["signalDate"]==d and x["status"]=="filled" for x in trades):participated+=1
            portfolio*=max(0,1+value/100)
            peak=max(peak,portfolio);mdd=max(mdd,(1-portfolio/peak)*100)
            curve.append({"exit":dates[pos[d]+horizon],"equity":round(portfolio,6),"cohortNet":round(value,3)})
        # Precommitted: each selected signal-day has up to three independent slots; gaps stay cash.
        summary[str(horizon)]={"signalsWithCandidates":sum(bool(flattened[d]["rows"]) for d in per_day),
            "filledTrades":counts["filled"],"unfilledHighOpeningGaps":counts["gap_skip"],
            "invalidOrMissingBars":counts["missing"],"tradeNet":stats(net),"grossTargetTouches":tp,
            "targetHitPct":round(tp/max(len(fills),1)*100,2),"stopHits":stop,"stopHitPct":round(stop/max(len(fills),1)*100,2),
            "profitFactor":round(profits/losses,3) if losses>0 else None,
            "slotDailyNet":stats(per_day.values()),
            "nonOverlapping":{"cohorts":len(curve),"investedCohorts":participated,
                              "totalNetPct":round((portfolio-1)*100,2),"maxDrawdownPct":round(mdd,2)}}
        if horizon==5:detail5=trades
        curves[str(horizon)]=curve
        print("H2_HORIZON "+json.dumps({"horizon":horizon,**summary[str(horizon)]},ensure_ascii=False),flush=True)
    return summary,detail5,curves
def run():
    start_time=time.time()
    company=load_universe()
    # No price relative to index, cap ceiling, D score or G momentum candidate pool.
    fs=datetime(2025,3,1)
    fe=min(datetime.now(ZoneInfo("Asia/Taipei")).replace(tzinfo=None),datetime(2026,10,8))
    print("H2 standalone stocks",len(company),"fetch",fs.date(),"..",fe.date(),flush=True)
    hist,errors=update_many([(x["code"],x["market"]) for x in company],fs,fe)
    _,idx,err=update_symbol("^TWII",fs,fe)
    if err or idx is None or len(idx)<120:raise RuntimeError("Missing TWII trading calendar: "+str(err))
    dates=idx.date.astype(str).tolist();all_signal_dates={d for d in dates if START<=d<=END}
    top,cov=build_signals(hist,company,all_signal_dates)
    price={sym:df.sort_values("date").drop_duplicates("date",keep="last").set_index("date",drop=False)
           for sym,df in hist.items() if df is not None and not df.empty}
    summary,trades5,curves=evaluate(top,dates,price)
    output={"model":"H2_INDEPENDENT_TURNOVER_CONSOLIDATION","period":{"start":START,"end":END},
        "generatedAt":datetime.now(ZoneInfo("Asia/Taipei")).isoformat(timespec="seconds"),
        "signalDays":len(all_signal_dates),"historyFailures":len(errors),"coverage":cov,
        "criteria":SPEC,"execution":{"signal":"completed daily close","entry":"next open if <= prior close * 1.025",
            "takeProfitGrossPct":7,"stopLossGrossPct":3.5,"stopFirstIfSameDailyBar":True,
            "costs":"0.1425% commission per side +0.3% sell tax +0.1% slippage per side",
            "threeEqualSlots":True,"gapSkippedSlot":"cash","cohortRule":"non-overlapping fixed holding periods; early exits hold cash until next cohort"},
        "summary":summary,"notes":["This backtest did not read A/D/F/G signals, indicators, selection scores or ranks.",
            "Stock turnover uses present paid-in capital / assumed 10 TWD nominal share value, not historical shares outstanding: historical proxy and potential lookahead bias.",
            "The universe is current listed/OTC companies, subject to survivorship bias.",
            "Daily OHLCV cannot establish within-day order of TP and stop: stop assumed first when both touched.",
            "High-gap opening above prior-close+2.5% is assumed not filled; no speculative intraday buy.",
            "Gross 7% TP will yield lower net take-home after transaction costs and slippage.",
            "2026 is an exploratory test; keep rules fixed and seek a separate unseen year before production."],
        "elapsedSeconds":round(time.time()-start_time,2)}
    folder=DATA_DIR/"backtest_h_v2";folder.mkdir(exist_ok=True,parents=True)
    (folder/"H2_2026_summary.json").write_text(json.dumps(output,ensure_ascii=False,indent=2),encoding="utf-8")
    (folder/"H2_2026_5D_trades.json").write_text(json.dumps(trades5,ensure_ascii=False,indent=2),encoding="utf-8")
    (folder/"H2_2026_top3.json").write_text(json.dumps({d:x for d,x in top.items() if x},ensure_ascii=False,indent=2),encoding="utf-8")
    (folder/"H2_2026_curves.json").write_text(json.dumps(curves,ensure_ascii=False,indent=2),encoding="utf-8")
    print("H2_2026_RESULT "+json.dumps({"period":output["period"],"signalDays":output["signalDays"],
        "coverage":cov,"summary":summary,"historicalFailures":len(errors),"elapsed":output["elapsedSeconds"]},ensure_ascii=False),flush=True)
    return output
if __name__=="__main__":run()
