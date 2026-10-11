"""Auditable official TWSE extended history coverage; no fabricated or interpolated days."""
import json
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
DATA=Path(__file__).resolve().parents[1]/"docs"/"data"/"research"
ROOT=DATA/"market_history_extended"
def main():
    years=[];known=0;verified=0
    for year in range(2015,2024):
        p=ROOT/"years"/(str(year)+".json")
        if not p.exists():
            years.append({"year":year,"status":"NOT_STARTED","tradingDays":None,
                "officialValidDays":0,"riskScoredDays":0,"complete":False});continue
        d=json.loads(p.read_text(encoding="utf-8"));c=d["coverage"]
        if d["year"]!=year or len(d["riskRows"])!=c["riskScoredDays"]:raise RuntimeError("Corrupt year "+str(year))
        years.append({"year":year,"status":"COMPLETE" if c["complete"] else "PARTIAL",
            "tradingDays":c["tradingDays"],"officialValidDays":c["officialValidDays"],
            "riskScoredDays":c["riskScoredDays"],"complete":c["complete"],
            "coveragePct":c["coveragePct"],"missingSample":[x["date"] for x in d["errors"][:6]]})
        known+=c["tradingDays"];verified+=c["riskScoredDays"]
    old=json.loads((DATA/"g_regime_3y"/"coverage.json").read_text(encoding="utf-8"))
    if not old.get("complete") or old["riskScoredDays"]!=728:raise RuntimeError("Original 728 dates changed")
    result={"createdAt":datetime.now(ZoneInfo("Asia/Taipei")).isoformat(),
        "originalThreeYearArchiveUnchanged":True,"annualCoverage":years,
        "newOfficialVerifiedDays":verified,"newTargetDaysWithIndex":known,
        "totalKnownVerifiedDailyRows":verified+728,
        "completeYears":sum(z["complete"] for z in years),
        "message":"Yearly shards with missing TWSE report dates are incomplete, not silently filled. Time-series models only use a contiguous fully complete chain."}
    ROOT.mkdir(parents=True,exist_ok=True)
    (ROOT/"summary.json").write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False),encoding="utf-8")
    print("EXTENDED_HISTORY_COVERAGE",json.dumps({"newDays":verified,"knownDays":known,
        "completeYears":result["completeYears"],"combined":verified+728},ensure_ascii=False),flush=True)
if __name__=="__main__":main()
