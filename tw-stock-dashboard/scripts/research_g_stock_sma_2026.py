"""2026 G Double Persistence Top3 x individual-stock SMA10 / panic / SMA5 backtest.
Research branch only. All signals at D close; fills at next available D+1 open.
Uses *stock's own* SMA and daily percentage changes, never TWII averages.
"""
from __future__ import annotations
import collections,json,math,sys
from datetime import datetime,timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from yahoo_cache import update_many,update_symbol,to_symbol
SRC=ROOT/"docs/data/backtest_g/g_persistence_2026.json"
MARKETS=ROOT/"docs/data/research/model_execution_2026/trades/G_DOUBLE_PERSIST.json"
MARKETS_AUX=ROOT/"docs/data/research/model_execution_2026/trades/G_TRIGGER.json"
OUT=ROOT/"docs/data/research/g_stock_sma_2026"
START="2026-01-02"
SIGNAL_END="2026-10-07"
MARKET_END="2026-10-16"
INITIAL=1_000_000.
BUY_FACTOR=1+0.001425+0.001
SELL_FACTOR=1-0.001425-0.003-0.001
MAX_WEIGHT=.25
MAX_SLOTS=4
MODES={
"G_HOLD5":{"entry":"any","panic":None,"fast":False,"hold":5},
"G_SMA10":{"entry":"sma10","panic":None,"fast":False,"hold":None},
"G_SMA10_PANIC4":{"entry":"sma10","panic":.04,"fast":False,"hold":None},
"G_SMA10_PANIC4_CRASH2_SMA5":{"entry":"sma10","panic":.04,"fast":True,"hold":None},
"G_SMA10_PANIC7_CRASH2_SMA5":{"entry":"sma10","panic":.07,"fast":True,"hold":None},
}
def finite(x):
    try:return math.isfinite(float(x))
    except (ValueError,TypeError):return False
def compile_bars(df):
    if df is None or df.empty:return {}
    d=df.copy()
    for k in ("open","high","low","close","volume"):
        if k not in d:return {}
        d[k]=pd.to_numeric(d[k],errors="coerce")
    d=d.dropna(subset=["open","high","low","close"]).sort_values("date").drop_duplicates("date",keep="last")
    d=d[(d.open>0)&(d.high>0)&(d.low>0)&(d.close>0)&(d.high>=d.low)]
    if len(d)<12:return {}
    # Raw Yahoo OHLC is used consistently; do not fabricate split-session fills.
    d["sma5"]=d.close.rolling(5,min_periods=5).mean()
    d["sma10"]=d.close.rolling(10,min_periods=10).mean()
    d["ret1"]=d.close.pct_change()
    d["below10"]=(d.close<d.sma10*.98)
    d["below3"]=d.below10.rolling(3,min_periods=3).sum()>=3
    d["crash2_4"]=(d.ret1<=-.04)&(d.ret1.shift(1)<=-.04)
    d["crash2_7"]=(d.ret1<=-.07)&(d.ret1.shift(1)<=-.07)
    d["recent2_4"]=d.crash2_4.rolling(5,min_periods=1).max().astype(bool)
    d["recent2_7"]=d.crash2_7.rolling(5,min_periods=1).max().astype(bool)
    return {str(r["date"]):{k:(bool(r[k]) if k in ("below3","recent2_4","recent2_7") else (float(r[k]) if finite(r[k]) else None)) for k in
      ("open","high","low","close","sma5","sma10","ret1","below3","recent2_4","recent2_7")}
      for _,r in d.iterrows()}
