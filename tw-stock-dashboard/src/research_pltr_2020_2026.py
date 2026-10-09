"""PLTR actual listing-to-2026 account backtest; no pre-IPO prices.
Price/volume: Yahoo PLTR; USD/TWD: Yahoo TWD=X, daily, adjusted OHLC.
Trained candidates only 2020-09-30 to 2023-12-29; 2024-25 and 2026 never
used for selection. All strategies begin at first-session OPEN with USD cash
converted from NT$1m, compound proceeds, no margin, close signal -> next OPEN.
"""
from __future__ import annotations
import json,math,itertools,time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import numpy as np,pandas as pd
from yahoo_cache import update_symbol
from config import DATA_DIR
START="2020-09-30";END="2026-10-08";TRAIN=(START,"2023-12-29")
VALID=("2024-01-01","2025-12-31");AUDIT=("2026-01-01",END);FULL=(START,END)
NTD_START=1_000_000;BROKER=.001425;SLIP=.001;US_SELL_TAX=0
OUT=DATA_DIR/"research/pltr_2020_2026"
FAMILIES=("SMA","EMA","WMA","VWMA")
WINDOWS=(5,10,15,20,30,50,75,100,150,200)
DOWNS=(0.,.02,.04,.07,.10)
UPS=(0.,.01,.03,.05)
CONFIRMS=(1,2,3)
def load(symbol):
    _,d,err=update_symbol(symbol,datetime(2018,1,1),datetime(2026,10,9))
    if err or d is None or d.empty:raise RuntimeError(f"Cannot retrieve genuine {symbol} price series: {err}")
    d=d.copy().sort_values("date").drop_duplicates("date",keep="last")
    for col in ("open","high","low","close","volume","adjclose"):
        d[col]=pd.to_numeric(d[col],errors="coerce")
    d=d.dropna(subset=["date","open","close","adjclose","volume"]).reset_index(drop=True)
    d["date"]=d.date.astype(str)
    d["adjFactor"]=d.adjclose/d.close
    if d.adjFactor.isna().any() or (d.adjFactor<=0).any():raise RuntimeError("Invalid corporate-action adjustment")
    for col in ("open","high","low","close"):d[col]=d[col]*d.adjFactor
    d=d[(d.date>=START)&(d.date<=END)].reset_index(drop=True)
    if len(d)<1450 and symbol=="PLTR":raise RuntimeError("PLTR data incomplete")
    return d
def fxrate(d,days):
    f=d[["date","close"]].copy();f["date"]=pd.to_datetime(f.date)
    f=f.sort_values("date").drop_duplicates("date",keep="last")
    fx=pd.merge_asof(pd.DataFrame({"date":pd.to_datetime(days)}),f.rename(columns={"close":"rate"}),on="date",direction="backward").rate.to_numpy(float)
    if np.isnan(fx).any() or (fx<20).any() or (fx>45).any():raise RuntimeError("Missing USD/TWD spot rate")
    return fx
def ma(x,v,f,n):
    s=pd.Series(x)
    if f=="SMA":return s.rolling(n,min_periods=n).mean().to_numpy(float)
    if f=="EMA":return s.ewm(span=n,adjust=False,min_periods=n).mean().to_numpy(float)
    if f=="WMA":
        w=np.arange(1,n+1,dtype=float)
        return s.rolling(n,min_periods=n).apply(lambda x:float(np.dot(w,x)/np.sum(w)),raw=True).to_numpy(float)
    if f=="VWMA":
        vol=pd.Series(v).where(lambda x:x>0)
        pv=(s*vol).rolling(n,min_periods=n).sum()
        total=vol.rolling(n,min_periods=n).sum()
        return (pv/total).to_numpy(float)
    raise ValueError(f)
def config(f,n,down,up,confirm):
    return {"id":f"{f}{n}_D{int(round(down*100))}_U{int(round(up*100))}_C{confirm}",
      "family":f,"window":n,"down":down,"up":up,"confirm":confirm}
