"""00675L 2018–2026 SMA10 entry/exit stress study, replaying frozen legacy cash execution.
Research-only; ranking uses 2018–23, 2024–25 is validation, 2026 is a previously inspected audit.
Writes a *new* ETF archive study; does not alter any historical archive models or signals.
"""
from __future__ import annotations
import os,json,math,itertools
from datetime import datetime,timezone
from pathlib import Path
from dataclasses import dataclass,replace
import numpy as np,pandas as pd
from research_00675l_vwma5_sma10_2018_2026 import index_data,backtest
from research_00675l_ma_family_2020_2026 import ma_array,mkcfg
from research_00675l_swing_grid import CAPITAL,SLIP,BROKER,ETF_SELL_TAX
ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/"docs/data/research/etf_history"
OUT=DATA/"00675l_risk_v2"
STUDY="00675_risk_v2"
BEGIN="2018-01-02";END="2026-10-07"
@dataclass(frozen=True)
class Rule:
    id:str
    name:str
    n:int=10
    exit_buffer:float=.02
    entry_buffer:float=.01
    exit_days:int=3
    entry_days:int=1
    panic_index:float=0.
    panic_etf:float=0.
    panic_index2:float=0.
    cooldown:int=0
    initial_guard:bool=False
    note:str=""
def rule(id,name,**kw):return Rule(id=id,name=name,**kw)
def candidates():
    base=[rule("BASE","原始 SMA10｜跌2%連3日／回1%",note="完全沿用舊版訊號與期初強制建倉"),
      rule("EXIT_2","出場加快｜2日確認",exit_days=2),
      rule("EXIT_1","出場加快｜1日確認",exit_days=1),
      rule("ENTRY_2","買回連2日",entry_days=2),
      rule("ENTRY_3","買回連3日",entry_days=3),
      rule("IDX_DROP_2","台指單日急跌2%保護",panic_index=.02),
      rule("IDX_DROP_3","台指單日急跌3%保護",panic_index=.03),
      rule("IDX_DROP_4","台指單日急跌4%保護",panic_index=.04),
      rule("ETF_DROP_5","00675L 單日急跌5%保護",panic_etf=.05),
      rule("IDX_2D_DROP_4","台指兩日跌4%保護",panic_index2=.04),
      rule("IDX_DROP3_ENTRY2","急跌3%＋買回連2日",panic_index=.03,entry_days=2),
      rule("EXIT2_ENTRY2","出場2日＋買回2日",exit_days=2,entry_days=2),
      rule("EXIT2_PANIC3","出場2日＋急跌3%",exit_days=2,panic_index=.03),
      rule("EXIT2_PANIC3_ENTRY2","出場2日＋急跌3%＋買回2日",exit_days=2,panic_index=.03,entry_days=2),
      rule("PANIC3_ENTRY2_CD2","急跌3%＋買回2日＋冷卻2日",panic_index=.03,entry_days=2,cooldown=2),
      rule("PANIC3_ENTRY2_CD5","急跌3%＋買回2日＋冷卻5日",panic_index=.03,entry_days=2,cooldown=5),
      rule("EXIT2_PANIC3_ENTRY2_CD2","2日出場＋急跌3%＋2日買回＋冷卻2日",exit_days=2,panic_index=.03,entry_days=2,cooldown=2),
      rule("INITIAL_FILTER","期初訊號符合才進場",initial_guard=True),
      rule("INITIAL_FILTER_RISK","期初確認＋2日出場＋急跌3%＋買回2日",initial_guard=True,exit_days=2,panic_index=.03,entry_days=2)]
    return base
def trailing_ok(prices,ma,j,days,buffer,above):
    if j-days+1<0:return False
    for k in range(j-days+1,j+1):
        if not np.isfinite(ma[k]) or not np.isfinite(prices[k]):return False
        if above:
            if not prices[k]>ma[k]*(1+buffer):return False
        elif not prices[k]<ma[k]*(1-buffer):return False
    return True
