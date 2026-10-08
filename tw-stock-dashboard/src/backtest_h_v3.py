"""H3 exploratory condition search (NO A/D/F/G signals).
Choose on 2026 Jan-Jul, freeze rules, check 2026 Aug-Oct only once.
Explicit 7% gross target vs -3.5% stop, 5 market sessions, actual next open
and conservative daily OHLC path. Never require a future feature in the selector.
"""
from __future__ import annotations
import itertools,json,time,math
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from collections import defaultdict
import numpy as np,pandas as pd
from pipeline import load_universe
from yahoo_cache import update_many,update_symbol,to_symbol
from config import DATA_DIR
from h_v2 import SPEC
START="2026-01-01";END="2026-10-07"
TRAIN_END="2026-05-29";VALID_END="2026-07-31";HOLDOUT_START="2026-08-03"
FEE_IN=.1425/100;FEE_OUT=(.1425+.30)/100;SLIP=.10/100
TARGET=1.07;STOP=.965;H=5
MAX_CANDIDATES=2500;TOP=3
def stat(rows):
    a=rows[rows["status"]==1]
    n=len(a);tp=int(a["tp"].sum()) if n else 0;loss=int(a["stop"].sum()) if n else 0
    net=a["net"].to_numpy() if n else np.array([])
    win=net[net>0];lose=net[net<0]
    return {"n":n,"target":tp,"hitPct":round(100*tp/n,2) if n else None,
        "stopN":loss,"stopPct":round(100*loss/n,2) if n else None,
        "avgNet":round(float(np.mean(net)),3) if n else None,
        "winPct":round(100*np.mean(net>0),2) if n else None,
        "avgWin":round(float(np.mean(win)),3) if len(win) else None,
        "avgLoss":round(float(np.mean(lose)),3) if len(lose) else None,
        "profitFactor":round(float(sum(win)/-sum(lose)),3) if len(lose) and sum(lose)<0 else None,
        "signalDays":int(a["date"].nunique()) if n else 0}
def trade(open_arr,high_arr,low_arr,close_arr,factor,indices,signal_close,cap=2.5):
    idx0=indices[0]
    op=float(open_arr[idx0])
    if not np.isfinite(op) or op<=0:return (2,False,False,None,"bad_price")
    if op>signal_close*(1+cap/100):return (0,False,False,None,"gap_skip")
    prices=close_arr[indices]
    ratio=prices[1:]/prices[:-1]
    if np.any((ratio<.55)|(ratio>1.8)):return (2,False,False,None,"corp_jump")
    entry=op*factor[idx0]*(1+SLIP)
    tp_price=entry*TARGET;stop_price=entry*STOP
    for j in indices:
        o,h,l,c=[float(x[j])*float(factor[j]) for x in (open_arr,high_arr,low_arr,close_arr)]
        if not (np.isfinite(o) and np.isfinite(h) and np.isfinite(l) and np.isfinite(c)):return (2,False,False,None,"nan")
        if o<=stop_price:price=o;kind="stop"
        elif o>=tp_price:price=o;kind="tp"
        elif l<=stop_price:price=stop_price;kind="stop"
        elif h>=tp_price:price=tp_price;kind="tp"
        elif j==indices[-1]:price=c;kind="timeout"
        else:continue
        net=(price*(1-SLIP)*(1-FEE_OUT)/(entry*(1+FEE_IN))-1)*100
        return (1,kind=="tp",kind=="stop",round(net,4),kind)
    return (2,False,False,None,"unknown")
