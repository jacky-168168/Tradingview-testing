"""Publish independently verified TXF 2m/5m 2025-26 signal comparisons to
GitHub Pages, with full trade logs and true daily (not intrabar) equity chart.
Original minute-price data are not republished. Read-only archive only.
"""
from pathlib import Path
import subprocess,json,math
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/"docs/data/research/txf_extreme_reversal_2m_5m_2025_2026"
BRANCH="research/txf-extreme-reversal-trend70-2m-vs-5m"
SOURCE="tw-stock-dashboard/docs/data/research/txf_extreme_reversal_2m_5m_2025_2026/"
def get(name):
    r=subprocess.run(["git","show",f"origin/{BRANCH}:{SOURCE}{name}"],cwd=ROOT,capture_output=True,check=True)
    return json.loads(r.stdout)
def main():
    summary=get("summary.json");trace=get("trades_and_equity.json")
    assert summary["version"]=="TXF_EXTREME_REVERSAL_TREND70_2M_5M_V1"
    assert len(summary["results"])==36 and len(trace["cases"])==36
    BASE.mkdir(parents=True,exist_ok=True)
    original_models=[]
    for tf in (2,5):
        for mode in summary["variants"]:
            label=f"{tf}m_{mode}_2025_2026"
            source=trace["cases"][label]
            assert source["period"]==["2025-01-02","2026-08-31"]
            raw=source["equity"];txs=source["trades"]
            bydate={}
            for stamp,nav in raw:bydate[stamp[:10]]=round(nav,2)
            assert 200<len(bydate)<500
            out={"timeframeMin":tf,"mode":mode,"period":source["period"],
                "dailyEquityTWD":[[day,value] for day,value in bydate.items()],
                "simulatedTrades":txs,
                "note":"每日圖僅使用當日最後一筆帳戶權益，原回測中的日內最大回撤請以 summary.json 指標為準。"}
            target=f"cases/{tf}m_{mode}.json"
            BASE.joinpath("cases").mkdir(exist_ok=True)
            BASE.joinpath(target).write_text(json.dumps(out,ensure_ascii=False,separators=(",",":")),encoding="utf-8")
            result=next(z for z in summary["results"] if z["mode"]==mode and z["timeframeMin"]==tf and z["segment"]==source["period"])
            assert result["trades"]==len(txs)
            original_models.append({"id":f"{tf}m_{mode}","file":target,"trades":result["trades"]})
    summary["websiteModels"]=original_models
    summary["provenance"]={"studyBranch":BRANCH,
        "sourceSummary":f"https://github.com/jacky-168168/Tradingview-testing/blob/{BRANCH}/{SOURCE}summary.json",
        "sourceExecution":"https://github.com/jacky-168168/Tradingview-testing/actions/runs/37917535070",
        "sourceMinuteResearch":"https://github.com/jason43314-crypto/taiwan-futures-1min-ohlc"}
    (BASE/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    assert len(original_models)==12
    print("PASS TXF_WEBSITE "+json.dumps({"studies":12,"nperiods":3,"summary":len(summary["results"]),
       "dailyFiles":len(list(BASE.glob("cases/*.json"))),
       "savedTradeLogs":sum(x["trades"] for x in original_models)}),flush=True)
if __name__=="__main__":main()
