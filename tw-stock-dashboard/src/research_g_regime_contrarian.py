"""Predeclared 2023-2026 market-score contrarian entry & profit taking study.
Official TWII score and BOTTOM/TOP states at completed close D; orders execute
NEXT session open only. No retroactive intraday execution or future lookahead.
Cash-constrained with daily marked equity and fee/tax on every buy/sell.
"""
from __future__ import annotations
import collections,json,math,time
from datetime import datetime,timedelta
from zoneinfo import ZoneInfo
import numpy as np
from config import DATA_DIR,BENCHMARK
from pipeline import load_universe
from yahoo_cache import update_many,update_symbol
from g_pro_rules import build_daily_indicators
from research_g_regime_3y import START,END,get_risk,make_g,finite
from research_g_pro_round2 import make_ranked_pool,build_variants
from research_g_pro_3y import SPLITS,BUY_FEE,SELL_FEE,compact_stats,daily_bar
OUT=DATA_DIR/"research"/"g_regime_contrarian_3y"
RESEARCH_SELECTORS=("G","G Pro balanced","G Pro trend")
ENTRY_RULES=("GTE60","GTE70","LTE30","LTE40","LTE50","BOTTOM","LTE40_BOTTOM","LOW40_REBOUND")
EXIT_RULES=("HOLD20","GTE70_ALL","GTE80_ALL","GTE70_HALF_80_ALL","TOP_ALL","GTE80_OR_TOP")
STARTING_CAPITAL=1000000.
MAX_HOLD_SESSIONS=20
def entry_ok(label,today,yesterday=None):
    score=int(today["score"]);mode=today.get("mode","NORMAL")
    if label=="GTE60":return score>=60
    if label=="GTE70":return score>=70
    if label=="LTE30":return score<=30
    if label=="LTE40":return score<=40
    if label=="LTE50":return score<=50
    if label=="BOTTOM":return mode=="BOTTOM"
    if label=="LTE40_BOTTOM":return score<=40 and mode=="BOTTOM"
    if label=="LOW40_REBOUND":
        return yesterday is not None and int(yesterday["score"])<=40 and score>40 and float(today.get("dayRet") or 0)>0
    raise ValueError("Unknown entry rule "+label)
def exit_orders(label,today,has_scaled):
    """At D close, return the fraction of initial units to liquidate at D+1 open.
    GTE70_HALF_80_ALL means sell half the REMAINING basket once at 70,
    all remainder after >=80; never rebuild sold exposure in same position.
    """
    sc=int(today["score"]);top=today.get("mode")=="TOP"
    if label=="HOLD20":return 0.
    if label=="GTE70_ALL":return 1. if sc>=70 else 0.
    if label=="GTE80_ALL":return 1. if sc>=80 else 0.
    if label=="GTE70_HALF_80_ALL":
        if sc>=80:return 1.
        if sc>=70 and not has_scaled:return .5
        return 0.
    if label=="TOP_ALL":return 1. if top else 0.
    if label=="GTE80_OR_TOP":return 1. if (sc>=80 or top) else 0.
    raise ValueError("Unknown exit rule "+label)
