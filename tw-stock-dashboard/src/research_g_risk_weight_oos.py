"""Frozen-sample, point-in-time G market Risk Score weight sensitivity study.
Uses already-published trades from independently run G three-year study. No price
refetch, no modifications to live Risk Score, no 2026 data in model selection.
DO NOT interpret signal averages/phase curves as investable portfolio returns.
"""
from __future__ import annotations
import json, math, statistics, random
from collections import defaultdict
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
ROOT=Path(__file__).resolve().parents[1]
DIR=ROOT/"docs"/"data"/"research"/"g_regime_3y"
OUT=DIR/"weight_oos_summary.json"
NAMES=("close_ma20","ma5_ma20","ma20_slope","breadth","foreign","ret5","ret20","day_up")
MAXIMUM=(15,10,5,20,15,15,10,10)
WEIGHTS={
 "ORIGINAL":(15,10,5,20,15,15,10,10),
 "TREND_FOCUS":(20,15,10,15,5,15,15,5),
 "BREADTH_FOCUS":(15,10,5,30,5,15,10,10),
 "LOW_FOREIGN":(20,15,5,20,5,15,10,10),
 "MOMENTUM_FOCUS":(15,10,5,15,5,25,20,5),
 "NO_DAY_NOISE":(20,10,10,25,10,15,10,0),
 "LONG_MOMENTUM":(20,15,10,15,10,10,20,0),
 "HIGH_FOREIGN":(10,5,5,20,30,15,10,5)
}
THRESHOLDS=(50,55,60,65,70,75,80)
HORIZONS=(1,5,10,20)
SPLITS={"train":("2023-10-09","2024-12-31"),"validation":("2025-01-01","2025-12-31"),"holdout":("2026-01-01","2026-10-08")}
def read(name):return json.loads((DIR/name).read_text(encoding="utf-8"))
def metric(nums):
    a=sorted(float(v)*100 for v in nums)
    n=len(a)
    if not n:return {"n":0,"meanPct":None,"medianPct":None,"winPct":None,"meanWinPct":None,"meanLossPct":None,"p10Pct":None,"worstPct":None,"profitFactor":None}
    wins=[v for v in a if v>0];loss=[v for v in a if v<0]
    return {"n":n,"meanPct":round(statistics.mean(a),3),"medianPct":round(statistics.median(a),3),"winPct":round(100*len(wins)/n,2),
      "meanWinPct":round(statistics.mean(wins),3) if wins else None,
      "meanLossPct":round(statistics.mean(loss),3) if loss else None,
      "p10Pct":round(a[max(0,math.ceil(n*.1)-1)],3),"worstPct":round(a[0],3),
      "profitFactor":round(sum(wins)/-sum(loss),3) if loss else None}
def score_parts(rows,inputs):
    result={};mismatched=[]
    closes=[float(z["index"]) for z in rows]
    for i,z in enumerate(rows):
        day=z["date"];inp=inputs.get(day)
        if not isinstance(inp,dict) or inp.get("ok") is not True:raise RuntimeError("Missing verified TWSE official inputs "+day)
        if int(inp["up"])+int(inp["down"])<500:raise RuntimeError("Insufficient TWSE market breadth "+day)
        br=100*int(inp["up"])/(int(inp["up"])+int(inp["down"]))
        foreign=float(inp["foreign"]);c=closes[i]
        r5=100*(c/closes[i-5]-1) if i>=5 else float(z["ret5"])
        r20=100*(c/closes[i-20]-1) if i>=20 else float(z["ret20"])
        dayup=c>closes[i-1] if i else float(z["dayRet"])>0
        ma5=float(z["ma5"]);ma20=float(z["ma20"])
        # MA20 5 bars ago is the previous, non-overlapping 20-session mean.
        if i>=25:prev20=sum(closes[i-24:i-4])/20
        elif i>=5:prev20=float(rows[i-5]["ma20"])
        else:prev20=None
        parts=[15 if c>ma20 else 0,10 if ma5>ma20 else 0,0,
          20 if br>=55 else 12 if br>=50 else 5 if br>=45 else 0,
          15 if foreign>0 else 6 if foreign>-50 else 0,
          15 if r5>2 else 10 if r5>0 else 4 if r5>-2 else 0,
          10 if r20>5 else 6 if r20>0 else 2 if r20>-5 else 0,
          10 if dayup else 0]
        other=sum(parts);score=int(z["score"])
        parts[2]=5 if (ma20>prev20 if prev20 is not None else abs(score-other-5)<abs(score-other)) else 0
        check=sum(parts)
        if check!=score:mismatched.append({"date":day,"saved":score,"reconstructed":check,"delta":score-check})
        result[day]=tuple(p/m for p,m in zip(parts,MAXIMUM))
    return result,mismatched
