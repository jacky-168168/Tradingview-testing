"""00675L daily trend-capture rotation research.
Parameter ranking uses 2024-2025 only; 2026 is read only for precommitted finalists.
A single NT$1m cash account reinvests available profits. Regime switches rebalance on
next-session OPEN; no lookahead or assumed perfect peak/trough execution.
"""
from __future__ import annotations
import json,math,time,itertools
from datetime import datetime
from zoneinfo import ZoneInfo
import numpy as np,pandas as pd
from research_00675l_swing_grid import data_prepare,update_symbol,SYMBOL,INDEX,BROKER,ETF_SELL_TAX,SLIP,CAPITAL,DATA_DIR
START="2024-01-01";DEVELOP_END="2025-12-31";TEST_START="2026-01-01";TEST_END="2026-10-08"
OUT=DATA_DIR/"research/etf_00675l_trend_capture_2024_2026"
def prepare():
    _,etf,e1=update_symbol(SYMBOL,datetime(2023,5,1),datetime(2026,10,9))
    _,twii,e2=update_symbol(INDEX,datetime(2023,5,1),datetime(2026,10,9))
    if e1 or e2 or etf is None or twii is None or etf.empty or twii.empty:
        raise RuntimeError("Unable to get market data "+str((e1,e2)))
    d=data_prepare(etf,twii)
    if len(d[d.date.between(START,DEVELOP_END)])<450 or len(d[d.date.between(TEST_START,TEST_END)])<170:raise RuntimeError("incomplete OHLC history")
    for n in (10,20,40,60,120):
        d["twii_ma"+str(n)]=d.twii.rolling(n,min_periods=n).mean()
        d["etf_ma"+str(n)]=d.close.rolling(n,min_periods=n).mean()
        d["etf_ret"+str(n)]=d.close/d.close.shift(n)-1
        d["twii_ret"+str(n)]=d.twii/d.twii.shift(n)-1
    for n in (20,40,60,120):
        d["etf_dd"+str(n)]=d.close/d.close.rolling(n,min_periods=n).max()-1
    return d
def candidates():
    configs=[{"id":"BUY_HOLD","family":"hold","off":1.0}]
    for source,ma,fast,buf,off,confirm in itertools.product(("twii","etf"),(10,20,40,60,120),(10,20),(0,.02,.04),(0,.25,.5,.75),(1,3)):
        if fast>ma:continue
        c={"id":f"MA_{source}_{ma}_F{fast}_B{int(buf*100)}_OFF{int(off*100)}_C{confirm}",
           "family":"ma","source":source,"ma":ma,"fast":fast,"buffer":buf,"off":off,"confirm":confirm}
        configs.append(c)
    for etf_ma,index_ma,off,confirm in itertools.product((10,20,40),(20,60),(0,.25,.5,.75),(1,3)):
        for entry in ("either","both"):
            configs.append({"id":f"DUAL_E{etf_ma}_I{index_ma}_OFF{int(off*100)}_C{confirm}_{entry}",
                "family":"dual","etf_ma":etf_ma,"index_ma":index_ma,"off":off,"confirm":confirm,"entry":entry})
    for window,threshold,off,reentry in itertools.product((20,40,60,120),(.08,.12,.16,.20), (0,.25,.5,.75),("ema10","index20","both")):
        configs.append({"id":f"DD{window}_T{int(threshold*100)}_OFF{int(off*100)}_{reentry}",
                "family":"drawdown","window":window,"threshold":threshold,"off":off,"reentry":reentry})
    for source,lookback,limit,off,reentry in itertools.product(("twii","etf"),(10,20,40,60),(-.02,0,.02),(0,.25,.5,.75),("ma10","ma20")):
        configs.append({"id":f"MOM_{source}{lookback}_L{limit}_OFF{int(off*100)}_{reentry}",
                "family":"momentum","source":source,"lookback":lookback,"limit":limit,"off":off,"reentry":reentry})
    # Try gradually reducing just a small satellite sleeve rather than fully exiting the high beta ETF.
    for etf_ma,index_ma,off in itertools.product((10,20),(20,60),(.5,.75,.90)):
        configs.append({"id":f"CORE_ETF{etf_ma}_IDX{index_ma}_OFF{int(off*100)}",
                "family":"core","etf_ma":etf_ma,"index_ma":index_ma,"off":off,"confirm":2,"entry":"either"})
    return configs
