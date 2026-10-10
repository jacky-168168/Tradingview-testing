"""00675L SMA10+panic exit versus VT/QQQ allocation, 2018-2026, TWD.
Reuses frozen, independently published executable-account curves (not naked price returns).
US sleeves are converted using Yahoo USD/TWD daily spot, backward-asof on a
calendar-date joint close ledger. The three exchange sessions are asynchronous:
Taiwan ETF has closed by the time NYSE closes later the same calendar date.
No equity curve is allowed to trigger a trade in another sleeve. Separate
no-rebalance and yearly-rebalance scenarios. No retuning on 2026 data.
"""
from __future__ import annotations
import json,math,time
from datetime import datetime,timezone
from pathlib import Path
import numpy as np,pandas as pd
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from yahoo_cache import update_symbol
BASE=ROOT/"docs"/"data"/"research"/"etf_history"
OUT=BASE/"alloc_00675_vt_qqq_2018_2026"
START="2018-01-02";END="2026-10-07";INITIAL=1_000_000.
ASSETS={
 "L2_SMA10":"curves/00675_crash_sma5__BASE.json",
 "L2_HOLD":"curves/00675_2018__BUY_HOLD.json",
 "VT":"curves/qqq_vt__VT__BUY_HOLD.json",
 "QQQ":"curves/qqq_vt__QQQ__BUY_HOLD.json"}
# Weights are specified BEFORE computing the combined portfolio.
CONFIGS={
 "L2_SMA10_100":{"L2_SMA10":1.},
 "L2_SMA10_50_VT30_QQQ20":{"L2_SMA10":.5,"VT":.3,"QQQ":.2},
 "L2_SMA10_30_VT50_QQQ20":{"L2_SMA10":.3,"VT":.5,"QQQ":.2},
 "VT55_QQQ45":{"VT":.55,"QQQ":.45},
 "VT_100":{"VT":1.},
 "QQQ_100":{"QQQ":1.},
 "L2_BUY_HOLD_100":{"L2_HOLD":1.},
}
# Extra ALL-PORTFOLIO yearly rebalancing trading friction beyond the
# transactions already included within each independent sleeve curve.
# Costs applied on amounts traded: 0.1425% brokerage + 0.1% slippage;
# extra 0.1% ETF sale tax if the leverage sleeve is reduced.
REBAL_FEE=.002425
REBAL_L2_SELL_TAX=.001
def safe_round(v,n=3):
    return round(float(v),n) if v is not None and math.isfinite(float(v)) else None
def load_curve(asset):
    p=BASE/ASSETS[asset]
    doc=json.loads(p.read_text(encoding="utf-8"))
    if doc.get("columns")!=["date","equity"]:raise RuntimeError(asset+" has incompatible curve schema")
    points=doc.get("points")
    if not points or points[0][0]!=START or points[-1][0]!=END:raise RuntimeError(asset+" dates invalid")
    dates=[z[0] for z in points]
    if dates!=sorted(set(dates)):raise RuntimeError(asset+" duplicates/unsorted dates")
    val=pd.to_numeric(pd.Series([z[1] for z in points],index=pd.to_datetime(dates)),errors="raise")
    if not bool(np.isfinite(val).all()) or (val<=0).any():raise RuntimeError(asset+" invalid equity")
    if doc["currency"]!=("USD" if asset in ("VT","QQQ") else "TWD"):
        raise RuntimeError(asset+" inconsistent currency")
    return val,doc
def market_usdtwd():
    _,data,error=update_symbol("TWD=X",datetime(2017,12,1),datetime(2026,10,8))
    if error or data is None or data.empty:raise RuntimeError("Missing USD/TWD spot historical data: "+str(error))
    f=data[["date","close"]].copy()
    f["date"]=pd.to_datetime(f.date.astype(str));f["close"]=pd.to_numeric(f["close"],errors="coerce")
    f=f.dropna().drop_duplicates("date",keep="last").sort_values("date")
    f=f[(f.close>20)&(f.close<45)]
    if f.empty or f.date.iloc[0]>pd.Timestamp(START):raise RuntimeError("FX archive misses starting date")
    return pd.Series(f.close.to_numpy(float),index=pd.DatetimeIndex(f.date))
