"""Cash-constrained 3-year A/D/F/G risk-gate stress audit. Research only."""
from __future__ import annotations
import collections,json,math,time
from datetime import datetime,timedelta
from zoneinfo import ZoneInfo
from pathlib import Path
import pandas as pd
import numpy as np
from config import DATA_DIR,BENCHMARK
from pipeline import load_universe
from yahoo_cache import update_many,update_symbol,to_symbol
from research_g_regime_3y import START,END,make_g,get_risk,finite
import research_g_pro_3y as core
OUT=DATA_DIR/"research"/"market_cash_oos_3y"
ARCHIVES=("2023-01-01_2023-12-31.json","2024-01-01_2024-12-31.json","2025-01-01_2025-12-31.json","2026-01-01_2026-10-07.json")
FOLDS={"train":(START,"2024-12-31"),"validation":("2025-01-01","2025-12-31"),"holdout":("2026-01-01",END)}
GATES=("BASE","GE60","GE70","GE80","GE60_NO_TOP","GE60_NO_HEAT","GE60_NEAR_HIGH","LOW40","LOW40_OVERSOLD","LOW40_REBOUND")
HORIZONS=(10,20)
VETO=("🔴 Strong Top Reversal","🟠 Top Reversal Attempt","🔴 Extreme Overbought")
def read(p):return json.loads(Path(p).read_text(encoding="utf-8"))
def build_ad(dates):
    out={"A":{},"D":{}};audit=collections.Counter();valid=set(dates);index={d:i for i,d in enumerate(dates)}
    for filename in ARCHIVES:
        report=read(DATA_DIR/"backtest"/filename);byid={z["id"]:z for z in report["models"]}
        if not {"A","D"}.issubset(byid):raise RuntimeError("Missing archived A/D "+filename)
        for model in out:
            groups=collections.defaultdict(list)
            for tr in byid[model]["signals"]:
                d=str(tr["signalDate"]);rank=int(tr["rank"])
                if d in valid and rank in (1,2,3):groups[d].append(tr)
            for d,rows in groups.items():
                if d in out[model]:raise RuntimeError("Duplicate signal "+d+" "+model)
                rows.sort(key=lambda x:x["rank"])
                i=index[d]
                if len(rows)!=3 or [x["rank"] for x in rows]!=[1,2,3]:
                    audit[model+" missing Top3"]+=1;continue
                if i+1>=len(dates) or any(x.get("buyDate")!=dates[i+1] for x in rows):
                    audit[model+" buy-date mismatch"]+=1;continue
                out[model][d]=[{"code":str(x["code"]),"market":str(x["market"]),
                    "sym":to_symbol(str(x["code"]),str(x["market"]))} for x in rows]
    if len(out["A"])<650 or len(out["D"])<400:raise RuntimeError("Annual backtest A/D archive too incomplete")
    return out,dict(audit)
def price_map(hist,symbols):
    price={};missing=[]
    for sy in symbols:
        x=hist.get(sy)
        if x is None or x.empty:missing.append(sy);continue
        x=x.copy()
        for c in ("open","high","low","close","adjclose","volume"):
            x[c]=pd.to_numeric(x[c],errors="coerce")
        x=x.dropna(subset=["open","close","adjclose"])
        x=x[(x.open>0)&(x.close>0)&(x.adjclose>0)]
        if x.empty:missing.append(sy);continue
        x["adjOpen"]=x.open*x.adjclose/x.close;x["adjClose"]=x.adjclose
        price[sy]=x.drop_duplicates("date",keep="last").sort_values("date").set_index("date",drop=False)
    return price,missing
def gate(model,label,day,risk,dayindex,priorHigh,dates):
    x=risk[day];score=int(x["score"]);top=str(x.get("topState") or "")
    if label=="BASE":return (score>=60 or x.get("bottomState")=="🟢 Strong Bottom Reversal") if model=="F" else True
    if label=="GE60":return score>=60
    if label=="GE70":return score>=70
    if label=="GE80":return score>=80
    if label=="GE60_NO_TOP":return score>=60 and top not in VETO
    if label=="GE60_NO_HEAT":return score>=60 and top not in VETO and not(x.get("mode")=="TOP" and float(x.get("distMA20") or 0)>=6 and float(x.get("ret5") or 0)>=8)
    if label=="GE60_NEAR_HIGH":
        dist=None if day not in priorHigh else (float(x["index"])/priorHigh[day]-1)*100
        return score>=60 and top not in VETO and not(dist is not None and -2<=dist<=0 and x.get("mode")=="TOP")
    if label=="LOW40":return score<40
    if label=="LOW40_OVERSOLD":return score<40 and int(x.get("oversoldScore") or 0)>=3
    if label=="LOW40_REBOUND":
        i=dayindex[day]
        return i>0 and int(risk[dates[i-1]]["score"])<=40 and score>40 and float(x.get("dayRet") or 0)>0
    raise ValueError(label)
