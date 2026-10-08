"""Isolated H vs existing D/G 2026 event-driven 7% TP research.
No changes to website, published ranking, original D/G results or their source.
"""
from __future__ import annotations
import json,time,math,statistics
from pathlib import Path
from collections import defaultdict
from datetime import datetime,timedelta
from zoneinfo import ZoneInfo
import numpy as np,pandas as pd
from config import DATA_DIR,MAX_CAPITAL_B,BENCHMARK
from pipeline import load_universe
from yahoo_cache import update_many,update_symbol,to_symbol
from scoring import precompute_features
from h_turnover import score_h,exit_trade
START="2026-01-01";END="2026-10-07";HORIZONS=[1,3,5,10,20];TOP=3
ROOT=Path(__file__).resolve().parents[1]
def stats(vals):
    xs=[float(v) for v in vals if v is not None and np.isfinite(v)]
    return {"n":len(xs),"avg":round(float(np.mean(xs)),2) if xs else None,"median":round(float(np.median(xs)),2) if xs else None,"win":round(sum(x>0 for x in xs)/len(xs)*100,1) if xs else None,"avgWin":round(float(np.mean([x for x in xs if x>0])),2) if any(x>0 for x in xs) else None,"avgLoss":round(float(np.mean([x for x in xs if x<0])),2) if any(x<0 for x in xs) else None}
def load_signals(filename,model_name):
    d=json.loads((DATA_DIR/filename).read_text(encoding="utf-8"))
    m=d.get("models",{})
    if isinstance(m,list):m={x["id"]:x for x in m}
    if model_name not in m:raise RuntimeError(f"Baseline {model_name} not found in {filename}")
    result=defaultdict(list)
    for row in m[model_name].get("signals",[]):
        day=str(row.get("signalDate") or "")
        if START<=day<=END and 1<=int(row.get("rank") or 999)<=TOP:
            result[day].append({"code":str(row["code"]),"market":row["market"],"name":row["name"],"rank":int(row["rank"])})
    for day in result:result[day]=sorted(result[day],key=lambda x:x["rank"])
    return result
def build_h(hist,stocks,market20,signal_dates):
    pool=defaultdict(list);aud={"validOHLC":0,"missingStock":0,"qualifiedStockDays":0,"proxyExcludedMarketCaps":0}
    for i,s in enumerate(stocks):
        capital=float(s.get("capitalB") or 0)
        if capital<=0 or capital>=MAX_CAPITAL_B:continue
        key=to_symbol(s["code"],s["market"]);df=hist.get(key)
        if df is None or len(df)<55:
            aud["missingStock"]+=1;continue
        z=precompute_features(df)
        if z.empty:continue
        aud["validOHLC"]+=1
        z=z[(z.date.astype(str)>=START)&(z.date.astype(str)<=END)]
        if z.empty:continue
        for _,row in z.iterrows():
            dt=str(row["date"]);mkt=market20.get(dt)
            if mkt is None:continue
            m=row.to_dict()
            if not pd.notna(m.get("volume")) or not pd.notna(m.get("close")):continue
            rs=float(m.get("ret20") or 0)-mkt
            value_b=float(m["close"])*float(m["volume"])/100_000_000
            h=score_h(m,rs,capital,value_b)
            if h is not None:
                aud["qualifiedStockDays"]+=1
                pool[dt].append({"code":str(s["code"]),"name":str(s["name"]),"market":str(s["market"]),"capitalB":capital,**h})
        if (i+1)%400==0:print(f"H features {i+1}/{len(stocks)}",flush=True)
    result={}
    for date in signal_dates:
        xs=sorted(pool.get(date,[]),key=lambda x:(-x["score"],-x["turnoverProxyPct"],-x["rs20"],x["code"]))
        result[date]=[{**x,"rank":i+1} for i,x in enumerate(xs[:TOP])]
    aud["candidateDays"]=sum(bool(v) for v in pool.values());aud["daysAtLeast3"]=sum(len(v)>=3 for v in pool.values())
    aud["candidateAvg"]=round(sum(len(pool.get(d,[])) for d in signal_dates)/max(1,len(signal_dates)),2)
    aud["turnoverRateCaution"]="Current paid-in capital/NT$10 par proxy, not time-varying issued shares; can be distorted by stock splits/par changes"
    return result,aud
