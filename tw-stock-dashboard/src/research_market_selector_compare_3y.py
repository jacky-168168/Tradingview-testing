"""A / D / F / G cross-selector official market-gate audit using archived real trades.
Only existing frozen archived fills/returns; official TWSE Risk Score for every signal.
Does not modify production selectors or live thresholds. Research only.
"""
from __future__ import annotations
import json,math,statistics
from pathlib import Path
from collections import defaultdict
from datetime import datetime
from zoneinfo import ZoneInfo
ROOT=Path(__file__).resolve().parents[1];DATA=ROOT/"docs"/"data";RISK=DATA/"research"/"g_regime_3y"
OUT=DATA/"research"/"market_selector_compare_3y";OUT.mkdir(parents=True,exist_ok=True)
ARCHIVE=["2023-01-01_2023-12-31.json","2024-01-01_2024-12-31.json","2025-01-01_2025-12-31.json","2026-01-01_2026-10-07.json"]
HORIZONS=(1,5,10,20);COST=.00585
END="2026-10-07"
SPLITS={"train":("2023-10-11","2024-12-31"),"validation":("2025-01-01","2025-12-31"),"holdout":("2026-01-01",END)}
GATES=("ALL","GE60","GE70","GE80","F_OFFICIAL","GE60_NO_TOP","GE60_NO_HEAT","BELOW40","BELOW40_OVERSOLD","BELOW40_STRONG_BOTTOM")
VETO=("🔴 Strong Top Reversal","🟠 Top Reversal Attempt","🔴 Extreme Overbought")
def read(path):return json.loads(path.read_text(encoding="utf-8"))
def pct(x):
    if not x:return {"n":0,"avgNetPct":None,"medianNetPct":None,"winPct":None,"avgWinPct":None,"avgLossPct":None,"p10NetPct":None,"minNetPct":None}
    a=sorted([100*float(v) for v in x]);wins=[v for v in a if v>0];loss=[v for v in a if v<0]
    return {"n":len(a),"avgNetPct":round(statistics.mean(a),3),"medianNetPct":round(statistics.median(a),3),"winPct":round(100*len(wins)/len(a),2),
      "avgWinPct":round(statistics.mean(wins),3) if wins else None,"avgLossPct":round(statistics.mean(loss),3) if loss else None,
      "p10NetPct":round(a[max(0,math.ceil(.1*len(a))-1)],3),"minNetPct":round(a[0],3)}
