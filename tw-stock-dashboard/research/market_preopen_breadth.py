"""Official cash-market preopen proxy: only D-close facts predict D+1/D+2.
No intraday 9:00 quote exists here. Do not imply this reconstructs 09:00 signals.
Tests majority of TWSE stock advances, index direction, red vs green close and
two-session flips, with dated outcomes and chronological year diagnostics.
"""
from __future__ import annotations
import json,math,statistics
from collections import Counter
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
BASE=Path(__file__).resolve().parents[1]/"docs"/"data"/"research"/"g_regime_3y"
OUT=Path(__file__).resolve().parents[1]/"docs"/"data"/"research"/"market_preopen_breadth"
OUT.mkdir(parents=True,exist_ok=True)
def read(p):return json.loads(p.read_text(encoding="utf-8"))
def wilson(positives,total):
    if not total:return [None,None]
    p=positives/total;z=1.96;den=1+z*z/total
    ctr=(p+z*z/(2*total))/den
    half=z*math.sqrt(p*(1-p)/total+z*z/(4*total*total))/den
    return [round((ctr-half)*100,2),round((ctr+half)*100,2)]
def eval_rows(rows):
    n=len(rows)
    if not n:return {"n":0}
    nxt=sum(z["nextUpMajority"] for z in rows)
    nxtidx=sum(z["nextIndexUp"] for z in rows)
    dy2=sum(z["day2Majority"] for z in rows)
    return {"n":n,"nextStockMajorityUpPct":round(nxt*100/n,2),"nextStockMajorityUpCI95":wilson(nxt,n),
      "nextIndexUpPct":round(nxtidx*100/n,2),"day2StockMajorityUpPct":round(dy2*100/n,2),
      "nextStockBreadthMeanPct":round(statistics.mean(x["nextBreadth"] for x in rows),2),
      "nextIndexCloseReturnMeanPct":round(statistics.mean(x["nextReturnPct"] for x in rows),3),
      "nextDownThenDay2UpCount":sum(not x["nextUpMajority"] and x["day2Majority"] for x in rows),
      "nextUpThenDay2DownCount":sum(x["nextUpMajority"] and not x["day2Majority"] for x in rows)}
def group(data,key):
    d={}
    for x in data:d.setdefault(str(key(x)),[]).append(x)
    return {name:eval_rows(items) for name,items in sorted(d.items())}
def main():
    a=read(BASE/"market_risk_daily.json");cov=read(BASE/"coverage.json");inp=read(BASE/"risk_inputs.json")
    if len(a)!=728 or not cov.get("complete") or cov.get("officialValidDays")!=728:raise RuntimeError("Unverified 728-day official source")
    if [x["date"] for x in a]!=sorted(x["date"] for x in a):raise RuntimeError("Misordered dates")
    for x in a:
        z=inp.get(x["date"])
        if not z or not z.get("ok") or x.get("up")!=z.get("up") or x.get("down")!=z.get("down"):
            raise RuntimeError("Unverified historical breadth day "+x["date"])
    records=[]
    for i in range(len(a)-2):
        at,nxt,two=a[i:i+3];score=at["score"]
        records.append({"knownAtClose":at["date"],"targetTradingDay":nxt["date"],
          "nextTradingDay2":two["date"],"score":score,"afterRedDay":float(at["dayRet"])<0,
          "afterGreenDay":float(at["dayRet"])>0,
          "signalYear":at["date"][:4],
          "nextUpMajority":float(nxt["breadth"])>50,"nextIndexUp":float(nxt["dayRet"])>0,
          "day2Majority":float(two["breadth"])>50,"nextBreadth":float(nxt["breadth"]),
          "nextReturnPct":float(nxt["dayRet"]),
          "nextYear":nxt["date"][:4]})
    binned=lambda z:"0-39" if z["score"]<40 else "40-59" if z["score"]<60 else "60-79" if z["score"]<80 else "80-100"
    allgroups=group(records,binned)
    gates={}
    for name,pred in {"LESS_60":lambda x:x["score"]<60,"GE_60":lambda x:x["score"]>=60,
      "GE_70":lambda x:x["score"]>=70,"GE_80":lambda x:x["score"]>=80,
      "BELOW_40":lambda x:x["score"]<40}.items():
        subset=[x for x in records if pred(x)]
        gates[name]=eval_rows(subset)
    red=[x for x in records if x["afterRedDay"]]
    green=[x for x in records if x["afterGreenDay"]]
    # Keep same-day red/green observable only at day's close, never earlier.
    report={"version":"MARKET_PREOPEN_BREADTH_EVAL_2026_10_V1",
      "createdAt":datetime.now(ZoneInfo("Asia/Taipei")).isoformat(),
      "sourceDates":{"start":a[0]["date"],"end":a[-1]["date"],"officialVerifiedSessions":len(a)},
      "signalDefinition":"All facts are available at end of day D and may be used by 08:59 on next *trading* session D+1. No 09:00 intraday quotation reconstructed.",
      "primaryLabel":"Of TWSE advancing+declining STOCKS, more than half advanced on next market session D+1. Not OTC. On exactly 50% treated not majority.",
      "secondaryLabel":"^TWII D+1 close versus D close; 2nd-next breadth majority; labels observed AFTER decision, never input to predictor",
      "outcomeCount":len(records),"baseline":eval_rows(records),
      "riskScorePreviousCloseBands":allgroups,"candidateThresholds":gates,
      "scoreBandBySignalYear":{y:group([r for r in records if r["signalYear"]==y],binned) for y in sorted({x["signalYear"] for x in records})},
      "redVersusGreenPreviousClose":{"PREVIOUS_INDEX_RED":eval_rows(red),"PREVIOUS_INDEX_GREEN":eval_rows(green)},
      "counterexamples":{"highScore70NextMajorityDown":sum(x["score"]>=70 and not x["nextUpMajority"] for x in records),
        "highScore70NextIndexDown":sum(x["score"]>=70 and not x["nextIndexUp"] for x in records),
        "lowScore40NextMajorityUp":sum(x["score"]<40 and x["nextUpMajority"] for x in records),
        "highScore70NextDownThenDay2Up":sum(x["score"]>=70 and not x["nextUpMajority"] and x["day2Majority"] for x in records),
        "highScore70NextUpThenDay2Down":sum(x["score"]>=70 and x["nextUpMajority"] and not x["day2Majority"] for x in records)},
      "limitations":["This is a next-session PREOPEN proxy from previous-day close, NOT true 9AM first traded/opening-price snapshot",
        "Score captures market regime, not guaranteed next-day breadth prediction or expected profit",
        "TWSE listed-only advancing/declining report, not all listed+OTC stock universe",
        "Wilson confidence intervals assume independent days and are optimistic under serial dependence",
        "Index red/green close-to-close statistics do NOT model executable next-open entry/exit or transaction fees",
        "2026 was inspected previously; no pristine held-out causal test",
        "No after-hours foreign data known at 08:59 beyond prior officially published closing day",
        "Do not make 09:00 trading claims until actual time-stamped opening records are collected"]}
    (OUT/"summary.json").write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False),encoding="utf-8")
    print("PREOPEN_BREADTH_AUDIT_DONE",json.dumps({"n":len(records),"baseline":report["baseline"],
      "scoreBands":allgroups,"redGreen":report["redVersusGreenPreviousClose"],
      "counterexamples":report["counterexamples"]},ensure_ascii=False),flush=True)
if __name__=="__main__":main()
