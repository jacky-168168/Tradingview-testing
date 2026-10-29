#!/usr/bin/env python3
"""Historical 5m 09:30 breakout study. No lookahead or trading orders."""
import json, random, statistics, sys, traceback
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import pandas as pd
import requests
import yfinance as yf

TZ=ZoneInfo("Asia/Taipei")
OUT=Path("tw-stock-dashboard/docs/data/research/early_breakout_0930/backtest.json")
SEED=20261029
N_RANDOM=500
WATCH=["2352","2491","8240","6233","7750","2465"]
OTC={"8240","6233"}
FEE_SIDE=0.001425
SELL_TAX=0.003
SLIP_SIDE=0.001
VARIANTS=("breakout","breakout_rvol2","breakout_rvol2_vwap")

def net_pct(entry, exit_):
    return 100.0*((exit_*(1-FEE_SIDE-SELL_TAX-SLIP_SIDE))/(entry*(1+FEE_SIDE+SLIP_SIDE))-1.0)

def load_universe():
    url="https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"
    r=requests.get(url,timeout=25,headers={"User-Agent":"Mozilla/5.0"});r.raise_for_status()
    a=r.json()
    if not isinstance(a,list):raise ValueError("TWSE list malformed")
    codes=sorted(set(str(x.get("Code","")).strip() for x in a if len(str(x.get("Code","")).strip())==4 and str(x.get("Code","")).strip().isdigit()))
    if len(codes)<500:raise ValueError("TWSE list too short")
    selectable=[c for c in codes if c not in WATCH]
    return random.Random(SEED).sample(selectable,min(N_RANDOM,len(selectable))),len(codes)

def fetch_one(code):
    ticker=code+(".TWO" if code in OTC else ".TW")
    start=(datetime.now(TZ)-timedelta(days=59)).strftime("%Y-%m-%d")
    end=(datetime.now(TZ)+timedelta(days=1)).strftime("%Y-%m-%d")
    try:
        f=yf.Ticker(ticker).history(start=start,end=end,interval="5m",auto_adjust=False,actions=False,timeout=18)
        if f is None or f.empty: return code,[], "no_history"
        if f.index.tz is None: f.index=f.index.tz_localize(TZ)
        else:f.index=f.index.tz_convert(TZ)
        f=f.sort_index().between_time("09:00","13:30")
        f=f[["Open","High","Low","Close","Volume"]].dropna()
        f=f[(f["Close"]>0)&(f["Volume"]>=0)]
        byday={}
        for d,g in f.groupby(f.index.strftime("%Y-%m-%d")):
            if len(g)>=6:byday[d]=g
        dates=sorted(byday)
        rows=[]
        for j in range(20,len(dates)):
            date=dates[j]; day=byday[date]; prev=byday[dates[j-1]]
            b=day.between_time("09:00","09:25")
            nextbar=day.between_time("09:30","09:30")
            exitbar=day.between_time("13:25","13:30")
            if len(b)<5 or nextbar.empty: continue
            if j < len(dates)-1 and day.index.max().strftime("%H:%M")<"13:20":continue
            prevclose=float(prev["Close"].iloc[-1]);prevhigh=float(prev["High"].max())
            signal=float(b["Close"].iloc[-1]);entry=float(nextbar["Open"].iloc[0])
            if not 0<prevclose or not 0<entry or signal<=prevhigh:continue
            gain=(signal/prevclose-1)*100
            if gain<2.5:continue
            # Conservatively exclude near-limit-up entries incl. tick-size rounding (9.6% or more).
            if entry/prevclose>=1.096:continue
            h=[byday[x] for x in dates[j-20:j]]
            earlyVol=[float(g.between_time("09:00","09:25")["Volume"].sum()) for g in h]
            if len(earlyVol)<20 or min(earlyVol)<=0:continue
            avgEarly=sum(earlyVol)/len(earlyVol)
            if avgEarly<=0:continue
            volratio=float(b["Volume"].sum())/avgEarly
            typical=(b["High"]+b["Low"]+b["Close"])/3
            vwap=float((typical*b["Volume"]).sum()/max(b["Volume"].sum(),1))
            avgValue=sum(float((g["Close"]*g["Volume"]).sum()) for g in h)/20
            if avgValue<10000000 or signal<10:continue
            complete=day.index.max().strftime("%H:%M")>="13:20"
            nextdate=dates[j+1] if j+1<len(dates) else None
            nextday=byday[nextdate] if nextdate else None
            next_complete=nextday is not None and nextday.index.max().strftime("%H:%M")>="13:20"
            nn=nextday.between_time("09:30","09:30") if nextday is not None else None
            rec={"code":code,"date":date,"sessionComplete":complete,"nextDate":nextdate,
                 "nextDateMaxTime":nextday.index.max().strftime("%H:%M") if nextday is not None else None,
                 "entryTime":"09:30","entry":round(entry,4),"signal":round(signal,4),
                 "priorHigh":round(prevhigh,4),"gainAt0930Pct":round(gain,3),
                 "earlyRvol20":round(volratio,3),"vwap":round(vwap,4),
                 "exitLastBarTime":day.index.max().strftime("%H:%M"),
                 "netSameDayPct":round(net_pct(entry,float(day["Close"].iloc[-1])),4) if complete else None,
                 "netNextClosePct":round(net_pct(entry,float(nextday["Close"].iloc[-1])),4) if next_complete else None,
                 "netNext0930Pct":round(net_pct(entry,float(nn["Open"].iloc[0])),4) if nn is not None and not nn.empty else None}
            rows.append(rec)
        return code,rows,None
    except Exception as exc:return code,[],type(exc).__name__+": "+str(exc)[:120]

