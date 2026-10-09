"""00675L daily causal walk-forward research: 2024-25 exploration, 2026 held-out audit.
2026-10-08 completed close is now published; rerun the frozen rank without tuning 2026.
Never pick parameters using 2026. Strict signal on completed close, next trading OPEN execution.
Research only; does not alter deployed G scanner or Bottom/Top Pine indicator.
"""
from __future__ import annotations
import math,json,time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import pandas as pd,numpy as np
from config import DATA_DIR
from yahoo_cache import update_symbol
SYMBOL="00675L.TW";INDEX="^TWII";DATE_START="2024-01-01";TRAIN_END="2025-12-31";TEST_START="2026-01-01";TEST_END="2026-10-08"
CAPITAL=1_000_000;BROKER=.001425;ETF_SELL_TAX=.001;SLIP=.001
OUT=DATA_DIR/"research/etf_00675l_2024_2026"
def rsi(s,n):
    delta=s.diff();g=delta.clip(lower=0).ewm(alpha=1/n,adjust=False,min_periods=n).mean()
    l=(-delta.clip(upper=0)).ewm(alpha=1/n,adjust=False,min_periods=n).mean()
    rs=g/l.replace(0,np.nan)
    return (100-100/(1+rs)).fillna(100)
def data_prepare(etf,idx):
    a=etf.copy();b=idx.copy()
    for frame in [a,b]:
        frame["date"]=frame["date"].astype(str)
        for key in ("open","high","low","close","adjclose","volume"):
            frame[key]=pd.to_numeric(frame[key],errors="coerce")
        frame.dropna(subset=["open","high","low","close"],inplace=True)
        frame.sort_values("date",inplace=True)
        frame.drop_duplicates("date",keep="last",inplace=True)
    if len(a)<500:raise RuntimeError("00675L history too short: "+str(len(a)))
    ratios=(a["adjclose"]/a["close"]).replace([np.inf,-np.inf],np.nan)
    # Yahoo normalized close generally already includes split ratio. A factor in adjclose is used consistently
    # across all OHLC so indicator and executable prices always share one corporate-action basis.
    a["factor"]=ratios.fillna(1.0)
    if ((a["factor"]<=0)|(a["factor"]>100)|(a["factor"]<.01)).any():raise RuntimeError("Unusable adjustment factor")
    for key in ("open","high","low","close"):a[key]=a[key]*a["factor"]
    an=a[["date","open","high","low","close","volume","factor"]]
    bn=b[["date","close"]].rename(columns={"close":"twii"})
    d=an.merge(bn,on="date",how="inner").sort_values("date").reset_index(drop=True)
    d=d[d.date<=TEST_END].reset_index(drop=True)
    if d.empty or d.iloc[-1]["date"]<"2026-09-30":raise RuntimeError("2026 data insufficient, last="+(str(d.iloc[-1]["date"]) if len(d) else "none"))
    if len(d[d.date.between("2024-01-01","2025-12-31")])<450:raise RuntimeError("2024-25 training history incomplete")
    if len(d[d.date.between(TEST_START,TEST_END)])<170:raise RuntimeError("2026 OOS history incomplete")
    d["ema10"]=d.close.ewm(span=10,adjust=False,min_periods=10).mean()
    for n in [5,10,20,60,120]:
        d[f"sma{n}"]=d.close.rolling(n,min_periods=n).mean()
        if n in (20,60):d[f"twii_ma{n}"]=d.twii.rolling(n,min_periods=n).mean()
    d["rsi2"]=rsi(d.close,2);d["rsi5"]=rsi(d.close,5);d["rsi14"]=rsi(d.close,14)
    d["high20"]=d.high.shift(1).rolling(20).max()
    d["high40"]=d.high.shift(1).rolling(40).max()
    d["d2"]=d.close.pct_change(2)
    std=d.close.rolling(20).std()
    d["band15"]=d.sma20-1.5*std;d["band20"]=d.sma20-2.0*std
    d["sma20_up"]=d.sma20>d.sma20.shift(5)
    d["twii_above20"]=d.twii>d.twii_ma20
    d["twii_above60"]=d.twii>d.twii_ma60
    changes=(d.close/d.close.shift(1)-1).dropna()
    if (changes.abs()>.60).any():raise RuntimeError("Corporate action / uncorrected 60% price jump detected")
    d["d3"]=d.close.pct_change(3)
    d["ema20"]=d.close.ewm(span=20,adjust=False,min_periods=20).mean()
    d["ema40"]=d.close.ewm(span=40,adjust=False,min_periods=40).mean()
    d["atr14"]=pd.concat([d.high-d.low,(d.high-d.close.shift()).abs(),(d.low-d.close.shift()).abs()],axis=1).max(axis=1).ewm(alpha=1/14,adjust=False,min_periods=14).mean()
    d["high60"]=d.high.shift(1).rolling(60).max()
    d["sma10_up"]=d.sma10>d.sma10.shift(5)
    return d
