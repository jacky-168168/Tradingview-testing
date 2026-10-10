"""Second-round, PREDECLARED G Pro candidate-pool and walk-forward comparison.
As-of close D only. Original G remains unchanged and is reconstructed independently.
2026 is permanently sealed for model selection, used only as a holdout report.
"""
from __future__ import annotations
import collections,json,math,time
from datetime import datetime,timedelta
from zoneinfo import ZoneInfo
import numpy as np
import pandas as pd
from config import DATA_DIR,BENCHMARK
from pipeline import load_universe
from yahoo_cache import update_many,update_symbol,to_symbol
from g_persistence import persistence_features
from g_pro_rules import build_daily_indicators,pro_pass
from research_g_regime_3y import START,END,calc_g,get_risk,make_g,stock_ret,finite
from research_g_pro_3y import compact_stats,simulate_cash,SPLITS,THRESHOLDS
OUT=DATA_DIR/"research"/"g_pro_round2"
HORIZONS=(5,10,20)
PRICES_BEGIN_DAYS=430
TOP_CANDIDATES=20
# All candidate families and thresholds fixed in source BEFORE the holdout is inspected.
FAMILIES={
    "G Pro v1":{"source":"top3","ret20":75,"slope":80,"turnover":75,"past":2,"rvol":1.3,"ema60":True,"overheat":1.15},
    "G Pro balanced":{"source":"top20","ret20":70,"slope":75,"turnover":70,"past":1,"rvol":1.0,"ema60":True,"overheat":1.25},
    "G Pro trend":{"source":"top20","ret20":70,"slope":75,"turnover":65,"past":0,"rvol":1.0,"ema60":True,"overheat":1.25},
    "G Pro persistent":{"source":"top20","ret20":65,"slope":70,"turnover":65,"past":2,"rvol":0.8,"ema60":True,"overheat":1.30},
    "G Pro quality":{"source":"top20","ret20":80,"slope":80,"turnover":75,"past":1,"rvol":1.0,"ema60":True,"overheat":1.20},
}
def make_ranked_pool(dates,index,universe,hist):
    """Same exact G percentiles/persistence as original selector, but retain top20
    for independent Pro reranking; never use future or same-day persistence.
    """
    cal={d:(d[:4],i) for yr in sorted({d[:4] for d in index.date.astype(str)})
         for i,d in enumerate(x for x in index.date.astype(str) if x[:4]==yr)}
    frames=[]
    for s in universe:
        sy=to_symbol(s["code"],s["market"]);h=hist.get(sy)
        if h is None or h.empty:continue
        try:
            q=calc_g(h,s,cal)
            if q is None:continue
            frames.append(q[["date","code","name","market","sym","close","ret20","ma20Slope","atrPct","range20Pct","turnoverB","breakoutPct","cap","break3","break18"]])
        except Exception as e:print("V2 G feature skipped",sy,str(e)[:120],flush=True)
    if not frames:raise RuntimeError("No historical G cross-sectional data")
    panel=pd.concat(frames,ignore_index=True)
    panel=panel[(panel.date>=dates[0])&(panel.date<=dates[-1])].copy()
    panel=panel.replace([np.inf,-np.inf],np.nan).dropna(subset=["close","ret20","ma20Slope","atrPct","range20Pct","turnoverB","breakoutPct"])
    panel=panel[(panel.close>0)&(panel.turnoverB>0)]
    for f,p in (("ret20","ret20P"),("ma20Slope","slopeP"),("atrPct","atrP"),("range20Pct","range20P"),("turnoverB","turnoverP")):
        panel[p]=panel.groupby("date")[f].rank(method="average",pct=True)*100
    ok=(panel.close>=10)&(panel.cap>0)&(panel.ret20P>=60)&(panel.slopeP>=70)&(panel.atrP>=55)&(panel.range20P>=65)&(panel.turnoverP>=65)&(panel.breakoutPct>=-25)&panel.break3&panel.break18
    panel=panel[ok].copy()
    panel["base"]=(30*panel.ret20P+25*panel.slopeP+10*panel.atrP+15*panel.range20P+15*panel.turnoverP+5*(100+panel.breakoutPct/18*100).clip(lower=0,upper=100))/100
    panel.sort_values(["date","base","code"],ascending=[True,False,True],inplace=True)
    groups={d:g.to_dict("records") for d,g in panel.groupby("date",sort=False)}
    pool={};window=collections.deque(maxlen=10);lastyear=None
    for d in dates:
        if d[:4]!=lastyear:window.clear();lastyear=d[:4]
        rows=groups.get(d,[])
        pocket={x["code"]:{"rank":i+1,"score":round(float(x["base"]),4)} for i,x in enumerate(rows[:20])}
        ranked=[]
        for x in rows:
            b=float(x["base"]);p=persistence_features(x["code"],list(window),round(b,4))
            ranked.append({**x,"base":b,"score":round(round(b,4)+p["bonus"],4),
                           "bonus":p["bonus"],"previousTop20":p["past10Top20"]})
        ranked.sort(key=lambda x:(-x["score"],-round(x["base"],4),x["code"]))
        pool[d]=ranked[:TOP_CANDIDATES];window.append(pocket)
    return pool
