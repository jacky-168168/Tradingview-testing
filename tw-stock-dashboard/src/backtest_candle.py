"""2026-only exploratory 3D/18D price-structure hypothesis against broad G control.
A completed bullish engulfing is a BONUS, not mandatory; 20 targets refute using
it as a universal hard gate. Reports next-session Top3 forward returns and labels.
"""
from __future__ import annotations
import argparse,bisect,json,time
from datetime import datetime,timedelta
from zoneinfo import ZoneInfo
import numpy as np,pandas as pd
from config import DATA_DIR
from pipeline import load_universe
from yahoo_cache import update_many,update_symbol,to_symbol
from scoring import precompute_features
from multi_day_candles import aggregate_bars,candle_test
from research_signal_samples import SAMPLES
from backtest_signal_model import H,stat,price_return,phase_portfolio
from g_target import eligible
FEAT=("ret20","ma20Slope","atrPct","range20Pct","turnoverB")
PCT=("ret20P","slopeP","atrP","range20P","turnoverP")
WEIGHTS={"break3":4,"break18":3,"bull3":2,"bull18":1,"eng18":2,"eng3":1}
def num(x):
    try:return float(x) if np.isfinite(float(x)) else None
    except:return None
def base_score(r):
    near=max(0,min(100,100+r["breakoutPct"]/18*100))
    return round((30*r["ret20P"]+25*r["slopeP"]+10*r["atrP"]+15*r["range20P"]+15*r["turnoverP"]+5*near)/100,4)
def structure(base,flags):
    return round(base+sum(weight*int(flags.get(name,False)) for name,weight in WEIGHTS.items()),4)
def bar_state(confirmed,ends,d,close):
    ix=bisect.bisect_right(ends,d)-1
    if ix<0:return {"bull":False,"eng":False,"break":False}
    curr=confirmed[ix];prev=confirmed[ix-1] if ix>=1 else None
    pattern=candle_test(prev,curr) if prev is not None else None
    ref=prev if curr["date"]==d else curr
    return {"bull":bool(curr["close"]>curr["open"]),"eng":bool(pattern and pattern["bodyEngulf"]),"break":bool(ref and close>float(ref["high"]))}
def build_flags(bars3,ends3,bars18,ends18,d,close):
    a=bar_state(bars3,ends3,d,close);b=bar_state(bars18,ends18,d,close)
    return {"bull3":a["bull"],"eng3":a["eng"],"break3":a["break"],"bull18":b["bull"],"eng18":b["eng"],"break18":b["break"]}