def configurations():
    a=[{"id":"BUY_HOLD","family":"buy_hold"}]
    for src in ("twii","etf"):
        for n in (20,60):
            for stop in (.10,.15):
                a.append({"id":f"TREND_{src}{n}_SL{int(stop*100)}","family":"trend","source":src,"n":n,"sl":stop})
    for gate in ("twii60","twii20"):
        for threshold in (10,20,30):
            for tp in (.03,.05,.08):
                for sl in (.08,.10):
                    a.append({"id":f"RSI2_PULL_{gate}_{threshold}_TP{int(tp*100)}_SL{int(sl*100)}",
                        "family":"pullback","gate":gate,"rsi":threshold,"tp":tp,"sl":sl,"hold":10})
    for gate in ("all","twii60"):
        for threshold in (5,15):
            for tp in (.03,.05,.08):
                for sl in (.08,.12):
                    a.append({"id":f"RSI2_SHOCK_{gate}_{threshold}_TP{int(tp*100)}_SL{int(sl*100)}",
                        "family":"shock","gate":gate,"rsi":threshold,"tp":tp,"sl":sl,"hold":7})
    for length in (20,40):
        for trail in (.08,.12):
            for sl in (.10,.15):
                a.append({"id":f"BREAKOUT_{length}_TRAIL{int(trail*100)}_SL{int(sl*100)}",
                    "family":"breakout","lookback":length,"sl":sl,"trail":trail,"hold":45})
    for width in (15,20):
        for tp in (.05,.10):
            a.append({"id":f"BB_PULL_{width}_TP{int(tp*100)}","family":"band","width":width,
                "tp":tp,"sl":.10,"hold":10})
    for d2 in (-.03,-.05):
        for tp in (.03,.05):
            a.append({"id":f"2DAY_DIVE_{int(abs(d2)*100)}_TP{int(tp*100)}","family":"dip",
                "dip":d2,"tp":tp,"sl":.10,"hold":10})
    return a
