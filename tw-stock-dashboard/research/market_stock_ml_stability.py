"""20-session moving-block bootstrap of out-of-time ML gate increments.
Tests whether GRU+Score>=60 improves executed A/D/G net Top3 returns over
same eligible Score>=60 sessions; preserve serial correlation in market regimes.
Intervals are descriptive and NOT independent population confidence intervals.
"""
from __future__ import annotations
import json,math,statistics,random
from collections import defaultdict
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
ROOT=Path(__file__).resolve().parents[1]/"docs"/"data"/"research"
DATA=ROOT.parents[1]/"data"
OUTPUT=ROOT/"market_stock_ml_oos"
BLOCK=20;REPS=3000;SEED=20261011;COST=.00585
ARCHIVES=("2023-01-01_2023-12-31.json","2024-01-01_2024-12-31.json",
    "2025-01-01_2025-12-31.json","2026-01-01_2026-10-07.json")
def read(path):return json.loads(path.read_text(encoding="utf-8"))
def models(h,dates):
    g=read(ROOT/"g_regime_3y"/"trades.json")
    model=next(z for z in g["models"] if z["model"]=="SPOT_0" and z["horizon"]==h)
    dateset=set(dates);grid={"G":{},"D":{}}
    for z in model["trades"]:
        if z["date"] in dateset and len(z["codes"])==3:
            grid["G"][z["date"]]={"net":float(z["net"]),"exit":z["sell"]}
    rows=defaultdict(list)
    for y in ARCHIVES:
        for z in next(m for m in read(DATA/"backtest"/y)["models"] if m["id"]=="D")["signals"]:
            if z["signalDate"] in dateset and int(z["rank"])<=3:rows[z["signalDate"]].append(z)
    for day,arr in rows.items():
        arr.sort(key=lambda z:z["rank"])
        if len(arr)!=3 or [x["rank"] for x in arr]!=[1,2,3]:continue
        vals=[x.get("ret"+str(h)) for x in arr]
        if any(v is None for v in vals):continue
        pos=dates.index(day)
        if pos+h>=len(dates):continue
        if any(x["buyDate"]!=dates[pos+1] for x in arr):continue
        val=(1+sum(float(v) for v in vals)/300.)*(1-COST)-1
        grid["D"][day]={"net":val,"exit":dates[pos+h]}
    return grid
def summarize(x):
    x=sorted(x)
    if not x:return {"samples":0,"mean":None}
    return {"samples":len(x),"mean":round(statistics.mean(x)*100,3),
         "winRatePct":round(sum(z>0 for z in x)*100/len(x),2)}
def evaluation(series,signals,risk,preds,fold,h,model):
    days=[d for d in series if fold[0]<=d<=fold[1]]
    eligible={d:tr for d,tr in signals.items() if d in set(days) and tr["exit"]<=fold[1] and d in preds}
    eligible={d:tr for d,tr in eligible.items() if risk[d]["score"]>=60}
    tests={
        "SCORE_GE80":lambda d:risk[d]["score"]>=80,
        "GRU_AND_SCORE60":lambda d:preds[d]["GRU"]>=.5,
        "GREEN_AND_SCORE60":lambda d:risk[d]["dayRet"]>0,
        "RED_AND_SCORE60":lambda d:risk[d]["dayRet"]<0}
    base=[v["net"] for v in eligible.values()]
    result={"model":model,"horizon":h,"fold":fold[0][:4],
        "baselineScore60":summarize(base),"fixedPolicies":{}}
    rng=random.Random(SEED+int(fold[0][:4])*10+h+(101 if model=="D" else 0))
    for name,predicate in tests.items():
        selected={d:t["net"] for d,t in eligible.items() if predicate(d)}
        observed=(statistics.mean(selected.values())-statistics.mean(base))*100 if selected and base else None
        draws=[]
        for rep in range(REPS):
            chosen=[]
            while len(chosen)<len(days):
                i=rng.randrange(len(days))
                chosen.extend(days[(i+j)%len(days)] for j in range(BLOCK))
            chosen=chosen[:len(days)]
            bvals=[eligible[d]["net"] for d in chosen if d in eligible]
            svals=[selected[d] for d in chosen if d in selected]
            if len(bvals)<10 or len(svals)<5:continue
            draws.append((statistics.mean(svals)-statistics.mean(bvals))*100)
        draws.sort()
        stable=len(draws)>=1500
        result["fixedPolicies"][name]={
            "selected":summarize(selected.values()),"meanNetImprovementVsScore60Pts":round(observed,3) if observed is not None else None,
            "bootstrapBlockTradingDays":BLOCK,"draws":len(draws),
            "delta95IntervalPctPts":[round(draws[int(.025*len(draws))],3),round(draws[int(.975*len(draws))-1],3)] if stable else None,
            "bootstrapFractionDeltaPositivePct":round(sum(x>0 for x in draws)/len(draws)*100,2) if stable else None,
            "excludesZero":bool(stable and (draws[int(.025*len(draws))]>0 or draws[int(.975*len(draws))-1]<0)),
            "smallSample":len(selected)<20,
            "warning":"Non-iid market block resampling. Estimates only mean selected-signal edge vs SCORE60, not portfolio excess return."}
    return result
