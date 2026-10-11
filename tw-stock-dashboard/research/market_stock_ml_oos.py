"""Research-only chronological stock-outcome audit of dated market-breadth ML signals.
Original A/D/G Top3 baskets, original official TWSE Risk Score and train-2024/validate-2025
GRU are checked against executable D+1 open -> D+H close archived net returns.
No 9:00 intraday input, model prediction published as live signal, or overlapping
capital in the separate EXIT-SAMPLED (not daily MTM) portfolio scenario.
"""
from __future__ import annotations
import json,math,statistics,random,time
from collections import defaultdict
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import numpy as np
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss,roc_auc_score,balanced_accuracy_score
from market_deep_breadth import load_complete,create,fit_nn,SEEDS
ROOT=Path(__file__).resolve().parents[1]/"docs"/"data"
OUT=ROOT/"research"/"market_stock_ml_oos"
GROOT=ROOT/"research"/"g_regime_3y"
ARCHIVES=("2023-01-01_2023-12-31.json","2024-01-01_2024-12-31.json",
  "2025-01-01_2025-12-31.json","2026-01-01_2026-10-07.json")
HORIZONS=(1,5,10,20)
GATES=("ALL","SCORE_GE60","SCORE_GE80","SCORE_GE60_RED_PULLBACK",
       "SCORE_GE60_GREEN_MOMENTUM","SCORE_GE60_BREADTH_GE50",
       "SCORE_GE60_NO_CONFIRMED_TOP","GRU_GE50","GRU_GE55",
       "GRU_GE50_AND_SCORE60","LOGIT_GE50","LOGIT_GE50_AND_SCORE60")
SPLITS={"validation":("2025-01-01","2025-12-31"),"holdout":("2026-01-01","2026-10-08")}
COST=0.00585
def read(p):return json.loads(Path(p).read_text(encoding="utf-8"))
def finite(v):
    try:return float(v) if v is not None and math.isfinite(float(v)) else None
    except (TypeError,ValueError):return None
def dates_and_picks(market_dates):
    index={d:i for i,d in enumerate(market_dates)}
    stocks={m:{h:{} for h in HORIZONS} for m in ("A","D","F","G")}
    reasons=defaultdict(int)
    for name in ARCHIVES:
        yr=read(ROOT/"backtest"/name)
        byid={x["id"]:x for x in yr["models"]}
        for model in ("A","D"):
            byday=defaultdict(list)
            for row in byid[model]["signals"]:
                d=str(row["signalDate"]);r=int(row["rank"])
                if d in index and r in (1,2,3):byday[d].append(row)
            for d,group in byday.items():
                group.sort(key=lambda q:q["rank"]);i=index[d]
                if len(group)!=3 or [int(z["rank"]) for z in group]!=[1,2,3]:
                    reasons[model+"_rank_count"]+=1;continue
                if i+1>=len(market_dates) or any(z["buyDate"]!=market_dates[i+1] for z in group):
                    reasons[model+"_buy_date"]+=1;continue
                for h in HORIZONS:
                    if i+h>=len(market_dates):continue
                    vals=[finite(z.get("ret"+str(h))) for z in group]
                    if any(v is None for v in vals):
                        reasons[model+"_missing_return_"+str(h)]+=1;continue
                    gross=sum(vals)/300.
                    net=(1+gross)*(1-COST)-1
                    stocks[model][h][d]={"date":d,"entry":market_dates[i+1],"exit":market_dates[i+h],
                         "net":net,"codes":[z["code"] for z in group],"source":"archived_stock_Top3_adj_open_close"}
    # F is EXACTLY identical D candidates; its default gate is official >=60
    # OR Strong Bottom reversal. Gate overrides will NOT affect D ranking.
    for h in HORIZONS:
        stocks["F"][h]={d:dict(z) for d,z in stocks["D"][h].items()}
    g=read(GROOT/"trades.json")
    for h in HORIZONS:
        models=[m for m in g["models"] if m["model"]=="SPOT_0" and m["horizon"]==h]
        if len(models)!=1:raise RuntimeError("Frozen G baseline model missing "+str(h))
        m=models[0]
        for z in m["trades"]:
            d=z["date"];i=index.get(d)
            if i is None or i+h>=len(market_dates):continue
            if len(z.get("codes",[]))!=3:reasons["G_missing_top3"]+=1;continue
            if z["buy"]!=market_dates[i+1] or z["sell"]!=market_dates[i+h]:
                raise RuntimeError("G trade time alignment mismatch "+d)
            if d in stocks["G"][h]:raise RuntimeError("Duplicate G source trade "+d)
            stocks["G"][h][d]={"date":d,"entry":z["buy"],"exit":z["sell"],"net":float(z["net"]),
                 "codes":z["codes"],"source":"frozen_official_G_SPOT_0_Top3"}
    assert len(stocks["G"][20])>500
    return stocks,dict(reasons)