def run(start="2026-01-01",end="2026-10-07"):
    if start!="2026-01-01" or not end.startswith("2026-"):raise ValueError("僅回測2026年")
    if end>datetime.now(ZoneInfo("Asia/Taipei")).date().isoformat():raise ValueError("不可回測未來")
    t=time.time();universe=load_universe()
    hist,errors=update_many([(x["code"],x["market"]) for x in universe],datetime(2025,7,1),datetime.fromisoformat(end)+timedelta(days=30))
    _,market,me=update_symbol("^TWII",datetime(2026,1,1),datetime.fromisoformat(end)+timedelta(days=30))
    if me or market is None or market.empty:raise RuntimeError(f"benchmark failed: {me}")
    calendar=sorted(set(z for z in market.date.astype(str) if z.startswith("2026-")))
    signals=[d for d in calendar if start<=d<=end];pos={d:i for i,d in enumerate(calendar)}
    targets={};posts=[]
    for p in SAMPLES:
        prev=[d for d in signals if d<p["date"]]
        if not prev:continue
        d=prev[-1];targets.setdefault(d,set()).add(p["code"])
        posts.append({**p,"anchor":d})
    features={};prices={};bar_sets={}
    for i,s in enumerate(universe,1):
        sy=to_symbol(s["code"],s["market"]);raw=hist.get(sy)
        if raw is None or len(raw)<60:continue
        raw=raw.sort_values("date").drop_duplicates("date",keep="last").reset_index(drop=True)
        f=precompute_features(raw)
        h=pd.to_numeric(f.high,errors="coerce");l=pd.to_numeric(f.low,errors="coerce");v=pd.to_numeric(f.volume,errors="coerce")
        f["range20Pct"]=(h.rolling(20).max()/l.rolling(20).min()-1)*100
        f["turnoverB"]=pd.to_numeric(f.close,errors="coerce")*v/100_000_000
        features[sy]=f.set_index("date",drop=False)
        prices[sy]=raw.set_index("date",drop=False)
        year=raw[raw.date.astype(str).str.startswith("2026-")]
        candle3=aggregate_bars(year,calendar,3);candle18=aggregate_bars(year,calendar,18)
        complete3=candle3[candle3.complete].to_dict("records") if not candle3.empty else []
        complete18=candle18[candle18.complete].to_dict("records") if not candle18.empty else []
        bar_sets[sy]=(complete3,[x["date"] for x in complete3],complete18,[x["date"] for x in complete18])
        if i%400==0:print(f"precomputed {i}/{len(universe)} candle histories",flush=True)
    models={"G_BROAD":{"ranks":{},"counts":{}},"G_CANDLE":{"ranks":{},"counts":{}},"G_TRIGGER":{"ranks":{},"counts":{}}}
    samples={}
    for di,d in enumerate(signals,1):
        rows=[]
        for s in universe:
            sy=to_symbol(s["code"],s["market"]);ft=features.get(sy)
            if ft is None or d not in ft.index:continue
            q=ft.loc[d];q=q.iloc[-1] if isinstance(q,pd.DataFrame) else q
            vals=[num(q.get(k)) for k in FEAT];close=num(q.get("close"));br=num(q.get("breakoutPct"))
            if close is None or br is None or min([close,num(q.get("volume")) or 0])<=0 or any(v is None for v in vals):continue
            rows.append({"code":s["code"],"market":s["market"],"name":s["name"],"capitalB":num(s.get("capitalB")) or 0,"close":close,"breakoutPct":br,**dict(zip(FEAT,vals))})
        if not rows:
            for k in models:models[k]["ranks"][d]=[];models[k]["counts"][d]=0
            continue
        frame=pd.DataFrame(rows)
        for raw,pct in zip(FEAT,PCT):frame[pct]=frame[raw].rank(pct=True,method="average")*100
        candidates=[]
        for z in frame.to_dict("records"):
            if not eligible(z):continue
            sy=to_symbol(z["code"],z["market"]);bs=bar_sets.get(sy)
            if bs is None:continue
            flags=build_flags(*bs,d,z["close"])
            z["candleFlags"]=flags;z["baselineScore"]=base_score(z);z["candleScore"]=structure(z["baselineScore"],flags)
            candidates.append(z)
            if z["code"] in targets.get(d,set()):samples[(d,z["code"])]=z
        choice={
            "G_BROAD":sorted(candidates,key=lambda x:(-x["baselineScore"],x["code"])),
            "G_CANDLE":sorted(candidates,key=lambda x:(-x["candleScore"],x["code"])),
            "G_TRIGGER":sorted([x for x in candidates if any(x["candleFlags"][f] for f in ("break3","break18","eng3","eng18"))],key=lambda x:(-x["candleScore"],x["code"]))
        }
        for key,order in choice.items():
            models[key]["counts"][d]=len(order)
            models[key]["ranks"][d]=[{**x,"rank":i+1,"score":x["baselineScore"] if key=="G_BROAD" else x["candleScore"]} for i,x in enumerate(order[:20])]
            if d in targets:
                models[key].setdefault("targetRanks",{})
                for i,x in enumerate(order):
                    if x["code"] in targets[d]:models[key]["targetRanks"][(d,x["code"])]=i+1
        if di%35==0 or di==len(signals):print(f"{d} candle {di}/{len(signals)} candidates={len(candidates)}",flush=True)
    out_models={}
    for key,content in models.items():
        rs=content["ranks"];returns={h:[] for h in H};per_rank={h:{i:[] for i in (1,2,3)} for h in H};trade_rows=[]
        for d in signals:
            p=pos[d]
            if p+1>=len(calendar):continue
            buydate=calendar[p+1];by_h={h:[] for h in H}
            for x in rs.get(d,[]):
                if x["rank"]>3:continue
                row={"signalDate":d,"rank":x["rank"],"code":x["code"],"name":x["name"],"score":x["score"],"flags":x["candleFlags"]}
                sy=to_symbol(x["code"],x["market"])
                for h in H:
                    r=price_return(prices.get(sy),buydate,calendar[p+h]) if p+h<len(calendar) else None
                    row[f"ret{h}"]=round(r,2) if r is not None else None
                    if r is not None:by_h[h].append(r);per_rank[h][x["rank"]].append(r)
                trade_rows.append(row)
            for h in H:
                if by_h[h]:returns[h].append(float(np.mean(by_h[h])))
        check=[]
        for s in sorted(posts,key=lambda x:(x["date"],x.get("time",""),x["code"])):
            r=content.get("targetRanks",{}).get((s["anchor"],s["code"]))
            row=samples.get((s["anchor"],s["code"]))
            check.append({"code":s["code"],"postDate":s["date"],"postTime":s.get("time"),"anchor":s["anchor"],"rank":r,"top3":bool(r and r<=3),"top20":bool(r and r<=20),"flags":row.get("candleFlags") if row else None})
        summary={"n":len(check),"eligible":sum(x["flags"] is not None for x in check),"top20":sum(x["top20"] for x in check),"top3":sum(x["top3"] for x in check)}
        out_models[key]={"candidateStats":{"avg":round(float(np.mean(list(content["counts"].values()))),1),"min":min(content["counts"].values()),"max":max(content["counts"].values()),"days":len(content["counts"])},"summary":[{"horizon":h,"top3Daily":stat(returns[h]),"rank1":stat(per_rank[h][1]),"rank2":stat(per_rank[h][2]),"rank3":stat(per_rank[h][3]),"phasePortfolio":phase_portfolio(signals,calendar,pos,rs,prices,{},h)} for h in H],"sampleAudit":{**summary,"checks":check},"signals":trade_rows}
    out={"version":"G-CANDLE-3D-18D-2026-V1","generatedAt":datetime.now(ZoneInfo("Asia/Taipei")).isoformat(timespec="seconds"),"period":{"start":start,"end":end},"days":len(signals),"historyErrors":len(errors),"universe":len(universe),"weights":WEIGHTS,"hardTrigger":"3D/18D prior confirmed bar high broken by close, OR latest confirmed 3D/18D bullish body engulf","models":out_models,"notes":["2026-only historical day-close selection; next trading session open entry; no poster trigger-price strategy claimed.","3D/18D bars use year-reset trading sessions; only fully completed multi-day bars may qualify as engulf.","Same broad G gate in all three models, without 500B stock-cap hard gate; G_BROAD is not exactly the previously published G_BASE.","G_CANDLE bonuses fixed in exploratory research; informed by already seen 20 samples, so neither that label fit nor 2026 retrospective returns is a true independent prospective test.","Rank 4-20 are diagnostic only; trading PnL simulates only top 3.","Before enough completed 18D bars in 2026, G_CANDLE has fewer active higher-timeframe conditions.","Current stock universe may suffer survivorship bias."]}
    target=DATA_DIR/"backtest_g";target.mkdir(parents=True,exist_ok=True)
    (target/"g_candle_2026.json").write_text(json.dumps(out,ensure_ascii=False,separators=(",",":")),encoding="utf-8")
    print(json.dumps({"period":out["period"],"historyErrors":out["historyErrors"],"runtime":round(time.time()-t,1),"results":{k:{"samples":v["sampleAudit"]["top20"],"samplesTop3":v["sampleAudit"]["top3"],"stats":{x["horizon"]:x["top3Daily"] for x in v["summary"]}} for k,v in out_models.items()}},ensure_ascii=False),flush=True)
if __name__=="__main__":
    ap=argparse.ArgumentParser();ap.add_argument("--start",default="2026-01-01");ap.add_argument("--end",default="2026-10-07");a=ap.parse_args();run(a.start,a.end)