def ok_value(v):return bool(pd.notna(v))
def signal(p,q,c):
    fam=c["family"]
    if fam in ("swing_rsi","swing_dip","swing_band","swing_reclaim","swing_trend","swing_breakout","swing_atr"):
        gate=c.get("gate","all")
        healthy=(gate=="all" or
            (gate=="twii20" and bool(p.twii_above20)) or
            (gate=="twii60" and bool(p.twii_above60)) or
            (gate=="etf60" and ok_value(p.sma60) and p.close>p.sma60))
        if fam=="swing_rsi":
            field="rsi"+str(c["rsi_n"])
            return bool(healthy and ok_value(p[field]) and ok_value(q[field]) and p[field]<c["threshold"] and q[field]>=c["threshold"]),bool(p.rsi5>c.get("exit_rsi",80))
        if fam=="swing_dip":
            field="d"+str(c["days"])
            return bool(healthy and ok_value(p[field]) and ok_value(q[field]) and p[field]<c["threshold"] and q[field]>=c["threshold"]),bool(p.close>p.ema10 and p.rsi5>80)
        if fam=="swing_band":
            field="band"+str(c["band"])
            return bool(healthy and ok_value(p[field]) and ok_value(q[field]) and p.close<p[field] and q.close>=q[field]),bool(p.close>p.ema10 and p.rsi5>85)
        if fam=="swing_reclaim":
            fld="ema"+str(c["length"])
            return bool(healthy and ok_value(p[fld]) and ok_value(q[fld]) and p.close>p[fld] and q.close<=q[fld]),bool(p.close<p[fld] and p.close<p.sma20)
        if fam=="swing_trend":
            n=c["length"];fld=("twii_ma"+str(n) if c["source"]=="twii" else "sma"+str(n));val="twii" if c["source"]=="twii" else "close"
            return bool(healthy and ok_value(p[fld]) and ok_value(q[fld]) and p[val]>p[fld] and q[val]<=q[fld]),bool(p[val]<p[fld])
        if fam=="swing_breakout":
            fld="high"+str(c["length"])
            return bool(healthy and ok_value(p[fld]) and p.close>p[fld] and q.close<=q[fld]),bool(p.close<p.ema10)
        if fam=="swing_atr":
            # Enter after pullback in rising trend when ETF recovers yesterday's EMA10, stop ATR-based.
            return bool(healthy and p.close>p.ema10 and q.close<=q.ema10 and p.sma20_up),bool(p.close<p.sma20)
    if fam=="buy_hold":return False,False
    if fam=="trend":
        n=c["n"];field=("twii" if c["source"]=="twii" else "close")
        avg=("twii_ma"+str(n) if c["source"]=="twii" else "sma"+str(n))
        if not all(ok_value(z[avg]) for z in [p,q]):return False,False
        # Separate index-trend from ETF-trend, no extra indicator threshold tuned on test.
        enter=(p[field]>p[avg] and q[field]<=q[avg])
        if c["source"]=="etf":enter=enter and p["twii_above60"]
        leave=p[field]<p[avg]
        return enter,leave
    if fam in ("pullback","shock"):
        if not (ok_value(p.rsi2) and ok_value(q.rsi2)):return False,False
        gate=c["gate"];healthy=(gate=="all" or (gate=="twii60" and p.twii_above60) or (gate=="twii20" and p.twii_above20))
        if fam=="pullback":healthy=healthy and ok_value(p.sma60) and p.close>p.sma60
        enter=bool(healthy and p.rsi2<c["rsi"] and q.rsi2>=c["rsi"])
        exit_=bool(p.rsi2>70)
        return enter,exit_
    if fam=="breakout":
        highcol="high"+str(c["lookback"])
        if not all(ok_value(z[highcol]) for z in (p,q)):return False,False
        enter=bool(p.twii_above60 and p.close>p[highcol] and q.close<=q[highcol])
        return enter,bool(p.close<p.sma20)
    if fam=="band":
        band="band"+str(c["width"])
        if not all(ok_value(z[band]) for z in (p,q)):return False,False
        enter=bool(p.twii_above60 and p.close<p[band] and q.close>=q[band])
        return enter,bool(p.close>=p.sma20)
    if fam=="dip":
        if not all(ok_value(z.d2) for z in (p,q)):return False,False
        enter=bool(p.twii_above60 and p.close>p.sma60 and p.d2<c["dip"] and q.d2>=c["dip"])
        return enter,bool(p.close>p.ema10)
    raise RuntimeError("Unknown family "+fam)
