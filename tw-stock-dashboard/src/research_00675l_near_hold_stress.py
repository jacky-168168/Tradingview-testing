"""Post-selection stress tests for frozen 00675L near-buyhold genuine roundtrip rules.
Report only: no model choice depends on 2026 stress outcomes.
"""
from __future__ import annotations
import json,time
from datetime import datetime
from zoneinfo import ZoneInfo
from research_00675l_near_hold_switch import *
import research_00675l_near_hold_switch as orig
def bt_lag(a,dates,c,begin,end,detailed=False,lag=0):
    idx=np.where((dates>=begin)&(dates<=end))[0]
    if len(idx)<50:raise RuntimeError("insufficient bars "+begin)
    cash=float(CAPITAL);shares=0;state=True;trades=[];events=[];equity=[];regime_days=0;traded_days=0
    opens=a["open"];closes=a["close"];buy_factor=(1+SLIP)*(1+BROKER);sell_factor=(1-SLIP)*(1-BROKER-ETF_SELL_TAX)
    for pos,i in enumerate(idx):
        date=dates[i];px=float(opens[i]);mark=float(closes[i]);oldshares=shares
        if pos==0:
            desired=True
        else:
            # Causal: previous close decides trades at today's open, never today's close.
            j=i-1-lag;desired=risk_state(c,a,j,not state)
        if desired!=state:state=desired
        # Align to target allocation *only on regime changes* (or first open).
        if pos==0 or desired!=bool(prev_target):
            want=1. if state else c.get("riskOffWeight",0.0)
            gross=cash+shares*px*sell_factor
            target=int(max(0,gross*want)//(px*buy_factor))
            if shares>target:
                n=shares-target
                proceeds=n*px*sell_factor;cash+=proceeds;shares-=n
                events.append({"date":str(date),"side":"SELL","shares":n,"grossPrice":round(px*(1-SLIP),4),
                               "netCash":round(proceeds,2),"accountCash":round(cash,2),"phase":"risk_off"})
            elif shares<target:
                count=min(target-shares,int(cash//(px*buy_factor)))
                if count>0:
                    paid=count*px*buy_factor;cash-=paid;shares+=count
                    events.append({"date":str(date),"side":"BUY","shares":count,"grossPrice":round(px*(1+SLIP),4),
                                   "netCash":round(-paid,2),"accountCash":round(cash,2),"phase":"risk_on"})
        prev_target=state
        if shares>0:traded_days+=1
        if not state:regime_days+=1
        account=cash+shares*mark*sell_factor
        equity.append({"date":str(date),"equity":round(account,2),"heldShares":int(shares),"riskOn":bool(state)})
    if shares>0:
        px=float(closes[idx[-1]])
        proceeds=shares*px*sell_factor
        cash+=proceeds
        events.append({"date":str(dates[idx[-1]]),"side":"SELL","shares":shares,
                       "grossPrice":round(px*(1-SLIP),4),"netCash":round(proceeds,2),
                       "accountCash":round(cash,2),"phase":"period_end"})
        shares=0
        equity[-1]["equity"]=round(cash,2);equity[-1]["heldShares"]=0
    vals=np.array([x["equity"] for x in equity])
    m=np.maximum.accumulate(np.r_[CAPITAL,vals])[1:]
    dd=float(min((vals/m-1)*100))
    sells=sum(e["side"]=="SELL" and e["phase"]=="risk_off" for e in events)
    rebuys=sum(e["side"]=="BUY" and e["phase"]=="risk_on" for e in events)-1
    result={"start":str(dates[idx[0]]),"end":str(dates[idx[-1]]),
            "returnPct":round((cash/CAPITAL-1)*100,3),"endNTD":round(cash,2),
            "mddPct":round(dd,3),"riskOffSessions":int(regime_days),
            "investedSessions":int(traded_days),"sessions":len(idx),
            "riskOffSells":int(sells),"riskOnReentries":int(max(rebuys,0)),
            "switchEvents":int(len(events)-2 if events[-1]["phase"]=="period_end" else len(events)-1)}
    if detailed:result.update({"equity":equity,"orders":events})
    return result

OUT=OUTPUT
WATCH=["CRASH_3_0.1_RE10_Gtwii_below60_W0.0","MA_twii_20_O0.03_R0.0_C1_W0.0","TRAIL_20_0.16_RE10_W0.0"]
def lite(z):
    return {k:z[k] for k in ("returnPct","endNTD","mddPct","riskOffSells","riskOnReentries","riskOffSessions")}
def main():
    _,etf,e=update_symbol(SYMBOL,datetime(2023,1,1),datetime(2026,10,9))
    _,ind,e2=update_symbol(INDEX,datetime(2023,1,1),datetime(2026,10,9))
    if e or e2 or etf is None or ind is None or etf.empty or ind.empty:raise RuntimeError(str((e,e2)))
    summary=json.loads((OUT/"summary.json").read_text(encoding="utf-8"))
    # Compare against EXACTLY the frozen research date, independent of fresh Yahoo bar updates.
    raw=data_prepare(etf,ind)
    d=prepare(raw[raw.date<=summary["dateEnd"]].copy());a,dates=indicators(d)
    byid={x["id"]:x["params"] for x in summary["frozenComparisons"]}
    baseline=bt_lag(a,dates,byid[WATCH[0]],*PERIODS["continuous"],lag=0)
    expected=next(x["continuous"] for x in summary["frozenComparisons"] if x["id"]==WATCH[0])
    assert baseline["returnPct"]==expected["returnPct"] and baseline["mddPct"]==expected["mddPct"],(baseline,expected)
    cost={}
    for side in (.001,.003,.005,.01):
        globals()["SLIP"]=side
        cost[str(side)]={}
        for name in WATCH:
            rule=byid[name]
            full=bt_lag(a,dates,rule,*PERIODS["continuous"])
            y26=bt_lag(a,dates,rule,*PERIODS["2026"])
            cost[str(side)][name]={"continuous":lite(full),"2026":lite(y26)}
        buyhold=bt_lag(a,dates,{"id":"BUY_HOLD","family":"buyhold","riskOffWeight":1},*PERIODS["continuous"])
        cost[str(side)]["BUY_HOLD"]={"continuous":lite(buyhold)}
        print("ETF_STRESS_FRICTION "+json.dumps({"sidePct":side*100,"candidateReturn":cost[str(side)][WATCH[0]]["continuous"]["returnPct"],
            "buyholdReturn":cost[str(side)]["BUY_HOLD"]["continuous"]["returnPct"]}),flush=True)
    globals()["SLIP"]=.001
    lags={}
    for lag in (0,1,2):
        lags[str(lag)]={}
        for name in WATCH:
            rule=byid[name]
            full=bt_lag(a,dates,rule,*PERIODS["continuous"],lag=lag)
            lags[str(lag)][name]={"continuous":lite(full)}
        print("ETF_STRESS_DELAY "+json.dumps({"extraTradingSessions":lag,"winner":lags[str(lag)][WATCH[0]]["continuous"]["returnPct"]}),flush=True)
    # Mechanically vary a SMALL neighborhood without choosing a new 2026 winner.
    neighborhood=[]
    for n in (2,3,5):
        for drop in (.08,.10,.12):
            for recovery in (10,20):
                c={"id":f"POSTSTRESS_{n}_{drop}_{recovery}","family":"crash_protection","n":n,
                   "fall":drop,"re":recovery,"gate":"twii_below60","riskOffWeight":0}
                y24=bt_lag(a,dates,c,*PERIODS["2024"])
                y25=bt_lag(a,dates,c,*PERIODS["2025"])
                y26=bt_lag(a,dates,c,*PERIODS["2026"])
                full=bt_lag(a,dates,c,*PERIODS["continuous"])
                neighborhood.append({"nDays":n,"fallPct":drop*100,"recoverEMA":recovery,
                 "2024":lite(y24),"2025":lite(y25),"2026":lite(y26),"continuous":lite(full)})
    positive=sum(all(x[y]["returnPct"]>0 for y in ("2024","2025","2026")) for x in neighborhood)
    abovehold=sum(x["continuous"]["returnPct"]>=summary["baseline"]["continuous"]["returnPct"] for x in neighborhood)
    report={"version":"00675L_NEAR_HOLD_ROBUSTNESS_V1",
         "generatedAt":datetime.now(ZoneInfo("Asia/Taipei")).isoformat(timespec="seconds"),
         "lastDate":str(d.iloc[-1].date),"ticker":SYMBOL,"models":WATCH,
         "originalBuyholdReturnPct":summary["baseline"]["continuous"]["returnPct"],
         "originalCandidateReturnPct":baseline["returnPct"],
         "transactionCostSensitivity":{"perSideSlippageFraction":list(cost),"stats":cost},
         "delaySensitivity":{"extraTradingSessions":[0,1,2],
            "method":"trade decision is based on indicator at close T-lag instead of T; execute next open, no future data",
            "stats":lags},
         "neighborhood":{"variants":neighborhood,"count":len(neighborhood),"allThreeCalendarYearsProfitable":positive,
                          "continuousReturnAtLeastBuyHold":abovehold},
         "warnings":["This stress analysis is descriptive only, not a strategy reoptimization by 2026 outcomes.",
           "Daily bars do not prove ability to trade intraday through volatile crash or rebound sessions.",
           "Extreme slippage up to 1% per side may be hypothetical and not based on order book.",
           "Delayed signal history simulates stale signals, not intraday exchange execution; no price impact or financing.",
           "2026 market regime has been previously researched and cannot be treated as fully unseen.",
           "Adjacent parameters that exceed buy-and-hold in sampled years do not imply statistically reliable future alpha."]}
    (OUT/"stress.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print("ETF_STRESS_DONE "+json.dumps({"baseline":baseline["returnPct"],
         "slip5bp":cost["0.005"][WATCH[0]]["continuous"]["returnPct"],
         "lag1":lags["1"][WATCH[0]]["continuous"]["returnPct"],
         "neighborCount":len(neighborhood),"neighborsBeatHold":abovehold}),flush=True)
if __name__=="__main__":main()
