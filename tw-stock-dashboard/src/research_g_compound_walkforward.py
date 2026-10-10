"""G Compound V3: monthly recursive walk-forward train, daily causal Top1.
No future trade result can train a model until after its historical EXIT DATE.
Base candidate set is all four V2 early-setup families PLUS historical G Top3;
full CURRENT listed/OTC universe, no inherited G screen for V2 candidates.
2023-24 initial label training; monthly walk-forward 2025-2026, validation
model selection only in 2025, audit in 2026. We never fit to maximize 2026.
"""
from __future__ import annotations
import collections,json,math,time
from datetime import datetime,timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
import numpy as np,pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler
from config import BENCHMARK,DATA_DIR
from pipeline import load_universe
from yahoo_cache import update_many,update_symbol,to_symbol
from research_g_regime_3y import START,END,finite,make_g,get_risk
from g_compound_early_setup import FAMILIES,asof_features,classify_frame
from research_g_compound_3y import (PRINCIPAL,BUY_FACTOR,SELL_FACTOR,
    TP_FILL_BUFFER,PRICE_CHASE_LIMIT,FOLDS,price_bars,study_one)
OUT=DATA_DIR/"research"/"g_compound_walkforward_3y"
PLANS={"FAST":{"tp":.05,"sl":.08,"hold":5},
       "SWING":{"tp":.08,"sl":.12,"hold":10}}
ALGORITHMS=("Ridge","HGB")
MODES=("ALWAYS","POSITIVE")
CAPS=(200_000.,None)
GATE="SCORE60"
EVAL_START="2025-01-01"
FOLDS_TEST={"validation2025":("2025-01-01","2025-12-31"),
            "audit2026":("2026-01-01",END),
            "authorWindow2026":("2026-04-15","2026-10-02"),
            "allWalkforward":(EVAL_START,END)}
FEATURES=("rs20","rvol","prev5RangePct","prev10RangePct","prev15RangePct",
    "prev20RangePct","break10Pct","break15Pct","break20Pct",
    "dayPct","ret20Pct","aboveMa20Pct","turnoverB","price",
    "marketScore","marketBreadth","marketRet5","marketRet20",
    "marketDistMA20","marketForeign","candleClosePosition",
    "ma10AboveMa20Pct","isBox15","isBox10","isPrebreak","isSqueeze",
    "isGTop1","isGTop3")
MIN_TRAIN=180
def id_for(algorithm,plan,mode,cap):
    return f"{algorithm}__{plan}__{mode}__{'ALL' if cap is None else 'CAP200'}"