def arrays(d):
    keys=["open","close","twii","ema10","ema20","ema40","sma20","sma60"]+[f"{src}_{field}{n}" for src in ("etf","twii") for field,ns in (("ma",(10,20,40,60,120)),("ret",(10,20,40,60,120))) for n in ns]+[f"etf_dd{n}" for n in (20,40,60,120)]
    return {k:d[k].to_numpy(dtype=float) for k in set(keys)}
def raw_exit_enter(a,c,k):
    fam=c["family"]
    if fam=="hold":return False,True
    if fam=="ma":
        val=a["twii"][k] if c["source"]=="twii" else a["close"][k]
        prev=a["twii"][k-1] if c["source"]=="twii" else a["close"][k-1]
        slow=a[c["source"]+"_ma"+str(c["ma"])][k]
        fast=a[c["source"]+"_ma"+str(c["fast"])][k]
        if not np.isfinite(slow) or not np.isfinite(fast):return False,False
        buffer=c["buffer"]
        below=val<slow*(1-buffer)
        if below and c["confirm"]==3:
            # confirm consecutive closes below the same-day MA; all observed before subsequent open
            for j in (k-1,k-2):
                if j<0 or not (a["twii" if c["source"]=="twii" else "close"][j]<a[c["source"]+"_ma"+str(c["ma"])][j]*(1-buffer)):below=False;break
        enter=val>fast*(1+buffer/2)
        return bool(below),bool(enter)
    if fam in ("dual","core"):
        e=a["close"][k];t=a["twii"][k]
        eavg=a["etf_ma"+str(c["etf_ma"])][k];tavg=a["twii_ma"+str(c["index_ma"])][k]
        if not (np.isfinite(eavg) and np.isfinite(tavg)):return False,False
        below=e<eavg and t<tavg
        if below and c.get("confirm",1)>1:
            for j in range(k-c["confirm"]+1,k):
                if j<0 or not (a["close"][j]<a["etf_ma"+str(c["etf_ma"])][j] and a["twii"][j]<a["twii_ma"+str(c["index_ma"])][j]):below=False;break
        fast_e=e>a["ema10"][k];fast_t=t>a["twii_ma20"][k]
        enter=(fast_e or fast_t) if c["entry"]=="either" else (fast_e and fast_t)
        return bool(below),bool(enter)
    if fam=="drawdown":
        dd=a["etf_dd"+str(c["window"])][k]
        if not np.isfinite(dd):return False,False
        above_ema=a["close"][k]>a["ema10"][k]
        above_index=a["twii"][k]>a["twii_ma20"][k]
        entry={"ema10":above_ema,"index20":above_index,"both":above_ema and above_index}[c["reentry"]]
        return bool(dd<=-c["threshold"]),bool(entry)
    if fam=="momentum":
        f=c["source"];ret=a[f+"_ret"+str(c["lookback"])][k]
        if not np.isfinite(ret):return False,False
        val=a["twii" if f=="twii" else "close"][k]
        ma=a[f+"_ma"+("10" if c["reentry"]=="ma10" else "20")][k]
        return bool(ret<c["limit"]),bool(val>ma)
    raise RuntimeError("Unknown signal family")
