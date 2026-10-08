"""H5 unchanged fixed fresh-break screener, revised five-buy price ladder.
One 2026 research evaluation, using only past close for selection.
No A/D/F/G signals or stock ranking data are read.
"""
from __future__ import annotations
import json,time
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from collections import defaultdict
import numpy as np,pandas as pd
from config import DATA_DIR
from pipeline import load_universe
from yahoo_cache import update_many,update_symbol,to_symbol
from backtest_h_v5 import features,mask_family,score
from h5_ladder import simulate
START="2026-01-01";END="2026-10-07"
HORIZONS=(5,10,20);DISCOUNTS=(2.0,2.5,3.0);TOP_N=3
# FROZEN H5 variant is EXACTLY the previous H5 1% entry research winner.
# Only the buy/averaging/TP/SL execution layer changes.
FROZEN={"family":"fresh_break","break":3,"turn":5,"vrel":2.0,"ranking":2}
KEYS=("turn","turn5","vrel","p120","b8","b20","draw20","ret5","prev5","ret20","day","priorDay",
      "range8","vcon","pos","body","aboveEma","emaSlope","aboveMa60","atr","tradedM")
def summarize(rows):
    fills=[r for r in rows if r["status"]=="filled"]
    if not fills:return {"signals":len(rows),"filled":0,"unfilled":sum(r["status"]=="unfilled" for r in rows),"invalid":sum(r["status"]=="missing" for r in rows)}
    def num(xs):
        return round(float(np.mean(xs)),3) if xs else None
    t=sum(r["targetHit"] for r in fills);st=sum(r["stopHit"] for r in fills)
    wins=[r["netReturnOnDeployedPct"] for r in fills if r["netReturnOnDeployedPct"]>0]
    losses=[r["netReturnOnDeployedPct"] for r in fills if r["netReturnOnDeployedPct"]<0]
    counts={str(n):sum(r["trancheCount"]==n for r in fills) for n in range(1,6)}
    return {"signals":len(rows),"filled":len(fills),"unfilled":sum(r["status"]=="unfilled" for r in rows),
        "invalid":sum(r["status"]=="missing" for r in rows),"targetHit":t,
        "targetHitPct":round(t/len(fills)*100,2),"stopHit":st,"stopHitPct":round(st/len(fills)*100,2),
        "netWinPct":round(sum(r["netReturnOnDeployedPct"]>0 for r in fills)/len(fills)*100,2),
        "avgNetOnDeployedPct":num([r["netReturnOnDeployedPct"] for r in fills]),
        "avgNetOnFiveTrancheBudgetPct":num([r["netReturnOnFiveTrancheBudgetPct"] for r in fills]),
        "avgWinPct":num(wins),"avgLossPct":num(losses),
        "profitFactor":round(sum(wins)/abs(sum(losses)),3) if losses else None,
        "avgTranches":num([r["trancheCount"] for r in fills]),"trancheCountDistribution":counts,
        "avgGrossPct":num([r["grossReturnPct"] for r in fills]),
        "avgFilledEntryPriceVsFirstLimitPct":num([(r["firstFill"]/r["initialLimit"]-1)*100 for r in fills]),
        "distinctStocks":len(set(r["code"] for r in fills)),
        "signalDays":len(set(r["signalDate"] for r in fills))}
def selection(hist,universe,marketdates,marketpos):
    all_rows=[]
    for i,s in enumerate(universe):
        cap=float(s.get("capitalB") or 0)
        if cap<=0:continue
        sym=to_symbol(s["code"],s["market"]);df=hist.get(sym)
        if df is None or len(df)<160:continue
        x=features(df,cap,marketdates,marketpos,sample_start=START,sample_end=END)
        if not x:continue
        for row in x:
            d=row[0];vals=row[1:1+len(KEYS)]
            rec={"date":d,"code":str(s["code"]),"market":s["market"],"name":s["name"],
                 "signalClose":float(df.loc[df.date.astype(str)==d,"close"].iloc[-1])}
            rec.update(zip(KEYS,vals));all_rows.append(rec)
        if i%400==0:print(f"H5 ladder features: {i}/{len(universe)} stocks, {len(all_rows)} event rows",flush=True)
    if not all_rows:raise RuntimeError("No H5 research events")
    f=pd.DataFrame(all_rows)
    mask=mask_family(f,FROZEN)
    qualified=f.loc[mask].copy()
    qualified["score"]=score(qualified,FROZEN["family"],FROZEN["ranking"])
    selected=qualified.sort_values(["date","score","turn","code"],ascending=[True,False,False,True]).groupby("date",sort=False).head(TOP_N).copy()
    selected["rank"]=selected.groupby("date").cumcount()+1
    return selected,{"candidateEvents":len(f),"qualifiedStockDays":len(qualified),
                     "selectedEvents":len(selected),"selectedSignalDays":int(selected.date.nunique()),
                     "selectedDistinctStocks":int(selected.code.nunique())}
