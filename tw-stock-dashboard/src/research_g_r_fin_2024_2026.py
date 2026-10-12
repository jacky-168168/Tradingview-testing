"""G baseline and four PREDECLARED variants, 2024-01-01 to last audited 2026-10-08.
Research only: no change to production G or any live selection.
All conditions use daily close D or fundamentals available on/before D.
Data caveat: latest universe/paid-in capital => historical survivorship bias;
MOPS archive is revised, not point-in-time immutable.
"""
from __future__ import annotations
import collections,json,math
from datetime import datetime,timedelta
from zoneinfo import ZoneInfo
import numpy as np,pandas as pd
from config import DATA_DIR,BENCHMARK
from pipeline import load_universe
from yahoo_cache import update_many,update_symbol
from research_g_regime_3y import START,END,finite,make_g,get_risk,stock_ret,COST
from research_g_compound_3y import price_bars,study_one,PRINCIPAL
from n_fundamental_archive import month_safe_date
HORIZONS=(1,3,5,10,20)
FIRST="2024-01-01"
OUT=DATA_DIR/"research"/"g_r_fin_2024_2026"
STRATEGIES=("G","G-R1","G-R2","G-R3","G-R4")
CAP_TWD=200000
GATE="SCORE60";TP=.08;SL=.12;HOLD=10
def prev_month(y,m):
    return (y-1,12) if m==1 else (y,m-1)
class Revenue:
    def __init__(self,rows):
        self.index=collections.defaultdict(dict)
        for x in rows:
            try:
                k=(x["market"],str(x["code"]));y=int(x["year"]);m=int(x["month"])
                a=str(x["availableFrom"]);val=float(x["revenue"])
                if a!=month_safe_date(y,m) or val<0 or not math.isfinite(val):continue
                if k in self.index and (y,m) in self.index[k]:
                    if self.index[k][(y,m)][0]!=val:raise ValueError("monthly revenue conflict")
                self.index[k][(y,m)]=(val,a)
            except (TypeError,KeyError,ValueError):
                continue
    def factors(self,stock,day):
        k=("sii" if stock["market"]=="上市" else "otc",str(stock["code"]))
        entries=self.index.get(k,{})
        keys=sorted([p for p,(v,a) in entries.items() if a<=day])
        if not keys:return None
        y,m=keys[-1];out=[]
        for _ in range(14):
            v=entries.get((y,m))
            if v is None or v[1]>day or v[0]<0:return None
            out.append(v[0]);y,m=prev_month(y,m)
        if min(np.mean(out[:12]),out[12])<=0:return None
        avg3=float(np.mean(out[:3]));avg12=float(np.mean(out[:12]))
        prior_windows=[float(np.mean(out[i:i+3])) for i in range(1,12)]
        return {"avg3_12":avg3/avg12,
                "yoy":out[0]/out[12]-1,
                "three_month_new_high":avg3>max(prior_windows),
                "asof":keys[-1]}
def indicators(hist):
    out={}
    for sy,df in hist.items():
        if df is None or len(df)<130:continue
        q=df.sort_values("date").drop_duplicates("date").copy()
        for c in ("open","high","low","close","volume"):
            q[c]=pd.to_numeric(q[c],errors="coerce")
        close=q.close;vol=q.volume;hi=q.high;lo=q.low
        for n in (20,60,120):
            q[f"ma{n}"]=close.rolling(n).mean()
        q["high20prev"]=hi.shift(1).rolling(20).max()
        q["vol20prev"]=vol.shift(1).rolling(20).mean()
        q["vol5prev"]=vol.shift(1).rolling(5).mean()
        q["range5prev"]=hi.shift(1).rolling(5).max()/lo.shift(1).rolling(5).min()-1
        q["range20prev"]=hi.shift(1).rolling(20).max()/lo.shift(1).rolling(20).min()-1
        q["prevclose"]=close.shift(1)
        d={}
        for x in q.itertuples(index=False):
            if str(x.date)>=FIRST:
                d[str(x.date)]=x
        out[sy]=d
    return out
def elig_r1(x,v,rev):
    if v is None or rev is None:return False
    return bool(math.isfinite(v.ma120) and v.close>v.ma20>v.ma60>v.ma120 and rev["avg3_12"]>1.0)
def elig_r2(x,v,rev):
    if v is None or rev is None:return False
    return bool(v.close>v.high20prev and rev["yoy"]>.10 and rev["three_month_new_high"])
def elig_r3(x,v,rev):
    if v is None:return False
    args=(v.range5prev,v.range20prev,v.vol5prev,v.vol20prev,v.high20prev,v.volume)
    if not all(math.isfinite(float(a)) for a in args):return False
    return bool(v.range5prev<v.range20prev*.65 and v.vol5prev<v.vol20prev*.8
        and v.volume>v.vol20prev*1.2 and v.close>v.high20prev)
