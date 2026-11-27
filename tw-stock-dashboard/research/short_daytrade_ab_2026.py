#!/usr/bin/env python3
"""Taiwan equity SHORT day-trading A/B, research only, 5-minute historical pilot.

Data: Yahoo Finance historical 5m OHLCV, FinMind per-symbol TaiwanStockDayTrading
point-in-time BuyAfterSale when accessible. Nothing is sent to brokerage or website.
Never assert that exchange qualification guarantees account, locate or borrow availability.
"""
from __future__ import annotations
import argparse
import concurrent.futures
import datetime as dt
import json
import math
import os
import statistics
import sys
from collections import defaultdict
from pathlib import Path
from zoneinfo import ZoneInfo

TPE=ZoneInfo("Asia/Taipei")
BASE=Path(__file__).resolve().parents[1]
UNIVERSE_SNAPSHOT=BASE/"docs/data/daily/2026-10-06.json"
ANCHORS=("2330","2317","2454","2303","2382","2603","2615","2610","3037",
         "2408","3481","3231","2376","2344","3443","3711","6669","3017",
         "1513","1519","1605","2367","2324","3661","3324","6285","3706",
         "2356","2357","2498","3045","2881","2882","2886","2884","2891")
START="2026-10-07"
END="2026-11-26"
MODES=("A_weak_continuation","B_failed_breakout")
# Full published exchange tax for day-trades (currently 0.15% sell side),
# and undiscounted stock commission 0.1425% per side; add adverse 0.05% per side.
COMMISSION=0.001425
SELL_TAX=0.0015
SLIPPAGE=0.0005
CAPITAL_NOTIONAL=100000
CAP=3
QUALITY_MIN_DAYS=10
MIN_20DAY_TURNOVER=500_000_000

def universe():
    snap=json.loads(UNIVERSE_SNAPSHOT.read_text(encoding="utf-8"))
    codes=set(ANCHORS)
    for items in snap.get("models",{}).values():
        for row in items:
            c=str(row.get("code",""))
            if len(c)==4 and c.isdigit() and "-" not in str(row.get("name","")):
                codes.add(c)
    return sorted(codes)

def quote_suffix(sym):
    # OTC symbols are NOT guessed as .TW when a quote is missing.
    return [f"{sym}.TW",f"{sym}.TWO"]

def fetch_one(code, benchmark=False):
    import yfinance as yf
    names=["^TWII"] if benchmark else quote_suffix(code)
    for symbol in names:
        try:
            frame=yf.Ticker(symbol).history(period="60d",interval="5m",
                    auto_adjust=False,prepost=False,raise_errors=False)
            if frame is None or frame.empty or len(frame)<120:
                continue
            if frame.index.tz is None:
                continue
            frame=frame.tz_convert(TPE)
            series=defaultdict(list)
            for stamp,row in frame.iterrows():
                d=stamp.date().isoformat()
                if not START<=d<=END:continue
                key=stamp.strftime("%H:%M")
                if not ("09:00"<=key<="13:30"):continue
                try:
                    op,hi,lo,cl,vol=[float(row.get(k,float("nan"))) for k in
                                     ["Open","High","Low","Close","Volume"]]
                except (ValueError,TypeError):continue
                if not all(map(math.isfinite,[op,hi,lo,cl,vol])) or min(op,hi,lo,cl)<=0:
                    continue
                if hi<max(op,cl) or lo>min(op,cl) or vol<0:continue
                series[d].append({"time":key,"o":op,"h":hi,"l":lo,"c":cl,"v":vol})
            clean={}
            for d,rows in series.items():
                rows.sort(key=lambda x:x["time"])
                if rows and rows[0]["time"]<="09:05" and rows[-1]["time"]>="13:15" and len(rows)>=47:
                    clean[d]=rows
            if len(clean)>=QUALITY_MIN_DAYS:
                return {"code":code,"vendorSymbol":symbol,"dates":clean}
        except Exception as exc:
            print("QUOTE_WARNING",code,symbol,type(exc).__name__,str(exc)[:75],file=sys.stderr)
    return {"code":code,"error":"No sufficient authentic historical 5-minute OHLCV for both open and close"}

