"""Run an isolated 365-day D vs E research backtest; NEVER overwrite production D results."""
from datetime import datetime,timedelta
from zoneinfo import ZoneInfo
from pathlib import Path
import argparse,json
from revenue_monthly import fetch_mops_monthly
from backtest import run

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--start",default="2025-10-08")
    parser.add_argument("--end",default="2026-10-07")
    parser.add_argument("--revenue-cache",default="cache/revenue_monthly")
    args=parser.parse_args()
    if (datetime.fromisoformat(args.end)-datetime.fromisoformat(args.start)).days+1!=365:
        raise SystemExit("E initial research requires exactly 365 calendar days")
    revenue=fetch_mops_monthly(args.start,args.end,Path(args.revenue_cache))
    print("revenue coverage:",json.dumps({"months":len(revenue.coverage),"stocks":len(revenue.rows),"policy":revenue.policy},ensure_ascii=False),flush=True)
    out=run(args.start,args.end,revenue=revenue,output_namespace="backtest_e")
    models={m["id"]:m for m in out["models"]}
    def group(m,h):
        g=next((x for x in m["summary"] if x["group"]=="Top3可用等權"),{})
        return g.get("d"+str(h),{})
    comparison={}
    for h in [1,3,5,10,20]:
        comparison[str(h)]={k:{"n":group(m,h).get("n"),"avg":group(m,h).get("avg"),"win":group(m,h).get("win"),
                         "portfolioNet":m["portfolio"]["d"+str(h)]["totalReturn"],
                         "mdd":m["portfolio"]["d"+str(h)]["maxDrawdown"]}
                       for k,m in models.items()}
    report={"period":out["period"],"days":out["signalDays"],"universe":out["universeCount"],"historyErrors":out["historyErrors"],
            "institutionErrors":out["institutionErrors"],"revenuePolicy":out["revenuePolicy"],"revenueMonthSources":len(out["revenueCoverage"]),
            "candidates":{k:models[k]["candidateStats"] for k in models},
            "comparison":comparison}
    path=Path("docs/data/backtest_e/D_vs_E_1year_summary.json")
    path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print("D_VS_E_RESULT "+json.dumps(report,ensure_ascii=False),flush=True)
if __name__=="__main__":main()
