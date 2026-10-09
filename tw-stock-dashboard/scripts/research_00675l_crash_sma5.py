"""00675L shock-triggered SMA5 recovery entry vs frozen SMA10+1%, 2018-2026.
Rules: same initial full investment, SMA10<-2% for 3 closes or TWII down 4% exit;
while flat, allow normal SMA10+1% reentry OR (after prior crisis, close>SMA5).
Studies distinguish each-day -4%, all-red X days totalling -4%, and rolling X-day -4%.
Uses prior session's completed TWII signals -> next 00675L open. No new capital.
"""
from __future__ import annotations
import json,os
from pathlib import Path
from datetime import datetime,timezone
import numpy as np
from research_00675l_vwma5_sma10_2018_2026 import index_data
from research_00675l_ma_family_2020_2026 import ma_array
from research_00675l_swing_grid import CAPITAL,SLIP,BROKER,ETF_SELL_TAX
from research_00675l_exit_entry_v2 import simulate,rule,trailing_ok,publicstats
ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/"docs/data/research/etf_history";OUT=DATA/"00675l_crash_sma5"
STUDY="00675_crash_sma5";BEGIN="2018-01-02";END="2026-10-07"
BF=(1+SLIP)*(1+BROKER);SF=(1-SLIP)*(1-BROKER-ETF_SELL_TAX)
EVENTS={"COVID_2020":("2020-02-20","2020-06-30"),"TARIFF_2025":("2025-04-01","2025-06-30"),
        "IRAN_2026":("2026-02-27","2026-06-30")}
def signal(idx,kind,n):
    mask=np.zeros(len(idx),dtype=bool)
    for j in range(n,len(idx)):
        q=float(idx[j]/idx[j-n]-1.)
        if kind=="each4":
            mask[j]=all(idx[k]/idx[k-1]-1<=-.04 for k in range(j-n+1,j+1))
        elif kind=="red4":
            mask[j]=q<=-.04 and all(idx[k]<idx[k-1] for k in range(j-n+1,j+1))
        else:
            mask[j]=q<=-.04
    return mask