def run_cash(dates,picks,prices,market,entry_label,exit_label):
    """Capital is deployed to at most one Top3 basket; no leverage or overlap.
    Sell/scale orders from signal-day CLOSE execute next day OPEN. Market
    score high on entry day cannot retroactively sell the opening position.
    Mandatory exit after 20 sessions at an OPEN (consistent for all methods).
    """
    cash=STARTING_CAPITAL;positions=[];pending_entry=None;pending_exit=0.
    peak=cash;dd=0.;curve=[];deals=[];baskets=0
    stale_marks=0;missed_opens=0;missing_exit_opens=0;scaled_baskets=0;signal_days=0
    basket_meta=None
    for i,d in enumerate(dates):
        # Execute an exit order queued at yesterday's close.
        if positions and pending_exit>0:
            sellable=[daily_bar(prices,p["stock"],d,"adjOpen") for p in positions]
            if any(p is None or p<=0 for p in sellable):
                missing_exit_opens+=1
            else:
                fraction=min(pending_exit,1.)
                for pos,px in zip(positions,sellable):
                    amt=pos["units"]*fraction
                    cash+=amt*px*(1-SELL_FEE)
                    pos["units"]-=amt
                    pos["realized"]+=amt*px*(1-SELL_FEE)
                if fraction>=1.-1e-9:
                    final_cash=cash
                    deals.append({"signalDate":basket_meta["signalDate"],"entry":basket_meta["entry"],
                        "exit":d,"codes":basket_meta["codes"],"reason":basket_meta.get("reason",""),
                        "scaled":basket_meta["scaled"],"netPct":round(100*(final_cash/basket_meta["capital"]-1),4)})
                    positions=[];basket_meta=None
                else:
                    if not basket_meta["scaled"]:
                        basket_meta["scaled"]=True;scaled_baskets+=1
                pending_exit=0.
        # At most one entry order is queued at close D and filled at opening D+1.
        if pending_entry is not None and pending_entry["i"]==i:
            row=pending_entry;pending_entry=None
            if positions or cash<=0:missed_opens+=1
            else:
                open_px=[daily_bar(prices,s,d,"adjOpen") for s in row["stocks"]]
                if not open_px or any(p is None or p<=0 for p in open_px):missed_opens+=1
                else:
                    invested=cash;unit_budget=cash/len(row["stocks"])
                    positions=[{"stock":s,"units":unit_budget/(px*(1+BUY_FEE)),
                                "last":px,"realized":0.} for s,px in zip(row["stocks"],open_px)]
                    basket_meta={"signalDate":row["signalDate"],"entry":d,
                        "codes":[s["code"] for s in row["stocks"]],"capital":invested,
                        "scaled":False,"reason":""}
                    cash=0.;baskets+=1
        # Conservative daily adjusted-close valuation; report any stale marks.
        for pos in positions:
            close_px=daily_bar(prices,pos["stock"],d,"adjClose")
            if close_px is None or close_px<=0:stale_marks+=1
            else:pos["last"]=close_px
        equity=cash+sum(p["units"]*p["last"] for p in positions)
        peak=max(peak,equity);dd=min(dd,equity/peak-1)
        curve.append({"date":d,"equity":round(equity,2),"invested":bool(positions)})
        if i+1>=len(dates):continue
        m=market[d]
        if positions:
            # Forced 20-session exit is next open after 20 trading sessions
            # counting the purchase session as session 1.
            age=i-dates.index(basket_meta["entry"])+1
            if age>=MAX_HOLD_SESSIONS:
                pending_exit=1.;basket_meta["reason"]="MAX20";continue
            fraction=exit_orders(exit_label,m,basket_meta["scaled"])
            if fraction>0:
                pending_exit=fraction
                basket_meta["reason"]=exit_label
        elif pending_entry is None and cash>0:
            prev=market[dates[i-1]] if i>0 else None
            if entry_ok(entry_label,m,prev):
                chosen=picks.get(d) or []
                if chosen:
                    signal_days+=1
                    pending_entry={"i":i+1,"signalDate":d,"stocks":chosen}
    if positions:
        # Last session open positions valued but not fabricated as closed trades.
        unrealized=1
    else:unrealized=0
    final=curve[-1]["equity"]
    return {"startCapital":STARTING_CAPITAL,"finalEquity":final,"netReturnPct":round(100*(final/STARTING_CAPITAL-1),3),
        "dailyMaxDrawdownPct":round(100*dd,3),"entrySignalDays":signal_days,"openedBaskets":baskets,
        "closedBaskets":len(deals),"closedTradeWinPct":round(100*sum(z["netPct"]>0 for z in deals)/len(deals),2) if deals else None,
        "avgClosedBasketNetPct":round(sum(z["netPct"] for z in deals)/len(deals),3) if deals else None,
        "scaledBaskets":scaled_baskets,"unclosedBaskets":unrealized,
        "staleCloseMarks":stale_marks,"missedEntryOpens":missed_opens,
        "missingExitOpens":missing_exit_opens,
        "exposureDays":sum(z["invested"] for z in curve),
        "exposurePct":round(100*sum(z["invested"] for z in curve)/len(curve),2) if curve else 0},deals,curve
