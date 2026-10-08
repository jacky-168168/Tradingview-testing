from __future__ import annotations
import json
from datetime import datetime,timedelta
import numpy as np,pandas as pd
from config import DATA_DIR
from pipeline import load_universe
from yahoo_cache import update_many,update_symbol,to_symbol
from scoring import precompute_features
from research_signal_samples import SAMPLES
KEYS=["ret20","ma20Slope","atrPct","range20Pct","turnoverB","ret5","mom10Pct","range10Pct","rvol10","closePosition","dayRet","ema20Slope5","vol5vs20"]
PKEYS=["r20","slope","atr","rng20","turn","r5","mom10","rng10","rvol10","position","day","emaSlope","v520"]
def run():
    uni=load_universe();hist,errors=update_many([(x["code"],x["market"]) for x in uni],datetime(2026,2,1),datetime(2026,10,9))
    _,idx,error=update_symbol("^TWII",datetime(2026,2,1),datetime(2026,10,9))
    if error or idx is None or idx.empty:raise RuntimeError("benchmark unavailable")
    dates=sorted(set(idx.date.astype(str)))
    anchors={}
    for x in SAMPLES:
        prior=[d for d in dates if d<x["date"]]
        if prior:anchors[(prior[-1],x["code"])]=x
    sample_dates=sorted({x[0] for x in anchors})
    records={d:[] for d in sample_dates}
    sample_codes={d:set() for d in sample_dates}
    for d,code in anchors:sample_codes[d].add(code)
    for n,meta in enumerate(uni,1):
        sym=to_symbol(meta["code"],meta["market"]);px=hist.get(sym)
        if px is None or len(px)<30:continue
        f=precompute_features(px)
        hi=pd.to_numeric(f.high,errors="coerce");lo=pd.to_numeric(f.low,errors="coerce");vol=pd.to_numeric(f.volume,errors="coerce")
        f["range20Pct"]=(hi.rolling(20).max()/lo.rolling(20).min()-1)*100
        f["range10Pct"]=(hi.rolling(10).max()/lo.rolling(10).min()-1)*100
        f["vol5vs20"]=vol.rolling(5).mean()/vol.rolling(20).mean()
        f["turnoverB"]=pd.to_numeric(f.close,errors="coerce")*vol/100_000_000
        f=f.set_index("date")
        for date in sample_dates:
            if date not in f.index:continue
            q=f.loc[date];q=q.iloc[-1] if isinstance(q,pd.DataFrame) else q
            z=[q.get(k) for k in KEYS]
            if any(pd.isna(v) or not np.isfinite(float(v)) for v in z) or float(q["close"])<=0:continue
            cap=meta.get("capitalB") or 0
            records[date].append({"c":meta["code"],"a":float(cap),"px":round(float(q["close"]),3),"br":round(float(q["breakoutPct"]),3),"f":z})
        if n%400==0:print(f"matrix {n}/{len(uni)}",flush=True)
    allrows={};sample_report=[]
    for date,rs in records.items():
        if not rs:continue
        mat=pd.DataFrame([x["f"] for x in rs],columns=PKEYS);pct=mat.rank(pct=True).mul(100).round(1).values
        output=[]
        for x,p in zip(rs,pct):
            v=[round(float(t),1) for t in p]
            # Exclude broadly weak stocks, keep all 20 positive examples.
            if v[0]<55 or v[1]<65 or v[2]<50 or v[3]<60 or v[4]<55 or x["px"]<10 or x["br"]<-27:
                if x["c"] not in sample_codes.get(date,set()):continue
            output.append([x["c"],round(x["a"],2),round(x["px"],2),x["br"]]+v)
        allrows[date]=output
    for (d,code),s in sorted(anchors.items()):
        rr=next((x for x in allrows.get(d,[]) if x[0]==code),None)
        sample_report.append({"anchor":d,"post":s["date"],"time":s.get("time"),"code":code,"available":rr is not None})
    out={"version":"matrix-v1","featureKeys":PKEYS,"rowLayout":["code","capitalB","close","breakoutPct"]+PKEYS,"sampleDays":allrows,"samples":sample_report,"historyErrors":len(errors)}
    p=DATA_DIR/"research";p.mkdir(parents=True,exist_ok=True)
    (p/"g_target_matrix_2026.json").write_text(json.dumps(out,ensure_ascii=False,separators=(",",":")),encoding="utf-8")
    print(json.dumps({"dates":len(allrows),"marketCandidates":{d:len(v) for d,v in allrows.items()},"sampleAvailable":sum(s["available"] for s in sample_report),"errors":len(errors)}),flush=True)
if __name__=="__main__":run()
