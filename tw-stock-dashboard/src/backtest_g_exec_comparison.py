"""G_DOUBLE_PERSIST frozen signal list: compare two execution methods, NO selection changes.
A: first limit at signal close-2.5% remains alive up to five trading days.
   4 further buys at FIRST actual fill x(.98,.96,.94,.92), five equal-cash lots.
B: four separate equal-cash buys only when today's complete OHLC touches the
   PREVIOUS completed day's SMA5/10/20/60, each once. First touch must occur
   within five trading days; after first touch add until basket exit.
   Weakness: two consecutive COMPLETED closes below their own SMA60 and the
   latest SMA20 below SMA20 three sessions earlier; cancel watch / exit next OPEN.
Both: basket average cost +7% gross TP, -15% gross stop, 5/10/20 trading
days maximum counted from FIRST actual entry. Conservative same-bar order.
Does not estimate a financed portfolio cash curve or 2-minute entry fills.
"""
from __future__ import annotations
import math,json,time
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from collections import defaultdict
import numpy as np,pandas as pd
from config import DATA_DIR
from pipeline import load_universe
from yahoo_cache import update_many,update_symbol,to_symbol
START="2026-01-01";END="2026-10-07"
MODEL="G_DOUBLE_PERSIST";HORIZONS=(5,10,20);INITIAL_WAIT_DAYS=5
MA_WINDOWS=(5,10,20,60)
BUY_FEE=.001425;SELL_FEE=.001425;SELL_TAX=.003;SLIP=.001;TP=.07;SL=.15
def prepare_bars(df):
    if df is None or df.empty:return None
    x=df.sort_values("date").drop_duplicates("date",keep="last").reset_index(drop=True).copy()
    for c in ("open","high","low","close"):x[c]=pd.to_numeric(x[c],errors="coerce")
    for m in MA_WINDOWS:x[f"ma{m}"]=x["close"].rolling(m,min_periods=m).mean()
    x["weak"]=(x["close"]<x["ma60"])&(x["close"].shift(1)<x["ma60"].shift(1))&(x["ma20"]<x["ma20"].shift(3))
    x["date"]=x.date.astype(str)
    return x.set_index("date",drop=False)
