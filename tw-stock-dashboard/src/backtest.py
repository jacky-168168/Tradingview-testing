from __future__ import annotations
import argparse,json,os,time
from datetime import datetime,timedelta
import numpy as np,pandas as pd
from config import DATA_DIR,MAX_CAPITAL_B,MIN_PRICE,MIN_TURNOVER_M,BENCHMARK
from pipeline import load_universe
from yahoo_cache import update_many,update_symbol,to_symbol
from scoring import precompute_features,score_a,score_d,d_pass,sort_key
from institution import fetch_many
from edge import build as build_edge
H=[1,3,5,10,20]

def stat(a):
    a=sorted(float(x) for x in a if x is not None and np.isfinite(x))
    if not a:return {"n":0,"avg":None,"median":None,"win":None,"max":None,"min":None}
    return {"n":len(a),"avg":round(float(np.mean(a)),2),"median":round(float(np.median(a)),2),"win":round(sum(x>0 for x in a)/len(a)*100,1),"max":round(a[-1],2),"min":round(a[0],2)}

def num(v,d=0.0):
    try:
        x=float(v);return x if np.isfinite(x) else d
    except:return d

def metrics(r):
    ks=["close","dayRet","ret5","ret20","ma20","ma60","ma20Slope","rvol","rvol10","mom10Pct","ema20","ema50","ema20Slope5","prevHigh20","breakoutPct","atrPct","volD","closePosition","volume"]
    return {k:num(r.get(k)) for k in ks}

def rankings(universe,hist,index_df,inst,start,end):
    idx=index_df.copy().sort_values("date").reset_index(drop=True);idx["close"]=pd.to_numeric(idx.close,errors="coerce")
    dates=idx.date.astype(str).tolist();pos={d:i for i,d in enumerate(dates)};signals=[d for d in dates if start<=d<=end]
    feats={};prices={}
    for s in universe:
        sym=to_symbol(s["code"],s["market"]);df=hist.get(sym)
        if df is None or len(df)<55:continue
        feats[sym]=precompute_features(df).set_index("date",drop=False);prices[sym]=df.set_index("date",drop=False)
    ranks={"A":{},"D":{}};cand={"A":{},"D":{}}
    for n,d in enumerate(signals,1):
        ip=pos[d]
        if ip<25:continue
        market20=(float(idx.loc[ip,"close"])/float(idx.loc[ip-20,"close"])-1)*100;rows={"A":[],"D":[]};iday=inst.get(d,{})
        for s in universe:
            sym=to_symbol(s["code"],s["market"]);ft=feats.get(sym)
            if ft is None or d not in ft.index:continue
            rr=ft.loc[d];rr=rr.iloc[-1] if isinstance(rr,pd.DataFrame) else rr
            if pd.isna(rr.get("ret20")) or pd.isna(rr.get("ma20")) or pd.isna(rr.get("ema50")):continue
            m=metrics(rr)
            if m["close"]<MIN_PRICE:continue
            rs=m["ret20"]-market20;turn=m["close"]*m["volume"]/100_000_000;base={"code":s["code"],"name":s["name"],"market":s["market"],"close":m["close"],"ret5":m["ret5"],"ret20":m["ret20"],"rs20":rs,"rvol":m["rvol"],"rvol10":m["rvol10"],"mom10Pct":m["mom10Pct"],"volD":m["volD"],"breakoutPct":m["breakoutPct"],"closePosition":m["closePosition"],"turnoverB":turn}
            ii=iday.get(f'{s["market"]}_{s["code"]}',{})
            if turn*100>=MIN_TURNOVER_M:rows["A"].append({**base,**score_a(m,rs,ii),"model":"A"})
            if d_pass(m):rows["D"].append({**base,**score_d(m,rs,ii),"model":"D"})
        for model in ["A","D"]:
            rows[model].sort(key=sort_key);cand[model][d]=len(rows[model]);ranks[model][d]=[{**x,"rank":i+1} for i,x in enumerate(rows[model][:3])]
        if n%10==0 or n==len(signals):print(f"rank {n}/{len(signals)} {d}",flush=True)
    return signals,idx,pos,ranks,cand,prices