def elig_r4(x,v):
    if v is None:return False
    args=(v.ma20,v.open,v.low,v.close,v.prevclose)
    if not all(math.isfinite(float(a)) for a in args):return False
    return bool(v.low<=v.ma20*1.02 and v.close>=v.ma20*.995
        and v.close>v.open and v.close>v.prevclose)
def construct(dates,base,history,revenues):
    picks={name:{} for name in STRATEGIES}
    counts=collections.Counter();available=collections.Counter()
    for i,day in enumerate(dates):
        rows=base.get(day,[])
        picks["G"][day]=rows
        for name in ("G-R1","G-R2","G-R3"):
            group=[]
            for x in rows:
                v=history.get(x["sym"],{}).get(day)
                rev=revenues.factors(x,day) if name!="G-R3" else None
                if name in ("G-R1","G-R2"):
                    available[name]+=rev is not None
                passed={"G-R1":elig_r1,"G-R2":elig_r2,"G-R3":elig_r3}[name](x,v,rev)
                if passed:group.append(x)
            picks[name][day]=group
        # G-R4 uses a PRIOR G signal, observed pullback on day D, entry D+1.
        # Never calls this the two-minute original Bottom indicator.
        recent={}
        for delta in range(1,6):
            if i-delta<0:break
            prior=dates[i-delta]
            for x in base.get(prior,[]):
                sy=x["sym"]
                if sy not in recent:recent[sy]=x
        matched=[]
        for sy,x in recent.items():
            v=history.get(sy,{}).get(day)
            if elig_r4(x,v):matched.append({**x,"close":float(v.close),
                  "signalAgeSessions":(i-dates.index(next(
                   dates[j] for j in range(max(0,i-5),i) if any(p["sym"]==sy for p in base.get(dates[j],[])))))})
        matched.sort(key=lambda x:(-float(x.get("score",0)),str(x["code"])))
        picks["G-R4"][day]=matched[:3]
        for name in STRATEGIES:counts[name]+=len(picks[name].get(day,[]))
    return picks,dict(counts),dict(available)
def forward_stats(dates,picks,prices,gate,risk,h):
    vals=[];years=collections.defaultdict(list);missing=0
    for i,d in enumerate(dates):
        if i+h>=len(dates) or i+1>=len(dates):continue
        if (risk.get(d) or {}).get("score",-1)<gate:continue
        items=picks.get(d,[])
        if not items:continue
        ret=[stock_ret(prices,x,dates[i+1],dates[i+h]) for x in items]
        if any(x is None for x in ret):
            missing+=1;continue
        v=float((1+np.mean(ret))*(1-COST)-1)
        vals.append(v);years[d[:4]].append(v)
    def calc(a):
        if not a:return {"signals":0,"winPct":None,"avgNetPct":None,"avgWinPct":None,"avgLossPct":None}
        w=[x for x in a if x>0];l=[x for x in a if x<=0]
        return {"signals":len(a),"winPct":round(100*len(w)/len(a),2),
        "avgNetPct":round(100*np.mean(a),3),
        "avgWinPct":round(100*np.mean(w),3) if w else None,
        "avgLossPct":round(100*np.mean(l),3) if l else None}
    return {"full":calc(vals),"byYear":{y:calc(a) for y,a in years.items()},"missingPriceSignals":missing}