def summarize(rows, key):
    a=[float(x[key]) for x in rows if x[key] is not None]
    if not a:return {"n":0,"winRatePct":None,"avgNetPct":None,"medianNetPct":None,"profitFactor":None}
    wins=sum(x>0 for x in a);pos=sum(x for x in a if x>0);neg=-sum(x for x in a if x<0)
    return {"n":len(a),"winRatePct":round(100*wins/len(a),2),"avgNetPct":round(statistics.mean(a),3),
            "medianNetPct":round(statistics.median(a),3),"profitFactor":round(pos/neg,3) if neg else None}

def main():
    sample,total=load_universe()
    universe=sample+WATCH
    signals=[];failed={};success=0
    with ThreadPoolExecutor(max_workers=4) as executor:
        jobs={executor.submit(fetch_one,c):c for c in universe}
        for future in as_completed(jobs):
            code,found,error=future.result()
            if error:failed[code]=error
            else:success+=1;signals.extend(found)
    group_results={}
    for group,codes in (("random_listed",set(sample)),("six_pictured",set(WATCH)),("combined",set(universe))):
        base=[r for r in signals if r["code"] in codes and r["sessionComplete"]]
        records={}
        for variant in VARIANTS:
            subset=[r for r in base if variant=="breakout" or
              (r["earlyRvol20"]>=2 and (variant!="breakout_rvol2_vwap" or r["signal"]>r["vwap"]))]
            records[variant]={"signalCount":len(subset),"distinctStockCount":len(set(x["code"] for x in subset)),
                "sameDay":summarize(subset,"netSameDayPct"),
                "nextClose":summarize(subset,"netNextClosePct"),
                "next0930":summarize(subset,"netNext0930Pct"),
                "exampleTrades":sorted(subset,key=lambda x:x["date"],reverse=True)[:25]}
        group_results[group]=records
    output={"generatedAt":datetime.now(TZ).isoformat(),"status":"ok" if success else "no_history",
        "method":"5m Yahoo; 09:00-09:25 confirmed bars -> 09:30 next-bar open; previous day's 5m high; 20 prior days SAME 30-minute volume for RVOL; 20-day average liquidity; no lookahead",
        "sampling":{"seed":SEED,"twseListedUniverseAtRun":total,"randomListedSample":len(sample),
                    "sixPictured":WATCH,"successfullyFetched":success,"failed":len(failed),
                    "failureExamples":dict(list(sorted(failed.items()))[:30]),
                    "bias":"Survivorship bias: today's listed universe; six featured stocks were chosen after seeing their rise and are evaluated separately; random is listed-only."},
        "rules":{"signalTime":"09:30","returnAtSignalMinPct":2.5,"breakYesterdayHigh":True,
                 "rvolThreshold":2,"vwapFilter":True,"avgDailyTurnoverMinTWD":10000000,
                 "excludeLimitUpAtEntryPct":9.6,"minPrice":10,
                 "fill":"09:30 bar open, not 09:25 close","exit":"same-day last observed bar after 13:20 (5m, NOT necessarily official 13:30 auction), next day same convention, or 09:30",
                 "brokerFeeOneWayPct":FEE_SIDE*100,"sellTaxPct":SELL_TAX*100,"slippageOneWayPct":SLIP_SIDE*100,
                 "costAtFlatPricePct":round(net_pct(100,100),3)},
        "results":group_results,
        "today0930Candidates":{"date":datetime.now(TZ).strftime("%Y-%m-%d"),"allRandomPlusSix":[r for r in signals if not r["sessionComplete"] and r["date"]==datetime.now(TZ).strftime("%Y-%m-%d")],"picturedSix":[r for r in signals if not r["sessionComplete"] and r["date"]==datetime.now(TZ).strftime("%Y-%m-%d") and r["code"] in WATCH]},
        "caveats":["Yahoo intraday bars may be missing or adjusted; last available 5m bar can be earlier than official closing auction; 09:30 opening price does not guarantee tradable fills.",
         "The full 1,988-stock market is not covered; random sample excludes OTC except explicit pictured 6233/8240.",
         "Last 60 calendar days only, earlier 20 sessions serve as warm-up; single-window sample is not out-of-sample.",
         "Trade returns are equal-weight hypothetical signal returns, not portfolio returns; simultaneous signals can exceed capital.",
         "No pre-open screening or timestamp earlier than 09:30 is claimed."]}
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(output,ensure_ascii=False,indent=2),encoding="utf-8")
    for group,variants in group_results.items():
        for v,r in variants.items():
            print(json.dumps({"group":group,"variant":v,"signals":r["signalCount"],"day":r["sameDay"],"nextDay":r["nextClose"]},ensure_ascii=False))
    print("coverage",json.dumps(output["sampling"],ensure_ascii=False)[:1400])
    if success<20:print("WARNING: data availability too low for inference")
    return 0 if success else 2

if __name__=="__main__":
    if "--self-test" in sys.argv:
        assert -0.85<net_pct(100,100)<-0.7
        assert summarize([{"x":1},{"x":-2}],"x")["n"]==2
        print("self-test passed")
    else:sys.exit(main())