def simulate_model(name,signals,dates,index_pos,pxmap,h):
    daily=[];all_trades=[];signals_with_positions=0;unavailable=0
    for d in dates:
        si=index_pos[d]
        if si+1>=len(index_pos) or si+h>=len(index_pos):continue
        buydate=dates[si+1];exitdate=dates[si+h]
        active=[];used=set()
        for row in signals.get(d,[])[:TOP]:
            code=row["code"]
            if code in used:continue
            used.add(code)
            sym=to_symbol(code,row["market"])
            result=exit_trade(pxmap.get(sym),buydate,exitdate)
            if result is None:
                unavailable+=1;continue
            active.append({"signalDate":d,"model":name,"code":code,"name":row["name"],"market":row["market"],"rank":row["rank"],"horizon":h,**{k:v for k,v in row.items() if k in ("score","turnoverProxyPct","rvol10","rs20")},"buyDate":buydate,**result})
        if active:
            signals_with_positions+=1
            daily.append({"date":d,"ret":sum(x["netPct"] for x in active)/TOP,"slots":len(active),"tp":sum(x["reason"].startswith("tp") for x in active)})
            all_trades+=active
    vals=[t["netPct"] for t in all_trades]
    by_reason={r:sum(t["reason"]==r for t in all_trades) for r in ("tp","tp_gap","stop","stop_gap","timeout")}
    wins=[v for v in vals if v>0];losses=[v for v in vals if v<0]
    pf=sum(wins)/abs(sum(losses)) if losses else None
    # A single 3-slot portfolio can only deploy every h-th signal date; stay in cash if no candidates.
    equity=1.;peak=1.;mdd=0.;curve=[];invested=0
    daily_map={x["date"]:x for x in daily}
    for n in range(0,len(dates),h):
        day=dates[n]
        if n+1>=len(dates) or n+h>=len(dates):break
        rec=daily_map.get(day)
        net=rec["ret"] if rec else 0.
        if rec:invested+=1
        equity*=max(0.,1.+net/100.)
        peak=max(peak,equity);mdd=max(mdd,(1-equity/peak)*100)
        curve.append({"date":dates[n+h],"equity":round(equity,6),"cohortNet":round(net,3)})
    totalcohorts=len(curve)
    result={"daysWithPositions":signals_with_positions,"trades":len(all_trades),"unavailableBarPairs":unavailable,"tradeNet":stats(vals),
            "top3SlotDailyNet":stats([x["ret"] for x in daily]),"targetHits":by_reason["tp"]+by_reason["tp_gap"],"targetHitPct":round(100*(by_reason["tp"]+by_reason["tp_gap"])/len(vals),1) if vals else None,
            "exitReasons":by_reason,"profitFactor":round(pf,3) if pf is not None else None,
            "nonOverlappingPortfolio":{"cohorts":totalcohorts,"investedCohorts":invested,"totalNetReturnPct":round((equity-1)*100,2),"mddPct":round(mdd,2),"curve":curve}}
    return result,all_trades
