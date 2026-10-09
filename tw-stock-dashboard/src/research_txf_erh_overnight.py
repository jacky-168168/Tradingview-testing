"""Overnight variant of TXF ERH Trend70. Research only; signals approximate Pine.
Baseline uses prior daily-futures Trend>70 and unchanged daytime BOTTOM criteria.
Nighttop allows TOP in every valid day/night minute bar, including after-hours.
Entry remains day-session three windows. No session-close flatten.
End-of-sample open positions are MARKED, NOT counted as closed trades.
"""
from __future__ import annotations
import json,time,math
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import numpy as np,pandas as pd
from research_txf_erh_2m_5m import sqlbars,daily_trend,resample,indicator,START,END,OUT as BASE_OUT,COST
OUT=BASE_OUT.parent/"txf_erh_overnight_2025_2026"
SEGS=((START,END),(START,"2025-12-31"),("2026-01-01",END))
PV=float(COST["pointValueTWD"]);FEE=float(COST["brokerFeeTWDPerSide"])
SLIP=float(COST["simulatedSlippagePointsEachSide"]);TAX=float(COST["futuresTransactionTaxNotionalPerSide"])
INIT=float(COST["initialEquityTWD"])
def all_session_top(b):
    # Reproduce the original two candidate formulas, changing only TOP session eligibility.
    c=b.close;h=b.high;l=b.low;atr=b.atr
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
    preB=(fearRecent&dn&(m5>m5.shift())&(b.pressUp>=.6)&sess).fillna(False).to_numpy(bool)
    preT=(greedHot&up&(m5<m5.shift())&(b.pressDn>=.6)).fillna(False).to_numpy(bool)
    bottoms=np.zeros(len(b),dtype=bool);tops=np.zeros(len(b),dtype=bool)
    last=-10000
    for i in range(len(b)):
        if i-last<8:continue
        if preB[i]:bottoms[i]=True;last=i
        elif preT[i]:tops[i]=True;last=i
    b=b.copy()
    b["bottomNightTop"]=bottoms
    b["topNightTop"]=tops
    b["strongBottomNightTop"]=bottoms&b.trend70.to_numpy(bool)
    return b
def fee(price):
    return FEE+TAX*max(price,0)*PV