def align_curves(raw,fx):
    calendar=pd.DatetimeIndex(sorted(set().union(*(set(v.index) for v in raw.values()))))
    calendar=calendar[(calendar>=pd.Timestamp(START))&(calendar<=pd.Timestamp(END))]
    aligned={}
    f=fx.reindex(calendar,method="ffill")
    if f.isna().any():raise RuntimeError("Cannot backfill USD/TWD into all portfolio dates")
    for asset,src in raw.items():
        s=src.reindex(calendar,method="ffill")
        if s.isna().any():raise RuntimeError("Missing initial sleeve return "+asset)
        aligned[asset]=s*(f if asset in ("VT","QQQ") else 1.)
    # Never forward-fill older than seven calendar days; ETF holidays are expected.
    for label,src in list(raw.items())+[("FX",fx)]:
        last_dates=pd.Series(src.index,index=src.index).reindex(calendar,method="ffill")
        days=(pd.Series(calendar,index=calendar)-last_dates).dt.days
        if int(days.max())>8:raise RuntimeError(label+" prolonged data gap "+str(int(days.max())))
    return calendar,aligned,f
def curve_summary(dates,values):
    v=np.asarray(values,dtype=float)
    if not np.isfinite(v).all() or np.any(v<=0):raise RuntimeError("Invalid daily ledger")
    if len(v)!=len(dates):raise RuntimeError("Date vs values mismatch")
    maxima=np.maximum.accumulate(np.r_[INITIAL,v])[1:]
    dd=v/maxima-1
    trough=int(np.argmin(dd))
    peak=int(np.argmax(v[:trough+1])) if trough>0 else 0
    if v[peak]<INITIAL:peak_date="2018-01-01"
    else:peak_date=dates[peak].strftime("%Y-%m-%d")
    peak_value=max(INITIAL,float(v[peak]))
    recovered=next((j for j in range(trough+1,len(v)) if v[j]>=peak_value),None)
    recovered_date=dates[recovered].strftime("%Y-%m-%d") if recovered is not None else None
    deepest={"drawdownPct":safe_round(100*dd[trough]),
             "peakDate":peak_date,"troughDate":dates[trough].strftime("%Y-%m-%d"),
             "recoveryDate":recovered_date,
             "peakToRecoveryCalendarDays":(dates[recovered]-pd.Timestamp(peak_date)).days if recovered is not None else None,
             "recoveryFromTroughCalendarDays":(dates[recovered]-dates[trough]).days if recovered is not None else None}
    horizon_years=(dates[-1]-dates[0]).days/365.2425
    yearret=[]
    prev=INITIAL
    for y in sorted(set(dates.year)):
        idx=np.flatnonzero(dates.year==y)[-1];asset=float(v[idx])
        yearret.append({"year":int(y),"lastDate":dates[idx].strftime("%Y-%m-%d"),
                        "returnPct":safe_round((asset/prev-1)*100),
                        "closingTWD":safe_round(asset,2)})
        prev=asset
    rolling=[];end_dt=dates[-1]
    # True calendar five-year (not 5*252 or only nonoverlapping calendar buckets).
    for i,start in enumerate(dates):
        goal=start+pd.DateOffset(years=5)
        if goal>end_dt:break
        j=int(dates.searchsorted(goal,side="left"))
        if j>=len(dates):continue
        start_value=INITIAL if i==0 else float(v[i])
        ret=100*(float(v[j])/start_value-1)
        rolling.append({"start":start.strftime("%Y-%m-%d"),"end":dates[j].strftime("%Y-%m-%d"),"returnPct":safe_round(ret)})
    ranked=sorted(rolling,key=lambda z:z["returnPct"])
    # Count longest continuous underwater calendar period, include unfinished ongoing stretches.
    peak_nav=INITIAL;underwater_start=None;worst_span=0;worst_period=None
    for i,val in enumerate(v):
        if val>=peak_nav-1e-7:
            if underwater_start is not None:
                days=(dates[i]-underwater_start).days
                if days>worst_span:worst_span=days;worst_period={"start":underwater_start.strftime("%Y-%m-%d"),"recovered":dates[i].strftime("%Y-%m-%d")}
                underwater_start=None
            peak_nav=val
        elif underwater_start is None:underwater_start=dates[max(0,i-1)]
    ongoing=None
    if underwater_start is not None:
        days=(dates[-1]-underwater_start).days
        ongoing={"since":underwater_start.strftime("%Y-%m-%d"),"calendarDays":days}
        if days>worst_span:worst_span=days;worst_period={"start":underwater_start.strftime("%Y-%m-%d"),"recovered":None}
    return {"start":START,"end":END,"tradingValuationDates":len(dates),
      "startingTWD":int(INITIAL),"endingTWD":safe_round(v[-1],2),
      "netReturnPct":safe_round(100*(v[-1]/INITIAL-1)),
      "cagrPct":safe_round(100*((v[-1]/INITIAL)**(1/horizon_years)-1)),
      "maxDrawdownPct":safe_round(100*min(dd)),"deepestDrawdown":deepest,
      "longestUnderwaterDays":worst_span,"longestUnderwaterPeriod":worst_period,
      "underwaterAtEnd":ongoing,
      "rollingFiveYear":{"n":len(rolling),"worst":ranked[0] if ranked else None,
                         "medianReturnPct":safe_round(np.median([x["returnPct"] for x in rolling])) if rolling else None,
                         "best":ranked[-1] if ranked else None},
      "calendarYears":yearret}
