"""2025/01 to 2026/08/31 TXF 2m vs 5m backtest of user-supplied
Extreme_Reversal_Hunter_Trend70.pine (sha256 bf45b473792d1dc656bf8b050f211eef33ce7e64f485c321b98dfa546bf1e3a3).
Pine indicator -> independently translated Python EVENT/transaction backtest.
Input: public research 1-minute TXFR1 near-month continuous futures with daily
session and after-hours, NOT TAIFEX official certified continuous contract data.
2024 is warm-up, fixed parameters only; 2025 and 2026 separately audited.
Signals: Pine bottomEv/topEv with shared 8-bar cooldown, WVF/GVF dynamic rolling
P90/400, ATR14, SMA200 impulse, pressure and time filters; strongBottom=bottomEv
and prior completed daily TrendScore >70. Pivot/divergence/grade only decorate
original signal, not signal predicates. Exit either opposite signal or TP/SL,
PLUS mandatory day-session close liquidation to avoid overnight futures risk.
This is an approximation, not bit-exact TradingView Pine execution. Read README.
"""
from __future__ import annotations
import os,re,json,math,time,sys
from pathlib import Path
from datetime import datetime
import numpy as np,pandas as pd,requests
from zoneinfo import ZoneInfo
from config import DATA_DIR
START="2025-01-02";END="2026-08-31";WARMUP="2024-01-01"
OUT=DATA_DIR/"research/txf_extreme_reversal_2m_5m_2025_2026"
S_URL="https://raw.githubusercontent.com/jason43314-crypto/taiwan-futures-1min-ohlc/main/data_TXFR1_{year}.sql"
COST={"contract":"TXF one large Taiwan index futures contract","pointValueTWD":200,
      "brokerFeeTWDPerSide":60,"simulatedSlippagePointsEachSide":1.0,
      "futuresTransactionTaxNotionalPerSide":.00002,"initialEquityTWD":1_000_000,
      "position":"fixed one TXF lot maximum, no compounding contract lots",
      "exitAtDaySessionClose":True,"marginCallsModeled":False}
def acquire(year):
    dest=Path("/tmp")/f"TXFR1_{year}.sql"
    if not dest.exists():
        with requests.get(S_URL.format(year=year),timeout=120,stream=True) as r:
            r.raise_for_status()
            with dest.open("wb") as f:
                for chunk in r.iter_content(262144):
                    if chunk:f.write(chunk)
    if dest.stat().st_size<4_000_000:raise RuntimeError("Missing/corrupt 1m TXF data "+str(year))
    print("TXF_DOWNLOAD "+json.dumps({"year":year,"bytes":dest.stat().st_size}),flush=True)
    return dest
def sqlbars(year):
    file=acquire(year);heads=None;rows=[];in_copy=False
    with file.open("r",encoding="utf-8-sig",errors="replace") as f:
        for line in f:
            if line.startswith("COPY ") and "FROM stdin" in line:
                m=re.search(r"\(([^)]+)\)\s+FROM\s+stdin",line)
                if not m:raise RuntimeError("Unsupported COPY header: "+line[:220])
                heads=[x.strip().strip('"') for x in m.group(1).split(",")]
                in_copy=True;continue
            if not in_copy:continue
            if line.startswith("\\."):in_copy=False;continue
            vals=line.rstrip("\n").split("\t")
            if len(vals)!=len(heads):continue
            rec=dict(zip(heads,vals))
            if rec.get("product_id") not in ("TXFR1","FITXN*1"):continue
            if rec.get("is_synthetic","f").strip().lower() in ("true","t","1"):continue
            dt=rec.get("datetime")
            if not dt or dt[:4]!=str(year):continue
            try:
                rows.append((dt,rec["trading_date"],float(rec["open"]),float(rec["high"]),
                    float(rec["low"]),float(rec["close"]),float(rec["volume"])))
            except (ValueError,KeyError):continue
    if len(rows)<70_000:raise RuntimeError(f"Too few genuinely traded one-minute TXF 202{year}: {len(rows)}")
    a=pd.DataFrame(rows,columns=["datetime","trading_date","open","high","low","close","volume"])
    a["datetime"]=pd.to_datetime(a.datetime)
    a["trading_date"]=pd.to_datetime(a.trading_date)
    a=a.sort_values("datetime").drop_duplicates("datetime").reset_index(drop=True)
    print("TXF_SOURCE "+json.dumps({"year":year,"n":len(a),"first":str(a.datetime.iloc[0]),"last":str(a.datetime.iloc[-1])}),flush=True)
    return a
