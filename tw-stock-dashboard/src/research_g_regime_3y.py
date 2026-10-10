"""2023-10..2026-10 audited G_DOUBLE_PERSIST + dated TWII market regime.
Only historical information available by each signal-day close may enter selection.
Stock signal at close D; buy next exchange opening; sell H sessions after D.
Risk Score is reconstructed from date-pinned TWSE equity breadth + foreign flow.
Night-risk overlay is optional and only evaluated with genuine dated official TX
afterhours reports, never same-date OpenAPI night rows (which may be prior night).
"""
from __future__ import annotations
import argparse,collections,json,math,os,time
from concurrent.futures import ThreadPoolExecutor,as_completed
from datetime import datetime,timedelta
from zoneinfo import ZoneInfo
import numpy as np,pandas as pd,requests
from bs4 import BeautifulSoup
from config import DATA_DIR,BENCHMARK
from pipeline import load_universe
from yahoo_cache import update_many,update_symbol,to_symbol
from g_target import eligible
from g_live import g_score
from g_persistence import persistence_features
from risk import breadth,foreign_market_net
from futures_night import night_from_html
START="2023-10-09";END="2026-10-08";HORIZONS=(1,5,10,20)
THRESHOLDS=(0,50,55,60,65,70,75,80)
OUT=DATA_DIR/"research"/"g_regime_3y"
COST=0.00585 # 0.1425% brokerage per side + .30% Taiwan share transaction tax
def finite(x):
    try:
        v=float(x);return v if math.isfinite(v) else None
    except (ValueError,TypeError):return None
def score_risk(c,i,br,foreign):
    # Mirrors src/risk.py build() (historical day-specific inputs).
    ma5=np.mean(c[i-4:i+1]);ma20=np.mean(c[i-19:i+1]);prev20=np.mean(c[i-24:i-4])
    r5=(c[i]/c[i-5]-1)*100;r20=(c[i]/c[i-20]-1)*100
    s=(15 if c[i]>ma20 else 0)+(10 if ma5>ma20 else 0)+(5 if ma20>prev20 else 0)
    s+=20 if br>=55 else 12 if br>=50 else 5 if br>=45 else 0
    s+=15 if foreign>0 else 6 if foreign>-50 else 0
    s+=15 if r5>2 else 10 if r5>0 else 4 if r5>-2 else 0
    s+=10 if r20>5 else 6 if r20>0 else 2 if r20>-5 else 0
    s+=10 if c[i]>c[i-1] else 0
    return min(100,s)
def get_risk(index,dates,workers=7):
    """Use the completed, independently collected official date-pinned Risk Score archive.
    No TWSE live refetch, no missing-day interpolation, no changing archived bins.
    """
    coverage_path=OUT/"coverage.json";daily_path=OUT/"market_risk_daily.json";inputs_path=OUT/"risk_inputs.json"
    if not all(p.exists() for p in (coverage_path,daily_path,inputs_path)):
        raise RuntimeError("Validated historical risk archive missing; run standalone collector first")
    coverage=json.loads(coverage_path.read_text(encoding="utf-8"))
    rows=json.loads(daily_path.read_text(encoding="utf-8"))
    inputs=json.loads(inputs_path.read_text(encoding="utf-8"))
    n=len(dates)
    if coverage.get("complete") is not True or any(coverage.get(k)!=n for k in ("tradingDays","riskScoredDays","officialValidDays")):
        raise RuntimeError("Historical Risk Score coverage is not verified for every market session")
    if len(rows)!=n or [r.get("date") for r in rows]!=list(dates) or len(set(dates))!=n:
        raise RuntimeError("Historical risk archive and benchmark trading calendars differ")
    ix=index.set_index(index.date.astype(str))
    scores={}
    for r in rows:
        day=r["date"];z=inputs.get(day)
        if not isinstance(z,dict) or z.get("ok") is not True:
            raise RuntimeError("Official TWSE risk inputs unverified for "+day)
        try:
            up=int(z["up"]);down=int(z["down"]);foreign=float(z["foreign"])
            score=r["score"];close=float(r["index"]);index_close=float(ix.loc[day,"close"])
            if isinstance(score,bool) or not isinstance(score,int) or not 0<=score<=100:
                raise ValueError("bad score")
            if up+down<500 or not math.isfinite(foreign) or abs(float(r["breadth"])-100*up/(up+down))>0.11:
                raise ValueError("bad official breadth/foreign")
            if not math.isfinite(close) or abs(close-index_close)>max(0.5,index_close*0.0001):
                raise ValueError("index close differs from archived scoring source")
        except (KeyError,ValueError,TypeError) as e:
            raise RuntimeError("Risk archive invalid on "+day+": "+str(e)) from e
        scores[day]=score
    print("PASS verified official historical Risk Score archive",len(scores),"/",n,
          "source",str(daily_path),"collected",coverage.get("generatedAt"),flush=True)
    return scores,inputs
