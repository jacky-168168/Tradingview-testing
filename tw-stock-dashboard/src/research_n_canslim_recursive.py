"""N CANSLIM factor screening + monthly recursive Top1 model, 2023-2026.

1. Authoritative full-market historical MOPS revenue and EPS snapshots must
   have passed strict source completeness checks.
2. Growth and market technical eligibility at close D only.
3. As-of D revenue/EPS information is gated by conservative RELEASE DELAY
   ESTIMATES; MOPS historical source can include later restatements.
4. Trade labels are learned only when their hypothetical exit is complete,
   monthly next models trained only on matured data.
5. 2025 selection, 2026 chronological audit, apples-to-apples G V3 and 0050.
"""
from __future__ import annotations
import collections,json,math,time
from datetime import datetime,timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
import numpy as np,pandas as pd
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import Ridge
from sklearn.ensemble import HistGradientBoostingRegressor
from config import BENCHMARK,DATA_DIR
from pipeline import load_universe
from yahoo_cache import update_many,update_symbol
from research_g_regime_3y import START,END,finite,get_risk
from research_g_compound_3y import (PRINCIPAL,BUY_FACTOR,SELL_FACTOR,
    price_bars,study_one)
from research_g_compound_walkforward import (PLANS,ALGORITHMS,MODES,CAPS,
    GATE,MIN_TRAIN,trainer,historical_label,with_mature_labels,
    assert_training_past,FOLDS_TEST,model_preference)
from n_canslim_features import FundamentalIndex,RULES,FEATURE_NAMES,generate_n_candidates
OUT=DATA_DIR/"research"/"n_canslim"
SOURCE=OUT
VERSION="N_CANSLIM_GROWTH_MOMENTUM_RECURSIVE_V1"
HIST_LABEL_FLOOR=70
def to_plain(p):
    cols=("start","end","capitalEnd","netReturnPct","maxDDPct",
      "filledBuys","closedTrades","wins","losses","winPct","avgNetPct",
      "avgWinPct","avgLossPct","avgHoldSessions","openAtEnd","cashAtEnd")
    return {k:p.get(k) for k in cols}
def perf_stats(dates,curve):
    """Daily NAV Sharpe zero benchmark risk-free rate, 252 scaling, CAGR.
    Drawdown includes nominal initial capital; no double-counting 0050 tax.
    """
    vals=np.asarray(curve,float)
    if len(vals)!=len(dates) or len(vals)<40 or np.any(vals<=0) or not np.isfinite(vals).all():
        raise RuntimeError("Cannot compute risk stats on incomplete NAV")
    daily=np.diff(np.r_[PRINCIPAL,vals])/np.r_[PRINCIPAL,vals][:-1]
    sd=float(np.std(daily,ddof=1));sharpe=(np.sqrt(252)*float(np.mean(daily))/sd) if sd>1e-12 else None
    dd=vals/np.maximum.accumulate(np.r_[PRINCIPAL,vals])[1:]-1
    years=(pd.Timestamp(dates[-1])-pd.Timestamp(dates[0])).days/365.2425
    return {"start":dates[0],"end":dates[-1],"finalTWD":round(float(vals[-1]),2),
      "netReturnPct":round(float(100*(vals[-1]/PRINCIPAL-1)),3),
      "annualizedCAGRpct":round(float(100*((vals[-1]/PRINCIPAL)**(1/years)-1)),3) if years>0 else None,
      "annualizedSharpeRf0":round(sharpe,3) if sharpe is not None else None,
      "maxDrawdownPct":round(100*float(np.min(dd)),3),
      "dailyVolAnnualizedPct":round(float(sd*np.sqrt(252)*100),3),
      "dailySamples":len(vals),"riskFreeRateAssumed":0.0}
