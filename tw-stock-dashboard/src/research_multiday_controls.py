"""Compare 3D/18D candle patterns in 20 posted signals to same-date strong peers.
Exploratory discrimination, not a proof of predictive edge.
"""
from __future__ import annotations
import json,math
from collections import defaultdict
from datetime import datetime
from zoneinfo import ZoneInfo
import numpy as np,pandas as pd
from config import DATA_DIR
from pipeline import load_universe
from yahoo_cache import update_many,update_symbol,to_symbol
from multi_day_candles import aggregate_bars,candle_test,latest_pair

KEYS=["bullD","bodyD","bull3Confirmed","body3Confirmed","body3Recent3","bull3Now","half3","bull18Confirmed","body18Confirmed","body18Recent3","bull18Now","half18","trend18","closeAbove3DHigh","closeAbove18DHigh"]
def eligible(x):
    return bool(x[2]>=10 and x[1]>0 and x[4]>=60 and x[5]>=70 and x[6]>=55 and x[7]>=65 and x[8]>=65 and x[3]>=-25)
def recent_engulfs(bars,asof,n):
    if bars is None or bars.empty:return False
    z=bars[(bars.date.astype(str)<=asof)&bars.complete]
    if len(z)<2:return False
    low=max(1,len(z)-n)
    for i in range(low,len(z)):
        if candle_test(z.iloc[i-1].to_dict(),z.iloc[i].to_dict())["bodyEngulf"]:return True
    return False