def simulate(b,tf,mode,segment):
    lo_date,hi_date=segment
    # Slice includes full indicator warmup computed before; segment starts FLAT.
    a=b[(b.datetime>=pd.Timestamp(lo_date))&(b.datetime<=pd.Timestamp(hi_date+" 23:59"))].copy()
    o=a.open.to_numpy(float);h=a.high.to_numpy(float);l=a.low.to_numpy(float)
    c=a.close.to_numpy(float);atr=a.atr.to_numpy(float);dates=a.datetime.astype(str).to_numpy()
    strong=(a.strongBottom.to_numpy(bool) if mode=="overnight_daytop" else a.strongBottomNightTop.to_numpy(bool))
    tops=(a.top.to_numpy(bool) if mode=="overnight_daytop" else a.topNightTop.to_numpy(bool))
    is_day=a.isDay.to_numpy(bool);dt=a.datetime.dt.date.to_numpy()
    cash=INIT;qty=0;entry=0.;stop=0.;entry_cost=0.;entry_ts=""
    pending=0;pending_entry_day=None;trades=[];curve=[];peak=INIT;mdd=0.
    night_exits=0;stop_exits=0;cross_night=0;max_hold_hrs=0.
    def close_pos(price,i,reason):
        nonlocal cash,qty,entry_cost,night_exits,stop_exits,cross_night,max_hold_hrs
        px=float(price)-SLIP;gross=(px-entry)*PV;out=fee(px);net=gross-entry_cost-out
        cash+=gross-out
        hold=(pd.Timestamp(dates[i])-pd.Timestamp(entry_ts)).total_seconds()/3600
        overnight=pd.Timestamp(dates[i]).date()!=pd.Timestamp(entry_ts).date()
        night=not bool(is_day[i])
        trades.append({"entry":entry_ts,"exit":dates[i],"entryPrice":round(entry,2),
            "exitPrice":round(px,2),"netTWD":round(net,2),"grossTWD":round(gross,2),
            "reason":reason,"holdHours":round(hold,2),"heldAcrossCalendarDay":overnight,
            "exitInNightSession":night})
        cross_night+=int(overnight);night_exits+=int(night);stop_exits+=int(reason=="ATR2_stop")
        max_hold_hrs=max(max_hold_hrs,hold);qty=0;entry_cost=0.
    for i in range(len(a)):
        p=o[i];pending_now=pending;pending=0
        # TOP set at last bar before a closed market executes at the NEXT real bar open.
        if pending_now==2 and qty:close_pos(p,i,"TOP")
        # BOTTOM entry must be next consecutive day-session bar, not night or next day.
        if pending_now==1 and not qty and is_day[i] and pending_entry_day==dt[i]:
            entry=p+SLIP;qty=1;entry_cost=fee(entry);cash-=entry_cost;entry_ts=dates[i]
            signal_atr=atr[i-1] if i else atr[i]
            if not np.isfinite(signal_atr):signal_atr=0.
            stop=entry-2.*max(float(signal_atr),.1)
        if qty and mode=="overnight_atr2" and l[i]<=stop:
            # Gap through stop executes at open, not impossible favorable stop fill.
            close_pos(min(stop,p),i,"ATR2_stop")
        if not qty:
            if is_day[i] and strong[i] and i+1<len(a):pending=1;pending_entry_day=dt[i]
        elif tops[i] and i+1<len(a):pending=2
        nav=cash+(c[i]-entry)*PV-fee(c[i]) if qty else cash
        peak=max(peak,nav);mdd=min(mdd,100*(nav/peak-1))
        if i%20==0 or i==len(a)-1 or pending or (i>0 and dt[i]!=dt[i-1]):
            curve.append([dates[i],round(nav,2)])
    last_px=float(c[-1]) if len(c) else 0.
    mtm=float(cash+(last_px-entry)*PV-fee(last_px)) if qty else float(cash)
    complete=np.array([t["netTWD"] for t in trades],dtype=float)
    pos=float(complete[complete>0].sum()) if len(complete) else 0.
    neg=-float(complete[complete<0].sum()) if len(complete) else 0.
    holding={"isOpen":bool(qty),"entry":entry_ts if qty else None,"entryPrice":entry if qty else None,
        "unrealizedNetAfterEstExitCostTWD":round(mtm-cash,2) if qty else 0}
    years={}
    for yr in ("2025","2026"):
        subset=[t for t in trades if t["exit"].startswith(yr)]
        eq=[e for e in curve if e[0].startswith(yr)]
        if eq:years[yr]={"closedTrades":len(subset),"realizedTradesNetTWD":round(sum(t["netTWD"] for t in subset),2),
            "firstObservedEquityTWD":eq[0][1],"lastObservedEquityTWD":eq[-1][1]}
    return {"timeframeMin":tf,"mode":mode,"segment":segment,"trades":len(trades),
      "wins":int(sum(t["netTWD"]>0 for t in trades)),
      "winRatePct":round(100*sum(t["netTWD"]>0 for t in trades)/len(trades),2) if trades else None,
      "profitFactor":round(pos/neg,3) if neg else None,
      "avgNetTWD":round(float(complete.mean()),2) if len(complete) else None,
      "netPnlTWD":round(mtm-INIT,2),"endingEquityTWD":round(mtm,2),
      "returnPct":round((mtm/INIT-1)*100,3),"maxDrawdownPct":round(mdd,3),
      "nightExits":night_exits,"overnightHeldTrades":cross_night,"stopExits":stop_exits,
      "maxHoldHours":round(max_hold_hrs,2),"openPosition":holding,
      "annual":years,"tradeLog":trades,"equity":curve}
