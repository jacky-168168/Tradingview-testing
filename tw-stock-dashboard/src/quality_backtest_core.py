"""Non-optimised monthly as-of growth vs ROE/PB portfolio audit.
At month-end close form Top10, buy NEXT trading session adjusted open,
exit next month first open. Net of explicitly modeled costs.
Report monthly (NOT daily) Sharpe and max drawdown.
"""
from __future__ import annotations
import math
from datetime import date

BUY=.002425 # 0.1425% brokerage + 0.1% slippage
SELL=.005425 # 0.1425% brokerage + 0.3% tax + 0.1% slippage
TOP=10
MIN_NAMES=5
def adjopen(row):
    try:
        a=float(row["open"]);c=float(row["close"]);v=float(row["adjclose"])
        x=a*v/c
        return x if a>0 and c>0 and v>0 and math.isfinite(x) else None
    except (KeyError,ValueError,TypeError,ZeroDivisionError):return None
def rows_by_day(df):
    return {str(z["date"]):z for z in df.to_dict("records")} if df is not None and not df.empty else {}
def month_signal_days(days):
    last={}
    for day in sorted(days):last[day[:7]]=day
    return [last[k] for k in sorted(last)]
def screen(universe,bars,mops,quality,day):
    growth=[];verified=[]
    for s in universe:
        code=str(s["code"]);m="sii" if s["market"]=="上市" else "otc"
        sy=code+(".TW" if m=="sii" else ".TWO")
        p=bars.get(sy,{}).get(day)
        if p is None:continue
        close=p.get("close")
        f=mops.profile(s["market"],code,day,close)
        eps=f.get("epsYtdYoYPct");rev=f.get("revenueYoYPct")
        if any(v is None for v in (eps,rev,f.get("ttmEPS"))):continue
        if eps<10 or rev<10 or f["ttmEPS"]<=0 or (f.get("revenue12mHighRatioPct") or 0)<80:continue
        rank=.6*max(0,min(200,eps))+.4*max(0,min(200,rev))
        entry={"symbol":sy,"code":code,"rank":round(rank,2),"epsYoY":eps,"revYoY":rev,
               "epsAvailableFrom":f["epsAvailableFrom"],"revenueAvailableFrom":f["revenueAvailableFrom"]}
        assert entry["epsAvailableFrom"]<=day and entry["revenueAvailableFrom"]<=day
        growth.append(entry)
        if quality is None:continue
        q=quality.at(m,code,day);roe=q["roePct"];pb=q["pbRatio"];hist=q["pbHistoryPercentile3Y"]
        if roe is None or pb is None or hist is None:continue
        if roe>=15 and .3<=pb<=12 and hist<=50:
            assert q["roeAvailableFrom"]<=day and q["pbAsOf"]<=day
            verified.append({**entry,"rank":round(rank+.7*min(roe,60)+.3*(100-hist),2),
                "roePct":roe,"pb":pb,"pbPercentile":hist,
                "roeAvailableFrom":q["roeAvailableFrom"],"pbAsOf":q["pbAsOf"]})
    order=lambda x:(-x["rank"],x["code"])
    return sorted(growth,key=order)[:TOP],sorted(verified,key=order)[:TOP]
def period_return(selections,bars,entry,exit):
    if len(selections)<MIN_NAMES:return None,"min_names"
    returns=[]
    for x in selections:
        stock=bars.get(x["symbol"],{})
        p=adjopen(stock.get(entry,{}));q=adjopen(stock.get(exit,{}))
        if p is None or q is None:return None,"missing_adjusted_open"
        returns.append(q/p*(1-SELL)/(1+BUY)-1)
    return sum(returns)/len(returns),"ok"
def summary(points,start_date,end_date):
    good=[r for r in points if r["status"]=="ok"]
    if not good:return {"status":"insufficient_data","periods":len(points),"tradedMonths":0}
    capital=1_000_000;curve=[capital];monthly=[]
    for row in points:
        if row["status"]!="ok":
            return {"status":"incomplete_history","periods":len(points),"tradedMonths":len(good),
                "note":"One or more monthly intervals lacked sufficient validated trades"}
        capital*=1+row["netReturn"]
        curve.append(capital);monthly.append(row["netReturn"])
    high=curve[0];dd=0
    for v in curve[1:]:
        high=max(high,v);dd=min(dd,v/high-1)
    years=(date.fromisoformat(end_date)-date.fromisoformat(start_date)).days/365.2425
    mu=sum(monthly)/len(monthly);var=sum((r-mu)**2 for r in monthly)/(len(monthly)-1) if len(monthly)>1 else 0
    sharpe=math.sqrt(12)*mu/math.sqrt(var) if var>1e-16 else None
    return {"status":"ok","periods":len(points),"tradedMonths":len(monthly),
        "capitalStartTWD":1_000_000,"capitalEndTWD":round(capital,2),
        "totalReturnPct":round(100*(capital/1_000_000-1),3),
        "cagrPct":round(100*((capital/1_000_000)**(1/years)-1),3) if years>0 else None,
        "monthlySharpeRf0":round(sharpe,3) if sharpe is not None else None,
        "monthlyMaxDrawdownPct":round(100*dd,3),
        "positiveMonths":sum(x>0 for x in monthly),"monthlyWinRatePct":round(100*sum(x>0 for x in monthly)/len(monthly),2),
        "note":"Maximum drawdown and Sharpe are calculated from MONTHLY snapshots (daily intramonth declines are not captured)."}
def simulate(universe,bars,mops,quality,days):
    signals=month_signal_days(days);next_day={d:days[i+1] for i,d in enumerate(days[:-1])}
    report={"growth":[],"quality":[]}
    for i in range(len(signals)-1):
        signal=signals[i];end_signal=signals[i+1]
        entry=next_day.get(signal);exit=next_day.get(end_signal)
        if not entry or not exit:continue
        g,q=screen(universe,bars,mops,quality,signal)
        for name,picks in (("growth",g),("quality",q)):
            ret,status=period_return(picks,bars,entry,exit)
            report[name].append({"signal":signal,"entry":entry,"exit":exit,
                "n":len(picks),"status":status,"netReturn":ret,
                "top10Codes":[x["code"] for x in picks]})
    return report