def candidate_universe(hist,universe,market_returns,risk,dates,original_g):
    """Use same-day past-only features, include all four qualified patterns,
    plus up to 3 original G stocks per day, irrespective of their setup.
    Must not use labels to decide candidate inclusion.
    """
    last_by_date={};counts=collections.Counter();selected_days=collections.defaultdict(set)
    date_set=set(dates)
    g_lookup={(day,x["sym"]):i+1 for day,rows in original_g.items()
        for i,x in enumerate(rows[:3])}
    for n,item in enumerate(universe,1):
        sy=to_symbol(item["code"],item["market"]);h=hist.get(sy)
        if h is None or h.empty:continue
        q=asof_features(h,market_returns)
        if q.empty:continue
        flags=classify_frame(q)
        q=q[q.date.astype(str).isin(date_set)].copy()
        if q.empty:continue
        for day,z in q.iterrows():
            d=str(z["date"]);mr=risk.get(d)
            if mr is None:raise RuntimeError("Missing official risk day "+d)
            source=[bool(flags[f].loc[day]) for f in FAMILIES]
            grank=g_lookup.get((d,sy))
            if not any(source) and grank is None:continue
            qclose=finite(z["close"]);ma10=finite(z["ma10"]);ma20=finite(z["ma20"])
            vol=finite(z["volume"]);high=finite(z["high"]);low=finite(z["low"])
            if not all(v is not None for v in (qclose,ma10,ma20,vol,high,low)):continue
            if qclose<=0 or vol<=0 or ma20<=0 or low<=0:continue
            info={"rs20":z["rs20"],"rvol":z["rvol"],
                "prev5RangePct":z["prev5RangePct"],
                "prev10RangePct":z["prev10RangePct"],
                "prev15RangePct":z["prev15RangePct"],
                "prev20RangePct":z["prev20RangePct"],
                "break10Pct":z["break10Pct"],
                "break15Pct":z["break15Pct"],
                "break20Pct":z["break20Pct"],
                "dayPct":z["dayPct"],"ret20Pct":z["ret20Pct"],
                "aboveMa20Pct":z["aboveMa20Pct"],
                "turnoverB":z["turnoverB"],"price":qclose,
                "marketScore":mr.get("score"),"marketBreadth":mr.get("breadth"),
                "marketRet5":mr.get("ret5"),"marketRet20":mr.get("ret20"),
                "marketDistMA20":mr.get("distMA20"),"marketForeign":mr.get("foreign"),
                "candleClosePosition":100*(qclose-low)/max(.01,high-low),
                "ma10AboveMa20Pct":100*(ma10/ma20-1),
                "isBox15":float(source[0]),"isBox10":float(source[1]),
                "isPrebreak":float(source[2]),"isSqueeze":float(source[3]),
                "isGTop1":float(grank==1),"isGTop3":float(grank is not None)}
            a=np.asarray([finite(info[k]) for k in FEATURES],dtype=object)
            if any(v is None or not math.isfinite(float(v)) for v in a):continue
            x=[float(v) for v in a]
            row={"date":d,"sym":sy,"code":str(item["code"]),"name":str(item["name"]),
                 "close":float(qclose),"features":x,
                 "sources":[FAMILIES[i] for i,b in enumerate(source) if b]+(["G Top"+str(grank)] if grank else [])}
            last_by_date.setdefault(d,[]).append(row)
            for name in row["sources"]:counts[name]+=1;selected_days[name].add(d)
        if n%500==0:print("V3_CANDIDATE_SCAN",n,"/",len(universe),
            "stockDays",sum(map(len,last_by_date.values())),flush=True)
    for d in last_by_date:last_by_date[d].sort(key=lambda x:x["code"])
    return last_by_date,{"sourceStockDays":dict(counts),"sourceSignalDays":{k:len(v) for k,v in selected_days.items()},
                         "uniqueCandidates":sum(map(len,last_by_date.values())),
                         "candidateDays":len(last_by_date)}
def historical_label(dates,day_pos,stock,bars,plan):
    """The ONLY function allowed to inspect post-signal stock price bars.
    Labels mature at actual exit date, never at signal date.
    Exactly V1 close signal / next open / tp sl time-expiry mechanics,
    conservative stop-first and 0.1% target cushion.
    """
    i=day_pos.get(stock["date"]);sy=stock["sym"]
    if i is None or i+1>=len(dates):return None
    buyday=dates[i+1];start=bars.get(sy,{}).get(buyday)
    if start is None:return None
    op_raw,_,_,_,op_adj,_,_,_,_=start
    prior_raw=stock["close"]
    if not op_raw or not op_adj or op_adj<=0 or op_raw>prior_raw*(1+PRICE_CHASE_LIMIT):
        return None
    if op_raw>=prior_raw*1.095 and start[1]<=start[2]+1e-8:return None
    tp=op_adj*(1+plan["tp"]);sl=op_adj*(1-plan["sl"])
    for j in range(i+1,min(len(dates),i+plan["hold"]+2)):
        d=dates[j];v=bars.get(sy,{}).get(d)
        if v is None:return None
        _,_,_,_,o,h,l,c,_=v
        if j>i+plan["hold"]:return {"pnl":(o*SELL_FACTOR)/(op_adj*BUY_FACTOR)-1,
             "maturity":d,"exit":"time_next_open"}
        if o<=sl:return {"pnl":(o*SELL_FACTOR)/(op_adj*BUY_FACTOR)-1,
             "maturity":d,"exit":"gap_stop"}
        if o>=tp:return {"pnl":(o*SELL_FACTOR)/(op_adj*BUY_FACTOR)-1,
             "maturity":d,"exit":"gap_target"}
        if l<=sl:return {"pnl":(sl*SELL_FACTOR)/(op_adj*BUY_FACTOR)-1,
             "maturity":d,"exit":"intraday_stop"}
        if h>=tp*(1+TP_FILL_BUFFER):return {"pnl":(tp*SELL_FACTOR)/(op_adj*BUY_FACTOR)-1,
             "maturity":d,"exit":"target_limit"}
    return None
