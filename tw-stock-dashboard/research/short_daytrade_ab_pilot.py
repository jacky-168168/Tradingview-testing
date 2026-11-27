"""Stand-alone short-sell day-trading RESEARCH. Never imports or edits live stock selection.
Real Yahoo 5-minute bars, recent <= 60 days. Historical eligible-to-short data NOT verified.
No claims of executable returns, intrabar stop always takes precedence, no EOD overnight.
"""
import argparse,collections,json,math,statistics
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
TZ=ZoneInfo("Asia/Taipei")
UNIVERSE="2317.TW 2454.TW 2303.TW 2382.TW 3231.TW 2376.TW 2356.TW 2324.TW 2345.TW 3037.TW 3035.TW 3017.TW 3008.TW 3661.TW 3711.TW 6669.TW 2603.TW 2618.TW 2881.TW 2882.TW 2886.TW 2891.TW 2892.TW 3706.TW 6214.TW 4904.TW 8046.TW 8069.TWO 5483.TWO 2377.TW".split()
CAPITAL=1_000_000
FEE=0.001425
TAX=0.0015
MAX_LOTS_PER_TRADE=1
SHARES=1000
SLIPPAGE_TICKS=1
MAX_NOTIONAL=300_000
MAX_SINGLE_LOSS=5_000
MIN_TURNOVER=5e8
OR_END="09:10"
END_TIME="13:20"
def tick(p): return .01 if p<10 else .05 if p<50 else .1 if p<100 else .5 if p<500 else 1 if p<1000 else 5
def finite(x):
    try:return math.isfinite(float(x))
    except (TypeError,ValueError):return False
def get_history(symbol,interval,period):
    import yfinance as yf
    import pandas as pd
    frame=yf.Ticker(symbol).history(interval=interval,period=period,prepost=False,
                                    auto_adjust=False,actions=False,raise_errors=False)
    if frame is None or frame.empty:return []
    out=[]
    for stamp,z in frame.iterrows():
        vals=[z.get(k) for k in ("Open","High","Low","Close","Volume")]
        if not all(finite(v) for v in vals) or min(vals[:4])<=0 or vals[4]<0:continue
        t=stamp.tz_convert("Asia/Taipei") if stamp.tzinfo else stamp.tz_localize("Asia/Taipei")
        out.append({"day":t.date().isoformat(),"time":t.strftime("%H:%M"),"o":float(vals[0]),
                    "h":float(vals[1]),"l":float(vals[2]),"c":float(vals[3]),"v":float(vals[4])})
    return out
def good_days(bars):
    days=collections.defaultdict(list)
    for b in bars:
        if "09:00"<=b["time"]<="13:25" and b["l"]<=min(b["o"],b["c"]) and b["h"]>=max(b["o"],b["c"]):
            days[b["day"]].append(b)
    valid={}
    for day,rows in days.items():
        rows=sorted({x["time"]:x for x in rows}.values(),key=lambda x:x["time"])
        if len(rows)<48 or rows[0]["time"]!="09:00" or rows[-1]["time"]<END_TIME:continue
        gaps=[(datetime.strptime(rows[i]["time"],"%H:%M")-
               datetime.strptime(rows[i-1]["time"],"%H:%M")).seconds
              for i in range(1,len(rows))]
        if any(g>900 for g in gaps):continue
        valid[day]=rows
    return valid
def indicators(d,idx,index,index_pos):
    # Exclusively closes and OHLC from days BEFORE current session.
    if idx<21 or index_pos<6:return None
    p=d[idx-1]
    avg=statistics.mean(x["c"]*x["v"] for x in d[idx-20:idx])
    prev=p["c"]
    trs=[max(d[k]["h"]-d[k]["l"],abs(d[k]["h"]-d[k-1]["c"]),abs(d[k]["l"]-d[k-1]["c"]))
         for k in range(idx-14,idx)]
    atr=statistics.mean(trs)/prev if prev else 0
    rel=p["c"]/d[idx-6]["c"]-1-(index[index_pos-1]["c"]/index[index_pos-6]["c"]-1)
    return {"prev":prev,"prevHigh":p["h"],"turnover":avg,"atr":atr,"relative":rel}
def vwap(rows,i):
    # Approximate tick VWAP from 5m typical price x shares (not actual tick VWAP).
    v=sum(b["v"] for b in rows[:i+1])
    return sum(((b["h"]+b["l"]+b["c"])/3)*b["v"] for b in rows[:i+1])/v if v>0 else None