def test(a,dates,sma10,sma5,mask,window,begin=BEGIN,end=END,details=False):
    xs=np.flatnonzero((dates>=begin)&(dates<=end))
    idx=a["twii"];etf=a["close"]
    cash=float(CAPITAL);shares=0;holding=False;equity=[];trades=[];cashdays=0;extra=0;special_dates=[]
    for pos,i in enumerate(xs):
        dt=str(dates[i]);o=float(a["open"][i]);cl=float(etf[i]);j=i-1;reason="risk_on"
        if pos==0:want=True
        elif holding:
            trend=trailing_ok(idx,sma10,j,3,.02,False)
            panic=j>=1 and idx[j]/idx[j-1]-1<=-.04
            want=not(trend or panic)
            if not want:reason="panic_index" if panic else "risk_off"
        else:
            old=trailing_ok(idx,sma10,j,1,.01,True)
            after_crash=window>0 and np.any(mask[max(0,j-window+1):j+1])
            fast=after_crash and j>=0 and np.isfinite(sma5[j]) and idx[j]>sma5[j]
            want=old or fast
            if want and fast and not old:
                reason="crash_sma5";extra+=1;special_dates.append(dt)
        if pos==0 or want!=holding:
            holding=want
            gross=cash+shares*o*SF
            target=int(max(0,gross*(1 if holding else 0))//(o*BF))
            if target<shares:
                n=shares-target;v=n*o*SF;cash+=v;shares-=n
                trades.append([dt,"SELL",reason,int(n),round(o,5),round(v,2),round(cash,2)])
            elif target>shares:
                n=min(target-shares,int(cash//(o*BF)))
                if n>0:
                    v=n*o*BF;cash-=v;shares+=n
                    trades.append([dt,"BUY",reason,int(n),round(o,5),round(-v,2),round(cash,2)])
        if not holding:cashdays+=1
        equity.append([dt,round(cash+shares*cl*SF,2)])
    if shares:
        i=xs[-1];v=shares*float(etf[i])*SF;cash+=v
        trades.append([str(dates[i]),"SELL","period_end",int(shares),None,round(v,2),round(cash,2)])
        equity[-1][1]=round(cash,2)
    vals=np.array([x[1] for x in equity]);peaks=np.maximum.accumulate(np.r_[CAPITAL,vals])[1:]
    annual=[];prev=float(CAPITAL)
    for yr in sorted({x[0][:4] for x in equity}):
        w=next(z[1] for z in reversed(equity) if z[0].startswith(yr))
        annual.append({"year":yr,"pct":round((w/prev-1)*100,3),"wealthTWD":w,"wealthUSD":None,"usdPct":None});prev=w
    stats={"start":equity[0][0],"end":equity[-1][0],"returnPct":round((cash/CAPITAL-1)*100,3),
          "endNTD":round(cash,2),"mddPct":round(float(np.min((vals/peaks-1)*100)),3),
          "riskOffSells":sum(z[1]=="SELL" and z[2]!="period_end" for z in trades),
          "riskOnReentries":max(0,sum(z[1]=="BUY" for z in trades)-1),"riskOffSessions":cashdays,
          "sma5OverrideBuys":extra,"sma5OverrideDates":special_dates,"sessions":len(xs),"annual":annual}
    if details:stats.update(points=equity,orders=trades)
    return stats
def event_slice(points,lo,hi):
    active=[x for x in points if lo<=x[0]<=hi]
    start_idx=next(j for j,x in enumerate(points) if x[0]==active[0][0])
    before=points[start_idx-1][1] if start_idx else float(CAPITAL)
    values=np.array([z[1] for z in active]);peaks=np.maximum.accumulate(np.r_[before,values])[1:]
    return {"period":[active[0][0],active[-1][0]],"returnPct":round((values[-1]/before-1)*100,3),
            "maxDrawdownPct":round(float(np.min((values/peaks-1)*100)),3)}
def main():
    OUT.mkdir(parents=True,exist_ok=True);(DATA/"curves").mkdir(parents=True,exist_ok=True)
    _,a,dates,quality=index_data()
    sma10=ma_array(a["twii"],None,"SMA",10);sma5=ma_array(a["twii"],None,"SMA",5)
    prior=simulate(a,dates,rule("BASE","SMA10原始+急跌4%",panic_index=.04),sma10,details=True)
    control=test(a,dates,sma10,sma5,np.zeros(len(dates),dtype=bool),0,details=True)
    for k in ("returnPct","endNTD","mddPct","riskOffSells","riskOnReentries","riskOffSessions"):
        assert prior[k]==control[k],(k,prior[k],control[k])
    assert prior["orders"]==control["orders"],"Control orders mismatch"
    assert prior["points"]==control["points"],"Control account curve mismatch"
    assert prior["returnPct"]==4194.082 and len(prior["points"])==2128
    archive=json.loads((DATA/"index.json").read_text(encoding="utf-8"))
    frozen=next(m for m in next(x for x in archive["studies"] if x["id"]=="00675_risk_v2")["models"] if m["id"]=="IDX_DROP_4")
    assert frozen["endTWD"]==control["endNTD"] and frozen["mddPct"]==control["mddPct"]
    print("PARITY_OK",json.dumps(publicstats(control)),flush=True)
    variants=[("BASE","基準｜台指SMA10＋1%買回",None,0,0)]
    desc={"each4":"每一天跌幅≥4%","red4":"連續收跌且累計≥4%","total4":"X日累積跌幅≥4%"}
    for typ,n in [("each4",1),("each4",2),("each4",3),
                  ("red4",2),("red4",3),("total4",2),("total4",3)]:
        for w in (5,10,20):
            variants.append((f"{typ.upper()}_{n}D_W{w}",f"{desc[typ]}｜X={n}｜{w}日內SMA5買回",typ,n,w))
    masks={(typ,n):signal(a["twii"],typ,n) for _,_,typ,n,w in variants if typ is not None}
    split_periods={"training_2018_2023":("2018-01-02","2023-12-31"),
          "validation_2024_2025":("2024-01-01","2025-12-31"),
          "audit_2026":("2026-01-01",END)}
    models=[];cases={};indexdates=[str(d) for d in dates]
    for ident,title,typ,n,w in variants:
        mask=np.zeros(len(dates),dtype=bool) if typ is None else masks[(typ,n)]
        out=control if typ is None else test(a,dates,sma10,sma5,mask,w,details=True)
        splits={k:test(a,dates,sma10,sma5,mask,w,start,stop) for k,(start,stop) in split_periods.items()}
        rel=f"curves/{STUDY}__{ident}.json"
        (DATA/rel).write_text(json.dumps({"study":STUDY,"id":ident,"currency":"TWD",
            "columns":["date","equity"],"points":out["points"],
            "tradeColumns":["date","side","phase","units","unitPrice","cashFlow","cashAfter"],"trades":out["orders"]},
            ensure_ascii=False,separators=(",",":")),encoding="utf-8")
        events={k:event_slice(out["points"],*bounds) for k,bounds in EVENTS.items()}
        models.append({"id":ident,"name":title,"group":"原始SMA10對照" if typ is None else "暴跌觸發SMA5提前買回",
            "endTWD":out["endNTD"],"returnPct":out["returnPct"],"mddPct":out["mddPct"],
            "sells":out["riskOffSells"],"rebuys":out["riskOnReentries"],"cashDays":out["riskOffSessions"],
            "sessions":2128,"annual":out["annual"],"curve":rel,"curveCurrency":"TWD",
            "notes":"原始SMA10+1%買回，跌破SMA10 2%連3日或台指單日跌4%即出場；空手時若近期已發生指定暴跌，且台指收盤>SMA5，可提前買回。"+("無提前買回" if typ is None else f"崩跌定義:{desc[typ]}, X={n}, 最長{w}日有效")+".隔日開盤成交；無外部注資；初始2018/1/2直接建倉。",
            "sma5OverrideBuys":out["sma5OverrideBuys"],"sma5OverrideDates":out["sma5OverrideDates"],
            "crashTriggerDays":int(mask.sum()),
            "rule":{"crashType":typ,"x":n,"validDays":w},
            "splitResults":{k:publicstats(v)|{"sma5OverrideBuys":v["sma5OverrideBuys"]} for k,v in splits.items()},
            "events":events})
        cases[ident]={"total":publicstats(out),"sma5OverrideBuys":out["sma5OverrideBuys"],
           "sma5OverrideDates":out["sma5OverrideDates"],"triggerDates":[indexdates[i] for i in np.flatnonzero(mask) if BEGIN<=indexdates[i]<=END],
           "split":{k:publicstats(v)|{"sma5OverrideBuys":v["sma5OverrideBuys"]} for k,v in splits.items()},
           "episodes":events}
        print("TEST",ident,json.dumps({"pct":out["returnPct"],"mdd":out["mddPct"],
            "trigger":int(mask.sum()),"earlierBuys":out["sma5OverrideBuys"],
            "validPct":splits["validation_2024_2025"]["returnPct"]},ensure_ascii=False),flush=True)
    besttrain=sorted([m for m in models if m["id"]!="BASE"],key=lambda m:m["splitResults"]["training_2018_2023"]["returnPct"],reverse=True)[:5]
    data={"version":"00675_CRASH_SMA5_REENTRY_2026_V1","generatedAtUTC":datetime.now(timezone.utc).isoformat(),
          "study":STUDY,"period":[BEGIN,END],"currency":"TWD","principal":CAPITAL,
          "method":"TWII close signals with no lookahead; next TWSE 00675L open execution. 100% cash deployed initially; no credit, no capital injection.",
          "normalSell":"TWII below own SMA10*(1-0.02) 3 closes OR a single TWII session daily decline >=4%; next open full liquidation.",
          "reentry":"Normal: TWII close>SMA10*1.01. Crash override: a qualifying X-day TWII crash in previous W trading sessions AND TWII close>SMA5. First condition wins if both.",
          "crashDefs":desc,"crashN":[1,2,3],"lookbackDays":[5,10,20],
          "fees":{"brokerEachSide":BROKER,"etfSellTax":ETF_SELL_TAX,"slippageEachSide":SLIP},
          "controlExactTradeParity":True,"testCount":len(models)-1,"caseResults":cases,
          "trainTop5":besttrain,"dataQuality":quality,
          "warnings":["Each-day -4% for multiple consecutive days is exceedingly rare; inspect triggerDays and override buys, not only returns.",
            "Rolling X-day cumulative -4% and strictly X consecutive down days totalling -4% are different definitions.",
            "All windows 5, 10, 20 and X=1,2,3 are post-hoc exploratory comparisons; picking best retrospectively may overfit.",
            "2026 and all three crises already studied before and NOT pristine out-of-sample.",
            "Crisis examples are within the whole continuously invested strategy, not independently new cash positions.",
            "Index crash and SMA5 recovery are based on confirmed CLOSE; ETF trades NEXT session open including opening gaps."]}
    (OUT/"summary.json").write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding="utf-8")
    repo="https://github.com/jacky-168168/Tradingview-testing"
    study={"id":STUDY,"title":"00675L｜連跌X日 4%後SMA5提前買回｜2018～2026",
        "description":"與SMA10＋台指急跌4%原始版同源回測：若X天每天下跌4%、連續下跌合計4%、或X日累跌4%，在5/10/20天內站上SMA5提前買回。21個配置＋原版、疫情／關稅／伊朗戰爭事件檢驗。",
        "period":[BEGIN,END],"sessions":2128,"models":models,
        "warnings":data["warnings"][:4],
        "dataQuality":"與原版2128根日K逐筆／逐日淨值完全核對，無新增現金。SMA5只在已發生暴跌後當作提前買回條件。",
        "sourceBranch":"main",
        "sourceSummary":repo+"/blob/main/tw-stock-dashboard/docs/data/research/etf_history/00675l_crash_sma5/summary.json",
        "sourceExecution":repo+"/actions/runs/"+os.environ.get("GITHUB_RUN_ID",""),
        "extraSource":repo+"/blob/main/tw-stock-dashboard/scripts/research_00675l_crash_sma5.py"}
    archive["studies"]=[s for s in archive["studies"] if s["id"]!=STUDY]+[study]
    archive["studyOrder"]=[s for s in archive.get("studyOrder",[]) if s!=STUDY]+[STUDY]
    archive["generatedAtUTC"]=data["generatedAtUTC"]
    (DATA/"index.json").write_text(json.dumps(archive,ensure_ascii=False,separators=(",",":")),encoding="utf-8")
    assert len(models)==22 and all(len(json.loads((DATA/x["curve"]).read_text())["points"])==2128 for x in models)
    print("CRASH_SMA5_COMPLETE",json.dumps({"base":cases["BASE"]["total"],"topTrain":[{"id":m["id"],"train":m["splitResults"]["training_2018_2023"]["returnPct"],"all":m["returnPct"],"mdd":m["mddPct"],"overrideBuys":m["sma5OverrideBuys"]} for m in besttrain]},ensure_ascii=False),flush=True)
if __name__=="__main__":main()