def with_mature_labels(pooled,bars,dates):
    pos={d:i for i,d in enumerate(dates)}
    stats={k:collections.Counter() for k in PLANS}
    labeled={k:[] for k in PLANS}
    for d,stocks in pooled.items():
        for stock in stocks:
            for k,plan in PLANS.items():
                z=historical_label(dates,pos,stock,bars,plan)
                if z is None:stats[k]["unfilledOrUnmatured"]+=1;continue
                if not math.isfinite(z["pnl"]):raise RuntimeError("Bad future label")
                row={"date":d,"symbol":stock["sym"],"code":stock["code"],
                     "features":stock["features"],"pnl":float(z["pnl"]),
                     "maturity":z["maturity"],"exitReason":z["exit"]}
                labeled[k].append(row);stats[k]["labeled"]+=1
                stats[k]["winners"]+=z["pnl"]>0
    return labeled,{k:dict(v) for k,v in stats.items()}
def assert_training_past(training,cutoff):
    if any(z["maturity"]>=cutoff or z["date"]>=cutoff for z in training):
        raise AssertionError("FUTURE LABEL LEAK INTO TRAINING "+cutoff)
def trainer(kind,X,y):
    if kind=="Ridge":
        scaler=StandardScaler()
        norm=scaler.fit_transform(X)
        model=Ridge(alpha=100.)
        model.fit(norm,y)
        return lambda inp: model.predict(scaler.transform(inp))
    if kind=="HGB":
        model=HistGradientBoostingRegressor(learning_rate=.045,max_iter=85,
             max_leaf_nodes=9,min_samples_leaf=45,l2_regularization=30,
             random_state=17,early_stopping=False)
        model.fit(X,y)
        return lambda inp:model.predict(inp)
    raise ValueError(kind)
def rank_monthly_walkforward(dates,pool,labeled,kind,plan,positive_only):
    """Retrain on the FIRST session of each new month. The latest label
    matured strictly before that date; fit with no knowledge of later closes.
    Each daily Top1 is chosen using that day's completed close only.
    """
    available=[d for d in dates if d>=EVAL_START]
    month_rows=collections.defaultdict(list)
    for d in available:month_rows[d[:7]].append(d)
    byday={};audit=[];traindata=labeled[plan]
    for month,mdays in sorted(month_rows.items()):
        cutoff=mdays[0]
        training=[x for x in traindata if x["maturity"]<cutoff and x["date"]<cutoff]
        assert_training_past(training,cutoff)
        if len(training)<MIN_TRAIN or sum(x["pnl"]>0 for x in training)<25 or sum(x["pnl"]<=0 for x in training)<25:
            raise RuntimeError("Insufficient mature diverse examples "+month+" "+str(len(training)))
        X=np.asarray([z["features"] for z in training],float)
        y=np.asarray([max(-.35,min(.35,z["pnl"]))*100 for z in training],float)
        predict=trainer(kind,X,y)
        month_count=0;skipped=0
        for d in mdays:
            today=pool.get(d) or []
            if not today:byday[d]=[];continue
            feats=np.asarray([z["features"] for z in today],float)
            predictions=predict(feats)
            if not np.isfinite(predictions).all():raise RuntimeError("Nonfinite ranking "+d)
            ranking=sorted(zip(today,predictions),
                key=lambda pair:(-float(pair[1]),pair[0]["code"]))
            stock,value=ranking[0]
            if positive_only and value<=0:
                byday[d]=[];skipped+=1;continue
            byday[d]=[{k:stock[k] for k in ("sym","code","name","close","sources")}|
                {"predictedNetPct":round(float(value),4),"candidatesRanked":len(today)}]
            month_count+=1
        audit.append({"month":month,"fitAsOfFirstTradeDate":cutoff,
            "trainingSamples":len(training),
            "latestMaturedLabel":max(z["maturity"] for z in training),
            "latestTrainingSignal":max(z["date"] for z in training),
            "rankedSignalDays":month_count,"withheldOnPredictedNonpositive":skipped})
        print("V3_MONTHLY_RETRAIN",kind,plan,"positive" if positive_only else "always",
          month,"training",len(training),"ranked",month_count,flush=True)
    return byday,audit
def portfolio_metric(dates,picks,bars,risk,plan,cap):
    p=PLANS[plan]
    a,_,_=study_one(dates,picks,bars,risk,GATE,p["tp"],p["sl"],p["hold"],cap)
    return a