def features(df,capital,marketdates,marketpos,sample_start=START,sample_end=END):
    x=df.sort_values("date").drop_duplicates("date",keep="last").reset_index(drop=True).copy()
    if len(x)<160:return None
    for c in ("open","high","low","close","volume"):x[c]=pd.to_numeric(x[c],errors="coerce")
    o,h,l,c,v=[x[t] for t in ("open","high","low","close","volume")]
    f=pd.to_numeric(x.get("adjclose",c),errors="coerce").fillna(c)/c
    high8=h.shift(1).rolling(8).max();high20=h.shift(1).rolling(20).max()
    high120=h.shift(1).rolling(120,min_periods=100).max()
    low8=l.shift(1).rolling(8).min()
    ema20=c.ewm(span=20,adjust=False,min_periods=20).mean()
    ma60=c.rolling(60).mean()
    prevcl=c.shift(1)
    rel=v/v.shift(1).rolling(20).mean()
    day=(c/prevcl-1)*100
    data=pd.DataFrame({
        "date":x.date.astype(str),
        "turn":v/(capital*10_000_000)*100,
        "turn5":v.shift(1).rolling(5).mean()/(capital*10_000_000)*100,
        "vrel":rel,
        "p120":c/high120,
        "b8":(c/high8-1)*100,
        "b20":(c/high20-1)*100,
        "draw20":(c/high20-1)*100,
        "ret5":(c/c.shift(5)-1)*100,
        "prev5":(c.shift(1)/c.shift(6)-1)*100,
        "ret20":(c/c.shift(20)-1)*100,
        "day":day,
        "priorDay":(c.shift(1)/c.shift(2)-1)*100,
        "range8":(high8/low8-1)*100,
        "vcon":v.shift(1).rolling(3).mean()/v.shift(1).rolling(20).mean(),
        "pos":(c-l)/(h-l).replace(0,np.nan),
        "body":(c/o-1)*100,
        "aboveEma":c/ema20-1,
        "emaSlope":ema20/ema20.shift(5)-1,
        "aboveMa60":c/ma60-1,
        "atr":pd.concat([h-l,(h-prevcl).abs(),(l-prevcl).abs()],axis=1).max(axis=1).rolling(14).mean()/c*100,
        "tradedM":(c*v)/1_000_000,
        "c":c,
        "o":o,
        "high":h,
        "low":l,
        "f":f
    })
    basic=data[(data.date>=sample_start)&(data.date<=sample_end)&(data.c>=12)&(data.tradedM>=65)&(data.turn>=0.7)&(data.vrel>=0.7)]
    if basic.empty:return []
    dates=x.date.astype(str).tolist();stockpos={d:i for i,d in enumerate(dates)}
    opens=o.to_numpy();highs=h.to_numpy();lows=l.to_numpy();closes=c.to_numpy();fac=f.to_numpy()
    out=[]
    req=("turn","turn5","vrel","p120","b8","b20","draw20","ret5","prev5","ret20",
         "day","priorDay","range8","vcon","pos","body","aboveEma","emaSlope","aboveMa60","atr","tradedM")
    for row in basic.itertuples(index=False):
        date=row.date;mi=marketpos.get(date)
        if mi is None or mi+H>=len(marketdates) or marketdates[mi+H]>sample_end:continue
        future=marketdates[mi+1:mi+H+1]
        indices=[stockpos.get(t) for t in future]
        if any(z is None for z in indices):continue
        v1=[float(getattr(row,k)) for k in req]
        if not np.isfinite(v1).all():continue
        status,tp,stop,net,reason=trade(opens,highs,lows,closes,fac,indices,float(row.c))
        out.append((date,*v1,status,int(tp),int(stop),net,reason))
    return out
def score(frame,family,ranking):
    clip=np.clip
    if ranking==0:return 0.5*frame.turn+10*frame.p120+0.12*frame.ret5+0.5*frame.vrel
    if ranking==1:return 1.2*frame.vrel+0.5*frame.day+3*frame.pos+0.3*frame.turn
    if ranking==2:return 0.4*frame.turn5+frame.ret20/6+frame.atr/2+frame.b20/8
    return 2*frame.p120+0.3*frame.turn+frame.day/3+3*frame.emaSlope
def configs():
    # Families from papers and published GitHub breakout projects, not A/D/F/G.
    # 6 families x parameter grid; all thresholds specified before seeing holdout.
    for family in ("near_high","runup","rebound","flag","contraction","fresh_break","washout"):
        if family=="near_high":
            for p,turn,rel,ret,rank in itertools.product((.90,.95,.98),(1.5,3,5),(1.1,1.7),(0,4),(0,1,2)):
                yield {"family":family,"p120":p,"turn":turn,"vrel":rel,"ret":ret,"ranking":rank}
        elif family=="runup":
            for gain,p,turn,rank in itertools.product((2.5,4.5,6),(.88,.95),(2,4),(0,1,3)):
                yield {"family":family,"gain":gain,"p120":p,"turn":turn,"ranking":rank}
        elif family=="rebound":
            for prev,p,turn,gain,rank in itertools.product((-2,-4,-6),(.80,.92),(1.5,3),(1,2),(0,1)):
                yield {"family":family,"prev":prev,"p120":p,"turn":turn,"gain":gain,"ranking":rank}
        elif family=="flag":
            for ret,vcon,turn,rank in itertools.product((8,13),(1,1.3),(1.5,3),(0,1,3)):
                yield {"family":family,"ret":ret,"vcon":vcon,"turn":turn,"ranking":rank}
        elif family=="contraction":
            for rg,ret,p,rank in itertools.product((12,20,30),(1,-2),(.8,.92),(0,1,2)):
                yield {"family":family,"range8":rg,"ret":ret,"p120":p,"ranking":rank}
        elif family=="fresh_break":
            for br,turn,vrel,rank in itertools.product((0,1,3),(1.5,3,5),(1.2,2),(0,1,2)):
                yield {"family":family,"break":br,"turn":turn,"vrel":vrel,"ranking":rank}
        else:
            for negative,turn,atr,p,rank in itertools.product((-2,-4),(2,4),(3,5),(.7,.85),(0,2)):
                yield {"family":family,"negative":negative,"turn":turn,"atr":atr,"p120":p,"ranking":rank}
