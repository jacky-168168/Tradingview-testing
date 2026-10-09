"""QLD leveraged Nasdaq-100 ETF 2018-2026 vs buy-hold, 10D SMA, 5D VWMA.
Reuses the QQQ/VT validated 100萬 TWD -> USD fully reinvested daily signal engine.
Own-QLD SMA10/VWMA5 use identical 2% 3-close exit and 1% recovery reentry.
NDX SMA10 uses index-level signal, analogous to earlier 00675L/^TWII study.
No changing parameters based on 2018-2026 outcomes.
"""
from __future__ import annotations
import json,time,math
from datetime import datetime
from zoneinfo import ZoneInfo
import numpy as np,pandas as pd
from config import DATA_DIR
from yahoo_cache import update_symbol
import research_qqq_vt_2018_2026 as us
import research_00675l_vwma5_sma10_2018_2026 as base
START="2018-01-01";END="2026-10-07"
OUT=DATA_DIR/"research/qld_sma10_vwma5_ndx_2018_2026"
TWD=1_000_000.
def convert(ticker,label,raw,spots,fx_start,first_usd):
    daily=raw["dailyAccountEquity"];orders=raw["orders"];last=float(spots[-1])
    spot_by_day={z["date"]:float(k) for z,k in zip(ticker.date,spots)}
    twd=[float(r["equity"])*spot_by_day[r["date"]] for r in daily]
    peaks=np.maximum.accumulate(np.r_[TWD,twd])[1:]
    mdd_twd=round(float(100*np.min(np.array(twd)/peaks-1)),3)
    usd_end=float(raw["endNTD"]);twd_end=round(usd_end*last,2)
    ys=us.years_from_equity(daily,spot_by_day,first_usd)
    return {"id":label,"ticker":"QLD","entryDate":raw["start"],"lastDate":raw["end"],
       "sessions":raw["sessions"],"initialCapitalTWD":int(TWD),"initialCapitalUSD":round(first_usd,4),
       "endCapitalUSD":round(usd_end,2),"endCapitalTWD":twd_end,
       "netReturnUSD":raw["returnPct"],"netReturnTWD":round(100*(twd_end/TWD-1),3),
       "maxDDUSD":raw["mddPct"],"maxDDTWD":mdd_twd,
       "riskOffSells":raw["riskOffSells"],"riskOnReentries":raw["riskOnReentries"],
       "riskOffSessions":raw["riskOffSessions"],"tradingOrders":len(orders),
       "yearsContinuous":ys}
