"""Frozen 00675L exit study: change ONLY cash-to-ETF reentry trigger from TWII SMA10+1% to SMA5.
Benchmark is IDX_DROP_4 from 00675_risk_v2. Inputs 2018-01-02 through 2026-10-07.
Causal prior close signal / next trading open execution, same cash/fee/slippage model.
"""
from __future__ import annotations
import json,os,math
from pathlib import Path
from dataclasses import replace
from datetime import datetime,timezone
import numpy as np
from research_00675l_vwma5_sma10_2018_2026 import index_data
from research_00675l_ma_family_2020_2026 import ma_array
from research_00675l_swing_grid import CAPITAL,SLIP,BROKER,ETF_SELL_TAX
from research_00675l_exit_entry_v2 import simulate as old_simulate,rule,trailing_ok,publicstats
ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/"docs/data/research/etf_history"
OUT=DATA/"00675l_sma5_entry"
STUDY="00675_sma5_entry"
BEGIN="2018-01-02";END="2026-10-07"
BASE=rule("IDX_DROP_4","原版｜SMA10＋1%買回",panic_index=.04)
CASES=[
 ("SMA5_ABOVE","台指收盤站上SMA5即買回",5,0.0,1,False),
 ("SMA5_05","台指SMA5＋0.5%買回",5,.005,1,False),
 ("SMA5_1","台指SMA5＋1%買回",5,.01,1,False),
 ("SMA5_2CONF","台指站上SMA5連續2日買回",5,0.,2,False),
 ("SMA5_CROSS","台指從下向上穿越SMA5買回",5,0.,1,True)
]
def run(a,dates,entry_ma,entry_buffer=0.,entry_days=1,cross=False,begin=BEGIN,end=END,details=False,exit_n=10):
    xs=np.flatnonzero((dates>=begin)&(dates<=end))
    if len(xs)<40:raise ValueError("Too few trading sessions")
    exit_ma=ma_array(a["twii"],None,"SMA",exit_n)
    idx=a["twii"];etf=a["close"];cash=float(CAPITAL);shares=0;holding=False;last_sell=-9999;orders=[];equity=[];cashdays=0
    buy_factor=(1+SLIP)*(1+BROKER);sell_factor=(1-SLIP)*(1-BROKER-ETF_SELL_TAX)
    for pos,i in enumerate(xs):
        date=str(dates[i]);o=float(a["open"][i]);cl=float(etf[i]);j=i-1
        if pos==0:want=True
        elif holding:
            trend_exit=trailing_ok(idx,exit_ma,j,3,.02,False)
            panic=j>=1 and idx[j]/idx[j-1]-1<=-.04
            want=not(trend_exit or panic)
            if not want:reason="panic_index" if panic else "risk_off"
        else:
            buy=trailing_ok(idx,entry_ma,j,entry_days,entry_buffer,True)
            if cross:buy=buy and j>=1 and np.isfinite(entry_ma[j-1]) and idx[j-1]<=entry_ma[j-1]*(1+entry_buffer)
            want=buy
        if pos==0 or want!=holding:
            holding=want
            gross=cash+shares*o*sell_factor
            target=int(max(0,gross*(1 if holding else 0))//(o*buy_factor))
            if target<shares:
                n=shares-target;v=n*o*sell_factor;cash+=v;shares-=n;last_sell=pos
                orders.append([date,"SELL",reason if pos else "risk_off",int(n),round(o,5),round(v,2),round(cash,2)])
            elif target>shares:
                n=min(target-shares,int(cash//(o*buy_factor)))
                if n>0:
                    v=n*o*buy_factor;cash-=v;shares+=n
                    orders.append([date,"BUY","risk_on",int(n),round(o,5),round(-v,2),round(cash,2)])
        if not holding:cashdays+=1
        equity.append([date,round(cash+shares*cl*sell_factor,2)])
    if shares:
        last_i=xs[-1];v=shares*float(etf[last_i])*sell_factor;cash+=v
        orders.append([str(dates[last_i]),"SELL","period_end",int(shares),None,round(v,2),round(cash,2)])
        equity[-1][1]=round(cash,2)
    vals=np.array([z[1] for z in equity]);peak=np.maximum.accumulate(np.r_[CAPITAL,vals])[1:]
    annual=[];last=float(CAPITAL)
    for year in sorted({z[0][:4] for z in equity}):
        wealth=next(v for day,v in reversed(equity) if day.startswith(year))
        annual.append({"year":year,"pct":round((wealth/last-1)*100,3),"wealthTWD":wealth,"wealthUSD":None,"usdPct":None})
        last=wealth
    z={"start":equity[0][0],"end":equity[-1][0],"returnPct":round((cash/CAPITAL-1)*100,3),
       "endNTD":round(cash,2),"mddPct":round(float(np.min((vals/peak-1)*100)),3),
       "riskOffSells":sum(o[1]=="SELL" and o[2]!="period_end" for o in orders),
       "riskOnReentries":max(0,sum(o[1]=="BUY" for o in orders)-1),
       "riskOffSessions":cashdays,"sessions":len(xs),"annual":annual}
    if details:z.update(points=equity,orders=orders)
    return z
def main():
    DATA.mkdir(parents=True,exist_ok=True);OUT.mkdir(parents=True,exist_ok=True);(DATA/"curves").mkdir(parents=True,exist_ok=True)
    _,a,dates,quality=index_data()
    sma10=ma_array(a["twii"],None,"SMA",10)
    legacy=old_simulate(a,dates,BASE,sma10,details=True)
    control=run(a,dates,sma10,.01,1,False,details=True)
    for key in ("returnPct","endNTD","mddPct","riskOffSells","riskOnReentries","riskOffSessions"):
        assert control[key]==legacy[key],(key,control[key],legacy[key])
    assert control["orders"]==legacy["orders"],"Baseline exact order parity failed"
    assert control["points"]==legacy["points"],"Baseline daily account parity failed"
    assert control["returnPct"]==4194.082,control["returnPct"]
    print("PARITY_SMA10_PLUS_PANIC4_OK",json.dumps(publicstats(control)),flush=True)
    index_path=DATA/"index.json";ix=json.loads(index_path.read_text(encoding="utf-8"))
    old_study=next(x for x in ix["studies"] if x["id"]=="00675_risk_v2")
    old_m=next(x for x in old_study["models"] if x["id"]=="IDX_DROP_4")
    assert old_m["endTWD"]==control["endNTD"],"Archived control changed"
    periods={"training_2018_2023":("2018-01-02","2023-12-31"),"validation_2024_2025":("2024-01-01","2025-12-31"),
             "audit_2026":("2026-01-01",END)}
    studies=[("SMA10_BASE","原版｜台指SMA10＋1%買回",10,.01,1,False)]+CASES+[("SMA5_EXIT","台指SMA5買回＋SMA5跌2%連3日出場＋急跌4%保護",5,0.,1,False,5)]
    models=[];summary={}
    for spec in studies:
        id,title,n,buf,days,cross=spec[:6]
        exit_n=spec[6] if len(spec)>6 else 10
        entry_ma=ma_array(a["twii"],None,"SMA",n)
        z=run(a,dates,entry_ma,buf,days,cross,details=True,exit_n=exit_n)
        stats={p:publicstats(run(a,dates,entry_ma,buf,days,cross,beg,end,exit_n=exit_n)) for p,(beg,end) in periods.items()}
        if id=="SMA10_BASE":assert z["orders"]==control["orders"]
        path="curves/"+STUDY+"__"+id+".json"
        payload={"study":STUDY,"id":id,"currency":"TWD","columns":["date","equity"],"points":z["points"],
                 "tradeColumns":["date","side","phase","units","unitPrice","cashFlow","cashAfter"],"trades":z["orders"]}
        (DATA/path).write_text(json.dumps(payload,ensure_ascii=False,separators=(",",":")),encoding="utf-8")
        record={"id":id,"name":title,"group":"原版對照" if id=="SMA10_BASE" else "SMA5買回",
             "endTWD":z["endNTD"],"returnPct":z["returnPct"],"mddPct":z["mddPct"],
             "sells":z["riskOffSells"],"rebuys":z["riskOnReentries"],"cashDays":z["riskOffSessions"],
             "sessions":z["sessions"],"annual":z["annual"],"curve":path,"curveCurrency":"TWD",
             "notes":f"賣出：台指低於SMA{exit_n}之98%連3日或單日跌4%；買回：站上SMA{n}之{100*buf:g}%"+("，只接受從下向上突破" if cross else f"，連續{days}日")+"；期初2018/1/2開盤強制建倉。固定手續費/稅/滑價。",
             "splitResults":stats,"entryMA":n,"exitMA":exit_n,"entryBufferPct":round(100*buf,2),"entryConfirmDays":days,"crossOnly":cross}
        models.append(record);summary[id]={"continuous":publicstats(z),"segments":stats}
        print("CASE_"+id,json.dumps({"total":z["returnPct"],"endingTWD":z["endNTD"],"mdd":z["mddPct"],"sells":z["riskOffSells"],"train":stats["training_2018_2023"]["returnPct"],"valid":stats["validation_2024_2025"]["returnPct"],"audit":stats["audit_2026"]["returnPct"]},ensure_ascii=False),flush=True)
    meta={"version":"00675L_SMA5_REENTRY_V1","generatedAtUTC":datetime.now(timezone.utc).isoformat(),
          "ticker":"00675L.TW","signal":"^TWII","period":[BEGIN,END],"capitalNTD":CAPITAL,"samples":len(control["points"]),
          "sharedSellRule":"3 consecutive TWII closes < own SMA10*0.98 OR TWII daily close-to-close return <= -4%",
          "reentryInterpretation":"When FLAT, prior completed TWII close > prior same-day SMA5, no +1% buffer. Not a crossover-only requirement.",
          "fills":"The day after signal at ETF open, including gap. Full available cash with integer shares; no margin.",
          "initialPosition":"On 2018-01-02 open, force buy exactly as historical original, irrespective of entry indicator.",
          "feeRateEachSide":BROKER,"etfSellTax":ETF_SELL_TAX,"slippageEachSide":SLIP,
          "exactControlParity":True,"models":summary,"dataQuality":quality,
          "warnings":["2018–2026 has been analyzed in earlier studies; 2026 is NOT a pristine holdout.",
                      "SMA5 variants are exploratory: if their results are inspected to choose a winner, consider the selection hindsight-biased.",
                      "Historical adjusted Yahoo prices can differ from TradingView corporate-action price policy.",
                      "Fast re-entry can increase round trips; report turnover and risk in addition to return.",
                      "Independent split tests reset to NT$1m at the segment start, while annual rows are continuous compounding."]}
    (OUT/"summary.json").write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding="utf-8")
    repo="https://github.com/jacky-168168/Tradingview-testing"
    desc={"id":STUDY,"title":"00675L｜SMA5 買回 vs SMA10 原版｜2018～2026",
       "description":"原版SMA10對照、5組SMA5買回且SMA10出場，以及新增SMA5買回且SMA5跌2%連3日出場；全系列維持台指單日跌4%急跌保護。",
       "period":[BEGIN,END],"sessions":2128,"models":models,
       "warnings":meta["warnings"][:4],"dataQuality":"2018～2026 共2,128個交易日，原版逐日淨值與逐筆訂單完全一致。SMA5定義為指數收盤高於自身5日簡單均線；不是ETF自身均線。",
       "sourceBranch":"main",
       "sourceSummary":repo+"/blob/main/tw-stock-dashboard/docs/data/research/etf_history/00675l_sma5_entry/summary.json",
       "sourceExecution":repo+"/actions/runs/"+os.environ.get("GITHUB_RUN_ID",""),
       "extraSource":repo+"/blob/main/tw-stock-dashboard/scripts/research_00675l_sma5_entry.py"}
    ix["studies"]=[s for s in ix["studies"] if s["id"]!=STUDY]+[desc]
    ix["studyOrder"]=[s for s in ix.get("studyOrder",[]) if s!=STUDY]+[STUDY]
    ix["generatedAtUTC"]=meta["generatedAtUTC"]
    index_path.write_text(json.dumps(ix,ensure_ascii=False,separators=(",",":")),encoding="utf-8")
    assert len(models)==7 and all((DATA/m["curve"]).exists() for m in models)
    assert next(m for m in models if m["id"]=="SMA5_EXIT")["entryMA"]==next(m for m in models if m["id"]=="SMA5_EXIT")["exitMA"]==5
    assert next(m for m in models if m["id"]=="SMA5_ABOVE")["exitMA"]==10
    print("SMA5_ENTRY_RESULT",json.dumps({"study":STUDY,"models":len(models),"period":[BEGIN,END],"sma5":summary["SMA5_ABOVE"],"base":summary["SMA10_BASE"]},ensure_ascii=False),flush=True)
if __name__=="__main__":main()