def sar(hi,lo): # standard PSAR(0.02,0.02,0.2), clamp to previous two bars
    n=len(hi);s=np.full(n,np.nan);bull=np.full(n,False)
    if n<3:return s,bull
    up=bool(hi[1]+lo[1]>=hi[0]+lo[0]);af=.02
    ep=float(hi[1] if up else lo[1]);s[1]=lo[0] if up else hi[0];bull[1]=up
    for i in range(2,n):
        value=s[i-1]+af*(ep-s[i-1])
        value=min(value,lo[i-1],lo[i-2]) if up else max(value,hi[i-1],hi[i-2])
        reverse=(lo[i]<value) if up else (hi[i]>value)
        if reverse:
            value=ep;up=not up;af=.02;ep=hi[i] if up else lo[i]
        else:
            newer=max(ep,hi[i]) if up else min(ep,lo[i])
            if newer!=ep:ep=newer;af=min(.2,af+.02)
        s[i]=value;bull[i]=up
    return s,bull
def daily_trend(minute):
    # use source trading_date: combines prior evening+following morning/day
    d=minute.groupby("trading_date",sort=True).agg(high=("high","max"),low=("low","min"),
        close=("close","last"),count=("close","size"))
    d=d[d.index>=pd.Timestamp(WARMUP)].copy()
    x=d.close;hi=d.high;lo=d.low
    e20=x.ewm(span=20,adjust=False).mean();e60=x.ewm(span=60,adjust=False).mean()
    v10=(x/x.shift(10)-1)*100
    low20=lo.rolling(20,min_periods=20).min()
    hi20=hi.rolling(20,min_periods=20).max()
    rise=(x/low20-1)*100
    location=((x-low20)/(hi20-low20)*100).where(hi20>low20,50)
    persist=(x>e60).astype(float).rolling(10,min_periods=10).mean()*100
    base=5*(x>e20)+5*(x>e60)+8*(e20>e60)+6*(e20>e20.shift(5))+6*(e60>e60.shift(5))
    base=base.astype(float)+15*(v10/30).clip(0,1).fillna(0)+20*(rise/35).clip(0,1).fillna(0)
    base+=np.select([location>=85,location>=70,location>=55,location>=40],[15.,12.,8.,4.],default=0.)
    base+=10*((persist-40)/40).clip(0,1).fillna(0)
    ps,bull=sar(hi.to_numpy(float),lo.to_numpy(float))
    sar_score=[]
    bars=0
    for i,b in enumerate(bull):
        bars=1 if i>0 and b!=bull[i-1] else bars+1
        sar_score.append(10 if b else (5 if bars<=2 else 0))
    score=np.minimum(100,np.array(base)+np.array(sar_score))
    # Pine request.security(f_stDailyBaseScore()[1],lookahead_on): ALWAYS yesterday completed trading date.
    d["trendPrev"]=pd.Series(score,index=d.index).shift(1)
    return d
def resample(minute,tf):
    # Time is bar OPEN in Taiwan local; aggregate all day and night minutes
    f=f"{tf}min"
    b=minute.set_index("datetime").resample(f,origin="start_day",label="left",closed="left").agg(
        open=("open","first"),high=("high","max"),low=("low","min"),close=("close","last"),
        volume=("volume","sum"),n=("close","count"),trading_date=("trading_date","last"))
    b=b[b.n==tf].copy() # never invent missing minute prices or fake OHLC
    b=b[b.index<=pd.Timestamp("2026-09-01")].copy()
    day=b.index.hour*60+b.index.minute
    b["isDay"]=(day>=8*60+45)&(day<13*60+45)
    b["timeHHMM"]=b.index.strftime("%H:%M")
    return b.reset_index()
