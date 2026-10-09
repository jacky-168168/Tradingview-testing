"""Date-pinned TWIF futures sessions for the dashboard (official TAIFEX).
Official DailyMarketReportFut is a completed-session report, NOT a live feed.
Use TAIFEX:TXF1! TradingView widget for delayed/live intraday context.
No inference when overnight quote is missing, stale, or contract has rolled.
"""
from __future__ import annotations
import json,re
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import requests
from config import DATA_DIR
ENDPOINT="https://openapi.taifex.com.tw/v1/DailyMarketReportFut"
OUT=DATA_DIR/"futures"/"latest.json"
UA={"User-Agent":"Mozilla/5.0 TW Stock Dashboard research contact github.com/jacky-168168","Accept":"application/json"}
def num(v):
    if v is None:return None
    try:return float(str(v).replace(",","").replace("%","").strip())
    except (ValueError,TypeError):return None
def session(s):
    t=str(s or "").strip()
    if t in ("一般","一般交易","一般交易時段"):return "DAY"
    if t in ("盤後","盤後交易","盤後交易時段"):return "NIGHT"
    return None
def parse(rows):
    if not isinstance(rows,list) or not rows:raise RuntimeError("Empty official TAIFEX report")
    usable=[]
    for x in rows:
        if str(x.get("Contract") or "").strip()!="TX":continue
        date=str(x.get("Date") or "").replace("/","").strip()
        mon=str(x.get("ContractMonth(Week)") or "").strip()
        ss=session(x.get("TradingSession"))
        if not(re.fullmatch(r"20\d{6}",date) and re.fullmatch(r"20\d{4}",mon) and ss):continue
        px=num(x.get("Last"));vol=num(x.get("Volume"))
        if px is None or px<=0 or vol is None or vol<=0:continue
        usable.append({"date":date,"contract":mon,"session":ss,"close":px,"volume":int(vol),
            "open":num(x.get("Open")),"high":num(x.get("High")),"low":num(x.get("Low"))})
    if not usable:raise RuntimeError("TAIFEX payload has no traded TX session")
    newest=max(x["date"] for x in usable)
    group=[x for x in usable if x["date"]==newest]
    contracts=sorted({x["contract"] for x in group if x["contract"]>=newest[:6]})
    if not contracts:contracts=sorted({x["contract"] for x in group})
    first=contracts[0]
    taken=[x for x in group if x["contract"]==first]
    day=next((x for x in taken if x["session"]=="DAY"),None)
    night=next((x for x in taken if x["session"]=="NIGHT"),None)
    delta=round(night["close"]-day["close"],2) if day and night else None
    pct=round(delta/day["close"]*100,3) if delta is not None else None
    return {"asOfDate":newest[:4]+"-"+newest[4:6]+"-"+newest[6:8],"contract":first,
      "day":day,"night":night,"nightVsDayPoints":delta,"nightVsDayPct":pct,
      "quality":"paired-day-night" if day and night else "single-session",
      "source":"TAIFEX 官方 DailyMarketReportFut 盤後報表",
      "sourceUrl":ENDPOINT,"timestampNature":"盤後統計；非即時報價",
      "displayNote":"僅在同一交易日、同一月份契約的日夜盤均可取得時，計算夜盤相對日盤漲跌。"}
def main():
    r=requests.get(ENDPOINT,headers=UA,timeout=45)
    r.raise_for_status()
    try:raw=r.json()
    except Exception as exc:raise RuntimeError("Non-JSON TAIFEX response") from exc
    if isinstance(raw,dict):raw=raw.get("data") or raw.get("Data") or raw.get("rows") or raw
    output=parse(raw)
    now=datetime.now(ZoneInfo("Asia/Taipei"))
    d=output["asOfDate"]
    if d>now.date().isoformat():raise RuntimeError("TAIFEX report date unexpectedly in future "+d)
    if OUT.exists():
        prior=json.loads(OUT.read_text(encoding="utf-8"))
        if prior.get("asOfDate","")>d:raise RuntimeError("Would overwrite newer futures quote with stale report")
        if prior.get("asOfDate")==d and prior.get("quality")=="paired-day-night" and output["quality"]!="paired-day-night":
            print(json.dumps({"status":"skip-incomplete-replacement","last":d},ensure_ascii=False));return
    output["fetchedAt"]=now.isoformat(timespec="seconds")
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(output,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({"status":"success","date":d,"contract":output["contract"],"quality":output["quality"],
      "day":output["day"] and output["day"]["close"],"night":output["night"] and output["night"]["close"],
      "nightVsDayPct":output["nightVsDayPct"]},ensure_ascii=False))
if __name__=="__main__":main()