def load_signals():
    raw=json.loads(SRC.read_text(encoding="utf-8"))
    rows=raw["models"]["G_DOUBLE_PERSIST"]["signals"]
    # Execution ledgers preserve exchange suffix; signal rankings alone do not.
    markets={}
    for file in (MARKETS,MARKETS_AUX):
        audit=json.loads(file.read_text(encoding="utf-8"))
        for p in audit["5"]["ladder"]:
            if p.get("market") in ("上市","上櫃"):
                code=str(p["code"]);m=p["market"]
                if code in markets and markets[code]!=m:raise RuntimeError("Market mismatch "+code)
                markets[code]=m
    officialFallback={"2409":"上市","1709":"上市","3094":"上市","6672":"上市"}
    markets.update({k:v for k,v in officialFallback.items() if k not in markets})
    out=collections.defaultdict(list);seen=set();unresolved=set()
    for p in rows:
        d=str(p["signalDate"]);code=str(p["code"]);market=markets.get(code)
        if not(START<=d<=SIGNAL_END):continue
        if market not in ("上市","上櫃"):
            unresolved.add(code);continue
        tag=(d,code)
        if tag in seen:raise RuntimeError("Duplicate G daily stock "+str(tag))
        seen.add(tag)
        out[d].append({"code":code,"market":market,"sym":to_symbol(code,market),
                        "name":p.get("name",code),"rank":int(p["rank"])})
    if unresolved:raise RuntimeError("Unresolved exchange for G symbols "+",".join(sorted(unresolved)))
    if len(out)<160 or len(seen)<475:raise RuntimeError(f"Incomplete G rank archive {len(out)} days, {len(seen)} rows")
    for d in out:out[d].sort(key=lambda x:x["rank"])
    return dict(out)
def rolling_stats(xs):
    w=[x for x in xs if x is not None]
    return round(sum(w)/len(w),3) if w else None