def execution(bars,first_day_index,signal_close,hold_days,mode):
    """bars starts at signal+1 with historical warmup rows available separately.
    first_day_index is absolute position of next session.
    Only next 5 sessions permitted for FIRST buy; additions may continue later.
    Output records earliest possible fill, with adverse path assumptions.
    """
    if mode not in ("ladder","ma"):raise ValueError(mode)
    max_lots=5 if mode=="ladder" else 4
    if first_day_index<0 or first_day_index>=len(bars):return {"status":"invalid"}
    frames=bars.iloc[first_day_index:]
    if len(frames)<hold_days+INITIAL_WAIT_DAYS-1:return {"status":"insufficient_future"}
    seq=frames.iloc[:hold_days+INITIAL_WAIT_DAYS-1]
    if len(seq)<hold_days+INITIAL_WAIT_DAYS-1:return {"status":"insufficient_future"}
    closes=pd.to_numeric(seq.close,errors="coerce").to_numpy(dtype=float)
    if not np.isfinite(closes).all() or np.any((closes[1:]/closes[:-1]>1.80)|(closes[1:]/closes[:-1]<.55)):return {"status":"invalid"}
    first_limit=signal_close*.975
    bought={};orders=[];first_fill=None;first_fill_i=None;first_open=None
    def pay(px,k,day):
        paid=px*(1+SLIP)
        orders.append({"key":k,"date":day,"fill":float(px),"paid":paid,"qty":1/paid})
        bought[k]=True
    def average():return len(orders)/sum(o["qty"] for o in orders)
    def done(px,reason,date,last_index):
        if not orders:return {"status":"unfilled","trackingEnd":date}
        cash=len(orders)*(1+BUY_FEE)
        receipt=px*(1-SLIP)*(1-SELL_FEE-SELL_TAX)*sum(o["qty"] for o in orders)
        avg=average()
        return {"status":"filled","firstEntryDate":first_fill,"exitDate":date,"trackingEnd":date,
                "entryAfterSignalDays":int(first_fill_i+1),"holdTradingDays":int(last_index-first_fill_i+1),
                "tranches":len(orders),"maFilled":[o["key"] for o in orders if mode=="ma"],
                "fills":[{"type":o["key"],"date":o["date"],"price":round(o["fill"],4)} for o in orders],
                "avgCost":round(avg,4),"exitPrice":round(px,4),"reason":reason,
                "tp":reason.startswith("tp"),"stop":reason.startswith("stop"),
                "weakExit":reason=="weak_exit","timeout":reason=="timeout",
                "netOnDeployedPct":round((receipt/cash-1)*100,3),
                "netOnReservedPct":round((receipt-cash)/(max_lots*(1+BUY_FEE))*100,3)}
    dates=bars.index.tolist()
    for rel,(date,bar) in enumerate(seq.iterrows()):
        i=first_day_index+rel;o,h,l,c=(float(bar[k]) for k in ("open","high","low","close"))
        if not all(math.isfinite(v) and v>0 for v in (o,h,l,c)):return {"status":"invalid"}
        previous=bars.iloc[i-1] if i>=1 else None
        if mode=="ma" and previous is not None and bool(previous["weak"]):
            if orders:return done(o,"weak_exit",date,rel)
            return {"status":"weak_cancel","trackingEnd":date}
        if orders:
            avg=average()
            if o<=avg*(1-SL):return done(o,"stop_gap",date,rel)
            if o>=avg*(1+TP):return done(o,"tp_gap",date,rel)
        newly_intraday=False
        if not orders and rel>=INITIAL_WAIT_DAYS:
            return {"status":"unfilled","trackingEnd":dates[min(i,first_day_index+INITIAL_WAIT_DAYS-1)]}
        if mode=="ladder":
            if not orders:
                if o<=first_limit:
                    first_fill=date;first_fill_i=rel;first_open=o;pay(o,"L1",date)
                elif l<=first_limit:
                    first_fill=date;first_fill_i=rel;first_open=first_limit;pay(first_limit,"L1",date);newly_intraday=True
            if orders:
                while len(orders)<5:
                    t=first_open*(1-.02*len(orders));key=f"L{len(orders)+1}"
                    if o<=t and not newly_intraday:pay(o,key,date);continue
                    if l<=t:pay(t,key,date);newly_intraday=True;continue
                    break
        else:
            if previous is not None:
                # A touch is valid ONLY when LOW <= yesterday's MA <= HIGH.
                # No entries in K-bars wholly above/below an MA.
                for span in MA_WINDOWS:
                    if span in bought:continue
                    val=float(previous[f"ma{span}"])
                    if not math.isfinite(val) or val<=0:continue
                    if l<=val<=h:
                        if first_fill is None:first_fill=date;first_fill_i=rel
                        pay(val,span,date)
                        if o!=val:newly_intraday=True
        if orders:
            avg=average()
            if l<=avg*(1-SL):return done(avg*(1-SL),"stop",date,rel)
            # Day in which an intraday entry/add took place has unknown path;
            # never credit that day's higher high as take-profit.
            if not newly_intraday and h>=avg*(1+TP):return done(avg*(1+TP),"tp",date,rel)
            if rel-first_fill_i+1>=hold_days:return done(c,"timeout",date,rel)
    return {"status":"unfilled" if not orders else "insufficient_future","trackingEnd":seq.index[-1]}
