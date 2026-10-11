"""Locked research summary for practical homepage G/D stock entry playbook.
Uses published 2025 validation and 2026 time-ordered research, not new AI fitting.
Does NOT assert any live 09:00 price/breadth history or backtested minute-entry edge.
"""
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
ROOT=Path(__file__).resolve().parents[1]/"docs"/"data"
R=ROOT/"research"
OUT=R/"market_entry_playbook"
def load(p):return json.loads(p.read_text(encoding="utf-8"))
def case(study,model,h,gate,fold):
    z=[x for x in study["results"] if x["model"]==model and x["horizon"]==h and x["gate"]==gate and x["fold"]==fold]
    if len(z)!=1:raise RuntimeError(f"Case not found {model} {h} {gate} {fold}")
    x=z[0];s=x["signalReturn"];eq=x["exitSampledOneBasketCash"]
    if not s["n"] or s["averageNetPct"] is None:raise RuntimeError("Incomplete published experiment")
    return {"n":s["n"],"meanNetPct":s["averageNetPct"],"winPct":s["winPct"],
        "exitSampledCapitalReturnPct":eq["exitSampledReturnPct"],
        "exitSampledMDDPct":eq["exitSampledMDDPct"]}
def build():
    study=load(R/"market_stock_ml_oos"/"summary.json")
    stability=load(R/"market_stock_ml_oos"/"stability_bootstrap.json")
    breadth=load(R/"market_preopen_breadth"/"summary.json")
    latest=load(ROOT/"latest.json")
    if study["marketRows"]!=728 or breadth["outcomeCount"]!=726 or stability["blockDays"]!=20:raise RuntimeError("Published market evidence not verified")
    if study["periods"]["validation"][0]!="2025-01-01" or study["periods"]["holdout"][0]!="2026-01-01":raise RuntimeError("Study fold mismatch")
    if latest.get("dataDate")!=(latest.get("risk") or {}).get("date"):raise RuntimeError("Cash risk date mismatch")
    cases={"G20_RISK60":("G",20,"SCORE_GE60"),"G20_RISK80":("G",20,"SCORE_GE80"),
      "G10_RISK60":("G",10,"SCORE_GE60"),"G1_RISK60":("G",1,"SCORE_GE60"),
      "D10_RISK60":("D",10,"SCORE_GE60"),"G10_GRU_RISK60":("G",10,"GRU_GE50_AND_SCORE60")}
    comparison={}
    for key,(model,h,gate) in cases.items():
        comparison[key]={fold:case(study,model,h,gate,fold) for fold in ("validation","holdout")}
    # Rules depend on 2025 validation only. 2026 is reported solely for independent
    # time-order checking; prior research had already looked at 2026.
    if comparison["G20_RISK60"]["validation"]["meanNetPct"]<=0 or comparison["D10_RISK60"]["validation"]["meanNetPct"]<=0:raise RuntimeError("Baseline validation failed")
    if comparison["G20_RISK80"]["validation"]["n"]<35:raise RuntimeError("G80 validation lacks minimum samples")
    if comparison["G10_GRU_RISK60"]["validation"]["meanNetPct"]>=comparison["G10_RISK60"]["validation"]["meanNetPct"]:
        raise RuntimeError("Review AI gate before using this predeclared decision")
    boot={}
    for x in stability["results"]:
        if x["model"]=="G" and x["horizon"]==20:
            z=x["fixedPolicies"]["SCORE_GE80"]
            boot[x["fold"]]={"differenceRisk80MinusRisk60PctPts":z["meanNetImprovementVsScore60Pts"],"CI95PctPts":z["delta95IntervalPctPts"],"excludesZero":z["excludesZero"]}
    if set(boot)!={"2025","2026"}:raise RuntimeError("Missing date-block bootstrap")
    return {"version":"MARKET_ENTRY_PLAYBOOK_2026_V1","generatedAt":datetime.now(ZoneInfo("Asia/Taipei")).isoformat(),
      "source2025ValidationOnly":True,"testYear2026PreviouslyInspected":True,
      "referenceCashDate":latest["dataDate"],"referenceCashRiskScore":latest["risk"]["score"],
      "research":{"marketDays":study["marketRows"],"training":study["training"],
         "noMinuteOHLC":True,"noLive09ClockClaims":True,"roundTripCostPct":study["transactionCostRoundTripPct"]},
      "policy":{"risk60":"minimum trend candidate, not an execution permission",
         "risk80":"stronger G20 context, not proven incremental win over Risk60",
         "strongTop":"veto追價","09to1330":"lack live breadth and G synchrony: wait for independently verified confirmation",
         "nightTX":"completed night market is preopen caution only, never an automatic positive buy gate",
         "GRU":"research-only; failed validation and not used for buy permission"},
      "comparisons":comparison,"blockBootstrapG20Risk80Vs60":boot,
      "nextDayBreadth":{"baselineMajorityUpPct":breadth["baseline"]["nextStockMajorityUpPct"],
         "risk60MajorityUpPct":breadth["candidateThresholds"]["GE_60"]["nextStockMajorityUpPct"],
         "risk80MajorityUpPct":breadth["candidateThresholds"]["GE_80"]["nextStockMajorityUpPct"]},
      "limitations":["2026 was inspected previously; not pristine holdout",
         "Daily overlapping stock returns are not investable compounded account equity",
         "Exit-sampled capital MDD is not daily marked-to-market MDD",
         "No historic 09:15/09:30 market-wide synchronized prices or true intraday breadth",
         "Current universe/survivorship bias; G80 vs G60 bootstrap confidence intervals cross zero"]}
def report(x):
    lines=["# 台股買進時機：研究佐證與主頁規則","","**這是前次已完成 728 交易日研究的再驗證，不是新訓練的深度模型；GRU 原本已實際研究。**","","| 情境 | 2025 驗證 n／平均淨報酬 | 2026 時序測試 n／平均淨報酬 |","|---|---:|---:|"]
    for k,v in x["comparisons"].items():
        a=v["validation"];b=v["holdout"]
        lines.append(f"| {k} | {a['n']}／{a['meanNetPct']:+.3f}% | {b['n']}／{b['meanNetPct']:+.3f}% |")
    lines+=["","20D G Risk>=80 相對 >=60 的20交易日區塊 Bootstrap 差異：",
      *[f"- {year}: {item['differenceRisk80MinusRisk60PctPts']:+.3f} pp，95% CI {item['CI95PctPts']}，排除零：{item['excludesZero']}" for year,item in x["blockBootstrapG20Risk80Vs60"].items()],
      "","實務方向：Risk >=60 只代表隔日波段研究條件；Risk >=80 表示更強波段環境。出現已確認 TOP 則暫緩追價。沒有即時市場廣度或 G 同步率，不發布『盤中立即買進』聲明。",
      "","2026 曾在先前研究被檢視；歷史報酬含交易成本，但不能當作未來獲利或真實帳戶複利。",
      "","來源：market_stock_ml_oos/summary.json、stability_bootstrap.json、market_preopen_breadth/summary.json。",""]
    return "\n".join(lines)
if __name__=="__main__":
    v=build();OUT.mkdir(parents=True,exist_ok=True)
    (OUT/"summary.json").write_text(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False),encoding="utf-8")
    (OUT/"report.md").write_text(report(v),encoding="utf-8")
    print("ENTRY_PLAYBOOK_VERIFIED",json.dumps({k:{y:row["meanNetPct"] for y,row in a.items()} for k,a in v["comparisons"].items()},ensure_ascii=False))