def portfolio(dates,nav,w,rebalancing):
    # One unit of each sleeve == its pre-existing hypothetical 1,000,000 TWD ledger.
    # No cross-sleeve trades after inception for buy-and-hold of sleeve weights.
    units={a:float(frac) for a,frac in w.items()}
    series=[];events=[]
    for i,d in enumerate(dates):
        if rebalancing=="annual" and i>0 and d.year!=dates[i-1].year and len(units)>1:
            prev={a:float(nav[a].iat[i-1])*units[a] for a in units}
            wealth=sum(prev.values());desired={a:wealth*w[a] for a in units}
            cost=sum(abs(desired[a]-prev[a])*REBAL_FEE for a in units)
            cost+=sum(max(0,prev[a]-desired[a])*REBAL_L2_SELL_TAX for a in units if a.startswith("L2_"))
            if cost>=wealth:raise RuntimeError("Impossibly high annual rebalancing friction")
            wealth_after=wealth-cost
            units={a:(wealth_after*w[a]/float(nav[a].iat[i-1])) for a in units}
            events.append({"effectiveDate":d.strftime("%Y-%m-%d"),"pricedAtLastValuationDate":dates[i-1].strftime("%Y-%m-%d"),
                "turnoverTWD":safe_round(sum(abs(prev[a]-desired[a]) for a in w),2),
                "costTWD":safe_round(cost,2)})
        series.append(sum(units[a]*float(nav[a].iat[i]) for a in units))
    equity=np.array(series,dtype=float)
    last_exposure={a:safe_round(100*units[a]*nav[a].iat[-1]/equity[-1],2) for a in units}
    return equity,last_exposure,events
