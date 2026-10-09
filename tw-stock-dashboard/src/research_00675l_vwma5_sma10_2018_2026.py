"""2018-2026 cash-compounded 00675L: exact original index SMA10 vs index VWMA5.
A priori identical exit/reentry buffers on two different lookbacks; optional VWMA5
alternative from fixed previous study. All rules use ^TWII (NOT ETF) volume for VWMA.
"""
from __future__ import annotations
import json,time,math
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path
import numpy as np,pandas as pd
from research_00675l_swing_grid import data_prepare,update_symbol,SYMBOL,INDEX,CAPITAL,BROKER,ETF_SELL_TAX,SLIP,DATA_DIR
from research_00675l_near_hold_switch import prepare,indicators,bt
from research_00675l_ma_family_2020_2026 import ma_array,mkcfg,localarrays
OUT=DATA_DIR/"research/etf_00675l_vwma5_sma10_2018_2026"
FULL=("2018-01-01","2026-10-07")
REF=("2020-01-01","2026-10-07")
CASES=[
    ("SMA10_index_original_2_1",mkcfg("SMA","twii",10,.02,.01,3)),
    ("VWMA5_index_equal_2_1",mkcfg("VWMA","twii",5,.02,.01,3)),
    ("VWMA5_index_alternative_1_2",mkcfg("VWMA","twii",5,.01,.02,3))
]
def stats(x):
    return {k:x[k] for k in ("start","end","returnPct","endNTD","mddPct",
        "riskOffSells","riskOnReentries","riskOffSessions","investedSessions","sessions","switchEvents")}
def years_from_equity(points):
    last=float(CAPITAL);out={}
    for year in sorted({x["date"][:4] for x in points}):
        row=next(x for x in reversed(points) if x["date"].startswith(year))
        eq=float(row["equity"])
        out[year]={"openingNTD":round(last,2),"closingNTD":round(eq,2),
                   "annualNetReturnPct":round(100*(eq/last-1),3)}
        last=eq
    return out
def index_data():
    # Full 2017 lookback for warm-up of indicators and pre-2018 volume.
    _,etf,e=update_symbol(SYMBOL,datetime(2017,1,1),datetime(2026,10,8))
    _,idx,e2=update_symbol(INDEX,datetime(2017,1,1),datetime(2026,10,8))
    if e or e2 or etf is None or idx is None or etf.empty or idx.empty:
        raise RuntimeError(f"Unreliable data fetch etf={e}, index={e2}")
    raw=data_prepare(etf,idx)
    volume=idx[["date","volume"]].copy()
    volume.date=volume.date.astype(str)
    volume["volume"]=pd.to_numeric(volume.volume,errors="coerce")
    volume=volume.rename(columns={"volume":"index_volume"})
    d=prepare(raw).merge(volume.drop_duplicates("date",keep="last"),on="date",how="left")
    d=d[d.date<=FULL[1]].reset_index(drop=True)
    a,dates=indicators(d)
    valid=(dates>=FULL[0])&(dates<=FULL[1])
    if dates[0]>"2017-03-01" or dates[valid].size<2050:
        raise RuntimeError(f"2018-26 missing history: first {dates[0]} sessions {dates[valid].size}")
    vol=np.asarray(a["index_volume"],dtype=float)
    missing=np.where(valid&(~np.isfinite(vol)|(vol<=0)))[0]
    bad=[str(d.iloc[i]["date"]) for i in missing]
    q={"firstHistoricalDate":str(d.iloc[0]["date"]),"lastDate":str(d.iloc[-1]["date"]),
       "totalTradingDays":int(valid.sum()),"indexVolumeValidDays":int(valid.sum()-len(bad)),
       "indexVolumeValidPct":round(100*(valid.sum()-len(bad))/valid.sum(),4),
       "indexVolumeMissingDates":bad,"indexVolumeUnique":int(np.unique(vol[valid&(vol>0)]).size),
       "etfPriceAdjFactorRange":[round(float(d.loc[valid,"factor"].min()),6),round(float(d.loc[valid,"factor"].max()),6)]}
    print("DATA_2018_2026 "+json.dumps(q,ensure_ascii=False),flush=True)
    return d,a,dates,q
