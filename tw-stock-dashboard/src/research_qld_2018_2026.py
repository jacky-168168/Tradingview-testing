"""QLD 2x daily Nasdaq-100 ETF 2018-2026 independent cash-account backtest.
Source data QLD, QQQ, USD/TWD Yahoo daily corporate action adjusted OHLC.
Primary compare buyhold, QLD's own SMA10/VWMA5; secondary QQQ's SMA10/VWMA5
signals trading QLD to emulate trading 00675L using its underlying market signal.
"""
from __future__ import annotations
import json,time,math
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path
import numpy as np,pandas as pd
from yahoo_cache import update_symbol
from config import DATA_DIR
import research_qqq_vt_2018_2026 as us
import research_00675l_vwma5_sma10_2018_2026 as base
OUT=DATA_DIR/"research/qld_sma10_vwma5_2018_2026"
START=us.START;END=us.END;START_TWD=us.START_TWD
def summary_item(result,dayfx,initial_usd,initial_fx,etf="QLD",id=""):
    d=result["dailyAccountEquity"];usd=result["endNTD"]
    twd=usd*dayfx[d[-1]["date"]]
    t=np.asarray([float(x["equity"])*dayfx[x["date"]] for x in d])
    peaks=np.maximum.accumulate(np.r_[START_TWD,t])[1:]
    dd=round(float(np.min(100*(t/peaks-1))),3)
    years=us.years_from_equity(d,dayfx,initial_usd)
    return {"ticker":etf,"id":id,
       "start":d[0]["date"],"end":d[-1]["date"],"sessions":len(d),
       "initialUSD":round(initial_usd,5),"startUSD_TWD":round(initial_fx,5),"lastUSD_TWD":round(dayfx[d[-1]["date"]],5),
       "endUSD":round(usd,2),"endTWD":round(twd,2),
       "totalReturnUSD":result["returnPct"],"totalReturnTWD":round(100*(twd/START_TWD-1),3),
       "maxDrawdownUSD":result["mddPct"],"maxDrawdownTWD":dd,
       "riskOffSells":result["riskOffSells"],"riskOnReentries":result["riskOnReentries"],
       "daysInCash":result["riskOffSessions"],
       "yearByYearCompounded":years}