def eligibility(code,first,last):
    """Historical point-in-time exchange stock-level eligibility, no lookahead.
    FinMind may require authentication or deny access; missing days remain unknown.
    """
    import requests
    params={"dataset":"TaiwanStockDayTrading","data_id":code,
            "start_date":first,"end_date":last}
    token=os.getenv("FINMIND_TOKEN","").strip()
    h={"Authorization":"Bearer "+token} if token else {}
    try:
        rsp=requests.get("https://api.finmindtrade.com/api/v4/data",params=params,
                         headers=h,timeout=15)
        rsp.raise_for_status()
        data=rsp.json()
        if not isinstance(data.get("data"),list):
            return {"status":"unavailable","error":str(data.get("msg","No data"))[:160],"dates":{}}
        days={}
        for row in data["data"]:
            mark=str(row.get("BuyAfterSale","")).strip()
            days[str(row.get("date"))]="eligible" if mark in {"","Y"} else "suspended"
        if not days:
            return {"status":"unavailable","error":"No day-trading qualification records returned","dates":{}}
        return {"status":"ok","dates":days}
    except Exception as e:
        return {"status":"unavailable","error":str(e)[:170],"dates":{}}

def daily_aggregates(dayrows):
    ag={}
    for d,rows in sorted(dayrows.items()):
        ag[d]={"open":rows[0]["o"],"close":rows[-1]["c"],
               "high":max(r["h"] for r in rows),"low":min(r["l"] for r in rows),
               "turnover":sum(((r["h"]+r["l"]+r["c"])/3)*r["v"] for r in rows)}
    return ag

def past_atr(daydates,dayagg,i):
    if i<14:return None
    vals=[]
    for j in range(i-14,i):
        d=daydates[j];a=dayagg[d]
        prev=dayagg[daydates[j-1]]["close"] if j else a["open"]
        vals.append(max(a["high"]-a["low"],abs(a["high"]-prev),abs(a["low"]-prev)))
    return statistics.mean(vals)/dayagg[daydates[i-1]]["close"]

def past_rvol(days,current_i,slot,vol):
    priors=[]
    for _,bars in days[max(0,current_i-12):current_i]:
        row=next((r for r in bars if r["time"]==slot),None)
        if row is not None and row["v"]>0:priors.append(row["v"])
    return vol/statistics.median(priors) if len(priors)>=8 else None

def tick_size(price):
    if price<10:return .01
    if price<50:return .05
    if price<100:return .1
    if price<500:return .5
    if price<1000:return 1.
    return 5.