def indicator(b,daily):
    c=b.close;h=b.high;l=b.low;op=b.open;v=b.volume
    lastclose=c.shift();tr=pd.concat([h-l,(h-lastclose).abs(),(l-lastclose).abs()],axis=1).max(axis=1)
    # ta.atr = true range Wilder RMA; ewm alpha approximates Pine seed by 14-period mean
    atr=tr.ewm(alpha=1/14,min_periods=14,adjust=False).mean()
    ma200=c.rolling(200,min_periods=200).mean()
    xd=(c-ma200)/atr;xd=xd.replace([np.inf,-np.inf],np.nan)
    sne=np.zeros(len(b));spo=np.zeros(len(b))
    for i,t in enumerate(xd):
        neg=bool(pd.notna(t) and t< -1);pos=bool(pd.notna(t) and t>1)
        sne[i]=(sne[i-1] if i else 0)+(float(-t)-1) if neg else (sne[i-1] if i else 0)*.6
        spo[i]=(spo[i-1] if i else 0)+(float(t)-1) if pos else (spo[i-1] if i else 0)*.6
    b["pressUp"]=1-np.exp(-sne/6);b["pressDn"]=1-np.exp(-spo/6)
    hiC=c.rolling(40,min_periods=40).max()
    loC=c.rolling(40,min_periods=40).min()
    wvf=(hiC-l)/hiC*100;gvf=(h-loC)/loC*100
    fearTh=wvf.rolling(400,min_periods=50).quantile(.90,interpolation="linear")
    greedTh=gvf.rolling(400,min_periods=50).quantile(.90,interpolation="linear")
    fearHot=wvf>=fearTh;greedHot=gvf>=greedTh
    fearRecent=fearHot|fearHot.shift(1,fill_value=False)|fearHot.shift(2,fill_value=False)
    m5=(c-c.shift(5))/atr
    dn=m5.rolling(3,min_periods=3).min()<=-2
    up=m5.rolling(3,min_periods=3).max()>=2
    tt=b.datetime.dt.hour*60+b.datetime.dt.minute
    sess=((tt>=9*60)&(tt<9*60+30))|((tt>=10*60+30)&(tt<11*60))|((tt>=13*60+30)&(tt<14*60))
    preBottom=(fearRecent&dn&(m5>m5.shift())&(b.pressUp>=.6)&sess)
    preTop=(greedHot&up&(m5<m5.shift())&(b.pressDn>=.6)&sess)
    bottoms=np.zeros(len(b),dtype=bool);tops=np.zeros(len(b),dtype=bool)
    last=-10000
    for i in range(len(b)):
        if i-last<8:continue
        if bool(preBottom.iloc[i]):bottoms[i]=True;last=i
        elif bool(preTop.iloc[i]):tops[i]=True;last=i
    b["bottom"]=bottoms;b["top"]=tops;b["atr"]=atr
    score=daily["trendPrev"]
    b["trend70"]=b.trading_date.map(score).gt(70).fillna(False)
    b["dailyTrendScore"]=b.trading_date.map(score)
    b["strongBottom"]=b.bottom & b.trend70
    return b