def same_clock_rvol(history,day,clock,rows):
    old=[sum(x["v"] for x in history[d] if x["time"]<=clock)
         for d in sorted(history) if d<day][-10:]
    if len(old)<5:return None
    avg=statistics.mean(old)
    return sum(b["v"] for b in rows if b["time"]<=clock)/avg if avg>0 else None
def scan(symbol,days,daily,index):
    dpos={x["day"]:i for i,x in enumerate(daily)}
    ipos={x["day"]:i for i,x in enumerate(index)}
    result=[]
    for day,rows in sorted(days.items()):
        di=dpos.get(day);ii=ipos.get(day)
        if di is None or ii is None:continue
        f=indicators(daily,di,index,ii)
        if not f or not (10<=f["prev"]<=300 and f["turnover"]>=MIN_TURNOVER and .03<=f["atr"]<=.08):continue
        first=[x for x in rows if x["time"]<="09:10"]
        if len(first)!=3:continue
        rh=max(x["h"] for x in first);rl=min(x["l"] for x in first)
        gap=rows[0]["o"]/f["prev"]-1
        for mode in ("A","B"):
            if mode=="A" and not (f["relative"]<=-.03 and -.01<=gap<=.01):continue
            if mode=="B" and not (.01<=gap<=.10):continue
            for i in range(3,len(rows)-2):
                x=rows[i]
                if not ("09:15"<=x["time"]<="11:00"):continue
                w=vwap(rows,i)
                if w is None or x["c"]>=w:continue
                rv=same_clock_rvol(days,day,x["time"],rows)
                if rv is None or rv<1.5:continue
                if mode=="A":
                    if x["c"]>=rl or (i>3 and x["c"]>=min(z["l"] for z in rows[3:i])):continue
                    stop=max(rh,x["h"],w)+tick(x["c"])
                else:
                    highest=max(z["h"] for z in rows[:i+1])
                    if highest<=max(rh,f["prevHigh"]) or x["c"]>=f["prevHigh"] or x["c"]>=x["o"]:continue
                    stop=max(highest,w)+tick(x["c"])
                nxt=rows[i+1]
                if (datetime.strptime(nxt["time"],"%H:%M")-datetime.strptime(x["time"],"%H:%M")).seconds!=300:continue
                entry=nxt["o"]-SLIPPAGE_TICKS*tick(nxt["o"])
                risk=(stop-entry)/entry
                if not (.0025<=risk<=.035):continue
                if entry*SHARES>MAX_NOTIONAL or (stop-entry)*SHARES>MAX_SINGLE_LOSS:continue
                result.append({"day":day,"symbol":symbol,"mode":mode,
                  "signalTime":x["time"],"entryTime":nxt["time"],"entryIndex":i+1,
                  "rawEntry":nxt["o"],"stop":stop,"rvol":round(rv,3),"gap":round(gap,4),
                  "relativeWeak":round(f["relative"],4)})
                break
    return result
def simulate(sig,rows,slippage=1):
    entry=sig["rawEntry"]-slippage*tick(sig["rawEntry"])
    stop=sig["stop"];target=entry-1.5*(stop-entry)
    if stop<=entry or target<=0:return None
    for x in rows[sig["entryIndex"]:]:
        if x["time"]>=END_TIME:
            px=x["o"];reason="time"
        elif x["o"]>=stop:
            px=x["o"];reason="gap_stop"
        elif x["h"]>=stop:
            px=stop;reason="stop_first"
        elif x["o"]<=target:
            px=x["o"];reason="gap_target"
        elif x["l"]<=target:
            px=target;reason="target"
        else:continue
        cover=px+slippage*tick(px)
        gross=(entry-cover)*SHARES
        fees=max(20,entry*SHARES*FEE)+max(20,cover*SHARES*FEE)
        tax=entry*SHARES*TAX
        return {**sig,"entry":round(entry,3),"cover":round(cover,3),"exitTime":x["time"],
          "exitReason":reason,"grossTwd":round(gross,2),"feesTwd":round(fees,2),
          "taxTwd":round(tax,2),"netTwd":round(gross-fees-tax,2)}
    return None