def simulate(code,mode,d,rows,signal_idx,vwap,score,eligibility_mark,prior_close):
    """Confirmed signal close -> next 5m open; intrabar stop before target on ambiguity."""
    if signal_idx+1>=len(rows):return None
    src=rows[signal_idx]
    entryrow=rows[signal_idx+1]
    if entryrow["time"]>"11:05":return None
    entry=entryrow["o"]*(1-SLIPPAGE)
    lastmax=max(x["h"] for x in rows[max(0,signal_idx-2):signal_idx+1])
    stop=max(lastmax,entry*1.008)
    risk=(stop-entry)/entry
    if risk<.003 or risk>.03:return None
    target=entry-2*(stop-entry)
    exit_price=None;exit_time=None;exit_why=None;possible_limitup=False
    for j in range(signal_idx+1,len(rows)):
        bar=rows[j]
        if bar["time"]>"13:20":break
        if bar["h"]>=prior_close*1.095:
            possible_limitup=True
        if bar["h"]>=stop:
            exit_price=max(stop,bar["o"])*(1+SLIPPAGE)
            exit_time=bar["time"];exit_why="stop_first_on_intrabar_ambiguity";break
        if bar["l"]<=target:
            exit_price=target*(1+SLIPPAGE)
            exit_time=bar["time"];exit_why="target_2R";break
        # VWAP reclaimed at bar close: buy at NEXT bar open to avoid lookahead
        cumulative=rows[:j+1]
        vol=sum(x["v"] for x in cumulative)
        local_vwap=sum((x["h"]+x["l"]+x["c"])/3*x["v"] for x in cumulative)/vol if vol else float("nan")
        if j>signal_idx+1 and bar["c"]>local_vwap and j+1<len(rows):
            exit_price=rows[j+1]["o"]*(1+SLIPPAGE)
            exit_time=rows[j+1]["time"];exit_why="next_open_vwap_reclaim";break
    if exit_price is None:
        candidates=[b for b in rows if b["time"]<="13:20"]
        if not candidates:return None
        row=candidates[-1];exit_price=row["c"]*(1+SLIPPAGE)
        exit_time=row["time"];exit_why="time_exit"
    gross=1-exit_price/entry
    net=gross-2*COMMISSION-SELL_TAX
    return {"mode":mode,"symbol":code,"date":d,"signal":src["time"],
       "entryTime":entryrow["time"],"exitTime":exit_time,"entry":round(entry,3),
       "exit":round(exit_price,3),"stop":round(stop,3),"target":round(target,3),
       "score":round(score,3),"grossPct":round(gross*100,3),"netPct":round(net*100,3),
       "netTwdPer100k":round(CAPITAL_NOTIONAL*net,2),
       "exitReason":exit_why,"exchangeEligibility":eligibility_mark,
       "possibleUncoveredLimitUp":possible_limitup,
       "executionNote":"Hypothetical quote-only fills; borrow/locate and lock-limit fills unavailable"}

def generate_signals(code,days,benchmark,qual):
    stocks=sorted(days.items())
    daydates=[d for d,_ in stocks]
    agg=daily_aggregates(days)
    benchmark_close={}
    if benchmark:
        benchmark_close={d:rows[-1]["c"] for d,rows in benchmark.items()}
    out=[]
    for i,(d,rows) in enumerate(stocks):
        if i<21:continue
        prev=agg[daydates[i-1]]
        if not(10<=prev["close"]<=1500):continue
        avgturn=statistics.mean(agg[dd]["turnover"] for dd in daydates[i-20:i])
        if avgturn<MIN_20DAY_TURNOVER:continue
        atr=past_atr(daydates,agg,i)
        if atr is None or not(.02<=atr<=.10):continue
        prevclose=prev["close"];dayopen=rows[0]["o"]
        benchweak=False
        if all(k in benchmark_close for k in [d,daydates[i-1],daydates[i-6]]):
            retstock=prevclose/agg[daydates[i-6]]["close"]-1
            retindex=benchmark_close[daydates[i-1]]/benchmark_close[daydates[i-6]]-1
            benchweak=(retstock-retindex<=-.03)
        dayvol=0.;dayvp=0.;first15low=min(x["l"] for x in rows[:3])
        runninghigh=0.;candidates={"A_weak_continuation":None,
                                    "B_failed_breakout":None}
        for j,bar in enumerate(rows):
            dayvol+=bar["v"]
            dayvp+=((bar["h"]+bar["l"]+bar["c"])/3)*bar["v"]
            runninghigh=max(runninghigh,bar["h"])
            tm=bar["time"]
            if j<3 or not ("09:15"<=tm<="11:00") or dayvol<=0:continue
            vwap=dayvp/dayvol
            rvol=past_rvol(stocks,i,tm,bar["v"])
            if rvol is None or rvol<1.2:continue
            if candidates["A_weak_continuation"] is None:
                cond=(benchweak and bar["c"]<prevclose and bar["c"]<dayopen and
                      bar["c"]<first15low and bar["c"]<vwap and
                      bar["c"]<rows[j-1]["l"])
                if cond:
                    candidates["A_weak_continuation"]=(j,vwap,rvol+(.01*abs(1-bar["c"]/prevclose)))
            if candidates["B_failed_breakout"] is None:
                wick=(bar["h"]-max(bar["o"],bar["c"]))/(bar["h"]-bar["l"]) if bar["h"]>bar["l"] else 0.
                cond=(dayopen/prevclose>=1.01 and runninghigh/prevclose>=1.015 and
                      bar["c"]<dayopen and bar["c"]<vwap and
                      bar["c"]<rows[j-1]["l"] and
                      (wick>=.3 or runninghigh/bar["c"]>=1.016))
                if cond:candidates["B_failed_breakout"]=(j,vwap,rvol+runninghigh/prevclose-1)
        for mode,signal in candidates.items():
            if signal is None:continue
            j,vwap,score=signal
            mark=qual.get("dates",{}).get(d,"unknown")
            result=simulate(code,mode,d,rows,j,vwap,score,mark,prevclose)
            if result:out.append(result)
    return out