def run_case(b,tf,mode,segment):
    start,end=segment;open_=b.open.to_numpy(float);hi=b.high.to_numpy(float);lo=b.low.to_numpy(float)
    close=b.close.to_numpy(float);atr=b.atr.to_numpy(float)
    bottom=b.bottom.to_numpy(bool);top=b.top.to_numpy(bool);strong=b.strongBottom.to_numpy(bool)
    inDay=b.isDay.to_numpy(bool);day=b.datetime.dt.date.to_numpy();ts=b.datetime.astype(str).to_numpy()
    equity=1_000_000.;qty=0;entry=0;stop=0;tp1=0;tp3=0;highest=0;beReached=False
    trades=[];rows=[];peak=equity;mdd=0;byyear={};pnlGross=0;pnlNet=0
    pending=0 # 1 open long, -1 open short, 2 close only
    openedDate=None;entryNetCost=0;lastEntryDate="";lastExitDate="";pertrade=[]
    fixed=60.;tax=2e-5;pointVal=200;slip=1.;closed=0;wins=0
    minHour=13*60+40 if tf==5 else 13*60+42
    for i in range(len(b)):
        d=b.datetime.iloc[i]
        if str(d.date())<start or str(d.date())>end:continue
        p=float(open_[i]);cl=float(close[i]);dstr=str(d.date())
        # Execute all previous bar-close events only if THIS open belongs to same day.
        if pending:
            if not inDay[i] or (openedDate is not None and openedDate!=dstr):
                pending=0
            else:
                direction=pending
                if qty and (direction==2 or direction==-qty):
                    execution=p-(slip*qty)
                    value=(execution-entry)*qty*pointVal
                    outcost=fixed+tax*execution*pointVal
                    pnl=value-outcost-entryNetCost
                    equity+=value-outcost
                    pertrade.append({"entry":lastEntryDate,"exit":ts[i],"dir":qty,"netTWD":round(pnl,2),"reason":"opposite_signal"})
                    closed+=1;wins+=int(pnl>0)
                    qty=0;entryNetCost=0
                if direction in (1,-1) and qty==0:
                    execution=p+slip*direction
                    qty=direction;entry=execution;highest=cl
                    entryNetCost=fixed+tax*execution*pointVal
                    equity-=entryNetCost;lastEntryDate=ts[i];openedDate=dstr
                    risk=max(atr[i-1],.1)*2 if i else max(atr[i],.1)*2
                    stop=entry-direction*risk;tp1=entry+direction*risk*1.5;tp3=entry+direction*risk*3.0
                    beReached=False
                pending=0
        # Position safety; on the same bar OPEN we can conservatively check SL and TP3 hits.
        exitReason=""
        if qty and inDay[i] and mode.endswith("_atr"):
            if qty==1:
                if lo[i]<=stop:exitReason="ATR2_stop"
                elif hi[i]>=tp3:exitReason="TP3_hit"
                elif not beReached and hi[i]>=tp1:beReached=True;stop=max(stop,entry)
            else:
                if hi[i]>=stop:exitReason="ATR2_stop"
                elif lo[i]<=tp3:exitReason="TP3_hit"
                elif not beReached and lo[i]<=tp1:beReached=True;stop=min(stop,entry)
        if exitReason:
            execution=(stop if exitReason=="ATR2_stop" else tp3)-qty*slip
            pnl=(execution-entry)*qty*pointVal
            outcost=fixed+tax*execution*pointVal
            net=pnl-outcost-entryNetCost;equity+=pnl-outcost
            pertrade.append({"entry":lastEntryDate,"exit":ts[i],"dir":qty,"netTWD":round(net,2),"reason":exitReason})
            closed+=1;wins+=int(net>0);qty=0;entryNetCost=0;pending=0
        # Day-flat is mandatory independent of indicator session. No unrealistically carrying futures overnight.
        isLast=bool(inDay[i] and (i==len(b)-1 or day[i+1]!=day[i] or not inDay[i+1]))
        if isLast and qty:
            execution=cl-qty*slip
            pnl=(execution-entry)*qty*pointVal
            outcost=fixed+tax*execution*pointVal
            net=pnl-outcost-entryNetCost;equity+=pnl-outcost
            pertrade.append({"entry":lastEntryDate,"exit":ts[i],"dir":qty,"netTWD":round(net,2),"reason":"day_flat"})
            closed+=1;wins+=int(net>0);qty=0;entryNetCost=0;pending=0
        elif isLast:pending=0
        elif inDay[i] and not exitReason:
            if qty==0:
                if mode.startswith("strong"):signal=strong[i]
                else:signal=bottom[i]
                if signal:pending=1
                elif mode.startswith("both") and top[i]:pending=-1
            elif qty==1 and top[i]:pending=2 if mode.startswith("long") or mode.startswith("strong") else -1
            elif qty==-1 and bottom[i]:pending=1
        nav=equity+qty*(cl-entry)*pointVal-(fixed+tax*cl*pointVal if qty else 0)
        peak=max(peak,nav);mdd=min(mdd,(nav/peak-1)*100)
        if inDay[i]:rows.append([ts[i],round(nav,2)])
    arr=np.asarray([t["netTWD"] for t in pertrade])
    profit=arr[arr>0].sum() if arr.size else 0;loss=abs(arr[arr<0].sum()) if arr.size else 0
    years={}
    for year in ("2025","2026"):
        j=[r for r in rows if r[0].startswith(year)]
        if j:years[year]={"endTWD":j[-1][1],"startTWD":j[0][1],"nBars":len(j),
             "netPnlTWD":round(sum(t["netTWD"] for t in pertrade if t["exit"].startswith(year)),2)}
    return {"timeframeMin":tf,"mode":mode,"segment":segment,"firstBar":rows[0][0] if rows else None,
        "lastBar":rows[-1][0] if rows else None,"trades":closed,"wins":wins,
        "winRatePct":round(100*wins/closed,2) if closed else None,
        "profitFactor":round(float(profit/loss),3) if loss else None,
        "avgNetTWD":round(float(arr.mean()),2) if arr.size else None,
        "medianNetTWD":round(float(np.median(arr)),2) if arr.size else None,
        "netPnlTWD":round(equity-1_000_000,2),"endingEquityTWD":round(equity,2),
        "returnPct":round((equity/1_000_000-1)*100,3),"maxDrawdownPct":round(mdd,3),
        "annual":years,"tradeLog":pertrade,"equity":rows}
