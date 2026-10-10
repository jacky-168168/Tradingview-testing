"""G Compound: 500k top-1 daily target-limit cash compounding experiment.
Author vanilla118 PTT Oct 4 2026 disclosed WORKFLOW but NOT proprietary
ranking/risk model/target calculation/stoploss/capital resizing.
This is NOT a clone. Independently test immutable existing G/G Pro candidates,
verified official 728 TWII market scores and transparent preset TP/SL alternatives.
2023-24 train, 2025 validation, Apr-Oct 2026 audit; no 2026 parameter choice.
No capital borrowing, multiple concurrent tickets if cash, max one entry per day.
"""
from __future__ import annotations
import collections,json,math,time
from datetime import datetime,timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
import numpy as np,pandas as pd
from config import DATA_DIR,BENCHMARK
from pipeline import load_universe
from yahoo_cache import update_many,update_symbol
from research_g_regime_3y import START,END,make_g,get_risk,finite
from research_g_pro_round2 import make_ranked_pool,build_variants
from g_pro_rules import build_daily_indicators
OUT=DATA_DIR/"research"/"g_compound_3y"
PRINCIPAL=500_000.
BROKER=.001425
SELL_TAX=.003
SLIP=.001
BUY_FACTOR=1+BROKER+SLIP
SELL_FACTOR=1-BROKER-SELL_TAX-SLIP
TP_FILL_BUFFER=.001
PRICE_CHASE_LIMIT=.03
MIN_TRADE=20_000.
# Explicit exploratory grid. None of the author-hidden target or stop levels is known.
SELECTORS=("G","G Pro balanced","G Pro quality")
GATES=("SCORE50","SCORE60","SCORE70","SCORE60_NOT_STRONG_TOP")
TARGETS=(.03,.05,.08,.10)
STOPS=(.05,.08,.12,None)
MAX_HOLD=(3,5,10)
CAPACITY=(200_000.,500_000.)
FOLDS={"train":("2023-10-09","2024-12-31"),
       "validation":("2025-01-01","2025-12-31"),
       "audit2026":("2026-01-01",END),
       "authorWindow2026":("2026-04-15","2026-10-02"),
       "postPublication2026":("2026-04-15",END),
       "all":(START,END)}
def price_bars(hist, symbols):
    """Daily adjusted OHLC derived using SAME-DAY adjclose/close ratio;
    raw close on signal D is compared with D+1 RAW open for +3% cap.
    """
    bars={};excluded=collections.Counter()
    for sy in sorted(symbols):
        df=hist.get(sy)
        if df is None or df.empty:excluded["missing_symbol"]+=1;continue
        q=df.copy().sort_values("date").drop_duplicates("date",keep="last")
        for c in ("open","high","low","close","adjclose","volume"):
            q[c]=pd.to_numeric(q[c],errors="coerce")
        adj=q.adjclose/q.close.replace(0,np.nan)
        q["adjOpen"]=q.open*adj;q["adjHigh"]=q.high*adj;q["adjLow"]=q.low*adj;q["adjClose"]=q.adjclose
        ok=q[["open","high","low","close","adjOpen","adjHigh","adjLow","adjClose","volume"]].notna().all(axis=1)
        q=q[ok & (q.close>0) & (q.volume>0)].copy()
        bars[sy]={str(r.date):(float(r.open),float(r.high),float(r.low),float(r.close),
            float(r.adjOpen),float(r.adjHigh),float(r.adjLow),float(r.adjClose),float(r.volume))
            for r in q.itertuples(index=False)}
    return bars,dict(excluded)
def market_allows(rule,rec):
    if rec is None:return False
    sc=int(rec["score"])
    if rule=="SCORE50":return sc>=50
    if rule=="SCORE60":return sc>=60
    if rule=="SCORE70":return sc>=70
    if rule=="SCORE60_NOT_STRONG_TOP":
        return sc>=60 and rec.get("topState")!="🔴 Strong Top Reversal"
    raise ValueError(rule)
