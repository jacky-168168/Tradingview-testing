"""Independent QQQ and VT USA ETF 2018-2026 daily backtest.
Compare buy/hold, own-price SMA10 (3 closes below 98% exit, close above 101% rebuy),
own-price-and-own-volume VWMA5 with SAME buffers, and a separate sensitivity VWMA5 1%/2%.
Execute NEXT market OPEN, whole ETF shares, all cash USD-compounded, no leverage.
Initially exchange exactly NTD 1m for USD at 2018-01-02 Yahoo TWD=X spot;
FX adjusts NTD-valued NAV through period without intervening currency conversions.
ETF OHLC are Yahoo dividend/split-adjusted synthetic total-return prices.
US ETF: 0% TW ETF selling tax, brokerage 0.1425% per side, slippage 0.1% per side.
"""
from __future__ import annotations
import json,time,math
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import numpy as np,pandas as pd
from yahoo_cache import update_symbol
from config import DATA_DIR
import research_00675l_vwma5_sma10_2018_2026 as base
START="2018-01-01"; END="2026-10-07"; BEGIN_FETCH=datetime(2017,1,1);END_FETCH=datetime(2026,10,8)
START_TWD=1_000_000.0
FEE=.001425;SLIPPAGE=.001;US_SELL_ETF_TAX=0.
OUT=DATA_DIR/"research/qqq_vt_sma10_vwma5_2018_2026"
base.BROKER=FEE;base.SLIP=SLIPPAGE;base.ETF_SELL_TAX=US_SELL_ETF_TAX
PERIODS={"2018_2019":("2018-01-01","2019-12-31"),
         "2020_2023":("2020-01-01","2023-12-31"),
         "2024_2026":("2024-01-01","2026-10-07"),
         "2026":("2026-01-01","2026-10-07")}
def summarize(raw,capital):
    dd=dict(raw)
    for k in ("dailyAccountEquity","orders"):dd.pop(k,None)
    dd["startingCapitalUSD"]=round(capital,2)
    return dd
def prepare_etf(df,ticker):
    d=df.copy()
    d["date"]=d["date"].astype(str)
    for k in ("open","high","low","close","adjclose","volume"):
        d[k]=pd.to_numeric(d[k],errors="coerce")
    d=d.sort_values("date").drop_duplicates("date",keep="last")
    d=d.dropna(subset=["date","open","high","low","close","adjclose","volume"])
    if len(d[d.date.between(START,END)])<1900:raise RuntimeError(ticker+" incomplete history")
    d["adj_factor"]=(d.adjclose/d.close).replace([np.inf,-np.inf],np.nan)
    if d.adj_factor.isna().any() or (d.adj_factor<=0).any():raise RuntimeError(ticker+" bad adjusted close")
    for k in ("open","high","low","close"):d[k]=d[k]*d.adj_factor
    for k in ("open","high","low","close"):
        if (d[k]<=0).any():raise RuntimeError(ticker+" nonpositive adjusted OHLC")
    if (d.close.pct_change().abs()>.55).any():raise RuntimeError(ticker+" unexplained >55% adjusted split/gap")
    return d[d.date<=END].reset_index(drop=True)
def fxseries(raw,daystrings):
    f=raw[["date","close"]].copy();f.date=f.date.astype(str);f.close=pd.to_numeric(f.close,errors="coerce")
    f=f.dropna().sort_values("date").drop_duplicates("date",keep="last")
    f=f[(f.close>15)&(f.close<50)]
    if f.empty:raise RuntimeError("USD/TWD Yahoo TWD=X unavailable")
    df=pd.DataFrame({"date":pd.to_datetime(list(daystrings))})
    f["date"]=pd.to_datetime(f["date"])
    df=pd.merge_asof(df.sort_values("date"),f.rename(columns={"close":"usdTwd"}).sort_values("date"),on="date",direction="backward")
    if df.usdTwd.isna().any():raise RuntimeError("Missing USD/TWD spot values on ETF dates")
    if float(df.usdTwd.min())<20 or float(df.usdTwd.max())>45:raise RuntimeError("Invalid FX range")
    return df.usdTwd.to_numpy(float)
def years_from_equity(rows,fx_dict,capital_usd):
    years=sorted(set(r["date"][:4] for r in rows))
    prev_usd=capital_usd;prev_twd=START_TWD;result={}
    for y in years:
        r=next(v for v in reversed(rows) if v["date"].startswith(y))
        spot=fx_dict[r["date"]];end_usd=float(r["equity"]);end_twd=end_usd*spot
        result[y]={"lastDate":r["date"],"endAccountUSD":round(end_usd,2),
            "endAccountTWD":round(end_twd,2),
            "USDAnnualReturnPct":round(100*(end_usd/prev_usd-1),3),
            "TWDAnnualReturnPct":round(100*(end_twd/prev_twd-1),3)}
        prev_usd=end_usd;prev_twd=end_twd
    return result