def metrics(trades,days):
    if not trades:return {"n":0,"netTwd":0,"winRate":None,"PF":None,"maxDrawdownTwd":None,
                           "worstTradeTwd":None,"returnOnInitialPct":0}
    vals=[t["netTwd"] for t in trades]
    by=collections.defaultdict(float)
    for x in trades:by[x["day"]]+=x["netTwd"]
    equity=CAPITAL;peak=CAPITAL;dd=0
    for d in sorted(days):
        equity+=by[d];peak=max(peak,equity);dd=max(dd,peak-equity)
    wins=sum(x>0 for x in vals)
    pos=sum(x for x in vals if x>0);neg=-sum(x for x in vals if x<0)
    return {"n":len(vals),"netTwd":round(sum(vals),2),"winRate":round(wins/len(vals),4),
      "PF":round(pos/neg,4) if neg else None,"maxDrawdownTwd":round(dd,2),
      "worstTradeTwd":min(vals),"returnOnInitialPct":round(sum(vals)/CAPITAL*100,4),
      "avgNetTwd":round(statistics.mean(vals),2)}
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--out",required=True);ap.add_argument("--symbols",default=",".join(UNIVERSE))
    args=ap.parse_args()
    by_symbol={};error={}
    for ticker in args.symbols.split(","):
        try:
            b=good_days(get_history(ticker,"5m","60d"))
            d=get_history(ticker,"1d","6mo")
            if not b or not d:error[ticker]="insufficient_5m_or_daily";continue
            by_symbol[ticker]=(b,d)
        except Exception as e:error[ticker]=str(e)[:150]
    try:index=get_history("^TWII","1d","6mo")
    except Exception as e:index=[];error["^TWII"]=str(e)[:150]
    signals=[]
    for sym,(bars,daily) in by_symbol.items():
        if index:signals.extend(scan(sym,bars,daily,index))
    # Select no more than the first three signals per mode/day, chronologically.
    chosen=[];counts=collections.defaultdict(int)
    for s in sorted(signals,key=lambda x:(x["day"],x["entryTime"],x["symbol"],x["mode"])):
        key=(s["day"],s["mode"])
        if counts[key]>=3:continue
        counts[key]+=1;chosen.append(s)
    results={1:[],2:[]}
    for s in chosen:
        for slip in (1,2):
            x=simulate(s,by_symbol[s["symbol"]][0][s["day"]],slip)
            if x:results[slip].append(x)
    dates=sorted({d for b,_ in by_symbol.values() for d in b})
    cutoff=dates[int(.7*len(dates))] if len(dates)>=10 else None
    modes={}
    for mode in ("A","B"):
        rows=[x for x in results[1] if x["mode"]==mode]
        later=[x for x in rows if cutoff and x["day"]>=cutoff]
        modes[mode]={"full":metrics(rows,dates),
          "doubleSlippage":metrics([x for x in results[2] if x["mode"]==mode],dates),
          "early70pct":metrics([x for x in rows if cutoff and x["day"]<cutoff],dates),
          "later30pct":metrics(later,dates)}
    report={"status":"PILOT_ONLY" if index and len(by_symbol)>=5 else "NO_RELIABLE_DATA",
      "researchOnly":True,"integrationApproved":False,
      "eligibilityByHistoricalDateVerified":False,
      "source":"Yahoo Finance recent 5-minute OHLCV, max roughly 60 calendar days",
      "historicalUniverse":"fixed 30-symbol pilot, NOT full historically shortable stock pool",
      "knownLimitations":["missing historical sell-first eligibility, daily suspension, broker short quota",
        "5-minute bars and OHLC stop priority, not actual tick fills",
        "no historical order book, limit-up fill model, or proper longer-term out-of-sample",
        "typical-price-weighted VWAP approximates trade-price VWAP",
        "present-day sample stocks induce survivorship/universe bias"],
      "parameters":{"capitalTwd":CAPITAL,"lot":SHARES,"commissionPerSide":FEE,
         "cashDaytradeSaleTax":TAX,"maxPositionTwd":MAX_NOTIONAL,"maxRiskPerTradeTwd":MAX_SINGLE_LOSS,
         "oneWaySlippageTicks":SLIPPAGE_TICKS,"takeProfitR":1.5,"maxTradesPerModePerDay":3},
      "studyFrom":dates[0] if dates else None,"studyTo":dates[-1] if dates else None,
      "sampleDays":len(dates),"timeSplit":cutoff,"symbolsRequested":len(args.symbols.split(",")),
      "symbolsWithValidIntraday":len(by_symbol),"downloadErrors":error,
      "modes":modes,"trades":results[1],
      "decision":"DO_NOT_INTEGRATE; require historical eligibility + >=1yr 1m data and independent test"}
    path=Path(args.out);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    print(json.dumps({"status":report["status"],"sampleDays":len(dates),"symbols":len(by_symbol),
      "modes":{k:v["full"] for k,v in modes.items()},"downloadErrors":len(error)},ensure_ascii=False))
    return 0 if report["status"]=="PILOT_ONLY" else 2
if __name__=="__main__":raise SystemExit(main())
