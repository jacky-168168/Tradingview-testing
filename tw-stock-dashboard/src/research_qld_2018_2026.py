"""2018-2026 QLD Nasdaq-100 daily +2x ETF, held and rotated with SMA10/VWMA5.
2017 warmup; NTD 1 million converted to USD once; profits 100% compounded.
Duplicate earlier verified US ETF backtest to preserve trade-cost and fill assumptions.
QLD self-signals (SMA/VWMA), Nasdaq-100 index SMA, QQQ ETF proxy SMA/VWMA.
"""
from __future__ import annotations
import json,math,time
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path
import pandas as pd,numpy as np
from yahoo_cache import update_symbol
from config import DATA_DIR
import research_qqq_vt_2018_2026 as us
import research_00675l_vwma5_sma10_2018_2026 as engine
OUT=DATA_DIR/"research/qld_sma_vwma_2018_2026"
START="2018-01-01";END="2026-10-07"
def market(symbol):
    _,raw,e=update_symbol(symbol,datetime(2017,1,1),datetime(2026,10,8))
    if e or raw is None or raw.empty:raise RuntimeError("Missing history "+symbol+" "+str(e))
    print("QLD_PRICE_FETCH "+json.dumps({"ticker":symbol,"rows":len(raw),"first":str(raw.date.iloc[0]),"last":str(raw.date.iloc[-1])}),flush=True)
    return raw
def aligned(df,dates,key):
    p=df[["date",key]].copy();p.date=p.date.astype(str)
    p[key]=pd.to_numeric(p[key],errors="coerce")
    return p.drop_duplicates("date",keep="last").set_index("date").reindex(list(dates))[key].to_numpy(float)
def extra_model(name,signal,signal_close,ma,a,dates,fx,cash,fxstart,config):
    # Signal close independent of QLD trade price; execution ALWAYS QLD open.
    signal_arr={**a,"twii":signal_close}
    raw=engine.backtest(signal_arr,dates,config,ma,START,END,True)
    eq=raw["dailyAccountEquity"];orders=raw["orders"]
    spot=dict(zip(dates,fx))
    usd_end=float(raw["endNTD"]);twd_end=usd_end*spot[END]
    daily=np.asarray([q["equity"]*spot[q["date"]] for q in eq])
    peaks=np.maximum.accumulate(np.r_[1e6,daily])[1:]
    result={"ticker":"QLD","strategy":name,"signalSource":signal,
        "entryDate":eq[0]["date"],"lastDate":eq[-1]["date"],"sessions":len(eq),
        "initialTWD":1_000_000,"initialUSD":round(cash,4),
        "finalUSD":round(usd_end,2),"finalTWD":round(twd_end,2),
        "netReturnUSD":raw["returnPct"],"netReturnTWD":round(100*(twd_end/1e6-1),3),
        "maxDDUSD":raw["mddPct"],"maxDDTWD":round(float(np.min(100*(daily/peaks-1))),3),
        "riskOffSells":raw["riskOffSells"],"riskOnReentries":raw["riskOnReentries"],
        "riskOffSessions":raw["riskOffSessions"],"nOrders":len(orders),
        "blockedSignalDays":int(sum(not np.isfinite(ma[i-1]) or not np.isfinite(signal_close[i-1])
           for i in np.flatnonzero((dates>=START)&(dates<=END))[1:])),
        "yearlyContinuous":us.years_from_equity(eq,spot,cash)}
    print("QLD_INDEX_SIGNAL "+json.dumps({"name":name,"source":signal,"USDpercent":result["netReturnUSD"],
       "TWDpercent":result["netReturnTWD"],"endTWD":result["finalTWD"],"DD":result["maxDDTWD"],"exits":result["riskOffSells"]}),flush=True)
    return result,{"equityUSD":eq,"ordersUSD":orders}