def simulate(d,a,c,begin,end,full=False):
    idx=np.flatnonzero((d.date.to_numpy(dtype="U10")>=begin)&(d.date.to_numpy(dtype="U10")<=end))
    if len(idx)<40:raise RuntimeError("too few daily observations")
    cash=float(CAPITAL);q=0;mode=1;orders=0;switches=0;cash_days=0;in_days=0;trades=[];nav=[];entry_px=None
    def rebalance(open_price,target,date,last=False):
        nonlocal q,cash,orders,entry_px
        if target>=1 and q==0 or target>0:
            pass
        mval=cash+q*open_price
        current_exposure=q*open_price/max(mval,1)
        if target>=.9999:
            desired=math.floor(mval/(open_price*(1+SLIP)*(1+BROKER)))
        elif target<=0:
            desired=0
        else:
            desired=math.floor(mval*target/open_price)
        delta=desired-q
        if delta>0:
            px=open_price*(1+SLIP)
            n=min(delta,math.floor(max(cash,0)/(px*(1+BROKER))))
            if n>0:
                cost=n*px*(1+BROKER);cash-=cost;q+=n;orders+=1
                trades.append({"date":date,"side":"buy","units":int(n),"price":round(px,4),"amountNTD":round(cost,2)})
        elif delta<0:
            n=-delta;px=open_price*(1-SLIP)
            proceeds=n*px*(1-BROKER-ETF_SELL_TAX);cash+=proceeds;q-=n;orders+=1
            trades.append({"date":date,"side":"sell","units":int(n),"price":round(px,4),"amountNTD":round(proceeds,2)})
    for h,i in enumerate(idx):
        px=float(a["open"][i]);date=str(d.iloc[i].date)
        if h==0:rebalance(px,1.0,date)
        else:
            ex,en=raw_exit_enter(a,c,i-1)
            if mode and ex:mode=0;switches+=1
            elif not mode and en:mode=1;switches+=1
            if mode:in_days+=1
            else:cash_days+=1
            target=1.0 if mode else c["off"]
            # Rebalance only when the desired regime changes, never rebalance every price bar.
            if h==1 or mode!=previous_mode:rebalance(px,target,date)
        previous_mode=mode
        close=float(a["close"][i])
        equity=cash+q*close*(1-SLIP)*(1-BROKER-ETF_SELL_TAX)
        nav.append({"date":date,"equity":round(equity,2),"units":int(q),"cashNTD":round(cash,2),"regime":int(mode)})
    if q:
        day=idx[-1];close=float(a["close"][day])
        proceeds=q*close*(1-SLIP)*(1-BROKER-ETF_SELL_TAX);cash+=proceeds
        trades.append({"date":str(d.iloc[day].date),"side":"final_sell","units":int(q),"price":round(close*(1-SLIP),4),"amountNTD":round(proceeds,2)})
        q=0;nav[-1]["equity"]=round(cash,2);nav[-1]["units"]=0;nav[-1]["cashNTD"]=round(cash,2)
    vec=np.asarray([r["equity"] for r in nav])
    peaks=np.maximum.accumulate(np.r_[CAPITAL,vec])[1:]
    dd=float(np.min(100*(vec/peaks-1)))
    days=int(sum(z["units"]>0 for z in nav))
    yearly={}
    year_start=CAPITAL
    for year in sorted(set(r["date"][:4] for r in nav)):
        last=next(r for r in reversed(nav) if r["date"].startswith(year))
        equity=last["equity"]
        yearly[year]={"startNTD":round(year_start,2),"endNTD":equity,
                      "returnPct":round((equity/year_start-1)*100,3)}
        year_start=equity
    result={"start":nav[0]["date"],"end":nav[-1]["date"],"endingNTD":round(cash,2),
       "returnPct":round((cash/CAPITAL-1)*100,3),"maxDrawdownPct":round(dd,3),
       "tradeOrders":orders,"regimeSwitches":switches,"heldSessions":days,
       "totalSessions":len(nav),"exposureDaysPct":round(100*days/len(nav),2),
       "yearly":yearly}
    if full:result.update({"dailyEquity":nav,"orders":trades})
    return result