def mask_family(df,cfg):
    f=cfg["family"];t=df.turn;vol=df.vrel;p=df.p120
    basic=(df.tradedM>=100)&(df.turn5>=0.4)&(df.atr>=2.0)
    if f=="near_high":return basic&(p>=cfg["p120"])&(t>=cfg["turn"])&(vol>=cfg["vrel"])&(df.ret5>=cfg["ret"])&(df.pos>=.55)&(df.day<=9.5)
    if f=="runup":return basic&(df.day>=cfg["gain"])&(df.day<=9.5)&(t>=cfg["turn"])&(p>=cfg["p120"])&(df.b20>=-1)&(df.pos>=.65)
    if f=="rebound":return basic&(df.prev5<=cfg["prev"])&(df.day>=cfg["gain"])&(df.day<=7.5)&(t>=cfg["turn"])&(p>=cfg["p120"])&(df.pos>=.55)
    if f=="flag":return basic&(df.ret20>=cfg["ret"])&(df.priorDay<=0)&(df.vcon<=cfg["vcon"])&(t>=cfg["turn"])&(df.b8>=0)&(df.day.between(.3,8))
    if f=="contraction":return basic&(df.range8<=cfg["range8"])&(df.prev5<=cfg["ret"])&(p>=cfg["p120"])&(vol>=1.2)&(df.b8>=-.5)&(df.pos>=.65)&(df.day.between(.3,8))
    if f=="fresh_break":return basic&(df.b20>=cfg["break"])&(t>=cfg["turn"])&(vol>=cfg["vrel"])&(df.day.between(1,9.5))&(df.pos>=.7)
    return basic&(df.day<=cfg["negative"])&(t>=cfg["turn"])&(df.atr>=cfg["atr"])&(p>=cfg["p120"])&(df.pos<=.45)
def pick(frame,selector,rank):
    a=frame.loc[selector].copy()
    if a.empty:return a
    a["sortScore"]=score(a,"",rank)
    return a.sort_values(["date","sortScore","turn","code"],ascending=[True,False,False,True]).groupby("date",sort=False).head(3)
def percent_wilson_lower(hits,n):
    if n==0:return 0.
    z=1.96;p=hits/n
    return (p+z*z/(2*n)-z*math.sqrt((p*(1-p)+z*z/(4*n))/n))/(1+z*z/n)