def evaluate(dates,variants,prices,market):
    grid=[];audit=[];curves={}
    for selector in RESEARCH_SELECTORS:
        picks=variants[selector]
        for entry in ENTRY_RULES:
            for ex in EXIT_RULES:
                overall,deals,curve=run_cash(dates,picks,prices,market,entry,ex)
                byfold={}
                for key,(lo,hi) in SPLITS.items():
                    fold_dates=[d for d in dates if lo<=d<=hi]
                    fold,deals_f,curve_f=run_cash(fold_dates,picks,prices,market,entry,ex)
                    byfold[key]=fold
                row={"selector":selector,"entry":entry,"exit":ex,"portfolio":overall,"byPeriod":byfold}
                grid.append(row)
                audit.append({"selector":selector,"entry":entry,"exit":ex,"closedBaskets":deals})
                if (selector in ("G","G Pro balanced") and entry in ("GTE60","LTE40","LTE40_BOTTOM")
                    and ex in ("HOLD20","GTE80_ALL","GTE70_HALF_80_ALL")):
                    curves[selector+"__"+entry+"__"+ex]={"dates":[v["date"] for v in curve],
                        "equity":[v["equity"] for v in curve]}
        print("MARKET_CONTRARIAN_SELECTOR_DONE",selector,flush=True)
    return grid,audit,curves
def lock_choice(grid):
    # Never inspect 2026 when choosing a hypothetical winner.
    rows=[]
    for r in grid:
        tr=r["byPeriod"]["train"];va=r["byPeriod"]["validation"]
        if tr["closedBaskets"]<8 or va["closedBaskets"]<6:continue
        if tr["netReturnPct"]<=0 or va["netReturnPct"]<=0:continue
        # Penalize peak-to-trough losses; strategy outcome includes cash idle.
        objective=.4*tr["netReturnPct"]+.6*va["netReturnPct"]+.25*tr["dailyMaxDrawdownPct"]+.4*va["dailyMaxDrawdownPct"]
        rows.append((objective,r))
    rows.sort(key=lambda x:(-x[0],x[1]["selector"],x[1]["entry"],x[1]["exit"]))
    if not rows:return {"status":"no_eligible_candidate","minTrainClosed":8,"minValidationClosed":6}
    score,rr=rows[0]
    return {"status":"selected_without_2026","selector":rr["selector"],"entry":rr["entry"],"exit":rr["exit"],
        "objective":round(score,3),"train":rr["byPeriod"]["train"],
        "validation":rr["byPeriod"]["validation"],"holdout":rr["byPeriod"]["holdout"],
        "candidateCount":len(rows)}