def run():
    stamp=time.monotonic()
    raw={}
    for ticker in ("QLD","QQQ","TWD=X"):
        _,x,err=update_symbol(ticker,us.BEGIN_FETCH,us.END_FETCH)
        if err or x is None or x.empty:raise RuntimeError(f"Missing {ticker} history: {err}")
        raw[ticker]=x
        print("QLD_FETCH "+json.dumps({"ticker":ticker,"rows":len(x),"first":str(x.date.iloc[0]),"last":str(x.date.iloc[-1])}),flush=True)
    qld=us.prepare_etf(raw["QLD"],"QLD")
    qqq=us.prepare_etf(raw["QQQ"],"QQQ")
    qld=qld.set_index("date")
    qqq=qqq.set_index("date")
    dates_qld=set(qld.loc[START:END].index)
    dates_qqq=set(qqq.loc[START:END].index)
    if dates_qld!=dates_qqq:raise RuntimeError("QLD and QQQ US session calendars diverge: "+str((sorted(dates_qld-dates_qqq)[:8],sorted(dates_qqq-dates_qld)[:8])))
    qqq=qqq.reindex(qld.index)
    if qqq.loc[START:END,["close","volume"]].isna().any().any():raise RuntimeError("QQQ data missing on QLD dates")
    dates=qld.index.to_numpy(str)
    fx=us.fxseries(raw["TWD=X"],dates)
    dayfx=dict(zip(dates,fx))
    ix=int(np.flatnonzero((dates>=START)&(dates<=END))[0]);fx0=float(fx[ix])
    usd0=START_TWD/fx0;base.CAPITAL=usd0
    qld_close=qld.close.to_numpy(float);qld_vol=qld.volume.to_numpy(float)
    qqq_close=qqq.close.to_numpy(float);qqq_vol=qqq.volume.to_numpy(float)
    open_arr=qld.open.to_numpy(float)
    cases=[
      ("BUY_HOLD_QLD",{"family":"buyhold","riskOffWeight":1.0},qld_close,base.ma_array(qld_close,None,"SMA",10),"QLD"),
      ("QLD_SMA10",base.mkcfg("SMA","twii",10,.02,.01,3),qld_close,base.ma_array(qld_close,None,"SMA",10),"QLD"),
      ("QLD_VWMA5",base.mkcfg("VWMA","twii",5,.02,.01,3),qld_close,base.ma_array(qld_close,qld_vol,"VWMA",5),"QLD"),
      ("QLD_VWMA5_ALT_1_2",base.mkcfg("VWMA","twii",5,.01,.02,3),qld_close,base.ma_array(qld_close,qld_vol,"VWMA",5),"QLD"),
      ("QQQ_SIGNAL_SMA10",base.mkcfg("SMA","twii",10,.02,.01,3),qqq_close,base.ma_array(qqq_close,None,"SMA",10),"QQQ"),
      ("QQQ_SIGNAL_VWMA5",base.mkcfg("VWMA","twii",5,.02,.01,3),qqq_close,base.ma_array(qqq_close,qqq_vol,"VWMA",5),"QQQ")
    ]
    outcome=[];trace={}
    for id,rule,source,ma,srcname in cases:
        arrays={"open":open_arr,"close":qld_close,"twii":source}
        r=base.backtest(arrays,dates,rule,ma,START,END,True)
        x=summary_item(r,dayfx,usd0,fx0,id=id)
        x["signalTicker"]=srcname
        x["nInvalidVWMA"]=int(sum(not np.isfinite(ma[i-1]) for i in np.flatnonzero((dates>=START)&(dates<=END))[1:])) if "VWMA" in id else 0
        outcome.append(x)
        trace[id]={"dailyEquityUSD":r["dailyAccountEquity"],"ordersUSD":r["orders"]}
        print("QLD_2018_2026_RESULT "+json.dumps({"id":id,"returnUSD":x["totalReturnUSD"],"returnTWD":x["totalReturnTWD"],"endTWD":x["endTWD"],"mddTWD":x["maxDrawdownTWD"],"sells":x["riskOffSells"],"cashDays":x["daysInCash"]}),flush=True)
    anchor={v["id"]:v for v in outcome}
    # Compare two independent symbols' results, same exact 2018–26 trading horizon.
    prior=DATA_DIR/"research/qqq_vt_sma10_vwma5_2018_2026/summary.json"
    other=None
    if prior.exists():
        old=json.loads(prior.read_text())
        same_dates=all(z["entryDate"]=="2018-01-02" and z["lastDate"]==END for z in old["results"])
        assert same_dates,"Old QQQ and VT must share comparison dates"
        other={"previousResearchVersion":old["version"],"results":[{k:y[k] for k in ("ticker","strategy","netReturnTWD","finalTWD","maxDDTWD")} for y in old["results"]]}
    sample=next(v for v in outcome if v["id"]=="BUY_HOLD_QLD")
    assert sample["start"]=="2018-01-02" and sample["end"]=="2026-10-07"
    assert all(v["sessions"]==sample["sessions"] for v in outcome)
    assert len(sample["yearByYearCompounded"])==9
    assert all((x["riskOffSells"]==x["riskOnReentries"] for x in outcome))
    report={"version":"QLD_2018_2026_USD_TWD_ALL_CASH_SMA_VWMA_V1",
       "createdAt":datetime.now(ZoneInfo("Asia/Taipei")).isoformat(timespec="seconds"),
       "period":["2018-01-02","2026-10-07"],"USSessions":sample["sessions"],
       "ticker":"QLD","underlying":"Nasdaq-100 daily 2x; not the 1x QQQ fund",
       "startingCapitalTWD":START_TWD,
       "conversion":{"firstFX":fx0,"lastFX":float(fx[-1]),"firstUSD":usd0,
          "USD_to_TWD_source":"Yahoo TWD=X, spot FX backward as-of to US ETF calendar",
          "tradingCash":"USD stays in USD between trades, no conversion during rotation"},
       "executionModel":{"signal":"Only prior completed daily close; trade next US session open",
         "fill":"adjusted OHLC, shares integer, buy full free USD cash, sell all shares on signal",
         "brokerFeeEachSidePct":us.FEE*100,"slippageEachSidePct":us.SLIPPAGE*100,
         "US_ETF_SellTaxPct":us.US_SELL_ETF_TAX*100,"idleCashInterest":0,
         "dividends":"Yahoo adjusted OHLC total return proxy, with dividends reinvested notionally",
         "excluded":"US dividend withholding tax, broker conversion spread, international transfer fees and taxes not explicitly modeled"},
       "priceData":{"adjustmentFactorMin_QLD":float(qld.adj_factor.min()),
         "adjustmentFactorMax_QLD":float(qld.adj_factor.max()),
         "adjustmentFactorMin_QQQ":float(qqq.adj_factor.min()),
         "adjustmentFactorMax_QQQ":float(qqq.adj_factor.max()),
         "QLDPositiveVolumeDaysPct":float((qld.loc[START:END,"volume"]>0).mean()*100),
         "QQQPositiveVolumeDaysPct":float((qqq.loc[START:END,"volume"]>0).mean()*100)},
       "strategies":outcome,"previousQQQVT":other,
       "warnings":["QLD is Nasdaq-100 daily +2x ETF; daily reset causes path dependence and potential extremely large drawdowns.",
        "All statistics are historical and 2026 was viewed in earlier studies; they do not estimate forward returns.",
        "Own-price QLD SMA10 and QQQ-proxy SMA10 use different signals, so compare explicitly and do not mix with ^NDX exact index.",
        "Real-world dividend-withholding tax and cross-border/currency conversion charges could materially reduce returns.",
        "Adjusted close reconstructed OHLC plus raw ETF volume is an approximation; volume remains in share units.",
        "If US market dates differ between QQQ and QLD the script must fail instead of forward-fill proxy trade signals.",
        "Accumulated profit entirely reinvested and no external contributions; figures are hindsight model results, not financial advice."],
       "executionSeconds":round(time.monotonic()-stamp,1)}
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/"summary.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    (OUT/"daily_equity_and_orders.json").write_text(json.dumps({"version":report["version"],"simulations":trace},ensure_ascii=False),encoding="utf-8")
    print("QLD_FINAL_SUMMARY "+json.dumps({"period":report["period"],"nSessions":sample["sessions"],"models":len(outcome),
       "allInEndTWD":[{"name":z["id"],"twd":z["endTWD"],"returnPct":z["totalReturnTWD"]} for z in outcome],
       "seconds":report["executionSeconds"]},ensure_ascii=False),flush=True)
if __name__=="__main__":run()
