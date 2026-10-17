"""SqueezeMetrics DIX/GEX: conservative TWII association research, display-only.
Never changes the production risk score, G ranking, or any entry gate.
A US-session observation is used for a TW session only if its US date is
strictly before (TW session date - 1 calendar day): publication-lag embargo.
"""
from __future__ import annotations
import bisect,csv,io,json,math,os,urllib.request
from datetime import date,datetime,timedelta,timezone
from pathlib import Path

BASE=Path(__file__).resolve().parents[1]
DATA=BASE/"docs/data/research/us_options"
SOURCE="https://squeezemetrics.com/monitor/static/DIX.csv"

def read_source():
    req=urllib.request.Request(SOURCE,headers={"User-Agent":"Mozilla/5.0 (compatible; TWII-research/1.0)","Accept":"text/csv,*/*"})
    with urllib.request.urlopen(req,timeout=45) as res:
        raw=res.read(2_500_001)
        if len(raw)>2_500_000:raise ValueError("DIX CSV unexpectedly large")
    text=raw.decode("utf-8-sig").strip()
    reader=csv.DictReader(io.StringIO(text))
    if not {"date","price","dix","gex"}.issubset(set(reader.fieldnames or [])):raise ValueError("DIX CSV columns missing")
    items={}
    for row in reader:
        try:
            d=date.fromisoformat(row["date"].strip())
            price=float(row["price"]);dix=float(row["dix"]);gex=float(row["gex"])
            if not all(map(math.isfinite,(price,dix,gex))) or not(0.05<dix<0.95) or price<=0:continue
            if d>datetime.now(timezone.utc).date():continue
            items[d.isoformat()]={"date":d.isoformat(),"price":price,"dix":dix,"gex":gex}
        except (ValueError,TypeError,KeyError):continue
    out=sorted(items.values(),key=lambda x:x["date"])
    if len(out)<2000:raise ValueError(f"Historical DIX CSV too short ({len(out)} rows)")
    return out

def tw_market():
    out={}
    yearly=BASE/"docs/data/research/market_history_extended/years"
    for year in range(2015,2024):
        f=yearly/f"{year}.json"
        if not f.exists():continue
        for r in json.loads(f.read_text(encoding="utf-8")).get("riskRows",[]):
            try:
                d=r["date"];v=float(r["dayRet"])
                if math.isfinite(v) and r.get("index") and float(r["index"])>0:out[d]=v
            except (TypeError,ValueError,KeyError):continue
    f=BASE/"docs/data/research/g_regime_3y/market_risk_daily.csv"
    if f.exists():
        with f.open(encoding="utf-8-sig",newline="") as stream:
            for r in csv.DictReader(stream):
                try:
                    d=r["date"];v=float(r["dayRet"])
                    if math.isfinite(v) and float(r["index"])>0:out[d]=v
                except (TypeError,ValueError,KeyError):continue
    return sorted(out.items())

def round_stats(items):
    if not items:return {"n":0,"upRatePct":None,"meanReturnPct":None}
    n=len(items)
    return {"n":n,"upRatePct":round(100*sum(r>0 for r in items)/n,2),"meanReturnPct":round(sum(items)/n,4)}

def backtest(us,tw):
    dates=[x["date"] for x in us]
    aligned=[]
    for d,ret in tw:
        # t: Taiwan session; a US series updated after the US close is
        # not assumed publicly available on the immediate TW morning.
        cut=(date.fromisoformat(d)-timedelta(days=1)).isoformat()
        i=bisect.bisect_left(dates,cut)-1
        if i<0:continue
        obs=us[i]
        if (date.fromisoformat(d)-date.fromisoformat(obs["date"])).days>9:continue
        aligned.append({"date":d,"ret":ret,"gpos":obs["gex"]>=0,"dix45":obs["dix"]>=.45})
    groups={}
    for key,sel in [("training_2015_2021",lambda d:d<"2022"),("oos_2022_2023",lambda d:"2022"<=d<"2024"),("recent_2024_2026",lambda d:d>="2024")]:
        sub=[v for v in aligned if sel(v["date"])]
        gplus=round_stats([r["ret"] for r in sub if r["gpos"]])
        gminus=round_stats([r["ret"] for r in sub if not r["gpos"]])
        dplus=round_stats([r["ret"] for r in sub if r["dix45"]])
        dminus=round_stats([r["ret"] for r in sub if not r["dix45"]])
        valid=(gplus["n"]>=50 and gminus["n"]>=30)
        # Descriptive association only, never an automatic strategy gate.
        delta=round(gplus["upRatePct"]-gminus["upRatePct"],2) if valid else None
        groups[key]={"start":sub[0]["date"] if sub else None,"end":sub[-1]["date"] if sub else None,"n":len(sub),
                     "gexPositive":gplus,"gexNegative":gminus,"gexUpRateDiffPctPoints":delta,
                     "dixAtLeast45":dplus,"dixBelow45":dminus,"sufficientGexGroups":valid}
    return {"source":SOURCE,"twSource":"repository TWSE market-risk archive, original close-to-close dayRet",
        "updatedAt":datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "usSourceEnd":us[-1]["date"],"lagPolicy":"US date strictly before (TW date minus 1 calendar day); conservative publication embargo",
        "caution":"Association is not causation, and historical close-to-close TWII return is not a tradable open-to-close forecast. No risk-score weights changed.",
        "samples":len(aligned),"groups":groups}

def write_if_changed(path,obj,stable_keys):
    path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists():
        try:
            old=json.loads(path.read_text(encoding="utf-8"))
            if all(old.get(k)==obj.get(k) for k in stable_keys):return False
        except (ValueError,OSError):pass
    path.write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    return True

def main():
    us=read_source()
    latest=us[-1]
    age=(datetime.now(timezone.utc).date()-date.fromisoformat(latest["date"])).days
    if age>10:raise RuntimeError(f"Latest US data is stale: {latest['date']}")
    risk={"date":latest["date"],"dix":round(latest["dix"]*100,3),"gex":round(latest["gex"],2),
          "spx":round(latest["price"],3),"gammaState":"POSITIVE" if latest["gex"]>=0 else "NEGATIVE",
          "source":SOURCE,"updatedAt":datetime.now(timezone.utc).isoformat(timespec="seconds"),
          "message":"Only a delayed US options-positioning observation; NOT a Taiwan entry signal and NOT part of the market score."}
    changed1=write_if_changed(DATA/"latest.json",risk,["date","dix","gex","spx"])
    report=backtest(us,tw_market())
    changed2=write_if_changed(DATA/"backtest.json",report,["usSourceEnd","groups","samples","lagPolicy"])
    print(json.dumps({"latest":latest["date"],"sample":report["samples"],"changed":changed1 or changed2,"oos":report["groups"]["oos_2022_2023"],"recent":report["groups"]["recent_2024_2026"]},ensure_ascii=False))
if __name__=="__main__":main()