def main():
    st=time.monotonic()
    minute=pd.concat([sqlbars(y) for y in (2024,2025,2026)],ignore_index=True).sort_values("datetime")
    minute=minute[minute.datetime<=pd.Timestamp("2026-09-01")].copy()
    allDays=daily_trend(minute)
    assert len(allDays)>450
    overview={"dataUrl":"https://github.com/jason43314-crypto/taiwan-futures-1min-ohlc",
      "dataSnapshot":"repository 2026-09-07 snapshot containing data through 2026-09-05",
      "market":"TXFR1 near-month Taiwan TX futures continuous","start":START,"end":END,
      "warmupStart":WARMUP,"nightDataUsedInIndicators":True,
      "testTransactions":"08:45-13:45 DAY SESSION ONLY",
      "entrySessionTimes":["09:00-09:30","10:30-11:00","13:30-13:45"],
      "minuteRows":len(minute),"tradingDates":int(minute.trading_date.nunique()),
      "sourceIsThirdParty":True,
      "sourceCaveats":["Monthly futures settlement concatenation creates unadjusted roll gaps",
        "Some one-minute records are synthetic and are excluded",
        "Sub-2 minute and sub-5 minute aggregation depends on source timestamp correctness",
        "Exact TradingView futures settlement and daily SAR may differ",
        "No order book / bid-ask depth; large moves may have larger slippage."]}
    cases=[]
    for tf in (2,5):
        bars=indicator(resample(minute,tf),allDays)
        main_mask=(bars.datetime>=pd.Timestamp(START))&(bars.datetime<=pd.Timestamp(END+" 23:59"))
        diag={"timeframeMin":tf,"totalBars":len(bars),"testBars":int(main_mask.sum()),
            "dayTestBars":int((main_mask&bars.isDay).sum()),
            "bottoms":int((main_mask&bars.bottom).sum()),"tops":int((main_mask&bars.top).sum()),
            "strongBottoms":int((main_mask&bars.strongBottom).sum()),
            "trend70Days":int(bars.loc[main_mask & bars.isDay & bars.trend70,"trading_date"].nunique()),
            "startingSignalTime":bars.loc[main_mask,"datetime"].min().isoformat()}
        print("TXF_SIGNAL_DIAG "+json.dumps(diag),flush=True)
        overview.setdefault("dataQuality",[]).append(diag)
        modes=("long_top","strong_top","long_atr","strong_atr","both_top","both_atr")
        for mode in modes:
            for period in ((START,END),("2025-01-02","2025-12-31"),("2026-01-01",END)):
                x=run_case(bars,tf,mode,period)
                cases.append(x)
                print("TXF_TEST "+json.dumps({k:x[k] for k in ("timeframeMin","mode","segment","trades",
                      "netPnlTWD","returnPct","maxDrawdownPct","winRatePct","profitFactor")}),flush=True)
    OUT.mkdir(parents=True,exist_ok=True)
    summary={"version":"TXF_EXTREME_REVERSAL_TREND70_2M_5M_V1",
        "generated":datetime.now(ZoneInfo("Asia/Taipei")).isoformat(timespec="seconds"),
        "sourcePineSha256":"bf45b473792d1dc656bf8b050f211eef33ce7e64f485c321b98dfa546bf1e3a3",
        "data":overview,"cost":COST,"variants":{"long_top":"BOTTOM long -> TOP exit or session close",
         "strong_top":"Trend>70 and BOTTOM long -> TOP exit or session close",
         "long_atr":"BOTTOM long; ATR2 SL, 1.5R BE, 3R exit or session close",
         "strong_atr":"Trend>70 and BOTTOM long; ATR2 SL, 1.5R BE, 3R exit or session close",
         "both_top":"BOTTOM long, TOP short, reverse on other signal or session close",
         "both_atr":"BOTTOM long, TOP short; ATR2 SL/BE/TP3, opposite reversal, session close"},
        "evaluationWarnings":["Pine indicator not a TradingView strategy: these are newly explicit, rule-based simulated fills.",
          "Backtest approximates Pine ta.atr via EWM and SAR; 2m and 5m are reconstructed from public third-party one-minute OHLC.",
          "Pine's default session filter allows signals only three Taiwan day segments. All trades are flattened before day session close (extra backtest rule).",
          "Daily Trend70 is previous completed futures trading-date day+night OHLC, not price-only day-session equity market score.",
          "This backtest fixes one TXF contract; initial 1m capital is margin rather than fully invested market value, no contract scaling or margin enforcement.",
          "When price hits SL and TP during same bar, pessimistically assume SL filled first, with one point worse fill.",
          "Transaction notional tax and broker fee are estimated, not broker quote. No detailed intra-bar execution paths available.",
          "Do not claim one resolution is superior if sample trades are small or profitability is sensitive to trading conditions."],
        "results":[{k:v for k,v in item.items() if k not in ("tradeLog","equity")} for item in cases],
        "durationSeconds":round(time.monotonic()-st,1)}
    (OUT/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    (OUT/"trades_and_equity.json").write_text(json.dumps({"version":summary["version"],
      "cases":{f'{r["timeframeMin"]}m_{r["mode"]}_{r["segment"][0][:4]}_{r["segment"][1][:4]}':
          {"timeframe":r["timeframeMin"],"mode":r["mode"],"period":r["segment"],
           "trades":r["tradeLog"],"equity":r["equity"]} for r in cases}},ensure_ascii=False),encoding="utf-8")
    assert len(cases)==36
    print("TXF_DONE "+json.dumps({"bars":overview["dataQuality"],"studyCount":len(cases),
      "strongCases":[{k:v[k] for k in ("timeframeMin","mode","segment","netPnlTWD","trades","profitFactor")}
          for v in cases if v["mode"]=="strong_atr" and v["segment"][0]==START],
      "seconds":summary["durationSeconds"]}),flush=True)
if __name__=="__main__":main()