def benchmark_0050(dates,etf):
    """Index 0050 adjusted OHLC, first local session buys at adjusted open.
    Portfolio end valuation includes a theoretical after-cost sell at market
    close; dividends approximated by Yahoo adjusted series.
    """
    q=etf.sort_values("date").drop_duplicates("date",keep="last").copy()
    for col in ("open","close","adjclose"):q[col]=pd.to_numeric(q[col],errors="coerce")
    factor=q.adjclose/q.close.replace(0,np.nan)
    q["adjOpen"]=q.open*factor
    p=q.set_index(q.date.astype(str))
    first=next((d for d in dates if d in p.index and float(p.loc[d,"adjOpen"])>0),None)
    if first is None:raise RuntimeError("0050 benchmark lacks valid entry")
    open_px=float(p.loc[first,"adjOpen"])
    qty=math.floor(PRINCIPAL/(open_px*BUY_FACTOR))
    invested=qty*open_px*BUY_FACTOR
    remaining=PRINCIPAL-invested
    curves=[];last=None;stale=0
    for day in dates:
        if day<first:curves.append(PRINCIPAL);continue
        if day in p.index:
            c=float(p.loc[day,"adjclose"])
            if not math.isfinite(c) or c<=0:raise RuntimeError("0050 missing adjusted close "+day)
            last=c
        else:stale+=1
        if last is None:raise RuntimeError("0050 close missing "+day)
        curves.append(remaining+qty*last*(1-.001425-.001-.001))
    return curves,{"symbol":"0050.TW","firstBuyDate":first,"firstAdjustedOpen":round(open_px,4),
        "shares":qty,"remainingCashTWD":round(remaining,2),"staleSessionCount":stale,
        "costBasis":"broker 0.1425% per side, 0.1% exit stock ETF tax, 0.1% slippage each side"}
def monthly_n_learn(dates,pool,labels,kind,plan,mode):
    """Months without enough historical matured examples = NO BUY, not fake
    fitted model. No Q4 report appears until its safe-release date.
    """
    periods=collections.defaultdict(list)
    for d in dates:
        if d>="2025-01-01":periods[d[:7]].append(d)
    training=labels[plan];out={};audit=[]
    for month,daylist in sorted(periods.items()):
        cutoff=daylist[0]
        maturity=[t for t in training if t["maturity"]<cutoff and t["date"]<cutoff]
        assert_training_past(maturity,cutoff)
        wins=sum(t["pnl"]>0 for t in maturity);losses=len(maturity)-wins
        qualified=(len(maturity)>=HIST_LABEL_FLOOR and wins>=18 and losses>=18)
        predictor=None
        if qualified:
            X=np.asarray([r["features"] for r in maturity],float)
            y=np.asarray([max(-.35,min(.35,r["pnl"]))*100 for r in maturity],float)
            predictor=trainer(kind,X,y)
        accepted=0;abstained=0
        for d in daylist:
            stocks=pool.get(d) or []
            if predictor is None or not stocks:
                out[d]=[];continue
            values=predictor(np.asarray([r["features"] for r in stocks],float))
            if not np.isfinite(values).all():raise RuntimeError("NaN prediction "+d)
            ranked=sorted(zip(stocks,values),key=lambda z:(-float(z[1]),z[0]["code"]))
            winner,expected=ranked[0]
            if mode=="POSITIVE" and float(expected)<=0:
                out[d]=[];abstained+=1;continue
            out[d]=[{k:winner[k] for k in ("sym","code","name","close","sources")}|
                {"predictedNetPct":round(float(expected),4),
                 "candidatesRanked":len(stocks),
                 "epsAvailableFrom":winner["metrics"]["epsAvailableFrom"],
                 "revAvailableFrom":winner["metrics"]["revAvailableFrom"],
                 "epsYtdGrowthPct":winner["metrics"]["epsYtdGrowthPct"],
                 "revenueYoYPct":winner["metrics"]["revenueYoYPct"],
                 "rsPercentile":winner["metrics"]["rsPercentile"],
                 "near52WeekHighPct":winner["metrics"]["near52WeekHighPct"]}]
            if not (out[d][0]["epsAvailableFrom"]<=d and out[d][0]["revAvailableFrom"]<=d):
                raise AssertionError("Future EPS or revenue leaked into N model "+d)
            accepted+=1
        audit.append({"month":month,"firstTradeDate":cutoff,
          "trained":qualified,"historicalMaturedLabels":len(maturity),
          "winsAvailable":wins,"lossesAvailable":losses,
          "latestUsedLabelExit":max((v["maturity"] for v in maturity),default=None),
          "newSignals":accepted,"abstainedNonPositive":abstained})
        print("N_RECURSIVE_MONTH",kind,plan,mode,month,
            "train",len(maturity),"signals",accepted,flush=True)
    return out,audit