def tx_report(d,contract,report_date):
    query={"queryType":"2","marketCode":"1","MarketCode":"1","dateaddcnt":"",
           "commodity_id":"TX","commodity_idt":"TX","commodity_id2":"",
           "queryDate":report_date.replace("-","/")}
    for trial in range(2):
        try:
            r=requests.get("https://www.taifex.com.tw/cht/3/futDailyMarketReport",params=query,timeout=27)
            r.raise_for_status()
            return night_from_html(r.text,d,contract,report_date)
        except Exception:
            if trial==1:return None
            time.sleep(1)
    return None
def get_night(dates,workers=6):
    """Closest dated settlement-relative return: same-contract TX night only.
    Query NEXT exchange business session to match starting-night D.
    Dataset may have missing periods; never fill with cash-index/ETF proxies.
    """
    cache=OUT/"tx_night_inputs.json";old=json.loads(cache.read_text()) if cache.exists() else {}
    jobs=[]
    for i,d in enumerate(dates[:-1]):
        if d in old:continue
        next_date=dates[i+1]
        # Query known front contract months; rollover may need prior month.
        month=d[:7].replace("-","")
        contracts=[month]
        next_month=(pd.Timestamp(d)+pd.DateOffset(months=1)).strftime("%Y%m")
        if next_month!=month:contracts.append(next_month)
        jobs.append((d,next_date,contracts))
    print("TX official historical afterhours: cached",len(old),"request",len(jobs),flush=True)
    def task(job):
        d,nx,cs=job;out=None
        for contract in cs:
            result=tx_report(d,contract,nx)
            if result is not None:
                out={"ok":True,"contract":contract,"night":result["close"],"officialPct":result.get("officialChangePct"),
                     "officialPoints":result.get("officialChangePoints"),"queryDate":nx};break
        return d,out or {"ok":False,"error":"No fully date-matched official TX afterhours report"}
    for batch in range(0,len(jobs),25):
        with ThreadPoolExecutor(max_workers=workers) as ex:
            fs=[ex.submit(task,j) for j in jobs[batch:batch+25]]
            for ff in as_completed(fs):
                d,res=ff.result();old[d]=res
        cache.write_text(json.dumps(old,ensure_ascii=False),encoding="utf-8")
        print("TX night",min(batch+25,len(jobs)),"/",len(jobs),"valid",sum(bool(z.get("ok")) for z in old.values()),flush=True)
    return old
