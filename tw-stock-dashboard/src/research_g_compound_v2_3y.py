"""G Compound V2 - independent consolidation before early breakout, 2023-2026.
This study is FIXED BEFORE examining 2026's V2 performance. It does NOT
relabel original G or purport to reconstruct vanilla118's secret method.
Market gate and 500k execution are exactly original G Compound v1's code.
"""
from __future__ import annotations
import json,math,time
from datetime import datetime,timedelta
from zoneinfo import ZoneInfo
import pandas as pd,numpy as np
from config import DATA_DIR,BENCHMARK
from pipeline import load_universe
from yahoo_cache import update_many,update_symbol
from research_g_regime_3y import START,END,finite,get_risk,make_g
from g_compound_early_setup import FAMILIES,RULES,historical_candidates
from research_g_compound_3y import (PRINCIPAL,BROKER,SELL_TAX,SLIP,FOLDS,
    price_bars,study_one,summary_pair)
OUT=DATA_DIR/"research"/"g_compound_v2_3y"
SELECTORS=("G",)+FAMILIES
GATES=("SCORE60","SCORE70")
TARGETS=(.05,.08)
STOPS=(.08,.12)
HOLD=(5,10)
CAPACITY=(200_000.,None)
ANCHOR={"gate":"SCORE60","tp":.05,"sl":.08,"hold":5,"cap":200_000.}
# 5 candidate families including the unchanged original G * 2^5 = 160.
EXPECT_MODELS=len(SELECTORS)*len(GATES)*len(TARGETS)*len(STOPS)*len(HOLD)*len(CAPACITY)
def candidate_id(selector,gate,tp,sl,hold,cap):
    return f"{selector.replace(' ','_')}__{gate}__TP{round(tp*100):02d}__SL{round(sl*100):02d}__H{hold}__CAP{int(cap/1000) if cap is not None else 'ALL'}"
def train_validate_selection(models):
    """Model chosen only using 2023-24 and 2025 for robustness.
    Require both positive, sufficiently many independent completed trades,
    capped drawdowns and no concentration in single period.
    No 'winner' forced if none qualifies.
    """
    ranked=[]
    for row in models:
        if row["params"]["selector"]=="G":continue
        t=row["periods"]["train"];v=row["periods"]["validation"]
        if min(t["closedTrades"],v["closedTrades"])<12:continue
        if min(t["netReturnPct"],v["netReturnPct"])<=0:continue
        if min(t["maxDDPct"],v["maxDDPct"])< -40:continue
        # With compounded capital, prefer robustness over raw upside.
        quality=(.35*min(t["netReturnPct"],100)+.55*min(v["netReturnPct"],100)
           +.5*t["maxDDPct"]+.65*v["maxDDPct"]
           +.07*min(t["closedTrades"],v["closedTrades"]))
        ranked.append((quality,row))
    ranked.sort(key=lambda x:(-x[0],x[1]["id"]))
    if not ranked:return {"status":"no_setup_passed_predefined_test",
        "criteria":"train+validation each >=12 completed trades, positive returns, daily drawdown no worse than -40%"}
    q,selected=ranked[0]
    return {"status":"chosen_without_2026","id":selected["id"],"qualityScore":round(q,3),
        "eligibleCandidates":len(ranked),"train":selected["periods"]["train"],
        "validation":selected["periods"]["validation"],"audit2026":selected["periods"]["audit2026"],
        "authorWindow2026":selected["periods"]["authorWindow2026"]}
def compact_performance(p):
    return {k:p[k] for k in ("capitalEnd","netReturnPct","maxDDPct","entryOffers",
      "filledBuys","closedTrades","wins","losses","winPct","avgNetPct","avgWinPct",
      "avgLossPct","avgHoldSessions","openAtEnd","cashAtEnd","netUnrealizedTWD")}
def run_models(dates,picks,bars,risk):
    results=[];fold_dates={key:[d for d in dates if lo<=d<=hi] for key,(lo,hi) in FOLDS.items()}
    for family in SELECTORS:
        signal=picks[family]
        for gate in GATES:
            for target in TARGETS:
                for stop in STOPS:
                    for hold in HOLD:
                        for cap in CAPACITY:
                            id=candidate_id(family,gate,target,stop,hold,cap)
                            periods={}
                            for part,segment in fold_dates.items():
                                outcome,_,_=study_one(segment,signal,bars,risk,gate,target,stop,hold,cap)
                                periods[part]=compact_performance(outcome)
                            results.append({"id":id,
                              "params":{"selector":family,"gate":gate,
                                "targetPct":round(target*100,2),
                                "stopPct":round(stop*100,2),
                                "maxHold":hold,"maxPerTradeTWD":cap},
                              "periods":periods})
        print("EARLY_SETUP_MODEL_FINISHED",family,len(results),flush=True)
    if len(results)!=EXPECT_MODELS:raise RuntimeError("Incomplete candidate combination grid")
    return results
