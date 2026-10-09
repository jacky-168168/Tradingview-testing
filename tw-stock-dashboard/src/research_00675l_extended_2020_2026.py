"""Out-of-period robustness of PREVIOUSLY FROZEN 00675L trend-rotation rules, 2020-2026.
NO strategy parameters are chosen by the newly retrieved 2020-2023 sample.
Each daily close is observed before the following session's OPEN execution.
"""
from __future__ import annotations
import json,math,time
from datetime import datetime
from zoneinfo import ZoneInfo
from collections import defaultdict
import numpy as np,pandas as pd
from research_00675l_near_hold_switch import prepare,indicators,bt,OUTPUT,universe
from research_00675l_near_hold_stress import bt_lag
from research_00675l_reinvestment import simulate_sizing,BASE_RULE
from research_00675l_swing_grid import update_symbol,data_prepare,SYMBOL,INDEX,CAPITAL,BROKER,ETF_SELL_TAX,SLIP,DATA_DIR
import research_00675l_near_hold_switch as prior
import research_00675l_near_hold_stress as delay_runner
PERIOD_START="2020-01-01";PERIOD_END="2026-10-07"
FROZEN_IDS=[
 "BUY_HOLD",
 "CRASH_3_0.1_RE10_Gtwii_below60_W0.0",
 "MA_twii_20_O0.03_R0.0_C1_W0.0",
 "TRAIL_20_0.16_RE10_W0.0",
 "CRASH_3_0.1_RE10_Gall_W0.0",
 "DUAL_twii_120_20_RE10_W0.5",
 "MA_twii_10_O0.02_R0.01_C3_W0.0",
 "MA_close_10_O0.04_R0.02_C3_W0.0"
]
OUT=DATA_DIR/"research/etf_00675l_extended_2020_2026"
WINDOWS={"2020_2023":("2020-01-01","2023-12-31"),
         "2024_2025":("2024-01-01","2025-12-31"),
         "2024_2026":("2024-01-01",PERIOD_END),
         "2026":("2026-01-01",PERIOD_END)}
def lite(res):
    return {k:res[k] for k in ("start","end","returnPct","endNTD","mddPct",
        "riskOffSells","riskOnReentries","riskOffSessions","investedSessions","sessions","switchEvents")}
def yearly_from_equity(rows):
    years=sorted(set(z["date"][:4] for z in rows))
    start=float(CAPITAL);out={}
    for year in years:
        r=next(z for z in reversed(rows) if z["date"].startswith(year))
        last=float(r["equity"])
        out[year]={"beginNTD":round(start,2),"endNTD":round(last,2),
                   "calendarGainNTD":round(last-start,2),
                   "calendarReturnPct":round(100*(last/start-1),3),
                   "endDate":r["date"]}
        start=last
    return out
def drawdown_segments(rows):
    out={}
    for yr in sorted(set(z["date"][:4] for z in rows)):
        points=[z for z in rows if z["date"].startswith(yr)]
        prices=np.array([z["equity"] for z in points],dtype=float)
        first=prices[0]
        tops=np.maximum.accumulate(np.r_[first,prices])[1:]
        out[yr]={"yearMaxDDPct":round(float(np.min(100*(prices/tops-1))),3),
                 "lastDate":points[-1]["date"],"sessions":len(points)}
    return out
def assert_no_lookahead_orders(events,dates):
    days=set(dates)
    assert all(z["date"] in days for z in events)
    assert all(events[i]["date"]<=events[i+1]["date"] for i in range(len(events)-1))
