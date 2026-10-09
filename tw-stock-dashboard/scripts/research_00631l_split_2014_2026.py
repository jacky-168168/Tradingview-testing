"""00631L split-aware causal backtest, 2014-10-31 to 2026-10-07.
2026-03-25 ETF 22:1 split; 03/25-03/30 halted, resumes 03/31.
TWII close provides all signals, actual 00631L adjusted OHLC executes next ETF open.
Separately compare common 2018-26 to verified 00675L archive.
"""
from __future__ import annotations
import os,json
from datetime import datetime,timezone
from pathlib import Path
import numpy as np,pandas as pd
from yahoo_cache import _fetch
from research_00675l_swing_grid import CAPITAL,BROKER,ETF_SELL_TAX,SLIP
ROOT=Path(__file__).resolve().parents[1];DATA=ROOT/"docs/data/research/etf_history"
OUT=DATA/"00631l_full_split_v1";STUDY="00631_split_v1"
BEGIN="2014-10-31";COMMON="2018-01-02";END="2026-10-07"
SPLIT_LAST="2026-03-24";SPLIT_RESUME="2026-03-31";SPLIT_RATIO=22
BUY=(1+SLIP)*(1+BROKER);SELL=(1-SLIP)*(1-BROKER-ETF_SELL_TAX)
def fetch(sym,start,end):
    d=_fetch(sym,datetime.fromisoformat(start),datetime.fromisoformat(end),retries=4)
    if d.empty:raise RuntimeError("No Yahoo chart data for "+sym)
    for k in ("open","high","low","close","adjclose","volume"):
        d[k]=pd.to_numeric(d[k],errors="coerce")
    d["date"]=d.date.astype(str)
    d=d.dropna(subset=["open","high","low","close"]).sort_values("date").drop_duplicates("date",keep="last").reset_index(drop=True)
    return d
