"""00675L full cash reinvestment versus original NT$1m capped orders.
2024-25 historical development and 2026 audit; same frozen daily EMA10 strategy.
100% reinvest replicates the previous simulator exactly, checked per year.
"""
from __future__ import annotations
import json,math,time
from datetime import datetime
from zoneinfo import ZoneInfo
import numpy as np,pandas as pd
from research_00675l_swing_grid import *
from research_00675l_swing_grid import data_prepare,signal
def simulate_sizing(d,c,begin,end,trade_details=False,reinvest_fraction=1.0):
    if not 0<=reinvest_fraction<=1:raise ValueError('reinvest_fraction must be from 0 to 1')
    x=d.index[d.date.between(begin,end)].tolist()
    if len(x)<20:raise RuntimeError("Insufficient dates "+begin+" .. "+end)
    cash=float(CAPITAL);qty=0;entry_px=0;entry_cost=0;entry_at=-1;peakclose=0;equities=[];trades=[]
    # exit_signal for last closed day, not contemporary close. A single position at any time.
    for kk,i in enumerate(x):
        bar=d.iloc[i];date=bar.date
        o,h,l,close=(float(bar[z]) for z in ("open","high","low","close"))
        p=d.iloc[i-1] if i>=1 else None;q=d.iloc[i-2] if i>=2 else None
        buy_sig,sell_sig=signal(p,q,c) if p is not None and q is not None else (False,False)
        if c["family"]=="buy_hold":buy_sig=kk==0;sell_sig=False
        closed_today=False;opened_today=False
        def sell(gross_px,reason):
            nonlocal qty,cash,entry_px,entry_cost,entry_at,peakclose,closed_today
            px=max(0.01,gross_px*(1-SLIP));proceeds=qty*px*(1-BROKER-ETF_SELL_TAX)
            cash+=proceeds
            net=100*(proceeds/entry_cost-1)
            trades.append({"buyDate":str(d.iloc[entry_at].date),"sellDate":date,"buyPx":round(entry_px,3),
                  "sellPx":round(px,3),"holdingDays":i-entry_at+1,"reason":reason,
                  "netPct":round(net,3),"netNTD":round(proceeds-entry_cost,2),
                  "positionCostNTD":round(entry_cost,2),"cashAfterExitNTD":round(cash,2)})
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
            # Initial NT$1m is the fixed per-trade cap. Only an explicitly allowed
            # fraction of accumulated *net* profits can increase the next position.
            # Losses reduce available capital; no borrowing or external deposits.
            purchase_budget=min(cash,CAPITAL+reinvest_fraction*max(cash-CAPITAL,0.0))
            number=math.floor(purchase_budget/(paid_px*(1+BROKER)))
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

BASE_RULE={"id":"RECLAIM_EMA10_twii20_TP0.1_SL0.07_H20","family":"swing_reclaim",
 "length":10,"gate":"twii20","tp":.10,"sl":.07,"hold":20}
SIZINGS={"fixed_100m":0.0,"half_profit_reinvest":0.5,"all_profit_reinvest":1.0}
WINDOWS={"2024":("2024-01-01","2024-12-31"),"2025":("2025-01-01","2025-12-31"),
         "2026":("2026-01-01","2026-10-08"),
         "continuous_2024_2026":("2024-01-01","2026-10-08")}
OUT=DATA_DIR/"research/etf_00675l_grid_2024_2026"
def compact(v):
    return {k:v[k] for k in ("start","end","returnPct","maxDrawdownPct","trades","winPct",
        "avgNetPerTradePct","profitFactor","avgHoldingDays","investedDays","sessions")}
def years_from_continuous(curve):
    yearly={}
    last=CAPITAL
    for y in ("2024","2025","2026"):
        seg=[x for x in curve if x["date"].startswith(y)]
        if not seg:continue
        equity=float(seg[-1]["equity"])
        yearly[y]={"startCapitalNTD":round(last,2),"endCapitalNTD":round(equity,2),
                   "netGainNTD":round(equity-last,2),"yearReturnPct":round((equity/last-1)*100,3),
                   "lastDate":seg[-1]["date"]}
        last=equity
    return yearly