def main():
    coverage=read(RISK/"coverage.json");riskrows=read(RISK/"market_risk_daily.json")
    assert coverage["complete"] is True and coverage["riskScoredDays"]==728 and len(riskrows)==728
    risk={z["date"]:z for z in riskrows};cal=list(risk);pos={d:i for i,d in enumerate(cal)}
    assert cal[0]=="2023-10-11" and cal[-1]=="2026-10-08",("unexpected date range",cal[0],cal[-1])
    assert END in pos
    # A/D historical signals are authored in frozen annual backtest archives.
    # Reapply official risk gate to *unchanged* A/D rankings, instead of their older
    # synthetic risk source. F is therefore recomputed from D, not the old F export.
    signals={m:defaultdict(list) for m in ("A","D")}
    annual=[]
    for filename in ARCHIVE:
        report=read(DATA/"backtest"/filename)
        models={m["id"]:m for m in report["models"]}
        if not {"A","D"}.issubset(models):raise RuntimeError("Missing A/D in "+filename)
        annual.append({"file":filename,"version":report.get("version"),"dateRange":report["period"],"signalDays":report.get("signalDays"),
          "sourceRiskNote":"Past annual F risk estimated historical breadth/flow, excluded from official comparison"})
        for model in ("A","D"):
            for rec in models[model]["signals"]:
                d=str(rec["signalDate"]);rank=int(rec["rank"])
                if d not in pos or d>END or rank>3:continue
                if rank<1 or rank>3:raise RuntimeError("Invalid signal rank")
                if any(z["rank"]==rank for z in signals[model][d]):raise RuntimeError("Duplicate "+model+" "+d+" rank "+str(rank))
                signals[model][d].append(rec)
    for m in signals:
        for d in signals[m]:signals[m][d].sort(key=lambda a:a["rank"])
    historicG=read(RISK/"trades.json")
    if historicG.get("period")!=coverage.get("period"):raise RuntimeError("Historic G versus Risk Score period mismatch")
    gbase={m["horizon"]:m for m in historicG["models"] if m["model"]=="SPOT_0"}
    if set(gbase)!=set(HORIZONS):raise RuntimeError("Missing frozen G original baselines")
    rawG={h:{} for h in HORIZONS}
    for h,model in gbase.items():
        if len(model["trades"])!=model["executedSignals"]:raise RuntimeError("G archived executed count mismatch")
        for tr in model["trades"]:
            d=tr["date"]
            if d not in risk or d in rawG[h]:raise RuntimeError("Duplicate G date/invalid risk "+d)
            if tr["score"]!=risk[d]["score"]:raise RuntimeError("Risk mismatch with frozen G trade "+d)
            if len(tr.get("codes",[]))!=3:continue
            rawG[h][d]=tr
    valid={m:{h:{} for h in HORIZONS} for m in ("A","D","F","G")}
    counter={m:{h:{"signalDates":0,"incompleteRanks":0,"invalidFutureReturn":0,"dateMismatch":0,"valid":0} for h in HORIZONS} for m in ("A","D","F","G")}
    for model in ("A","D"):
        for d,recs in signals[model].items():
            i=pos[d]
            for h in HORIZONS:
                count=counter[model][h];count["signalDates"]+=1
                if i+h>pos[END]:continue
                if len(recs)!=3 or [x["rank"] for x in recs]!=[1,2,3]:
                    count["incompleteRanks"]+=1;continue
                if any(x.get("buyDate")!=cal[i+1] for x in recs):
                    count["dateMismatch"]+=1;continue
                vals=[x.get("ret"+str(h)) for x in recs]
                if any(v is None or not isinstance(v,(int,float)) or not math.isfinite(v) for v in vals):
                    count["invalidFutureReturn"]+=1;continue
                gross=sum(vals)/300
                net=(1+gross)*(1-COST)-1
                if net<=-1:raise RuntimeError("Invalid total-loss encoding "+model+" "+d)
                valid[model][h][d]={"date":d,"buy":cal[i+1],"sell":cal[i+h],"net":net,
                  "codes":[r["code"] for r in recs],"source":"annual historical Top3 net adjusted-OHLC"}
                count["valid"]+=1
    # The official F rule is D+60 or Strong Bottom single-day exception.
    # Preserve identical D top-three and individual future fill assumptions.
    for h in HORIZONS:
        for d,tr in valid["D"][h].items():valid["F"][h][d]=dict(tr)
        counter["F"][h]={"signalDates":counter["D"][h]["signalDates"],
            "incompleteRanks":counter["D"][h]["incompleteRanks"],
            "invalidFutureReturn":counter["D"][h]["invalidFutureReturn"],
            "dateMismatch":counter["D"][h]["dateMismatch"],
            "valid":counter["D"][h]["valid"]}
        for d,tr in rawG[h].items():
            if d>END:continue
            i=pos[d]
            if i+h>pos[END]:continue
            if tr["buy"]!=cal[i+1] or tr["sell"]!=cal[i+h]:
                raise RuntimeError("G trade date misalignment "+d)
            valid["G"][h][d]={"date":d,"buy":tr["buy"],"sell":tr["sell"],"net":float(tr["net"]),
              "codes":tr["codes"],"source":"G original official three-year published net basket"}
            counter["G"][h]["valid"]+=1
    def allow(d,gate):
        r=risk[d];s=r["score"];bot=r.get("bottomState");top=r.get("topState")
        if gate=="ALL":return True
        if gate=="GE60":return s>=60
        if gate=="GE70":return s>=70
        if gate=="GE80":return s>=80
        if gate=="F_OFFICIAL":return s>=60 or bot=="🟢 Strong Bottom Reversal"
        if gate=="GE60_NO_TOP":return s>=60 and top not in VETO
        if gate=="GE60_NO_HEAT":return s>=60 and top not in VETO and not(r["mode"]=="TOP" and r.get("distMA20",0)>=6 and r.get("ret5",0)>=8)
        if gate=="BELOW40":return s<40
        if gate=="BELOW40_OVERSOLD":return s<40 and r.get("oversoldScore",0)>=3
        if gate=="BELOW40_STRONG_BOTTOM":return s<40 and bot=="🟢 Strong Bottom Reversal"
        raise ValueError(gate)
    grid=[];roundingIssues=[]
    for model in ("A","D","F","G"):
        for gate in GATES:
            for h in HORIZONS:
                filt={d:tr for d,tr in valid[model][h].items() if allow(d,gate)}
                pieces={}
                for split,(start,end) in SPLITS.items():
                    cohort=[tr["net"] for d,tr in filt.items() if start<=d<=end and tr["sell"]<=end]
                    pieces[split]=pct(cohort)
                both=pct([tr["net"] for tr in filt.values()])
                # Phase-disjoint 20-day basket rebalancing is a *scenario*, not
                # a daily mark-to-market portfolio drawdown.
                phase=[]
                for phase_idx in range(h):
                    equity=1.;peak=1.;worst=0.;nt=0
                    for i in range(phase_idx,pos[END]-h+1,h):
                        d=cal[i];tr=filt.get(d)
                        if tr:
                            equity*=1+tr["net"];nt+=1
                        peak=max(peak,equity);worst=min(worst,equity/peak-1)
                    if nt:phase.append({"phase":phase_idx,"trades":nt,"returnPct":round(100*(equity-1),2),"exitMDDPct":round(100*worst,2)})
                grid.append({"model":model,"gate":gate,"horizon":h,"all":both,"bySplit":pieces,
                  "phaseScenario":{"count":len(phase),"medianReturnPct":round(statistics.median(x["returnPct"] for x in phase),2) if phase else None,
                    "worstReturnPct":round(min(x["returnPct"] for x in phase),2) if phase else None,
                    "worstExitDrawdownPct":round(min(x["exitMDDPct"] for x in phase),2) if phase else None},
                  "overlapWarning":h>1})
    # Fixed no-selection bias: display the same six 20D comparisons side-by-side.
    snapshots={}
    for model in ("A","D","F","G"):
        baseGate="F_OFFICIAL" if model=="F" else "ALL"
        for gate in dict.fromkeys((baseGate,"GE60","GE80","GE60_NO_TOP","BELOW40")):
            snapshots[model+"_"+gate]={str(h):next(v for v in grid if v["model"]==model and v["gate"]==gate and v["horizon"]==h) for h in (5,10,20)}
    # Accounting reconciliation for the identical D vs F_OFFICIAL valid basket.
    for h in HORIZONS:
        drow=valid["D"][h];frow=valid["F"][h]
        if drow.keys()!=frow.keys() or any(drow[d]["net"]!=frow[d]["net"] for d in drow):
            raise RuntimeError("F must be a pure D filter before gating")
    out={"version":"A_D_F_G_OFFICIAL_MARKET_GATE_ALIGNED_3Y_V1",
      "createdAt":datetime.now(ZoneInfo("Asia/Taipei")).isoformat(),"marketPeriod":{"start":cal[0],"end":END},
      "riskCoverage":coverage["riskScoredDays"],"officialSource":coverage["sources"],
      "sourceArchives":annual,"sources":{"G":"research/g_regime_3y/trades.json: SPOT_0",
        "A_D":"data/backtest/*.json: unfiltered signal Top3, re-gated using published official Risk Score",
        "F":"D ranking with official Risk Score >=60 OR strong bottom exception, not older archive F"},
      "sampleAudit":counter,"method":{"ranking":"A/D original frozen same-day Top3; G original frozen 3-year G Top3; F exactly D with official dated market gate",
        "signal": "Signal day's finished cash-market close; enter next market open; Hth trading session close",
        "fairness":"Require Rank1/2/3 all present and all three future adjusted returns valid; G also has 3 codes; no survivor replacement",
        "stockReturns":"A/D adjusted open-to-close from historical archived signal ret fields; G archived net basket already included same fee and tax",
        "roundTripCostPct":COST*100,
        "risk":"Date-locked 728-day official Taiwan market Risk Score; original weights unchanged",
        "horizonTradeOverlap":"Signals on adjacent dates are NOT independent for h>1; mean signal net is not investable portfolio net return",
        "phasePortfolio":"Equal-capital Top3 basket on every Hth trading day for each of H start offsets, hold cash otherwise; exit-sampled drawdown only",
        "splitTrainingLeakage":"Train 2023-2024; 2025 validation; 2026 holdout. Positions closing after fold-end excluded.",
        "limitations":["Different selectors historical archives come from different published code versions, including G reconstructing its own top3",
          "Current company universe causes survivorship and historical-capital bias",
          "A/D historical foreign and breadth previously approximate but their selection rankings do not depend on historical market score; recomputed F gate from official historical data",
          "All TOP3 events may share stock names across dates and vary in market liquidity",
          "No exchange open limit-up/limit-down order-fill simulation and not a daily marked-to-market portfolio MDD",
          "F is D with the verified daily risk gate, not fully identical to the archived F using synthetic historical risk",
          "G data includes only historical executed signals; missing/unfilled G signals cannot be independently repriced from archives",
          "No new optimization of risk weights or thresholds; 60/70/80 are fixed comparisons only"]},
      "gates":{"ALL":"No market filter","GE60":"risk >=60","GE70":"risk >=70","GE80":"risk >=80",
        "F_OFFICIAL":"Risk Score >=60 OR Strong Bottom Reversal",
        "GE60_NO_TOP":"risk>=60 with confirmed top / extreme heat veto",
        "GE60_NO_HEAT":"risk>=60 with confirmed top veto and joint MA20 >=6% and 5D >=8% stretch veto",
        "BELOW40":"risk<40","BELOW40_OVERSOLD":"risk<40 and oversold score >=3",
        "BELOW40_STRONG_BOTTOM":"risk<40 and Strong Bottom Reversal"},
      "snapshots":snapshots,"grid":grid}
    (OUT/"summary.json").write_text(json.dumps(out,ensure_ascii=False,indent=2,allow_nan=False),encoding="utf-8")
    print("COMPARE_DONE",json.dumps({"coverage":out["riskCoverage"],"period":out["marketPeriod"],
      "top20D":{m:{gate:{"n":val["20"]["all"]["n"],"mean":val["20"]["all"]["avgNetPct"],"win":val["20"]["all"]["winPct"],
        "train":val["20"]["bySplit"]["train"]["avgNetPct"],"validation":val["20"]["bySplit"]["validation"]["avgNetPct"],
        "holdout":val["20"]["bySplit"]["holdout"]["avgNetPct"]}
        for gate,val in [(v.split(m+"_")[-1],z) for v,z in snapshots.items() if v.startswith(m+"_")]}
        for m in ("A","D","F","G")}},ensure_ascii=False),flush=True)
if __name__=="__main__":main()