def run():
    start_clock=time.time()
    all_u=load_universe();stocks=[x for x in all_u if 0<float(x.get("capitalB") or 0)<MAX_CAPITAL_B]
    fs=datetime(2025,8,1);fe=min(datetime.now(ZoneInfo("Asia/Taipei")).replace(tzinfo=None),datetime(2026,10,28))
    print(f"H 2026 universe={len(stocks)} whole_market={len(all_u)} fetch={fs.date()}..{fe.date()}",flush=True)
    hist,errors=update_many([(x["code"],x["market"]) for x in all_u],fs,fe)
    _,ix,idxerr=update_symbol(BENCHMARK,fs,fe)
    if idxerr or ix is None or len(ix)<50:raise RuntimeError("Index data insufficient: "+str(idxerr))
    ix=ix.sort_values("date").drop_duplicates("date")
    dates=ix.date.astype(str).tolist();pos={d:i for i,d in enumerate(dates)}
    signal_dates=[d for d in dates if START<=d<=END];close=pd.to_numeric(ix.close,errors="coerce")
    rel=(close/close.shift(20)-1)*100;market20=dict(zip(dates,rel))
    market20={d:float(v) for d,v in market20.items() if np.isfinite(v)}
    hs,hinfo=build_h(hist,stocks,market20,signal_dates)
    d=load_signals("backtest/2026-01-01_2026-10-08.json","D")
    g=load_signals("backtest_g/g_persistence_2026.json","G_DOUBLE_PERSIST")
    pxmap={sym:df.sort_values("date").drop_duplicates("date",keep="last").set_index("date",drop=False) for sym,df in hist.items() if df is not None and not df.empty}
    signals={"H":hs,"D":d,"G":g};summary={};trades=[]
    for h in HORIZONS:
        summary[str(h)]={}
        for name,records in signals.items():
            r,t=simulate_model(name,records,dates,pos,pxmap,h)
            summary[str(h)][name]={k:v for k,v in r.items() if k!="nonOverlappingPortfolio"}
            summary[str(h)][name]["portfolio"]={k:v for k,v in r["nonOverlappingPortfolio"].items() if k!="curve"}
            trades+=t if h==5 else []
        print("H_COMPARE "+json.dumps({"horizon":h,"data":summary[str(h)]},ensure_ascii=False),flush=True)
    output={"version":"H-TURNOVER-TP7-2026-V1","generatedAt":datetime.now(ZoneInfo("Asia/Taipei")).isoformat(timespec="seconds"),
            "period":{"start":START,"end":END},"signalDays":len(signal_dates),"universe":len(stocks),"historicalPriceErrors":len(errors),
            "hCriteria":{"capitalBMax":MAX_CAPITAL_B,"turnoverProxyPctMin":5.0,"rvol10Min":1.4,"rs20Min":4.0,
                         "ret5Min":3.0,"ret20Min":5.0,"minTradedValueNTD":150_000_000,
                         "closeAboveEma20":True,"ema20Slope5Positive":True,"closePositionMin":60,"near20DayHighPctMin":-4,
                         "atrPctMin":2.5,"mom10Positive":True,"dayRetMaxExclusive":9.5,
                         "score":"24% turnover proxy + 16% RVOL10 +20% RS20 +15% 5D momentum +15% 20-day breakout +10% ATR"},
            "execution":{"signal":"close of completed day","entry":"next trading-day open","takeProfitGrossPct":7,"stopLossGrossPct":-4,
                         "maxTradingDays":HORIZONS,"slippageEachSidePct":0.1,"buyFeePct":0.1425,"sellFeePct":0.1425,"sellTaxPct":0.3,
                         "sameDayHighLowConflict":"stop assumed first","bothGapAndThreshold":"gap open first",
                         "positionSize":"three equal 1/3 slots; missing candidates stay cash"},
            "baseline":{"D":"official backtest archive strict D Top3","G":"G_DOUBLE_PERSIST 2026 signal Top3"},
            "coverage":hinfo,"baselineSignalDays":{k:len(v) for k,v in signals.items()},
            "comparison":summary,"warnings":["H turnover uses current paid-in capital proxy with assumed NT$10 par value; historical issued share counts not available: lookahead/survivorship bias risk","Daily OHLC cannot establish intraday ordering or fill probability; stops precede targets if both touched; slippage is an assumption","2026 sample is in-sample exploratory, no parameter tuning performed and no future return guaranteed","Baseline G historical selection was previously developed using 2026 data, hence independently validating it with 2026 again is in-sample","Target +7% is before fees; after 0.1% slippage each side, commissions and 0.3% sell tax, realized TP net is typically below 7%"],
            "elapsedSeconds":round(time.time()-start_clock,1)}
    p=DATA_DIR/"backtest_h";p.mkdir(parents=True,exist_ok=True)
    (p/"H_2026_summary.json").write_text(json.dumps(output,ensure_ascii=False,indent=2),encoding="utf-8")
    (p/"H_2026_trades5D.json").write_text(json.dumps(trades,ensure_ascii=False,indent=2),encoding="utf-8")
    (p/"H_2026_top3.json").write_text(json.dumps({k:v for k,v in hs.items() if v},ensure_ascii=False,indent=2),encoding="utf-8")
    print("H_2026_RESULT "+json.dumps({"period":output["period"],"signalDays":output["signalDays"],"coverage":hinfo,"comparison":summary,"elapsedSeconds":output["elapsedSeconds"]},ensure_ascii=False),flush=True)
    return output
if __name__=="__main__":run()