def freeze_rank(train,hold):
    # Only rank based on 2024-25. Lower switching and lower peak-to-trough loss preferred.
    filtered=[x for x in train if x["id"]!="BUY_HOLD" and x["train"]["regimeSwitches"]>=2]
    for x in filtered:
        v=x["train"];cap=v["returnPct"]/hold["returnPct"]
        ddgain=abs(hold["maxDrawdownPct"])-abs(v["maxDrawdownPct"])
        x["captureTrainPct"]=round(cap*100,3)
        x["ddImprovementTrainPP"]=round(ddgain,3)
        x["scoreTrain"]=round(v["returnPct"]+.9*ddgain-0.8*v["tradeOrders"],3)
    by_group={}
    for x in filtered:
        fam=x["params"]["family"]
        by_group.setdefault(fam,[]).append(x)
    ids=["BUY_HOLD"]
    picked=[]
    def add(x,label):
        if x["id"] not in ids:
            ids.append(x["id"]);picked.append({"id":x["id"],"selection":label})
    eligible=[x for x in filtered if x["train"]["returnPct"]>0 and
      x["train"]["yearly"]["2024"]["returnPct"]>0 and x["train"]["yearly"]["2025"]["returnPct"]>0]
    for x in sorted(eligible,key=lambda x:(-x["scoreTrain"],x["id"]))[:4]:add(x,"best_train_balance")
    guards=[x for x in eligible if x["ddImprovementTrainPP"]>=8]
    for x in sorted(guards,key=lambda x:(-x["train"]["returnPct"],x["id"]))[:3]:add(x,"train_dd_improvement_at_least_8pp")
    for fam,items in by_group.items():
        viable=[x for x in items if x["train"]["returnPct"]>0 and x["train"]["regimeSwitches"]>=3]
        for x in sorted(viable,key=lambda x:(-x["scoreTrain"],x["id"]))[:2]:add(x,"family_"+fam)
    for fraction in (.25,.5,.75):
        subset=[x for x in eligible if x["params"]["off"]==fraction]
        if subset:add(sorted(subset,key=lambda x:(-x["train"]["returnPct"],x["id"]))[0],"core_satellite_"+str(fraction))
    return ids,picked
