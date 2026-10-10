"""Rolling two-calendar-month repeat rankings from genuinely frozen daily Top lists.

Never recompute any historical selection from today's stock prices, and never
treat a missing model in an older snapshot as a zero-signal trading day.
Running it after full/intraday pipeline updates is deterministic and cheap.
"""
from __future__ import annotations
import calendar,json
from collections import defaultdict
from datetime import date,datetime
from pathlib import Path
from zoneinfo import ZoneInfo

DATA=Path(__file__).resolve().parents[1]/"docs"/"data"
MODELS=("G","G Pro","D","F","F2","A")
VERSION="TWO_CALENDAR_MONTHS_FROZEN_TOP20_V1"
MIXED_VERSION="TWO_CALENDAR_MONTHS_FROZEN_PLUS_RECONSTRUCTED_G_V2"

def months_before(iso,months=2):
    day=date.fromisoformat(iso)
    total=day.year*12+day.month-1-months
    y,m=divmod(total,12);m+=1
    return date(y,m,min(day.day,calendar.monthrange(y,m)[1])).isoformat()

def build(daily,asof=None,reconstruction=None):
    indexfile=daily/"index.json"
    if not indexfile.exists():raise RuntimeError("Missing daily snapshot index")
    idx=json.loads(indexfile.read_text(encoding="utf-8"))
    if not isinstance(idx,list) or not idx:raise RuntimeError("Daily index is empty")
    dates=sorted({str(row.get("date") or "") for row in idx if isinstance(row,dict) and row.get("date")})
    if not dates:raise RuntimeError("No valid daily dates")
    latest=asof or dates[-1]
    date.fromisoformat(latest)
    earliest=months_before(latest)
    days=[x for x in dates if earliest<=x<=latest]
    # Empty and absent have different meanings. Same symbol on same date is
    # counted exactly once, regardless of duplicate rows in source file.
    daily_rows={model:[] for model in MODELS}
    index_counts={str(x.get("date")):x for x in idx if isinstance(x,dict)}
    index_names={"G":"gCount","G Pro":"gProCount","D":"dCount","F":"fCount","F2":"f2Count","A":"aCount"}
    for day in days:
        rawfile=daily/f"{day}.json"
        if not rawfile.exists():raise RuntimeError("Indexed snapshot file missing "+day)
        snap=json.loads(rawfile.read_text(encoding="utf-8"))
        if str(snap.get("dataDate"))!=day:raise RuntimeError("Daily snapshot date does not match "+day)
        models=snap.get("models")
        if not isinstance(models,dict):raise RuntimeError("Invalid models in "+day)
        for model in MODELS:
            if model not in models:
                if index_counts[day].get(index_names[model]) is not None:
                    raise RuntimeError("Index claims "+model+" but missing from snapshot "+day)
                continue
            rows=models[model]
            if not isinstance(rows,list):raise RuntimeError("Model list malformed: "+model+" "+day)
            expected=index_counts[day].get(index_names[model])
            if expected is not None and expected!=len(rows):
                raise RuntimeError("Frozen snapshot/index count mismatch: "+model+" "+day)
            daily_rows[model].append((day,rows,"original_frozen"))
    # Read the separate research archive only when an original G day is missing.
    # NEVER change daily/ and never describe the rebuilt ranking as frozen.
    reconstructed_count=0
    if reconstruction is None:
        path=daily.parent/"research"/"g_history_reconstruction_2m"/"history.json"
        if path.exists():
            reconstruction=json.loads(path.read_text(encoding="utf-8"))
    if reconstruction is not None:
        if reconstruction.get("version")!="G_LIVE_DOUBLE_PERSIST_HISTORICAL_RECONSTRUCTION_V1":
            raise RuntimeError("Reconstructed G provenance version invalid")
        ref=reconstruction.get("referenceDate")
        if not ref or ref>latest or reconstruction.get("model")!="G":
            raise RuntimeError("Reconstructed G reference date/model invalid")
        rebuilt=reconstruction.get("days") or {}
        frozen_dates={d for d,_,_ in daily_rows["G"]}
        for day in sorted(rebuilt):
            if not(earliest<=day<=latest) or day in frozen_dates:continue
            row=rebuilt[day];stocks=row.get("stocks")
            if row.get("dataDate")!=day or row.get("source")!="reconstructed" or not isinstance(stocks,list) or len(stocks)>20:
                raise RuntimeError("Malformed G reconstruction "+day)
            if any(x.get("dataOrigin")!="retrospectively_reconstructed_not_historical_snapshot" for x in stocks):
                raise RuntimeError("Unlabeled historical reconstruction "+day)
            daily_rows["G"].append((day,stocks,"reconstructed"))
            reconstructed_count+=1
    for model in MODELS:daily_rows[model].sort(key=lambda x:x[0])
    results={}
    for model in MODELS:
        records=daily_rows[model]
        seen=defaultdict(list)
        signal_count=0
        for day,rows,origin in records:
            if rows:signal_count+=1
            once=set()
            for rank,stock in enumerate(rows,1):
                code=str(stock.get("code") or "").strip()
                market=str(stock.get("market") or "").strip()
                if not code or market not in ("上市","上櫃"):continue
                key=(market,code)
                if key in once:raise RuntimeError("Duplicate stock in one frozen Top list "+day+" "+model+" "+code)
                once.add(key)
                seen[key].append((day,rank,stock,origin))
        repeats=[]
        for (market,code),history in seen.items():
            if len(history)<2:continue
            history.sort(key=lambda x:x[0])
            last,rank,stock,origin=history[-1];previous=history[-2][0]
            value={k:stock.get(k) for k in (
                "code","name","market","theme","subIndustry","total","gScore","sarText",
                "close","currentPrice","rs20","ret5","ret20","turnoverB","rvol",
                "foreignToday","trustToday","ma20Slope","signal")}
            value.update({"count":len(history),"firstSeen":history[0][0],
                "lastSeen":last,"previousSeen":previous,"lastRank":rank,
                "onReferenceDate":last==latest,
                "dates":[d for d,_,_,_ in history],
                "lastSeenSource":origin,
                "reconstructedCount":sum(src=="reconstructed" for _,_,_,src in history),
                "frozenCount":sum(src=="original_frozen" for _,_,_,src in history)})
            # Never publish a stale intraday quote in frozen history.
            value.pop("currentPrice",None)
            repeats.append(value)
        repeats.sort(key=lambda r:(not r["onReferenceDate"],-r["count"],-int(r["lastSeen"].replace("-","")),r["lastRank"],r["code"]))
        results[model]={"snapshotDays":sum(src=="original_frozen" for _,_,src in records),
            "reconstructedDays":sum(src=="reconstructed" for _,_,src in records),
            "totalObservedDays":len(records),
            "firstCovered":records[0][0] if records else None,
            "lastCovered":records[-1][0] if records else None,
            "signalDays":signal_count,
            "firstSnapshot":next((d for d,_,src in records if src=="original_frozen"),None),
            "lastSnapshot":next((d for d,_,src in reversed(records) if src=="original_frozen"),None),
            "repeatedSymbols":len(repeats),"stocks":repeats}
    return {"version":MIXED_VERSION if reconstructed_count else VERSION,
        "generatedAt":datetime.now(ZoneInfo("Asia/Taipei")).isoformat(timespec="seconds"),
        "referenceDate":latest,"windowStart":earliest,"calendarWindowMonths":2,
        "source":"Original frozen days plus explicitly labeled research rebuilt G (only when missing)" if reconstructed_count else "Original frozen docs/data/daily/YYYY-MM-DD.json ranked models only",
        "calendarDaysAvailable":len(days),
        "backfilledGCalendarDays":reconstructed_count,
        "effectiveMarketDates":len(set(days)|{d for d,_,_ in daily_rows["G"]}),
        "savedDates":days,"models":results,
        "meaning":"Distinct dated top-ranking appearances; actual snapshots always take priority. G research reconstruction dates are separately counted and labeled, never presented as originally published.",
        "coverageWarning":"Retrospective G is subject to current survivor universe/capital and historical OHLC revisions. G Pro and other models stay frozen-only."}

def main():
    DATA.mkdir(parents=True,exist_ok=True)
    latest=DATA/"latest.json"
    if not latest.exists():raise RuntimeError("Latest live data missing")
    live=json.loads(latest.read_text(encoding="utf-8"))
    reference=str(live.get("dataDate") or "")
    if not reference:raise RuntimeError("Latest live data date missing")
    value=build(DATA/"daily",reference)
    # Fail closed when the new daily payload was not archived yet.
    if reference not in value["savedDates"]:raise RuntimeError("Latest market date not present in official daily index")
    target=DATA/"rolling-repeats.json"
    target.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding="utf-8")
    print("ROLLING_RANKING_REPEATS_OK",json.dumps({
        "reference":reference,"windowStart":value["windowStart"],
        "calendarDays":value["calendarDaysAvailable"],
        "models":{k:{"snapshotDays":v["snapshotDays"],"repeats":v["repeatedSymbols"]} for k,v in value["models"].items()}},
        ensure_ascii=False),flush=True)

if __name__=="__main__":main()