def predictions(rows):
    X,y,split,dates=create(rows,"NEXT_BREADTH_MAJORITY")
    train,val,hold=[split[k] for k in ("train","validation","holdout")]
    series=np.array([x["score"] for x in rows],dtype=float)
    # Train-only logistic using original signal-day Risk Score; do NOT refit
    # using 2025/2026. Time labels cross-fold were purged in create().
    base=make_pipeline(StandardScaler(),LogisticRegression(max_iter=1000,C=.5))
    base.fit(X[train,-1][:,[0]],y[train])
    logit=base.predict_proba(X[:,-1][:,[0]])[:,1]
    mean=X[train].reshape(-1,X.shape[-1]).mean(axis=0)
    std=X[train].reshape(-1,X.shape[-1]).std(axis=0)
    z=np.clip((X-mean)/np.maximum(std,.05),-5,5).astype(np.float32)
    vals=[]
    for seed in SEEDS:
        p,epoch=fit_nn("GRU",z,y,split,seed)
        score=float(brier_score_loss(y[val],p["validation"]))
        vals.append((score,seed,p,epoch))
    vals.sort(key=lambda x:(x[0],x[1]))
    chosen=vals[0]
    # GRU output is only provided for 2025/2026 periods; do not back-fill in-sample
    # probabilities from the early-stopped model to earlier dates as if OOS.
    output={}
    for k,splitName in (("validation",val),("holdout",hold)):
        for j,pos in enumerate(splitName):
            d=dates[pos]
            output[d]={"riskLogit":round(float(logit[pos]),7),
                       "gru":round(float(chosen[2][k][j]),7),
                       "trueNextMajority":int(y[pos]),"sampleFold":k}
    err={}
    for fold,idx in (("validation",val),("holdout",hold)):
        yp=np.array([output[dates[i]]["gru"] for i in idx])
        ep=np.array([output[dates[i]]["riskLogit"] for i in idx])
        err[fold]={"n":len(idx),"GRU_Brier":round(float(brier_score_loss(y[idx],yp)),5),
            "SCORE_LOGIT_Brier":round(float(brier_score_loss(y[idx],ep)),5),
            "GRU_AUC":round(float(roc_auc_score(y[idx],yp)),4),
            "GRU_balancedAccuracyPct":round(float(balanced_accuracy_score(y[idx],yp>=.5)*100),2),
            "GRU_vs_SCORE_BrierImprovement":round(float(brier_score_loss(y[idx],ep)-brier_score_loss(y[idx],yp)),5)}
    return output,{"trainingSamples":len(train),"validationSamples":len(val),"holdoutSamples":len(hold),
        "selectedGRUSeedOn2025":chosen[1],"selectedEpochOn2025":chosen[3],
        "candidateSeeds":list(SEEDS),"expectedDateTrainStarts":rows[0]["date"],
        "predictiveSkill":err}
def is_allowed(gate,model,market,pred):
    if gate=="ALL":
        return model!="F" or market["score"]>=60 or market["bottomState"]=="🟢 Strong Bottom Reversal"
    if gate=="SCORE_GE60":return market["score"]>=60
    if gate=="SCORE_GE80":return market["score"]>=80
    if gate=="SCORE_GE60_RED_PULLBACK":return market["score"]>=60 and market["dayRet"]<0
    if gate=="SCORE_GE60_GREEN_MOMENTUM":return market["score"]>=60 and market["dayRet"]>0
    if gate=="SCORE_GE60_BREADTH_GE50":return market["score"]>=60 and market["breadth"]>50
    if gate=="SCORE_GE60_NO_CONFIRMED_TOP":return market["score"]>=60 and market.get("topState") not in (
            "🔴 Strong Top Reversal","🟠 Top Reversal Attempt","🔴 Extreme Overbought")
    if gate=="GRU_GE50":return pred is not None and pred["gru"]>=.50
    if gate=="GRU_GE55":return pred is not None and pred["gru"]>=.55
    if gate=="GRU_GE50_AND_SCORE60":return pred is not None and pred["gru"]>=.50 and market["score"]>=60
    if gate=="LOGIT_GE50":return pred is not None and pred["riskLogit"]>=.50
    if gate=="LOGIT_GE50_AND_SCORE60":return pred is not None and pred["riskLogit"]>=.50 and market["score"]>=60
    raise ValueError(gate)