def main():
    started=time.monotonic();OUT.mkdir(parents=True,exist_ok=True)
    req=(SOURCE/"fundamental_coverage.json",SOURCE/"monthly_revenue.json",SOURCE/"eps_ytd.json")
    missing=[p.name for p in req if not p.exists()]
    if missing:raise RuntimeError("Historical official MOPS fundamentals NOT READY: "+str(missing))
    coverage=json.loads(req[0].read_text(encoding="utf-8"))
    if coverage.get("failures") or coverage.get("revenueRows",0)<20000 or coverage.get("epsRows",0)<5000:
        raise RuntimeError("Official full-market fundamental coverage failed validation")
    funds=FundamentalIndex(
        json.loads(req[1].read_text(encoding="utf-8")),
        json.loads(req[2].read_text(encoding="utf-8")))
    universe=[x for x in load_universe() if finite(x.get("capitalB")) is not None and float(x["capitalB"])>0]
    begin=datetime.fromisoformat(START)-timedelta(days=430)
    finish=datetime.fromisoformat(END)+timedelta(days=35)
    hist,errors=update_many([(z["code"],z["market"]) for z in universe],begin,finish)
    _,index,indexerr=update_symbol(BENCHMARK,begin,finish)
    if indexerr or index is None or index.empty:raise RuntimeError("TWII benchmark unavailable: "+str(indexerr))
    index=index.sort_values("date").drop_duplicates("date").reset_index(drop=True)
    days=[d for d in index.date.astype(str) if START<=d<=END]
    if len(days)!=728:raise RuntimeError("Expected verified 728 trade days, got "+str(len(days)))
    official,_=get_risk(index,days)
    prev=json.loads((DATA_DIR/"research/g_regime_3y/market_risk_daily.json").read_text(encoding="utf-8"))
    if [x["date"] for x in prev]!=days:raise RuntimeError("Historical risk date mismatch")
    risks={z["date"]:z for z in prev}
    if any(official[d]!=risks[d]["score"] for d in days):raise RuntimeError("Historical market score drift")
    pool,top3,stat=generate_n_candidates(hist,universe,funds,risks,days)
    if stat["signalDays"]<90:raise RuntimeError("N factor screen too sparse to validate across 728 days: "+str(stat))
    all_sy={p["sym"] for candidates in pool.values() for p in candidates}
    bars,barerr=price_bars(hist,all_sy)
    if len(bars)!=len(all_sy):raise RuntimeError("N selected stock price data missing")
    labels,label_audit=with_mature_labels(pool,bars,days)
    print("N_CANDIDATES_READY",json.dumps({"stockUniverse":len(universe),"signal":stat,
        "MOPS":funds.coverage,"labels":label_audit,"barSymbols":len(bars),
        "priceErrors":len(errors)},ensure_ascii=False),flush=True)
    daily={};fit_audit={};cases=[]
    periods={k:[d for d in days if lo<=d<=hi] for k,(lo,hi) in FOLDS_TEST.items()}
    for algorithm in ALGORITHMS:
      for plan in PLANS:
        for mode in MODES:
            picks,train_audit=monthly_n_learn(days,pool,labels,algorithm,plan,mode)
            key=f"{algorithm}__{plan}__{mode}";daily[key]=picks;fit_audit[key]=train_audit
            for cap in CAPS:
                id=f"N__{key}__{'ALL' if cap is None else 'CAP200'}"
                fold={}
                for name,market_days in periods.items():
                    pp=PLANS[plan]
                    m,ledger,trades=study_one(market_days,picks,bars,risks,GATE,
                         pp["tp"],pp["sl"],pp["hold"],cap,logs=True)
                    fold[name]={**to_plain(m),"metrics":perf_stats(market_days,[r["equity"] for r in ledger])}
                cases.append({"id":id,"algorithm":algorithm,"plan":plan,"mode":mode,
                    "maxPerTradeTWD":cap,"periods":fold})
      print("N_MODEL_FAMILY_DONE",algorithm,flush=True)
    if len(cases)!=16:raise RuntimeError("N candidate grid should have 16 cases")
    selection=[]
    for case in cases:
        sample=case["periods"]["validation2025"]
        if sample["closedTrades"]<20 or sample["netReturnPct"]<=0 or sample["maxDDPct"]< -30:continue
        objective=sample["netReturnPct"]+.6*sample["maxDDPct"]-20/math.sqrt(sample["closedTrades"])
        selection.append((objective,case))
    selection.sort(key=lambda z:(-z[0],z[1]["id"]))
    if selection:
        _,best=selection[0];selected={"status":"selected_by_2025_only",
            "id":best["id"],"eligibleModels":len(selection),
            "validation2025":best["periods"]["validation2025"],
            "audit2026":best["periods"]["audit2026"]}
    else:
        selected={"status":"none_passed_validation_2025","eligibleModels":0,
            "gate":"2025 closed>=20, positive net return, MDD no worse than -30%"}
    # 0050 using exactly same fold-day calendar, no restricted N market gate.
    _,etf,etferr=update_symbol("0050.TW",begin,finish)
    if etferr or etf is None or etf.empty:raise RuntimeError("Cannot compare N to 0050, missing adjusted OHLC")
    reference={}
    for name,market_days in periods.items():
        nav,desc=benchmark_0050(market_days,etf)
        reference[name]=perf_stats(market_days,nav) | {"execution":desc}
    base_v3=json.loads((DATA_DIR/"research/g_compound_walkforward_3y/summary.json").read_text(encoding="utf-8"))
    if base_v3.get("officialRiskDays")!=728:raise RuntimeError("G V3 validated comparable audit unavailable")
    v3=base_v3["selectedBy2025Only"]
    # Different N and V3 picks require the SAME execution rule to attribute
    # improvements to factor ranking, not reward a different stop/hold/sizing.
    matched=None
    if selected.get("id"):
        chosen=next(v for v in cases if v["id"]==selected["id"])
        v3_id=f'{chosen["algorithm"]}__{chosen["plan"]}__{chosen["mode"]}__'+("ALL" if chosen["maxPerTradeTWD"] is None else "CAP200")
        other=next((z for z in base_v3["allCandidateModels"] if z["id"]==v3_id),None)
        if other is None:raise RuntimeError("Exact V3 exit/sizing comparator missing: "+v3_id)
        matched={"N":chosen["id"],"G_V3":v3_id,
            "rules":{"tpPct":100*PLANS[chosen["plan"]]["tp"],
              "stopPct":100*PLANS[chosen["plan"]]["sl"],
              "holdSessions":PLANS[chosen["plan"]]["hold"],
              "maxTradeTWD":chosen["maxPerTradeTWD"],"marketGate":GATE},
            "N_2025":chosen["periods"]["validation2025"],
            "N_2026":chosen["periods"]["audit2026"],
            "G_V3_2025":to_plain(other["periods"]["validation2025"]),
            "G_V3_2026":to_plain(other["periods"]["audit2026"])}
    details={};curves={};picks_daily={}
    for x in cases:
        if x["algorithm"]=="Ridge" and x["plan"]=="SWING" and x["mode"]=="POSITIVE" and x["maxPerTradeTWD"] is None:keep=True
        else:keep=x["id"]==selected.get("id")
        if not keep:continue
        p=daily[f'{x["algorithm"]}__{x["plan"]}__{x["mode"]}']
        details[x["id"]]={};curves[x["id"]]={}
        for period,market_days in periods.items():
            settings=PLANS[x["plan"]]
            met,ledger,trades=study_one(market_days,p,bars,risks,GATE,
                settings["tp"],settings["sl"],settings["hold"],x["maxPerTradeTWD"],logs=True)
            if abs(met["capitalEnd"]-x["periods"][period]["capitalEnd"])>.02:
                raise RuntimeError("N trade equity reconciliation failure "+period)
            details[x["id"]][period]={"metrics":met,"trades":trades}
            curves[x["id"]][period]=ledger
        picks_daily[x["id"]]={d:p.get(d,[]) for d in days if d>="2025-01-01"}
    historical_signal_preview={d:top3[d] for d in days if d>="2025-01-01" and top3[d]}
    summary={"version":VERSION,"generatedAt":datetime.now(ZoneInfo("Asia/Taipei")).isoformat(),
        "marketDays":len(days),"officialRiskDays":len(risks),
        "baseUniverse":len(universe),"stockPriceErrors":len(errors),
        "fundamentals":dict(funds.coverage),"historicalSource":"MOPS historical bulk aggregate, revised",
        "disclosureGate":"Monthly no earlier than following month 16th; quarter Q1 May22 Q2 Aug22 Q3 Nov22 Q4 Apr12 next year. Conservative estimated release, NOT verified individual filing timestamps.",
        "rules":RULES,"featureNames":FEATURE_NAMES,
        "signal":stat,"label":label_audit,"trainingAudit":fit_audit,
        "capitalInitialTWD":PRINCIPAL,"recursion":"2025-2026 monthly models trained using ONLY historical hypothetical trades CLOSED before each month's first market session; daily D close Top1 ranked; entry D+1 open",
        "testWindows":FOLDS_TEST,"exitTemplates":PLANS,
        "modelSelection":"2025 positive returns and >=20 closed trades, maxDD > -30; no 2026 optimization",
        "models":cases,"modelCount":len(cases),"selected":selected,
        "benchmark0050":reference,
        "baselineGV3Selected":{"id":v3.get("id"),"2025":v3.get("validation2025"),"2026":v3.get("audit2026")},
        "matchedWithG_V3":matched,
        "warnings":["Historical MOPS pages may contain amended/restated data; exact original release timestamp not preserved. Even conservative as-of delay cannot fully remove data revision leakage.",
          "Present-day listed/OTC universe excludes delisted firms, introducing survivorship bias.",
          "Monthly N retraining only uses completed prior simulation labels; HOWEVER 2026 historical outcomes were examined by earlier G model research. No pristine unseen holdout exists.",
          "Screener filters minimum 20% EPS year-on-year growth in year-to-date EPS, NOT raw quarter EPS growth.",
          "Price momentum includes 252-session return and same-date full universe RS percentile; stock-specific prices beyond signal D are used ONLY for matured training labels or evaluation.",
          "Revenue near 12-report high compares as-of published revenues, not current historical revised high.",
          "0050 benchmark uses adjusted OHLC and initial-day entry, dividends approximated and commissions/slippage/ETF tax; execution is simulated.",
          "Sharpe assumes 0% risk-free rate and annualizes daily account returns by sqrt 252; includes days in cash.",
          "CANSLIM factor family is an interpretation, not William O'Neil's exact proprietary scoring formula.",
          "No invented 2026-09 monthly figures or future 2026Q3 earnings.",
          "MOPS source full market includes domestic and foreign in _0 historical page; no missing month silently filled.",
          "Daily OHLC stop-before-target pessimistic ambiguity handling still cannot reproduce real odd lot, limit order queue, suspension or broker settlement cash availability.",
          "If no model passes 2025 gate, do not recommend N even if hindsight 2026 winner exists."]}
    outputs={"summary.json":summary,"trades.json":{"version":VERSION,"models":details},
        "equity.json":{"version":VERSION,"models":curves},
        "picks.json":{"version":VERSION,"signalTop3":historical_signal_preview,
            "modelDailyTop1":picks_daily}}
    for name,data in outputs.items():
        (OUT/name).write_text(json.dumps(data,ensure_ascii=False,
            indent=2 if name=="summary.json" else None),encoding="utf-8")
    print("N_CANSLIM_BACKTEST_COMPLETED",json.dumps({"candidateStockDays":stat["rsAndGrowthQualifiedStockDays"],
        "candidateDates":stat["signalDays"],"models":len(cases),"selected":selected,
        "0050_2025":reference["validation2025"]["netReturnPct"],
        "0050_2026":reference["audit2026"]["netReturnPct"],
        "elapsedSec":round(time.monotonic()-started)},ensure_ascii=False),flush=True)
if __name__=="__main__":main()