def backtest(a,dates,c,ma,start,end,detailed=True):
    """Copy of original bt cash-account math with explicit missing-VWMA no-signal guard.
    SMA and BUY_HOLD paths are asserted equal to original bt on 2020-26.
    """
    idxs=np.flatnonzero((dates>=start)&(dates<=end))
    if len(idxs)<40:raise RuntimeError("Insufficient trading bars")
    cash=float(CAPITAL);shares=0;state=True;orders=[];equity=[];regime_days=0;hold_days=0
    buy_factor=(1+SLIP)*(1+BROKER)
    sell_factor=(1-SLIP)*(1-BROKER-ETF_SELL_TAX)
    for pos,i in enumerate(idxs):
        date=str(dates[i]);open_px=float(a["open"][i]);close_px=float(a["close"][i])
        if pos==0:desired=True
        elif c["family"]=="buyhold":desired=True
        else:
            j=i-1
            # Never invent VWMA if the original source has no volume for any bar in window.
            # No new signal is possible on a missing rolling VWMA; keep prior position.
            if not np.isfinite(ma[j]):desired=state
            else:
                t=float(a["twii"][j]);m=float(ma[j]);conf=int(c["confirm"])
                if state:
                    below=t<m*(1-c["out"])
                    if conf>1:
                        for k in range(j-conf+1,j):
                            if k<0 or not np.isfinite(ma[k]) or not a["twii"][k]<ma[k]*(1-c["out"]):
                                below=False;break
                    desired=not below
                else:
                    desired=t>m*(1+c["rein"])
        if pos==0 or desired!=state:
            state=desired
            target_fraction=1 if state else 0
            gross=cash+shares*open_px*sell_factor
            target=int(max(0,gross*target_fraction)//(open_px*buy_factor))
            if target<shares:
                n=shares-target;proc=n*open_px*sell_factor
                cash+=proc;shares-=n
                orders.append({"date":date,"side":"SELL","phase":"risk_off","units":int(n),
                               "openPrice":round(open_px,5),"cashFlow":round(proc,2),"accountCash":round(cash,2)})
            if target>shares:
                n=min(target-shares,int(cash//(open_px*buy_factor)))
                if n>0:
                    proc=n*open_px*buy_factor;cash-=proc;shares+=n
                    orders.append({"date":date,"side":"BUY","phase":"risk_on","units":int(n),
                                   "openPrice":round(open_px,5),"cashFlow":round(-proc,2),"accountCash":round(cash,2)})
        if not state:regime_days+=1
        if shares>0:hold_days+=1
        equity.append({"date":date,"equity":round(cash+shares*close_px*sell_factor,2),
                       "heldUnits":shares,"state":"invested" if state else "cash"})
    if shares>0:
        i=idxs[-1];endprice=float(a["close"][i]);proceeds=shares*endprice*sell_factor
        cash+=proceeds
        orders.append({"date":str(dates[i]),"side":"SELL","phase":"period_end",
                       "units":int(shares),"openPrice":None,"cashFlow":round(proceeds,2),"accountCash":round(cash,2)})
        shares=0
        equity[-1]["equity"]=round(cash,2);equity[-1]["heldUnits"]=0
    vals=np.array([x["equity"] for x in equity]);high=np.maximum.accumulate(np.r_[CAPITAL,vals])[1:]
    out={"start":equity[0]["date"],"end":equity[-1]["date"],
         "returnPct":round((cash/CAPITAL-1)*100,3),"endNTD":round(cash,2),
         "mddPct":round(float(np.min(100*(vals/high-1))),3),
         "riskOffSells":sum(t["phase"]=="risk_off" for t in orders),
         "riskOnReentries":max(0,sum(t["phase"]=="risk_on" for t in orders)-1),
         "riskOffSessions":regime_days,"investedSessions":hold_days,"sessions":len(equity),
         "switchEvents":len([x for x in orders if x["phase"]!="period_end"])-1}
    if detailed:out.update({"dailyAccountEquity":equity,"orders":orders})
    return out
def run():
    started=time.monotonic()
    d,a,dates,quality=index_data()
    prices=a["twii"];idx_volume=a["index_volume"]
    ma_sma=ma_array(prices,None,"SMA",10)
    ma_vwma=ma_array(prices,idx_volume,"VWMA",5)
    base=CASES[0][1]
    legacy_a=localarrays(a,{("SMA","twii",10):ma_sma},base)
    legacy=bt(legacy_a,dates,base,*REF)
    current=backtest(a,dates,base,ma_sma,*REF,detailed=False)
    assert legacy["returnPct"]==3312.334,(legacy["returnPct"],current["returnPct"])
    for key in stats(legacy):
        assert stats(current)[key]==stats(legacy)[key],(key,stats(current)[key],stats(legacy)[key])
    reference_hold={"id":"BUY_HOLD","family":"buyhold","riskOffWeight":1.0}
    old_hold=bt(a,dates,reference_hold,*REF)
    now_hold=backtest(a,dates,reference_hold,ma_sma,*REF,detailed=False)
    assert old_hold["returnPct"]==now_hold["returnPct"]==1653.043
    print("PARITY_SMA_AND_HOLD_2020_2026 "+json.dumps({"sma":current["returnPct"],"hold":now_hold["returnPct"]}),flush=True)
    windows={"2018_2019":("2018-01-01","2019-12-31"),
             "2020_2023":("2020-01-01","2023-12-31"),
             "2024_2026":("2024-01-01","2026-10-07"),
             "2026":("2026-01-01","2026-10-07")}
    cases=[("BUY_HOLD",reference_hold,ma_sma)]+[(title,c,ma_sma if i==0 else ma_vwma) for i,(title,c) in enumerate(CASES)]
    result=[];detail={}
    for name,c,ma in cases:
        z=backtest(a,dates,c,ma,*FULL)
        subs={n:stats(backtest(a,dates,c,ma,*period,detailed=False)) for n,period in windows.items()}
        missing_signals=0
        if name.startswith("VWMA"):
            y=(dates>=FULL[0])&(dates<=FULL[1]);pos=np.flatnonzero(y)
            missing_signals=int(sum(not np.isfinite(ma[i-1]) for i in pos[1:]))
        r={"id":name,"indexUsed":"^TWII","maType":c.get("maType","hold"),"length":c.get("n"),
           "exitBufferPct":round(100*c.get("out",0),3),"reentryBufferPct":round(100*c.get("rein",0),3),
           "consecutiveClosesForExit":c.get("confirm",0),
           "continuous2018_2026":stats(z),"calendarYearsContinuous":years_from_equity(z["dailyAccountEquity"]),
           "independentPeriodChecks":subs,"invalidSignalDaysBlocked":missing_signals,
           "sellDates":[x["date"] for x in z["orders"] if x["phase"]=="risk_off"],
           "rebuyDates":[x["date"] for x in z["orders"] if x["phase"]=="risk_on"][1:]}
        result.append(r)
        detail[name]={"dailyEquity":z["dailyAccountEquity"],"orders":z["orders"]}
        print("CASE_2018_2026 "+json.dumps({"id":name,"endNTD":z["endNTD"],"netReturnPct":z["returnPct"],
            "mddPct":z["mddPct"],"sells":z["riskOffSells"],"blockedInvalidSignals":missing_signals,
            "2018":r["calendarYearsContinuous"]["2018"]["annualNetReturnPct"],
            "2022":r["calendarYearsContinuous"]["2022"]["annualNetReturnPct"],
            "2026":r["calendarYearsContinuous"]["2026"]["annualNetReturnPct"]},ensure_ascii=False),flush=True)
    benchmark=result[1]["continuous2018_2026"]
    for item in result:
        if item["id"]!="BUY_HOLD":
            item["vsSMA10"]={"returnPctPointDiff":round(item["continuous2018_2026"]["returnPct"]-benchmark["returnPct"],3),
                "endingAssetNTDDiff":round(item["continuous2018_2026"]["endNTD"]-benchmark["endNTD"],2)}
    report={"version":"00675L_VWMA5_VS_SMA10_2018_2026_V1",
        "generatedAt":datetime.now(ZoneInfo("Asia/Taipei")).isoformat(timespec="seconds"),
        "symbol":SYMBOL,"index":INDEX,"period":"2018-01-02 to 2026-10-07",
        "quality":quality,"historyNotional":{"startCapitalNTD":CAPITAL,"profitReinvestment":"100% of current available cash on every risk-on reentry",
        "margin":False,"brokerFeeEachSidePct":round(100*BROKER,5),"sellEtfTaxPct":round(100*ETF_SELL_TAX,5),
        "slippageEachSidePct":round(100*SLIP,5),"cashInterestRatePct":0,
        "tradeTime":"signals on prior completed daily close; actual model execution on next trading open",
        "marking":"end of entire test hypothetically liquidated at last close with tax/fees/slippage",
        "vwmaVolume":"Yahoo Finance ^TWII daily raw volume, not 00675L ETF traded volume",
        "missingVWMAHandling":"do not trade on unavailable VWMA signal; keep previous position, do not interpolate source volume"},
        "method":"Primary fair control changes only moving-average type AND the stated lookback (VWMA5 versus SMA10); both use 2% break / 1% regain and 3-day exit confirmation. Optional VWMA5 1%/2% listed separately, pre-specified.",
        "referenceParity":{"SMA10_2020_2026_pct":current["returnPct"],"BUYHOLD_2020_2026_pct":now_hold["returnPct"]},
        "cases":result,"seconds":round(time.monotonic()-started,1),
        "warnings":["A VWMA using ^TWII volume is only as reliable as Yahoo's ^TWII daily market-volume reporting, especially across market-data schema changes.","Historical Yahoo adjusted OHLC and unadjusted trading volumes do not guarantee a perfectly investable VWMA.","2026 and 2020-2023 already examined during prior strategy research: do not claim untouched out-of-sample.","Market gaps, leveraged ETF volatility drag, commissions and real fill liquidity can cause realized deviations.","Comparison at fixed buffers changes BOTH MA type and lookback by user request (VWMA5 vs SMA10); thus any performance gap cannot be attributed to MA weighting formula alone.","The 2%/1% alternative is illustrative and pre-defined, not selected by 2018-2026 highest return."]}
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/"summary.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    (OUT/"trades_and_equity.json").write_text(json.dumps({"version":report["version"],"cases":detail},ensure_ascii=False),encoding="utf-8")
    print("VWMA5_SMA10_2018_2026_COMPLETE "+json.dumps({"start":result[0]["continuous2018_2026"]["start"],
      "end":result[0]["continuous2018_2026"]["end"],"sessions":result[0]["continuous2018_2026"]["sessions"],
      "sma10pct":result[1]["continuous2018_2026"]["returnPct"],
      "vwma5pct":result[2]["continuous2018_2026"]["returnPct"],
      "elapsed":report["seconds"]}),flush=True)
if __name__=="__main__":run()