def calculate_metrics(trades):
    if not trades:return {"trades":0,"winRatePct":None,"avgNetPct":None,"sumNetTwdPer100k":0,
       "profitFactor":None,"maxPeakToTroughTwd":None,"limitUpAlerts":0}
    pnl=[x["netTwdPer100k"] for x in trades]
    gains=sum(x for x in pnl if x>0);losses=-sum(x for x in pnl if x<0)
    equity=0;peak=0;mdd=0
    for x in pnl:
        equity+=x;peak=max(peak,equity);mdd=min(mdd,equity-peak)
    return {"trades":len(trades),"winRatePct":round(sum(x>0 for x in pnl)/len(pnl)*100,2),
       "avgNetPct":round(statistics.mean(x["netPct"] for x in trades),3),
       "sumNetTwdPer100k":round(sum(pnl),2),
       "profitFactor":round(gains/losses,3) if losses>0 else None,
       "maxPeakToTroughTwd":round(mdd,2),
       "limitUpAlerts":sum(x["possibleUncoveredLimitUp"] for x in trades)}

def portfolio(trades,mode):
    # One 100k-notional signal per day; mode-comparison uses identical allocation.
    eligible=[x for x in trades if x["mode"]==mode]
    dates=sorted({x["date"] for x in eligible})
    chosen=[]
    for d in dates:
        signals=[x for x in eligible if x["date"]==d]
        signals.sort(key=lambda x:(-x["score"],x["entryTime"],x["symbol"]))
        chosen.append(signals[0])
    first=dt.date.fromisoformat(START)
    last=dt.date.fromisoformat(END)
    split=first+(last-first)*.6
    splitDate=split.isoformat()
    train=[x for x in chosen if x["date"]<splitDate]
    test=[x for x in chosen if x["date"]>=splitDate]
    verified=[x for x in chosen if x["exchangeEligibility"]=="eligible"]
    return {"mode":mode,"selection":"one highest signal score per trading day, 100k TWD notional",
      "train":calculate_metrics(train),"laterPeriod":calculate_metrics(test),
      "allConditional":calculate_metrics(chosen),"exchangeQualifiedOnly":calculate_metrics(verified),
      "exchangeQualifiedTradeCount":len(verified),"unknownEligibilityCount":
          sum(x["exchangeEligibility"]=="unknown" for x in chosen),
      "integrationReady":False,
      "integrationReason":"Research pilot only; full-period exchange eligibility, borrowability, 1m validation and blind out-of-sample not certified",
      "trades":chosen}