def simulate(d,c,begin,end,trade_details=False):
    x=d.index[d.date.between(begin,end)].tolist()
    if len(x)<20:raise RuntimeError("Insufficient dates "+begin+" .. "+end)
    cash=float(CAPITAL);qty=0;entry_px=0;entry_cost=0;entry_at=-1;peakclose=0;equities=[];trades=[]
    # exit_signal for last closed day, not contemporary close. A single position at any time.
    for kk,i in enumerate(x):
        bar=d.iloc[i];date=bar.date
        o,h,l,close=(float(bar[z]) for z in ("open","high","low","close"))
        p=d.iloc[i-1] if i>=1 else None;q=d.iloc[i-2] if i>=2 else None
        buy_sig,sell_sig=signal(p,q,c) if p is not None and q is not None else (False,False)
        if c["family"]=="buy_hold":buy_sig=kk==0;sell_sig=False
        closed_today=False;opened_today=False
        def sell(gross_px,reason):
            nonlocal qty,cash,entry_px,entry_cost,entry_at,peakclose,closed_today
            px=max(0.01,gross_px*(1-SLIP));proceeds=qty*px*(1-BROKER-ETF_SELL_TAX)
            cash+=proceeds
            net=100*(proceeds/entry_cost-1)
            trades.append({"buyDate":str(d.iloc[entry_at].date),"sellDate":date,"buyPx":round(entry_px,3),
                  "sellPx":round(px,3),"holdingDays":i-entry_at+1,"reason":reason,
                  "netPct":round(net,3),"netNTD":round(proceeds-entry_cost,2)})
            qty=0;entry_px=0;entry_cost=0;entry_at=-1;peakclose=0;closed_today=True
        if qty:
            sl=float(c.get("sl",0))
            stop=entry_px*(1-sl) if sl>0 else 0
            if c.get("atr_stop_mult") and entry_at>=1:
                v=float(d.iloc[entry_at-1].atr14)
                if math.isfinite(v):stop=max(stop,entry_px-c["atr_stop_mult"]*v)
            if c.get("trail"):stop=max(stop,peakclose*(1-c["trail"]))
            if c.get("atr_trail_mult") and p is not None and math.isfinite(float(p.atr14)):
                stop=max(stop,peakclose-c["atr_trail_mult"]*float(p.atr14))
            target=entry_px*(1+c["tp"]) if c.get("tp") else None
            if o<=stop and stop>0:sell(o,"gap_stop")
            elif sell_sig:sell(o,"indicator_exit")
            elif target and o>=target:sell(o,"gap_target")
            elif stop>0 and l<=stop:sell(stop,"stop")
            elif target and h>=target:sell(target,"target")
            elif c.get("hold") and i-entry_at+1>=c["hold"]:sell(close,"time_exit")
        if not qty and not closed_today and buy_sig:
            paid_px=o*(1+SLIP)
            number=math.floor(cash/(paid_px*(1+BROKER)))
            if number>0:
                total=number*paid_px*(1+BROKER)
                cash-=total;qty=number;entry_px=paid_px;entry_cost=total;entry_at=i;peakclose=paid_px;opened_today=True
                # Newly opened intraday path unknown; conservatively honor same-day downside,
                # never a positive TP on day of entry.
                sl=float(c.get("sl",0))
                if sl>0 and l<=paid_px*(1-sl):sell(paid_px*(1-sl),"entry_day_stop")
        if qty and not opened_today:peakclose=max(peakclose,close)
        marked=cash+(qty*close*(1-SLIP)*(1-BROKER-ETF_SELL_TAX) if qty else 0)
        equities.append({"date":date,"equity":round(marked,2),"held":bool(qty)})
    if qty:
        last=d.iloc[x[-1]]
        sell(float(last.close),"period_end")
        equities[-1]["equity"]=round(cash,2);equities[-1]["held"]=False
    vals=np.array([e["equity"] for e in equities],dtype=float)
    mx=np.maximum.accumulate(np.r_[CAPITAL,vals])[1:]
    maxdd=float(np.min(100*(vals/mx-1)))
    gain=100*(cash/CAPITAL-1)
    wins=sum(t["netPct"]>0 for t in trades)
    avgnet=float(np.mean([t["netPct"] for t in trades])) if trades else 0
    pf=(sum(max(t["netNTD"],0) for t in trades)/-sum(min(t["netNTD"],0) for t in trades)) if any(t["netNTD"]<0 for t in trades) else None
    return {"start":str(d.iloc[x[0]].date),"end":str(d.iloc[x[-1]].date),
            "returnPct":round(gain,3),"maxDrawdownPct":round(maxdd,3),
            "trades":len(trades),"winPct":round(wins/len(trades)*100,2) if trades else None,
            "avgNetPerTradePct":round(avgnet,3),"profitFactor":round(pf,3) if pf is not None else None,
            "avgHoldingDays":round(float(np.mean([t["holdingDays"] for t in trades])),2) if trades else None,
            "investedDays":sum(e["held"] for e in equities),"sessions":len(x),
            **({"events":trades,"dailyEquity":equities} if trade_details else {})}
def snapshot(d):
    x=d[(d.date>=DATE_START)&(d.date<=TRAIN_END)].copy()
    x["forward3"]=x.close.shift(-3)/x.close-1
    samples={}
    for key,cond in [("all",x.rsi2>=0),("rsi2_lt10",x.rsi2<10),("rsi2_lt20",x.rsi2<20),
           ("index_above_ma60",x.twii_above60),("index_below_ma60",~x.twii_above60),
           ("dip2_over5pct",x.d2<-.05)]:
        f=x.loc[cond,"forward3"].dropna()
        samples[key]={"count":len(f),"next3dAvgPct":round(float(f.mean()*100),3) if len(f) else None,
                      "next3dPositivePct":round(float((f>0).mean()*100),2) if len(f) else None}
    return samples

