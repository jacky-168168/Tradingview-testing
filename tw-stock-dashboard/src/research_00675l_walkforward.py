"""00675L daily causal walk-forward research: 2024-25 exploration, 2026 held-out audit.
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
            if c.get("trail"):stop=max(stop,peakclose*(1-c["trail"]))
            target=entry_px*(1+c["tp"]) if c.get("tp") else None
            if o<=stop and stop>0:sell(o,"gap_stop")
            elif sell_sig:sell(o,"indicator_exit")
            elif stop>0 and l<=stop:sell(stop,"stop")
            elif target and o>=target:sell(o,"gap_target")
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
def main():
    begun=time.time();start=datetime(2023,5,1);end=datetime(2026,10,9)
    _,a,ae=update_symbol(SYMBOL,start,end)
    _,b,be=update_symbol(INDEX,start,end)
    if ae or be or a is None or b is None or a.empty or b.empty:raise RuntimeError("History failed "+str({"etf":ae,"index":be}))
    d=data_prepare(a,b);print("00675L DATA",json.dumps({"rows":len(d),"first":d.iloc[0].date,"last":d.iloc[-1].date,
          "y2024":len(d[d.date.str.startswith("2024")]),"y2025":len(d[d.date.str.startswith("2025")]),
          "y2026":len(d[d.date.str.startswith("2026")]),
          "startClose":round(float(d.iloc[0].close),3),"endClose":round(float(d.iloc[-1].close),3),
          "adjustFactors":sorted(set(round(float(v),6) for v in d.factor))[:15]},ensure_ascii=False),flush=True)
    configs=configurations();training=[]
    hold_train=simulate(d,configs[0],DATE_START,TRAIN_END)
    for conf in configs:
        both=simulate(d,conf,DATE_START,TRAIN_END)
        y24=simulate(d,conf,"2024-01-01","2024-12-31")
        y25=simulate(d,conf,"2025-01-01","2025-12-31")
        # No out-of-sample 2026 access. Penalize concentrated winnings and deep drawdowns.
        score=both["returnPct"]-.8*abs(both["maxDrawdownPct"])+.25*min(y24["returnPct"],y25["returnPct"])
        eligible=(conf["family"]!="buy_hold" and both["trades"]>=8 and y24["trades"]>=2 and y25["trades"]>=2)
        training.append({"id":conf["id"],"params":conf,"train":both,"y2024":y24,
          "y2025":y25,"score":round(score,4),"eligible":eligible})
    sorted_train=sorted([x for x in training if x["eligible"]],key=lambda x:(-x["score"],-x["train"]["trades"],x["id"]))
    if not sorted_train:raise RuntimeError("No eligible candidate matched precommitted thresholds")
    # Only THEN inspect 2026, never select based on test outcomes.
    selected=sorted_train[:5];fixed=["BUY_HOLD","TREND_twii60_SL10","TREND_etf20_SL10"]
    ids=list(dict.fromkeys(fixed+[x["id"] for x in selected]))
    byid={x["id"]:x for x in training}
    verification=[]
    for k in ids:
        train=byid[k]
        y26=simulate(d,train["params"],TEST_START,TEST_END,trade_details=True)
        h1=simulate(d,train["params"],"2026-01-01","2026-06-30")
        h2=simulate(d,train["params"],"2026-07-01",TEST_END)
        verification.append({"id":k,"trainScore":train["score"],"train":train["train"],
             "y2024":train["y2024"],"y2025":train["y2025"],"test2026":{z:v for z,v in y26.items() if z not in ("events","dailyEquity")},
             "testH1":h1,"testH2":h2,"events":y26["events"],"equity":y26["dailyEquity"]})
        print("00675L_OOS_CASE "+json.dumps({"name":k,"trainReturn":train["train"]["returnPct"],
          "trainMDD":train["train"]["maxDrawdownPct"],"2026Return":y26["returnPct"],
          "2026MDD":y26["maxDrawdownPct"],"trades":y26["trades"],"win":y26["winPct"],
          "h1":h1["returnPct"],"h2":h2["returnPct"]},ensure_ascii=False),flush=True)
    winner=selected[0]["id"]
    outcome=next(v for v in verification if v["id"]==winner)
    result={"version":"00675L_2024_25_TRAIN_2026_FORWARD_1",
       "generatedAt":datetime.now(ZoneInfo("Asia/Taipei")).isoformat(timespec="seconds"),
       "ticker":SYMBOL,"securityName":"富邦臺灣加權正2",
       "trainingPeriod":{"start":"2024-01-01","end":"2025-12-31"},"outOfSamplePeriod":{"start":TEST_START,"end":TEST_END},
       "actualDataEnd":str(d.iloc[-1].date),
       "data":{"source":"Yahoo Finance via repo daily OHLC and TWII, adjusted price basis applied consistently",
              "rows":len(d),"etfRawRows":len(a),"indexRawRows":len(b),
              "trainingBars":len(d[d.date.between(DATE_START,TRAIN_END)]),
              "testingBars":len(d[d.date.between(TEST_START,TEST_END)]),
              "etfAdjustedCloseStartTrain":round(float(d.loc[d.date>=DATE_START,"close"].iloc[0]),3),
              "etfAdjustedCloseLast":round(float(d.iloc[-1].close),3),
              "adjustmentFactorFirst":round(float(d.iloc[0].factor),6),
              "adjustmentFactorLast":round(float(d.iloc[-1].factor),6)},
       "costs":{"brokerEachSidePct":BROKER*100,"slippageEachSidePct":SLIP*100,"etfSaleTaxPct":ETF_SELL_TAX*100,
                "startingCapitalNTD":CAPITAL,"unit":"one ETF certificate share, integer units","leverage":"fund 2x but no margin borrowing by account"},
       "execution":{"signal":"completed close of session T","entry":"next session T+1 open",
                   "exit":"next session open if completed prior-day exit signal; daily low triggers stop and high triggers TP; stop first",
                   "gap":"open price if crossed exit stop/target","sameBar":"stop may hit day of first entry but cannot hit take-profit day of entry",
                   "capital":"all available cash each trade; one position max; no financing",
                   "trainSelection":"2024+2025 total net% -0.8*absolute maxDD% +0.25*min(2024 return, 2025 return); trade N>=8 and each year >=2",
                   "oos":"top five TRAIN scores and 3 precommitted baselines only; 2026 never used for choice"},
       "candidateCount":len(configs),"eligibleCount":len(sorted_train),
       "trainContext":snapshot(d),
       "trainTop10":[{"id":x["id"],"params":x["params"],"train":x["train"],"y2024":x["y2024"],"y2025":x["y2025"],
                      "score":x["score"]} for x in sorted_train[:10]],
       "selectedTrainingWinner":winner,
       "holdTrain":hold_train,"validation":[{k:v for k,v in z.items() if k not in ("events","equity")} for z in verification],
       "warnings":[
         "2026 was held out for this specific parameter ranking, but strategy family design was still informed by general historical ETF behavior; further forward validation is necessary.",
         "Daily OHLC cannot identify intraday order sequence. Stop is prioritized and no same-day positive take profit after entry.",
         "Yahoo adjusted OHLC factor and stock-exchange historical unadjusted fills may differ, especially if future distributions/corporate actions occur.",
         "No leverage in cash account beyond ETF's inherent daily 2x benchmark reset; fund incurs volatility compounding and path dependency.",
         "Integer ETF units and fixed full-commission rates; no discount, broker minimum fee or real order-book liquidity/price impact.",
         "Small 2026 independent verification period, dominated by distinct market regimes; no promise of future excess returns.",
         "NOT a verified 2-minute Bottom/Top execution backtest."
       ],"elapsedSeconds":round(time.time()-begun,1)}
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/"summary.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    (OUT/"selected_trades_equity.json").write_text(json.dumps({"version":result["version"],"selected":verification},ensure_ascii=False),encoding="utf-8")
    print("00675L_WALK_FORWARD_DONE "+json.dumps({"trainCandidates":len(configs),
          "trainEligible":len(sorted_train),"winner":winner,"hold26":next(z["test2026"]["returnPct"] for z in verification if z["id"]=="BUY_HOLD"),
          "winner26":outcome["test2026"]["returnPct"],"winnerMDD":outcome["test2026"]["maxDrawdownPct"],
          "elapsed":result["elapsedSeconds"]},ensure_ascii=False),flush=True)
if __name__=="__main__":main()