def test(ticker,prices,volumes,spots,cash,fxstart):
    global base
    base.CAPITAL=float(cash)
    idx=(prices.date>=START)&(prices.date<=END)
    dates=prices.date.to_numpy(str)
    close=prices.close.to_numpy(float)
    volume=prices.volume.to_numpy(float)
    a={"open":prices.open.to_numpy(float),"close":close,"twii":close}
    valid=int(np.count_nonzero(idx))
    missingvol=prices.loc[idx & ~(prices.volume>0),"date"].tolist()
    sma=base.ma_array(close,None,"SMA",10)
    vwma=base.ma_array(close,volume,"VWMA",5)
    schemas=[
      ("BUY_HOLD",{"family":"buyhold","riskOffWeight":1.0},sma),
      ("SMA10_2out_1in_c3",base.mkcfg("SMA","twii",10,.02,.01,3),sma),
      ("VWMA5_2out_1in_c3",base.mkcfg("VWMA","twii",5,.02,.01,3),vwma),
      ("VWMA5_1out_2in_c3",base.mkcfg("VWMA","twii",5,.01,.02,3),vwma)
    ]
    trading_idx=np.flatnonzero(idx)
    fxmap=dict(zip(dates,spots))
    records=[];daily={}
    for label,conf,ma in schemas:
        # Critical: backtest.cash is US dollars (1m TWD converted on starting date).
        # The engine is the very same as used for 2018-26 00675L with US sell tax changed to 0.
        raw=base.backtest(a,dates,conf,ma,START,END,True)
        lines=raw["dailyAccountEquity"];orders=raw["orders"]
        assert len(lines)==valid,("daily missing",ticker,label,len(lines),valid)
        if lines[-1]["date"]!=END:raise RuntimeError("Wrong end date "+str(lines[-1]["date"]))
        usd_end=raw["endNTD"]
        twd_end=usd_end*fxmap[END]
        daily_twd=np.array([v["equity"]*fxmap[v["date"]] for v in lines])
        peaks=np.maximum.accumulate(np.r_[START_TWD,daily_twd])[1:]
        twd_dd=round(float(np.min((daily_twd/peaks-1)*100)),3)
        fxtotal=fxmap[END]/fxstart
        fxadj_return=round(100*(twd_end/START_TWD-1),3)
        result={"ticker":ticker,"strategy":label,"entryDate":lines[0]["date"],
           "lastDate":lines[-1]["date"],"sessions":len(lines),
           "initialTWD":int(START_TWD),"initialUSD":round(cash,4),
           "finalUSD":round(usd_end,2),"finalTWD":round(twd_end,2),
           "netReturnUSD":raw["returnPct"],"netReturnTWD":fxadj_return,
           "maxDDUSD":raw["mddPct"],"maxDDTWD":twd_dd,
           "riskOffSells":raw["riskOffSells"],"riskOnReentries":raw["riskOnReentries"],
           "riskOffSessions":raw["riskOffSessions"],"nOrders":len(orders),
           "blockedVWMAInvalidDays":int(sum(not np.isfinite(ma[i-1]) for i in trading_idx[1:])) if label.startswith("VWMA") else 0,
           "currencyChangePct":round(100*(fxtotal-1),3),
           "yearlyContinuous":years_from_equity(lines,fxmap,cash)}
        # No TWD conversion at each sell. Only conversion once at initial and final endpoints.
        trace={"equityUSD":lines,"ordersUSD":orders}
        records.append(result);daily[label]=trace
        print("USA_ETF_RESULT "+json.dumps({k:result[k] for k in ["ticker","strategy","netReturnUSD","netReturnTWD",
         "finalTWD","maxDDUSD","maxDDTWD","riskOffSells","riskOffSessions"]},ensure_ascii=False),flush=True)
    assert all(r["sessions"]==valid for r in records)
    assert all(r["entryDate"]==records[0]["entryDate"] for r in records)
    return records,daily,{"ticker":ticker,"startDate":records[0]["entryDate"],
        "endDate":END,"nSessions":valid,
        "rawVolumePositiveDaysPct":round(100*(valid-len(missingvol))/valid,3),
        "missingVolumeDates":missingvol,
        "adjustFactorMin":round(float(prices.adj_factor.min()),6),
        "adjustFactorMax":round(float(prices.adj_factor.max()),6),
        "closeCurrency":"USD","volumeCurrency":"shares","startUSDperTWD":round(1/fxstart,6)}