def normalized(etf):
    a=etf.copy()
    pre=a[a.date==SPLIT_LAST];post=a[a.date==SPLIT_RESUME]
    if len(pre)!=1 or len(post)!=1:
        raise RuntimeError(f"Missing exact split endpoints: March24={len(pre)}, March31={len(post)}")
    rawpre=float(pre.close.iloc[0]);rawpost=float(post.close.iloc[0])
    rawratio=rawpost/rawpre
    ratios=(a.adjclose/a.close).replace([np.inf,-np.inf],np.nan).fillna(1.)
    if ((ratios<=.001)|(ratios>100)).any():raise RuntimeError("Invalid Yahoo adjusted close factors")
    for k in ("open","high","low","close"):a[k]=a[k]*ratios
    adpre=float(a.loc[a.date==SPLIT_LAST,"close"].iloc[0]);adpost=float(a.loc[a.date==SPLIT_RESUME,"close"].iloc[0])
    adjustment="Yahoo adjclose/close factors"
    if abs(adpre-443.15/22)>3.0 or abs(adpost-19.26)>3.0:
        # Some provider revisions fail to adjust 22-for-1 historical quotes.
        if .025<rawratio<.08:
            a=etf.copy()
            a.loc[a.date<=SPLIT_LAST,["open","high","low","close"]]=a.loc[a.date<=SPLIT_LAST,["open","high","low","close"]]/22.
            adjustment="Manual pre-2026/03/25 OHLC /22 because source failed split adjustment"
        elif .65<rawratio<1.4:
            a=etf.copy()
            adjustment="Yahoo raw OHLC were already split-adjusted, adjclose inconsistent"
        else:raise RuntimeError(f"Cannot resolve split: raw pre/post={rawpre}/{rawpost}, factor pre/post={adpre}/{adpost}")
        adpre=float(a.loc[a.date==SPLIT_LAST,"close"].iloc[0]);adpost=float(a.loc[a.date==SPLIT_RESUME,"close"].iloc[0])
    assert abs(adpre-443.15/22)<3 and abs(adpost-19.26)<3,(adpre,adpost)
    splitrealreturn=(adpost/adpre-1)*100
    assert -15<splitrealreturn<15,("Artificial split jump",splitrealreturn)
    halted=a[(a.date>="2026-03-25")&(a.date<="2026-03-30")]
    removed=a[(a.volume<=0)|(~np.isfinite(a.volume))]
    a=a[a.volume>0].copy().reset_index(drop=True)
    assert not ((a.date>="2026-03-25")&(a.date<="2026-03-30")).any()
    assert (a.date==SPLIT_LAST).any() and (a.date==SPLIT_RESUME).any()
    # Yahoo sometimes has the first 2014 segment on pre-2026 units while 2015+ is adjusted.
    # Fund began near NT$20 in 2014 and did NOT actually split during 2015.
    # Permit only an exactly identified 22x source artifact at 2015-01-05, not any general gap.
    gaps=a.close.pct_change().abs()
    artifacts=[]
    severe=a.loc[gaps>.52,["date","close"]]
    if len(severe)==1 and str(severe.iloc[0].date)=="2015-01-05":
        p=int(severe.index[0]);before=float(a.iloc[p-1].close);after=float(a.iloc[p].close)
        jump=after/before
        print("EARLY_SOURCE_ARTIFACT",json.dumps({"date":"2015-01-05","before":before,"after":after,"jump":jump}),flush=True)
        if not (0.025<jump<0.065 and before>10 and after<2):
            raise RuntimeError(f"Unexpected 2015 provider discontinuity, cannot safely repair: {jump}")
        a.loc[a.date<"2015-01-05",["open","high","low","close"]]=a.loc[a.date<"2015-01-05",["open","high","low","close"]]/22.
        artifacts.append({"date":"2015-01-05","reason":"Yahoo earliest 2014 prices weren't back-adjusted by the 2026 22-for-1 split",
                          "applied":"divide all pre-2015-01-05 OHLC by 22","originalJump":jump})
        gaps=a.close.pct_change().abs()
        severe=a.loc[gaps>.52,["date","close"]]
    if len(severe):
        raise RuntimeError("Uncorrected corporate-action or abnormal >52% ETF gap: "+severe.to_json(orient="records"))

    q={"ratio":22,"lastPreSplitTradingDate":SPLIT_LAST,"firstPostSplitTradingDate":SPLIT_RESUME,
       "officialOldLastClose":443.15,"officialSplitAdjustedPreClose":round(443.15/22,5),
       "YahooRawPre":round(rawpre,5),"YahooRawPost":round(rawpost,5),
       "usedAdjustedPreClose":round(adpre,5),"usedAdjustedPostClose":round(adpost,5),
       "postPreAdjustedPct":round(splitrealreturn,5),
       "adjustmentMethod":adjustment,"zeroVolumeQuoteRowsDropped":[str(x) for x in removed.date],
       "haltedQuotesRemoved":[str(x) for x in halted.date],
       "adjustedEtfDailyReturnsAbove52Pct":int((gaps>.52).sum()),
       "additionalProviderScalingFixes":artifacts,
       "firstTradingSession":str(a.date.iloc[0]),"lastTradingSession":str(a.date.iloc[-1])}
    print("SPLIT_AUDIT",json.dumps(q,ensure_ascii=False),flush=True)
    return a,q
def signals(idx):
    x=idx.copy().sort_values("date").reset_index(drop=True)
    x["sma10"]=x.close.rolling(10,min_periods=10).mean()
    x["sma5"]=x.close.rolling(5,min_periods=5).mean()
    x["d1"]=x.close.pct_change()
    x["crash2"]=((x.d1<=-.04)&(x.d1.shift(1)<=-.04))
    x["crash1"]=x.d1<=-.04
    x["crash3"]=((x.d1<=-.04)&(x.d1.shift(1)<=-.04)&(x.d1.shift(2)<=-.04))
    x["crash2red"]=(x.close/x.close.shift(2)-1<=-.04)&(x.d1<0)&(x.d1.shift(1)<0)
    x["cross5"]=x.close>x.sma5
    x["buy10"]=x.close>x.sma10*1.01
    x["exit10"]=(x.close<x.sma10*.98)&(x.close.shift(1)<x.sma10.shift(1)*.98)&(x.close.shift(2)<x.sma10.shift(2)*.98)
    x["exit5"]=(x.close<x.sma5*.98)&(x.close.shift(1)<x.sma5.shift(1)*.98)&(x.close.shift(2)<x.sma5.shift(2)*.98)
    return x