def run():
    start=time.time()
    _,etf,e1=update_symbol(SYMBOL,datetime(2023,5,1),datetime(2026,10,9))
    _,idx,e2=update_symbol(INDEX,datetime(2023,5,1),datetime(2026,10,9))
    if e1 or e2 or etf is None or idx is None or etf.empty or idx.empty:raise RuntimeError(str({"00675L":e1,"index":e2}))
    d=data_prepare(etf,idx)
    frozen=json.loads((OUT/"summary.json").read_text(encoding="utf-8"))
    previously=next(z for z in frozen["validation"] if z["id"]==BASE_RULE["id"])
    variants={};trades={}
    for name,fraction in SIZINGS.items():
        cases={};trades[name]={}
        for period,(a,b) in WINDOWS.items():
            x=simulate_sizing(d,BASE_RULE,a,b,trade_details=True,reinvest_fraction=fraction)
            item=compact(x)
            item["endingEquityNTD"]=round(x["dailyEquity"][-1]["equity"],2)
            item["totalRealizedProfitNTD"]=round(sum(t["netNTD"] for t in x["events"]),2)
            item["maxSingleTradeCostNTD"]=round(max((z["positionCostNTD"] for z in x["events"]),default=0),2)
            item["yearlyReturns"]=years_from_continuous(x["dailyEquity"]) if period.startswith("continuous") else None
            cases[period]=item
            trades[name][period]={"events":x["events"],"dailyEquity":x["dailyEquity"]}
            if name=="all_profit_reinvest" and period in ("2024","2025","2026"):
                old=previously[period]
                for key in ("returnPct","maxDrawdownPct","trades"):
                    if item[key]!=old[key]:raise RuntimeError(f"Old full-reinvest parity mismatch {period}/{key}: {item[key]} vs {old[key]}")
            print("00675L_SIZING_CASE "+json.dumps({"variant":name,"period":period,
                "endingEquityNTD":item["endingEquityNTD"],"totalReturnPct":item["returnPct"],
                "maxDrawdownPct":item["maxDrawdownPct"],"maxInvestedNTD":item["maxSingleTradeCostNTD"],
                "trades":item["trades"]},ensure_ascii=False),flush=True)
        variants[name]={"fractionOfAccumulatedProfitsReinvested":fraction,"byPeriod":cases}
    fixed=variants["fixed_100m"]["byPeriod"]["2026"]
    compound=variants["all_profit_reinvest"]["byPeriod"]["2026"]
    continuous_fixed=variants["fixed_100m"]["byPeriod"]["continuous_2024_2026"]
    continuous_compound=variants["all_profit_reinvest"]["byPeriod"]["continuous_2024_2026"]
    output={"version":"00675L_PROFIT_REINVESTMENT_2024_2026_V1",
      "generatedAt":datetime.now(ZoneInfo("Asia/Taipei")).isoformat(timespec="seconds"),
      "ticker":SYMBOL,"security":"富邦臺灣加權正2",
      "startingCapitalNTD":CAPITAL,"frozenStrategy":BASE_RULE,
      "dataEnd":str(d.iloc[-1].date),"executableDates":{"train":"2024-2025","test":"2026-01-01 to 2026-10-08","continuation":"2024-01-01 to 2026-10-08"},
      "capitalAllocation":{"fixed_100m":"Each new trade invests up to original NT$1,000,000; net gains retained as idle account cash. After losses, invests only available cash. No margin.",
          "half_profit_reinvest":"Each trade invests up to NT$1,000,000 plus 50% of total account equity already above original NT$1,000,000.",
          "all_profit_reinvest":"Each trade invests all available cash including cumulative net gains; losses reduce next position size. This is the SAME as previous 00675L study.",
          "firstTrade":"All modes initially invest as much of original NT$1,000,000 as integer ETF units and fee budget allow.",
          "idleCash":"Idle profits remain counted in total account equity, no bank interest; 100% full reinvest has no intentional cash reserve.",
          "wholeShares":True,"oneOpenETFPosition":True,"noBorrowing":True},
      "tradeRules":{"entry":"Price closes above EMA10 after previous close at or below EMA10, TWII index last closed above MA20; buy next opening",
          "exit":"Gross TP +10% or SL -7%; indicator exit next opening; max 20 trading days",
          "fees":{"perSideBrokerPct":BROKER*100,"sellETFTaxPct":ETF_SELL_TAX*100,"perSideSlippagePct":SLIP*100},
          "noSameDayPositiveTarget":True},
      "comparison":variants,
      "keyDeltas":{"2026_fullMinusFixedReturnPercentagePoints":round(compound["returnPct"]-fixed["returnPct"],3),
                   "2026_fullMinusFixedEndingEquityNTD":round(compound["endingEquityNTD"]-fixed["endingEquityNTD"],2),
                   "continuous_fullMinusFixedReturnPercentagePoints":round(continuous_compound["returnPct"]-continuous_fixed["returnPct"],3),
                   "continuous_fullMinusFixedEndingEquityNTD":round(continuous_compound["endingEquityNTD"]-continuous_fixed["endingEquityNTD"],2)},
      "warnings":["The original +66.445% 2026 ETF result already used 100% full-cash profit reinvestment.",
          "All sizing comparisons use exactly the SAME fixed entry/exit rule chosen earlier, not reoptimized after checking 2026.",
          "2024-2026 continuous means PROFITS and LOSSES carry through year boundaries; isolated yearly 2024, 2025, 2026 runs each independently START with NT$1,000,000.",
          "Market daily OHLC and adjusted pricing cannot verify real intraday fill or 2-minute Bottom/Top alerts.",
          "Compounding raises exposure after gains and reduces it after losses; performance is path dependent and this ETF resets its benchmark leverage daily.",
          "ETF order-book slippage can exceed 0.1% each side. No margin, minimum broker charge, or intraday liquidity impact modeled.",
          "Original model research has repeatedly examined 2026 so do not treat these historical results as untouched out-of-sample proof.",
          "Annualized figures should NOT be inferred by summing independent yearly backtests."],
      "elapsedSeconds":round(time.time()-start,1)}
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/"reinvestment_summary.json").write_text(json.dumps(output,ensure_ascii=False,indent=2),encoding="utf-8")
    (OUT/"reinvestment_trades_equity.json").write_text(json.dumps({"version":output["version"],"tradesAndEquity":trades},ensure_ascii=False),encoding="utf-8")
    print("00675L_REINVESTMENT_DONE "+json.dumps({"2026_fixedReturnPct":fixed["returnPct"],
        "2026_halfReturnPct":variants["half_profit_reinvest"]["byPeriod"]["2026"]["returnPct"],
        "2026_compoundReturnPct":compound["returnPct"],
        "continuous_fixedEndingNTD":continuous_fixed["endingEquityNTD"],
        "continuous_compoundEndingNTD":continuous_compound["endingEquityNTD"],
        "elapsed":output["elapsedSeconds"]},ensure_ascii=False),flush=True)
if __name__=="__main__":run()