def run_one(mode,dates,signals,bars):
    cfg=MODES[mode]
    cash=INITIAL
    positions={}
    closed=[]
    equity_curve=[]
    exits=collections.Counter()
    buys=collections.Counter()
    missing=collections.Counter()
    lastG={}
    lastPanicExit={}
    maxdd=0.
    peak=INITIAL
    dateIndex={d:i for i,d in enumerate(dates)}
    early=0
    for idx,d in enumerate(dates):
        if d<START or d>MARKET_END:continue
        prev=dates[idx-1] if idx else None
        if prev is not None:
            for p in signals.get(prev,[]):lastG[p["sym"]]=idx-1
        exited_today=set()
        # Exits first, using only the prior fully completed daily candle.
        for sym,p in list(positions.items()):
            y=bars.get(sym,{}).get(prev)
            today=bars.get(sym,{}).get(d)
            if today is None:continue   # no fill when ETF/stock is untradable
            why=None
            if cfg["hold"] is not None:
                if idx-p["entryIdx"]>=cfg["hold"]:why="time5"
            elif y is not None:
                if cfg["panic"] is not None and y["ret1"] is not None and y["ret1"]<=-cfg["panic"]:why="panic"
                elif y["below3"]:why="sma10_3below"
            if why is None:continue
            sell=float(today["open"])*SELL_FACTOR
            income=p["qty"]*sell
            cash+=income
            pnl=income-p["cost"]
            closed.append({"sym":sym,"code":p["code"],"name":p["name"],"entryDate":p["entryDate"],
                           "exitDate":d,"entryPrice":round(p["entryPrice"],4),
                           "exitPrice":round(float(today["open"]),4),
                           "qty":p["qty"],"pnl":round(pnl,2),
                           "netPct":round(100*pnl/p["cost"],4),"holdDays":idx-p["entryIdx"],
                           "exitReason":why,"entryReason":p["entryReason"]})
            del positions[sym]
            exits[why]+=1
            exited_today.add(sym)
            if why=="panic":lastPanicExit[sym]=idx
        candidates=[]
        # The G portfolio may buy only ranks known at yesterday's close.
        if prev is not None:
            for x in signals.get(prev,[]):
                sym=x["sym"]
                y=bars.get(sym,{}).get(prev)
                if y is None:missing["no_prior_candle"]+=1;continue
                if cfg["entry"]=="any" or (
                  y["sma10"] is not None and y["close"]>y["sma10"]*1.01
                ):
                    candidates.append((x,"G_top3"))
                else:missing["entry_sma10_not_met"]+=1
        # Fast buyback is only for stocks previously held, sold by the panic
        # rule, and present on a G list recently. Never back-date G membership.
        if cfg["fast"] and prev is not None:
            key="recent2_4" if cfg["panic"]==.04 else "recent2_7"
            for sym,exitIdx in lastPanicExit.items():
                if sym in positions or sym in exited_today or idx-exitIdx>12:continue
                if idx-lastG.get(sym,-999)>20:continue
                y=bars.get(sym,{}).get(prev)
                if not y or not y.get(key) or y["sma5"] is None or y["close"]<=y["sma5"]:continue
                candidates.append(({"sym":sym,"code":sym.split(".")[0],"name":sym},"SMA5_fast"))
        for x,why in candidates:
            sym=x["sym"]
            if len(positions)>=MAX_SLOTS:break
            if sym in positions or sym in exited_today:continue
            today=bars.get(sym,{}).get(d)
            if today is None:
                missing["no_entry_open"]+=1;continue
            # Odd-lot fills are modeled at official daily open (research idealization).
            unit=float(today["open"])*BUY_FACTOR
            if unit<=0:continue
            eq=cash+sum(z["qty"]*float((bars.get(k,{}).get(d) or
                bars.get(k,{}).get(prev) or {"close":z["entryPrice"]})["close"])*SELL_FACTOR
                for k,z in positions.items())
            budget=min(MAX_WEIGHT*eq,cash)
            qty=math.floor((budget+1e-8)/unit)
            if qty<1:missing["insufficient_cash"]+=1;continue
            cost=qty*unit
            if cost>cash+0.01:continue
            cash-=cost
            positions[sym]={"code":x["code"],"name":x.get("name",sym),"qty":qty,
                "entryDate":d,"entryIdx":idx,"entryPrice":float(today["open"]),
                "cost":cost,"entryReason":why}
            buys[why]+=1
            if why=="SMA5_fast":early+=1;del lastPanicExit[sym]
        # End-of-day mark to liquidation value, including exit costs.
        val=cash
        for sym,p in positions.items():
            z=bars.get(sym,{}).get(d)
            if z is None:
                past=[q for date,q in bars.get(sym,{}).items() if date<=d]
                if not past:raise RuntimeError(f"Missing mark {sym} {d}")
                z=past[-1]
                missing["stale_marks"]+=1
            val+=p["qty"]*float(z["close"])*SELL_FACTOR
        peak=max(peak,val)
        maxdd=max(maxdd,1-val/peak)
        equity_curve.append({"date":d,"equity":round(val,2),"cash":round(cash,2),"positions":len(positions)})
    if not equity_curve:raise RuntimeError("Empty equity curve")
    wins=[t for t in closed if t["pnl"]>0]
    loses=[t for t in closed if t["pnl"]<=0]
    winP=sum(t["pnl"] for t in wins)
    lossP=-sum(t["pnl"] for t in loses)
    periods={}
    for yy in ("2026",):
        these=[x for x in equity_curve if x["date"].startswith(yy)]
        periods[yy]={"first":these[0]["date"],"last":these[-1]["date"],
           "returnPct":round(100*(these[-1]["equity"]/INITIAL-1),3)}
    summary={"model":mode,"periodStart":equity_curve[0]["date"],"periodEnd":equity_curve[-1]["date"],
        "startCapital":INITIAL,"endEquity":equity_curve[-1]["equity"],
        "netReturnPct":round(100*(equity_curve[-1]["equity"]/INITIAL-1),3),
        "maxDrawdownPct":round(-100*maxdd,3),"closedTrades":len(closed),
        "wins":len(wins),"losses":len(loses),
        "winRatePct":round(100*len(wins)/len(closed),2) if closed else None,
        "profitFactor":round(winP/lossP,3) if lossP>0 else None,
        "avgWinPct":rolling_stats([t["netPct"] for t in wins]),
        "avgLossPct":rolling_stats([t["netPct"] for t in loses]),
        "avgHoldDays":rolling_stats([t["holdDays"] for t in closed]),
        "openAtEnd":len(positions),"entryTypes":dict(buys),"exitTypes":dict(exits),
        "earlySMA5Rebuys":early,"skips":dict(missing),
        "maxPositions":MAX_SLOTS,"maxInitialWeightPct":MAX_WEIGHT*100,"yearly":periods}
    return summary,closed,equity_curve
def synthetic_test():
    # Deterministic invariants: completed closes only, panic threshold, 2-day crash.
    ds=pd.DataFrame([
        {"date":f"2026-01-{i+1:02d}","open":100.,"high":101.,"low":99.,"close":x,"volume":1000}
        for i,x in enumerate([100,101,102,103,104,105,100,95,101,102,103,104,105])
    ])
    z=compile_bars(ds)
    assert len(z)==13
    assert z["2026-01-08"]["ret1"]<-.04
    assert z["2026-01-08"]["recent2_4"] is True
    assert z["2026-01-09"]["recent2_4"] is True
    for p in MODES.values():assert p["panic"] is None or p["panic"]>0
    print("UNIT_TEST_OK",len(z),list(MODES))