def precompute_exit(close,mean,down,confirm):
    cond=np.isfinite(mean)&(close<mean*(1-down))
    arr=pd.Series(cond).rolling(confirm,min_periods=confirm).sum().fillna(0).to_numpy(float)==confirm
    return arr
def precompute_entry(close,mean,up):return np.isfinite(mean)&(close>mean*(1+up))
def init_rule(kind,close,volume,means,conf):
    if kind=="ma":
        avg=means[conf["family"],conf["window"]]
        return precompute_exit(close,avg,conf["down"],conf["confirm"]),precompute_entry(close,avg,conf["up"])
    if kind=="dual":
        fast=means["EMA",conf["fast"]];slow=means["EMA",conf["slow"]];valid=np.isfinite(fast)&np.isfinite(slow)
        return (valid&(fast<slow*(1-conf["down"]))),(valid&(fast>slow*(1+conf["up"])))
    if kind=="donchian":
        s=pd.Series(close);low=s.rolling(conf["exitWindow"],min_periods=conf["exitWindow"]).min().shift(1).to_numpy(float)
        high=s.rolling(conf["entryWindow"],min_periods=conf["entryWindow"]).max().shift(1).to_numpy(float)
        return (np.isfinite(low)&(close<low)),(np.isfinite(high)&(close>high))
    if kind=="trail":
        ema=means["EMA",conf["ema"]]
        return np.zeros(len(close),dtype=bool),np.isfinite(ema)&(close>ema*(1+conf["up"]))
    return np.zeros(len(close),dtype=bool),np.ones(len(close),dtype=bool)