def main():
    live=read(ROOT/"g_regime_3y"/"market_risk_daily.json")
    original=read(OUTPUT/"summary.json")
    p=read(OUTPUT/"dated_predictions_2025_2026.json")["dates"]
    dates=[z["date"] for z in live];risk={z["date"]:z for z in live}
    if len(live)!=728 or len(p)<300 or len(original["results"])!=384:
        raise RuntimeError("Missing dated ML & stock archive baseline")
    result={"version":"AI_VS_RISK_MARKET_BLOCK_BOOTSTRAP_V1",
         "createdAt":datetime.now(ZoneInfo("Asia/Taipei")).isoformat(),
         "marketRows":len(live),"predictionDays":len(p),"blockDays":BLOCK,
         "resamples":REPS,"seed":SEED,
         "compareTo":"Risk Score >=60 baseline; same selector and horizon within same calendar year",
         "method":"Sample blocks of 20 CONSECUTIVE market sessions with replacement (circular); preserve clustering of daily signals; compute mean of full Top3 baskets selected by each fixed policy",
         "targets":["G","D"],"holds":[10,20],"results":[],
         "limitations":["2026 previously reviewed; do not interpret as pristine unseen data",
             "Intervals only descriptive with 1-2 years of highly autocorrelated, overlapping 10/20D trades",
             "No daily-MTM drawdown or executable buy fills inferred from bootstrap",
             "Mean-return differences affected by sample selection and policy trade frequency",
             "GRU trained using 2025 early stopping: validation results are model-selected, not pristine holdout",
             "Not a multiple-test-adjusted statistical significance result; study 4 gates, 2 selectors, 2 horizons and 2 years"]}
    for h in (10,20):
        source=models(h,dates)
        for model in ("G","D"):
            for fold in (("2025-01-01","2025-12-31"),("2026-01-01","2026-10-08")):
                result["results"].append(evaluation(dates,source[model],risk,p,fold,h,model))
    (OUTPUT/"stability_bootstrap.json").write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False),encoding="utf-8")
    print("BLOCK_BOOTSTRAP_DONE",json.dumps({"G20":[{"year":r["fold"],"base":r["baselineScore60"],"gru":r["fixedPolicies"]["GRU_AND_SCORE60"]} for r in result["results"] if r["model"]=="G" and r["horizon"]==20],
        "D10":[{"year":r["fold"],"base":r["baselineScore60"],"gru":r["fixedPolicies"]["GRU_AND_SCORE60"]} for r in result["results"] if r["model"]=="D" and r["horizon"]==10]},ensure_ascii=False),flush=True)
if __name__=="__main__":main()