def main():
    synthetic_test()
    picks=load_signals()
    unique={(x["code"],x["market"]) for pp in picks.values() for x in pp}
    begin=datetime(2025,10,1)
    end=datetime(2026,10,18)
    print("LOADING_MARKET",len(picks),"G days",sum(map(len,picks.values())),"G ranked entries",len(unique),"different symbols",flush=True)
    dfs,errors=update_many(sorted(unique),begin,end)
    _,index,indexErr=update_symbol("^TWII",begin,end)
    if indexErr or index is None or index.empty:raise RuntimeError("TWII calendar download failed "+str(indexErr))
    dates=sorted(set(str(d) for d in index.date if "2025-12-01"<=str(d)<=MARKET_END))
    if len(dates)<185:raise RuntimeError("Market calendar undercoverage: "+str(len(dates)))
    if dates[-1]!=MARKET_END:raise RuntimeError("Latest day unavailable "+dates[-1])
    symbols={to_symbol(c,m) for c,m in unique}
    bars={sym:compile_bars(dfs.get(sym)) for sym in symbols}
    good={sym for sym,df in bars.items() if len(df)>=100}
    if len(good)<len(symbols)*.85:
        raise RuntimeError(f"Stock daily OHLC coverage insufficient {len(good)}/{len(symbols)}: "+json.dumps(errors,ensure_ascii=False)[:1500])
    sourceData={"Garchive":"docs/data/backtest_g/g_persistence_2026.json",
        "stockBars":"Yahoo daily OHLC; cached source if present","benchmark":"TWII session calendar",
        "gScorePointInTime":"retrospectively backtested, NOT a preserved official historical daily top3",
        "signalDateEnd":SIGNAL_END,"gDays":len(picks),"gRows":sum(map(len,picks.values())),
        "gUniqueSymbols":len(symbols),"symbolDataUsable":len(good),"stockErrors":errors,
        "sessionCount":len([d for d in dates if START<=d<=MARKET_END])}
    OUT.mkdir(parents=True,exist_ok=True)
    allRows=[];allTrades={};allCurves={}
    for mode in MODES:
        metrics,trades,curve=run_one(mode,dates,picks,bars)
        allRows.append(metrics);allTrades[mode]=trades;allCurves[mode]=curve
        print("MODEL_DONE",json.dumps(metrics,ensure_ascii=False),flush=True)
    output={"version":"G_STOCK_SMA_2026_PREDECLARED_V1","generatedAt":datetime.now(ZoneInfo("Asia/Taipei")).isoformat(),
       "source":sourceData,"execution":{"startingCapitalTWD":INITIAL,"feeBuy":BUY_FACTOR-1,
       "feeSellAndTaxAndSlippage":1-SELL_FACTOR,"shareIncrement":1,
       "assumption":"daily close D triggers next D+1 open; odd-lot opening at official daily open optimistic; no intraday stops",
       "holdingSMA":"own stock SMA10, no borrowing/leverage","maxSlots":MAX_SLOTS,"entryAllocationPct":MAX_WEIGHT*100},
       "models":allRows,"notes":[
        "G model built after seeing 2026 history; results are retrospective, not fresh walk-forward out-of-sample.",
        "G signal list only through 2026-10-07; positions marked through 2026-10-16.",
        "SMA5 early reentry requires prior held G stock exited via panic, a recent G selection, and two daily crashes inside 5 sessions.",
        "SMA10 versions may hold indefinitely until confirmed exit, unlike G_HOLD5 time exit.",
        "G stock fees assume 0.1425% each-side broker, 0.3% sell tax, 0.1% each-side slippage.",
        "Cash dividends are not separately credited; no intraday stops; corporate actions and historic universes can introduce bias."
       ]}
    (OUT/"summary.json").write_text(json.dumps(output,ensure_ascii=False,indent=2),encoding="utf-8")
    (OUT/"trades.json").write_text(json.dumps({"version":output["version"],"models":allTrades},ensure_ascii=False),encoding="utf-8")
    (OUT/"equity.json").write_text(json.dumps({"version":output["version"],"models":allCurves},ensure_ascii=False),encoding="utf-8")
    print("ALL_RESEARCH_PASSED",len(allRows),"models",len(good),"stock series",flush=True)
if __name__=="__main__":main()
