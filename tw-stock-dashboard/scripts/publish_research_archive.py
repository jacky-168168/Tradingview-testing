"""Publish verified research GitHub Actions JSON into permanent static-site assets.
Source: successful 2026 selectors-vs-execution artifact. No selecting new winners,
no code changes to the underlying published main strategies.
"""
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
def main():
    parser=argparse.ArgumentParser();parser.add_argument("--artifact",required=True);parser.add_argument("--dest",required=True)
    opts=parser.parse_args()
    source=Path(opts.artifact);out=Path(opts.dest)
    with (source/"selector_execution_2026_summary.json").open(encoding="utf-8") as f:report=json.load(f)
    with (source/"selector_execution_2026_trades.json").open(encoding="utf-8") as f:trades=json.load(f)
    models=report.get("allModelStatistics") or {}
    assert len(models)==17,f"Expected 17 published models, got {len(models)}"
    assert len(trades)==17
    assert set(models)==set(trades),f"Model mismatch {set(models)^set(trades)}"
    expected={("G_DOUBLE_PERSIST","10","ladder"):(171,73.68),("G_STRICT","10","ladder"):(201,81.09),
              ("H5_FRESH_BREAK","10","ladder"):(246,78.46)}
    for (model,h,mode),(fills,tp) in expected.items():
        a=models[model][h][mode]
        assert (a["filled"],a["takeProfitPct"])==(fills,tp),f"Mismatch: {model}/{h}/{mode}"
    out.mkdir(exist_ok=True,parents=True)
    (out/"trades").mkdir(exist_ok=True)
    def save(p,x):
        p.write_text(json.dumps(x,ensure_ascii=False,separators=(",",":"),allow_nan=False),encoding="utf-8")
    save(out/"selector_execution_2026_summary.json",report)
    index={"version":"2026-model-17x2x3","period":report["period"],"generatedAt":report["generatedAt"],
           "modelIds":list(models),"methodIds":["ladder","ma"],"holdingDays":[5,10,20],
           "statsFile":"selector_execution_2026_summary.json",
           "tradesFiles":{model:f"trades/{model}.json" for model in models},
           "status":"retrospective research; no real-money returns or independent 2026 holdout"}
    save(out/"index.json",index)
    for model,obj in trades.items():
        assert all(str(h) in obj for h in (5,10,20)) and len(obj)==3,f"Missing trade horizon {model}"
        for h,modes in obj.items():
            for mode,rows in modes.items():
                assert len(rows)>=models[model][h][mode]["filled"],"Insufficient event rows"
        save(out/"trades"/f"{model}.json",obj)
    print("PUBLISH_VALIDATED "+json.dumps({"models":len(models),"scenarios":sum(len(v[h]) for v in models.values() for h in ("5","10","20")),"trades":sum(len(row) for obj in trades.values() for mode in obj.values() for row in mode.values()),"out":str(out)},ensure_ascii=False))
if __name__=="__main__":main()
