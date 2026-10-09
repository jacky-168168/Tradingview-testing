"""00675L crisis-entry study: COVID 2020, April-2025 tariff, March-2026 Iran conflict.
Fully causal: only prior completed TWII closes are used to buy 00675L next open.
No new funds; full-history 25/50% crash reserves reduce core trend exposure proportionally.
"""
from __future__ import annotations
import json,os
from datetime import datetime,timezone
from pathlib import Path
import numpy as np
from research_00675l_vwma5_sma10_2018_2026 import index_data
from research_00675l_ma_family_2020_2026 import ma_array
from research_00675l_swing_grid import CAPITAL,SLIP,BROKER,ETF_SELL_TAX
from research_00675l_exit_entry_v2 import simulate,rule
ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/"docs/data/research/etf_history"
OUT=DATA/"00675l_crash_entry"
STUDY="00675_crash_entry"
BEGIN="2018-01-02";END="2026-10-07"
EVENTS=[("COVID_2020","COVID-19疫情","2020-02-20","2020-06-30"),
        ("TARIFF_2025","2025美國關稅風暴","2025-04-01","2025-06-30"),
        ("IRAN_2026","2026伊朗戰爭","2026-02-27","2026-06-30")]
BF=(1+SLIP)*(1+BROKER)
SF=(1-SLIP)*(1-BROKER-ETF_SELL_TAX)
def lookback_dd(idx,j,days=60):
    if j<0:return 0.
    hi=float(np.max(idx[max(0,j-days+1):j+1]))
    return max(0.,1-float(idx[j])/hi)
def idx_pct(idx,j):
    return 0. if j<1 else float(idx[j]/idx[j-1]-1)