def run(dates,picks,prices,eligible,h,slip):
    # Independent cash simulator used by previous G Pro 3-year study.
    oldbuy,oldsell=core.BUY_FEE,core.SELL_FEE
    core.BUY_FEE=.001425+slip;core.SELL_FEE=.004425+slip
    try:return core.simulate_cash(dates,picks,prices,eligible,50,h)
    finally:core.BUY_FEE=oldbuy;core.SELL_FEE=oldsell
def main():
    tic=time.time();OUT.mkdir(parents=True,exist_ok=True)
    universe=[x for x in load_universe() if finite(x.get("capitalB")) and float(x["capitalB"])>0]
    if len(universe)<1700:raise RuntimeError("Current universe too small")
    begin=datetime.fromisoformat(START)-timedelta(days=430)
    end=datetime.fromisoformat(END)+timedelta(days=35)
    print("CASH_STRESS fetching full stock universe",len(universe),flush=True)
    histories,errors=update_many([(x["code"],x["market"]) for x in universe],begin,end)
    _,idx,ie=update_symbol(BENCHMARK,begin,end)
    if ie or idx is None or idx.empty:raise RuntimeError("Official benchmark OHLC missing "+str(ie))
    idx=idx.sort_values("date").drop_duplicates("date",keep="last").reset_index(drop=True)
    dates=[d for d in idx.date.astype(str) if START<=d<=END]
    if len(dates)!=728:raise RuntimeError("Official 728-day calendar required: "+str(len(dates)))
    score,officialInputs=get_risk(idx,dates)
    raw=read(DATA_DIR/"research"/"g_regime_3y"/"market_risk_daily.json")
    if [x["date"] for x in raw]!=dates or any(x["score"]!=score[x["date"]] for x in raw):
        raise RuntimeError("Risk score official history parity mismatch")
    risk={x["date"]:x for x in raw};positions={d:i for i,d in enumerate(dates)}
    picks,rankAudit=build_ad(dates)
    genuineG,gprices,gAudit=make_g(dates,idx,universe,histories)
    original=read(DATA_DIR/"research"/"g_regime_3y"/"trades.json")
    frozen=next(x for x in original["models"] if x["model"]=="SPOT_0" and x["horizon"]==20)
    drift=[x["date"] for x in frozen["trades"] if [s["code"] for s in genuineG[x["date"]]]!=x["codes"]]
    if drift:raise RuntimeError("G reconstruction differs from validated original G: "+str(drift[:5]))
    # Fair 3-name strategy comparison: do not let G invest in only one or two stocks
    # while A and D are required to supply the full ranked Top3.
    picks["G"]={d:rows if len(rows)==3 else [] for d,rows in genuineG.items()}
    # Daily mark every selected stock, never assume an unpriced stock generated zero return.
    symbols={x["sym"] for model in picks.values() for rows in model.values() for x in rows}
    prices=dict(gprices);extras=symbols-set(prices)
    additional,missing=price_map(histories,extras);prices.update(additional)
    absent=symbols-set(prices)
    if len(absent)>max(25,len(symbols)*.03):raise RuntimeError("Missing >3% of selected stock daily price histories")
    idxDates=idx.date.astype(str).tolist();idxpos={d:i for i,d in enumerate(idxDates)}
    high120={d:float(pd.to_numeric(idx.high.iloc[idxpos[d]-120:idxpos[d]],errors="coerce").max())
             for d in dates if idxpos[d]>=120}
    results=[];curves={};fold_names=("all","train","validation","holdout")
    for model in ("A","D","F","G"):
        stocks=picks["D"] if model=="F" else picks[model]
        for horizon in HORIZONS:
            for policy in GATES:
                regimes={d:100 if gate(model,policy,d,risk,positions,high120,dates) else 0 for d in dates}
                for slip in (0.,.001):
                    folds={};overallCurve=None
                    for fold in fold_names:
                        lo,hi=(START,END) if fold=="all" else FOLDS[fold]
                        calendar=[d for d in dates if lo<=d<=hi]
                        r,c,deals=run(calendar,stocks,prices,regimes,horizon,slip)
                        # Deals are per stock (3 records per completed Top3 basket).
                        folds[fold]={**r,"closedBaskets":len({z["signalDate"] for z in deals})}
                        if slip==0 and policy in ("BASE","GE60","GE80","GE60_NO_TOP"):
                            curves.setdefault(model+"_"+policy+"_"+str(horizon),{})[fold]={"date":[v["date"] for v in c],"equity":[v["equity"] for v in c]}
                    results.append({"model":model,"gate":policy,"hold":horizon,"slippagePerSidePct":round(100*slip,2),**folds})
            print("CASH_STRESS done",model,"H",horizon,flush=True)
    key={(x["model"],x["gate"],x["hold"],x["slippagePerSidePct"]):x for x in results}
    # This fixed candidate family is chosen on 2023-24 train + 2025 validation ONLY.
    candidates=[]
    for x in results:
        if x["slippagePerSidePct"]!=0 or x["gate"] not in ("BASE","GE60","GE70","GE80","GE60_NO_TOP"):continue
        a=x["train"];b=x["validation"]
        if a["closedBaskets"]<8 or b["closedBaskets"]<5 or a["netReturnPct"]<=0 or b["netReturnPct"]<=0:continue
        objective=min(a["netReturnPct"],b["netReturnPct"])+.35*a["dailyMaxDrawdownPct"]+.45*b["dailyMaxDrawdownPct"]
        candidates.append((objective,x))
    candidates.sort(key=lambda t:(-t[0],t[1]["model"],t[1]["gate"],t[1]["hold"]))
    winner=None
    if candidates:
        objective,x=candidates[0];stress=key[x["model"],x["gate"],x["hold"],.1]
        winner={"model":x["model"],"gate":x["gate"],"hold":x["hold"],"objective":round(objective,3),
            "train":x["train"],"validation":x["validation"],"holdout":x["holdout"],
            "holdoutSlippage0p10EachWay":stress["holdout"],"eligibleCandidates":len(candidates)}
    snapshots={}
    for model in ("A","D","F","G"):
        snapshots[model]={}
        for policy in ("BASE","GE60","GE70","GE80","GE60_NO_TOP","LOW40","LOW40_OVERSOLD","LOW40_REBOUND"):
            snapshots[model][policy]={str(h):key[model,policy,h,0.] for h in HORIZONS}
    result={"version":"A_D_F_G_FULL_CAPITAL_DAILY_OOS_V1",
       "createdAt":datetime.now(ZoneInfo("Asia/Taipei")).isoformat(),
       "period":{"start":START,"end":END},"tradingDays":len(dates),"riskCoverage":len(score),
       "currentUniverseSize":len(universe),"stockDownloadErrors":len(errors),
       "fullTop3SignalDays":{m:sum(len(v)==3 for v in p.values()) for m,p in picks.items()},
       "rankAudit":rankAudit,"originalGParity":True,"GAudit":gAudit,
       "priceSymbolsNeeded":len(symbols),"missingSelectedPriceHistory":len(absent),
       "method":{"capitalTWD":1000000,"holdingTradingDays":list(HORIZONS),"slippageEachWay":list(map(lambda t:round(100*t,2),(0.,.001))),
          "sizing":"One basket at a time, 100% capital equally split among Top3, no leverage or overlapping exposure",
          "timing":"Signal D close, next D+1 open buy, D+H close exit, per-day adjusted-close mark-to-market",
          "F":"D original picks, official score>=60 or Strong Bottom exception (policy BASE)",
          "G":"Rebuilt original G and matched every original archived executed Top3",
          "cost":"0.1425% brokerage per side, 0.30% stock-sale tax, plus explicit extra slippage scenario",
          "split":"2023-24 train, 2025 validation, 2026 chronological holdout; accounts restarted at each fold",
          "warnings":["2026 previously examined; not a genuinely blind out-of-sample",
             "Survivorship bias: present-day universe/capital; historical Yahoo adjusted OHLC revision",
             "Index Risk Score full 728 days, TX futures overnight not yet historically validated",
             "Historical A/D archived picks based on prior release methodology",
             "Delayed/unquoted exits and stale quotes are tracked; no assumed free execution",
             "No modeling for limit-up unfillable opens, bid-ask, market impact or margin",
             "High-120-day proximity and oversold hypotheses exploratory; sample sizes can be tiny",
             "Comparisons must consider cash idle time, trade counts, drawdowns, timing, costs and sample instability"]},
       "selectedUsingTrainValidationOnly":winner,"results":results,"snapshots":snapshots,
       "elapsedSeconds":round(time.time()-tic)}
    (OUT/"summary.json").write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False),encoding="utf-8")
    (OUT/"equity.json").write_text(json.dumps(curves,ensure_ascii=False),encoding="utf-8")
    brief={m:{p:{str(h):{"holdoutRet":key[m,p,h,0.]["holdout"]["netReturnPct"],"holdoutMDD":key[m,p,h,0.]["holdout"]["dailyMaxDrawdownPct"]} for h in HORIZONS} for p in ("BASE","GE60","GE80")} for m in ("A","D","F","G")}
    print("CASH_STRESS_COMPLETED",json.dumps({"winner":winner,"priceMissing":len(absent),"brief":brief,
          "elapsedSec":result["elapsedSeconds"]},ensure_ascii=False),flush=True)
if __name__=="__main__":main()