BASELINE_IDS=("BUY_HOLD","TREND_twii60_SL10","TREND_etf20_SL10","BREAKOUT_40_TRAIL12_SL10","2DAY_DIVE_3_TP3")
TRAIN_BEGIN="2024-01-01";TRAIN_END="2025-12-31";TEST_BEGIN="2026-01-01";TEST_END="2026-10-08"
OUT_GRID=DATA_DIR/"research/etf_00675l_grid_2024_2026"
def grid():
    all_conf=configurations()
    for rsi_n,levels in ((2,(5,10,20)),(5,(20,30))):
        for th in levels:
            for gate in ("all","twii20","twii60"):
                for tp in (.03,.05,.08):
                    for sl in (.07,.10):
                        for hold in (5,10):
                            all_conf.append({"id":f"RSI{rsi_n}_{th}_{gate}_TP{tp}_SL{sl}_H{hold}",
                              "family":"swing_rsi","rsi_n":rsi_n,"threshold":th,"gate":gate,
                              "tp":tp,"sl":sl,"hold":hold,"exit_rsi":80})
    for days,thresholds in ((2,(-.03,-.05,-.07)),(3,(-.05,-.08))):
        for th in thresholds:
            for gate in ("all","twii20","twii60"):
                for tp in (.03,.05,.08):
                    for sl in (.07,.10):
                        for hold in (5,10):
                            all_conf.append({"id":f"DIP{days}_{th}_{gate}_TP{tp}_SL{sl}_H{hold}",
                                 "family":"swing_dip","days":days,"threshold":th,"gate":gate,
                                 "tp":tp,"sl":sl,"hold":hold})
    for band in (15,20):
        for gate in ("all","twii20","twii60"):
            for tp in (.03,.05,.08):
                for sl in (.07,.10):
                    for hold in (5,10):
                        all_conf.append({"id":f"BB{band}_{gate}_TP{tp}_SL{sl}_H{hold}","family":"swing_band",
                                         "band":band,"gate":gate,"tp":tp,"sl":sl,"hold":hold})
    for length in (10,20,40):
        for gate in ("twii20","twii60","etf60"):
            for tp in (.05,.10):
                for sl in (.07,.10):
                    for hold in (10,20):
                        all_conf.append({"id":f"RECLAIM_EMA{length}_{gate}_TP{tp}_SL{sl}_H{hold}",
                        "family":"swing_reclaim","length":length,"gate":gate,"tp":tp,"sl":sl,"hold":hold})
    for source in ("twii","etf"):
        for length in (20,60):
            for tp in (0,.10):
                for sl in (.08,.12):
                    for trail in (0,.08,.12):
                        all_conf.append({"id":f"TREND_{source}{length}_TP{tp}_SL{sl}_TR{trail}",
                            "family":"swing_trend","source":source,"length":length,"gate":"all","tp":tp,"sl":sl,
                            "trail":trail,"hold":45})
    for length in (20,40,60):
        for gate in ("twii20","twii60"):
            for trail in (.06,.10):
                for sl in (.08,.12):
                    for tp in (0,.15):
                        all_conf.append({"id":f"BO_{length}_{gate}_TP{tp}_SL{sl}_TR{trail}",
                        "family":"swing_breakout","length":length,"gate":gate,"sl":sl,"tp":tp,"trail":trail,"hold":30})
    for gate in ("twii20","twii60","etf60"):
        for atr_stop in (1.5,2.5,3.5):
            for atr_trail in (2,3):
                for tp in (.05,.10,0):
                    all_conf.append({"id":f"ATR_{gate}_STOP{atr_stop}_TR{atr_trail}_TP{tp}",
                       "family":"swing_atr","gate":gate,"atr_stop_mult":atr_stop,"atr_trail_mult":atr_trail,
                       "sl":.12,"tp":tp,"hold":25})
    seen=set();unique=[]
    for c in all_conf:
        if c["id"] in seen:raise AssertionError("Duplicate "+c["id"])
        seen.add(c["id"]);unique.append(c)
    return unique
def compact(z):
    return {k:z.get(k) for k in ("returnPct","maxDrawdownPct","trades","winPct","avgNetPerTradePct","profitFactor","avgHoldingDays","investedDays","sessions")}
def risk_measure(z):
    # Reject unusually sparse patterns and high drawdown, reward both calendar years.
    if z["trades"]<4:return -999
    return z["returnPct"] - .7*abs(z["maxDrawdownPct"])
