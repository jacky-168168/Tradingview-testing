from __future__ import annotations
import argparse,json,time
from datetime import datetime,timedelta
from zoneinfo import ZoneInfo
import numpy as np,pandas as pd
from config import DATA_DIR,MIN_PRICE
from pipeline import load_universe
from yahoo_cache import update_many,update_symbol,to_symbol
from scoring import precompute_features

H=[3,5,10,20]
BUY_FEE=.1425;SELL_FEE=.1425;SELL_TAX=.30
VARIANTS={
 "G_BASE":{"ret20P":75,"slopeP":85,"atrP":70,"range20P":80,"turnoverP":80,"breakoutMin":-18},
 "G_RELAXED":{"ret20P":70,"slopeP":80,"atrP":65,"range20P":75,"turnoverP":75,"breakoutMin":-20},
 "G_STRICT":{"ret20P":80,"slopeP":90,"atrP":75,"range20P":85,"turnoverP":85,"breakoutMin":-15},
}
def num(v,d=None):
    try:
        x=float(v);return x if np.isfinite(x) else d
    except:return d
def stat(a):
    a=[float(x) for x in a if x is not None and np.isfinite(x)]
    if not a:return {"n":0,"avg":None,"median":None,"win":None,"max":None,"min":None}
    return {"n":len(a),"avg":round(float(np.mean(a)),2),"median":round(float(np.median(a)),2),"win":round(sum(x>0 for x in a)/len(a)*100,1),"max":round(max(a),2),"min":round(min(a),2)}
def adj(row,field):
    raw=num(row.get(field));close=num(row.get("close"));ac=num(row.get("adjclose"))
    if raw is None:return None
    return raw*(ac/close) if close and ac else raw
def price_return(px,buydate,exitdate):
    if px is None or buydate not in px.index or exitdate not in px.index:return None
    b=px.loc[buydate];b=b.iloc[-1] if isinstance(b,pd.DataFrame) else b
    e=px.loc[exitdate];e=e.iloc[-1] if isinstance(e,pd.DataFrame) else e
    bo=adj(b,"open");ec=adj(e,"close")
    if not bo or not ec:return None
    # 排除未調整公司行動尺度跳變
    q=px[(px.date.astype(str)>=buydate)&(px.date.astype(str)<=exitdate)]
    c=pd.to_numeric(q.close,errors="coerce");rat=c/c.shift(1)
    if bool(((rat<.55)|(rat>1.8)).fillna(False).any()):return None
    return (ec/bo-1)*100
def rank_pct(vals):
    s=pd.Series(vals,dtype=float);return s.rank(pct=True,method="average")*100
def score_row(x):
    prox=max(0.0,100.0-abs(float(x["breakoutPct"]))*4.0)
    return round((30*x["ret20P"]+25*x["slopeP"]+15*x["range20P"]+10*x["atrP"]+15*x["turnoverP"]+5*prox)/100,2)
def pass_variant(x,v):
    return x["ret20P"]>=v["ret20P"] and x["slopeP"]>=v["slopeP"] and x["atrP"]>=v["atrP"] and x["range20P"]>=v["range20P"] and x["turnoverP"]>=v["turnoverP"] and x["breakoutPct"]>=v["breakoutMin"]
def phase_portfolio(signals,dates,pos,ranks,prices,meta,h):
    outs=[]
    cost=(BUY_FEE+SELL_FEE+SELL_TAX)/100
    for phase in range(h):
        eq=1.0;rets=[]
        for si in range(phase,len(signals),h):
            d=signals[si];ip=pos.get(d)
            if ip is None or ip+1>=len(dates) or ip+h>=len(dates):continue
            buydate=dates[ip+1];exitdate=dates[ip+h];xs=[]
            for p in ranks.get(d,[])[:3]:
                px=prices.get(to_symbol(p["code"],p["market"]));r=price_return(px,buydate,exitdate)
                if r is not None:xs.append(r)
            if not xs:continue
            gross=float(np.mean(xs));net=(1+gross/100)*(1-cost)-1;rets.append(net*100);eq*=1+net
        outs.append({"phase":phase,"periods":len(rets),"totalReturn":round((eq-1)*100,2),"avgNet":round(float(np.mean(rets)),2) if rets else None,"winRate":round(sum(x>0 for x in rets)/len(rets)*100,1) if rets else None})
    vals=[x["totalReturn"] for x in outs if x["periods"]]
    return {"phases":outs,"meanTotalReturn":round(float(np.mean(vals)),2) if vals else None,"medianTotalReturn":round(float(np.median(vals)),2) if vals else None,"worstTotalReturn":round(float(np.min(vals)),2) if vals else None,"bestTotalReturn":round(float(np.max(vals)),2) if vals else None}