def passes(stock,x,rule):
    if not x:return False
    c=finite(stock.get("close"));e20=finite(x.get("ema20"));e60=finite(x.get("ema60"));rv=finite(x.get("rvol"))
    if None in (c,e20,e60,rv) or e20<=0:return False
    if stock["ret20P"]<rule["ret20"] or stock["slopeP"]<rule["slope"] or stock["turnoverP"]<rule["turnover"]:return False
    if stock["previousTop20"]<rule["past"] or rv<rule["rvol"]:return False
    if not(c>e20 and (not rule["ema60"] or e20>e60)):return False
    return c/e20<=rule["overheat"]
def build_variants(dates,base3,pool20,ind):
    variants={"G":base3}
    for name,rule in FAMILIES.items():
        out={}
        for d in dates:
            source=base3[d] if rule["source"]=="top3" else pool20[d]
            chosen=[s for s in source if passes(s,ind.get(s["sym"],{}).get(d),rule)]
            out[d]=chosen[:3]
        variants[name]=out
    return variants
def compute_samples(dates,picks,prices,risk,h,threshold):
    rows=[];eligible=0
    for i,d in enumerate(dates):
        if i+1>=len(dates) or i+h>=len(dates) or risk.get(d,0)<threshold:continue
        stocks=picks.get(d) or []
        if not stocks:continue
        eligible+=1
        buy=dates[i+1];sell=dates[i+h]
        gross=[stock_ret(prices,s,buy,sell) for s in stocks]
        if any(v is None for v in gross):continue
        # Match frozen original G's end-to-end cost convention exactly.
        net=(1+float(np.mean(gross)))*(1-0.00585)-1
        rows.append({"date":d,"buy":buy,"sell":sell,"codes":[s["code"] for s in stocks],"net":round(net,8)})
    return eligible,rows
def fold_stats(rows,key):
    lo,hi=SPLITS[key]
    rs=[r["net"] for r in rows if lo<=r["date"]<=hi and r["sell"]<=hi]
    return compact_stats(rs)
def evaluate(dates,variants,prices,risk):
    grid=[];audits=[];curves={}
    for h in HORIZONS:
        for th in THRESHOLDS:
            for name,picks in variants.items():
                count,samples=compute_samples(dates,picks,prices,risk,h,th)
                cash,curve,deals=simulate_cash(dates,picks,prices,risk,th,h)
                byperiod={}
                for key,(lo,hi) in SPLITS.items():
                    within=[d for d in dates if lo<=d<=hi]
                    cs,ec,dc=simulate_cash(within,picks,prices,risk,th,h)
                    byperiod[key]={"signal":fold_stats(samples,key),"portfolio":cs}
                row={"name":name,"threshold":th,"horizon":h,"eligibleSignalDays":count,
                     "executedSignalDays":len(samples),"signal":compact_stats([r["net"] for r in samples]),
                     "portfolio":cash,"byPeriod":byperiod}
                grid.append(row)
                if h==20:
                    audits.append({"name":name,"threshold":th,"horizon":h,"signals":samples,"closedStockTrades":deals})
                    if th in (60,70):curves[name+"_"+str(th)]={"dates":[z["date"] for z in curve],
                      "equity":[z["equity"] for z in curve]}
        print("G Pro round 2 completed horizon",h,flush=True)
    return grid,audits,curves
def select_prefrozen(grid):
    # Lock model choice to 2023-24 training and 2025 validation only.
    # Do not reward tiny historical 'jackpots'; demand broad sample coverage.
    candidates=[]
    for r in grid:
        if r["name"]=="G" or r["horizon"]!=20:continue
        tr=r["byPeriod"]["train"]["signal"];va=r["byPeriod"]["validation"]["signal"]
        if tr["n"]<35 or va["n"]<25 or tr["meanNetPct"] is None or va["meanNetPct"] is None:continue
        if tr["meanNetPct"]<=0 or va["meanNetPct"]<=0:continue
        trdd=r["byPeriod"]["train"]["portfolio"]["dailyMaxDrawdownPct"]
        vadd=r["byPeriod"]["validation"]["portfolio"]["dailyMaxDrawdownPct"]
        # Objective uses only chronological train/validation folds.
        objective=.4*tr["meanNetPct"]+.6*va["meanNetPct"]-.03*abs(trdd)-.04*abs(vadd)-2/math.sqrt(min(tr["n"],va["n"]))
        candidates.append((objective,r))
    candidates.sort(key=lambda x:(-x[0],x[1]["name"],x[1]["threshold"]))
    if not candidates:return {"status":"no_valid_candidate","rule":"Train>=35/validation>=25 20D signals, positive means both, choose highest pre-holdout objective"}
    score,row=candidates[0]
    return {"status":"selected_train_validation_only","name":row["name"],"threshold":row["threshold"],
            "horizon":20,"objective":round(score,4),"train":row["byPeriod"]["train"],
            "validation":row["byPeriod"]["validation"],"holdout":row["byPeriod"]["holdout"],
            "candidateCount":len(candidates)}