def main():
    cover=read("coverage.json");rows=read("market_risk_daily.json");inputs=read("risk_inputs.json")
    t=read("trades.json");summary=read("summary.json")
    days=[r["date"] for r in rows]
    if cover.get("complete") is not True or len(days)!=728 or len(set(days))!=728 or cover.get("riskScoredDays")!=728 or cover.get("tradingDays")!=728:raise RuntimeError("728-day audited index data are incomplete")
    if not all(SPLITS["train"][0]<=days[0] and days[-1]<=SPLITS["holdout"][1] for _ in (0,)):raise RuntimeError("Unexpected index date range")
    if t["period"]!=summary["period"]:raise RuntimeError("Trade archive/summary period mismatch")
    for k,w in WEIGHTS.items():
        if sum(w)!=100 or len(w)!=len(NAMES):raise RuntimeError("Invalid risk weights "+k)
    parts,drift=score_parts(rows,inputs)
    if len(drift)>12:raise RuntimeError("Too many discrepancies with original official Risk Score: "+str(drift[:5]))
    scored={name:{r["date"]:(int(r["score"]) if name=="ORIGINAL" else sum(100*w*p/100 for w,p in zip(weight,parts[r["date"]]))) for r in rows} for name,weight in WEIGHTS.items()}
    # Non-original scores remain fractional and are intentionally not rounded before gating.
    baselines={m["horizon"]:m for m in t["models"] if m["model"]=="SPOT_0"}
    if set(baselines)!=set(HORIZONS):raise RuntimeError("SPOT_0 trade sets missing")
    assert all(len(baselines[h]["trades"])==baselines[h]["executedSignals"] for h in HORIZONS)
    dates=set(days);ret={}
    for h,m in baselines.items():
        d={}
        for trade in m["trades"]:
            dt=trade["date"]
            if dt not in dates or trade["score"]!=int(next(x["score"] for x in rows if x["date"]==dt)):
                raise RuntimeError("Trade/score date mismatch "+dt)
            if trade["buy"]<=dt or trade["sell"]<trade["buy"] or not math.isfinite(float(trade["net"])):
                raise RuntimeError("Trade lookahead/date/return anomaly "+dt)
            if dt in d:raise RuntimeError("Duplicate signal "+dt)
            d[dt]=trade
        ret[h]=d
    checks=[]
    for m in summary["models"]:
        if m["model"].startswith("SPOT_"):
            base=ret[m["horizon"]]
            th=int(m["model"].split("_")[1])
            n=sum(scored["ORIGINAL"][day]>=th for day in base)
            if n!=m["executedSignals"]:checks.append({"model":m["model"],"h":m["horizon"],"n":n,"original":m["executedSignals"]})
    if checks:raise RuntimeError("Baseline reproduction mismatch: "+str(checks[:8]))
    def samples(h,name,threshold,period):
        lo,hi=SPLITS[period]
        # All rows included only if the trade EXIT is in the same chronological fold.
        return [a for d,a in ret[h].items() if lo<=d<=hi and a["sell"]<=hi and scored[name][d]>=threshold]
    def evalone(h,name,threshold,period):
        return metric([x["net"] for x in samples(h,name,threshold,period)])
    grid=[]
    for name in WEIGHTS:
        for threshold in THRESHOLDS:
            e={"name":name,"threshold":threshold,"byPeriod":{}}
            for split in SPLITS:
                e["byPeriod"][split]={str(h):evalone(h,name,threshold,split) for h in HORIZONS}
            grid.append(e)
    # Locked selection: 2026 is never consulted. Demand adequate signals and
    # positive 20D expectancy in both 2023-24 TRAIN and 2025 VALIDATION.
    candidates=[]
    for row in grid:
        tr=row["byPeriod"]["train"]["20"];va=row["byPeriod"]["validation"]["20"]
        if tr["n"]<45 or va["n"]<25 or tr["meanPct"]<=0 or va["meanPct"]<=0:continue
        # Penalize downside, regime instability and smaller validation samples.
        objective=.4*tr["meanPct"]+.6*va["meanPct"]-.12*max(0,-va["p10Pct"]-5)-.12*abs(tr["meanPct"]-va["meanPct"])
        objective-=1.0/math.sqrt(va["n"])
        candidates.append((objective,row["name"],row["threshold"]))
    candidates.sort(key=lambda v:(-v[0],v[1],v[2]))
    if not candidates:raise RuntimeError("No candidate satisfies prespecified validation safety gates")
    selected={"name":candidates[0][1],"threshold":candidates[0][2],"preHoldoutObjective":round(candidates[0][0],4)}
    selectedRow=next(x for x in grid if x["name"]==selected["name"] and x["threshold"]==selected["threshold"])
    reference={}
    for name,th in (("ORIGINAL",0),("ORIGINAL",60),("ORIGINAL",70),("ORIGINAL",80),(selected["name"],selected["threshold"])):
        key=f"{name}_{th}"
        reference[key]={"name":name,"threshold":th,"byPeriod":{p:{str(h):evalone(h,name,th,p) for h in HORIZONS} for p in SPLITS},
          "all":{"10":metric([a["net"] for d,a in ret[10].items() if scored[name][d]>=th]),
                 "20":metric([a["net"] for d,a in ret[20].items() if scored[name][d]>=th])}}
    # Resample by calendar months to account for clustered sequential signals.
    # This only compares per-day strategy payoff proxies, NOT investable portfolio returns.
    rng=random.Random(20261010)
    holdDates=[d for d in days if SPLITS["holdout"][0]<=d<=SPLITS["holdout"][1]]
    months=defaultdict(list)
    for d in holdDates:months[d[:7]].append(d)
    mm=list(months.values())
    def payoff(d,name,th):
        t=ret[20].get(d)
        if t is None or t["sell"]>SPLITS["holdout"][1] or scored[name][d]<th:return 0.
        return t["net"]*100
    boot={}
    for refName,refTh in (("ORIGINAL",60),("ORIGINAL",80)):
        monthly=[sum(payoff(d,selected["name"],selected["threshold"])-payoff(d,refName,refTh) for d in month)/len(month) for month in mm]
        draws=[statistics.mean(rng.choice(monthly) for _ in monthly) for _ in range(1500)]
        draws.sort()
        boot[f"{refName}_{refTh}"]={"differencePerMarketDayPct":round(statistics.mean(monthly),4),
          "monthBootstrap95Pct":[round(draws[int(.025*(len(draws)-1))],4),round(draws[int(.975*(len(draws)-1))],4)],
          "metric":"Average signal net return per 2026 market session, counting no-entry sessions as zero; not equity return"}
    latest=rows[-1];lastScore={name:round(scored[name][latest["date"]],2) for name in WEIGHTS}
    out={"createdAt":datetime.now(ZoneInfo("Asia/Taipei")).isoformat(),
      "study":"PREDECLARED_WEIGHT_FAMILY_2023_2026_TRAIN_VALIDATION_HOLDOUT_V1",
      "archiveCommitInputs":{"riskDays":len(rows),"gSignalDatesWith20DReturns":len(ret[20]),"stockUniverseSurvivorBias":True},
      "splits":SPLITS,"weights":{k:dict(zip(NAMES,w)) for k,w in WEIGHTS.items()},"testedThresholds":list(THRESHOLDS),
      "method":{"signal":"G top3 selected at close D; all gross and cost-adjusted trade returns frozen from prior audited backtest",
        "cost":"Uses existing net return with 0.1425% brokerage each side + 0.30% sell-side tax",
        "selection":"Select max prespecified 20D train/validation downside-penalized objective, never look at 2026",
        "tradeOverlap":"Per-signal averages overlap for >1D horizons; NOT investable portfolio PnL",
        "dateLeakage":"Training/validation trades with exits after period end removed; score uses only signal-day inputs",
        "rounding":"Non-original recomposed score fractions may differ at rounded indicator thresholds; preserved original score for baseline",
        "limitations":["Survivorship bias from current stock universe and share capital",
          "History of listed and delisted securities not point-in-time exhaustive",
          "No simulated real daily marked-to-market drawdown or actual order fill/limit-up handling",
          "G model parameters previously developed against historical datasets; only score weights are held out in 2026",
          "Bottom entry or Strong Reversal Top1-3 stock exception cannot be validated from the frozen G-top3 trade archive",
          "Multiple candidates studied: one held-out period cannot establish a universally optimal weighting"]},
      "roundingDiscrepancies":{"count":len(drift),"sample":drift[:12]},
      "baselineReproduction":"PASS","selectedBeforeHoldout":selected,
      "selectedPerformance":selectedRow["byPeriod"],"benchmarkPolicies":reference,
      "holdoutMonthlyBootstrap":boot,
      "allCandidates":grid,"currentLastDay":{"date":latest["date"],"originalScore":latest["score"],"alternativeScores":lastScore,
         "latestDisplayIsTradingSnapshot":True},
      "recommendationStatus":"RESEARCH_ONLY_NO_LIVE_CHANGE"}
    OUT.write_text(json.dumps(out,ensure_ascii=False,indent=2,allow_nan=False),encoding="utf-8")
    print("WEIGHT_OOS_DONE",json.dumps({"selected":selected,"train":selectedRow["byPeriod"]["train"]["20"],
       "validation":selectedRow["byPeriod"]["validation"]["20"],"holdout":selectedRow["byPeriod"]["holdout"]["20"],
       "baseline60Holdout":reference["ORIGINAL_60"]["byPeriod"]["holdout"]["20"],
       "baseline80Holdout":reference["ORIGINAL_80"]["byPeriod"]["holdout"]["20"],
       "roundingDrift":len(drift),"saved":str(OUT)},ensure_ascii=False),flush=True)
if __name__=="__main__":main()