def run():
    begin=time.monotonic()
    raw={}
    for sym in ("QLD","QQQ","^NDX","TWD=X"):
        _,q,error=update_symbol(sym,datetime(2017,1,1),datetime(2026,10,8))
        if error or q is None or q.empty:raise RuntimeError("Missing "+sym+" history: "+str(error))
        raw[sym]=q
        print("QLD_FETCH "+json.dumps({"symbol":sym,"bars":len(q),"first":str(q.date.iloc[0]),"last":str(q.date.iloc[-1])}),flush=True)
    qld=us.prepare_etf(raw["QLD"],"QLD")
    qqq=us.prepare_etf(raw["QQQ"],"QQQ")
    d=qld.date.to_numpy(str);fx=us.fxseries(raw["TWD=X"],d)
    pos=np.flatnonzero((d>=START)&(d<=END))
    assert len(pos)>2150 and d[pos[0]]=="2018-01-02" and d[pos[-1]]==END,(len(pos),d[pos[0]],d[pos[-1]])
    fx0=float(fx[pos[0]]);usd_start=TWD/fx0
    print("QLD_FX "+json.dumps({"startUSDTWD":fx0,"endUSDTWD":float(fx[-1]),"initialCashUSD":usd_start}),flush=True)
    # Reconfirm the QQQ previous-period output under exact same original formulas.
    qqq_fx=us.fxseries(raw["TWD=X"],qqq.date.to_numpy(str))
    qqq_spot0=float(qqq_fx[np.flatnonzero((qqq.date.to_numpy(str)>=START)&(qqq.date.to_numpy(str)<=END))[0]])
    qqq_ref,_,_=us.test("QQQ",qqq,qqq.volume.to_numpy(float),qqq_fx,TWD/qqq_spot0,qqq_spot0)
    qr={x["strategy"]:x for x in qqq_ref}
    assert abs(qr["BUY_HOLD"]["netReturnTWD"]-444.202)<.05,qr["BUY_HOLD"]
    assert abs(qr["SMA10_2out_1in_c3"]["netReturnTWD"]-253.305)<.05
    print("QLD_QQQ_PRIOR_STUDY_PARITY "+json.dumps({"holdTWD":qr["BUY_HOLD"]["netReturnTWD"],
      "smaTWD":qr["SMA10_2out_1in_c3"]["netReturnTWD"]}),flush=True)
    qld_own,own_trace,quality=us.test("QLD",qld,qld.volume.to_numpy(float),fx,usd_start,fx0)
    # Additional index-based SMA10: signal ^NDX (not QLD) in exact same time-window.
    ndx=raw["^NDX"].copy()
    ndx.date=ndx.date.astype(str);ndx["close"]=pd.to_numeric(ndx.close,errors="coerce")
    ndx=ndx.sort_values("date").drop_duplicates("date",keep="last")
    join=qld[["date"]].merge(ndx[["date","close"]].rename(columns={"close":"ndxClose"}),on="date",how="left")
    ndx_close=join.ndxClose.to_numpy(float)
    index_missing=[str(d[i]) for i in pos if not np.isfinite(ndx_close[i])]
    if len(index_missing)>6:raise RuntimeError("Missing ^NDX date alignment >6: "+str(index_missing[:15]))
    # Own QLD ETF OHLC is corporate-action adjusted. Nasdaq 100 index is unleveraged and 
    # not adjusted for fund distributions (as an index): used ONLY to generate signals.
    a={"open":qld.open.to_numpy(float),"close":qld.close.to_numpy(float),"twii":ndx_close}
    us.base.CAPITAL=float(usd_start)
    sma_ndx=base.ma_array(ndx_close,None,"SMA",10)
    c=base.mkcfg("SMA","twii",10,.02,.01,3)
    cross=base.backtest(a,d,c,sma_ndx,START,END,True)
    ndx_result=convert(qld,"NDX_SMA10_2out_1in_c3",cross,fx,fx0,usd_start)
    ndx_trace={"equityUSD":cross["dailyAccountEquity"],"ordersUSD":cross["orders"]}
    indexes={v["strategy"] for v in qld_own}
    assert indexes=={"BUY_HOLD","SMA10_2out_1in_c3","VWMA5_2out_1in_c3","VWMA5_1out_2in_c3"}
    cases=[{"id":z["strategy"],"ticker":"QLD","entryDate":z["entryDate"],"lastDate":z["lastDate"],
        "sessions":z["sessions"],"initialCapitalTWD":z["initialTWD"],"initialCapitalUSD":z["initialUSD"],
        "endCapitalUSD":z["finalUSD"],"endCapitalTWD":z["finalTWD"],
        "netReturnUSD":z["netReturnUSD"],"netReturnTWD":z["netReturnTWD"],
        "maxDDUSD":z["maxDDUSD"],"maxDDTWD":z["maxDDTWD"],
        "riskOffSells":z["riskOffSells"],"riskOnReentries":z["riskOnReentries"],
        "riskOffSessions":z["riskOffSessions"],"tradingOrders":z["nOrders"],
        "yearsContinuous":z["yearlyContinuous"],"blockedInvalidVWMA":z["blockedVWMAInvalidDays"]} for z in qld_own]
    cases.append(ndx_result)
    assert len({(t["entryDate"],t["lastDate"],t["sessions"]) for t in cases})==1
    for item in cases:
        print("QLD_BACKTEST_MODEL "+json.dumps({k:item[k] for k in ["id","netReturnUSD","netReturnTWD","endCapitalTWD","maxDDUSD","maxDDTWD","riskOffSells","riskOffSessions"]},ensure_ascii=False),flush=True)
    # 00675L remains NTD-domiciled benchmark; only comparable in calendar period 
    # and initial NT$ capital, not equal geography/FX or underlying risk profile.
    tw_etf_reference={"ticker":"00675L.TW","market":"Taiwan",
      "fromPreviousVerifiedSamePeriodStudy":{"buyHold":{"netReturnTWD":2464.173,"endCapitalTWD":25641733.91,"maxDDTWD":-55.244},
      "indexSMA10":{"netReturnTWD":4110.755,"endCapitalTWD":42107551.24,"maxDDTWD":-35.378},
      "indexVWMA5":{"netReturnTWD":2371.981,"endCapitalTWD":24719808.33,"maxDDTWD":-56.141}},
      "provenance":"research/00675l-vwma5-vs-sma10-2018-2026/summmary.json on same GitHub repo"}
    report={"version":"US_QDL_QLD_SMA10_VWMA5_NDX_2018_2026_V1",
      "generatedAtTaipei":datetime.now(ZoneInfo("Asia/Taipei")).isoformat(timespec="seconds"),
      "security":{"ticker":"QLD","product":"ProShares Ultra QQQ","objective":"Nasdaq-100 INDEX DAILY 2x exposure, not 2x buyhold across multi-day holding"},
      "window":["2018-01-02",END],"marketSessions":len(pos),
      "method":{"startingCapitalTWD":int(TWD),"startFX_USDTWD":round(fx0,6),
        "lastFX_USDTWD":round(float(fx[-1]),6),"startingCashUSD":round(usd_start,4),
        "afterInitialConversion":"USD cash only throughout; exchange back to TWD at last-day reference",
        "brokerFeeEachSidePct":us.FEE*100,"slippageEachSidePct":us.SLIPPAGE*100,"sellTaiwanEtfTaxPct":0,
        "enterExit":"Use completed close to decide; trade QLD NEXT trading session opening, one stock at a time, no shorting/margin. Reinvest 100% of available net cash.",
        "dividends":"Yahoo adjusted OHLC approximates gross dividend reinvestment (not after tax); dividend withholding not deducted",
        "riskOff":"Hold 100% USD cash until reentry; interest 0",
        "paramFrozen":"SMA10 and VWMA5 use same 3 consecutive closes below MA -2% to SELL, 1 close above MA +1% to BUY",
        "indexSMA10":"^NDX Nasdaq-100 index close -> SMA10 risk signal (analogous ^TWII for 00675L), but QLD trade fills",
        "ownQLD":"QLD ETF split/dividend-adjusted price used for own-SMA10 and own-VWMA5, real ETF daily shares volume for VWMA"},
      "dataQuality":{"QLD":quality,"Nasdaq100IndexMissingDates":index_missing,"QQQReferenceParity":{"priorStudyQQQBuyholdTWD":qr["BUY_HOLD"]["netReturnTWD"],"priorStudyQQQSMA10TWD":qr["SMA10_2out_1in_c3"]["netReturnTWD"]}},
      "results":cases,"samePeriodTW00675LReference":tw_etf_reference,
      "warnings":["This ETF uses DAILY 2x leverage. Cumulative performance of QLD is path-dependent and NOT necessarily QQQ's long-term growth times two.",
      "US leveraged ETF distributions and historical splits are incorporated via Yahoo adjusted prices; index data must align to NYSE trading days.",
      "No Taiwan US-investor dividend withholding or conversion spread, US regulatory SEC/FINRA transaction costs, individual taxes, FX transfer or financing costs.",
      "Performance assumes next-open execution with specified slippage; severe Nasdaq gaps and large-account market impact can deviate.",
      "QLD own-price-based signals do NOT correspond exactly to earlier index-based 00675L signals; ^NDX SMA10 included for a like-style comparison.",
      "Historical parameter choice follows previous 00675L experiments, not an independent QLD-specific selection; a retrospective study does not imply future edge."],
      "elapsedSec":round(time.monotonic()-begin,1)}
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/"summary.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    traces={"QLD":own_trace,"NDX_SMA10_2out_1in_c3":ndx_trace}
    (OUT/"transactions_and_daily_equity.json").write_text(json.dumps({"version":report["version"],"traces":traces},ensure_ascii=False),encoding="utf-8")
    print("QLD_BACKTEST_COMPLETE "+json.dumps({"period":report["window"],"n":len(cases),
      "returns":[{"id":x["id"],"twd":x["netReturnTWD"],"usd":x["netReturnUSD"]} for x in cases]},ensure_ascii=False),flush=True)
if __name__=="__main__":run()