def main():
    OUT.mkdir(parents=True,exist_ok=True)
    universe=[x for x in load_universe() if finite(x.get("capitalB")) and float(x["capitalB"])>0]
    start=datetime.fromisoformat(START)-timedelta(days=430)
    end=datetime.fromisoformat(END)+timedelta(days=35)
    hist,errors=update_many([(x["code"],x["market"]) for x in universe],start,end)
    _,ix,err=update_symbol(BENCHMARK,start,end)
    if err or ix is None or ix.empty:raise RuntimeError("Benchmark unavailable "+str(err))
    ix=ix.sort_values("date").drop_duplicates("date").reset_index(drop=True)
    all_dates=[d for d in ix.date.astype(str) if START<=d<=END]
    if len(all_dates)!=728:raise RuntimeError(f"Expected 728 dates; got {len(all_dates)}")
    risk,_=get_risk(ix,all_dates)
    risk_rows=json.loads((DATA_DIR/"research"/"g_regime_3y"/"market_risk_daily.json").read_text())
    risk_records={x["date"]:x for x in risk_rows}
    base,prices,g_audit=make_g(all_dates,ix,universe,hist)
    data_path=DATA_DIR/"research"/"n_canslim"/"monthly_revenue.json"
    if not data_path.exists():raise RuntimeError("Point-in-time delayed MOPS monthly revenue archive missing")
    archive=json.loads(data_path.read_text(encoding="utf-8"))
    rows=archive if isinstance(archive,list) else archive.get("rows",[])
    if len(rows)<50000:raise RuntimeError("MOPS archive has inadequate coverage")
    revenue=Revenue(rows)
    features=indicators(hist)
    picks,counts,coverage=construct(all_dates,base,features,revenue)
    test_days=[d for d in all_dates if d>=FIRST]
    groups={"all":test_days}
    for y in ("2024","2025","2026"):groups[y]=[d for d in test_days if d.startswith(y)]
    valid_symbols={x["sym"] for model in STRATEGIES for d in test_days for x in picks[model].get(d,[])}
    bars,bad=price_bars(hist,valid_symbols)
    model_results={}
    for model in STRATEGIES:
        yearly={}
        for segment,ds in groups.items():
            performance,curve,trades=study_one(ds,picks[model],bars,risk_records,
                GATE,TP,SL,HOLD,CAP_TWD,logs=True)
            yearly[segment]={"summary":{k:performance.get(k) for k in
                ("capitalEnd","netReturnPct","maxDDPct","filledBuys","closedTrades",
                 "wins","losses","winPct","avgNetPct","avgWinPct","avgLossPct","openAtEnd")},
                "dailyEquity":curve if segment=="all" else [],
                "trades":trades if segment=="all" else []}
        horizons={str(h):forward_stats(test_days,picks[model],prices,60,risk_records,h) for h in HORIZONS}
        model_results[model]={"performance":yearly,"horizons":horizons,
            "signals":sum(bool(picks[model].get(d)) for d in test_days),
            "candidateCount":sum(len(picks[model].get(d,[])) for d in test_days)}
        print("STRATEGY_COMPLETE",model,yearly["all"]["summary"],flush=True)
    report={"version":"G_R1_R4_FIN_RESEARCH_V1","status":"COMPLETE_G_R1_R4_ONLY",
            "createdAt":datetime.now(ZoneInfo("Asia/Taipei")).isoformat(),
            "window":{"start":FIRST,"end":END,"sessions":len(test_days)},
            "scope":"G variants share ORIGINAL reconstructed G top 3 as candidate pool; reject failing ranks; R4 postpones entry up to five sessions.",
            "execution":{"initialTWD":PRINCIPAL,"marketGate":GATE,"profitTargetPct":8,
               "stopPct":12,"maxHoldSessions":10,"maxTicketTWD":CAP_TWD,
               "brokerPctEachSide":.1425,"sellTaxPct":.3,"slippagePctEachSide":.1,
               "fillRule":"Signal close D, next open entry <=D close +3%; daily OHLC stop-first ambiguity"},
            "rules":{"G":"Unchanged G_DOUBLE_PERSIST top three each close",
               "G-R1":"G top3, latest point-in-time-safe 3m revenue mean > 12m mean, close > MA20 > MA60 > MA120",
               "G-R2":"G top3, close > preceding 20-day high, 3m average revenue new high vs preceding 11 complete 3m windows, latest revenue YoY > 10%",
               "G-R3":"G top3, prior five-day range < 65% of prior 20-day range, prior five-day mean volume < 80% of prior 20, today's volume > 1.2x prior 20, close > preceding 20-day high",
               "G-R4":"Within next 5 sessions of prior G top3, low <= MA20*1.02, close >= MA20*.995, close>open and >prior close; enter next open, daily MA proxy NOT 2-minute Bottom"},
            "audit":{"g":g_audit,"priceErrors":len(errors),"marketRiskDays":len(risk),
               "mopsRevenueRows":len(rows),"revenueFeatureAvailable":coverage,
               "latestSurvivingUniverse":len(universe),"stockBarMissing":bad,
               "lastDataLimit":"Risk Score pinned only through 2026-10-08; 2026-10-12 deliberately excluded"},
            "limitations":["Current, not historical, listed universe and paid-in capital: survivorship bias",
              "MOPS latest-vintage revised revenue with conservative 16th-next-month disclosure-date proxy is not a true point-in-time database",
              "R4 uses DAILY MA pullback proxy not the original Bottom(2m) signal",
              "Overlapping fixed-horizon forward outcome snapshots are not a cash-reinvested portfolio",
              "All G-R filters run on original top3 only, no replacement with previously lower-ranked G securities"],
            "strategies":model_results}
    (OUT/"summary.json").write_text(json.dumps({**report,"strategies":{
        k:{"signals":v["signals"],"candidateCount":v["candidateCount"],"horizons":v["horizons"],
        "performance":{p:w["summary"] for p,w in v["performance"].items()}}
        for k,v in model_results.items()}},ensure_ascii=False,indent=2))
    (OUT/"trades.json").write_text(json.dumps({k:v["performance"]["all"]["trades"] for k,v in model_results.items()},ensure_ascii=False))
    (OUT/"equity.json").write_text(json.dumps({k:v["performance"]["all"]["dailyEquity"] for k,v in model_results.items()},ensure_ascii=False))
    print("G_R_COMPLETE",json.dumps({"days":len(test_days),"signals":{k:v["signals"] for k,v in model_results.items()}},ensure_ascii=False))
if __name__=="__main__":main()
