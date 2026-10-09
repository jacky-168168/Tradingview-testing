"""00675L execution robustness: delay & friction test of calendar-frozen EMA10 reclaim.
The entry delay is a separate delayed-causal execution assumption, not a 2026-tuned new strategy.
"""
from __future__ import annotations
import json,math,time
from datetime import datetime
from zoneinfo import ZoneInfo
import pandas as pd,numpy as np
from research_00675l_swing_grid import *
from research_00675l_swing_grid import data_prepare,signal
import research_00675l_swing_grid as base
def simulate_delay(d,c,begin,end,trade_details=False,entry_delay=0):
    x=d.index[d.date.between(begin,end)].tolist()
    if len(x)<20:raise RuntimeError("Insufficient dates "+begin+" .. "+end)
    cash=float(CAPITAL);qty=0;entry_px=0;entry_cost=0;entry_at=-1;peakclose=0;equities=[];trades=[]
    # exit_signal for last closed day, not contemporary close. A single position at any time.
    for kk,i in enumerate(x):
        bar=d.iloc[i];date=bar.date
        o,h,l,close=(float(bar[z]) for z in ("open","high","low","close"))
        p=d.iloc[i-1] if i>=1 else None;q=d.iloc[i-2] if i>=2 else None
        buy_sig,sell_sig=signal(p,q,c) if p is not None and q is not None else (False,False)
        if entry_delay>0:
            lagidx=i-1-entry_delay
            buy_sig=signal(d.iloc[lagidx],d.iloc[lagidx-1],c)[0] if lagidx>=1 else False
        if c["family"]=="buy_hold":buy_sig=kk==0;sell_sig=False
        closed_today=False;opened_today=False
        def sell(gross_px,reason):
            nonlocal qty,cash,entry_px,entry_cost,entry_at,peakclose,closed_today
            px=max(0.01,gross_px*(1-SLIP));proceeds=qty*px*(1-BROKER-ETF_SELL_TAX)
            cash+=proceeds
            net=100*(proceeds/entry_cost-1)
            trades.append({"buyDate":str(d.iloc[entry_at].date),"sellDate":date,"buyPx":round(entry_px,3),
                  "sellPx":round(px,3),"holdingDays":i-entry_at+1,"reason":reason,
                  "netPct":round(net,3),"netNTD":round(proceeds-entry_cost,2)})
            qty=0;entry_px=0;entry_cost=0;entry_at=-1;peakclose=0;closed_today=True
        if qty:
            sl=float(c.get("sl",0))
            stop=entry_px*(1-sl) if sl>0 else 0
            if c.get("atr_stop_mult") and entry_at>=1:
                v=float(d.iloc[entry_at-1].atr14)
                if math.isfinite(v):stop=max(stop,entry_px-c["atr_stop_mult"]*v)
            if c.get("trail"):stop=max(stop,peakclose*(1-c["trail"]))
            if c.get("atr_trail_mult") and p is not None and math.isfinite(float(p.atr14)):
                stop=max(stop,peakclose-c["atr_trail_mult"]*float(p.atr14))
            target=entry_px*(1+c["tp"]) if c.get("tp") else None
            if o<=stop and stop>0:sell(o,"gap_stop")
            elif sell_sig:sell(o,"indicator_exit")
            elif target and o>=target:sell(o,"gap_target")
            elif stop>0 and l<=stop:sell(stop,"stop")
            elif target and h>=target:sell(target,"target")
            elif c.get("hold") and i-entry_at+1>=c["hold"]:sell(close,"time_exit")
        if not qty and not closed_today and buy_sig:
            paid_px=o*(1+SLIP)
            number=math.floor(cash/(paid_px*(1+BROKER)))
            if number>0:
                total=number*paid_px*(1+BROKER)
                cash-=total;qty=number;entry_px=paid_px;entry_cost=total;entry_at=i;peakclose=paid_px;opened_today=True
                # Newly opened intraday path unknown; conservatively honor same-day downside,
                # never a positive TP on day of entry.
                sl=float(c.get("sl",0))
                if sl>0 and l<=paid_px*(1-sl):sell(paid_px*(1-sl),"entry_day_stop")
        if qty and not opened_today:peakclose=max(peakclose,close)
        marked=cash+(qty*close*(1-SLIP)*(1-BROKER-ETF_SELL_TAX) if qty else 0)
        equities.append({"date":date,"equity":round(marked,2),"held":bool(qty)})
    if qty:
        last=d.iloc[x[-1]]
        sell(float(last.close),"period_end")
        equities[-1]["equity"]=round(cash,2);equities[-1]["held"]=False
    vals=np.array([e["equity"] for e in equities],dtype=float)
    mx=np.maximum.accumulate(np.r_[CAPITAL,vals])[1:]
    maxdd=float(np.min(100*(vals/mx-1)))
    gain=100*(cash/CAPITAL-1)
    wins=sum(t["netPct"]>0 for t in trades)
    avgnet=float(np.mean([t["netPct"] for t in trades])) if trades else 0
    pf=(sum(max(t["netNTD"],0) for t in trades)/-sum(min(t["netNTD"],0) for t in trades)) if any(t["netNTD"]<0 for t in trades) else None
    return {"start":str(d.iloc[x[0]].date),"end":str(d.iloc[x[-1]].date),
            "returnPct":round(gain,3),"maxDrawdownPct":round(maxdd,3),
            "trades":len(trades),"winPct":round(wins/len(trades)*100,2) if trades else None,
            "avgNetPerTradePct":round(avgnet,3),"profitFactor":round(pf,3) if pf is not None else None,
            "avgHoldingDays":round(float(np.mean([t["holdingDays"] for t in trades])),2) if trades else None,
            "investedDays":sum(e["held"] for e in equities),"sessions":len(x),
            **({"events":trades,"dailyEquity":equities} if trade_details else {})}