def run():
    start_time=time.time()
    universe=load_universe();start=datetime(2025,4,1);end=datetime(2026,10,8)
    print("H3 fetch OHLCV",len(universe),flush=True)
    history,errors=update_many([(x["code"],x["market"]) for x in universe],start,end)
    _,index,ixerr=update_symbol("^TWII",start,end)
    if ixerr or index is None or len(index)<150:raise RuntimeError("Index trading calendar unavailable")
    marketdates=index.date.astype(str).tolist();marketpos={d:i for i,d in enumerate(marketdates)}
    rows=[];labels=["date","turn","turn5","vrel","p120","b8","b20","draw20","ret5","prev5","ret20","day","priorDay",
                    "range8","vcon","pos","body","aboveEma","emaSlope","aboveMa60","atr","tradedM",
                    "status","tp","stop","net","reason"]
    for i,st in enumerate(universe):
        capital=float(st.get("capitalB") or 0)
        if capital<=0:continue
        sym=to_symbol(st["code"],st["market"])
        frame=history.get(sym)
        if frame is None or len(frame)<160:continue
        found=features(frame,capital,marketdates,marketpos)
        if found:
            rows += [(str(st["code"]),str(st["market"]),str(st["name"]),*r) for r in found]
        if i%400==0:print("H3 features",i,len(universe),"eventRows",len(rows),flush=True)
    columns=["code","market","name"]+labels
    frame=pd.DataFrame(rows,columns=columns)
    if frame.empty:raise RuntimeError("No H3 events found")
    frame["net"]=pd.to_numeric(frame.net,errors="coerce")
    frame["slice"]=np.select([frame.date<=TRAIN_END,frame.date<=VALID_END],["train","validation"],default="holdout")
    result=[];tested=0
    for cfg in configs():
        tested+=1
        selected=mask_family(frame,cfg)
        # Score fixed before holdout read, rank per-day only from known signal data.
        selected &= frame["slice"].isin(("train","validation"))
        picked=pick(frame,selected,cfg["ranking"])
        tr=stat(picked[picked["slice"]=="train"])
        val=stat(picked[picked["slice"]=="validation"])
        if tr["n"]<35 or val["n"]<15:continue
        # Seek robust TP hit AND positive expectancy; prioritize validation then train.
        # Penalize low sample counts and missing profitability.
        htr=tr["hitPct"];hv=val["hitPct"]
        consistency=abs(htr-hv)
        net=(tr["avgNet"]+val["avgNet"])/2
        objective=.65*hv+.35*htr-max(0,consistency-8)*.4+5*max(-2,min(2,net))+4*math.log1p(val["n"])
        result.append({"spec":cfg,"objective":round(objective,4),"train":tr,"validation":val})
        if tested%200==0:print("H3 completed",tested,flush=True)
    result.sort(key=lambda x:(-x["objective"],-x["validation"]["n"]))
    if not result:raise RuntimeError("No candidate reaches predeclared minimum train 35 / validation 15 fills; report no robust strategy")
    # Freeze one strategy selected by TRAIN+VALIDATION ONLY before accessing holdout outcomes.
    leader=result[0]
    hold=pick(frame,mask_family(frame,leader["spec"])&(frame["slice"]=="holdout"),leader["spec"]["ranking"])
    result_hold=stat(hold)
    pre=leader["train"];val=leader["validation"]
    success=(result_hold["n"]>=25 and result_hold["hitPct"]>=58
             and result_hold["avgNet"]>0 and percent_wilson_lower(result_hold["target"],result_hold["n"])>.40)
    report={"version":"H3_WALKFORWARD_RESEARCH_2026","createdAt":datetime.now(ZoneInfo("Asia/Taipei")).isoformat(),
        "period":{"start":START,"end":END},"training":{"start":START,"end":TRAIN_END},
        "validation":{"start":"2026-06-01","end":VALID_END},
        "untouchedHoldout":{"start":HOLDOUT_START,"end":END},
        "search":{"totalPrecommittedConfigurations":tested,"qualifiedOnTrainValidation":len(result),
                  "minTrainFilledTrades":35,"minValidationFilledTrades":15,
                  "holdoutSuccessRequires":{"filledTrades":25,"hitPct":58,"avgNetPct":0,"wilsonLower95":.40}},
        "marketUniverse":len(universe),"priceErrors":len(errors),
        "candidateStockDays":len(frame),"conditions":{"signal":"completed daily close","entry":"next open capped 2.5% above signal close",
            "grossTakeProfitPct":7,"grossStopLossPct":3.5,"maxTradingDays":5,
            "fees":"buy/sell 0.1425%, sell-tax 0.3%, slippage 0.1% per side",
            "sameDayStopFirst":True,"turnover":"volume / (current paid-in capital/NT$10) proxy, NOT true historical turnover",
            "ranking":"day-wise top3, dropped orders not replaced"},
        "selectedBeforeHoldout":{"config":leader["spec"],"train":pre,"validation":val},
        "holdout":result_hold,"holdoutWilsonLower95":round(percent_wilson_lower(result_hold["target"],result_hold["n"]),3),
        "passedPrecommittedGoal":success,
        "topTenTrainingValidation":[{"config":r["spec"],"train":r["train"],"validation":r["validation"],"objective":r["objective"]} for r in result[:10]],
        "researchWarnings":["Even though holdout only read once, prior H1/H2 tests used 2026 data; the year is not globally pristine out-of-sample.","Current paid-in capital turnover proxy and surviving universe risk lookahead/survivorship bias.","Daily OHLC stop first for same-day TP/SL, no high frequency order book.","Searching many variants inflates in-sample winners; report all tested combinations and minimum sample counts.",
            "Do not automatically optimize holdout until reaching 60%; independent future sample required for live deployment."],
        "elapsedSeconds":round(time.time()-start_time,1)}
    p=DATA_DIR/"backtest_h_v3";p.mkdir(parents=True,exist_ok=True)
    (p/"H3_2026_walkforward.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    (p/"H3_top10_train_valid.json").write_text(json.dumps(result[:10],ensure_ascii=False,indent=2),encoding="utf-8")
    (p/"H3_holdout_transactions.json").write_text(hold[["date","code","name","market","turn","vrel","p120","day","status","tp","stop","net","reason"]].to_json(orient="records",force_ascii=False,indent=2),encoding="utf-8")
    print("H3_RESULT "+json.dumps({k:report[k] for k in ("period","search","marketUniverse","candidateStockDays","selectedBeforeHoldout","holdout","passedPrecommittedGoal","elapsedSeconds")},ensure_ascii=False),flush=True)
    return report
if __name__=="__main__":run()