def run():
    tic=time.time();universe=load_universe()
    fs=datetime(2025,4,1);fe=datetime(2026,10,8)
    print(f"H5 ladder 2026: {len(universe)} universe securities",flush=True)
    hist,errors=update_many([(x["code"],x["market"]) for x in universe],fs,fe)
    _,idx,idxerr=update_symbol("^TWII",fs,fe)
    if idxerr or idx is None or len(idx)<160:raise RuntimeError("Missing 2026 trading calendar: "+str(idxerr))
    md=idx.date.astype(str).tolist();mi={d:i for i,d in enumerate(md)}
    selected,coverage=selection(hist,universe,md,mi)
    selected_records=selected.to_dict(orient="records")
    price={s:df.sort_values("date").drop_duplicates("date",keep="last").set_index("date",drop=False)
           for s,df in hist.items() if df is not None and not df.empty}
    results={};details={}
    for h in HORIZONS:
        results[str(h)]={};details[str(h)]={}
        for disc in DISCOUNTS:
            trades=[]
            for x in selected_records:
                sig=x["date"];j=mi.get(sig)
                if j is None or j+h>=len(md) or md[j+h]>END:continue
                ds=md[j+1:j+h+1]
                df=price.get(to_symbol(x["code"],x["market"]))
                if df is None or not all(z in df.index for z in ds):result={"status":"missing"}
                else:result=simulate(df.loc[ds],x["signalClose"],disc,h)
                trades.append({"signalDate":sig,"code":x["code"],"name":x["name"],"market":x["market"],
                               "rank":x["rank"],"signalClose":round(x["signalClose"],3),"turn":round(x["turn"],3),
                               "rvol20":round(x["vrel"],3),"breakout20Pct":round(x["b20"],3),**result})
            key=str(disc)
            results[str(h)][key]=summarize(trades)
            if h==5:details[str(h)][key]=trades
            print("H5_LADDER_COMPARE "+json.dumps({"horizon":h,"firstDiscountPct":disc,"stats":results[str(h)][key]},ensure_ascii=False),flush=True)
    report={"version":"H5_FIVE_TRANCHE_COST_AVERAGING_2026_V1",
        "period":{"start":START,"end":END},"generatedAt":datetime.now(ZoneInfo("Asia/Taipei")).isoformat(timespec="seconds"),
        "universe":len(universe),"priceHistoryErrors":len(errors),"coverage":coverage,
        "selection":{"frozenFromH5Version":"research/h-v5-limit-pullback-2026",
                     "fixedConfig":FROZEN,
                     "stockFilters":"H5 fresh_break: price>=12, initial turnover proxy>=0.7%, traded value>=NTD100m, previous5 daily turnover proxy>=0.4%, ATR14>=2%, current turnover proxy>=5%, current/prev20 volume>=2.0, close>=prior20-high+3%, daily gain 1%..9.5%, close>=70% of daily range",
                     "rank":"0.4*prior5_turnover_proxy_pct + ret20_pct/6 + atr14_pct/2 + breakout20_pct/8, descending, top3 per day",
                     "noOtherModels":"Does not depend on A/D/F/G stock signals, scores, or market regime"},
        "execution":{"discountOptionsPct":DISCOUNTS,"firstOrderActive":"NEXT trading day only; unfilled cancels",
           "ladderFromActualFirstFill":"P1 × (1−2%×n), n=1,2,3,4; five orders maximum",
           "addsActive":"from first fill through exit/max horizon","allocation":"equal notional every tranche; actual weighted average price from total shares",
           "profitTarget":"dynamic avg cost +7% gross","stopLoss":"dynamic avg cost -15% gross",
           "maxHoldingTradingDays":HORIZONS,"buyFeePct":0.1425,"sellFeePct":0.1425,"sellTaxPct":0.3,"slippageEachSidePct":0.1,
           "sameDayDailyOHLC":"new intraday add fills: same-day TP not credited, stop first; existing gap stops and targets settle before new adds",
           "noLiveOrderExecution":True},
        "results":results,
        "warnings":["Current paid-in capital/NTD10 proxy for turnover is NOT historical shares outstanding; survivorship and look-ahead limitations.",
          "Averages cost down and expands exposure into price weakness; -15% at basket average can yield meaningful five-tranche capital loss.",
          "Daily OHLC cannot resolve intraday sequencing, limit fill, or whether TP was hit after add; conservative same-day TP suppression used.",
          "2026 tested repeatedly in previous H research; in-sample exploratory only, cannot use results as out-of-sample evidence.",
          "Portfolio equity curve not computed because overlapping multiple basket positions require explicit account-level cash and margin modelling.",
          "Real-world price limits, fees, lot sizes, odd-lot execution, dividends and stock split corporate actions are simplified."],
        "elapsedSeconds":round(time.time()-tic,1)}
    p=DATA_DIR/"backtest_h_ladder";p.mkdir(parents=True,exist_ok=True)
    (p/"H5_ladder_2026_summary.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    (p/"H5_ladder_2026_5D_trades.json").write_text(json.dumps(details["5"],ensure_ascii=False,indent=2),encoding="utf-8")
    (p/"H5_ladder_2026_top3.json").write_text(selected[["date","rank","code","name","market","signalClose","score","turn","vrel","b20"]].to_json(orient="records",force_ascii=False,indent=2),encoding="utf-8")
    print("H5_LADDER_RESULT "+json.dumps({"period":report["period"],"coverage":coverage,"results":results,"elapsedSeconds":report["elapsedSeconds"]},ensure_ascii=False),flush=True)
    return report
if __name__=="__main__":run()