PERIODS={"2024":("2024-01-01","2024-12-31"),"2025":("2025-01-01","2025-12-31"),
         "2026":("2026-01-01","2026-10-08")}
BASE={"id":"RECLAIM_EMA10_twii20_TP0.1_SL0.07_H20","family":"swing_reclaim",
      "length":10,"gate":"twii20","tp":.10,"sl":.07,"hold":20}
BASE_SLIP=.001
def summarize(x):
    return {key:x[key] for key in ("returnPct","maxDrawdownPct","trades","winPct","profitFactor","avgHoldingDays","avgNetPerTradePct","investedDays")}
def run():
    start=time.time()
    _,etf,e1=update_symbol(SYMBOL,datetime(2023,5,1),datetime(2026,10,9))
    _,twii,e2=update_symbol(INDEX,datetime(2023,5,1),datetime(2026,10,9))
    if e1 or e2 or etf is None or twii is None or etf.empty or twii.empty:raise RuntimeError(str((e1,e2)))
    d=data_prepare(etf,twii)
    reference=json.loads((DATA_DIR/"research/etf_00675l_grid_2024_2026/summary.json").read_text(encoding="utf-8"))
    e=next(z for z in reference["validation"] if z["id"]==BASE["id"])
    original={}
    for year,(a,b) in PERIODS.items():
        v=simulate_delay(d,BASE,a,b,trade_details=True)
        exp=e[year]
        if (v["returnPct"],v["maxDrawdownPct"],v["trades"])!=(exp["returnPct"],exp["maxDrawdownPct"],exp["trades"]):
            raise RuntimeError(f"Original runner parity failed {year}: {summarize(v)} vs {exp}")
        original[year]=summarize(v)
    stress={}
    for slip in (.001,.003,.005,.01):
        # Override the copied simulator module global, not the base implementation.
        globals()["SLIP"]=slip
        entry={}
        for year,(a,b) in PERIODS.items():
            entry[year]=summarize(simulate_delay(d,BASE,a,b))
        stress[str(slip)]=entry
        print("ETF_STRESS_SLIPPAGE "+json.dumps({"perSidePct":slip*100,"2026":entry["2026"]}),flush=True)
    globals()["SLIP"]=BASE_SLIP
    delays={}
    for days in (0,1,2):
        z={}
        for year,(a,b) in PERIODS.items():z[year]=summarize(simulate_delay(d,BASE,a,b,entry_delay=days))
        delays[str(days)]=z
        print("ETF_STRESS_ENTRY_DELAY "+json.dumps({"waitAdditionalSessions":days,"2026":z["2026"]}),flush=True)
    neighborhood=[]
    for tp in (.03,.05,.08,.10,.12):
        for sl in (.05,.07,.10):
            for hold in (10,20):
                c=dict(BASE,tp=tp,sl=sl,hold=hold)
                z={"tp":tp,"sl":sl,"hold":hold}
                for year,(a,b) in PERIODS.items():z[year]=summarize(simulate_delay(d,c,a,b))
                neighborhood.append(z)
    near_positive_both=sum(z["2024"]["returnPct"]>0 and z["2025"]["returnPct"]>0 for z in neighborhood)
    near_positive_all=sum(all(z[y]["returnPct"]>0 for y in PERIODS) for z in neighborhood)
    near_dd10=sum(z["2026"]["maxDrawdownPct"]>=-10 and z["2026"]["returnPct"]>0 for z in neighborhood)
    output={"version":"00675L_RECLAIM_EMA10_EXECUTION_ROBUSTNESS_1",
      "generatedAt":datetime.now(ZoneInfo("Asia/Taipei")).isoformat(timespec="seconds"),
      "ticker":SYMBOL,"frozenRule":BASE,"actualDataEnd":str(d.iloc[-1].date),
      "referenceParity":original,
      "slippageStudy":{"perSideFractionsTested":[.001,.003,.005,.01],"stats":stress},
      "executionDelayStudy":{"additionalFullSessions":[0,1,2],"stats":delays},
      "localSensitivity":{"neighborhoodCount":len(neighborhood),
        "positive2024And2025":near_positive_both,"positiveAllThree":near_positive_all,
        "positive2026AndMDDUnder10":near_dd10,"testSlippagePerSidePct":.1,"variants":neighborhood},
      "warnings":["All families previously searched on 2024-25, and 2026 was repeatedly inspected; these are stress tests, not pristine independent validation.",
          "Execution delay replays the signal at the ORIGINAL daily close, but buys 1 or 2 extra sessions later at opening price.",
          "Stock calendar/daily OHLC cannot reproduce 2-minute Bottom/Top execution or order-book price impact.",
          "All-in account, 1M initial capital, integer ETF units. ATR/MA prices are corporate action adjusted by Yahoo.",
          "Comparing 2026 local-neighborhood outcomes and choosing an even better value would cause data snooping."
      ],"elapsedSeconds":round(time.time()-start,1)}
    out=DATA_DIR/"research/etf_00675l_grid_2024_2026"
    (out/"robustness.json").write_text(json.dumps(output,ensure_ascii=False,indent=2),encoding="utf-8")
    print("00675L_ROBUSTNESS_DONE "+json.dumps({"neighborhoods":len(neighborhood),"all3Positive":near_positive_all,
          "cashParity":original["2026"]["returnPct"],"slip50bp":stress["0.005"]["2026"]["returnPct"],
          "oneDayDelay":delays["1"]["2026"]["returnPct"],"seconds":output["elapsedSeconds"]}),flush=True)
if __name__=="__main__":run()
