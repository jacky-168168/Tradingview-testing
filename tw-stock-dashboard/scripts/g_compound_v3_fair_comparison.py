"""Post-published FAIR trading-rule-matched G Compound V3 comparison.
Separate learned ranking effect from exit-rule, sizing and market gate changes.
Does not recompute labels and never chooses on 2026 data.
"""
from __future__ import annotations
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]/"docs"/"data"/"research"
V1=ROOT/"g_compound_3y"/"summary.json"
V2=ROOT/"g_compound_v2_3y"/"summary.json"
OUT=ROOT/"g_compound_walkforward_3y"
def load(p):return json.loads(p.read_text(encoding="utf-8"))
def small(m):
    return {x:m.get(x) for x in ("capitalEnd","netReturnPct","maxDDPct","filledBuys",
        "closedTrades","wins","losses","winPct","avgNetPct","openAtEnd")}
def main():
    v1=load(V1);v2=load(V2);v3=load(OUT/"summary.json")
    a=v3["selectedBy2025Only"]
    if a.get("status")!="selected_by_2025_only":
        (OUT/"fair_comparison.json").write_text(json.dumps({
            "status":"no_selected_model","description":"No V3 model passed 2025 quality gate. Do not rank after seeing 2026."},
            ensure_ascii=False,indent=2),encoding="utf-8")
        return
    id=a["id"];item=next(x for x in v3["allCandidateModels"] if x["id"]==id)
    plan=v3["exitTemplates"][item["plan"]]
    cap=item["maxPerTradeTWD"]
    gate="SCORE60"
    tp=int(round(plan["tp"]*100));sl=int(round(plan["sl"]*100));hold=plan["hold"]
    c="ALL" if cap is None else f"{int(cap/1000)}K"
    g_id=f"G__{gate}__TP{tp}__SL{sl}__H{hold}__CAP{c}"
    original=next(x for x in v1["models"] if x["id"]==g_id)
    v2_id=f"Box20_Prebreak__{gate}__TP{tp:02d}__SL{sl:02d}__H{hold}__CAP{int(cap/1000) if cap is not None else 'ALL'}"
    prebreak=next(x for x in v2["models"] if x["id"]==v2_id)
    result={"version":"G_COMPOUND_V3_MATCHED_EXIT_PARITY_V1",
        "selectedModel":id,"sameExecution":{"riskGate":gate,"targetPct":tp,"stopPct":sl,
            "holdTradingDays":hold,"ticketCapTWD":cap,"initialAccountTWD":500000},
        "modelUses2026ForSelection":False,
        "comparators":{
          "Walk-forward learned Top1":{"id":id,"validation2025":small(item["periods"]["validation2025"]),
              "audit2026":small(item["periods"]["audit2026"]),
              "authorWindow2026":small(item["periods"]["authorWindow2026"])},
          "Original G Top1":{"id":g_id,"validation2025":small(original["byPeriod"]["validation"]),
              "audit2026":small(original["byPeriod"]["audit2026"]),
              "authorWindow2026":small(original["byPeriod"]["authorWindow2026"])},
          "Static Box20 Prebreak Top1":{"id":v2_id,"validation2025":small(prebreak["periods"]["validation"]),
              "audit2026":small(prebreak["periods"]["audit2026"]),
              "authorWindow2026":small(prebreak["periods"]["authorWindow2026"])}
        },
        "caveats":["All strategies use shared V1 study_one daily OHLC cash model; ranking itself differs.",
            "The learned V3 model also abstains on predicted nonpositive edge if POSITIVE in selected ID.",
            "2026 tested after seeing prior G and Box V2 findings; chronological order is correct but research is not pristine blind.",
            "Backtest adjusted OHLC, current-survivor universe, order fills, and T+2 capital reuse assumptions remain."]}
    if len({v["id"] for v in result["comparators"].values()})!=3:raise RuntimeError("Distinct matched comparators expected")
    for fold in ("validation2025","audit2026","authorWindow2026"):
        for name,z in result["comparators"].items():
            m=z[fold]
            if m["wins"]+m["losses"]!=m["closedTrades"]:raise RuntimeError(name+" inconsistent trade count")
            if m["capitalEnd"]<=0:raise RuntimeError(name+" invalid cash account")
    (OUT/"fair_comparison.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    print("V3_FAIR_2026",json.dumps({
        "rule":result["sameExecution"],
        "comparators":{n:{"2025":p["validation2025"]["netReturnPct"],
              "2026":p["audit2026"]["netReturnPct"],
              "2026MDD":p["audit2026"]["maxDDPct"],
              "authorPeriod":p["authorWindow2026"]["netReturnPct"]}
            for n,p in result["comparators"].items()}},ensure_ascii=False),flush=True)
if __name__=="__main__":main()
