"""Risk-score versus NEXT TX night: date-locked index risk screen, NOT trading P&L.
For each prior cash date D, use official Risk Score(D), TX regular close(D)
and TAIFEX night attributed to the NEXT cash session T (night begins 15:00 D).
Cash close(T)/cash close(D)-1 is an outcome, unavailable at decision time.
"""
import csv,json,math
from pathlib import Path
import requests
DATA=Path(__file__).resolve().parents[1]/"docs"/"data"
OUT=DATA/"research"/"tx_night_regime_3y"
def number(v):
    try:
        a=float(v)
        return a if math.isfinite(a) else None
    except (TypeError,ValueError):return None
def delta(p):
    return -25 if p<=-2 else -15 if p<=-1 else -8 if p<=-.5 else 10 if p>=2 else 7 if p>=1 else 4 if p>=.5 else 0
def risk_rows():
    with (DATA/"research/g_regime_3y/market_risk_daily.csv").open(encoding="utf-8-sig",newline="") as file:
        rows=[x for x in csv.DictReader(file) if "2023-10-09"<=x["date"]<="2026-10-08"]
    days=[x["date"] for x in rows]
    if len(days)<700 or days!=sorted(set(days)):raise ValueError("Risk archive date validation failed")
    return rows
def tx_rows(get=requests.get):
    r=get("https://api.finmindtrade.com/api/v4/data",params={"dataset":"TaiwanFuturesDaily","data_id":"TX","start_date":"2023-10-09","end_date":"2026-10-10"},timeout=65)
    r.raise_for_status();data=r.json()
    if data.get("status") not in (None,0,200) or not isinstance(data.get("data"),list) or not data["data"]:
        raise ValueError("FinMind history unavailable: "+str(data.get("msg") or data.get("status"))[:200])
    return data["data"]
def normalize(rows):
    buckets={}
    for r in rows:
        kind=str(r.get("trading_session") or "").lower()
        mode="night" if kind in ("after_market","night","afterhours") else "day" if kind in ("position","regular","day") else None
        if not mode:continue
        d=str(r.get("date") or "")[:10];month=str(r.get("contract_date") or "").replace("-","")[:6]
        if len(d)!=10 or len(month)!=6 or not month.isdigit():continue
        close=number(r.get("close"));volume=number(r.get("volume"))
        if not close or close<=0 or not volume or volume<=0:continue
        key=(d,mode,month);p={"contract":month,"close":close,"volume":volume}
        if key not in buckets or volume>buckets[key]["volume"]:buckets[key]=p
    return buckets
def pair(risk,tx):
    rows=[];missing={}
    for prior,nxt in zip(risk,risk[1:]):
        day=prior["date"];new=nxt["date"]
        dayrows=sorted((v for (d,s,m),v in tx.items() if d==day and s=="day"),key=lambda x:-x["volume"])
        nights=sorted((v for (d,s,m),v in tx.items() if d==new and s=="night"),key=lambda x:-x["volume"])
        why=None
        if not dayrows:why="prior_day_regular_missing"
        elif not nights:why="following_cash_date_night_missing"
        else:
            anchor=dayrows[0]
            matched=next((x for x in nights if x["contract"]==anchor["contract"]),None)
            if matched is None:why="near_month_roll_mismatch"
            else:
                pct=(matched["close"]/anchor["close"]-1)*100
                if abs(pct)>12:why="outlier_night_change"
                else:
                    score=int(float(prior["score"]));old=float(prior["index"]);newclose=float(nxt["index"])
                    rows.append({"cashDate":day,"decisionDate":new,"score":score,"contract":anchor["contract"],
                      "txDay":anchor["close"],"txNight":matched["close"],"txPct":round(pct,5),
                      "txDelta":delta(pct),"adjusted":max(0,min(100,score+delta(pct))),
                      "outcomeCloseToClosePct":round((newclose/old-1)*100,5)})
        if why:missing[why]=missing.get(why,0)+1
    return rows,missing
def summarize(rows,rule):
    keep=[x for x in rows if rule(x)];skip=[x for x in rows if not rule(x)]
    def pct(n,d):return round(n/d*100,2) if d else None
    down2=[x for x in rows if x["outcomeCloseToClosePct"]<=-2]
    down3=[x for x in rows if x["outcomeCloseToClosePct"]<=-3]
    up=[x for x in rows if x["outcomeCloseToClosePct"]>0]
    return {"n":len(rows),"pass":len(keep),"block":len(skip),"passPct":pct(len(keep),len(rows)),
      "passNextLoss2Pct":pct(sum(x["outcomeCloseToClosePct"]<=-2 for x in keep),len(keep)),
      "passNextLoss3Pct":pct(sum(x["outcomeCloseToClosePct"]<=-3 for x in keep),len(keep)),
      "avoidedOfAllLoss2Pct":pct(sum(x["outcomeCloseToClosePct"]<=-2 for x in skip),len(down2)),
      "avoidedOfAllLoss3Pct":pct(sum(x["outcomeCloseToClosePct"]<=-3 for x in skip),len(down3)),
      "upDaysMissedPct":pct(sum(x["outcomeCloseToClosePct"]>0 for x in skip),len(up)),
      "meanPassedCloseToClosePct":round(sum(x["outcomeCloseToClosePct"] for x in keep)/len(keep),3) if keep else None}
