"""G_STRICT / G_DOUBLE_PERSIST TP3 SL10 vs TP7 SL15 cost-inclusive comparison.
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
MODEL="G_STRICT";HORIZONS=(10,);INITIAL_WAIT_DAYS=5
GATES=("baseline","signal_ma20","wait_ma20","wait_ma20_twoday","wait_ma20_rising")
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
def execution(bars,first_day_index,signal_close,hold_days,mode,permit_first=None,tp_pct=TP,sl_pct=SL):
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
            if o<=avg*(1-sl_pct):return done(o,"stop_gap",date,rel)
            if o>=avg*(1+tp_pct):return done(o,"tp_gap",date,rel)
        newly_intraday=False
        if not orders and rel>=INITIAL_WAIT_DAYS:
            return {"status":"unfilled","trackingEnd":dates[min(i,first_day_index+INITIAL_WAIT_DAYS-1)]}
        if not orders and permit_first is not None and (rel>=len(permit_first) or not permit_first[rel]):continue
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
            if l<=avg*(1-sl_pct):return done(avg*(1-sl_pct),"stop",date,rel)
            # Day in which an intraday entry/add took place has unknown path;
            # never credit that day's higher high as take-profit.
            if not newly_intraday and h>=avg*(1+tp_pct):return done(avg*(1+tp_pct),"tp",date,rel)
            if rel-first_fill_i+1>=hold_days:return done(c,"timeout",date,rel)
    return {"status":"unfilled" if not orders else "insufficient_future","trackingEnd":seq.index[-1]}
def run_model(signals,prices,cal,h,mode,gate_mode,index_flags,tp_pct=TP,sl_pct=SL):
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
        if gate_mode=="signal_ma20" and not index_flags.get(date,{}).get("aboveMA20",False):
            trades.append({"date":date,"code":code,"rank":s["rank"],"status":"blocked"});continue
        permission=None
        if gate_mode.startswith("wait_ma20"):
            permission=[]
            for rel in range(INITIAL_WAIT_DAYS):
                facts=index_flags.get(cal[j+rel],{})
                allowed=facts.get("aboveMA20",False)
                if gate_mode=="wait_ma20_twoday":allowed=allowed and facts.get("previousAboveMA20",False)
                elif gate_mode=="wait_ma20_rising":allowed=allowed and facts.get("risingMA20",False)
                permission.append(bool(allowed))
        market=s.get("market");frame=prices.get(to_symbol(code,market))
        if frame is None or date not in frame.index:
            trades.append({"date":date,"code":code,"rank":s["rank"],"status":"missing"})
            continue
        fi=frame.index.get_loc(cal[j+1]) if cal[j+1] in frame.index else -1
        if fi<0:
            trades.append({"date":date,"code":code,"rank":s["rank"],"status":"missing"})
            continue
        price=float(frame.loc[date,"close"])
        out=execution(frame,fi,price,h,mode,permit_first=permission,tp_pct=tp_pct,sl_pct=sl_pct)
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
        "blocked":sum(x["status"]=="blocked" for x in trades),
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

INITIAL_CAPITAL=1_000_000.0
SLOT_COUNTS=(3,5,10)
SELECTORS=("G_STRICT","G_DOUBLE_PERSIST")
MARKET_MODES=("baseline","signal_ma20","wait_ma20")
def close_at(frame,date):
    i=frame.index.searchsorted(date,side="right")-1
    if i<0:return None
    v=float(frame.iloc[i]["close"])
    return v if math.isfinite(v) and v>0 else None
def trade_mark(x,day,prices,mode):
    if x["status"]!="filled" or x.get("firstEntryDate","9999")>day:return 0.0
    budget=float(x["budget"])
    if x.get("exitDate") and x["exitDate"]<=day:return budget*float(x["netOnReservedPct"])/100
    frame=prices.get(to_symbol(x["code"],x["market"]))
    px=close_at(frame,day) if frame is not None else None
    if not px:return 0.0
    lots=5 if mode=="ladder" else 4
    unit=budget/(lots*(1+BUY_FEE))
    pnl=0.0
    for f in x.get("fills",[]):
        if f["date"]>day:continue
        fill=float(f["price"])
        qty=unit/(fill*(1+SLIP))
        pnl+=qty*px*(1-SLIP)*(1-SELL_FEE-SELL_TAX)-unit*(1+BUY_FEE)
    return pnl
def equity_at(trades,day,prices,mode):
    return INITIAL_CAPITAL+sum(trade_mark(x,day,prices,mode) for x in trades)
def index_status(index_history):
    z=index_history.sort_values("date").drop_duplicates("date",keep="last").reset_index(drop=True)
    close=pd.to_numeric(z["close"],errors="coerce");ma20=close.rolling(20,min_periods=20).mean()
    above=close>=ma20
    return {str(d):{"aboveMA20":bool(above.iloc[i]) if pd.notna(ma20.iloc[i]) else False}
            for i,d in enumerate(z.date.astype(str))}
def _peak_run(trades,signal):
    items=sorted([x for x in trades if x.get("status")=="filled"],key=lambda x:(x.get("exitDate",""),x["code"]))
    max_loss=0;streak=0;max_stop=0;stop_streak=0
    for x in items:
        bad=x.get("netOnReservedPct",0)<0
        streak=streak+1 if bad else 0
        stop_streak=stop_streak+1 if x.get("stop") else 0
        max_loss=max(max_loss,streak);max_stop=max(max_stop,stop_streak)
    return max_loss,max_stop
def run_capacity(valid,prices,cal,h,mode,gate,flags,slots,tp_pct=TP,sl_pct=SL):
    calendar_index={d:i for i,d in enumerate(cal)}
    admitted=[];active=[];stock_until={}
    skipped={"noWindow":0,"duplicate":0,"market":0,"capacity":0,"liquidity":0,"missing":0}
    for s in sorted(valid,key=lambda x:(x["signalDate"],x["rank"])):
        day=s["signalDate"];j=calendar_index.get(day)
        if j is None or j+1+INITIAL_WAIT_DAYS-1+h>len(cal) or cal[j+h+INITIAL_WAIT_DAYS-1]>END:
            skipped["noWindow"]+=1;continue
        active=[a for a in active if a["end"]>day]
        code=str(s["code"])
        if day<=stock_until.get(code,""):
            skipped["duplicate"]+=1;continue
        if gate=="signal_ma20" and not flags.get(day,{}).get("aboveMA20",False):
            skipped["market"]+=1;continue
        if len(active)>=slots:
            skipped["capacity"]+=1;continue
        market=s.get("market");frame=prices.get(to_symbol(code,market))
        if frame is None or day not in frame.index or cal[j+1] not in frame.index:
            skipped["missing"]+=1;continue
        equity=equity_at(admitted,day,prices,mode)
        free=max(0.0,equity-sum(a["budget"] for a in active))
        target=INITIAL_CAPITAL/slots
        budget=min(target,free)
        if budget<=max(1000,0.02*target):
            skipped["liquidity"]+=1;continue
        permission=None
        if gate=="wait_ma20":
            permission=[flags.get(cal[j+rel],{}).get("aboveMA20",False) for rel in range(INITIAL_WAIT_DAYS)]
        fi=frame.index.get_loc(cal[j+1])
        out=execution(frame,fi,float(frame.loc[day,"close"]),h,mode,permit_first=permission,tp_pct=tp_pct,sl_pct=sl_pct)
        tracking=out.get("trackingEnd")
        if tracking:stock_until[code]=tracking
        trade={"date":day,"code":code,"name":s.get("name",""),"market":market,"rank":int(s["rank"]),
               "signalClose":float(frame.loc[day,"close"]),"budget":round(budget,3),**out}
        admitted.append(trade)
        if tracking:active.append({"code":code,"end":tracking,"budget":budget})
    dates=[d for d in cal if START<=d<=END]
    chart=[];max_peak=INITIAL_CAPITAL;worst_dd=0.0;maxactive=0;monthly={}
    for d in dates:
        eq=equity_at(admitted,d,prices,mode)
        max_peak=max(max_peak,eq);dd=100*(eq/max_peak-1)
        worst_dd=min(worst_dd,dd)
        slots_used=sum(x["date"]<=d<str(x.get("trackingEnd","")) for x in admitted)
        maxactive=max(maxactive,slots_used)
        chart.append({"date":d,"equity":round(eq,2),"drawdownPct":round(dd,3),"activeReservations":slots_used})
        monthly[d[:7]]=eq
    start_equity=INITIAL_CAPITAL;monthly_returns={}
    for month,last in sorted(monthly.items()):
        monthly_returns[month]=round(100*(last/start_equity-1),3)
        start_equity=last
    fills=[x for x in admitted if x.get("status")=="filled"]
    stops=[x for x in fills if x.get("stop")]
    tp=[x for x in fills if x.get("tp")]
    loss_runs=_peak_run(admitted,None)
    last=chart[-1]["equity"] if chart else INITIAL_CAPITAL
    worstmonth=min(monthly_returns,key=monthly_returns.get) if monthly_returns else None
    gross_positive=sum(max(0,x["budget"]*x["netOnReservedPct"]/100) for x in fills)
    gross_negative=-sum(min(0,x["budget"]*x["netOnReservedPct"]/100) for x in fills)
    return {
        "signalCount":len(valid),"admitted":len(admitted),"filled":len(fills),
        "tpN":len(tp),"stopN":len(stops),"tpPct":round(100*len(tp)/len(fills),2) if fills else None,
        "stopPct":round(100*len(stops)/len(fills),2) if fills else None,
        "netWinPct":round(100*sum(x["netOnReservedPct"]>0 for x in fills)/len(fills),2) if fills else None,
        "meanNetOnReservedPct":round(float(np.mean([x["netOnReservedPct"] for x in fills])),3) if fills else None,
        "totalReturnPct":round(100*(last/INITIAL_CAPITAL-1),3),
        "maxEquityNTD":round(max(x["equity"] for x in chart),2) if chart else INITIAL_CAPITAL,
        "lastEquityNTD":round(last,2),
        "avgHoldDays":round(float(np.mean([x["holdTradingDays"] for x in fills])),2) if fills else None,
        "totalTranches":sum(x.get("tranches",0) for x in fills),
        "averageNetReservedPct":round(float(np.mean([x["netOnReservedPct"] for x in fills])),3) if fills else None,
        "maxDrawdownPct":round(worst_dd,3),
        "profitFactor":round(gross_positive/gross_negative,3) if gross_negative else None,
        "maxConcurrentReservations":maxactive,"maxConsecutiveLosses":loss_runs[0],
        "maxConsecutiveStops":loss_runs[1],"skipped":skipped,
        "worstMonth":worstmonth,"worstMonthReturnPct":monthly_returns.get(worstmonth),
        "julyReturnPct":monthly_returns.get("2026-07"),
        "monthlyReturnsPct":monthly_returns,"dailyEquity":chart,
        "worstTrades":[{"date":x["date"],"code":x["code"],"name":x.get("name"),
            "netReservedPct":x["netOnReservedPct"],"realizedLossNTD":round(x["budget"]*x["netOnReservedPct"]/100)}
            for x in sorted(fills,key=lambda x:x["budget"]*x["netOnReservedPct"])[:8]]
    }

TP_SL_VARIANTS={"tp7_sl15":(.07,.15),"tp3_sl10":(.03,.10),"tp5_sl10":(.05,.10)}
def run():
    started=time.time()
    archives={
        "G_STRICT":json.loads((DATA_DIR/"backtest_g/2026-01-01_2026-10-07.json").read_text(encoding="utf-8")),
        "G_DOUBLE_PERSIST":json.loads((DATA_DIR/"backtest_g/g_persistence_2026.json").read_text(encoding="utf-8"))}
    company={str(x["code"]):x for x in load_universe()}
    candidates={}
    for selector,archive in archives.items():
        candidates[selector]=[dict(s,market=company[str(s["code"])]["market"]) for s in archive["models"][selector]["signals"]
              if str(s["code"]) in company and START<=s["signalDate"]<=END and int(s["rank"])<=3]
    symbols={(x["code"],x["market"]) for z in candidates.values() for x in z}
    print("2026 TP/SL SETUP",{"selections":{k:len(v) for k,v in candidates.items()},"symbols":len(symbols)},flush=True)
    hist,errors=update_many(sorted(symbols),datetime(2025,8,1),datetime(2026,10,8))
    _,idx,ixerr=update_symbol("^TWII",datetime(2025,8,1),datetime(2026,10,8))
    if ixerr or idx is None or idx.empty:raise RuntimeError("TWII unavailable: "+str(ixerr))
    flags=index_status(idx)
    cal=[d for d in idx.date.astype(str).tolist() if d<=END]
    prices={k:prepare_bars(v) for k,v in hist.items()}
    # Reproduce the immutable previously published 7/-15 gross TP/SL first.
    ref_path=DATA_DIR/"research/model_execution_2026/g_capital_2026_summary.json"
    reference=json.loads(ref_path.read_text(encoding="utf-8"))
    old_checks={}
    for selector,sig in candidates.items():
        old_checks[selector]={}
        for mode in ("ladder","ma"):
            runs,dupes=run_model(sig,prices,cal,10,mode,"baseline",flags)
            st=summary(runs,dupes,mode,10)
            old_checks[selector][mode]={k:st[k] for k in ("filled","stopN","takeProfitN","avgNetOnReservedPct")}
            for k,v in old_checks[selector][mode].items():
                expected=reference["controlParity"][selector][mode][k]
                if v!=expected:raise RuntimeError(f"Baseline failed: {selector}/{mode}/{k} actual={v}, expected={expected}")
    output={};trade_stats={};curves={}
    for selector,sig in candidates.items():
        output[selector]={};trade_stats[selector]={};curves[selector]={}
        for mode in ("ladder","ma"):
            output[selector][mode]={};trade_stats[selector][mode]={};curves[selector][mode]={}
            for gate in ("baseline","signal_ma20","wait_ma20"):
                output[selector][mode][gate]={};trade_stats[selector][mode][gate]={};curves[selector][mode][gate]={}
                for rule,(take,stop) in TP_SL_VARIANTS.items():
                    rows,dupes=run_model(sig,prices,cal,10,mode,gate,flags,tp_pct=take,sl_pct=stop)
                    trade_stats[selector][mode][gate][rule]=summary(rows,dupes,mode,10)
                    output[selector][mode][gate][rule]={};curves[selector][mode][gate][rule]={}
                    for slots in SLOT_COUNTS:
                        s=run_capacity(sig,prices,cal,10,mode,gate,flags,slots,tp_pct=take,sl_pct=stop)
                        d=s.pop("dailyEquity")
                        output[selector][mode][gate][rule][str(slots)]=s
                        curves[selector][mode][gate][rule][str(slots)]=d
                        print("TP_SL_CASE "+json.dumps({"model":selector,"mode":mode,"gate":gate,"rule":rule,"slots":slots,
                             "filled":s["filled"],"tpPct":s["tpPct"],"slPct":s["stopPct"],
                             "netPct":s["totalReturnPct"],"maxDrawdownPct":s["maxDrawdownPct"],
                             "avgHoldDays":s["avgHoldDays"],"PF":s["profitFactor"]},ensure_ascii=False),flush=True)
    # Benchmark every cash-limited 7/-15 run against the archived 36-case study.
    cash_checks=0
    for selector in SELECTORS:
        for mode in ("ladder","ma"):
            for gate in MARKET_MODES:
                for slots in SLOT_COUNTS:
                    saved=reference["statistics"][selector][mode][gate][str(slots)]
                    now=output[selector][mode][gate]["tp7_sl15"][str(slots)]
                    for key in ("filled","tpN","stopN","totalReturnPct","maxDrawdownPct"):
                        if now[key]!=saved[key]:raise RuntimeError(f"Portfolio baseline mismatch {selector} {mode} {gate} {slots} {key}: {now[key]} vs {saved[key]}")
                    cash_checks+=1
    report={
        "version":"G_2026_TP_SL_3_10_CAPACITY_1",
        "generatedAt":datetime.now(ZoneInfo("Asia/Taipei")).isoformat(timespec="seconds"),
        "period":{"start":START,"end":END},
        "sourceModels":{k:len(v) for k,v in candidates.items()},
        "stockSymbols":len(symbols),"priceErrors":errors,
        "exitRules":{k:{"grossTakeProfitPct":round(t*100,2),"grossStopLossPct":round(s*100,2)} for k,(t,s) in TP_SL_VARIANTS.items()},
        "execution":{"maxTradingDays":10,"firstEntryWaitSessions":5,"capitalNTD":INITIAL_CAPITAL,"maxBasketSlots":list(SLOT_COUNTS),
                     "entryModes":{"ladder":"First limit 2.5% below signal close; 5 equal tranches every 2% below first fill",
                                   "ma":"Previous completed-day MA5/10/20/60 levels touched within current session"},
                     "marketGates":{"baseline":"No TWII filter","signal_ma20":"signal day completed TWII index close >= MA20",
                                    "wait_ma20":"allow next-day first buy only if prior completed TWII closes >= MA20"},
                     "costs":{"buyCommissionPct":.1425,"sellCommissionPct":.1425,"sellTaxPct":.3,"slippagePerSidePct":.1},
                     "entryPriority":"Frozen G 2026 Top3, date and rank; same-stock duplicate suppressed; slot reserved from signal date",
                     "exitOrder":"Existing open gap checks and adverse same-bar stop-before-profit fill policy; target based on average executed entry price",
                     "portfolioCash":"Non-leveraged cash approximating 3/5/10 live basket slots, pending first orders reserve slots",
                     "wholeShares":False},
        "archived7_15Checks":{"tradeBaselineParity":old_checks,"cashPortfolioParityN":cash_checks},
        "tradeLevel":trade_stats,"statistics":output,
        "warnings":[
            "This tests FIXED +3% take-profit and -10% stop-loss, NOT a minute-level BOTTOM entry / TOP exit trading strategy.",
            "TP and SL percentages are gross changes in weighted average stock purchase price, not net account profits.",
            "2026 sample explored repeatedly; strong in-sample selection / overfitting risk. Not independent future validation.",
            "Only 2026-01-01 through 2026-10-07. Trades near end without complete holding window excluded.",
            "Daily OHLC cannot reproduce intraday execution path or 2-minute BOTTOM and TOP signals. Potential same-day ambiguity even with adverse TP assumptions.",
            "Partial fills, tick sizes, prices adjusted for corporate actions, survivorship and order fills may change results.",
            "Cash accounting uses fractional baskets, simplified daily marked portfolio, no broker constraints, margin or overnight carry.",
            "Rules are frozen historical G Top3; no look-ahead beyond historical signal; this study does not change live rankings."
        ],
        "elapsedSeconds":round(time.time()-started,1)}
    out=DATA_DIR/"research/g_tp_sl_2026";out.mkdir(parents=True,exist_ok=True)
    (out/"summary.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    (out/"equity_curves.json").write_text(json.dumps({"version":report["version"],"daily":curves},ensure_ascii=False),encoding="utf-8")
    print("TP_SL_2026_COMPLETED "+json.dumps({"cases":cash_checks*len(TP_SL_VARIANTS),"baselineChecks":cash_checks,"seconds":report["elapsedSeconds"]}),flush=True)
if __name__=="__main__":run()