RULES=[
 ("HOLD","買進持有",False,None),
 ("SMA10","台指SMA10跌2%連3日賣／站回1%買",False,None),
 ("SMA10_PANIC4","台指SMA10＋單日急跌4%賣出",True,None),
 ("SMA5_ENTRY10_EXIT","台指站上SMA5買回＋SMA10出場＋急跌4%",True,"always5"),
 ("SMA5_BOTH","台指SMA5買回及出場＋急跌4%",True,"both5"),
 ("CRASH2_SMA5","連2交易日各跌4%後5天內SMA5提前買回",True,"crash2"),
 ("CRASH1_SMA5","台指單日跌4%後5天內SMA5提前買回",True,"crash1"),
 ("CRASH3_SMA5","連3交易日各跌4%後5天內SMA5提前買回",True,"crash3"),
 ("CRASH2RED_SMA5","連跌2天累積跌4%後5天內SMA5提前買回",True,"crash2red")]
def sim(etf,ind,start,end,variant):
    xs=etf[(etf.date>=start)&(etf.date<=end)].copy().reset_index(drop=True)
    if len(xs)<50:raise RuntimeError("Not enough trading days for "+start)
    full_idx=ind.date.to_numpy(dtype=str);prev=np.searchsorted(full_idx,xs.date.to_numpy(dtype=str),side="left")-1
    if (prev<0).any():raise RuntimeError("Insufficient TWII warmup")
    id,label,panic,entry=variant
    cash=float(CAPITAL);units=0;held=False;eq=[];orders=[];flat=0;special=0
    for pos,r in xs.iterrows():
        dt=str(r["date"]);op=float(r["open"]);cl=float(r["close"]);j=int(prev[pos])
        k=ind.iloc[j];reason="hold"
        if pos==0:want=True;reason="start"
        elif id=="HOLD":want=True
        elif held:
            exit_condition=bool(k["exit5"] if entry=="both5" else k["exit10"])
            drop=bool(panic and k["d1"]<=-.04)
            # When 00631L is untradable because of 2026 split halt, never create synthetic fills.
            # If index panic hits before ETF can trade, exit at earliest ETF open after suspension.
            if panic and pos>0:
                lo=int(prev[pos-1])+1
                if lo<=j and bool((ind.d1.iloc[lo:j+1]<=-.04).any()):drop=True
            want=not(exit_condition or drop)
            if not want:reason="index_panic4" if drop else "sma_exit"
        else:
            normal=bool(k["buy10"])
            if entry=="always5" or entry=="both5":fast=bool(k["cross5"])
            elif entry is not None:
                fast=bool(k["cross5"] and ind[entry].iloc[max(0,j-4):j+1].any())
            else:fast=False
            want=normal or fast
            if want:reason="sma5_early" if fast and not normal else "sma10_reentry"
        if pos==0 or want!=held:
            held=want
            gross=cash+units*op*SELL
            target=int(max(0,gross*(1 if want else 0))//(op*BUY))
            if target<units:
                n=units-target;paid=n*op*SELL;units-=n;cash+=paid
                orders.append([dt,"SELL",reason,int(n),round(op,5),round(paid,2),round(cash,2)])
            elif target>units:
                n=min(target-units,int(cash//(op*BUY)))
                if n:
                    paid=n*op*BUY;units+=n;cash-=paid
                    orders.append([dt,"BUY",reason,int(n),round(op,5),round(-paid,2),round(cash,2)])
                    special+=int(reason=="sma5_early")
        if not held:flat+=1
        eq.append([dt,round(cash+units*cl*SELL,2)])
    if units:
        dt=str(xs.date.iloc[-1]);val=units*float(xs.close.iloc[-1])*SELL;cash+=val
        orders.append([dt,"SELL","period_end",int(units),None,round(val,2),round(cash,2)])
        eq[-1][1]=round(cash,2)
    vals=np.array([z[1] for z in eq]);peaks=np.maximum.accumulate(np.r_[CAPITAL,vals])[1:]
    annual=[];prev=float(CAPITAL)
    for yr in sorted({x[0][:4] for x in eq}):
        v=next(x[1] for x in reversed(eq) if x[0].startswith(yr))
        annual.append({"year":yr,"pct":round((v/prev-1)*100,3),"wealthTWD":v,"wealthUSD":None,"usdPct":None})
        prev=v
    return {"start":eq[0][0],"end":eq[-1][0],"returnPct":round((cash/CAPITAL-1)*100,3),
       "endNTD":round(cash,2),"mddPct":round(float(np.min((vals/peaks-1)*100)),3),
       "riskOffSells":sum(o[1]=="SELL" and o[2]!="period_end" for o in orders),
       "riskOnReentries":max(0,sum(o[1]=="BUY" for o in orders)-1),
       "riskOffSessions":flat,"sma5EarlyBuys":special,"sessions":len(xs),"annual":annual,
       "points":eq,"orders":orders}
def writecurve(id,sim_result):
    f=f"curves/{STUDY}__{id}.json"
    obj={"study":STUDY,"id":id,"currency":"TWD","columns":["date","equity"],"points":sim_result["points"],
         "tradeColumns":["date","side","phase","units","unitPrice","cashFlow","cashAfter"],"trades":sim_result["orders"]}
    (DATA/f).write_text(json.dumps(obj,ensure_ascii=False,separators=(",",":")),encoding="utf-8")
    return f
def public(z):
    return {k:z[k] for k in ("returnPct","endNTD","mddPct","riskOffSells","riskOnReentries","riskOffSessions","sma5EarlyBuys","sessions")}
def main():
    OUT.mkdir(parents=True,exist_ok=True);(DATA/"curves").mkdir(parents=True,exist_ok=True)
    # Fresh full download: do not reuse stale, pre-split parquet cached at a different quote scale.
    etfraw=fetch("00631L.TW","2014-10-01","2026-10-08")
    etf,quality=normalized(etfraw)
    ind=signals(fetch("^TWII","2014-01-01","2026-10-08"))
    print("UNIVERSE",json.dumps({"etfBars":len(etf),"first":str(etf.date.iloc[0]),"indexBars":len(ind),"indexFirst":str(ind.date.iloc[0]),"indexLast":str(ind.date.iloc[-1])}),flush=True)
    assert str(etf.date.iloc[0])=="2014-10-31"
    # The split MUST NOT manufacture a 95% drawdown; final relative return near 2026/03/31 is a real trade-date change.
    results={};models=[]
    ix=json.loads((DATA/"index.json").read_text(encoding="utf-8"))
    for v in RULES:
        full=sim(etf,ind,BEGIN,END,v)
        common=sim(etf,ind,COMMON,END,v)
        splits={name:public(sim(etf,ind,lo,hi,v)) for name,(lo,hi) in {
            "2014_2017":(BEGIN,"2017-12-31"),
            "2018_2023":(COMMON,"2023-12-31"),
            "2024_2025":("2024-01-01","2025-12-31"),
            "2026":("2026-01-01",END)}.items()}
        f=writecurve(v[0],full)
        # Comparison curves for 2018-26 must be separate and never silently fake common 2014 sessions.
        cf=writecurve(v[0]+"__2018",common)
        results[v[0]]={"full":public(full),"common2018":public(common),"segmented":splits,
            "fullYears":full["annual"],"commonYears":common["annual"],
            "firstTrades":full["orders"][:8],
            "splitWindowTrades":[t for t in full["orders"] if "2026-03-01"<=t[0]<="2026-04-20"]}
        for id,dat,group,curve in [(v[0],full,"完整上市歷史",f),(v[0]+"__2018",common,"2018～2026同期間比較",cf)]:
            models.append({"id":id,"name":"00631L｜"+v[1]+("（2018～2026）" if id.endswith("__2018") else "（2014～2026）"),
              "group":group,"endTWD":dat["endNTD"],"returnPct":dat["returnPct"],"mddPct":dat["mddPct"],
              "sells":dat["riskOffSells"],"rebuys":dat["riskOnReentries"],"cashDays":dat["riskOffSessions"],
              "sessions":dat["sessions"],"annual":dat["annual"],"curve":curve,"curveCurrency":"TWD",
              "notes":"使用台股加權指數^TWII發出訊號（與00675L原版一致，這不是00631L追蹤的台灣50指數）；交易標的是00631L。2026/03/25 22:1分割已調整；03/25-30停牌零成交，不把分割價差當成暴跌；期初強制建倉。",
              "companion2018":results[v[0]]["common2018"] if id==v[0] else None})
        print("RESULT",v[0],json.dumps({"all":public(full),"2018":public(common),"2026":splits["2026"]},ensure_ascii=False),flush=True)
    assert len(models)==2*len(RULES)
    # Compare unaltered frozen 00675 records: instrument changes, same original TWII index signal.
    comparison=[]
    mapping={"HOLD":("00675_2018","BUY_HOLD"),
             "SMA10":("00675_risk_v2","BASE"),
             "SMA10_PANIC4":("00675_risk_v2","IDX_DROP_4"),
             "SMA5_ENTRY10_EXIT":("00675_sma5_entry","SMA5_ABOVE"),
             "SMA5_BOTH":("00675_sma5_entry","SMA5_EXIT"),
             "CRASH2_SMA5":("00675_crash_sma5","EACH4_2D_W5"),
             "CRASH1_SMA5":("00675_crash_sma5","EACH4_1D_W5"),
             "CRASH3_SMA5":("00675_crash_sma5","EACH4_3D_W5"),
             "CRASH2RED_SMA5":("00675_crash_sma5","RED4_2D_W5")}
    for key,(study,key2) in mapping.items():
        old=next(m for m in next(st for st in ix["studies"] if st["id"]==study)["models"] if m["id"]==key2)
        comparison.append({"strategyId":key,"00631L":results[key]["common2018"],"00675L":{
            "endNTD":old["endTWD"],"returnPct":old["returnPct"],"mddPct":old["mddPct"],"sessions":old["sessions"]},
            "differentTradingDaysFrom00631L":old["sessions"]-results[key]["common2018"]["sessions"]})
    extra={"createdAt":datetime.now(timezone.utc).isoformat(),"instrument":"00631L.TW","indexSignal":"^TWII",
       "periodFull":[BEGIN,END],"periodCommon":[COMMON,END],"investInitialTWD":CAPITAL,
       "costs":{"broker":BROKER,"sellTax":ETF_SELL_TAX,"slippageEachSide":SLIP},
       "priceNote":"22-for-1 split adjustments applied to all historical OHLC before 2026/03/25 if provider not split adjusted; zero-volume split halt rows dropped.",
       "splitQuality":quality,"models":results,"comparison2018":comparison,
       "warnings":["TWII (not the Taiwan 50 index) is deliberately used for exactly comparable decision rules with 00675L; fund tracks Taiwan 50 index and this is a signal-source limitation.",
         "Two ETFs have different available trading sessions during March 2026 split halt. No phantom ETF trades on suspended days.",
         "2014–2026 starts at ETF actual first trade; no simulated prelisting history.",
         "All studies use prior completed TWII close and trade on NEXT AVAILABLE 00631L open, never same-bar trade.",
         "The 2026 split is NOT an economic loss; false Yahoo zero-volume rows are excluded.",
         "Historical optimized settings may not generalize. 2026 was previously inspected.",
         "2026 last partial calendar year ends October 7; costs assume full units and cannot replicate every actual execution restriction."]}
    (OUT/"summary.json").write_text(json.dumps(extra,ensure_ascii=False,indent=2),encoding="utf-8")
    st={"id":STUDY,"title":"00631L｜2014～2026 全歷史回測（2026分割22:1已修正）",
      "description":"元大台灣50正2自2014/10/31上市至2026/10/07；SMA10、急跌4%、SMA5、連2日跌4%後SMA5提前進場等9組，另有2018～2026與00675L同期間對照。2026年3月22:1分割及停牌已調整。",
      "period":[BEGIN,END],"sessions":results["HOLD"]["full"]["sessions"],"models":models,
      "warnings":extra["warnings"],
      "dataQuality":"2026/03/24分割前末日、03/31分割後首日逐日價格核對，分割因子22、停牌資料排除；使用台指TWII訊號以保持00675L研究一致。",
      "sourceBranch":"main",
      "sourceSummary":"https://github.com/jacky-168168/Tradingview-testing/blob/main/tw-stock-dashboard/docs/data/research/etf_history/00631l_full_split_v1/summary.json",
      "sourceExecution":"https://github.com/jacky-168168/Tradingview-testing/actions/runs/"+os.environ.get("GITHUB_RUN_ID",""),
      "extraSource":"https://github.com/jacky-168168/Tradingview-testing/blob/main/tw-stock-dashboard/scripts/research_00631l_split_2014_2026.py"}
    ix["studies"]=[x for x in ix["studies"] if x["id"]!=STUDY]+[st]
    ix["studyOrder"]=[x for x in ix.get("studyOrder",[]) if x!=STUDY]+[STUDY]
    ix["generatedAtUTC"]=extra["createdAt"]
    (DATA/"index.json").write_text(json.dumps(ix,ensure_ascii=False,separators=(",",":")),encoding="utf-8")
    print("SPLIT_SAFE_RESULT",json.dumps({"full":{k:v["full"] for k,v in results.items()},"common":comparison,"split":quality},ensure_ascii=False),flush=True)
if __name__=="__main__":main()