def run():
    began=time.monotonic()
    raw={t:market(t) for t in ("QLD","QQQ","^NDX","TWD=X")}
    qld=us.prepare_etf(raw["QLD"],"QLD");qqq=us.prepare_etf(raw["QQQ"],"QQQ")
    dates=qld.date.to_numpy(str)
    qdates=qqq.date.to_numpy(str)
    assert np.array_equal(dates[(dates>=START)&(dates<=END)],qdates[(qdates>=START)&(qdates<=END)]),"QLD/QQQ calendar mismatch"
    fx=us.fxseries(raw["TWD=X"],dates)
    first=int(np.flatnonzero((dates>=START)&(dates<=END))[0])
    fxstart=float(fx[first]);cash=1_000_000/fxstart
    # SAME broker+slip and 0% US ETF transaction tax as old QQQ/VT.
    results,traces,quality=us.test("QLD",qld,qld.volume.to_numpy(float),fx,cash,fxstart)
    results_ref,_,quality_ref=us.test("QQQ",qqq,qqq.volume.to_numpy(float),fx,cash,fxstart)
    refby={r["strategy"]:r for r in results_ref}
    assert refby["BUY_HOLD"]["netReturnTWD"]==444.202
    assert refby["SMA10_2out_1in_c3"]["netReturnUSD"]==230.283
    assert refby["VWMA5_2out_1in_c3"]["netReturnUSD"]==265.786
    # Reset capital explicitly after QQQ replica; same 1mTWD starting USD.
    engine.CAPITAL=cash;engine.BROKER=.001425;engine.SLIP=.001;engine.ETF_SELL_TAX=0.
    a={"open":qld.open.to_numpy(float),"close":qld.close.to_numpy(float),
       "twii":qld.close.to_numpy(float)}
    ndx_close=aligned(raw["^NDX"],dates,"close")
    qqq_close=aligned(qqq,dates,"close")
    qqq_volume=aligned(qqq,dates,"volume")
    configs=[
      ("QLD_NDX_SMA10","^NDX",ndx_close,engine.ma_array(ndx_close,None,"SMA",10),engine.mkcfg("SMA","twii",10,.02,.01,3)),
      ("QLD_QQQ_SMA10","QQQ",qqq_close,engine.ma_array(qqq_close,None,"SMA",10),engine.mkcfg("SMA","twii",10,.02,.01,3)),
      ("QLD_QQQ_VWMA5","QQQ ETF volume",qqq_close,engine.ma_array(qqq_close,qqq_volume,"VWMA",5),engine.mkcfg("VWMA","twii",5,.02,.01,3))
    ]
    extra={};extra_meta=[]
    for name,signal,p,m,c in configs:
        record,trace=extra_model(name,signal,p,m,a,dates,fx,cash,fxstart,c)
        assert record["sessions"]==2203
        extra[name]=trace;extra_meta.append(record)
    sources={"QLD":quality,"QQQ":quality_ref,"^NDX":{"validClosePct":round(100*np.isfinite(ndx_close[(dates>=START)&(dates<=END)]).mean(),3),
        "missingCloseDates":[dates[i] for i in np.flatnonzero((dates>=START)&(~np.isfinite(ndx_close)))]}}
    summary={"version":"QLD_DAILY_DOUBLE_NASDAQ_2018_2026_V1","createdAt":datetime.now(ZoneInfo("Asia/Taipei")).isoformat(timespec="seconds"),
      "ticker":"QLD","underlying":"Nasdaq-100","period":"2018-01-02 through 2026-10-07",
      "symbolsFromYahoo":["QLD","QQQ","^NDX","TWD=X"],"priceAdjustments":"Yahoo adjclose/close adjustment, including dividends/splits",
      "account":{"startTWD":1_000_000,"startUSD":round(cash,4),
        "startUSD_TWD":fxstart,"lastUSD_TWD":float(fx[-1]),
        "fullyReinvest":True,"margin":False,"wholeShares":True,"idleCashInterest":0,
        "brokerEachSidePct":.1425,"slippageEachSidePct":.1,"US_ETF_SellTransactionTaxPct":0,
        "FXConversion":"2018 initial conversion and final 2026 mark only, no intermediary FX fees",
        "time":"daily completed close signal; next trading open fills; final liquidation marked net of costs"},
      "method":{"buyHold":"Buy on first QLD 2018 US open and hold to 2026 closing mark",
        "sma10":"QLD close below OWN SMA10 by 2% for 3 consecutive daily closes sells QLD next open; close above OWN SMA10 by 1% buys back",
        "vwma5":"QLD close below OWN VWMA5 by 2% for 3 closes exits QLD; close above OWN VWMA5 by 1% reenters",
        "ndx_sma":"^NDX index close relative to ^NDX SMA10 to trade QLD on next open with same 2%/1%/3-close thresholds",
        "qqq_sma_vwma":"QQQ liquid ETF close and ETF share volume as index-related proxy controlling QLD, never claim this is index volume",
        "alternative":"Also QLD VWMA5 1% exit / 2% reentry with 3 closes"},
      "qlDResults":results,"benchmarkSignalQLDResults":extra_meta,"qqqVerification":results_ref,"dataQuality":sources,
      "limitations":["QLD seeks daily 2x Nasdaq-100, and its long-term realized return is not 2 times QQQ long-term return.",
       "2018-2026 is previously observed historical data; no parameter fitting in this specific QLD study, still not a prospective validation.",
       "Yahoo adjusted-price total-return convention models distributions without explicitly deducting US nonresident dividend withholding.",
       "No foreign exchange spread, remittance/FX service fee, cash interest, or capital gains taxes modeled.",
       "All models are historical next-open execution with fixed assumptions; volatile leveraged ETF may gap over thresholds.",
       "Both QLD/QQQ ETF own prices and ^NDX index differ; underlying-based trading results should not be confused with QLD-own signal studies.",
       "Broker/fee assumptions copied from earlier QQQ research for apples-to-apples simulated comparability, not proof of broker costs."],
      "runtimeSeconds":round(time.monotonic()-began,1)}
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    (OUT/"trades_daily_equity.json").write_text(json.dumps({"version":summary["version"],"QLD":{"ownSignals":traces,"underlyingSignals":extra}},ensure_ascii=False),encoding="utf-8")
    print("QLD_COMPLETE "+json.dumps({"QLD":{z["strategy"]:z["netReturnTWD"] for z in results},
      "NDX":extra_meta[0]["netReturnTWD"],"QQQcontrol":refby["BUY_HOLD"]["netReturnTWD"],
      "bars":results[0]["sessions"]},ensure_ascii=False),flush=True)
if __name__=="__main__":run()
