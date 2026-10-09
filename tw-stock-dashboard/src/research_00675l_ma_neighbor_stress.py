"""Parameter-neighbor stability audit; deliberately no picking new winners on later data."""
from __future__ import annotations
import json,itertools,time
import numpy as np
from datetime import datetime
from zoneinfo import ZoneInfo
from research_00675l_ma_family_2020_2026 import data,metrics,ma_array,localarrays,mkcfg,simulate,basic,FULL,TRAIN,VALID,AUDIT,OUT
from research_00675l_near_hold_switch import bt
CASES=[
  {"id":"WMA_twii_N5_OUT1_RE2_C3","name":"WMA5_index","family":"WMA","src":"twii","windows":(5,8,10),"breaks":(0,.01,.02),"re":(.01,.02,.03)},
  {"id":"EMA_twii_N5_OUT1_RE2_C3","name":"EMA5_index","family":"EMA","src":"twii","windows":(5,8,10),"breaks":(0,.01,.02),"re":(.01,.02,.03)},
  {"id":"VWMA_close_N12_OUT4_RE2_C3","name":"VWMA12_etf","family":"VWMA","src":"close","windows":(10,12,15),"breaks":(.03,.04,.05),"re":(.01,.02,.03)},
  {"id":"SMA_twii_N10_OUT2_RE1_C3","name":"SMA10_original","family":"SMA","src":"twii","windows":(8,10,12),"breaks":(.01,.02,.03),"re":(0,.01,.02)}
]
def quantile(values):
    if not values:return None
    a=np.array(values,dtype=float)
    return {"min":round(float(np.min(a)),3),"p25":round(float(np.percentile(a,25)),3),
            "median":round(float(np.median(a)),3),"p75":round(float(np.percentile(a,75)),3),
            "max":round(float(np.max(a)),3)}
def run():
    started=time.monotonic()
    d,a,dates=data()
    baseline={"id":"SMA_twii_N10_OUT2_RE1_C3"}
    sma=mkcfg("SMA","twii",10,.02,.01,3)
    means={}
    for c in CASES:
        for n in c["windows"]:
            key=(c["family"],c["src"],n)
            if key in means:continue
            vol=a["index_volume" if c["src"]=="twii" else "volume"] if c["family"]=="VWMA" else None
            means[key]=ma_array(a[c["src"]],vol,c["family"],n)
    sma24=simulate(a,dates,means,sma,VALID)
    sma26=simulate(a,dates,means,sma,AUDIT)
    smafull=simulate(a,dates,means,sma,FULL)
    assert smafull["returnPct"]==3312.334
    original={"validation2024_2025":sma24["returnPct"],"audit2026":sma26["returnPct"],
        "full2020_2026":smafull["returnPct"],"fullDD":smafull["mddPct"]}
    records=[]
    summaries=[]
    for family in CASES:
        group=[]
        for n,down,up,confirm in itertools.product(family["windows"],family["breaks"],family["re"],(2,3)):
            cfg=mkcfg(family["family"],family["src"],n,down,up,confirm)
            train=simulate(a,dates,means,cfg,TRAIN)
            val=simulate(a,dates,means,cfg,VALID)
            audit=simulate(a,dates,means,cfg,AUDIT)
            full=simulate(a,dates,means,cfg,FULL)
            item={"id":cfg["id"],"name":family["name"],"n":n,"exitPct":down*100,"reenterPct":up*100,
                "confirm":confirm,"trainPct":train["returnPct"],"validationPct":val["returnPct"],
                "auditPct":audit["returnPct"],"allPct":full["returnPct"],
                "allMDDPct":full["mddPct"],"exitCount":full["riskOffSells"],
                "beatsSMAValidation":val["returnPct"]>sma24["returnPct"],
                "beatsSMA2026":audit["returnPct"]>sma26["returnPct"],
                "beatsSMAFull":full["returnPct"]>smafull["returnPct"]}
            group.append(item);records.append(item)
        central=next((z for z in group if z["id"]==family["id"]),None)
        assert central is not None,("missing central",family["id"])
        summary={"id":family["id"],"name":family["name"],"cases":len(group),
            "center":{"trainPct":central["trainPct"],"validationPct":central["validationPct"],
                "auditPct":central["auditPct"],"allPct":central["allPct"],"allMDDPct":central["allMDDPct"]},
            "validationDistribution":quantile([z["validationPct"] for z in group]),
            "auditDistribution":quantile([z["auditPct"] for z in group]),
            "fullDistribution":quantile([z["allPct"] for z in group]),
            "fullMaxDDDistribution":quantile([z["allMDDPct"] for z in group]),
            "beatSMA2024_25Count":sum(z["beatsSMAValidation"] for z in group),
            "beatSMA2026Count":sum(z["beatsSMA2026"] for z in group),
            "beatSMA2020_26Count":sum(z["beatsSMAFull"] for z in group),
            "beatsSMA2024_25and2026Count":sum(z["beatsSMAValidation"] and z["beatsSMA2026"] for z in group),
            "positive2020_2023Count":sum(z["trainPct"]>0 for z in group),
            "positiveValidationCount":sum(z["validationPct"]>0 for z in group),
            "positive2026Count":sum(z["auditPct"]>0 for z in group)}
        summaries.append(summary)
        print("MA_NEIGHBOR_SUMMARY "+json.dumps(summary,ensure_ascii=False),flush=True)
    missing_index_dates=d.loc[(d.date>="2020-01-01")&((~np.isfinite(d.index_volume))|(d.index_volume<=0)),"date"].tolist()
    output={"version":"00675L_MA_FAMILY_NEIGHBOR_AUDIT_V1",
        "generatedAt":datetime.now(ZoneInfo("Asia/Taipei")).isoformat(timespec="seconds"),
        "period":"2020-01-02 to 2026-10-07",
        "note":"Sensitivity ONLY. Neighbors not newly selected based on 2024-26 data; center preselected using 2020-23 or original 2024 baseline.",
        "originalSMA":original,
        "sourceVolumeMissingTaiwanIndexDays":missing_index_dates,
        "groups":summaries,"allParameterNeighbors":records,
        "elapsedSeconds":round(time.monotonic()-started,1)}
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/"neighborhood.json").write_text(json.dumps(output,ensure_ascii=False,indent=2),encoding="utf-8")
    print("MA_NEIGHBORS_DONE "+json.dumps({"tested":len(records),"seconds":output["elapsedSeconds"]}),flush=True)
if __name__=="__main__":run()