def model_preference(rows):
    """Choose ONCE using validation2025 only; never optimize 2026.
    Require >=20 closed trades, nonnegative 2025 pnl, >=-30% MDD.
    Reject all if no robust candidate. Score rewards net minus DD and sparsity.
    """
    accepted=[]
    for row in rows:
        z=row["periods"]["validation2025"]
        if z["closedTrades"]<20 or z["netReturnPct"]<=0 or z["maxDDPct"]< -30:
            continue
        score=z["netReturnPct"]+.6*z["maxDDPct"]-20/(math.sqrt(z["closedTrades"]))
        accepted.append((score,row))
    accepted.sort(key=lambda p:(-p[0],p[1]["id"]))
    if not accepted:return {"status":"no_model_passed_validation_gate",
      "criteria":"2025 closed >=20, portfolio return >0%, daily MDD >-30%",
      "eligibleModels":0}
    best,rec=accepted[0]
    return {"status":"selected_by_2025_only","id":rec["id"],
      "validationScore":round(best,4),"eligibleModels":len(accepted),
      "validation2025":rec["periods"]["validation2025"],
      "audit2026":rec["periods"]["audit2026"],
      "authorWindow2026":rec["periods"]["authorWindow2026"]}
def split_dates(dates):
    return {k:[d for d in dates if lo<=d<=hi] for k,(lo,hi) in FOLDS_TEST.items()}