def current_bull(df,market_dates,asof,n):
    ys=[x for x in market_dates if x[:4]==asof[:4]]
    if asof not in ys:return False
    idx=ys.index(asof);first=ys[(idx//n)*n]
    q=df[(df.date.astype(str)>=first)&(df.date.astype(str)<=asof)]
    if q.empty:return False
    return bool(float(q.close.iloc[-1])>float(q.open.iloc[0]))
def flags(df,market_dates,asof):
    q=df[df.date.astype(str)<=asof]
    if q.empty or asof not in set(q.date.astype(str)):return None
    daily=q.iloc[-2:]
    if len(daily)<2:return None
    cd=candle_test(daily.iloc[-2].to_dict(),daily.iloc[-1].to_dict())
    out={"bullD":cd["nowBull"],"bodyD":cd["bodyEngulf"]}
    close=float(q.close.iloc[-1])
    for n in (3,18):
        a=aggregate_bars(df,market_dates,n)
        p,c=latest_pair(a,asof,True)
        cs=candle_test(p,c) if p and c else None
        out[f"bull{n}Confirmed"]=bool(cs and cs["nowBull"])
        out[f"body{n}Confirmed"]=bool(cs and cs["bodyEngulf"])
        out[f"body{n}Recent3"]=recent_engulfs(a,asof,3)
        out[f"bull{n}Now"]=current_bull(q,market_dates,asof,n)
        out[f"half{n}"]=bool(cs and cs["halfRecover"])
        out[f"closeAbove{n}DHigh"]=bool(c and close>float(c["high"]))
        if n==18:out["trend18"]=bool(p and c and c["close"]>p["close"])
    return out
def score(x):
    prox=max(0,min(100,100+x[3]/18*100))
    return (30*x[4]+25*x[5]+10*x[6]+15*x[7]+15*x[8]+5*prox)/100
def score_hypothesis(x,f):
    return score(x)+2*f["body3Confirmed"]+2*f["body18Confirmed"]+1.5*f["body3Recent3"]+1.5*f["body18Recent3"]+.5*f["trend18"]
def run():
    inputpath=DATA_DIR/"research"/"g_target_matrix_2026.json"
    data=json.loads(inputpath.read_text(encoding="utf-8"))
    uni={str(x["code"]):x for x in load_universe()}
    calStart=datetime(2026,1,1);calEnd=datetime(2026,10,8)
    _,market,err=update_symbol("^TWII",calStart,calEnd)
    if err or market is None or market.empty:raise RuntimeError("TWII unavailable "+str(err))
    market_dates=sorted(set(x for x in market.date.astype(str) if x.startswith("2026-")))
    rows={d:[x for x in group if eligible(x)] for d,group in data["sampleDays"].items()}
    needed={x[0] for group in rows.values() for x in group}
    codes=[(c,uni[c]["market"]) for c in needed if c in uni]
    print(f"Loading {len(codes)} 2026 strong control stocks across {len(rows)} signal dates",flush=True)
    hist,errors=update_many(codes,calStart,calEnd)
    bycode={}
    for c,m in codes:
        sy=to_symbol(c,m)
        px=hist.get(sy)
        if px is None or len(px)<45:continue
        q=px[px.date.astype(str).str.startswith("2026-")].sort_values("date").drop_duplicates("date",keep="last").reset_index(drop=True)
        if len(q)<45:continue
        bycode[c]=q
    samples={d:set() for d in rows}
    for s in data["samples"]:
        samples.setdefault(s["anchor"],set()).add(s["code"])
    featureRows=[];targetRanks=[]
    for n,(date,cands) in enumerate(sorted(rows.items()),1):
        ranked=[]
        for x in cands:
            px=bycode.get(x[0])
            if px is None:continue
            f=flags(px,market_dates,date)
            if f is None:continue
            ranked.append({"date":date,"code":x[0],"target":x[0] in samples.get(date,set()),"baseline":score(x),"hypothesis":score_hypothesis(x,f),"features":f})
        sorted_base=sorted(ranked,key=lambda z:(-z["baseline"],z["code"]))
        sorted_new=sorted(ranked,key=lambda z:(-z["hypothesis"],z["code"]))
        r0={x["code"]:i+1 for i,x in enumerate(sorted_base)}
        r1={x["code"]:i+1 for i,x in enumerate(sorted_new)}
        for z in ranked:
            z["baseRank"]=r0[z["code"]];z["hypothesisRank"]=r1[z["code"]]
        featureRows.extend(ranked)
        print(f"controls {n}/{len(rows)} {date}={len(ranked)} targets={sum(x['target'] for x in ranked)}",flush=True)
    positive=[r for r in featureRows if r["target"]]
    control=[r for r in featureRows if not r["target"]]
    summary={}
    for key in KEYS:
        tp=sum(bool(z["features"].get(key)) for z in positive);cp=sum(bool(z["features"].get(key)) for z in control)
        ta=tp/len(positive) if positive else 0
        ca=cp/len(control) if control else 0
        summary[key]={"targetYes":tp,"targetN":len(positive),"targetPct":round(ta*100,1),"peerYes":cp,"peerN":len(control),"peerPct":round(ca*100,1),"lift":round(ta/ca,2) if ca else None}
    original_bydate={(s["anchor"],s["code"]):s for s in data["samples"]}
    sample=[]
    for z in sorted(positive,key=lambda x:(original_bydate[(x["date"],x["code"])]["post"],original_bydate[(x["date"],x["code"])].get("time") or "",x["code"])):
        orig=original_bydate[(z["date"],z["code"])]
        sample.append({"code":z["code"],"date":orig["post"],"anchor":z["date"],"baseRank":z["baseRank"],"hypothesisRank":z["hypothesisRank"],"features":z["features"],"subset":"train" if z["date"]<="2026-09-18" else "later"})
    summarize=lambda rr:{"n":len(rr),"baseTop20":sum(x["baseRank"]<=20 for x in rr),"hypothesisTop20":sum(x["hypothesisRank"]<=20 for x in rr),"baseTop3":sum(x["baseRank"]<=3 for x in rr),"hypothesisTop3":sum(x["hypothesisRank"]<=3 for x in rr)}
    rankSummary={"all":summarize(sample),"early":summarize([x for x in sample if x["subset"]=="train"]),"later":summarize([x for x in sample if x["subset"]=="later"])}
    out={"version":"G-3D18D-PEER-2026-V1","generatedAt":datetime.now(ZoneInfo("Asia/Taipei")).isoformat(timespec="seconds"),"hypothesis":"G_BASE-like score (no 500B cap) +2 confirmed 3D engulf +2 confirmed 18D engulf +1.5 recent 3D engulf +1.5 recent 18D engulf +.5 rising confirmed 18D; exploratory NOT tuned","peerDefinition":"G_TARGET-style broad momentum candidate on the same actual signal-session date, not all 1982 market stocks","targetAndPeers":{"positiveN":len(positive),"peerN":len(control),"days":len(rows),"chartHistoryErrors":len(errors)},"featureComparisons":summary,"rankSummary":rankSummary,"samples":sample,"notes":["Only 2026 data; all features truncated strictly as of each last completed pre-publication day.","Recent engulfing defined as occurrence among prior three confirmed aggregate candles, not forming bars.","Same stock/date may be reused across candidate exposures; pooled percentages are descriptive, not independent-sample probabilities.","No code whitelist used for ranking; posted symbols used only as labels after assigning features.","Hypothesis bonus weights are exploratory; no genuine post-discovery holdout available."]}
    p=DATA_DIR/"research";p.mkdir(parents=True,exist_ok=True)
    (p/"g_multiday_controls_2026.json").write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({"controls":out["targetAndPeers"],"comparison":summary,"ranks":rankSummary},ensure_ascii=False),flush=True)
if __name__=="__main__":run()