def run():
    start=time.monotonic()
    symbols=["QQQ","VT","TWD=X"]
    fetched={}
    for symbol in symbols:
        _,raw,error=update_symbol(symbol,BEGIN_FETCH,END_FETCH)
        if error or raw is None or raw.empty:
            raise RuntimeError(f"Missing 2017-2026 historical daily bars for {symbol} error={error}")
        fetched[symbol]=raw
        print("USA_ETF_FETCH "+json.dumps({"ticker":symbol,"rows":len(raw),
             "firstDate":str(raw.date.iloc[0]),"lastDate":str(raw.date.iloc[-1])}),flush=True)
    allcases=[];dataall={};sources={}
    for ticker in ("QQQ","VT"):
        d=prepare_etf(fetched[ticker],ticker)
        fx=fxseries(fetched["TWD=X"],d.date.to_numpy(str))
        dates=d.date.to_numpy(str)
        first=int(np.flatnonzero((dates>=START)&(dates<=END))[0])
        fxstart=float(fx[first]);usdcash=START_TWD/fxstart
        print("USA_ETF_FX "+json.dumps({"ticker":ticker,"firstDate":dates[first],"firstFx_USD_to_TWD":fxstart,
              "lastFx_USD_to_TWD":float(fx[-1]),"startingUSD":usdcash}),flush=True)
        reports,traces,quality=test(ticker,d,d.volume.to_numpy(float),fx,usdcash,fxstart)
        quality.update({"firstFX":fxstart,"lastFX":float(fx[-1]),
            "fxSource":"Yahoo Finance TWD=X USD/TWD daily spot, backward as-of join to each NYSE date"})
        sources[ticker]=quality;allcases.extend(reports);dataall[ticker]=traces
    summary={"version":"US_ETF_QQQ_VT_2018_2026_SMA10_VWMA5_CASH_COMPOUND_V1",
      "generatedAtTaipei":datetime.now(ZoneInfo("Asia/Taipei")).isoformat(timespec="seconds"),
      "window":[START,END],"pricesSource":"Yahoo Finance QQQ,VT and TWD=X, 2017 prewarm, completed adjusted daily OHLC",
      "baselineDescription":"Buy & hold QQQ and VT individually; own ETF price signals for SMA10 and ETF price+ETF share volume for VWMA5",
      "account":{"startingCapitalTWD":START_TWD,"exchangeAtStart":"TWD to USD on first US trading date using TWD=X spot",
        "cashCurrencyBetweenTrades":"USD only; never converts FX on intermediate buy/sell",
        "endDateReturn":"USD portfolio proceeds valued at TWD=X rate on last date",
        "fullProfitsReinvested":True,"wholeSharesOnly":True,"margin":False,"interestOnIdleCash":0,
        "brokerFeeEachSidePct":FEE*100,"slippageEachSidePct":SLIPPAGE*100,
        "US_ETF_sellTaxPct":0.,
        "cashDividends":"Simulated using Yahoo dividend-adjusted OHLC as a total-return proxy; US nonresident dividend withholding and cash payment timings NOT explicitly deducted",
        "US_Tax_And_FX_Transfer_Fees":"No US dividend withholding, no Taiwan capital gains tax, no currency-conversion spread, no cross-border bank fees modeled",
        "execution":"Close-confirmed signal for next US trading day's open; terminal hypothetical close sale fee-slippage modeled"},
      "ruleDefinitions":[{"id":"BUY_HOLD","rule":"Hold from first 2018 open to last 2026 close, with hypothetical liquidation"},
        {"id":"SMA10_2out_1in_c3","rule":"ETF adjusted close below its own 10day simple average by >2% for 3 completed days -> next-open exit; ETF close above SMA10*1.01 -> next-open full-cash reentry"},
        {"id":"VWMA5_2out_1in_c3","rule":"ETF adjusted close below its own 5day volume-weighted moving average by >2% for 3 completed days -> next-open exit; close above VWMA5*1.01 -> next-open full-cash reentry"},
        {"id":"VWMA5_1out_2in_c3","rule":"Optional 00675L-study VWMA5 alternative: below 5day VWMA by >1% for 3 completed closes exit; above VWMA5 by >2% reenter"}],
      "assets":sources,"results":allcases,
      "warnings":["QQQ and VT trade in USD, and unlike Taiwan's leveraged 00675L, both are UNLEVERAGED; historical return levels are not risk-equivalent.",
        "SMA10/VWMA5 here are based on each ETF's OWN adjusted prices and actual ETF volumes. Prior 00675L rules were based on Taiwan's weighted index ^TWII.",
        "2018-2026 data are already historical; this is descriptive strategy research, not prospective predictive verification.",
        "ETF dividends are proxied by Yahoo adjusted-close total returns; US withholding tax for Taiwan resident investor and international tax reporting are not deducted.",
        "Exchange-rate conversion assumed no spreads; USD/TWD last daily reference may not coincide with exact broker FX execution time.",
        "Fully reinvested profits can create high losses after growth; there are no stops outside the MA risk-off triggers.",
        "Actual brokerage fees and ETF spreads may differ; whole-share rounding impacts QQQ/VT starting 1m TWD portfolios.",
        "EMA/WMA not tested for these US ETFs in this narrowly scoped request."],
      "secondsElapsed":round(time.monotonic()-start,1)}
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    (OUT/"transactions_equity.json").write_text(json.dumps({"version":summary["version"],"traces":dataall},ensure_ascii=False),encoding="utf-8")
    print("USA_ETF_COMPLETE "+json.dumps({"window":summary["window"],"tickers":list(sources),
       "elapsed":summary["secondsElapsed"],
       "USDreturns":[{"ticker":r["ticker"],"model":r["strategy"],"usd":r["netReturnUSD"],"twd":r["netReturnTWD"]} for r in allcases]},ensure_ascii=False),flush=True)
if __name__=="__main__":run()