def main():
    started=time.time();d=prepare();a=arrays(d);cfg=candidates()
    bench={"id":"BUY_HOLD","family":"hold","off":1.0}
    reftrain=simulate(d,a,bench,START,DEVELOP_END)
    full_hold=simulate(d,a,bench,START,TEST_END)
    train=[]
    for n,c in enumerate(cfg):
        z=simulate(d,a,c,START,DEVELOP_END)
        train.append({"id":c["id"],"params":c,"train":z})
        if (n+1)%300==0:print("TREND_CAPTURE_TRAIN_PROGRESS",n+1,"/",len(cfg),flush=True)
    ids,selection=freeze_rank(train,reftrain)
    lookup={x["id"]:x for x in train}
    results=[]
    for id in ids:
        c=lookup[id]["params"]
        oos=simulate(d,a,c,TEST_START,TEST_END)
        continuous=simulate(d,a,c,START,TEST_END,full=True)
        ratio=100*continuous["returnPct"]/full_hold["returnPct"]
        savings=abs(full_hold["maxDrawdownPct"])-abs(continuous["maxDrawdownPct"])
        output={"id":id,"params":c,"train":lookup[id]["train"],"oos2026":oos,
          "continuous2024_2026":{k:v for k,v in continuous.items() if k not in ("dailyEquity","orders")},
          "holdReturnCapturePct":round(ratio,2),"maxDDImprovementVsHoldPP":round(savings,3),
          "orders":continuous["orders"],"dailyEquity":continuous["dailyEquity"]}
        results.append(output)
        print("TREND_CAPTURE_FINALIST "+json.dumps({"id":id,"trainReturnPct":lookup[id]["train"]["returnPct"],
          "oosReturnPct":oos["returnPct"],"fullReturnPct":continuous["returnPct"],
          "fullDrawdownPct":continuous["maxDrawdownPct"],"capturePct":round(ratio,2),
          "regimeSwitches":continuous["regimeSwitches"],"exposureDaysPct":continuous["exposureDaysPct"]},ensure_ascii=False),flush=True)
    selected={name:next(r for r in results if r["id"]==name) for name in ids}
    archive={"version":"00675L_TREND_CAPTURE_ROTATION_V1",
      "generatedAt":datetime.now(ZoneInfo("Asia/Taipei")).isoformat(timespec="seconds"),
      "ticker":SYMBOL,"start":START,"requestedEnd":TEST_END,"actualEnd":str(d.iloc[-1].date),
      "model":{"initialCapitalNTD":CAPITAL,"brokerFeeEachSidePct":100*BROKER,
        "etfSellTaxPct":100*ETF_SELL_TAX,"slippageEachSidePct":100*SLIP,
        "priceData":"00675L and TAIEX daily Yahoo historical OHLC, with adjusted OHLC corporate action factor",
        "orders":"Completed close signal, NEXT session open trade (no clairvoyance); liquidation mark-to-market at daily close after conservative exit costs.",
        "capital":"Whole-unit cash ETF, all profits automatically reinvested when regime changes; no financing or futures hedging.",
        "riskOff":"Target exposure 0/25/50/75/90% when risk-off. 100% ETF exposure during risk-on. No daily automatic rebalancing if regime stays same.",
        "train":"2024-25 ONLY; rank by cash equity return +0.9*improved drawdown -0.8*trade orders, plus per-family choices",
        "verification":"2026 selected finalists evaluated without selecting extra settings from 2026 outcomes."},
      "nCases":len(cfg),"trainingPeriod":{"start":START,"end":DEVELOP_END,"sessions":reftrain["totalSessions"]},
      "testPeriod":{"start":TEST_START,"end":str(d.iloc[-1].date)},
      "benchmark":{"training":reftrain,"2026":simulate(d,a,bench,TEST_START,TEST_END),
                   "continuous":full_hold},
      "freezeList":selection,
      "familyCounts":{f:sum(x["params"]["family"]==f for x in train) for f in sorted(set(x["params"]["family"] for x in train))},
      "selectedCases":[{k:v for k,v in r.items() if k not in ("orders","dailyEquity")} for r in results],
      "trainTop25":[{k:v for k,v in x.items() if k!="train"}|{"trainReturnPct":x["train"]["returnPct"],"trainDrawdownPct":x["train"]["maxDrawdownPct"]} for x in sorted((x for x in train if "scoreTrain" in x),key=lambda x:(-x["scoreTrain"],x["id"]))[:25]],
      "warnings":["2026 is NOT an untouched researcher-level holdout because multiple previous experiments already examined that period.",
      "Strategy searches of hundreds of related thresholds increase multiple-testing bias. Selection criteria only used 2024-25 outputs.",
      "Single daily OHLC cannot test true 2-minute Bottom/Top signals or exact intra-bar fill sequencing.",
      "Daily 2x ETF compounding and market gap risk can produce losses far beyond the perceived stop or signal level.",
      "Full compounding causes growing notional exposure; no margin and no external contributions.",
      "Partial exposure portfolio cash isn't earning bank interest; conservative broad simulation not broker execution confirmation.",
      "Intraday commissions, discount broker rates and dividend corporate actions could change realized results."],
      "elapsedSeconds":round(time.time()-started,1)}
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/"summary.json").write_text(json.dumps(archive,ensure_ascii=False,indent=2),encoding="utf-8")
    (OUT/"selected_daily_equity_orders.json").write_text(json.dumps({"version":archive["version"],"cases":{r["id"]:{"orders":r["orders"],"dailyEquity":r["dailyEquity"]} for r in results}},ensure_ascii=False),encoding="utf-8")
    (OUT/"all_train.json").write_text(json.dumps({"version":archive["version"],"training":train},ensure_ascii=False),encoding="utf-8")
    print("TREND_CAPTURE_COMPLETE "+json.dumps({"studied":len(cfg),"selected":len(ids),"holdContinuousPct":full_hold["returnPct"],
       "maxDD":full_hold["maxDrawdownPct"],"bestHoldCapture":max((z["holdReturnCapturePct"] for z in results if z["id"]!="BUY_HOLD"),default=0),
       "seconds":archive["elapsedSeconds"]},ensure_ascii=False),flush=True)
if __name__=="__main__":main()