def main():
    started=time.time();OUT.mkdir(parents=True,exist_ok=True)
    universe=[x for x in load_universe() if finite(x.get("capitalB")) and float(x["capitalB"])>0]
    pfrom=datetime.fromisoformat(START)-timedelta(days=PRICES_BEGIN_DAYS)
    pto=datetime.fromisoformat(END)+timedelta(days=35)
    hist,errors=update_many([(x["code"],x["market"]) for x in universe],pfrom,pto)
    _,index,err=update_symbol(BENCHMARK,pfrom,pto)
    if err or index is None or index.empty:raise RuntimeError("TWII benchmark missing: "+str(err))
    index=index.sort_values("date").drop_duplicates("date").reset_index(drop=True)
    dates=[d for d in index.date.astype(str) if START<=d<=END]
    if len(dates)!=728:raise RuntimeError("Expected exactly 728 dated index sessions, found "+str(len(dates)))
    risk,_=get_risk(index,dates)
    g,prices,gAudit=make_g(dates,index,universe,hist)
    top20=make_ranked_pool(dates,index,universe,hist)
    drift=[(d,[x["code"] for x in g[d]],[x["code"] for x in top20[d][:3]]) for d in dates if [x["code"] for x in g[d]]!=[x["code"] for x in top20[d][:3]]]
    if drift:raise RuntimeError("G parity failed: "+str(drift[:3]))
    extras=build_daily_indicators(hist,{x["sym"] for daily in top20.values() for x in daily})
    variants=build_variants(dates,g,top20,extras)
    # The original published G Pro top3 must also match the rewritten V1 gate.
    v1drift=[d for d in dates if [x["code"] for x in variants["G Pro v1"][d]]!=
             [x["code"] for x in g[d] if pro_pass(x,extras.get(x["sym"],{}).get(d))[0]]]
    if v1drift:raise RuntimeError("G Pro V1 parity drift: "+str(v1drift[:3]))
    counts={name:{"signalDays":sum(bool(v) for v in picks.values()),"stockSignals":sum(len(v) for v in picks.values())}
            for name,picks in variants.items()}
    grid,audits,curves=evaluate(dates,variants,prices,risk)
    winner=select_prefrozen(grid)
    # Validate the previously published untouched original G baseline at 20D/60.
    baseline=next(x for x in grid if x["name"]=="G" and x["horizon"]==20 and x["threshold"]==60)
    if baseline["executedSignalDays"]!=341 or abs(baseline["signal"]["meanNetPct"]-3.103)>0.003:
        raise RuntimeError("Historical G baseline parity mismatch; refuse misleading comparison: "+str(baseline["signal"]))
    out={"version":"G_PRO_ROUND2_LOCKED_CANDIDATE_POOL_V1",
         "createdAt":datetime.now(ZoneInfo("Asia/Taipei")).isoformat(),
         "period":{"start":START,"end":END},"riskScoredDays":len(risk),
         "marketDays":len(dates),"universeNow":len(universe),"stockDataErrors":len(errors),
         "GParityVerified":True,"firstGProParityVerified":True,
         "sampleSizes":counts,"rules":FAMILIES,"primaryHorizon":20,
         "chronologicalFolds":SPLITS,"lockedSelection":winner,"grid":grid,
         "limitations":["Current company universe and current paid-in-capital cause survivorship/capital-history bias.",
                        "Historical Yahoo adjusted prices, dividends/corporate-actions revision risk.",
                        "TX night futures 0 verified sessions and not used.",
                        "Institution net historical series unavailable; no institution accumulation claimed.",
                        "Use only D-close features, buy D+1 open. 2026 never used to select model/threshold.",
                        "Fully funded, one basket at a time, no leverage and no overlapping cash; fractional units.",
                        "Daily equity marked at adjusted close, stale observations carried and counted.",
                        "Portfolio excludes bid-ask spread, impact, limit-up/down inability, stamp tax changes.",
                        "Comparing five predeclared model families still incurs multiple-testing risk.",
                        "2026 holdout already publicly observed in earlier G investigations; not pristine blind holdout."]}
    (OUT/"summary.json").write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding="utf-8")
    (OUT/"trades.json").write_text(json.dumps({"period":out["period"],"models":audits},ensure_ascii=False),encoding="utf-8")
    (OUT/"equity.json").write_text(json.dumps({"period":out["period"],"models":curves},ensure_ascii=False),encoding="utf-8")
    print("G_PRO_ROUND2_DONE",json.dumps({"riskDays":len(risk),"originalG":counts["G"],"candidateCounts":counts,
          "selected":winner,"elapsedSec":round(time.time()-started)},ensure_ascii=False),flush=True)
if __name__=="__main__":main()