def sim(open_,close,dates,fx,usdinit,kind,conf,signals,period=FULL,slip=SLIP,detail=False):
    ii=np.flatnonzero((dates>=period[0])&(dates<=period[1]))
    if len(ii)<50:raise RuntimeError(f"Only {len(ii)} sessions in period {period}")
    cash=float(usdinit);units=0;regime=True;peak=0.;sells=0;buys=0;cashdays=0
    feeBuy=(1+BROKER)*(1+slip);feeSell=(1-BROKER-US_SELL_TAX)*(1-slip)
    exits,entries=signals
    dayrows=[];orders=[];hwm=float(usdinit);worst=0.
    fx0=float(fx[ii[0]]);initialtwd=usdinit*fx0;tw_hwm=initialtwd;tw_worst=0.
    for p,i in enumerate(ii):
        d=dates[i];op=float(open_[i]);cl=float(close[i]);t=int(i-1)
        if p==0:desired=True
        elif kind=="hold":desired=True
        elif kind=="trail":
            if regime:desired=not(bool(peak>0 and float(close[t])<peak*(1-conf["trailPct"])))
            else:desired=bool(entries[t])
        else:
            desired=(not bool(exits[t])) if regime else bool(entries[t])
        if p==0 or desired!=regime:
            if not desired and units:
                qty=units;received=qty*op*feeSell;cash+=received;units=0;sells+=1;regime=False
                if detail:orders.append({"date":d,"side":"SELL","phase":"risk_off","units":qty,"price":round(op,5),"cashUSD":round(cash,2)})
            if desired and units==0:
                qty=int(cash//(op*feeBuy))
                if qty>0:
                    cash-=qty*op*feeBuy;units=qty;buys+=1;regime=True;peak=cl
                    if detail:orders.append({"date":d,"side":"BUY","phase":"risk_on","units":qty,"price":round(op,5),"cashUSD":round(cash,2)})
        if kind=="trail" and units>0:
            peak=max(peak,cl)
        if units==0:cashdays+=1
        worth=cash+units*cl*feeSell
        hwm=max(hwm,worth);worst=min(worst,100*(worth/hwm-1))
        tw=worth*float(fx[i]);tw_hwm=max(tw_hwm,tw);tw_worst=min(tw_worst,100*(tw/tw_hwm-1))
        if detail:dayrows.append({"date":d,"accountUSD":round(worth,2),"accountTWD":round(tw,2),"units":units})
    if units:
        cash+=units*close[ii[-1]]*feeSell
        if detail:
            orders.append({"date":dates[ii[-1]],"side":"SELL","phase":"period_end",
                           "units":units,"price":round(float(close[ii[-1]]),5),"cashUSD":round(float(cash),2)})
            dayrows[-1]["accountUSD"]=round(float(cash),2)
            dayrows[-1]["accountTWD"]=round(float(cash)*float(fx[ii[-1]]),2)
    endTWD=cash*float(fx[ii[-1]])
    result={"first":dates[ii[0]],"last":dates[ii[-1]],"sessions":len(ii),
      "initialUSD":round(usdinit,4),"endUSD":round(float(cash),2),"endTWD":round(float(endTWD),2),
      "returnUSD":round((cash/usdinit-1)*100,3),"returnTWD":round((endTWD/initialtwd-1)*100,3),
      "mddUSD":round(worst,3),"mddTWD":round(tw_worst,3),
      "sells":sells,"rebuys":max(0,buys-1),"daysCash":cashdays}
    if detail:result["equity"]=dayrows;result["orders"]=orders
    return result
def yearvalues(rows,startUSD,startTWD):
    prevUSD=float(startUSD);prevTWD=float(startTWD);r={}
    for year in sorted(set(x["date"][:4] for x in rows)):
        last=next(x for x in reversed(rows) if x["date"].startswith(year))
        u=float(last["accountUSD"]);t=float(last["accountTWD"])
        r[year]={"endUSD":round(u,2),"endTWD":round(t,2),
           "returnUSD":round(100*(u/prevUSD-1),3),
           "returnTWD":round(100*(t/prevTWD-1),3)}
        prevUSD=u;prevTWD=t
    return r
def main():
    start=time.monotonic()
    df=load("PLTR");rates=load("TWD=X") # fx start 2018; individual loader filters 2020+ 
    x=df.close.to_numpy(float);vol=df.volume.to_numpy(float);open_=df.open.to_numpy(float);dates=df.date.to_numpy(str)
    fx=fxrate(rates,dates)
    fx0=float(fx[0]);usd0=NTD_START/fx0
    if dates[0]!="2020-09-30" or dates[-1]!=END:raise RuntimeError("Unexpected PLTR date window "+dates[0]+" -> "+dates[-1])
    assert len(df)>1470 and len(df)<1600,(len(df),"Bad trading days")
    quality={"IPOFirstBar":dates[0],"lastCompletedBar":dates[-1],"sessions":len(df),
       "IPOOpenUSD":float(df.open.iloc[0]),"lastAdjustedCloseUSD":float(df.close.iloc[-1]),
       "dailyPositiveVolumePct":round(float(np.mean(vol>0))*100,4),
       "usdTwdFirst":fx0,"usdTwdLast":float(fx[-1]),
       "adjFactorRange":[float(df.adjFactor.min()),float(df.adjFactor.max())]}
    print("PLTR_DATA_OK "+json.dumps(quality),flush=True)
    means={(f,n):ma(x,vol,f,n) for f in FAMILIES for n in WINDOWS}
    fixed=[
      ("BUY_HOLD","hold",{"id":"BUY_HOLD"}),
      ("SMA10_D2_U1_C3","ma",config("SMA",10,.02,.01,3)),
      ("VWMA5_D2_U1_C3","ma",config("VWMA",5,.02,.01,3)),
      ("EMA10_D2_U1_C3","ma",config("EMA",10,.02,.01,3)),
      ("WMA10_D2_U1_C3","ma",config("WMA",10,.02,.01,3)),
      ("SMA20_D2_U1_C3","ma",config("SMA",20,.02,.01,3)),
      ("EMA20_D2_U1_C3","ma",config("EMA",20,.02,.01,3)),
      ("SMA50_D2_U1_C3","ma",config("SMA",50,.02,.01,3)),
      ("EMA50_D2_U1_C3","ma",config("EMA",50,.02,.01,3)),
      ("SMA100_D2_U1_C3","ma",config("SMA",100,.02,.01,3)),
      ("SMA200_D2_U1_C3","ma",config("SMA",200,.02,.01,3)),
      ("DUAL_EMA20_100_D0_U0","dual",{"id":"DUAL_EMA20_100_D0_U0","fast":20,"slow":100,"down":0.,"up":0.}),
      ("DONCHIAN_20_55","donchian",{"id":"DONCHIAN_20_55","exitWindow":20,"entryWindow":55}),
      ("TRAIL20_EMA20_RE","trail",{"id":"TRAIL20_EMA20_RE","trailPct":.20,"ema":20,"up":.01}),
      ("TRAIL30_EMA20_RE","trail",{"id":"TRAIL30_EMA20_RE","trailPct":.30,"ema":20,"up":.01})
    ]
    pool=[]
    for family,n,down,up,cf in itertools.product(FAMILIES,WINDOWS,DOWNS,UPS,CONFIRMS):
        cfg=config(family,n,down,up,cf)
        sig=init_rule("ma",x,vol,means,cfg)
        train=sim(open_,x,dates,fx,usd0,"ma",cfg,sig,TRAIN)
        if train["sells"]>=2 and train["rebuys"]>=1:
            score=round(train["returnUSD"]-.70*abs(train["mddUSD"])-.75*train["sells"],3)
            pool.append({"id":cfg["id"],"family":family,"window":n,"downPct":down*100,
              "upPct":up*100,"confirm":cf,"train":{k:train[k] for k in
              ("returnUSD","mddUSD","sells","rebuys","daysCash")},"trainScore":score})
    print("PLTR_TRAIN_GRID "+json.dumps({"tested":len(FAMILIES)*len(WINDOWS)*len(DOWNS)*len(UPS)*len(CONFIRMS),
       "validWithMin2Sells":len(pool)}),flush=True)
    top=[]
    for f in FAMILIES:
        t=sorted((row for row in pool if row["family"]==f),
          key=lambda row:(-row["trainScore"],row["id"]))[:2]
        for row in t:
            cfg=config(f,row["window"],row["downPct"]/100,row["upPct"]/100,row["confirm"])
            top.append((row["id"],"ma",cfg))
    targets={item[0]:(item[1],item[2]) for item in fixed+top}
    # Frozen strategy inventory first, 2024-26 not consulted until after candidates selected.
    outcomes=[];equities={}
    for id,(kind,cfg) in targets.items():
        sig=init_rule(kind,x,vol,means,cfg)
        full=sim(open_,x,dates,fx,usd0,kind,cfg,sig,FULL,detail=True)
        train=sim(open_,x,dates,fx,usd0,kind,cfg,sig,TRAIN)
        valid=sim(open_,x,dates,fx,usd0,kind,cfg,sig,VALID)
        audit=sim(open_,x,dates,fx,usd0,kind,cfg,sig,AUDIT)
        excluded=("equity","orders")
        o={"id":id,"kind":kind,"config":cfg,"selection":"predefined" if id in {z[0] for z in fixed} else "training_2020_2023",
            "full":{k:v for k,v in full.items() if k not in excluded},
            "train2020_2023":train,"validation2024_2025":valid,"audit2026":audit,
            "years":yearvalues(full["equity"],usd0,NTD_START)}
        outcomes.append(o);equities[id]={"equity":full["equity"],"orders":full["orders"]}
        print("PLTR_MODEL "+json.dumps({"name":id,"selection":o["selection"],
           "fullTWD":full["returnTWD"],"fullUSD":full["returnUSD"],"endTWD":full["endTWD"],
           "mddTWD":full["mddTWD"],"trades":full["sells"],"validation":valid["returnTWD"],"audit2026":audit["returnTWD"]}),flush=True)
    # Stress executed price slippage, no separate parameter retuning.
    stress_ids=list(dict.fromkeys([z[0] for z in fixed[:5]]+[z[0] for z in top]))
    slippage={}
    for s in (.001,.003,.005,.01):
        slippage[str(s)]={}
        for id in stress_ids:
            kind,cfg=targets[id];signal=init_rule(kind,x,vol,means,cfg)
            q=sim(open_,x,dates,fx,usd0,kind,cfg,signal,FULL,slip=s)
            slippage[str(s)][id]={"returnTWD":q["returnTWD"],"returnUSD":q["returnUSD"],
              "endTWD":q["endTWD"],"mddTWD":q["mddTWD"]}
    out={"version":"PLTR_2020_2026_FULL_100W_TWD_V1",
       "generated":datetime.now(ZoneInfo("Asia/Taipei")).isoformat(),
       "asset":"PLTR","firstActualListing":"2020-09-30",
       "unsupportedYears":["2018","2019"],
       "period":[START,END],"totalSessions":len(df),
       "quality":quality,
       "assumptions":{"startingCapitalTWD":NTD_START,"startingCapitalUSD":round(usd0,4),
           "currency":"USD internal cash account, TWD equivalent end assets and drawdowns",
           "brokerFeeEachSide":BROKER,"slippageEachSide":SLIP,"sellTax":US_SELL_TAX,
           "oneUnit":"whole shares, no margin","entry":"buy from first trading opening, reinvest all available USD on all reentries",
           "signal":"completed session close → next US exchange trading open, no same-close fill",
           "cashInterest":0,"FX":"Yahoo TWD=X spot at each date; original cash remains USD during rotations",
           "excluded":"non-US investor capital gain taxes, US dividend withholding, actual USD/TWD bid-ask spread, bank transfer fees"},
       "strategyResearch":{"gridSize":len(FAMILIES)*len(WINDOWS)*len(DOWNS)*len(UPS)*len(CONFIRMS),
           "qualifyingTrainingModels":len(pool),"train":"2020-09-30 to 2023-12-29",
           "validate":"2024-01-01 to 2025-12-31",
           "audit":"2026-01-01 to 2026-10-08",
           "trainingRank":"returnUSD-0.7*abs(maxDrawdownUSD)-0.75*completedSellCount; >=2 exits and >=1 repurchase",
           "selection":"top 2 train-only candidates per MA family; all earlier fixed comparators preserved; no 2024-26 used to choose parameters",
           "caveat":"2026 and 2024-25 not truly prospective unseen research; retrospective selection and multiple tests bias."},
       "topTrainingOnly":[{"id":r["id"],"trainScore":r["trainScore"],"train":r["train"]} for r in
               (next(row for row in pool if row["id"]==id) for id,_,_ in top)],
       "models":outcomes,"executionSlippageStress":slippage,
       "warnings":["PLTR did not trade publicly before its 2020-09-30 NYSE direct listing, so 2018-19 PLTR daily stock price does not exist.",
         "First day opening auction prices may not be accessible to a real retail investor at assumed friction; the buyhold backtest assumes execution at model open.",
         "Backtests have a large upward survivor-selection bias from picking a past multi-bagger; performance is not representative of ordinary new listings.",
         "PLTR concentration risk and major bear-market drawdowns may be extreme.",
         "Trading commissions, opening gaps and FX may differ materially from assumptions.",
         "Selected train-only candidates have far fewer years of data than a long-run stock strategy; potential overfit.",
         "2026 daily close included through Oct 8; later live bars and future prices are excluded."],
       "elapsedSeconds":round(time.monotonic()-start,1)}
    assert len(outcomes)==len(set(z["id"] for z in outcomes))
    assert all(z["full"]["sessions"]==len(df) for z in outcomes)
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/"summary.json").write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding="utf-8")
    (OUT/"daily_equity_orders.json").write_text(json.dumps({"version":out["version"],"cases":equities},ensure_ascii=False),encoding="utf-8")
    (OUT/"training_grid.json").write_text(json.dumps({"version":out["version"],"criteria":out["strategyResearch"],"results":pool},ensure_ascii=False),encoding="utf-8")
    print("PLTR_BACKTEST_ALL_DONE "+json.dumps({"sessions":len(df),"models":len(outcomes),"training":len(pool),
       "hold":next(z["full"] for z in outcomes if z["id"]=="BUY_HOLD"),
       "seconds":out["elapsedSeconds"]},ensure_ascii=False),flush=True)
if __name__=="__main__":main()