def study_one(dates, picks, bars, scores, gate, tp, sl, maxhold, cap, logs=False):
    """No future signals or overlapping cash. Entry +3% uses previous raw CLOSE.
    Execution next session OPEN; sells use intraday OHLC with ambiguous bars
    pessimistically assuming stop hits FIRST. Stop gaps sell at next OPEN.
    Open>=TP sells at OPEN, otherwise intraday limit target if high clears
    target with 0.1% high-price buffer, after stop conflict resolution.
    Time expiry exits at the NEXT day's OPEN. On last D leftover positions
    marked net-of-liquidation costs, NOT forged into closed trades.
    """
    cash=PRINCIPAL;positions=[];ledger=[];closed=[];reasons=collections.Counter()
    peak=PRINCIPAL;worstdd=0.;max_concurrent=0;stale_marks=0;limit_touch_uncertain=0
    blocked=collections.Counter();entry_offers=0;filled=0;cum_traded=0.;last_mark={}
    start_time=time.monotonic()
    def exit_pos(pos,dt,px,reason):
        nonlocal cash,cum_traded
        proceeds=pos["units"]*px*SELL_FACTOR
        cash+=proceeds;cum_traded+=proceeds
        ticket={"buyDate":pos["buyDate"],"sellDate":dt,"signalDate":pos["signalDate"],
                "code":pos["code"],"name":pos["name"],"units":pos["units"],
                "buyAdjusted":round(pos["buyPrice"],4),"sellAdjusted":round(px,4),
                "target":round(pos["target"],4),"stop":round(pos["stop"],4) if pos["stop"] else None,
                "invested":round(pos["invested"],2),"netPnL":round(proceeds-pos["invested"],2),
                "netPct":round(100*(proceeds/pos["invested"]-1),4),
                "calendarHoldDays":(datetime.fromisoformat(dt)-datetime.fromisoformat(pos["buyDate"])).days,
                "sessionHold":pos["held"],"exitReason":reason}
        closed.append(ticket);reasons[reason]+=1
    for i,day in enumerate(dates):
        # Executable D+1 entry uses only finished D prior risk and Top1 signal.
        if i>0:
            prior=dates[i-1];bucket=picks.get(prior) or []
            if bucket and market_allows(gate,scores.get(prior)):
                entry_offers+=1;stock=bucket[0];sy=stock["sym"]
                if any(p["symbol"]==sy for p in positions):blocked["already_owned"]+=1
                else:
                    q=bars.get(sy,{}).get(day)
                    if q is None:blocked["missing_entry_open"]+=1
                    else:
                        ro,rh,rl,rc,ao,ah,al,ac,volume=q;prev_close=finite(stock.get("close"))
                        if not prev_close or prev_close<=0:blocked["missing_prior_close"]+=1
                        elif ro>prev_close*(1+PRICE_CHASE_LIMIT)+1e-8:blocked["open_over_plus3pct"]+=1
                        elif ro>=prev_close*1.095 and rh<=rl+1e-8:blocked["locked_limit_up"]+=1
                        elif cash<MIN_TRADE:blocked["cash_below_minimum"]+=1
                        else:
                            budget=min(cash,float(cap));qty=int(budget/(ao*BUY_FACTOR))
                            if qty<=0 or qty*ao*BUY_FACTOR<MIN_TRADE:
                                blocked["insufficient_for_order"]+=1
                            else:
                                paid=qty*ao*BUY_FACTOR
                                if paid>cash+1e-7:raise RuntimeError("CASH OVERSPENT")
                                cash-=paid;filled+=1;cum_traded+=paid
                                positions.append({"symbol":sy,"code":stock["code"],"name":stock["name"],
                                    "units":qty,"invested":paid,"buyPrice":ao,
                                    "buyDate":day,"signalDate":prior,"target":ao*(1+tp),
                                    "stop":ao*(1-sl) if sl is not None else None,
                                    "held":0,"last":ao})
        remain=[]
        for pos in positions:
            q=bars.get(pos["symbol"],{}).get(day)
            if q is None:
                stale_marks+=1;remain.append(pos);continue
            ro,rh,rl,rc,ao,ah,al,ac,vol=q
            pos["held"]+=1
            pos["last"]=ac
            stop=pos["stop"];target=pos["target"];elapsed=pos["held"]
            # The time-stop already expired after the previous session close.
            # Execute at THIS OPEN before inspecting the current high or low.
            if elapsed>maxhold:
                exit_pos(pos,day,ao,"time_next_open");continue
            # Both sides cannot be filled at the same time; OPEN is known first.
            if stop is not None and ao<=stop:
                exit_pos(pos,day,ao,"gap_stop");continue
            if ao>=target:
                exit_pos(pos,day,ao,"gap_target");continue
            # Stop-first is conservative when intraday order is unknown.
            if stop is not None and al<=stop:
                if ah>=target:blocked["same_bar_tp_sl_ambiguous"]+=1
                exit_pos(pos,day,stop,"intraday_stop");continue
            if ah>=target*(1+TP_FILL_BUFFER):
                exit_pos(pos,day,target,"target_limit");continue
            if ah>=target:limit_touch_uncertain+=1
            remain.append(pos)
        positions=remain
        total=cash+sum(p["units"]*p["last"]*SELL_FACTOR for p in positions)
        peak=max(peak,total);worstdd=min(worstdd,total/peak-1)
        max_concurrent=max(max_concurrent,len(positions))
        ledger.append({"date":day,"equity":round(total,2),"cash":round(cash,2),
                       "openTickets":len(positions),"closedTickets":len(closed)})
    if not ledger:raise RuntimeError("Empty account ledger")
    win=[v for v in closed if v["netPnL"]>0];lose=[v for v in closed if v["netPnL"]<=0]
    n=len(closed);helds=[x["sessionHold"] for x in closed];ret=[x["netPct"] for x in closed]
    ending=float(ledger[-1]["equity"])
    report={"start":dates[0],"end":dates[-1],"capitalStart":PRINCIPAL,"capitalEnd":round(ending,2),
        "netReturnPct":round(100*(ending/PRINCIPAL-1),3),"maxDDPct":round(100*worstdd,3),
        "entryOffers":entry_offers,"filledBuys":filled,"closedTrades":n,
        "wins":len(win),"losses":len(lose),
        "winPct":round(100*len(win)/n,2) if n else None,
        "avgNetPct":round(float(np.mean(ret)),3) if n else None,
        "avgWinPct":round(float(np.mean([x["netPct"] for x in win])),3) if win else None,
        "avgLossPct":round(float(np.mean([x["netPct"] for x in lose])),3) if lose else None,
        "avgHoldSessions":round(float(np.mean(helds)),2) if n else None,
        "medianHoldSessions":round(float(np.median(helds)),2) if n else None,
        "maxConcurrent":max_concurrent,"openAtEnd":len(positions),
        "netUnrealizedTWD":round(sum(p["units"]*p["last"]*SELL_FACTOR for p in positions),2),
        "cashAtEnd":round(cash,2),"blocked":dict(blocked),"exitTypes":dict(reasons),
        "staleMarkDays":stale_marks,"uncertainLimitTouch":limit_touch_uncertain,
        "grossTicketTurnoverTWD":round(cum_traded,2)}
    if logs:return report,ledger,closed
    return report,None,None