def main():
    st=time.monotonic()
    minute=pd.concat([sqlbars(y) for y in (2024,2025,2026)],ignore_index=True).sort_values("datetime")
    minute=minute[minute.datetime<=pd.Timestamp("2026-09-01")].copy()
    days=daily_trend(minute)
    cases=[];diagnostics=[]
    for tf in (2,5):
        bars=all_session_top(indicator(resample(minute,tf),days))
        mask=(bars.datetime>=pd.Timestamp(START))&(bars.datetime<=pd.Timestamp(END+" 23:59"))
        night=(~bars.isDay)&mask
        diag={"timeframeMin":tf,"originalStrongBottoms":int((mask&bars.strongBottom).sum()),
          "nightTopStrongBottoms":int((mask&bars.strongBottomNightTop).sum()),
          "originalTops":int((mask&bars.top).sum()),
          "expandedTops":int((mask&bars.topNightTop).sum()),
          "nightTops":int((night&bars.topNightTop).sum()),
          "nightBars":int(night.sum())}
        diagnostics.append(diag);print("TXF_OVERNIGHT_SIGNALS "+json.dumps(diag),flush=True)
        for mode in ("overnight_daytop","overnight_top","overnight_atr2"):
            for segment in SEGS:
                r=simulate(bars,tf,mode,segment);cases.append(r)
                print("TXF_OVERNIGHT_RESULT "+json.dumps({k:r[k] for k in
                  ("timeframeMin","mode","segment","trades","wins","winRatePct","profitFactor",
                   "returnPct","netPnlTWD","maxDrawdownPct","nightExits","openPosition")}),flush=True)
    summary={"version":"TXF_ERH_TREND70_OVERNIGHT_V1",
      "generated":datetime.now(ZoneInfo("Asia/Taipei")).isoformat(timespec="seconds"),
      "sourcePineSha256":"bf45b473792d1dc656bf8b050f211eef33ce7e64f485c321b98dfa546bf1e3a3",
      "researchPeriod":[START,END],"dataSource":"public third-party TXFR1 unadjusted continuous one-minute OHLC",
      "cost":{**COST,"exitAtDaySessionClose":False},
      "rules":{"entries":"2m/5m previous-completed daily Trend>70 plus Bottom; original 3 intraday windows only",
        "overnight_daytop":"Hold across day/night; TOP only in the original three day windows",
        "overnight_top":"Hold across day/night; TOP emitted in both day and night sessions; no other stop",
        "overnight_atr2":"overnight_top plus protective initial SL 2*ATR14 in all sessions",
        "fill":"Signal at bar close, execute next valid bar open with 1-point per-side slippage.",
        "endOfTest":"No liquidation unless TOP or SL; any final position marked with estimated exit fee (unrealized).",
        "position":"one long TXF lot; no pyramiding; no compounding; no enforced margins"},
      "diagnostics":diagnostics,
      "evaluationWarnings":["NOT bit-exact TradingView Pine; day+night data are externally sourced one-minute bars.",
        "Enabling TOP at night changes shared 8-bar signal cooldown; daytime Bottom signal counts may change.",
        "Unadjusted continuous contract rolls can create unrealistically large apparent gains/losses across expiry.",
        "Model does not identify expiry contract-month switches, apply rollover transaction costs, or force-roll physical contracts.",
        "Open positions at sample end are marked to market, not treated as closed TOP trades.",
        "When ATR stop is gapped through, uses next open with 1-point slippage, not favorable stop price.",
        "No margin-call or gap execution-depth model. Returns can be unreliable at high futures leverage.",
        "Small numbers of completed Trend70 trades cannot establish a stable edge."],
      "results":[{k:v for k,v in x.items() if k not in ("tradeLog","equity")} for x in cases],
      "durationSeconds":round(time.monotonic()-st,1)}
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    (OUT/"trades_and_equity.json").write_text(json.dumps({"version":summary["version"],"cases":{
       f'{x["timeframeMin"]}m_{x["mode"]}_{x["segment"][0][:4]}_{x["segment"][1][:4]}':
       {"trades":x["tradeLog"],"equity":x["equity"]} for x in cases}},ensure_ascii=False),encoding="utf-8")
    assert len(cases)==18
    print("TXF_OVERNIGHT_DONE "+json.dumps({"studies":len(cases),"seconds":summary["durationSeconds"]}),flush=True)
if __name__=="__main__":main()