def compare(rows):
    rules={"official60":lambda x:x["score"]>=60,
      "TXadjust60":lambda x:x["adjusted"]>=60,
      "official60_and_TX_better_minus1":lambda x:x["score"]>=60 and x["txPct"]> -1,
      "TXadjust60_and_TX_better_minus1":lambda x:x["adjusted"]>=60 and x["txPct"]> -1,
      "TXadjust55":lambda x:x["adjusted"]>=55,
      "TXadjust65":lambda x:x["adjusted"]>=65,
      "TXadjust60_and_TX_better_minus2":lambda x:x["adjusted"]>=60 and x["txPct"]> -2,
      "TXadjust60_and_TX_better_minusHalf":lambda x:x["adjusted"]>=60 and x["txPct"]> -.5}
    return {name:summarize(rows,rule) for name,rule in rules.items()}
def main():
    risk=risk_rows()
    report={"period":["2023-10-09","2026-10-08"],"cashRiskDays":len(risk),"potentialNextDays":len(risk)-1,
      "txRows":0,"pairedNights":0,"coveragePct":0,"source":"FinMind TaiwanFuturesDaily TX position/after_market; TAIFEX next-day-night assignment",
      "status":"NO_VALIDATED_TX_BACKTEST","missing":{},"error":None,"train2023_2024":{},"evaluate2025_2026":{},"all":{},
      "caveats":["Risk classification only. Next cash close-to-close outcome is NOT executable trade P&L.",
        "Historical FinMind must be crosschecked against sample dated TAIFEX reports.",
        "No historical intraday 09:30 veto was tested; minute-index data not present.",
        "Survivorship and G stock strategies are NOT part of this index-only study.",
        "2026 has been researched before and is not a pristine untouched holdout.",
        "All score thresholds predeclared; compare false blocked up days as well as avoided loss days."]}
    pairs=[]
    try:
        tx=tx_rows();report["txRows"]=len(tx)
        pairs,missing=pair(risk,normalize(tx));report["missing"]=missing
        report["pairedNights"]=len(pairs);report["coveragePct"]=round(len(pairs)/(len(risk)-1)*100,2)
        if len(pairs)>=500 and report["coveragePct"]>=85:
            report["status"]="COMPARATIVE_RESEARCH_ONLY"
            report["all"]=compare(pairs)
            train=[r for r in pairs if r["decisionDate"]<"2025-01-01"]
            test=[r for r in pairs if r["decisionDate"]>="2025-01-01"]
            report["train2023_2024"]={"n":len(train),"results":compare(train)}
            report["evaluate2025_2026"]={"n":len(test),"results":compare(test)}
        else:report["error"]="Insufficient date-locked TX night coverage: require 500 matched sessions and >=85% of official index sessions"
    except Exception as error:
        report["error"]=type(error).__name__+": "+str(error)[:300]
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/"summary.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    with (OUT/"paired_nights.csv").open("w",encoding="utf-8-sig",newline="") as f:
        fields=["cashDate","decisionDate","score","contract","txDay","txNight","txPct","txDelta","adjusted","outcomeCloseToClosePct"]
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(pairs)
    lines=["# TX 夜盤 × Risk Score 三年回測","",
     "結論狀態："+report["status"],"正式風控日數："+str(len(risk)),
     "有效配對夜盤："+str(len(pairs))+"/"+str(len(risk)-1)+"（"+str(report["coveragePct"])+"%）",
     "缺值原因："+json.dumps(report["missing"],ensure_ascii=False),"錯誤："+str(report["error"]),"",
     "## 研究限制"]+["- "+x for x in report["caveats"]]
    for key in ["train2023_2024","evaluate2025_2026","all"]:
        t=report[key]
        if not t:continue
        lines.extend(["","## "+key,"| 規則 | 允許天數 | 大跌2%日通過率 | 避開全部大跌2%日比例 | 錯過上漲日比例 |",
                      "|---|---:|---:|---:|---:|"])
        for name,s in t.get("results",t).items():
            lines.append("| "+name+" | "+str(s["pass"])+" | "+str(s["passNextLoss2Pct"])+"% | "+str(s["avoidedOfAllLoss2Pct"])+"% | "+str(s["upDaysMissedPct"])+"% |")
    (OUT/"report.md").write_text("\n".join(lines)+"\n",encoding="utf-8")
    print(json.dumps({k:report[k] for k in ("status","cashRiskDays","txRows","pairedNights","coveragePct","missing","error")},ensure_ascii=False))
if __name__=="__main__":main()