def summary_pair(r):
    return {k:r[k] for k in ("capitalEnd","netReturnPct","maxDDPct","filledBuys","closedTrades",
        "wins","losses","winPct","avgNetPct","avgWinPct","avgLossPct","avgHoldSessions",
        "openAtEnd","cashAtEnd","netUnrealizedTWD")}
def freeze_selection(results):
    """Select only with 2023-24 training and 2025 validation; never 2026.
    Demand 12+ completed both periods, actual finite wealth, positive fold returns.
    Every family is post-hoc exploratory due prior G development.
    """
    rows=[]
    for r in results:
        tr=r["byPeriod"]["train"];va=r["byPeriod"]["validation"]
        if min(tr["closedTrades"],va["closedTrades"])<12:continue
        if tr["netReturnPct"]<=0 or va["netReturnPct"]<=0:continue
        if tr["maxDDPct"]< -45 or va["maxDDPct"]< -45:continue
        objective=.50*tr["netReturnPct"]+.50*va["netReturnPct"]+0.5*tr["maxDDPct"]+0.7*va["maxDDPct"]
        rows.append((objective,r))
    rows.sort(key=lambda t:(-t[0],t[1]["id"]))
    if not rows:return {"status":"no_strategy_met_prefrozen_quality_floor",
        "minClosedEachTrainValidation":12,"minReturnEachTrainValidation":0,"maxDrawdownFloorPct":-45}
    metric,row=rows[0]
    return {"status":"selected_without_2026","id":row["id"],"criteriaScore":round(metric,3),
            "eligibleChoices":len(rows),"training":row["byPeriod"]["train"],
            "validation":row["byPeriod"]["validation"],"audit2026":row["byPeriod"]["audit2026"],
            "authorWindow2026":row["byPeriod"]["authorWindow2026"]}
