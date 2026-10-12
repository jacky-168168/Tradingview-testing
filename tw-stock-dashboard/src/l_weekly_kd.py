"""L strategy: weekly KD(9,3,3) low-zone bullish crossover AND released monthly revenue growth.
Uses finished W-FRI candles and conservatively dated MOPS historical revised files only.
No intraday weekly crossover, no unreleased monthly data, no retroactive live signal.
"""
from __future__ import annotations
import argparse,json,math
from datetime import datetime,timedelta
from zoneinfo import ZoneInfo
import numpy as np,pandas as pd
from config import DATA_DIR,BENCHMARK
from yahoo_cache import update_many,update_symbol,to_symbol
from stock_fundamentals import MopsArchive
VERSION="L_WKD_933_LT40_REV_GROWTH_V1"
START="2023-10-01";HORIZONS=(1,2,3);COST_PCT=0.585
OUT=DATA_DIR/"research"/"l_weekly_kd"

def finite(x):
    try:
        n=float(x)
        return n if math.isfinite(n) else None
    except (ValueError,TypeError):return None

def last_completed_week(now,market_date):
    tz=ZoneInfo("Asia/Taipei")
    now=now.astimezone(tz) if now.tzinfo else now.replace(tzinfo=tz)
    current=pd.Timestamp(now.date()).to_period("W-FRI")
    market=pd.Timestamp(market_date).to_period("W-FRI")
    if market<current:return market
    if market==current and now.weekday()==4 and now.hour>=14:return current
    return current-1

def weekly_bars(frame):
    columns={"date","open","high","low","close","volume"}
    if frame is None or frame.empty or not columns.issubset(frame.columns):return pd.DataFrame()
    q=frame.copy();q["date"]=pd.to_datetime(q.date,errors="coerce")
    for name in ["open","high","low","close","volume"]:q[name]=pd.to_numeric(q[name],errors="coerce")
    q["adjclose"]=pd.to_numeric(q["adjclose"] if "adjclose" in q else q["close"],errors="coerce")
    q=q.dropna(subset=["date","open","high","low","close","volume"]).sort_values("date").drop_duplicates("date",keep="last")
    q=q[(q.close>0)&(q.open>0)&(q.high>=q.low)&(q.volume>=0)]
    if q.empty:return pd.DataFrame()
    q["adjopen"]=q.open*(q.adjclose/q.close).where((q.adjclose>0)&(q.close>0),1)
    q["week"]=q.date.dt.to_period("W-FRI")
    w=q.groupby("week",sort=True).agg(entryDate=("date","first"),signalDate=("date","last"),open=("open","first"),adjopen=("adjopen","first"),high=("high","max"),low=("low","min"),close=("close","last"),adjclose=("adjclose","last"),volume=("volume","sum"))
    hi=w.high.rolling(9,min_periods=9).max();lo=w.low.rolling(9,min_periods=9).min()
    rsv=100*(w.close-lo)/(hi-lo).replace(0,np.nan)
    k=50.;d=50.;ks=[];ds=[]
    for v in rsv:
        if not math.isfinite(float(v)):ks.append(np.nan);ds.append(np.nan);continue
        k=(2*k+float(v))/3;d=(2*d+k)/3
        ks.append(k);ds.append(d)
    w["K"]=ks;w["D"]=ds
    w["golden"]=(w.K.shift(1)<=w.D.shift(1))&(w.K>w.D)&w.K.notna()&w.D.notna()
    w["strict40"]=w.golden&(w.K<40)&(w.D<40)
    w["signalDate"]=w.signalDate.dt.strftime("%Y-%m-%d")
    w["entryDate"]=w.entryDate.dt.strftime("%Y-%m-%d")
    return w

def read_revenue(data_dir=DATA_DIR):
    root=data_dir/"research"/"n_canslim"
    try:
        coverage=json.loads((root/"fundamental_coverage.json").read_text(encoding="utf-8"))
        if coverage.get("failures") or int(coverage.get("revenueRows") or 0)<20000:raise ValueError("historical MOPS revenue source incomplete")
        rows=json.loads((root/"monthly_revenue.json").read_text(encoding="utf-8"))
        if len(rows)!=coverage["revenueRows"]:raise ValueError("historical MOPS revenue count mismatch")
        return MopsArchive(rows,[]),None
    except (OSError,ValueError,KeyError,TypeError) as exc:return None,str(exc)[:180]