def verify_archive_summary(raw,fx,calendar,aligned):
    idx=json.loads((BASE/"index.json").read_text(encoding="utf-8"))
    keys={("00675_crash_sma5","BASE"):"L2_SMA10",("00675_2018","BUY_HOLD"):"L2_HOLD",
      ("qqq_vt","VT__BUY_HOLD"):"VT",("qqq_vt","QQQ__BUY_HOLD"):"QQQ"}
    audit={}
    for (study,case),asset in keys.items():
        match=next((s for s in idx["studies"] if s["id"]==study),None)
        if not match:raise RuntimeError("Missing frozen archive study "+study)
        mod=next((m for m in match["models"] if m["id"]==case),None)
        if not mod:raise RuntimeError("Missing reference "+str((study,case)))
        if len(raw[asset])!=mod["sessions"]:raise RuntimeError("Archived sessions mismatch "+asset)
        ending=float(aligned[asset].iat[-1]);reference=float(mod["endTWD"])
        drift=(ending/reference-1)*100
        if abs(drift)>.15:raise RuntimeError(asset+" FX or archive drift "+str(drift))
        audit[asset]={"archiveCurve":ASSETS[asset],"reportedEndTWD":reference,
                      "joinedEndTWD":safe_round(ending,2),"deltaPct":safe_round(drift,5),
                      "marketSessions":len(raw[asset])}
    quote_days=len(fx);last=fx.index[-1]
    return {"sourceCurveParity":audit,"fxFirstQuote":safe_round(float(fx.loc[:START].iloc[-1]),5),
            "fxLastAsOfEnd":safe_round(float(fx.loc[:END].iloc[-1]),5),
            "fxFetchedTradingDays":quote_days,"fxLastQuoteDate":last.strftime("%Y-%m-%d"),
            "valuationCalendarDates":len(calendar)}