def run(start,end):
    t=time.time();all_u=load_universe();u=[x for x in all_u if num(x.get("capitalB"),0)>0]
    fs=datetime.fromisoformat(start)-timedelta(days=180);fe=datetime.fromisoformat(end)+timedelta(days=35)
    hist,errors=update_many([(x["code"],x["market"]) for x in all_u],fs,fe);_,ix,ie=update_symbol("^TWII",fs,fe)
    if ie or ix is None or ix.empty:raise RuntimeError(f"benchmark unavailable {ie}")
    ix=ix.sort_values("date").reset_index(drop=True);dates=ix.date.astype(str).tolist();pos={d:i for i,d in enumerate(dates)}
    signals=[d for d in dates if start<=d<=end]
    feats={};prices={}
    for s in all_u:
        sym=to_symbol(s["code"],s["market"]);df=hist.get(sym)
        if df is None or len(df)<60:continue
        q=precompute_features(df)
        q["range20Pct"]=(pd.to_numeric(q.high,errors="coerce").rolling(20).max()/pd.to_numeric(q.low,errors="coerce").rolling(20).min()-1)*100
        feats[sym]=q.set_index("date",drop=False);prices[sym]=df.sort_values("date").set_index("date",drop=False)
    ranks={k:{} for k in VARIANTS};counts={k:{} for k in VARIANTS}
    meta={x["code"]:x for x in u}
    for n,d in enumerate(signals,1):
        rows=[]
        for s in u:
            sym=to_symbol(s["code"],s["market"]);ft=feats.get(sym)
            if ft is None or d not in ft.index:continue
            r=ft.loc[d];r=r.iloc[-1] if isinstance(r,pd.DataFrame) else r
            close=num(r.get("close"));ret20=num(r.get("ret20"));slope=num(r.get("ma20Slope"));atr=num(r.get("atrPct"));rg=num(r.get("range20Pct"));br=num(r.get("breakoutPct"));vol=num(r.get("volume"),0)
            if None in (close,ret20,slope,atr,rg,br) or close<MIN_PRICE:continue
            turn=close*vol/100_000_000
            if turn<=0:continue
            rows.append({"code":s["code"],"name":s["name"],"market":s["market"],"close":close,"ret20":ret20,"ret5":num(r.get("ret5"),0),"ma20Slope":slope,"atrPct":atr,"range20Pct":rg,"breakoutPct":br,"turnoverB":turn,"rvol":num(r.get("rvol"),0),"rvol10":num(r.get("rvol10"),0),"mom10":num(r.get("mom10Pct"),0)})
        if not rows:
            for k in VARIANTS:ranks[k][d]=[];counts[k][d]=0
            continue
        df=pd.DataFrame(rows)
        df["ret20P"]=rank_pct(df.ret20);df["slopeP"]=rank_pct(df.ma20Slope);df["atrP"]=rank_pct(df.atrPct);df["range20P"]=rank_pct(df.range20Pct);df["turnoverP"]=rank_pct(df.turnoverB)
        recs=df.to_dict("records")
        for k,v in VARIANTS.items():
            ys=[x for x in recs if pass_variant(x,v)]
            for x in ys:x["gScore"]=score_row(x)
            ys.sort(key=lambda x:(-x["gScore"],-x["ret20P"],-x["slopeP"],-x["turnoverP"],x["code"]))
            counts[k][d]=len(ys);ranks[k][d]=[{**x,"rank":i+1} for i,x in enumerate(ys[:20])]
        if n%30==0 or n==len(signals):print(f"{d} {n}/{len(signals)} "+", ".join(f"{k}={counts[k][d]}" for k in VARIANTS),flush=True)
    models={}
    for k in VARIANTS:
        rb={h:{1:[],2:[],3:[]} for h in H};daily={h:[] for h in H};bands={b:{h:[] for h in H} for b in ["1-3","4-10","11-20"]};signals_out=[]
        for d in signals:
            ip=pos.get(d)
            if ip is None or ip+1>=len(dates):continue
            buydate=dates[ip+1]
            byh={h:[] for h in H}
            for p in ranks[k].get(d,[]):
                rec={"signalDate":d,"rank":p["rank"],"code":p["code"],"name":p["name"],"score":p["gScore"],"ret20P":round(p["ret20P"],1),"slopeP":round(p["slopeP"],1),"atrP":round(p["atrP"],1),"range20P":round(p["range20P"],1),"turnoverP":round(p["turnoverP"],1),"breakoutPct":round(p["breakoutPct"],2)}
                for h in H:
                    rr=None
                    if ip+h<len(dates):
                        rr=price_return(prices.get(to_symbol(p["code"],p["market"])),buydate,dates[ip+h])
                        if rr is not None:
                            byh[h].append((p["rank"],rr))
                            if p["rank"]<=3:rb[h][p["rank"]].append(rr)
                    rec[f"ret{h}"]=None if rr is None else round(rr,2)
                if p["rank"]<=3:signals_out.append(rec)
            for h in H:
                top=[r for rk,r in byh[h] if rk<=3]
                if top:daily[h].append(float(np.mean(top)))
                for name,lo,hi in [("1-3",1,3),("4-10",4,10),("11-20",11,20)]:
                    z=[r for rk,r in byh[h] if lo<=rk<=hi]
                    if z:bands[name][h].append(float(np.mean(z)))
        cvals=list(counts[k].values())
        models[k]={"id":k,"rule":VARIANTS[k],"candidateStats":{"avg":round(float(np.mean(cvals)),1) if cvals else 0,"median":round(float(np.median(cvals)),1) if cvals else 0,"max":max(cvals) if cvals else 0,"days3":sum(x>=3 for x in cvals),"days":len(cvals)},
          "summary":[{"horizon":h,"top3Daily":stat(daily[h]),"rank1":stat(rb[h][1]),"rank2":stat(rb[h][2]),"rank3":stat(rb[h][3]),"rank4_10":stat(bands["4-10"][h]),"rank11_20":stat(bands["11-20"][h]),"phasePortfolio":phase_portfolio(signals,dates,pos,ranks[k],prices,meta,h)} for h in H],
          "signals":signals_out}
    out={"generatedAt":datetime.now(ZoneInfo("Asia/Taipei")).isoformat(timespec="seconds"),"period":{"start":start,"end":end},"signalDays":len(signals),"universeCount":len(u),"historyErrors":len(errors),"models":models,"notes":["G models are derived from 20 shared 2026 breakout samples. 2023-2025 are out-of-sample validation years.","Selection uses prior completed daily data only; entry simulation is next trading-day open, so it validates stock-selection edge but does not claim to reproduce the author's bespoke breakout trigger price.","Phase portfolio reports every possible non-overlap starting phase to avoid single-phase bias."]}
    p=DATA_DIR/"backtest_g";p.mkdir(parents=True,exist_ok=True);fn=f"{start}_{end}.json";(p/fn).write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({"file":fn,"elapsed":round(time.time()-t,1),"candidates":{k:models[k]["candidateStats"] for k in models}},ensure_ascii=False,indent=2));return out
if __name__=="__main__":
    ap=argparse.ArgumentParser();ap.add_argument("--start",required=True);ap.add_argument("--end",required=True);a=ap.parse_args();run(a.start,a.end)