def main():
    started=time.monotonic();OUT.mkdir(parents=True,exist_ok=True)
    universe=[x for x in load_universe() if finite(x.get("capitalB")) and float(x["capitalB"])>0]
    pullfrom=datetime.fromisoformat(START)-timedelta(days=430)
    pullto=datetime.fromisoformat(END)+timedelta(days=35)
    hist,errors=update_many([(s["code"],s["market"]) for s in universe],pullfrom,pullto)
    _,index,err=update_symbol(BENCHMARK,pullfrom,pullto)
    if err or index is None or index.empty:raise RuntimeError("Missing dated TWII index: "+str(err))
    index=index.sort_values("date").drop_duplicates("date").reset_index(drop=True)
    dates=[d for d in index.date.astype(str) if START<=d<=END]
    if len(dates)!=728:raise RuntimeError("Must have exactly 728 historically verified TWII sessions, got "+str(len(dates)))
    official,_=get_risk(index,dates)
    archive=json.loads((DATA_DIR/"research"/"g_regime_3y"/"market_risk_daily.json").read_text(encoding="utf-8"))
    if [x["date"] for x in archive]!=dates:raise RuntimeError("Dated official risk archive calendar mismatch")
    risk={x["date"]:x for x in archive}
    if any(official[d]!=risk[d]["score"] for d in dates):raise RuntimeError("Official risk scores drift")
    g,_,gaudit=make_g(dates,index,universe,hist)
    top20=make_ranked_pool(dates,index,universe,hist)
    drift=[d for d in dates if [x["code"] for x in g[d]]!=[x["code"] for x in top20[d][:3]]]
    if drift:raise RuntimeError("Original G Top3 reconstruction parity failure "+str(drift[:3]))
    ins=build_daily_indicators(hist,{s["sym"] for daily in top20.values() for s in daily})
    variants=build_variants(dates,g,top20,ins)
    candidates={k:{d:v[0] if v else None for d,v in variants[k].items()} for k in SELECTORS}
    selected_sy={r["sym"] for p in candidates.values() for r in p.values() if r}
    bars,price_errors=price_bars(hist,selected_sy)
    if not bars:raise RuntimeError("No historical adjusted OHLC")
    print("G_COMPOUND_DATA_PREPARED",json.dumps({"marketDays":len(dates),"universe":len(universe),
        "stockErrors":len(errors),"uniqueSelectedSymbols":len(selected_sy),"bars":len(bars),
        "selectorSignalDays":{k:sum(bool(r) for r in v.values()) for k,v in candidates.items()}},ensure_ascii=False),flush=True)
    result=[];all_cases=[];all_logs={};trades={}
    for selector in SELECTORS:
        picks={d:([s] if s else []) for d,s in candidates[selector].items()}
        for gate in GATES:
            for tp in TARGETS:
                for sl in STOPS:
                    for maxhold in MAX_HOLD:
                        for cap in CAPACITY:
                            id=f"{selector.replace(' ','_')}__{gate}__TP{int(tp*100)}__SL{int(sl*100) if sl else 0}__H{maxhold}__CAP{int(cap/1000)}K"
                            cfg={"selector":selector,"riskGate":gate,"targetPct":100*tp,
                                 "stopPct":100*sl if sl is not None else None,
                                 "maxHoldTradingDays":maxhold,"maxPerEntryTWD":cap}
                            byfold={}
                            for fold,(lo,hi) in FOLDS.items():
                                dates1=[d for d in dates if lo<=d<=hi]
                                if len(dates1)<20:raise RuntimeError("Fold too short")
                                r,_,_=study_one(dates1,picks,bars,risk,gate,tp,sl,maxhold,cap)
                                byfold[fold]=summary_pair(r)
                            record={"id":id,"params":cfg,"byPeriod":byfold}
                            result.append(record)
        print("G_COMPOUND_SELECTOR_DONE",selector,len(result),flush=True)
    selected=freeze_selection(result)
    # Publish details of the train+validation pick, and predeclared original
    # G baseline alternatives. No cherry-picking 2026 top performer.
    audit_ids=set()
    if selected.get("id"):audit_ids.add(selected["id"])
    for name in ("G","G Pro balanced","G Pro quality"):
        for cap in (200_000.,500_000.):
            cid=f"{name.replace(' ','_')}__SCORE60__TP5__SL8__H5__CAP{int(cap/1000)}K"
            audit_ids.add(cid)
    detail={};ledger={}
    for model in result:
        if model["id"] not in audit_ids:continue
        p=model["params"];picks={d:([x] if x else []) for d,x in candidates[p["selector"]].items()}
        rows={};equities={}
        for fold in ("all","authorWindow2026","postPublication2026"):
            lo,hi=FOLDS[fold];valid_dates=[d for d in dates if lo<=d<=hi]
            performance,curve,tx=study_one(valid_dates,picks,bars,risk,p["riskGate"],
                p["targetPct"]/100,p["stopPct"]/100 if p["stopPct"] is not None else None,
                p["maxHoldTradingDays"],p["maxPerEntryTWD"],logs=True)
            rows[fold]={"metrics":performance,"trades":tx}
            equities[fold]=curve
        detail[model["id"]]=rows
        ledger[model["id"]]=equities
    # Counts realistic 2026 short sample; explicitly check target vs author's
    # self-reported 52 realized trades, 51 wins, +3,158,915.39 booked PnL.
    author={"postDate":"2026-10-04","author":"vanilla118",
        "claimedInitialTestingCapitalTWD":500_000,"claimedInitialDailyBudgetTWD":200_000,
        "claimedInitialInvestedCapTWD":500_000,
        "claimedClosedTickets":52,"claimedWinningTickets":51,
        "claimedRealizedProfitTWD":3_158_915.39,"impliedWealthWithoutNetDepositsTWD":3_658_915.39,
        "comparisonCutoff":"2026-10-02 (last TWSE session before 2026-10-04 article)",
        "unverifiable":["Secret ranking inputs and score","Secret market risk algorithm",
            "Secret profit target and stop loss","Exact trade accounting flows","Whether early cap later increased",
            "Historical futures/night snapshots"] }
    # Best 2026 is shown as explicit retrospective upper bound, never candidate selection.
    best_hindsight=sorted(result,key=lambda m:m["byPeriod"]["authorWindow2026"]["netReturnPct"],reverse=True)[:5]
    risk_counts=collections.Counter()
    for gate in GATES:risk_counts[gate]=sum(market_allows(gate,risk[d]) for d in dates)
    summary={"version":"G_COMPOUND_TOP1_CASH_LEDGER_3Y_V1",
      "createdAt":datetime.now(ZoneInfo("Asia/Taipei")).isoformat(),
      "period":[START,END],"riskScoreCoverage":len(risk),"universeNow":len(universe),
      "stockHistoryErrors":len(errors),"stockSelectedSymbols":len(selected_sy),
      "stockOHLCLoaded":len(bars),"missingOHLC":price_errors,
      "originalGParity":True,"selectorSignalDays":{k:sum(bool(r) for r in v.values()) for k,v in candidates.items()},
      "testConfig":{"selectors":SELECTORS,"riskGate":GATES,
          "targetsPct":[v*100 for v in TARGETS],
          "stopPct":[v*100 if v is not None else None for v in STOPS],
          "holds":MAX_HOLD,"capacityTWD":CAPACITY,"initialCapitalTWD":PRINCIPAL,
          "priceChaseMaxPct":3.0,"minTradeTWD":MIN_TRADE,"buyBrokerPct":100*BROKER,
          "sellBrokerPct":100*BROKER,"sellStockTaxPct":100*SELL_TAX,
          "eachSideSlippagePct":100*SLIP,"takeProfitLimitHighBufferPct":100*TP_FILL_BUFFER},
      "historicalGOfficialRiskDaysAllowed":dict(risk_counts),"authorDisclosure":author,
      "trainingWindows":FOLDS,"selectionFromTrainValidationOnly":selected,
      "totalCases":len(result),
      "retrospectiveBest2026NotSelected":[{"id":x["id"],"authorWindow":x["byPeriod"]["authorWindow2026"]} for x in best_hindsight],
      "models":result,
      "limitations":["Author does NOT disclose ranking, risk algorithm, target, stop loss or money-flow ledger; this is an independently specified simulation, NOT his system.",
        "Unknown 2026 source winner/target cannot be learned from a 52-ticket brokerage excerpt.",
        "Historic candidate pool is today's survivors and today's capital; delisted companies and capital change are omitted (survivorship/hindsight bias).",
        "Yahoo adjusted OHLC is only daily bars; order sequencing between high/low unknown. We assume STOP first in same-bar TP+SL conflicts, and target requires 0.1% high buffer.",
        "Taiwan intraday odd-lot at regular market OPEN is not the same matching mechanism as board lots; model uses integer units and open price as a capacity proxy.",
        "Buy at next open only if raw opening is <= previous close*1.03; if open over +3%, no later intraday entry, which is conservative.",
        "A true intraday conditional limit order might not fill at high/low touch even with buffer; simulation can still overestimate fills.",
        "One proposed new stock per day, multiple simultaneous holdings if cash allows, no leverage, same ticker cannot be bought again while held.",
        "Target sell remains working after day 1; maximum holding time exits next day's open; no guaranteed stop liquidity on gap/limit down.",
        "Stock market board lot/odd lot, trading halts, broker order and last-session settlement constraints are simplified.",
        "Night futures archival coverage insufficient; no invented night gate. Historical market risk uses dated TWSE data only.",
        "Early 200k/day and 500k max were author's initial experiment settings, not proof of later capacity.",
        "Grid is explorative and huge; best in 2026 is purely hindsight and cannot be called a valid strategy.",
        "2026 price paths are already historically observed in prior G work; chronological audit is not a pristine blind test.",
        "Unrealized open positions at end are valued net of hypothetical liquidation costs, but not counted as completed profitable trades.",
        "Any 52-win target comparison is only descriptive; false precision at 98% would mislead."]}
    for file,obj in (("summary.json",summary),("trades.json",{"version":summary["version"],
        "auditedModels":detail}),("equity.json",{"version":summary["version"],"auditedModels":ledger})):
        (OUT/file).write_text(json.dumps(obj,ensure_ascii=False,indent=2 if file=="summary.json" else None),encoding="utf-8")
    print("G_COMPOUND_DONE",json.dumps({"models":len(result),"chosen":selected.get("id"),
        "authorPeriodTarget":author["impliedWealthWithoutNetDepositsTWD"],
        "best2026Hindsight":best_hindsight[0]["byPeriod"]["authorWindow2026"],
        "elapsedSec":round(time.monotonic()-started)},ensure_ascii=False),flush=True)
if __name__=="__main__":main()
