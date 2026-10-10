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

def months_before(iso,months=2):
    day=date.fromisoformat(iso)
    total=day.year*12+day.month-1-months
    y,m=divmod(total,12);m+=1
    return date(y,m,min(day.day,calendar.monthrange(y,m)[1])).isoformat()

def build(daily,asof=None):
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
            daily_rows[model].append((day,rows))
    results={}
    for model in MODELS:
        records=daily_rows[model]
        seen=defaultdict(list)
        signal_count=0
        for day,rows in records:
            if rows:signal_count+=1
            once=set()
            for rank,stock in enumerate(rows,1):
                code=str(stock.get("code") or "").strip()
                market=str(stock.get("market") or "").strip()
                if not code or market not in ("上市","上櫃"):continue
                key=(market,code)
                if key in once:raise RuntimeError("Duplicate stock in one frozen Top list "+day+" "+model+" "+code)
                once.add(key)
                seen[key].append((day,rank,stock))
        repeats=[]
        for (market,code),history in seen.items():
            if len(history)<2:continue
            history.sort(key=lambda x:x[0])
            last,rank,stock=history[-1];previous=history[-2][0]
            value={k:stock.get(k) for k in (
                "code","name","market","theme","subIndustry","total","gScore","sarText",
                "close","currentPrice","rs20","ret5","ret20","turnoverB","rvol",
                "foreignToday","trustToday","ma20Slope","signal")}
            value.update({"count":len(history),"firstSeen":history[0][0],
                "lastSeen":last,"previousSeen":previous,"lastRank":rank,
                "onReferenceDate":last==latest,
                "dates":[d for d,_,_ in history]})
            # Never publish a stale intraday quote in frozen history.
            value.pop("currentPrice",None)
            repeats.append(value)
        repeats.sort(key=lambda r:(not r["onReferenceDate"],-r["count"],-r["lastSeen"],r["lastRank"],r["code"]))
        results[model]={"snapshotDays":len(records),
            "signalDays":signal_count,
            "firstSnapshot":records[0][0] if records else None,
            "lastSnapshot":records[-1][0] if records else None,
            "repeatedSymbols":len(repeats),"stocks":repeats}
    return {"version":VERSION,
        "generatedAt":datetime.now(ZoneInfo("Asia/Taipei")).isoformat(timespec="seconds"),
        "referenceDate":latest,"windowStart":earliest,"calendarWindowMonths":2,
        "source":"Original frozen docs/data/daily/YYYY-MM-DD.json ranked models only",
        "calendarDaysAvailable":len(days),
        "savedDates":days,"models":results,
        "meaning":"Counts unique frozen model Top-list appearances on distinct market dates, not candles or modeled backtest signals. Missing snapshots never count as zero or repeated. LastSeen is most recent; previousSeen is prior actual appearance.",
        "coverageWarning":"History began accumulating on different dates for different models; no reconstructed G/G Pro before their first genuine snapshot."}

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