def run_model(signals,prices,cal,h,mode):
    index={d:i for i,d in enumerate(cal)};trades=[];excluded=0
    # Duplicate G Top3 signals for a stock while existing watch/holding is
    # active are suppressed. No replacement with fourth-ranked stocks.
    track_until={}
    for s in sorted(signals,key=lambda x:(x["signalDate"],x["rank"])):
        date=s["signalDate"];j=index.get(date)
        if j is None or j+1+INITIAL_WAIT_DAYS-1+h>len(cal):continue
        # To avoid right-censoring and change of window after entry,
        # require all post-signal bars before END (horizon+initial wait).
        if cal[j+h+INITIAL_WAIT_DAYS-1]>END:continue
        code=str(s["code"])
        if date<=track_until.get(code,""):excluded+=1;continue
        market=s.get("market");frame=prices.get(to_symbol(code,market))
        if frame is None or date not in frame.index:
            trades.append({"date":date,"code":code,"rank":s["rank"],"status":"missing"})
            continue
        fi=frame.index.get_loc(cal[j+1]) if cal[j+1] in frame.index else -1
        if fi<0:
            trades.append({"date":date,"code":code,"rank":s["rank"],"status":"missing"})
            continue
        price=float(frame.loc[date,"close"])
        out=execution(frame,fi,price,h,mode)
        tracking=out.get("trackingEnd")
        if tracking:track_until[code]=tracking
        trades.append({"date":date,"code":code,"name":s["name"],"market":market,
                       "rank":s["rank"],"signalClose":round(price,3),**out})
    return trades,excluded
def summary(trades,excluded,mode,h):
    fills=[x for x in trades if x["status"]=="filled"]
    if not fills:return {"signalEvents":len(trades),"filled":0,"duplicateSuppressed":excluded}
    net=np.array([x["netOnDeployedPct"] for x in fills])
    reserved=np.array([x["netOnReservedPct"] for x in fills])
    positive=net[net>0];negative=net[net<0]
    n=len(fills);st=sum(x["stop"] for x in fills);tp=sum(x["tp"] for x in fills)
    return {"signalEvents":len(trades),"filled":n,"duplicateSuppressed":excluded,
        "unfilled":sum(x["status"]=="unfilled" for x in trades),
        "weakCancelled":sum(x["status"]=="weak_cancel" for x in trades),
        "incomplete":sum(x["status"]in("missing","invalid","insufficient_future") for x in trades),
        "takeProfitN":tp,"takeProfitPct":round(100*tp/n,2),
        "stopN":st,"stopPct":round(100*st/n,2),
        "weakExitN":sum(x["weakExit"] for x in fills),"weakExitPct":round(100*sum(x["weakExit"] for x in fills)/n,2),
        "avgNetOnDeployedPct":round(float(net.mean()),3),
        "avgNetOnReservedPct":round(float(reserved.mean()),3),
        "netWinPct":round(100*np.mean(net>0),2),
        "avgWinPct":round(float(positive.mean()),3) if len(positive) else None,
        "avgLossPct":round(float(negative.mean()),3) if len(negative) else None,
        "profitFactor":round(float(positive.sum()/abs(negative.sum())),3) if len(negative) else None,
        "avgTranches":round(float(np.mean([x["tranches"] for x in fills])),2),
        "trancheCounts":{str(k):sum(x["tranches"]==k for x in fills) for k in range(1,6 if mode=="ladder" else 5)},
        "maFillCounts":{str(k):sum(k in x["maFilled"] for x in fills) for k in MA_WINDOWS} if mode=="ma" else None,
        "avgSignalToEntryDays":round(float(np.mean([x["entryAfterSignalDays"] for x in fills])),2),
        "avgHoldDays":round(float(np.mean([x["holdTradingDays"] for x in fills])),2),
        "distinctStocks":len(set(x["code"] for x in fills))}