def robust_score(y24,y25,combined):
    # 2024+2025 ONLY, robustness over returns from both calendar years, hold penalty and cash drag included.
    worst=min(y24["returnPct"],y25["returnPct"])
    draw=max(abs(y24["maxDrawdownPct"]),abs(y25["maxDrawdownPct"]))
    return round(.35*(y24["returnPct"]+y25["returnPct"])+.3*worst-.7*draw,4)
def report_regime_perf(d,rule):
    # OOS-only reporting slices, DO NOT tune hyperparams on these slices
    cuts=[("26Q1","2026-01-01","2026-03-31"),("26Q2","2026-04-01","2026-06-30"),
          ("26Q3","2026-07-01","2026-09-30"),("26Oct","2026-10-01",TEST_END)]
    return {name:compact(simulate(d,rule,start,end)) for name,start,end in cuts if sum(d.date.between(start,end))>=20}
def main():
    start=time.time();_,etf,err=update_symbol(SYMBOL,datetime(2023,5,1),datetime(2026,10,9))
    _,index,e2=update_symbol(INDEX,datetime(2023,5,1),datetime(2026,10,9))
    if err or e2 or etf is None or index is None or etf.empty or index.empty:raise RuntimeError(str({"etf":err,"twii":e2}))
    d=data_prepare(etf,index)
    cases=grid();train_records=[]
    print("00675L_GRID_RUN "+json.dumps({"cases":len(cases),"from":str(d.iloc[0].date),"through":str(d.iloc[-1].date),
      "train2024":int(sum(d.date.str.startswith("2024"))),"train2025":int(sum(d.date.str.startswith("2025"))),
      "2026":int(sum(d.date.str.startswith("2026")))}),flush=True)
    for n,c in enumerate(cases):
        y24=simulate(d,c,"2024-01-01","2024-12-31")
        y25=simulate(d,c,"2025-01-01","2025-12-31")
        # Do not look at 2026 prior to freeze of ranked candidates.
        eligible=c["family"]!="buy_hold" and y24["trades"]>=3 and y25["trades"]>=3
        score=robust_score(y24,y25,None) if eligible else None
        train_records.append({"id":c["id"],"family":c["family"],"params":c,"2024":compact(y24),
                              "2025":compact(y25),"eligible":eligible,"score":score})
        if (n+1)%200==0:print("00675L_GRID_TRAINED",n+1,"/",len(cases),flush=True)
    eligible=sorted((z for z in train_records if z["eligible"]),key=lambda z:(-z["score"],z["id"]))
    best={}
    for z in eligible:
        fam=z["family"]
        if fam not in best:best[fam]=[]
        if len(best[fam])<2 and not any(all(z["params"].get(k)==v["params"].get(k) for k in ("tp","sl","hold","trail")) for v in best[fam]):
            best[fam].append(z)
    selected_ids=[]
    for name in BASELINE_IDS+tuple(z["id"] for family in best.values() for z in family):
        if name not in selected_ids:selected_ids.append(name)
    if len(selected_ids)<10:raise RuntimeError("Insufficient OOS diversity")
    by_id={x["id"]:x for x in train_records}
    testing=[]
    for name in selected_ids:
        c=by_id[name]["params"]
        oos=simulate(d,c,TEST_BEGIN,TEST_END,trade_details=True)
        testing.append({"id":name,"family":c["family"],"params":c,"2024":by_id[name]["2024"],
             "2025":by_id[name]["2025"],"trainScore":by_id[name]["score"],
             "2026":compact(oos),"2026Regimes":report_regime_perf(d,c),
             "events":oos["events"],"dailyEquity":oos["dailyEquity"]})
        print("00675L_GRID_TEST "+json.dumps({"name":name,"trainScore":by_id[name]["score"],
           "2024Net":by_id[name]["2024"]["returnPct"],"2025Net":by_id[name]["2025"]["returnPct"],
           "2026Net":oos["returnPct"],"2026MaxDD":oos["maxDrawdownPct"],
           "trades":oos["trades"],"winPct":oos["winPct"]},ensure_ascii=False),flush=True)
    all_train=[z for z in train_records if z["eligible"]]
    by_family={}
    for z in train_records:
        fam=z["family"];s=by_family.setdefault(fam,{"tested":0,"eligible":0,"trainPositiveBoth":0,"trainScorePositive":0})
        s["tested"]+=1
        if z["eligible"]:
            s["eligible"]+=1
            if z["2024"]["returnPct"]>0 and z["2025"]["returnPct"]>0:s["trainPositiveBoth"]+=1
            if z["score"]>0:s["trainScorePositive"]+=1
    winner=eligible[0] if eligible else None
    report={"version":"00675L_EXTENDED_SWING_GRID_2024_2026_V1",
        "generatedAt":datetime.now(ZoneInfo("Asia/Taipei")).isoformat(timespec="seconds"),
        "ticker":SYMBOL,"name":"富邦臺灣加權正2",
        "dataStart":str(d.iloc[0].date),"dataEnd":str(d.iloc[-1].date),
        "periods":{"development":"2024-01-01 .. 2024-12-31","stabilityCheck":"2025-01-01 .. 2025-12-31",
                   "frozenValidation":"2026-01-01 .. 2026-10-08 (actually available through dataEnd)"},
        "universe":{"total":len(cases),"eligible":len(eligible),"familyBreakdown":by_family},
        "procedure":{"rankingOnlyUses":"calendar years 2024 and 2025; 2026 outcomes read only for frozen selected candidates",
                     "minTradesEachYear":3,
                     "rankingFormula":"0.35*(2024%+2025%) + 0.30*min(2024%,2025%) - 0.70*max(abs(2024 max DD), abs(2025 max DD))",
                     "selection":"precommitted five baselines plus top two variants by 2024/25 train score in each signal family",
                     "position":"All-in cash, integer units, one long position at time",
                     "signals":"completed session T only; trade next OPEN",
                     "exits":"stop before intrabar take profit; if open gaps past target, exit OPEN; no profitable same-day exit after entry",
                     "costs":{"buyBrokerPct":BROKER*100,"sellBrokerPct":BROKER*100,"sellTaxPct":ETF_SELL_TAX*100,
                              "slippagePerSidePct":SLIP*100},
                     "cashNTD":CAPITAL},
        "trainBest":None if winner is None else {"id":winner["id"],"family":winner["family"],"score":winner["score"],
                         "2024":winner["2024"],"2025":winner["2025"],"params":winner["params"]},
        "familyWinners":{fam:[{"id":z["id"],"score":z["score"],"2024":z["2024"],"2025":z["2025"]} for z in zlist] for fam,zlist in best.items()},
        "trainTop30":[{"id":z["id"],"family":z["family"],"score":z["score"],"2024":z["2024"],"2025":z["2025"]} for z in eligible[:30]],
        "validation":[{key:z[key] for key in ("id","family","params","2024","2025","trainScore","2026","2026Regimes")} for z in testing],
        "warnings":[
          "Repeated research of 2026 by prior experiments means it is NOT truly pristine researcher-level holdout, even though this script never ranks on 2026.",
          "Hundreds of related parameter combinations have multiple-testing / data-snooping bias, despite robust 2024/25 scoring.",
          "ETF daily 2x reset creates compounding and drawdown risk; BUY_HOLD may outperform swing traders in trending markets.",
          "Daily OHLC is insufficient to test a 2-minute Bottom/Top signal. Intraday stop-profit order uses conservative assumptions.",
          "The whole-account paper strategy assumes full capital invested in one ETF position at a time; no partial fills, margin or intraday funding constraints.",
          "Adjustment factors use Yahoo daily data, not broker fill confirmations. Commission minimum, ETF premium-discount and financing omitted.",
          "Selecting winners based on 2026 rankings after inspecting test results would invalidate any independence claims.",
          "Backtested risk and performance do not guarantee future outcomes."],
        "elapsedSeconds":round(time.time()-start,1)}
    OUT_GRID.mkdir(parents=True,exist_ok=True)
    (OUT_GRID/"summary.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    (OUT_GRID/"oos_trades_and_equity.json").write_text(json.dumps({"version":report["version"],"frozenCandidates":testing},ensure_ascii=False),encoding="utf-8")
    (OUT_GRID/"all_train_variants.json").write_text(json.dumps({"version":report["version"],"training":train_records},ensure_ascii=False),encoding="utf-8")
    print("00675L_GRID_COMPLETE "+json.dumps({"all":len(cases),"eligible":len(eligible),"winner":winner["id"] if winner else None,
       "selected":len(testing),"elapsed":report["elapsedSeconds"]}),flush=True)
if __name__=="__main__":main()