def run():
    begin=time.monotonic()
    # Entire 2019 price history is fetched to fully warm-up EMA200 before Jan 2020.
    _,etf,e=update_symbol(SYMBOL,datetime(2019,1,1),datetime(2026,10,8))
    _,twii,e2=update_symbol(INDEX,datetime(2019,1,1),datetime(2026,10,8))
    if e or e2 or etf is None or twii is None or etf.empty or twii.empty:raise RuntimeError(str({"etf":e,"index":e2}))
    d=data_prepare(etf,twii)
    d=d[d.date<=PERIOD_END].reset_index(drop=True)
    d=prepare(d)
    a,dates=indicators(d)
    win=dates[(dates>=PERIOD_START)&(dates<=PERIOD_END)]
    if win.size<1600:raise RuntimeError("2020-2026 insufficient sessions "+str(win.size))
    if dates[0]>"2019-05-01":raise RuntimeError("Missing 2019 long EMA prewarming: first "+dates[0])
    for y in range(2020,2027):
        n=sum((dates>=f"{y}-01-01")&(dates<=f"{y}-12-31"))
        if n<140 and y<2026:raise RuntimeError(f"year {y} incomplete {n}")
    original=json.loads((OUTPUT/"summary.json").read_text(encoding="utf-8"))
    known={z["id"]:z["params"] for z in original["frozenComparisons"]}
    other={v["id"]:v for v in universe()}
    # Two MA10 rules were frozen in the OTHER independent trend-capture project,
    # whose recovery gate requires source close > MA10*(1+buffer/2).
    for c in [
      {"id":"MA_twii_10_O0.02_R0.01_C3_W0.0","family":"ma_hysteresis",
       "src":"twii","n":10,"out":.02,"rein":.01,"confirm":3,"riskOffWeight":0},
      {"id":"MA_close_10_O0.04_R0.02_C3_W0.0","family":"ma_hysteresis",
       "src":"close","n":10,"out":.04,"rein":.02,"confirm":3,"riskOffWeight":0}]:
        other[c["id"]]=c
    rules=[]
    for key in FROZEN_IDS:
        if key=="BUY_HOLD":rules.append(other[key])
        elif key in known:rules.append(known[key])
        elif key in other:rules.append(other[key])
        else:raise RuntimeError("Frozen strategy parameter not found "+key)
    reports=[];traces={}
    for conf in rules:
        name=conf["id"]
        entire=bt(a,dates,conf,PERIOD_START,PERIOD_END,detailed=True)
        assert_no_lookahead_orders(entire["orders"],win)
        sub={p:lite(bt(a,dates,conf,start,end)) for p,(start,end) in WINDOWS.items()}
        y=yearly_from_equity(entire["equity"])
        dd=drawdown_segments(entire["equity"])
        rep={"id":name,"family":conf["family"],"parametersFrozen":conf,
            "continuous":lite(entire),"compoundedCalendarYears":y,
            "annualMaxDrawdownWithinYear":dd,
            "independentWindowRuns":sub,
            "firstBuyDate":entire["orders"][0]["date"],
            "lastTradeDate":entire["orders"][-1]["date"],
            "totalOrderEvents":len(entire["orders"]),
            "signalExitDates":[t["date"] for t in entire["orders"] if t.get("phase")=="risk_off"],
            "rebuyDates":[t["date"] for t in entire["orders"] if t.get("phase")=="risk_on"][1:]}
        reports.append(rep)
        traces[name]={"dailyAccountEquity":entire["equity"],"transactions":entire["orders"]}
        print("EXTENDED_2020_CASE "+json.dumps({"id":name,"returnPct":rep["continuous"]["returnPct"],
            "endNTD":rep["continuous"]["endNTD"],"maxDD":rep["continuous"]["mddPct"],
            "2020_pct":y["2020"]["calendarReturnPct"],"2022_pct":y["2022"]["calendarReturnPct"],
            "2026_pct":y["2026"]["calendarReturnPct"],"exits":rep["continuous"]["riskOffSells"]},ensure_ascii=False),flush=True)
    baseline=next(z for z in reports if z["id"]=="BUY_HOLD")
    for z in reports:
        bh=baseline["continuous"];r=z["continuous"]
        z["vsHold"]={"endingNTDExcess":round(r["endNTD"]-bh["endNTD"],2),
                     "cumulativeReturnPctPointsExcess":round(r["returnPct"]-bh["returnPct"],3),
                     "maxDrawdownPctPointsImprovement":round(abs(bh["mddPct"])-abs(r["mddPct"]),3),
                     "profitCaptureRelativeToHoldPct":round((r["endNTD"]-CAPITAL)/(bh["endNTD"]-CAPITAL)*100,2) if bh["endNTD"]!=CAPITAL else None}
    # Original 2024+ data must still match even after fetching more 2019 indicator warm-up.
    matched=[]
    for key in FROZEN_IDS:
        if key not in known:continue
        old=next(v for v in original["frozenComparisons"] if v["id"]==key)["continuous"]
        now=next(v for v in reports if v["id"]==key)["independentWindowRuns"]["2024_2026"]
        matched.append({"id":key,"oldReturnPct":old["returnPct"],"newReturnPct":now["returnPct"],
                        "returnDifferencePctPoints":round(now["returnPct"]-old["returnPct"],3),
                        "sameRoundTripCount":now["riskOffSells"]==old["riskOffSells"]})
    # Fixed original EMA10 strategy also evaluated, using same 100% cash reinvest method.
    ema_cont=simulate_sizing(d,BASE_RULE,PERIOD_START,PERIOD_END,True,1)
    emacase={"id":"EMA10_TWII20_TP10_SL7","family":"prior_ema10_swing","parametersFrozen":BASE_RULE,
        "continuous":{"returnPct":ema_cont["returnPct"],"endNTD":round(ema_cont["dailyEquity"][-1]["equity"],2),
                       "mddPct":ema_cont["maxDrawdownPct"],"trades":ema_cont["trades"],
                       "sessions":ema_cont["sessions"]},
        "compoundedCalendarYears":yearly_from_equity(ema_cont["dailyEquity"])}
    emacase["vsHold"]={"endingNTDExcess":round(emacase["continuous"]["endNTD"]-baseline["continuous"]["endNTD"],2),
        "cumulativeReturnPctPointsExcess":round(emacase["continuous"]["returnPct"]-baseline["continuous"]["returnPct"],3)}
    traces[emacase["id"]]={"dailyAccountEquity":ema_cont["dailyEquity"],"transactions":ema_cont["events"]}
    print("EXTENDED_2020_EMA10 "+json.dumps({"returnPct":ema_cont["returnPct"],"endNTD":ema_cont["dailyEquity"][-1]["equity"],
          "maxDD":ema_cont["maxDrawdownPct"],"trades":ema_cont["trades"]},ensure_ascii=False),flush=True)
    # Out-of-period 2020-23 comparison is descriptive ONLY. No new parameter search.
    # Include only previously frozen 3 primary strategies in execution robustness stress.
    watch=["CRASH_3_0.1_RE10_Gtwii_below60_W0.0","MA_twii_20_O0.03_R0.0_C1_W0.0","TRAIL_20_0.16_RE10_W0.0"]
    byid={c["id"]:c for c in rules}
    stress={}
    for slip in (.001,.003,.005,.01):
        prior.SLIP=slip
        delay_runner.SLIP=slip
        stress[str(slip)]={}
        for key in watch+["BUY_HOLD"]:
            case=bt(a,dates,byid[key],PERIOD_START,PERIOD_END)
            stress[str(slip)][key]=lite(case)
        print("EXTENDED_SLIPPAGE "+json.dumps({"slippageEachSidePct":slip*100,
           "crash":stress[str(slip)][watch[0]]["returnPct"],"ma":stress[str(slip)][watch[1]]["returnPct"],
           "hold":stress[str(slip)]["BUY_HOLD"]["returnPct"]}),flush=True)
    prior.SLIP=.001
    delay_runner.SLIP=.001
    lag={}
    for n in (0,1,2):
        lag[str(n)]={}
        for key in watch:
            x=bt_lag(a,dates,byid[key],PERIOD_START,PERIOD_END,lag=n)
            lag[str(n)][key]=lite(x)
        print("EXTENDED_EXECUTION_LAG "+json.dumps({"delaySessions":n,
           "crash":lag[str(n)][watch[0]]["returnPct"],"ma":lag[str(n)][watch[1]]["returnPct"]}),flush=True)
    for key in watch:
        ref=next(v for v in reports if v["id"]==key)["continuous"]["returnPct"]
        assert lag["0"][key]["returnPct"]==ref,(key,lag["0"][key],ref)
    def scalar(z):return {k:z[k] for k in ("id","continuous","compoundedCalendarYears","vsHold")}
    complete={"version":"00675L_FROZEN_EXTENDED_2020_2026_V1",
        "generatedAt":datetime.now(ZoneInfo("Asia/Taipei")).isoformat(timespec="seconds"),
        "ticker":SYMBOL,"security":"富邦臺灣加權正2","requestedPeriod":"2020-01-01 through 2026-10-07",
        "actualLastTradingDate":win[-1],"prewarmFirstDate":dates[0],
        "researchPolicy":"All 8 exit and buyback rules frozen BEFORE 2020-2023 data retrieved. No 2020-2023 parameter optimization.",
        "model":{"initialCapitalNTD":CAPITAL,"position":"100% cash all-in in risk-on regime; full cash no debt; reinvest cumulative profit; 0% or 50% ETF when rule says risk off",
            "brokerEachSidePct":BROKER*100,"sellTaxPct":ETF_SELL_TAX*100,"slippagePerSidePct":SLIP*100,
            "decision":"Use only previous daily close and indicator; execute next trading-day open; no intraday perfect lows/highs.",
            "priceSource":"Yahoo Finance 00675L.TW + ^TWII adjusted daily OHLC with 2019 EMA warmup"},
        "sessions":int(win.size),"dateSplits":["2020-2023","2024-2025","2026-10-07"],
        "baseline":scalar(baseline),
        "comparison":[scalar(z) for z in reports if z["id"]!="BUY_HOLD"]+[scalar(emacase)],
        "original2024to2026Consistency":matched,
        "fullDetailsByModel":{z["id"]:{k:z[k] for k in ("id","family","parametersFrozen","continuous","compoundedCalendarYears","annualMaxDrawdownWithinYear","independentWindowRuns","firstBuyDate","lastTradeDate","totalOrderEvents","signalExitDates","rebuyDates","vsHold")} for z in reports},
        "stress":{"slippageEachSide":stress,"additionalDecisionSessionLag":lag},
        "warnings":["A successful 2020-2023 retrospective is not a guarantee of future real-money performance.",
          "Parameters chosen based on previously observed 2024-2026 market may still have selection bias.",
          "2020 COVID and 2022 bear are valuable additional regimes but were only checked after the prior parameter freeze.",
          "Do not sum independently reset calendar-year backtest results: use the year-by-year equity progression from continuous run.",
          "00675L daily-reset leveraged ETF experiences leverage decay and extreme drawdowns.",
          "Indicators on adjusted Yahoo OHLC are not actual executable broker fills, and events rely on available adjusted-history consistency.",
          "Same-day opening gaps and close-only signals can incur major losses before a protective risk-off order executes.",
          "No borrowing, intraday bottom/top 2-minute data, dividend cash reinvestment confirmation or share-lot sizing / liquidity constraints; whole ETF shares only."],
        "elapsedSeconds":round(time.monotonic()-begin,1)}
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/"summary.json").write_text(json.dumps(complete,ensure_ascii=False,indent=2),encoding="utf-8")
    (OUT/"daily_equity_orders.json").write_text(json.dumps({"version":complete["version"],"cases":traces},ensure_ascii=False),encoding="utf-8")
    print("EXTENDED_2020_2026_COMPLETE "+json.dumps({"ending":win[-1],"sessions":len(win),
       "hold":baseline["continuous"]["returnPct"],"crash":next(z for z in reports if z["id"]==watch[0])["continuous"]["returnPct"],
       "ma":next(z for z in reports if z["id"]==watch[1])["continuous"]["returnPct"],
       "elapsed":complete["elapsedSeconds"]},ensure_ascii=False),flush=True)
if __name__=="__main__":run()