def run(output):
    syms=universe()
    print("UNIVERSE",len(syms),"prior universe snapshot 2026-10-06",flush=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
        outputs=list(pool.map(fetch_one,syms))
    stocks={x["code"]:x["dates"] for x in outputs if "dates" in x}
    print("5MINUTE_DATA",len(stocks),"of",len(syms),flush=True)
    benchmark=fetch_one("TAIEX",True).get("dates",{})
    print("TAIEX_5MIN_DAYS",len(benchmark),flush=True)
    qualified={};alltrades=[];errors=[]
    for x in outputs:
        if "error" in x:errors.append(x["code"]+": "+x["error"])
    # Exchange eligibility records are fetched only for symbols with real bar histories.
    # The supplier may require a paid token; absence is not assumed to mean eligible.
    jobs=[(code,days,sorted(days)[0],sorted(days)[-1]) for code,days in sorted(stocks.items())]
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        qualifications=list(pool.map(lambda args: eligibility(args[0],args[2],args[3]),jobs))
    for (code,days,_,_),q in zip(jobs,qualifications):
        qualified[code]={"status":q["status"],"coveredDates":len(q.get("dates",{})),
                         "error":q.get("error")}
        alltrades.extend(generate_signals(code,days,benchmark,q))
    results={m:portfolio(alltrades,m) for m in MODES}
    assessment={"gatedResearch":False,"reason":"Not approved for website integration; no full ex-ante all-market qualification or source-complete 1m history.",
                "minRequiredDays":180,"availableTradingSessions":
                   len({d for rows in stocks.values() for d in rows})}
    report={"schemaVersion":1,"study":"Taiwan short-sale intraday modes A / B",
      "researchStatus":"exploratory_5minute_backtest_not_deployable",
      "generatedAt":dt.datetime.now(TPE).isoformat(),
      "source":"Yahoo Finance yfinance authentic 5-minute OHLCV + FinMind point-in-time TaiwanStockDayTrading where allowed",
      "lookback":{"start":START,"end":END,"universeFrozenAt":"2026-10-06",
                  "interval":"5m","countUniverse":len(syms),"symbolsWithCompleteFiveMinuteData":len(stocks),
                  "symbolList":syms,"successfulSymbols":sorted(stocks),"dataErrors":errors},
      "method":{"A":"5d relative weakness <= -3pp; 20d avg turnover >=500m; ATRp 2-10%; below 15m opening range/VWAP, RVOL >=1.2",
                "B":"open >=1% above prior close, peak >=1.5% above, failed high/VWAP, bearish reversal and RVOL >=1.2",
                "entry":"Signal confirmed on 5-minute close, entry at next bar open with adverse 5bps slippage",
                "exit":"Stop above last 3-bar high or >=0.8%; target 2R; VWAP reclaim next open or 13:20 flat; ambiguous bar stop first",
                "commissionsPerSide":COMMISSION,"sellDayTradeTax":SELL_TAX,
                "slippagePerSide":SLIPPAGE,"costRoundtripPct":(2*COMMISSION+SELL_TAX+2*SLIPPAGE)*100,
                "qualifying":"Historical stock-level BuyAfterSale eligible only if FinMind returns date-specific record; broker locate not observed",
                "selectionBias":"Fixed 2026-10-06 A/D candidate universe + ex-ante large-cap anchors, NOT marketwide survivorship-neutral stock set"},
      "shortableCoverage":qualified,"assessment":assessment,"results":results}
    Path(output).parent.mkdir(parents=True,exist_ok=True)
    Path(output).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    for m,x in results.items():
        print("RESULT",m,"all",json.dumps(x["allConditional"],ensure_ascii=False),
              "later",json.dumps(x["laterPeriod"],ensure_ascii=False),
              "eligible_only",json.dumps(x["exchangeQualifiedOnly"],ensure_ascii=False),flush=True)
    print("INTEGRATION_ALLOWED false",flush=True)
    if len(stocks)<8:
        print("::warning::Too few real OHLCV symbols for even a useful pilot; no profitability claim",flush=True)
    return report

def self_test():
    assert tick_size(8)==.01 and tick_size(49)==.05 and tick_size(88)==.1
    assert tick_size(350)==.5 and tick_size(900)==1
    assert calculate_metrics([])["trades"]==0
    sample=[{"netTwdPer100k":1000,"netPct":1.0,"possibleUncoveredLimitUp":False},
            {"netTwdPer100k":-2000,"netPct":-2.0,"possibleUncoveredLimitUp":True}]
    met=calculate_metrics(sample)
    assert met["trades"]==2 and met["sumNetTwdPer100k"]==-1000
    assert met["maxPeakToTroughTwd"]==-2000 and met["profitFactor"]==.5
    assert universe() and all(len(x)==4 for x in universe())
    print("SELF_TEST_PASS")

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--output",default="/tmp/tw-short-ab/pilot.json")
    parser.add_argument("--self-test",action="store_true")
    opts=parser.parse_args()
    if opts.self_test:self_test()
    else:run(opts.output)