def main():
    began=time.time();OUT.mkdir(parents=True,exist_ok=True)
    universe=[x for x in load_universe() if finite(x.get("capitalB")) is not None and float(x["capitalB"])>0]
    first=datetime.fromisoformat(START)-timedelta(days=430)
    last=datetime.fromisoformat(END)+timedelta(days=35)
    hist,stock_errors=update_many([(x["code"],x["market"]) for x in universe],first,last)
    _,index,indexerr=update_symbol(BENCHMARK,first,last)
    if indexerr or index is None or index.empty:raise RuntimeError("Index unavailable "+str(indexerr))
    index=index.sort_values("date").drop_duplicates("date").reset_index(drop=True)
    dates=[d for d in index.date.astype(str) if START<=d<=END]
    if len(dates)!=728:raise RuntimeError("Missing original 728-market-day TWII history")
    official,_=get_risk(index,dates)
    archival=json.loads((DATA_DIR/"research"/"g_regime_3y"/"market_risk_daily.json").read_text(encoding="utf-8"))
    if [z["date"] for z in archival]!=dates:raise RuntimeError("Risk dates misaligned")
    risk={z["date"]:z for z in archival}
    if any(official[d]!=risk[d]["score"] for d in dates):raise RuntimeError("Historical TWII risk changed")
    idx_close=pd.to_numeric(index.close,errors="coerce")
    idx_ret20=(idx_close/idx_close.shift(20)-1)*100
    market_returns=dict(zip(index.date.astype(str),idx_ret20))
    original_g,_,gmeta=make_g(dates,index,universe,hist)
    pool,stat=candidate_universe(hist,universe,market_returns,risk,dates,original_g)
    all_sy={r["sym"] for rows in pool.values() for r in rows}
    bars,barerrors=price_bars(hist,all_sy)
    if len(bars)!=len(all_sy):raise RuntimeError("Daily OHLC missing for selected stocks")
    labels,label_stat=with_mature_labels(pool,bars,dates)
    for name,series in labels.items():
        if len(series)<MIN_TRAIN*4:raise RuntimeError("Insufficient training labels "+name)
    print("V3_DATA_READY",json.dumps({"riskDays":len(risk),"pool":stat,
         "labeled":label_stat,"priceSeries":len(bars),"errors":len(stock_errors)},
         ensure_ascii=False),flush=True)
    parts=split_dates(dates);daily={}
    candidates=[];audits={}
    for kind in ALGORITHMS:
        for pl in PLANS:
            for mode in MODES:
                preds,month_audit=rank_monthly_walkforward(dates,pool,labels,kind,pl,mode=="POSITIVE")
                group=f"{kind}__{pl}__{mode}"
                daily[group]=preds;audits[group]=month_audit
                for cap in CAPS:
                    id=id_for(kind,pl,mode,cap)
                    performance={k:portfolio_metric(ds,preds,bars,risk,pl,cap)
                        for k,ds in parts.items()}
                    candidates.append({"id":id,"model":kind,"plan":pl,"filter":mode,
                        "maxPerTradeTWD":cap,"periods":performance})
        print("V3_FINISHED_ALGORITHM",kind,flush=True)
    selected=model_preference(candidates)
    # Unmodified original G benchmark, strictly identical to published V1/V2.
    g_picks={d:r[:1] for d,r in original_g.items()}
    base={k:portfolio_metric(ds,g_picks,bars,risk,"FAST",200_000.)
        for k,ds in parts.items()}
    archive=json.loads((DATA_DIR/"research"/"g_compound_v2_3y"/"summary.json").read_text(encoding="utf-8"))
    baseline=next(x for x in archive["baselineSetupModels"] if x["params"]["selector"]=="G")
    for p,k in (("validation2025","validation"),("audit2026","audit2026"),("authorWindow2026","authorWindow2026")):
        a=base[p];b=baseline["periods"][k]
        if abs(a["capitalEnd"]-b["capitalEnd"])>.02 or a["closedTrades"]!=b["closedTrades"]:
            raise RuntimeError("Original G parity failure on "+p+":"+str((a,b)))
    # Same V2 static Top1 baseline, but different picker implementation
    # deliberately not scored as successful V3 ML.
    qref=json.loads((DATA_DIR/"research"/"g_compound_v2_3y"/"summary.json").read_text(encoding="utf-8"))
    v2_static=[r for r in qref["baselineSetupModels"] if r["params"]["selector"]!="G"]
    detailed_keys=[x["id"] for x in candidates if (x["model"]=="Ridge" and x["plan"]=="FAST" and x["filter"]=="ALWAYS")]
    if selected.get("id") and selected["id"] not in detailed_keys:detailed_keys.append(selected["id"])
    if not detailed_keys:detailed_keys=[candidates[0]["id"]]
    trades={};equity={};day_top1={}
    for id in detailed_keys:
        z=next(x for x in candidates if x["id"]==id)
        group=f'{z["model"]}__{z["plan"]}__{z["filter"]}'
        pp=PLANS[z["plan"]];cap=z["maxPerTradeTWD"];picks=daily[group]
        trades[id]={};equity[id]={}
        for fold in parts:
            actual,curve,deals=study_one(parts[fold],picks,bars,risk,GATE,
                pp["tp"],pp["sl"],pp["hold"],cap,logs=True)
            if abs(actual["capitalEnd"]-z["periods"][fold]["capitalEnd"])>.02:
                raise RuntimeError("Cash accounting inconsistent for "+id+" "+fold)
            trades[id][fold]={"metrics":actual,"closedTickets":deals}
            equity[id][fold]=curve
        if z["plan"]=="FAST" and z["filter"]=="ALWAYS":
            day_top1[id]={d:picks.get(d,[]) for d in dates if d>=EVAL_START}
    detail={"trades.json":{"version":"G_COMPOUND_WALK_FORWARD_MONTHLY_V3",
           "models":trades},
       "equity.json":{"version":"G_COMPOUND_WALK_FORWARD_MONTHLY_V3","models":equity},
       "picks.json":{"version":"G_COMPOUND_WALK_FORWARD_MONTHLY_V3",
           "rankedDailyTop1":day_top1,"selectedModelTop1":(
               daily[f'{next(x for x in candidates if x["id"]==selected["id"])["model"]}__{next(x for x in candidates if x["id"]==selected["id"])["plan"]}__{next(x for x in candidates if x["id"]==selected["id"])["filter"]}']
               if selected.get("id") else {})}}
    hindsight=sorted(candidates,key=lambda x:x["periods"]["audit2026"]["netReturnPct"],reverse=True)
    author_target=3_658_915.39
    summary={"version":"G_COMPOUND_MONTHLY_WALKFORWARD_V3",
        "createdAt":datetime.now(ZoneInfo("Asia/Taipei")).isoformat(),
        "dates":{"start":START,"end":END,"testStart":EVAL_START},
        "marketDays":len(dates),"officialRiskDays":len(risk),
        "universeNow":len(universe),"stockDataErrors":len(stock_errors),
        "GUnmodifiedParityVerified":True,"initialCapitalTWD":PRINCIPAL,
        "featureNames":FEATURES,"candidatePoolStats":stat,"labelStats":label_stat,
        "trainRule":{"initial":"2023-10-09 through end-2024, matured labels only",
          "monthly":"At first exchange day each month, train only examples whose actual simulated trade EXIT occurred before cutoff",
          "trainingFrom":"2023-10-09","monthlyFrom":EVAL_START,
          "selection":"Choose model/cap/positive abstention using 2025 annual portfolio only; 2026 never used for selection",
          "2026":"Monthly models still recursively update using fully matured 2026 trade outcomes before each month's first day; signals and executions remain causal",
          "pricing":"Same G Compound V1 execution: D close, D+1 open <= previous close*1.03; real cash, 0.1425% brokerage per side, 0.1% slippage each side, 0.3% tax; intraday TP stop-first",
          "rankingObjective":"Ridge or gradient-boosted regression of net hypothetical trade return, ranks Top1 by expected net payoff; positive mode abstains if predicted payoff <=0%",
          "labels":"Historical forward TP/SL/expiry through actual exit date; unknown or untradeable entry discarded (not a zero or fake win)",
          "marketGate":"Official day D score>=60; market risk feature includes scored TWSE breadth and dated foreign flow"},
        "algorithms":ALGORITHMS,"exitTemplates":PLANS,"modes":MODES,"sizing":{"capsTWD":[200000,None]},
        "monthlyModelTrainingAudit":audits,
        "baselineOriginalG":{k:{kk:v[kk] for kk in ("capitalEnd","netReturnPct","maxDDPct","closedTrades","winPct","openAtEnd")}
                           for k,v in base.items()},
        "baselineStaticV2":[{"id":z["id"],"selector":z["params"]["selector"],
            "validation2025":z["periods"]["validation"],"audit2026":z["periods"]["audit2026"]}
            for z in v2_static],
        "selectedBy2025Only":selected,"allCandidateModels":candidates,"variantCount":len(candidates),
        "posthocBest2026NotDeployable":[{"id":x["id"],"validation2025":x["periods"]["validation2025"],
             "audit2026":x["periods"]["audit2026"]} for x in hindsight[:4]],
        "authorComparison":{"claimedClosed":52,"claimedWins":51,"claimedRealizedTWD":3_158_915.39,
             "claimedImpliedEquityNoExternalFlowsTWD":author_target,
             "anyModelMatchingImpliedEquity":any(x["periods"]["authorWindow2026"]["capitalEnd"]>=author_target for x in candidates)},
        "limitations":["Historically selected stock pool contains only CURRENT universe and capital, excludes historical delistings (survivorship bias).",
          "2026 was observed in preceding G Compound v1-v2 research; not pristine untouched holdout; repeated research introduces data snooping.",
          "Monthly retraining is causally valid but model family/candidate setup were developed after observing 2026 failure, so independent post-2026 forward paper trading is required.",
          "Daily OHLC cannot resolve intraday queue position, exact TP/SL sequence, trading halts or limit-up and limit-down; conservative stop-first approximation.",
          "Training examples require a historically executable next open and matured exit, which can create selection effects.",
          "A trained model cannot guarantee choosing tomorrow's optimal stock; model labels are hypothetical net trades, not certainty.",
          "Original author did not share ranking, cash settlement, target or stop; no claim of cloning the 51-win model.",
          "2025 model choice across 16 variants has multiple-testing risk; if none passes predefined criteria, no validated model is endorsed.",
          "Monthly model fitted with all historical matured candidates, not just what a real investor actually traded, using public historical OHLC archive.",
          "Cash simulations do not fully reproduce board lot/odd lot, settlement T+2 funding, broker order rejection or intraday ticks.",
          "2023-24 are used for initial model learning, not shown as a walkforward live portfolio."]}
    (OUT/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    for name,payload in detail.items():
        (OUT/name).write_text(json.dumps(payload,ensure_ascii=False,separators=(",",":")),encoding="utf-8")
    print("G_COMPOUND_V3_COMPLETE",json.dumps({"models":len(candidates),"marketDays":len(dates),
         "riskDays":len(risk),"stockErrors":len(stock_errors),
         "data":stat,"labels":label_stat,"selected":selected,
         "baselineG2026":base["audit2026"]["netReturnPct"],
         "best2026NotSelected":hindsight[0]["id"],
         "best2026Pct":hindsight[0]["periods"]["audit2026"]["netReturnPct"],
         "elapsed":round(time.time()-began)},ensure_ascii=False),flush=True)
if __name__=="__main__":main()