def revenue_ok(archive,info,day):
    f=archive.profile(info["market"],info["code"],day,None)
    mom=finite(f.get("revenueMoMPct"));yoy=finite(f.get("revenueYoYPct"))
    if (mom is None or mom<=0) and (yoy is None or yoy<=0):return None
    return {"revenueFiscal":f["revenueFiscal"],"revenueAvailableFrom":f["revenueAvailableFrom"],
            "revenueMoMPct":mom,"revenueYoYPct":yoy}

def to_pick(info,period,row,revenue):
    return {"code":str(info["code"]),"name":str(info.get("name") or info["code"]),"market":info["market"],
            "theme":str(info.get("theme") or info.get("industry") or "—"),"model":"L",
            "signalDate":str(row["signalDate"]),"signalWeek":period.end_time.strftime("%Y-%m-%d"),
            "close":round(float(row["close"]),2),"weekK":round(float(row["K"]),2),"weekD":round(float(row["D"]),2),
            "weekVolume":int(row["volume"]),"signal":"週KD(9,3,3)低檔金叉＋已公告營收成長",
            **revenue}

def select_current(universe,histories,market_date,now=None,limit=20,archive=None):
    now=now or datetime.now(ZoneInfo("Asia/Taipei"))
    target=last_completed_week(now,market_date)
    if archive is None:archive,error=read_revenue()
    else:error=None
    status={"version":VERSION,"dataDate":market_date,"signalWeek":target.end_time.strftime("%Y-%m-%d"),
            "state":"ready" if archive is not None else "unavailable","error":error,"strictCandidates":0,
            "crossoverCount":0,"weeklyCovered":0,"marketUniverse":len(universe),
            "weeklyBarRule":"Only fully completed W-FRI candles, never unclosed weekly KD",
            "revenueRule":"latest conservatively available MOPS month: MoM>0 OR YoY>0"}
    if archive is None:return [],status
    out=[]
    for info in universe:
        h=histories.get(to_symbol(info["code"],info["market"]))
        w=weekly_bars(h)
        if len(w)<26 or target not in w.index:continue
        status["weeklyCovered"]+=1;r=w.loc[target]
        if not bool(r["strict40"]):continue
        status["crossoverCount"]+=1
        rev=revenue_ok(archive,info,r["signalDate"])
        if rev is None:continue
        out.append(to_pick(info,target,r,rev))
    status["strictCandidates"]=len(out)
    out.sort(key=lambda x:(x["weekK"],-x["weekVolume"],x["code"]))
    status["publishedTop"]=min(limit,len(out))
    return out[:limit],status

def trades_for_stock(info,weekly,archive,market_date,now=None):
    rows=[]
    last=last_completed_week(now or datetime.now(ZoneInfo("Asia/Taipei")),market_date)
    eligible=weekly.index[weekly.index<=last]
    w=weekly.loc[eligible]
    if len(w)<26:return rows
    for i in range(25,len(w)):
        r=w.iloc[i];period=w.index[i];date=str(r["signalDate"])
        if date<START or not bool(r["strict40"]):continue
        rev=revenue_ok(archive,info,date)
        if rev is None:continue
        p=to_pick(info,period,r,rev)
        for horizon in HORIZONS:
            # Signal at Friday close; enter NEXT trading week's first opening price,
            # exit end of week number horizon. Exclude incomplete forward weeks.
            # A partial/trading-halt week with no bars is NOT a valid horizon.
            if i+horizon>=len(w) or (w.index[i+horizon].ordinal-period.ordinal)!=horizon or (w.index[i+1].ordinal-period.ordinal)!=1:continue
            target=w.iloc[i+horizon];entry=w.iloc[i+1]
            a=finite(entry.adjopen);b=finite(target.adjclose)
            if a is None or b is None or a<=0 or b<=0:continue
            gross=(b/a-1)*100
            rows.append({**p,"horizon":horizon,"entryDate":str(entry["entryDate"]),"exitDate":str(target["signalDate"]),
                         "grossPct":round(gross,4),"netPct":round(gross-COST_PCT,4)})
    return rows