def compact_stats(trades):
    n=len(trades)
    if not n:return {"n":0,"averageNetPct":None,"winPct":None,"medianNetPct":None,
      "avgPositiveNetPct":None,"avgNegativeNetPct":None,"worstNetPct":None}
    vals=sorted(float(v["net"])*100 for v in trades)
    pos=[v for v in vals if v>0];neg=[v for v in vals if v<0]
    return {"n":n,"averageNetPct":round(statistics.mean(vals),3),
        "medianNetPct":round(statistics.median(vals),3),"winPct":round(len(pos)*100/n,2),
        "avgPositiveNetPct":round(statistics.mean(pos),3) if pos else None,
        "avgNegativeNetPct":round(statistics.mean(neg),3) if neg else None,
        "worstNetPct":round(vals[0],3)}
def cash_proxy(trades,date_index,dates,h):
    # Single unleveraged full-capital basket; no concurrent investment.
    # Market values between exits CANNOT be reconstructed from these archived returns.
    # Hence the drawdown is EXIT-SAMPLED ONLY, not daily marked-to-market MDD.
    eq=1.;peak=1.;mdd=0.;n=0;exposure=0;last_exit=-1
    byday={t["date"]:t for t in trades}
    audit=[]
    for d in dates:
        i=date_index[d]
        if i<last_exit:continue
        t=byday.get(d)
        if t is None:continue
        end=date_index[t["exit"]]
        if end<last_exit:raise RuntimeError("overlapping schedule violation")
        old=eq;eq*=1+t["net"];peak=max(peak,eq);mdd=min(mdd,eq/peak-1)
        last_exit=end;n+=1;exposure+=h
        audit.append({"signal":d,"exit":t["exit"],"netPct":round(t["net"]*100,3)})
    return {"initialCapitalTWD":1000000,"endingCapitalTWD":round(1000000*eq,2),
        "exitSampledReturnPct":round((eq-1)*100,2),"exitSampledMDDPct":round(100*mdd,2),
        "nonOverlappingBaskets":n,"investedTradingDays":exposure,
        "note":"Cash idle between trades. No intratrade MTM; this is NOT actual daily account MDD."},audit