def ep_study(a,dates,ma,start,end,mode):
    xs=np.flatnonzero((dates>=start)&(dates<=end))
    cash=float(CAPITAL);shares=0;equity=[];orders=[];fired=set();shock=False
    idx=a["twii"];staging=[.05,.10,.15,.20]
    for pos,i in enumerate(xs):
        j=i-1;date=str(dates[i]);op=float(a["open"][i]);cl=float(a["close"][i])
        if pos>0:
            ret=idx_pct(idx,j);dd=lookback_dd(idx,j)
            if dd>=.05:shock=True
            steps=0
            if mode=="DAILY5_FULL" and ret<=-.05 and not fired:steps=4;fired.add("all")
            elif mode=="DAILY4_FULL" and ret<=-.04 and not fired:steps=4;fired.add("all")
            elif mode=="DD5_FULL" and dd>=.05 and not fired:steps=4;fired.add("all")
            elif mode=="DD10_FULL" and dd>=.10 and not fired:steps=4;fired.add("all")
            elif mode=="STAGGER_5_10_15_20":
                new=[k for k,t in enumerate(staging) if k not in fired and dd>=t]
                steps=len(new);fired.update(new)
            elif mode=="STAGGER_10_15_20_25":
                new=[k for k,t in enumerate((.10,.15,.20,.25)) if k not in fired and dd>=t]
                steps=len(new);fired.update(new)
            elif mode=="WAIT_SMA10" and shock and idx[j]>ma[j]*1.01 and not fired:steps=4;fired.add("all")
            budget=min(cash,CAPITAL*.25*steps)
            if budget>0:
                qty=int(budget//(op*BF))
                qty=min(qty,int(cash//(op*BF)))
                if qty:
                    val=qty*op*BF;cash-=val;shares+=qty
                    orders.append([date,"BUY",qty,round(op,5),round(val,2),round(dd*100,3),round(ret*100,3)])
        equity.append([date,round(cash+shares*cl*SF,2)])
    gross=cash+shares*float(a["close"][xs[-1]])*SF
    equity[-1][1]=round(gross,2)
    values=np.array([z[1] for z in equity]);peaks=np.maximum.accumulate(np.r_[CAPITAL,values])[1:]
    return {"returnPct":round((gross/CAPITAL-1)*100,3),"endNTD":round(gross,2),
        "mddPct":round(float(np.min((values/peaks-1)*100)),3),
        "numBuys":len(orders),"investedPctApprox":round(100*(1-(cash/CAPITAL)),2),
        "orders":orders,"signalCount":sum(idx_pct(idx,int(i))<=-.05 for i in xs),
        "points":equity}
def sleeve(a,dates,ma):
    idx=a["twii"];cash=float(CAPITAL);shares=0;budget=float(CAPITAL);used=set();orders=[];equity=[]
    xs=np.flatnonzero((dates>=BEGIN)&(dates<=END))
    for pos,i in enumerate(xs):
        j=i-1;dt=str(dates[i]);op=float(a["open"][i]);cl=float(a["close"][i])
        if pos>0 and j>=0:
            dd=lookback_dd(idx,j)
            recovery=np.isfinite(ma[j]) and idx[j]>ma[j]*1.01
            if recovery and shares>0:
                n=shares;v=n*op*SF;cash+=v;shares=0;used=set();budget=cash
                orders.append([dt,"SELL",n,round(op,5),round(v,2),round(dd*100,3)])
            elif recovery and shares==0:
                used=set();budget=cash
            elif dd>=.05:
                new=[k for k,t in enumerate((.05,.10,.15,.20)) if k not in used and dd>=t]
                if new:
                    if not used:budget=cash
                    used.update(new)
                    allocation=min(cash,len(new)*.25*budget)
                    n=min(int(allocation//(op*BF)),int(cash//(op*BF)))
                    if n:
                        v=n*op*BF;shares+=n;cash-=v
                        orders.append([dt,"BUY",n,round(op,5),round(v,2),round(dd*100,3)])
        equity.append([dt,round(cash+shares*cl*SF,2)])
    last=xs[-1];wealth=cash+shares*float(a["close"][last])*SF
    equity[-1][1]=round(wealth,2)
    return {"points":equity,"trades":orders,"final":round(wealth,2)}
def audit(base_curve,sleeve_curve,weight):
    assert len(base_curve)==len(sleeve_curve)==2128
    eq=[[b[0],round((1-weight)*b[1]+weight*s[1],2)] for b,s in zip(base_curve,sleeve_curve)]
    vals=np.array([x[1] for x in eq]);peaks=np.maximum.accumulate(np.r_[CAPITAL,vals])[1:]
    years=[];last=float(CAPITAL)
    for yr in sorted({x[0][:4] for x in eq}):
        wealth=next(x[1] for x in reversed(eq) if x[0].startswith(yr))
        years.append({"year":yr,"pct":round((wealth/last-1)*100,3),"wealthTWD":wealth,"wealthUSD":None,"usdPct":None})
        last=wealth
    return {"points":eq,"endTWD":eq[-1][1],"returnPct":round((eq[-1][1]/CAPITAL-1)*100,3),
        "mddPct":round(float(np.min((vals/peaks-1)*100)),3),"annual":years}
def episode_equity(a,lo,hi):
    xs=[x for x in a["points"] if lo<=x[0]<=hi]
    vals=np.array([x[1] for x in xs]);v0=a["points"][next(i for i,x in enumerate(a["points"]) if x[0]==xs[0][0])-1][1]
    peak=np.maximum.accumulate(np.r_[v0,vals])[1:]
    return {"beginDate":xs[0][0],"endDate":xs[-1][0],
        "returnPct":round((vals[-1]/v0-1)*100,3),
        "mddPct":round(float(np.min((vals/peak-1)*100)),3),
        "startingEquity":round(float(v0),2),"endingEquity":round(float(vals[-1]),2)}
def main():
    OUT.mkdir(parents=True,exist_ok=True);(DATA/"curves").mkdir(parents=True,exist_ok=True)
    _,a,dates,quality=index_data()
    sma=ma_array(a["twii"],None,"SMA",10)
    base=simulate(a,dates,rule("IDX_DROP_4","已驗證SMA10急跌4%主策略",panic_index=.04),sma,details=True)
    assert len(base["points"])==2128 and base["returnPct"]==4194.082
    archive=json.loads((DATA/"index.json").read_text(encoding="utf-8"))
    prev=next(s for s in archive["studies"] if s["id"]=="00675_risk_v2")
    old=next(m for m in prev["models"] if m["id"]=="IDX_DROP_4")
    assert old["endTWD"]==base["endNTD"] and old["mddPct"]==base["mddPct"]
    core={"points":base["points"],"endTWD":base["endNTD"],"returnPct":base["returnPct"],
          "mddPct":base["mddPct"],"annual":base["annual"]}
    crash=sleeve(a,dates,sma)
    variants=[("BASE","原版SMA10＋急跌4%（100%趨勢）",0.),
              ("RESERVE25","75%趨勢＋25%現金分批抄底",.25),
              ("RESERVE50","50%趨勢＋50%現金分批抄底",.50)]
    all_models=[];curves={}
    for id,title,weight in variants:
        r=core if weight==0 else audit(base["points"],crash["points"],weight)
        curves[id]=r
        rel="curves/"+STUDY+"__"+id+".json"
        points=r["points"]
        trades=base["orders"] if weight==0 else crash["trades"]
        payload={"study":STUDY,"id":id,"currency":"TWD","columns":["date","equity"],
            "points":points,"trades":trades,
            "tradeColumns":["date","side","phase","units","unitPrice","cashFlow","cashAfter"] if weight==0
                else ["date","side","units","unitPrice","cashFlow","lookback60dDrawdownPct"],
            "warning":"For reserve models, trades list describes the panic sleeve; SMA10 core trades remain in the original baseline archive."}
        (DATA/rel).write_text(json.dumps(payload,ensure_ascii=False,separators=(",",":")),encoding="utf-8")
        sample={"id":id,"name":title,"group":"趨勢＋股災備用金",
           "endTWD":r["endTWD"],"returnPct":r["returnPct"],"mddPct":r["mddPct"],
           "sells":base["riskOffSells"],"rebuys":base["riskOnReentries"],
           "cashDays":base["riskOffSessions"],"sessions":2128,"annual":r["annual"],"curve":rel,
           "curveCurrency":"TWD",
           "notes":"出場維持SMA10＋單日急跌4%；核心資金占"+str(int((1-weight)*100))+
                   "%，剩餘資金獨立保留，台指距當時過去60日高點回落5/10/15/20%各買入備用金25%，指數重返SMA10+1%時賣出備用部位並重新保留備用金。核心與備用金從不互相借款，無額外注資。"}
        all_models.append(sample)
        print("FULL",id,json.dumps({"returnPct":r["returnPct"],"endTWD":r["endTWD"],"mdd":r["mddPct"]}),flush=True)
    episode_results={}
    modes=["DAILY5_FULL","DAILY4_FULL","DD5_FULL","DD10_FULL","STAGGER_5_10_15_20","STAGGER_10_15_20_25","WAIT_SMA10"]
    for id,label,start,end in EVENTS:
        dates_scope=np.flatnonzero((dates>=start)&(dates<=end))
        drop_list=[{"date":str(dates[j]),"indexClose":round(float(a["twii"][j]),2),"pct":round(idx_pct(a["twii"],j)*100,3)} for j in dates_scope if idx_pct(a["twii"],j)<=-.05]
        focus={"id":id,"name":label,"window":[start,end],"days":len(dates_scope),
          "indexWorstDailyPct":round(min(idx_pct(a["twii"],j) for j in dates_scope)*100,3),
          "indexDrawdownPeak60dPct":round(max(lookback_dd(a["twii"],j) for j in dates_scope)*100,3),
          "indexDailyBelowMinus5Pct":drop_list,
          "modes":{v:ep_study(a,dates,sma,start,end,v) for v in modes},
          "actualHeldInFullRun":{name:episode_equity({"points":r["points"]},start,end) for name,r in curves.items()}}
        episode_results[id]=focus
        print("EVENT",id,json.dumps({"shock":drop_list,"returnPct":{mode:o["returnPct"] for mode,o in focus["modes"].items()},"full":{k:v["returnPct"] for k,v in focus["actualHeldInFullRun"].items()}},ensure_ascii=False),flush=True)
    file_event={"version":"00675L_CRISIS_BUYING_2026_V1","range":[BEGIN,END],"generatedAtUTC":datetime.now(timezone.utc).isoformat(),
      "study":STUDY,"capitalTWD":CAPITAL,
      "description":"Three preset event windows, each independent simulated 1m start in cash with no external cash injections. This event-only study is not directly comparable to a continuously held original portfolio.",
      "modeDefinitions":{
        "DAILY5_FULL":"First completed TWII daily close-to-close fall >=5%; buy all cash at next ETF open, hold to window end.",
        "DAILY4_FULL":"First completed TWII daily close-to-close fall >=4%; buy all cash at next ETF open, hold to window end.",
        "DD5_FULL":"First index close >=5% below trailing 60-session high; all cash next open.",
        "DD10_FULL":"First index close >=10% below trailing 60-session high; all cash next open.",
        "STAGGER_5_10_15_20":"At first index close 5%, 10%, 15%, 20% below trailing 60d high, deploy 25% initial 1m budget per threshold next open. Each tier used at most once per event. Hold all until event end.",
        "STAGGER_10_15_20_25":"As above at 10%, 15%, 20%, 25% drawdowns.",
        "WAIT_SMA10":"After index had first fallen 5% below its trailing 60-day high, wait for index daily close>SMA10*1.01; buy all cash next open, hold until same window end."
      },
      "costs":{"brokerEachSide":BROKER,"etfSaleTax":ETF_SELL_TAX,"slippageEachSide":SLIP},
      "eventWindows":"COVID 2020-02-20..2020-06-30; Tariff 2025-04-01..2025-06-30; Iran 2026-02-27..2026-06-30. These windows are historical selected events, NOT a blind forward selection.",
      "limitations":["A -5% threshold is evaluated at index CLOSE; intraday -5% which recovers by close does NOT trigger.",
        "All purchases fill the following session OPEN (no buy at the post-collapse close).",
        "The 60-session drawdown has a moving rolling anchor; stage thresholds do not necessarily mark identical absolute price levels.",
        "Event-only simulations begin fully in CASH for fair entry comparison, with no prior positions or additional funding.",
        "Continuous variants hold different reserve fractions; lower/higher returns may reflect different equity exposure rather than better timing.",
        "2026 Iran data already occurred and cannot serve as pristine out-of-sample validation.",
        "2008 crisis excluded because 00675L did not trade until 2016; no fake 2008 ETF data."],
      "episodes":episode_results}
    (OUT/"events.json").write_text(json.dumps(file_event,ensure_ascii=False,indent=2),encoding="utf-8")
    rep={"version":"00675L_CRASH_RESERVE_2018_2026_V1","generatedAtUTC":file_event["generatedAtUTC"],
      "controlValidated":True,"fullResults":{k:{"endTWD":v["endTWD"],"returnPct":v["returnPct"],"mddPct":v["mddPct"]} for k,v in curves.items()},
      "sleeve": {"trades":crash["trades"],"unallocatedEndTWD":crash["final"]},
      "eventFile":"00675l_crash_entry/events.json","dataQuality":quality,"warnings":file_event["limitations"]}
    (OUT/"summary.json").write_text(json.dumps(rep,ensure_ascii=False,indent=2),encoding="utf-8")
    repo="https://github.com/jacky-168168/Tradingview-testing"
    study={"id":STUDY,"title":"00675L｜疫情、關稅、伊朗戰爭：急跌分批買 vs SMA10",
      "description":"2018–2026全期間：100% SMA10對照，75%趨勢＋25%股災備用金，50%趨勢＋50%備用金；另附2020疫情、2025關稅、2026伊朗戰爭三段獨立事件入場測試。",
      "period":[BEGIN,END],"sessions":2128,"models":all_models,
      "warnings":file_event["limitations"][:5],
      "dataQuality":"Yahoo 台指+00675L相同2128交易日；原始SMA10急跌4%策略逐筆核對；以先前收盤訊號於下一開盤成交，未加入任何資金。",
      "sourceBranch":"main",
      "sourceSummary":repo+"/blob/main/tw-stock-dashboard/docs/data/research/etf_history/00675l_crash_entry/summary.json",
      "sourceExecution":repo+"/actions/runs/"+os.environ.get("GITHUB_RUN_ID",""),
      "extraSource":repo+"/blob/main/tw-stock-dashboard/docs/data/research/etf_history/00675l_crash_entry/events.json"}
    archive["studies"]=[s for s in archive["studies"] if s["id"]!=STUDY]+[study]
    archive["studyOrder"]=[s for s in archive.get("studyOrder",[]) if s!=STUDY]+[STUDY]
    archive["generatedAtUTC"]=file_event["generatedAtUTC"]
    (DATA/"index.json").write_text(json.dumps(archive,ensure_ascii=False,separators=(",",":")),encoding="utf-8")
    assert all(len(z["points"])==2128 for z in curves.values()) and len(all_models)==3
    print("CRISIS_COMPLETE",json.dumps({"full":rep["fullResults"],"events":{k:{mode:o["returnPct"] for mode,o in v["modes"].items()} for k,v in episode_results.items()}},ensure_ascii=False),flush=True)
if __name__=="__main__":main()