def calc_g(hist,info,daymap):
    q=hist.sort_values("date").drop_duplicates("date").copy()
    if len(q)<60:return None
    for k in ["open","high","low","close","volume","adjclose"]:q[k]=pd.to_numeric(q[k],errors="coerce")
    c=q.close;hi=q.high;lo=q.low;v=q.volume;old=c.shift()
    tr=pd.concat([hi-lo,(hi-old).abs(),(lo-old).abs()],axis=1).max(axis=1)
    q["ret20"]=(c/c.shift(20)-1)*100
    ma20=c.rolling(20).mean();q["ma20Slope"]=(ma20/ma20.shift(5)-1)*100
    q["atrPct"]=tr.rolling(14).mean()/c*100
    q["range20Pct"]=(hi.rolling(20).max()/lo.rolling(20).min()-1)*100
    q["breakoutPct"]=(c/hi.shift().rolling(20).max()-1)*100
    q["turnoverB"]=c*v/100_000_000
    q["cap"]=float(info["capitalB"])
    q["sym"]=to_symbol(info["code"],info["market"]);q["code"]=info["code"]
    q["name"]=info["name"];q["market"]=info["market"]
    q["adjOpen"]=q.open*q.adjclose/q.close
    q["adjClose"]=q.adjclose
    maps=q.date.astype(str).map(daymap)
    q["year"]=maps.map(lambda x:x[0] if isinstance(x,tuple) else "")
    q["i"]=maps.map(lambda x:x[1] if isinstance(x,tuple) else -1)
    for n in (3,18):
        group=q["i"].astype(int)//n
        tmp=q.assign(gr=group)
        counts=tmp[tmp.i>=0].groupby(["year","gr"]).date.nunique()
        highs=tmp[tmp.i>=0].groupby(["year","gr"]).high.max()
        lookup={(year,int(g)):float(h) for (year,g),h in highs.items()
                if counts.loc[(year,g)]==n}
        q[f"prior{n}High"]=[lookup.get((year,int(ix)//n-1)) if ix>=0 else None for year,ix in zip(q.year,q.i)]
        q[f"break{n}"]=q.close>q[f"prior{n}High"]
    return q
def make_g(dates,ix,universe,hist):
    # One complete historical cross-section per date; never use after-day pocket ranks.
    cal={d:(d[:4],i) for year in sorted({d[:4] for d in ix.date.astype(str)})
         for i,d in enumerate(x for x in ix.date.astype(str) if x[:4]==year)}
    frames=[];prices={}
    for n,item in enumerate(universe,1):
        sy=to_symbol(item["code"],item["market"])
        h=hist.get(sy)
        if h is None or h.empty:continue
        try:
            q=calc_g(h,item,cal)
            if q is None:continue
            frames.append(q[["date","code","name","market","sym","close","ret20","ma20Slope","atrPct","range20Pct","turnoverB","breakoutPct","cap","break3","break18"]])
            prices[sy]=q.set_index("date",drop=False)[["date","open","close","adjOpen","adjClose","volume"]]
        except Exception as e:
            print("G features invalid",sy,str(e)[:180],flush=True)
        if n%350==0:print("G feature matrices",n,"/",len(universe),flush=True)
    if not frames:raise RuntimeError("G stock history missing; cannot backtest.")
    panel=pd.concat(frames,ignore_index=True)
    panel=panel[(panel.date>=dates[0])&(panel.date<=dates[-1])].copy()
    panel=panel.replace([np.inf,-np.inf],np.nan).dropna(subset=["close","ret20","ma20Slope","atrPct","range20Pct","turnoverB","breakoutPct"])
    panel=panel[(panel.close>0)&(panel.turnoverB>0)]
    features={"ret20":"ret20P","ma20Slope":"slopeP","atrPct":"atrP","range20Pct":"range20P","turnoverB":"turnoverP"}
    for field,pct in features.items():
        panel[pct]=panel.groupby("date")[field].rank(method="average",pct=True)*100
    # Live eligibility uses all listed and OTC issues and current paid-in capital,
    # then score/3D&18D breaks; do not sneak same-day pocket into persistence.
    e=(panel.close>=10)&(panel.cap>0)&(panel.ret20P>=60)&(panel.slopeP>=70)&(panel.atrP>=55)&(panel.range20P>=65)&(panel.turnoverP>=65)&(panel.breakoutPct>=-25)&panel.break3&panel.break18
    panel=panel[e].copy()
    panel["base"]=(30*panel.ret20P+25*panel.slopeP+10*panel.atrP+
                    15*panel.range20P+15*panel.turnoverP+
                    5*(100+panel.breakoutPct/18*100).clip(lower=0,upper=100))/100
    panel.sort_values(["date","base","code"],ascending=[True,False,True],inplace=True)
    groups={d:g.to_dict("records") for d,g in panel.groupby("date",sort=False)}
    picks={};basepockets={};window=collections.deque(maxlen=10);lastyear=None
    for i,d in enumerate(dates):
        if d[:4]!=lastyear:window.clear();lastyear=d[:4]
        rows=groups.get(d,[])
        basepocket={x["code"]:{"rank":j+1,"score":round(float(x["base"]),4)} for j,x in enumerate(rows[:20])}
        ranked=[]
        for row in rows:
            base=float(row["base"])
            p=persistence_features(row["code"],list(window),round(base,4))
            ranked.append({**row,"base":base,"score":round(round(base,4)+p["bonus"],4),
                 "bonus":p["bonus"],"previousTop20":p["past10Top20"]})
        ranked.sort(key=lambda z:(-z["score"],-round(z["base"],4),z["code"]))
        picks[d]=ranked[:3]
        window.append(basepocket);basepockets[d]=basepocket
        if (i+1)%80==0:print("Reconstruct G_DOUBLE_PERSIST",i+1,"/",len(dates),d,"top3",len(picks[d]),flush=True)
    return picks,prices,{"symbols":len(prices),"dailyFeatureRows":len(panel),"validGSignalDays":sum(len(v)>0 for v in picks.values()),
        "meanGStocksPerSignal":round(len(panel)/max(1,len(dates)),2)}
def stock_ret(prices,stock,buy,exitdate):
    px=prices.get(stock.get("sym"))
    if px is None or buy not in px.index or exitdate not in px.index:return None
    a=px.loc[buy];b=px.loc[exitdate]
    if isinstance(a,pd.DataFrame):a=a.iloc[-1]
    if isinstance(b,pd.DataFrame):b=b.iloc[-1]
    op=finite(a.adjOpen);cl=finite(b.adjClose)
    if not op or not cl or op<=0 or cl<=0 or finite(a.volume) is None or a.volume<=0:return None
    between=px.loc[buy:exitdate]
    raw=between.close.astype(float)
    jumps=raw/raw.shift(1)
    if bool(((jumps<0.55)|(jumps>1.8)).fillna(False).any()):return None
    return cl/op-1
def stats(x):
    a=np.asarray([z for z in x if z is not None and np.isfinite(z)],float)
    return {"n":len(a),"avgPct":round(100*a.mean(),3) if len(a) else None,
        "medianPct":round(100*np.median(a),3) if len(a) else None,
        "winPct":round(100*np.mean(a>0),2) if len(a) else None}
def run_model(dates,picks,prices,score,night,model,h):
    means=[];samples=[];signals=0;allowed=0;miss=0;nightCoverage=0
    daily={}
    for i,d in enumerate(dates):
        if i+1>=len(dates) or i+h>=len(dates):continue
        g=picks.get(d,[])
        if not g:continue
        signals+=1;val=score.get(d)
        n=night.get(d) or {};txpct=n.get("officialPct") if n.get("ok") else None
        if txpct is not None:nightCoverage+=1
        if val is None:miss+=1;continue
        adj=-25 if txpct is not None and txpct<=-2 else -15 if txpct is not None and txpct<=-1 else -8 if txpct is not None and txpct<=-.5 else 10 if txpct is not None and txpct>=2 else 7 if txpct is not None and txpct>=1 else 4 if txpct is not None and txpct>=.5 else 0
        tval=max(0,min(100,val+adj))
        if model.startswith("TX") and txpct is None:continue
        thresh=int(model.split("_")[1])
        eligible=tval>=thresh if model.startswith("TX") else val>=thresh
        if not eligible:continue
        allowed+=1
        buy=dates[i+1];exitdate=dates[i+h]
        rets=[stock_ret(prices,x,buy,exitdate) for x in g]
        ok=[x for x in rets if x is not None]
        if len(ok)!=len(g):continue  # full top3 required; no silent survivor replacement
        r=(1+np.mean(ok))*(1-COST)-1
        daily[d]={"gross":round(float(np.mean(ok)),8),"net":round(float(r),8),"buy":buy,"sell":exitdate,"score":val,"txPct":txpct,"adjusted":tval,
                 "codes":[x["code"] for x in g]}
        means.append(r);samples.append({"date":d,**daily[d]})
    phases=[]
    for phase in range(h):
        eq=1.;peak=1.;mdd=0.;pn=0;posp=0
        for i in range(phase,len(dates)-h,h):
            d=dates[i];z=daily.get(d)
            if z is not None:
                eq*=1+z["net"];pn+=1;posp+=z["net"]>0
            peak=max(peak,eq);mdd=min(mdd,eq/peak-1)
        phases.append({"phase":phase,"trades":pn,"returnPct":round((eq-1)*100,2),
               "maxDDatExitPct":round(mdd*100,2),"winPct":round(posp/pn*100,2) if pn else None})
    vals=[v["returnPct"] for v in phases if v["trades"]]
    dd=[v["maxDDatExitPct"] for v in phases if v["trades"]]
    return {"model":model,"horizon":h,"GsignalDays":signals,"riskMissingDays":miss,
        "txNightDays":nightCoverage,"gatedDays":allowed,"executedSignals":len(means),
        "netSignal":stats(means),"phasePortfolio":phases,
        "meanPhaseReturnPct":round(float(np.mean(vals)),2) if vals else None,
        "medianPhaseReturnPct":round(float(np.median(vals)),2) if vals else None,
        "worstPhaseReturnPct":round(min(vals),2) if vals else None,
        "worstPhaseExitMDDPct":round(min(dd),2) if dd else None,
        "trades":samples}
def main(start,end,skip_tx=False):
    stamp=time.time();now=datetime.now(ZoneInfo("Asia/Taipei"))
    if end>now.date().isoformat():raise ValueError("Cannot backtest the future")
    OUT.mkdir(parents=True,exist_ok=True)
    universe=[x for x in load_universe() if finite(x.get("capitalB")) and float(x["capitalB"])>0]
    pullfrom=datetime.fromisoformat(start)-timedelta(days=430)
    pullto=datetime.fromisoformat(end)+timedelta(days=35)
    print("Retrieve",len(universe),"listed/OTC stock histories",pullfrom.date(),pullto.date(),flush=True)
    hist,errors=update_many([(x["code"],x["market"]) for x in universe],pullfrom,pullto)
    _,index,indexerr=update_symbol(BENCHMARK,pullfrom,pullto)
    if indexerr or index is None or index.empty:raise RuntimeError("TWII benchmark unavailable "+str(indexerr))
    index=index.sort_values("date").drop_duplicates("date").reset_index(drop=True)
    fullcalendar=index.date.astype(str).tolist();dates=[d for d in fullcalendar if start<=d<=end]
    if len(dates)<500:raise RuntimeError("Less than 500 trading days, abort incomplete 3y backtest")
    print("Stock fetch complete",len(hist),"errors",len(errors),"market days",len(dates),flush=True)
    picks,prices,audit=make_g(dates,index,universe,hist)
    risk,risk_data=get_risk(index,dates)
    if len(risk)!=len(dates):raise RuntimeError("Incomplete official historical Risk Score archive; refuse 3y result")
    night={} if skip_tx else get_night(dates)
    if night and sum(z.get("ok",False) for z in night.values())<len(dates)*.60:
        print("WARN insufficient night source coverage; TX models will be reported but never treated as validated",flush=True)
    out={"version":"G_DOUBLE_PERSIST_TWII_TX_3Y_V1","createdAt":now.isoformat(),
       "period":{"start":start,"end":end},"signalSessions":len(dates),"universeNow":len(universe),
       "stockDataErrors":len(errors),"riskCoverage":len(risk),
       "txNightCoverage":sum(bool(v.get("ok")) for v in night.values()),"audit":audit,
       "method":{"selector":"G_DOUBLE_PERSIST same-day market cross-sectional percentiles; 3D/18D confirmed prior-bar high; prior 10 exchange-day baseline Top20 persistence",
         "lookahead":"G and TWII risk at finished close D; TX night starts 15:00 D (reported under next trading day), completed 05:00 next trading date; next TX-aware entry at opening D+1",
         "execution":"Top3 equally weighted, next exchange open to Hth session close, 0.1425% brokerage each side plus 0.30% stock sale tax",
         "riskScore":"Exact risk.py 8 thresholds, date-pinned TWSE breadth/foreign for each session, no neutral fill",
         "TXScore":"Unvalidated scenario adjustment using official same-month TX night percentage relative to futures settlement reference (not cash-index). TX models require observed night report",
         "sampleRisk":"Latest company universe/capital => survivor/corporate-history bias; Yahoo adjusted OHLC; model thresholds tuned only after independent evaluation",
         "MDD":"Phase-portfolio MDD sampled at trade-exit, NOT a daily marked-to-market max drawdown"},
       "models":[]}
    for h in HORIZONS:
        for t in THRESHOLDS:
            out["models"].append(run_model(dates,picks,prices,risk,night,f"SPOT_{t}",h))
            if t>=50 and night:out["models"].append(run_model(dates,picks,prices,risk,night,f"TX_{t}",h))
        print("FINISHED HORIZON",h,flush=True)
    fn=OUT/"summary.json"
    fn.write_text(json.dumps({k:([dict((kk,vv) for kk,vv in m.items() if kk not in ("trades","phasePortfolio")) for m in v] if k=="models" else v) for k,v in out.items()},ensure_ascii=False,indent=2),encoding="utf-8")
    full=OUT/"trades.json";full.write_text(json.dumps({"period":out["period"],"models":out["models"]},ensure_ascii=False),encoding="utf-8")
    print("G_THREE_YEAR_DONE",json.dumps({"sessions":len(dates),"Gdays":audit["validGSignalDays"],"riskDays":len(risk),"txDays":out["txNightCoverage"],"elapsedSec":round(time.time()-stamp)},ensure_ascii=False),flush=True)
    for m in out["models"]:
        if m["horizon"]==10:print("TEN_DAY",m["model"],"trades",m["executedSignals"],"win",m["netSignal"]["winPct"],"meanPhase",m["meanPhaseReturnPct"],"worstMDDexit",m["worstPhaseExitMDDPct"],flush=True)
if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--start",default=START);p.add_argument("--end",default=END)
    p.add_argument("--skip-tx",action="store_true");p.add_argument("--workers",type=int,default=7);a=p.parse_args()
    main(a.start,a.end,a.skip_tx)