def evaluate(signals,idx,pos,ranks,cand,prices):
    models={};edgein={}
    for model in ["A","D"]:
        rb={h:{1:[],2:[],3:[]} for h in H};avail={h:[] for h in H};fixed={h:[] for h in H};dated={h:[] for h in H};sig=[]
        for d in signals:
            sip=pos.get(d)
            if sip is None or sip+1>=len(idx):continue
            buydate=str(idx.iloc[sip+1].date);day={h:[] for h in H}
            for p in ranks[model].get(d,[]):
                sym=to_symbol(p["code"],p["market"]);px=prices.get(sym);bo=None
                if px is not None and buydate in px.index:
                    q=px.loc[buydate];q=q.iloc[-1] if isinstance(q,pd.DataFrame) else q;bo=num(q.get("open"),None)
                rec={"model":model,"signalDate":d,"rank":p["rank"],"code":p["code"],"name":p["name"],"market":p["market"],"score":round(p["total"],2),"buyDate":buydate,"buyOpen":bo,"ret5Signal":round(p["ret5"],2),"ret20Signal":round(p["ret20"],2),"breakoutPct":round(p["breakoutPct"],2),"rvol":round(p["rvol"],2),"rvol10":round(p["rvol10"],2),"mom10Pct":round(p["mom10Pct"],2),"volD":round(p["volD"],2)}
                for h in H:
                    target=sip+h;r=None
                    if bo and target<len(idx):
                        ed=str(idx.iloc[target].date)
                        if px is not None and ed in px.index:
                            q=px.loc[ed];q=q.iloc[-1] if isinstance(q,pd.DataFrame) else q;ec=num(q.get("close"),None)
                            if ec:r=round((ec/bo-1)*100,2);day[h].append(r);rb[h][p["rank"]].append(r)
                    rec[f"ret{h}"]=r
                sig.append(rec)
            for h in H:
                if sip+h>=len(idx):continue
                if day[h]:avail[h].append(sum(day[h])/len(day[h]))
                x=sum(day[h])/3.0;fixed[h].append(x);dated[h].append({"date":d,"ret":x})
        summary=[{"group":f"Top{r}",**{f"d{h}":stat(rb[h][r]) for h in H}} for r in [1,2,3]]
        summary+=[{"group":"Top3可用等權",**{f"d{h}":stat(avail[h]) for h in H}},{"group":"Top3固定三槽",**{f"d{h}":stat(fixed[h]) for h in H}}]
        cc=list(cand[model].values());cs={"avg":round(float(np.mean(cc)),1) if cc else 0,"min":min(cc) if cc else 0,"max":max(cc) if cc else 0,"days3":sum(x>=3 for x in cc),"totalDays":len(cc)}
        models[model]={"id":model,"name":"原始版" if model=="A" else "截圖技術版","summary":summary,"candidateStats":cs,"signals":sig};edgein[model]=dated
    return [models["A"],models["D"]],build_edge(edgein)

def run(start,end):
    t=time.time();sd=datetime.fromisoformat(start);ed=datetime.fromisoformat(end)
    if sd>ed:raise ValueError("start > end")
    fs=sd-timedelta(days=180);fe=min(datetime.now(),ed+timedelta(days=50));u=[x for x in load_universe() if 0<x.get("capitalB",0)<MAX_CAPITAL_B]
    print(f"universe={len(u)} fetch={fs.date()}..{fe.date()}",flush=True)
    hist,he=update_many([(x["code"],x["market"]) for x in u],fs,fe);_,ix,ie=update_symbol(BENCHMARK,fs,fe)
    if ie or ix is None or len(ix)<60:raise RuntimeError(f"benchmark unavailable: {ie}")
    sdts=[d for d in ix.date.astype(str) if start<=d<=end];inst,ine=fetch_many(sdts);sdts,idx,pos,ranks,cand,prices=rankings(u,hist,ix,inst,start,end);models,edge=evaluate(sdts,idx,pos,ranks,cand,prices)
    out={"version":"PY-BT1-V12.2-COMPAT","generatedAt":datetime.now().isoformat(timespec="seconds"),"period":{"start":start,"end":end},"signalDays":len(sdts),"universeCount":len(u),"historySuccess":len(hist)-len(he),"historyErrors":len(he),"institutionErrors":len(ine),"models":models,"edgeAudit":edge,"elapsedSeconds":round(time.time()-t,1),"notes":["A/D核心評分、Top3固定三槽與Edge判讀對齊V12.2。","歷史法人沿用V12.2口徑：TWSE T86；上櫃法人0分。","Yahoo K使用雙向Parquet增量快取；已覆蓋日期不重抓。"]}
    p=DATA_DIR/"backtest";p.mkdir(parents=True,exist_ok=True);(p/"latest.json").write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding="utf-8");print(json.dumps({"signalDays":out["signalDays"],"historyErrors":out["historyErrors"],"institutionErrors":out["institutionErrors"],"elapsedSeconds":out["elapsedSeconds"]},ensure_ascii=False),flush=True);return out

if __name__=="__main__":
    ap=argparse.ArgumentParser();ap.add_argument("--start");ap.add_argument("--end");a=ap.parse_args();end=a.end or datetime.now().date().isoformat();start=a.start or (datetime.fromisoformat(end)-timedelta(days=180)).date().isoformat();run(start,end)