def main():
    began=time.monotonic();OUT.mkdir(parents=True,exist_ok=True)
    raw={};docs={}
    for asset in ASSETS:raw[asset],docs[asset]=load_curve(asset)
    if len(raw["L2_SMA10"])!=2128 or len(raw["VT"])!=2203 or len(raw["QQQ"])!=2203:
        raise RuntimeError("Missing validated asset history")
    fx=market_usdtwd()
    calendar,nav,spot=align_curves(raw,fx)
    audit=verify_archive_summary(raw,fx,calendar,nav)
    reports=[];equity={}
    for rebalancing in ("none","annual"):
        for name,weights in CONFIGS.items():
            curve,final_w,events=portfolio(calendar,nav,weights,rebalancing)
            metrics=curve_summary(calendar,curve)
            reports.append({"id":name,"rebalancing":rebalancing,
                "startWeightsPct":{a:int(100*w) for a,w in weights.items()},
                "endingExposurePct":final_w,"annualRebalanceEvents":len(events),
                "annualRebalanceCostTWD":safe_round(sum(e["costTWD"] for e in events),2),
                "metrics":metrics})
            key=name+"__"+rebalancing
            equity[key]={"dailyTWD":[safe_round(v,2) for v in curve],"rebalances":events}
            print("ALLOCATION_COMPLETED",name,rebalancing,
                json.dumps({"netPct":metrics["netReturnPct"],"mddPct":metrics["maxDrawdownPct"],
                  "worst5Y":metrics["rollingFiveYear"]["worst"],
                  "longestUnderwaterDays":metrics["longestUnderwaterDays"]},ensure_ascii=False),flush=True)
    primary=next(r for r in reports if r["id"]=="L2_SMA10_100" and r["rebalancing"]=="none")
    legacy=audit["sourceCurveParity"]["L2_SMA10"]["reportedEndTWD"]
    if abs(primary["metrics"]["endingTWD"]-legacy)>.10:raise RuntimeError("Pure 00675 strategy fails archival parity")
    if len(reports)!=len(CONFIGS)*2:raise RuntimeError("Incomplete allocation variants")
    summary={"version":"L2_SMA10_VT_QQQ_TWD_PORTFOLIO_2018_2026_LOCKED_V1",
       "generatedAtUTC":datetime.now(timezone.utc).isoformat(),"window":[START,END],
       "initialCapitalTWD":INITIAL,"dailyValuationDates":len(calendar),
       "portfolioWeights":CONFIGS,"sources":ASSETS,"audit":audit,
       "method":{"00675L":"Frozen market index SMA10 -2% three consecutive closes or -4% single-day index panic triggers sale, SMA10+1% reentry; trade next TWSE open; archived complete account curve with actual historical commission, sale tax and 0.1% slippage each side.",
                 "VT_QQQ":"Frozen whole-share USD buy-and-hold accounts; already include each-side broker fee and 0.1% modeled slippage; adjusted-price dividend reinvestment approximation.",
                 "currency":"Historical Yahoo TWD=X USD/TWD daily reference, asof-backward on each joint valuation calendar date; no interpolated future quotes.",
                 "calendar":"Union of Taiwan and US market dates; last observed stale closing price carries over holidays. Same calendar date valuation is defined after US close, hours after TWSE; only independent asset sleeve orders, no cross-asset day-of-close market signal.",
                 "fixedAllocation":"Initial allocated weights buy distinct strategy sleeves, then never cross-rebalance; winners can grow much larger than initial assigned allocation.",
                 "annualAllocation":"On first joint valuation day of next calendar year, rebalance based only on the preceding completed valuation date with additional 0.1425% broker+0.1% slippage on traded amount and Taiwan ETF selling tax; approximate cross-market execution.",
                 "cash":"Leverage sleeve holds TWD cash during its exit signals; no debt and no interest on uninvested TWD cash. VT/QQQ hold USD exposure throughout.",
                 "maxDrawdown":"Full daily TWD portfolio mark-to-market peak-to-trough, not trade-exit-only.",
                 "fiveYear":"Every joint valuation calendar date with five complete forward calendar years, use the first observation at or after its five-year anniversary."},
       "assetMetadata":{"symbol00675":"00675L.TW","currency00675":"TWD",
                        "globalEquity":"VT","usGrowth":"QQQ","fx":"TWD=X"},
       "results":reports,
       "limitations":["The observed 2018-2026 period is dominated by strong technology-led returns; do not project these returns into 2026-2031.",
         "Public archived 2018-2026 strategy variants and backtest choices were already studied; 2026 is not genuinely blind testing.",
         "QQQ and VT overlap heavily in US mega-cap technology holdings; neither eliminates equity bear-market risk.",
         "Asynchronous Taiwan/US trading calendars and daily Yahoo FX close references are approximations for historical valuation, not executable simultaneous prices.",
         "Rebalance on the previous complete joint valuation as a close-based approximation; real FX/US/TW order timing and spreads add execution friction.",
         "US ETF adjusted OHLC approximate dividend reinvestment without US nonresident 30% dividend withholding tax; actual after-tax wealth can be lower.",
         "Historical archived account curves already include the respective broker and 0.1% slippage assumptions but do not include foreign exchange conversion spreads, cross-border transfer fees, broker FX margins or local income tax.",
         "Terminal US archives have hypothetical liquidation transaction costs; ongoing rebalancing trades use approximate extra fees.",
         "FX daily spots can be revised and may not precisely match broker settlement FX rates.",
         "Only 2018-2026 historical records, not the 2008 crash. Rolling five-year windows overlap and are highly correlated.",
         "Leveraged 00675L targets 2x DAILY Taiwan index, not guaranteed 2x five-year cumulative returns.",
         "Risk-off only triggers after the close; overnight price gaps or market halts may cause much worse losses.",
         "Annual sleeves are mathematically scaled archived strategy NAVs; whole-share and discrete FX settlement not replayed on each rebalance."]}
    (OUT/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    (OUT/"equity.json").write_text(json.dumps({"version":summary["version"],"dates":[d.strftime("%Y-%m-%d") for d in calendar],
                        "portfolios":equity},ensure_ascii=False,separators=(",",":")),encoding="utf-8")
    (OUT/"fx.json").write_text(json.dumps({"source":"Yahoo Finance TWD=X (USD/TWD) as-of reference quote on each joint valuation date",
                   "dates":[d.strftime("%Y-%m-%d") for d in calendar],
                   "usdtwd":[safe_round(float(x),5) for x in spot]},ensure_ascii=False,separators=(",",":")),encoding="utf-8")
    print("ALLOCATION_FINAL_COMPLETE",json.dumps({"n":len(reports),"valuationDays":len(calendar),
         "frozenETFParity":True,"maxDDVerified":True,"fiveYearWindows":primary["metrics"]["rollingFiveYear"]["n"],
         "seconds":round(time.monotonic()-began,1)},ensure_ascii=False),flush=True)
if __name__=="__main__":main()