def summarize(trades):
    out={}
    for scope,subset in [("all",trades),("2026",[t for t in trades if t["signalDate"].startswith("2026")])]:
        out[scope]={}
        for h in HORIZONS:
            group=[t["netPct"] for t in subset if t["horizon"]==h]
            n=len(group)
            if not n:
                out[scope][str(h)]={"n":0,"winRatePct":None,"avgNetPct":None,"medianNetPct":None,"avgProfitPct":None,"avgLossPct":None}
                continue
            wins=[x for x in group if x>0];loss=[x for x in group if x<=0]
            out[scope][str(h)]={"n":n,"winRatePct":round(len(wins)/n*100,2),
                                  "avgNetPct":round(float(np.mean(group)),3),"medianNetPct":round(float(np.median(group)),3),
                                  "avgProfitPct":round(float(np.mean(wins)),3) if wins else None,
                                  "avgLossPct":round(float(np.mean(loss)),3) if loss else None}
    return out

def backtest(universe,histories,archive,market_date):
    alltrades=[];by_symbol=0;valid=0
    for info in universe:
        w=weekly_bars(histories.get(to_symbol(info["code"],info["market"])))
        if len(w)<26:continue
        valid+=1;one=trades_for_stock(info,w,archive,market_date)
        if one:by_symbol+=1;alltrades.extend(one)
    report={"version":VERSION,"asOf":market_date,"start":START,"weeks":HORIZONS,
            "entry":"signal week's completed closing signal -> next week's first OPEN",
            "exit":"end of week 1/2/3 after signal (only completed future weeks)",
            "feeAndTaxPct":COST_PCT,"priceBasis":"Yahoo adjusted historical daily closes and adjusted next-week opens",
            "universe":"currently listed TWSE+TPEx including historic price records (survivorship bias possible)",
            "fundamentals":"Official MOPS revised historic monthly revenue with conservative 16th availability proxy (not immutable as-reported archive)",
            "filters":"completed weekly KD(9,3,3) golden cross where both K and D <40; released latest MoM>0 OR YoY>0",
            "fullUniverse":len(universe),"stockPriceCoverage":valid,"stocksWithTrades":by_symbol,
            "statistics":summarize(alltrades)}
    return report,alltrades

def main():
    from pipeline import load_universe
    now=datetime.now(ZoneInfo("Asia/Taipei"))
    archive,error=read_revenue()
    if archive is None:raise RuntimeError("L historical revenue unavailable: "+str(error))
    universe=load_universe()
    _,benchmark,err=update_symbol(BENCHMARK,datetime(2022,10,1),now.replace(tzinfo=None))
    if err or benchmark.empty:raise RuntimeError("benchmark history missing "+str(err))
    market_date=str(benchmark.date.iloc[-1])
    print("L market universe",len(universe),"market_date",market_date,flush=True)
    histories,errors=update_many([(x["code"],x["market"]) for x in universe],datetime(2022,10,1),now.replace(tzinfo=None))
    print("L historical Yahoo coverage",len(histories),"fetchErrors",len(errors),flush=True)
    picks,live=select_current(universe,histories,market_date,now=now,archive=archive)
    report,trades=backtest(universe,histories,archive,market_date)
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/"summary.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    (OUT/"trades.json").write_text(json.dumps(trades,ensure_ascii=False,indent=2),encoding="utf-8")
    (OUT/"latest.json").write_text(json.dumps({"asOf":market_date,"selection":live,"rows":picks},ensure_ascii=False,indent=2),encoding="utf-8")
    print("L results",json.dumps({"stats":report["statistics"],"latest":live,"currentTop":picks[:5]},ensure_ascii=False),flush=True)
if __name__=="__main__":main()