def main():
    tic=time.time();OUT.mkdir(parents=True,exist_ok=True)
    rows,extra=load_complete()
    original=read(GROOT/"market_risk_daily.json")
    if len(original)!=728 or [z["date"] for z in original]!=[z["date"] for z in rows[-728:]]:
        raise RuntimeError("Original G official fixed rows must exactly match model trailing 728 dates")
    dates=[x["date"] for x in rows];pos={d:i for i,d in enumerate(dates)}
    market={z["date"]:z for z in rows}
    baskets,audit=dates_and_picks(dates)
    forecasts,training=predictions(rows)
    if not forecasts:raise RuntimeError("No historically separated forecasts generated")
    output={"version":"TWSE_BREADTH_AI_STOCK_RETURNS_OOS_V1",
        "createdAt":datetime.now(ZoneInfo("Asia/Taipei")).isoformat(),
        "marketRows":len(rows),"verifiedExtendedYears":extra,
        "label":"Next-session TWSE breadth > 50%, from D close to D+1 close",
        "signalClock":"Only D CLOSE finished official data, decision known before next D+1 open; not true live 09:00 snapshot",
        "periods":SPLITS,"models":["A","D","F","G"],"horizons":list(HORIZONS),"gates":list(GATES),
        "transactionCostRoundTripPct":0.585,
        "training":training,"dataIntegrity":{"stockArchives":list(ARCHIVES),"droppedRecords":audit,
            "GSource":"research/g_regime_3y/trades.json published SPOT_0",
            "A_D":"Frozen archived ranked Top3, only all 3 valid adjusted future returns",
            "F":"D Top3 with official dated >=60 or Strong Bottom exception under ALL gate"},
        "results":[],"predictions":{},"validationScope":"2025 threshold illustration (not new hyperparameter search); 2026 previously inspected and not pristine blind holdout",
        "limits":["Model targets market breadth, not individual stock returns; classification accuracy does not imply stock profitability",
          "A/D yearly archive and G frozen selector have different version/capital/universe bias",
          "2026 has been viewed in prior research: this is a chronological test, NOT untouched independent data",
          "Selection of GRU on 2025 Brier and many threshold policies invites multiple-testing and selection bias",
          "No intraday 09:00 indicator, live opening OHLC market feed, limit-up trading feasibility or order-book slippage",
          "Overlapping 5/10/20 day stock signal returns are dependent and can't be summed as account profits",
          "The EXIT-SAMPLED capital scenario skips unrealized drawdowns; compare separately with existing real daily-MTM audit",
          "Current frozen G stock universe is survivor biased and A/D frozen ranks may contain tuned factors",
          "Only official date-tied TWSE listed stock breadth, not OTC; 2015-2023 partial years excluded"]}
    output["predictions"]={d:{"riskLogit":v["riskLogit"],"GRU":v["gru"],"actualNextBreadthMajority":v["trueNextMajority"]}
        for d,v in forecasts.items()}
    years={fold:([d for d in dates if start<=d<=end],start,end) for fold,(start,end) in SPLITS.items()}
    for model in ("A","D","F","G"):
        for h in HORIZONS:
            for fold,(dateList,start,end) in years.items():
                eligible={d:t for d,t in baskets[model][h].items() if
                  start<=d<=end and start<=t["entry"]<=end and t["exit"]<=end and d in forecasts
                  and forecasts[d]["sampleFold"]==fold}
                for gate in GATES:
                    cohort=[t for d,t in eligible.items() if is_allowed(gate,model,market[d],forecasts.get(d))]
                    one,events=cash_proxy(cohort,pos,dateList,h)
                    record={"model":model,"horizon":h,"fold":fold,"gate":gate,
                        "allAvailableSignals":len(eligible),"selectionRatePct":round(len(cohort)*100/len(eligible),2) if eligible else None,
                        "signalReturn":compact_stats(cohort),"exitSampledOneBasketCash":one}
                    output["results"].append(record)
        print("STOCK_OOS_MODEL_DONE",model,flush=True)
    # Thresholds for ML entry are PRE-DECLARED, not optimized using future 2026 results.
    # A compact flag warns when a strategy has little evidence (less than 20 signals).
    output["mainComparisons"]={}
    for model in ("A","D","F","G"):
        output["mainComparisons"][model]={}
        for h in (1,5,10,20):
            main={}
            for gate in ("ALL","SCORE_GE60","SCORE_GE80","SCORE_GE60_RED_PULLBACK",
                         "SCORE_GE60_GREEN_MOMENTUM","GRU_GE50",
                         "GRU_GE50_AND_SCORE60","LOGIT_GE50_AND_SCORE60"):
                r=next(x for x in output["results"] if x["model"]==model and x["horizon"]==h
                    and x["fold"]=="holdout" and x["gate"]==gate)
                main[gate]={"n":r["signalReturn"]["n"],"averageNetPct":r["signalReturn"]["averageNetPct"],
                    "winPct":r["signalReturn"]["winPct"],
                    "oneBasketExitSampledReturnPct":r["exitSampledOneBasketCash"]["exitSampledReturnPct"],
                    "oneBasketExitSampledDrawdownPct":r["exitSampledOneBasketCash"]["exitSampledMDDPct"]}
            output["mainComparisons"][model][str(h)]=main
    out=OUT/"summary.json";out.write_text(json.dumps({k:v for k,v in output.items() if k!="predictions"},
        ensure_ascii=False,indent=2,allow_nan=False),encoding="utf-8")
    (OUT/"dated_predictions_2025_2026.json").write_text(json.dumps({
        "warning":"Historical research-only; 2026 actual outcomes are now known. This file is NOT a live forecast.",
        "dates":output["predictions"]},ensure_ascii=False,indent=2),encoding="utf-8")
    print("STOCK_OOS_RESEARCH_FINISHED",json.dumps({"rows":len(rows),"forecast":training,
        "holdout20":{m:output["mainComparisons"][m]["20"] for m in ("A","D","F","G")},
        "elapsedSec":round(time.time()-tic,1)},ensure_ascii=False),flush=True)
if __name__=="__main__":main()