def main():
    started=time.time();OUT.mkdir(parents=True,exist_ok=True)
    universe=[x for x in load_universe() if finite(x.get("capitalB")) is not None and float(x["capitalB"])>0]
    pullfrom=datetime.fromisoformat(START)-timedelta(days=430)
    pullto=datetime.fromisoformat(END)+timedelta(days=35)
    hist,errors=update_many([(x["code"],x["market"]) for x in universe],pullfrom,pullto)
    _,ix,err=update_symbol(BENCHMARK,pullfrom,pullto)
    if err or ix is None or ix.empty:raise RuntimeError("Index missing "+str(err))
    ix=ix.sort_values("date").drop_duplicates("date").reset_index(drop=True)
    dates=[d for d in ix.date.astype(str) if START<=d<=END]
    if len(dates)!=728:raise RuntimeError("Expected 728 official sessions, got "+str(len(dates)))
    _,riskinputs=get_risk(ix,dates)
    risk_rows=json.loads((DATA_DIR/"research"/"g_regime_3y"/"market_risk_daily.json").read_text(encoding="utf-8"))
    if [x["date"] for x in risk_rows]!=dates:raise RuntimeError("Market risk data day order mismatch")
    risk={x["date"]:x for x in risk_rows}
    index_close=pd.to_numeric(ix.close,errors="coerce")
    index_ret20=(index_close/index_close.shift(20)-1)*100
    index_rets=dict(zip(ix.date.astype(str),index_ret20))
    # THIS scanner visits the FULL exchange, not the G Top20 preselected stock pool.
    squeeze_picks,ranked,candidate_counts=historical_candidates(hist,universe,index_rets,dates)
    original,_,audit=make_g(dates,ix,universe,hist)
    picks={"G":{d:v[:1] for d,v in original.items()},**squeeze_picks}
    raw_sy={x["sym"] for family in picks.values() for day in family.values() for x in day}
    bars,priceerr=price_bars(hist,raw_sy)
    if len(bars)!=len(raw_sy):raise RuntimeError("Historical OHLC coverage incomplete: "+str(priceerr))
    print("EARLY_SETUP_READY",json.dumps({"dates":len(dates),"universe":len(universe),
         "priceSeries":len(bars),"stockErrors":len(errors),
         "candidates":candidate_counts,
         "originalGSignalDays":sum(bool(x) for x in picks["G"].values())},ensure_ascii=False),flush=True)
    cases=run_models(dates,picks,bars,risk)
    chosen=train_validate_selection(cases)
    # Cross-check exact original G baseline and previously verified G Compound V1.
    ref=json.loads((DATA_DIR/"research"/"g_compound_3y"/"highlights.json").read_text(encoding="utf-8"))
    if ref.get("riskScoreCoverage")!=728:raise RuntimeError("Original G Compound audit missing")
    baseline=next(x for x in cases if x["id"]==candidate_id("G",**ANCHOR))
    original_std=next(x for x in ref["standardBaselines"]
       if x["params"]["selector"]=="G" and x["params"]["maxPerEntryTWD"]==200_000)
    for new_fold,old_fold in (("train","train"),("validation","validation"),
         ("audit2026","audit2026"),("authorWindow2026","authorWindow2026"),("all","full")):
        lhs=baseline["periods"][new_fold];rhs=original_std[old_fold]
        if (abs(lhs["capitalEnd"]-rhs["capitalEnd"])>0.02 or
            lhs["closedTrades"]!=rhs["closedTrades"]):
            raise RuntimeError("G baseline not reproducible "+new_fold+":"+str((lhs,rhs)))
    print("VERIFIED ORIGINAL G COMPOUND MODEL PARITY",flush=True)
    report_detail=[baseline]
    for f in FAMILIES:
        report_detail.append(next(x for x in cases if x["id"]==candidate_id(f,**ANCHOR)))
    if chosen.get("id") and all(x["id"]!=chosen["id"] for x in report_detail):
        report_detail.append(next(x for x in cases if x["id"]==chosen["id"]))
    # 2026 retrospectives are published as warnings not recommendations.
    hindsight=sorted((x for x in cases if x["params"]["selector"]!="G"),
       key=lambda x:x["periods"]["authorWindow2026"]["netReturnPct"],reverse=True)[:5]
    audit_trades={};daily_equity={}
    for m in report_detail:
        p=m["params"];family=p["selector"];out={};curves={}
        for part in ("all","authorWindow2026","audit2026"):
            lo,hi=FOLDS[part];days=[d for d in dates if lo<=d<=hi]
            a,curve,trades=study_one(days,picks[family],bars,risk,p["gate"],
                p["targetPct"]/100,p["stopPct"]/100,p["maxHold"],p["maxPerTradeTWD"],logs=True)
            if abs(a["capitalEnd"]-m["periods"][part]["capitalEnd"])>.02:
                raise RuntimeError("Trade audit equity mismatch "+m["id"]+" "+part)
            out[part]={"metrics":a,"trades":trades}
            curves[part]=curve
        audit_trades[m["id"]]=out;daily_equity[m["id"]]=curves
    published_days={f:{d:ranked[f][d] for d in dates if ranked[f][d]} for f in FAMILIES}
    summary={"version":"G_COMPOUND_EARLY_CONSOLIDATION_V2_PREDECLARED",
        "createdAt":datetime.now(ZoneInfo("Asia/Taipei")).isoformat(),
        "dates":{"start":START,"end":END},"marketDays":len(dates),
        "riskDays":len(risk),"universeNow":len(universe),
        "stockDataErrors":len(errors),"historicalCandidates":candidate_counts,
        "originalGSignalDays":sum(bool(r) for r in picks["G"].values()),
        "originalGUnchangedAndParityPassed":True,"initialTWD":PRINCIPAL,
        "selectionFeatures":"Prior 5/10/15/20 day consolidation ranges exclude signal day; relative volume vs previous 20; day D breakout, price vs MA20, index-relative return; only information at D close.",
        "ruleDefinitions":RULES,"families":SELECTORS,
        "testConfig":{"gates":GATES,"targets":[100*x for x in TARGETS],
          "stops":[100*x for x in STOPS],"holds":HOLD,
          "capacityTWD":CAPACITY,"marketScoresFullyVerified":True,
          "trainingPeriods":FOLDS},
        "execution":"Identical unmodified G Compound V1 study_one cash model: buy next open if <=D close*1.03; TP/SL OHLC stop-first ambiguity; costs; daily mark; no overlapping cash reuse.",
        "selectionFromTrainValidation":chosen,"totalCases":len(cases),
        "baselineSetupModels":report_detail,
        "retrospective2026OnlyDontSelect":[{"id":x["id"],"authorWindow":x["periods"]["authorWindow2026"]} for x in hindsight],
        "models":cases,
        "limitations":["This is a public research hypothesis, NOT vanilla118's undisclosed ranking/target/stop methodology.",
        "G Compound V1 had already exposed 2026 results, so date-split 2026 evaluation is chronologically separated but NOT a pristine blind holdout.",
        "Historical full universe uses latest listed/OTC companies and today's capital, excluding delisted firms: survivorship bias.",
        "Daily OHLC cannot prove which price hit first intraday; assumes stop first on dual touch, limit target demands 0.1% margin.",
        "Listed stock odd lot / limit up-down / slippage and settlement feasibility not independently confirmed.",
        "Only truly date-verified TWSE market breadth and foreign flows; TX night data omitted as unverified.",
        "No fabricated intraday institutional buy/sell acceleration or thematic classification; these require reliable historical dated sources.",
        "16 and more candidate variants are explorative; multiple testing may overstate best backtest performance.",
        "No guaranteed repeatability or ability to turn 500k into the reported 3.659m; author brokerage statements do not verify all flows.",
        "Valuation of open holdings at adjusted close after estimated sell costs is NOT fully realized profit."]}
    files={"summary.json":summary,"picks.json":{"version":summary["version"],
        "marketDays":len(dates),"families":published_days},
        "trades.json":{"version":summary["version"],"cases":audit_trades},
        "equity.json":{"version":summary["version"],"dates":dates,"cases":daily_equity}}
    for name,value in files.items():
        (OUT/name).write_text(json.dumps(value,ensure_ascii=False,
            indent=2 if name=="summary.json" else None),encoding="utf-8")
    print("G_COMPOUND_V2_DONE",json.dumps({"models":len(cases),"selected":chosen,
      "hindsight2026":hindsight[0] if hindsight else None,
      "elapsedSeconds":round(time.time()-started)},ensure_ascii=False),flush=True)
if __name__=="__main__":main()