def main():
    started=time.time()
    OUT.mkdir(parents=True,exist_ok=True)
    universe=[x for x in load_universe() if finite(x.get("capitalB")) and float(x["capitalB"])>0]
    pfrom=datetime.fromisoformat(START)-timedelta(days=430)
    pto=datetime.fromisoformat(END)+timedelta(days=35)
    hist,errors=update_many([(x["code"],x["market"]) for x in universe],pfrom,pto)
    _,ix,err=update_symbol(BENCHMARK,pfrom,pto)
    if err or ix is None or ix.empty:raise RuntimeError("Missing TWII benchmark "+str(err))
    ix=ix.sort_values("date").drop_duplicates("date").reset_index(drop=True)
    dates=[d for d in ix.date.astype(str) if START<=d<=END]
    risk,_=get_risk(ix,dates)
    if len(dates)!=728 or len(risk)!=728:raise RuntimeError("Official risk coverage incomplete")
    raw=json.loads((DATA_DIR/"research"/"g_regime_3y"/"market_risk_daily.json").read_text(encoding="utf-8"))
    if [z["date"] for z in raw]!=dates:raise RuntimeError("Risk state and date alignment mismatch")
    market={z["date"]:z for z in raw}
    g,prices,gaudit=make_g(dates,ix,universe,hist)
    pool=make_ranked_pool(dates,ix,universe,hist)
    if any([x["code"] for x in g[d]]!=[x["code"] for x in pool[d][:3]] for d in dates):
        raise RuntimeError("G top3 parity failure; abort contrarian test")
    ind=build_daily_indicators(hist,{s["sym"] for rows in pool.values() for s in rows})
    variants=build_variants(dates,g,pool,ind)
    grid,trades,curves=evaluate(dates,variants,prices,market)
    distribution={"modeCounts":dict(collections.Counter(z.get("mode","NORMAL") for z in raw)),
        "LTE30Days":sum(z["score"]<=30 for z in raw),"LTE40Days":sum(z["score"]<=40 for z in raw),
        "LTE50Days":sum(z["score"]<=50 for z in raw),"GTE70Days":sum(z["score"]>=70 for z in raw),
        "GTE80Days":sum(z["score"]>=80 for z in raw),
        "LOW40_BOTTOMDays":sum(z["score"]<=40 and z.get("mode")=="BOTTOM" for z in raw)}
    out={"version":"G_MARKET_SCORE_CONTRARIAN_PREDECLARED_3Y_V1",
         "createdAt":datetime.now(ZoneInfo("Asia/Taipei")).isoformat(),
         "period":{"start":START,"end":END},"riskScoredDays":len(risk),"marketDays":len(dates),
         "stockDataErrors":len(errors),"selectors":RESEARCH_SELECTORS,
         "entryRules":ENTRY_RULES,"exitRules":EXIT_RULES,
         "maxHoldTradingSessions":MAX_HOLD_SESSIONS,"startCapital":STARTING_CAPITAL,
         "marketDistribution":distribution,"chronologicalFolds":SPLITS,
         "modelSelection":lock_choice(grid),"grid":grid,
         "limitations":["Risk Score high means momentum strength, NOT independently proven overvaluation.",
             "Risk Score low means weakness, NOT independently proven cheap valuation.",
             "BOTTOM and TOP are watch states in official dated market archive, not guaranteed turning points.",
             "Signals known at completed day D close, sell/buy/reduce at next open; no same-day execution.",
             "G/G Pro may have no strong candidates during low scores; entrySignalDays counts actual selection only.",
             "Current universe excludes delisted shares and uses current capital: survivorship/history bias.",
             "Yahoo adjusted open/close risk of corporate-action or fill distortion; no limit-up fill feasibility.",
             "Positions marked daily at adjusted close; missing marks held and disclosed, not treated as zero.",
             "One fully funded basket, fractional shares, 0.1425% entry brokerage, exit 0.1425% plus 0.3% tax.",
             "No bid-ask/slippage, financing, borrow or overnight execution costs.",
             "2026 was observed in prior investigations, so holdout is chronological but not entirely blind.",
             "Market mode TOP frequently denotes watch state; do not treat it as a confirmed reversal.",
             "TX futures night coverage still 0 and excluded; only TWII daytime close signals."]}
    for name,obj in (("summary.json",out),("trades.json",{"period":out["period"],"models":trades}),
                     ("equity.json",{"period":out["period"],"models":curves})):
        (OUT/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2 if name=="summary.json" else None),encoding="utf-8")
    print("G_MARKET_CONTRARIAN_DONE",json.dumps({"models":len(grid),"marketDays":len(dates),
        "trainChosen":out["modelSelection"],"elapsedSec":int(time.time()-started)},ensure_ascii=False),flush=True)
if __name__=="__main__":main()