def simulate(a,dates,c,ma,begin=BEGIN,end=END,details=False):
    xs=np.flatnonzero((dates>=begin)&(dates<=end))
    if len(xs)<40:raise ValueError("Too few market sessions")
    cash=float(CAPITAL);shares=0;holding=False;last_sell=-9999;trades=[];equity=[];cashdays=0
    buy_factor=(1+SLIP)*(1+BROKER);sell_factor=(1-SLIP)*(1-BROKER-ETF_SELL_TAX)
    idx=a["twii"];etf=a["close"]
    for pos,i in enumerate(xs):
        date=str(dates[i]);open_px=float(a["open"][i]);close_px=float(etf[i]);j=i-1
        if pos==0:
            want=True if not c.initial_guard else trailing_ok(idx,ma,j,c.entry_days,c.entry_buffer,True)
        elif holding:
            ordinary=trailing_ok(idx,ma,j,c.exit_days,c.exit_buffer,False)
            pidx=c.panic_index>0 and j>=1 and idx[j]/idx[j-1]-1<=-c.panic_index
            petf=c.panic_etf>0 and j>=1 and etf[j]/etf[j-1]-1<=-c.panic_etf
            pidx2=c.panic_index2>0 and j>=2 and idx[j]/idx[j-2]-1<=-c.panic_index2
            want=not (ordinary or pidx or petf or pidx2)
            if not want:reason=("panic_index" if pidx else "panic_etf" if petf else "panic_index2" if pidx2 else "risk_off")
        else:
            want=pos-last_sell>c.cooldown and trailing_ok(idx,ma,j,c.entry_days,c.entry_buffer,True)
        if pos==0 or want!=holding:
            prior=holding;holding=want
            gross=cash+shares*open_px*sell_factor
            target=int(max(0,gross*(1 if holding else 0))//(open_px*buy_factor))
            if target<shares:
                n=shares-target;v=n*open_px*sell_factor;cash+=v;shares-=n;last_sell=pos
                trades.append([date,"SELL",reason if pos else "risk_off",int(n),round(open_px,5),round(v,2),round(cash,2)])
            elif target>shares:
                n=min(target-shares,int(cash//(open_px*buy_factor)))
                if n>0:
                    v=n*open_px*buy_factor;cash-=v;shares+=n
                    trades.append([date,"BUY","risk_on" if prior or pos else "risk_on",int(n),round(open_px,5),round(-v,2),round(cash,2)])
        if not holding:cashdays+=1
        equity.append([date,round(cash+shares*close_px*sell_factor,2)])
    if shares:
        i=xs[-1];amount=shares*float(etf[i])*sell_factor;cash+=amount
        trades.append([str(dates[i]),"SELL","period_end",int(shares),None,round(amount,2),round(cash,2)])
        shares=0;equity[-1][1]=round(cash,2)
    vals=np.array([x[1] for x in equity]);peaks=np.maximum.accumulate(np.r_[CAPITAL,vals])[1:]
    years=[];last=float(CAPITAL)
    for year in sorted(set(x[0][:4] for x in equity)):
        wealth=next(v for day,v in reversed(equity) if day.startswith(year))
        years.append(dict(year=year,pct=round((wealth/last-1)*100,3),wealthTWD=wealth,wealthUSD=None,usdPct=None))
        last=wealth
    res=dict(start=equity[0][0],end=equity[-1][0],returnPct=round((cash/CAPITAL-1)*100,3),
         endNTD=round(cash,2),mddPct=round(float(np.min((vals/peaks-1)*100)),3),
         riskOffSells=sum(t[1]=="SELL" and t[2]!="period_end" for t in trades),
         riskOnReentries=max(0,sum(t[1]=="BUY" for t in trades)-1),
         riskOffSessions=cashdays,sessions=len(xs),annual=years)
    if details:res.update(points=equity,orders=trades)
    return res
def asrule(c):
    return {k:getattr(c,k) for k in c.__dataclass_fields__ if k not in ("name","note")}
def publicstats(z):
    return {k:z[k] for k in ("returnPct","endNTD","mddPct","riskOffSells","riskOnReentries","riskOffSessions")}
def emit():
    OUT.mkdir(parents=True,exist_ok=True);(DATA/"curves").mkdir(parents=True,exist_ok=True)
    d,a,dates,quality=index_data()
    sma10=ma_array(a["twii"],None,"SMA",10)
    orig=backtest(a,dates,mkcfg("SMA","twii",10,.02,.01,3),sma10,BEGIN,END,detailed=True)
    base=simulate(a,dates,candidates()[0],sma10,details=True)
    for k in ("returnPct","endNTD","mddPct","riskOffSells","riskOnReentries","riskOffSessions"):
        if base[k]!=orig[k]:raise AssertionError(f"Legacy simulator mismatch {k}: {base[k]} != {orig[k]}")
    legacyOrders=[(t["date"],t["side"],t["phase"],t["units"]) for t in orig["orders"]]
    modernOrders=[(t[0],t[1],t[2],t[3]) for t in base["orders"]]
    assert modernOrders==legacyOrders,("Orders mismatch",modernOrders[:5],legacyOrders[:5])
    assert len(base["points"])==2128 and base["points"][-1][0]==END
    print("BASELINE_PARITY",json.dumps(publicstats(base)),flush=True)
    # PRE-SPECIFIED candidates: no ranking using 2026, compare all fairly with same input and costs.
    display=candidates();records=[];summaries={}
    archive=json.loads((DATA/"index.json").read_text(encoding="utf-8"))
    old=next(s for s in archive["studies"] if s["id"]=="00675_2018")
    prior=next(m for m in old["models"] if m["id"]=="SMA10_index_original_2_1")
    source_delta=base["returnPct"]-prior["returnPct"]
    for c in display:
        res=simulate(a,dates,c,sma10,details=True)
        splits={}
        for name,(begin,end) in {"training_2018_2023":("2018-01-02","2023-12-31"),
                                "validation_2024_2025":("2024-01-01","2025-12-31"),
                                "audit_2026":("2026-01-01",END)}.items():
            splits[name]=publicstats(simulate(a,dates,c,sma10,begin,end))
        fid=f"{STUDY}__{c.id}";rel=f"curves/{fid}.json"
        payload={"study":STUDY,"id":c.id,"currency":"TWD","columns":["date","equity"],"points":res["points"],
                 "tradeColumns":["date","side","phase","units","unitPrice","cashFlow","cashAfter"],"trades":res["orders"]}
        (DATA/rel).write_text(json.dumps(payload,ensure_ascii=False,separators=(",",":")),encoding="utf-8")
        records.append({"id":c.id,"name":c.name,"group":"原始版" if c.id=="BASE" else "進出場風控",
            "endTWD":res["endNTD"],"returnPct":res["returnPct"],"mddPct":res["mddPct"],
            "sells":res["riskOffSells"],"rebuys":res["riskOnReentries"],"cashDays":res["riskOffSessions"],
            "sessions":res["sessions"],"annual":res["annual"],"curve":rel,"curveCurrency":"TWD",
            "notes":c.note or f"出場{c.exit_days}日、進場{c.entry_days}日；指數急跌={100*c.panic_index:g}%、ETF急跌={100*c.panic_etf:g}%；冷卻{c.cooldown}日",
            "splitResults":splits,"rule":asrule(c)})
        summaries[c.id]={"continuous":publicstats(res),"splits":splits}
        print("CASE",c.id,json.dumps({"fullPct":res["returnPct"],"mdd":res["mddPct"],
              "validPct":splits["validation_2024_2025"]["returnPct"],"audit2026Pct":splits["audit_2026"]["returnPct"]}),flush=True)
    # NEIGHBORHOOD GRID scored on 2018-23 only; 2024-26 remains descriptive, never used to pick.
    grid=[]
    for n,ex,en,days,panic in itertools.product((8,10,12,15,20),(.01,.02,.03),(0.,.01,.02),(1,2,3),(0.,.03)):
        cfg=rule(f"G_{n}_{int(ex*100)}_{int(en*100)}_{days}_{int(panic*100)}","參數鄰域",
            n=n,exit_buffer=ex,entry_buffer=en,exit_days=days,panic_index=panic)
        ma=ma_array(a["twii"],None,"SMA",n)
        tr=simulate(a,dates,cfg,ma,"2018-01-02","2023-12-31")
        grid.append({"id":cfg.id,"n":n,"exitPct":round(ex*100,1),"entryPct":round(en*100,1),
          "exitDays":days,"panicPct":round(panic*100,1),
          "train":publicstats(tr),"trainScore":round(tr["returnPct"]-.5*abs(tr["mddPct"])-.3*tr["riskOffSells"],3)})
    grid.sort(key=lambda z:z["trainScore"],reverse=True)
    # Audit at most the top 3 training-ranked grid configurations; show full span with provenance.
    picks=[]
    for row in grid:
        if row["train"]["riskOffSells"]<3 or row["train"]["mddPct"]<-50:continue
        picks.append(row)
        if len(picks)==3:break
    for rank,r in enumerate(picks,1):
        cfg=rule(r["id"],f"訓練期優選第{rank}名｜SMA{r['n']}",n=r["n"],
            exit_buffer=r["exitPct"]/100,entry_buffer=r["entryPct"]/100,exit_days=r["exitDays"],
            panic_index=r["panicPct"]/100,note="僅依2018–2023訓練期選出，非真正未見樣本；2026曾在其他研究中被檢視")
        ma=ma_array(a["twii"],None,"SMA",cfg.n)
        full=simulate(a,dates,cfg,ma,details=True)
        splits={name:publicstats(simulate(a,dates,cfg,ma,lo,hi)) for name,(lo,hi) in {
            "training_2018_2023":("2018-01-02","2023-12-31"),"validation_2024_2025":("2024-01-01","2025-12-31"),
            "audit_2026":("2026-01-01",END)}.items()}
        rel=f"curves/{STUDY}__{cfg.id}.json"
        (DATA/rel).write_text(json.dumps({"study":STUDY,"id":cfg.id,"currency":"TWD",
            "columns":["date","equity"],"points":full["points"],
            "tradeColumns":["date","side","phase","units","unitPrice","cashFlow","cashAfter"],
            "trades":full["orders"]},ensure_ascii=False,separators=(",",":")),encoding="utf-8")
        records.append({"id":cfg.id,"name":cfg.name,"group":"訓練期優選（過擬合警示）",
            "endTWD":full["endNTD"],"returnPct":full["returnPct"],"mddPct":full["mddPct"],
            "sells":full["riskOffSells"],"rebuys":full["riskOnReentries"],"cashDays":full["riskOffSessions"],
            "sessions":full["sessions"],"annual":full["annual"],"curve":rel,
            "curveCurrency":"TWD","notes":cfg.note,"splitResults":splits,"rule":asrule(cfg)})
        summaries[cfg.id]={"continuous":publicstats(full),"splits":splits}
    # Complete 270 neighborhood tests: validate all on 2024-25 and inspect 2026 (no selection).
    for row in grid:
        cfg=rule(row["id"],"參數鄰域",n=row["n"],exit_buffer=row["exitPct"]/100,
            entry_buffer=row["entryPct"]/100,exit_days=row["exitDays"],panic_index=row["panicPct"]/100)
        ma=ma_array(a["twii"],None,"SMA",cfg.n)
        row["validation2024_2025"]=publicstats(simulate(a,dates,cfg,ma,"2024-01-01","2025-12-31"))
        row["audit2026"]=publicstats(simulate(a,dates,cfg,ma,"2026-01-01",END))
    (OUT/"grid.json").write_text(json.dumps({"version":"00675L_ENTRY_EXIT_GRID_V2","count":len(grid),
        "rankingBasis":"2018–2023 only, return - 0.5*abs(MDD) - 0.3*sell events",
        "selectionRule":"Top 3 qualifying >=3 exits and MDD>=-50% (train only)",
        "warnings":["Every 2026 observation is retrospective; prior studies exposed that year.","Splits are individually initialized at period start and not equal to continuous calendar-year returns."],
        "rows":grid},ensure_ascii=False,separators=(",",":")),encoding="utf-8")
    score_summary={"trainPositive":sum(x["train"]["returnPct"]>0 for x in grid),
        "validationPositive":sum(x["validation2024_2025"]["returnPct"]>0 for x in grid),
        "auditPositive":sum(x["audit2026"]["returnPct"]>0 for x in grid),
        "positiveTrainValidation":sum(x["train"]["returnPct"]>0 and x["validation2024_2025"]["returnPct"]>0 for x in grid),
        "n":len(grid)}
    detail={"version":"00675L_EXIT_ENTRY_EXPERIMENT_2018_2026_V2","generatedAtUTC":datetime.now(timezone.utc).isoformat(),
        "instrument":"00675L.TW","signal":"^TWII","range":[BEGIN,END],"capital":CAPITAL,
        "method":"Completed previous close signals; next session open fills. 100% available cash invested; no borrowing; integer ETF units; ETF adjusted OHLC and index from Yahoo.",
        "costs":{"brokerEachSide":BROKER,"sellTax":ETF_SELL_TAX,"slippageEachSide":SLIP},
        "legacy":{"originalArchivedReturnPct":prior["returnPct"],"refetchedReturnPct":base["returnPct"],
            "deltaPctPoints":round(source_delta,3),"exactAlgorithmParity":True},
        "dataQuality":quality,"variants":summaries,"parameterGrid":{"count":len(grid),"top3Training":picks,"distribution":score_summary},
        "limitations":["Data can be retroactively adjusted by provider, creating differences from frozen archive.",
        "2026 was already accessed in previous research: NOT an untouched out-of-sample.",
        "Stop signals are end-of-day only. A single-session ETF gap can still cause huge losses.",
        "Grid results have multiple-testing risk. Report training, validation, 2026 separately.",
        "Daily leveraged ETF has path-dependent returns; backtest is not a guaranteed forecast."]}
    (OUT/"summary.json").write_text(json.dumps(detail,ensure_ascii=False,indent=2),encoding="utf-8")
    url="https://github.com/jacky-168168/Tradingview-testing/blob/main/tw-stock-dashboard/docs/data/research/etf_history/00675l_risk_v2/"
    study={"id":STUDY,"title":"00675L｜2018～2026 進出場風控實驗 V2",
      "description":"原始 SMA10 完整對照＋急跌保護／確認日／冷卻期共19組預設測試，以及270組參數穩健性網格（只以2018–2023選擇候選）。",
      "period":[BEGIN,END],"sessions":base["sessions"],"models":records,
      "warnings":["2018–2026已多次研究，2026不是完全獨立樣本。",
                  "本研究以日K收盤訊號於次交易日開盤執行，無法保證急殺可在觸價當下賣出。",
                  "年度表為連續複利；獨立分段測試自100萬重新啟動，兩者不可混淆。",
                  "參數穩健性網格包含270種組合，最高績效可能源於多重測試。"],
      "dataQuality":"2128 個台股交易日；Yahoo OHLC 使用企業行為調整；與舊版逐筆模型核對通過。"
       +(f"與舊存檔累積報酬差 {source_delta:+.3f} 個百分點（資料來源更新）。" if abs(source_delta)>.01 else "原版累積報酬與舊存檔一致。"),
      "sourceBranch":"main","sourceSummary":url+"summary.json",
      "sourceExecution":"https://github.com/jacky-168168/Tradingview-testing/actions/runs/"+os.environ.get("GITHUB_RUN_ID",""),
      "extraSource":url+"grid.json","trainingGrid":"00675l_risk_v2/grid.json"}
    archive["studies"]=[v for v in archive["studies"] if v["id"]!=STUDY]+[study]
    archive["studyOrder"]=[v for v in archive.get("studyOrder",[]) if v!=STUDY]+[STUDY]
    archive["generatedAtUTC"]=detail["generatedAtUTC"]
    archive["entryExitStudyWarning"]="新研究 00675_risk_v2 為後續額外測試；舊的 ETF 研究檔案保留原值。"
    (DATA/"index.json").write_text(json.dumps(archive,ensure_ascii=False,separators=(",",":")),encoding="utf-8")
    assert len(records)==22 and len(grid)==270,(len(records),len(grid))
    assert all((DATA/z["curve"]).exists() for z in records)
    print("RESULT_READY",json.dumps({"period":[BEGIN,END],"baseline":publicstats(base),"totalModels":len(records),
      "grid":len(grid),"distribution":score_summary,"sourceDeltaPctPoints":round(source_delta,3),
      "topByTrain":picks,"topDisplayed":sorted([(x["id"],x["returnPct"],x["mddPct"]) for x in records],key=lambda x:x[1],reverse=True)[:10]},ensure_ascii=False),flush=True)
if __name__=="__main__":emit()