def run():
    begun=time.time()
    raw=json.loads((DATA_DIR/"backtest_g/g_persistence_2026.json").read_text(encoding="utf-8"))
    g=raw["models"][MODEL]["signals"]
    universe=load_universe();companies={str(x["code"]):x for x in universe}
    valid=[dict(s,market=companies[str(s["code"])]["market"]) for s in g
           if str(s["code"]) in companies and START<=s["signalDate"]<=END and int(s["rank"])<=3]
    stocks={(x["code"],x["market"]) for x in valid}
    print("G frozen Top3",len(valid),"symbols",len(stocks),flush=True)
    fs=datetime(2025,8,1);fe=datetime(2026,10,8)
    hist,errors=update_many(sorted(stocks),fs,fe)
    _,idx,err=update_symbol("^TWII",fs,fe)
    if err or idx is None or idx.empty:raise RuntimeError("Index trading days not available: "+str(err))
    calendar=[d for d in idx.date.astype(str).tolist() if d<=END];prices={k:prepare_bars(v) for k,v in hist.items()}
    output={};details={}
    for h in HORIZONS:
        output[str(h)]={};details[str(h)]={}
        for m in ("ladder","ma"):
            trades,dupes=run_model(valid,prices,calendar,h,m)
            output[str(h)][m]=summary(trades,dupes,m,h)
            details[str(h)][m]=trades
            print("G_EXEC_COMPARE "+json.dumps({"holdingDays":h,"mode":m,"stats":output[str(h)][m]},ensure_ascii=False),flush=True)
    report={"version":"G_2026_LADDER_VS_MA_TOUCH_V1","generatedAt":datetime.now(ZoneInfo("Asia/Taipei")).isoformat(timespec="seconds"),
        "period":{"start":START,"end":END},"model":MODEL,"source":"Unmodified existing published G_DOUBLE_PERSIST Top3 signals; no stock selection or ranking modifications",
        "originalGSignals":len(g),"matchedSignals":len(valid),"universeSymbols":len(stocks),"priceErrors":errors,
        "methods":{
            "ladder":{"firstBuy":"signal-day close -2.5%, valid following 5 trading sessions",
                "adds":"P1*(1 - 2% * n), n=1,2,3,4, first actual fill fixed anchor, each order once",
                "tranches":5,"allocation":"five equal-cash tranches"},
            "ma":{"firstBuy":"ONLY when daily low<=previous completed-day SMA(5/10/20/60)<=high, first 5 trading sessions",
                "adds":"each of MA5/10/20/60 may fill at its previous completed-day MA level only once; other tranches pending until exit",
                "tranches":4,"allocation":"four equal-cash tranches",
                "weakness":"two consecutive prior completed closes below their MA60 plus prior MA20 < prior MA20 3 days earlier",
                "onWeakness":"stop following: cancel unfilled orders; if invested exit next trading-day OPEN"}},
        "common":{"holdingMaxTradingDaysAfterFirstFill":HORIZONS,"takeProfitPctAboveWeightedAvgCost":7,
            "stopLossPctBelowWeightedAvgCost":15,"slippagePerSidePct":0.1,"buyBrokerPct":0.1425,"sellBrokerPct":0.1425,"sellTaxPct":0.3,
            "entryOrders":"precommitted, filled only if low touches; MA requires full OHLC touches",
            "sameDayConflict":"stop before TP; no credit for TP on day with newly intraday-filled order",
            "duplicateSignal":"same stock new Top3 signal discarded while earlier basket or initial watch is active",
            "unknownDirection":"OHLC does not resolve multiple MA touch ordering or real stop/TP timing",
            "portfolioCash":"No shared-account capital / financing simulated; reserved-budget statistic is not a fund equity curve"},
        "statistics":output,
        "warnings":["MA20/MA60 touch and weakness are operational interpretations, not user-confirmed definitions.","MA indicators use previous completed day to prevent look-ahead in the order placement; daily touch is still not a guaranteed executable fill.","Current-survivor G signal archive and past strategy iterations were developed on 2026 data; results are in-sample historical studies.","Open-to-extreme same-day ambiguity may alter stops, averaging and wins; minute/2-minute K would be needed for execution-grade evidence.","-15% stop can be exceeded on a gap; averaging increases invested dollars as price falls.","Repeated G selection events are handled by no same-symbol overlap rule but trades for different stocks may exceed available cash; full equity curve not evaluated.","End-date right-censoring: require enough subsequent bars to fit max first-order wait and subsequent holding period."],
        "elapsedSeconds":round(time.time()-begun,1)}
    path=DATA_DIR/"backtest_g_exec";path.mkdir(exist_ok=True,parents=True)
    (path/"G_2026_ladder_vs_ma_summary.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    (path/"G_2026_ladder_vs_ma_trades.json").write_text(json.dumps(details,ensure_ascii=False,indent=2),encoding="utf-8")
    print("G_EXEC_RESULT "+json.dumps({"period":report["period"],"model":MODEL,"matchedSignals":len(valid),"statistics":output,"elapsedSeconds":report["elapsedSeconds"]},ensure_ascii=False),flush=True)
    return report
if __name__=="__main__":run()
