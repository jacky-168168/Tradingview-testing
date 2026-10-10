"""TAIFEX TX close: day D vs the AFTER-HOURS session that STARTS on D.
TAIFEX groups a session starting on D at 15:00 under the NEXT official
trading date in its dated reports (e.g. 2026-10-08 night -> 2026-10-12).
OpenAPI's same Date DAY+NIGHT rows are NOT the paired trading sessions.
Never compare TX to cash ^TWII or different TX contract months.
All displayed night quotes are completed exchange reports, not live prices.
"""
from __future__ import annotations
import json,re
from datetime import datetime,timedelta,date
from zoneinfo import ZoneInfo
from pathlib import Path
import requests
from bs4 import BeautifulSoup
from config import DATA_DIR
ENDPOINT="https://openapi.taifex.com.tw/v1/DailyMarketReportFut"
REPORT="https://www.taifex.com.tw/cht/3/futDailyMarketReport"
OUT=DATA_DIR/"futures"/"latest.json"
UA={"User-Agent":"Mozilla/5.0 TW Stock Dashboard GitHub Public Research","Accept":"text/html,application/json"}
def num(v):
    if v is None:return None
    try:return float(re.sub(r"[^0-9.+-]","",str(v)))
    except (ValueError,TypeError):return None
def day_from_openapi(raw):
    if isinstance(raw,dict):raw=raw.get("data") or raw.get("Data") or raw.get("rows") or []
    if not isinstance(raw,list):raise RuntimeError("TAIFEX OpenAPI day rows missing")
    rows=[]
    for x in raw:
        if str(x.get("Contract") or "").strip()!="TX":continue
        if str(x.get("TradingSession") or "").strip() not in ("一般","一般交易","一般交易時段"):continue
        d=str(x.get("Date") or "").replace("/","").strip()
        contract=str(x.get("ContractMonth(Week)") or "").strip()
        last=num(x.get("Last"));vol=num(x.get("Volume"))
        if re.fullmatch(r"20\d{6}",d) and re.fullmatch(r"20\d{4}",contract) and last and vol and vol>0:
            rows.append({"date":d,"contract":contract,"session":"DAY","close":last,"volume":int(vol),
                "open":num(x.get("Open")),"high":num(x.get("High")),"low":num(x.get("Low"))})
    if not rows:raise RuntimeError("No completed TX day-session rows")
    latest=max(x["date"] for x in rows)
    all_today=[x for x in rows if x["date"]==latest]
    eligible=sorted(x["contract"] for x in all_today if x["contract"]>=latest[:6])
    if not eligible:eligible=sorted(x["contract"] for x in all_today)
    return next(x for x in all_today if x["contract"]==eligible[0])
def night_from_html(html,expected_session_date,expected_contract,query_report_date):
    soup=BeautifulSoup(html,"html.parser")
    page=" ".join(soup.stripped_strings)
    # The exchange prints the actual AFTER-HOURS session date, which is NOT
    # necessarily the report's queryDate (following official trading day).
    dates=set()
    for y,m,d in re.findall(r"(20\d{2})\s*[/.-]\s*(\d{1,2})\s*[/.-]\s*(\d{1,2})\s*15\s*:\s*00",page):
        try:dates.add(date(int(y),int(m),int(d)).isoformat())
        except ValueError:pass
    if expected_session_date not in dates:return None
    table=soup.select_one("table.table_f")
    if table is None:return None
    for tr in table.select("tr"):
        c=[x.get_text(" ",strip=True) for x in tr.select("td")]
        if len(c)<9 or c[0]!="TX" or c[1]!=expected_contract:continue
        last=num(c[5]);vol=num(c[8])
        if not last or not vol or vol<=0:return None
        official_change=num(c[6]);official_pct=num(c[7])
        # The exchange's ▼-652 is relative to its exchange settlement/reference,
        # not directly to the TX day Last=49349. Show BOTH with separate labels.
        return {"date":expected_session_date.replace("-",""),"contract":expected_contract,"session":"NIGHT",
            "close":last,"volume":int(vol),"open":num(c[2]),"high":num(c[3]),"low":num(c[4]),
            "officialChangePoints":official_change,"officialChangePct":official_pct,
            "officialReference":round(last-official_change,2) if official_change is not None else None,
            "reportQueryDate":query_report_date}
    return None
def official_night(day,now):
    session=day["date"][:4]+"-"+day["date"][4:6]+"-"+day["date"][6:8]
    session_date=date.fromisoformat(session)
    # A holiday/weekend night is filed under NEXT trading day, possibly
    # several calendar days later. Never pair two OpenAPI rows by Date!
    for offset in range(1,12):
        report_date=(session_date+timedelta(days=offset)).isoformat()
        params={"queryType":"2","marketCode":"1","MarketCode":"1","dateaddcnt":"",
            "commodity_id":"TX","commodity_idt":"TX","commodity_id2":"",
            "queryDate":report_date.replace("-","/")}
        try:
            r=requests.get(REPORT,params=params,headers=UA,timeout=25)
            r.raise_for_status()
            result=night_from_html(r.text,session,day["contract"],report_date)
            if result:return result
        except (requests.RequestException,ValueError) as exc:
            print("TAIFEX nightly query failed",report_date,type(exc).__name__,str(exc)[:150])
    return None
def build(day,night,now):
    d=day["date"]
    out={"asOfDate":d[:4]+"-"+d[4:6]+"-"+d[6:8],"contract":day["contract"],"day":day,"night":night,
        "nightVsDayPoints":None,"nightVsDayPct":None,"quality":"day-only",
        "source":"TAIFEX OpenAPI day + official dated afterhours web report",
        "sourceUrl":REPORT,"timestampNature":"已完成交易時段；非即時報價",
        "displayNote":"日夜盤均為TX同一到期月份；夜盤報表歸屬下一官方交易日，依盤後時段實際起始日期配對。",
        "fetchedAt":now.isoformat(timespec="seconds")}
    if night:
        if night["contract"]!=day["contract"] or night["date"]!=day["date"]:
            raise RuntimeError("Mixed TX session dates or contract months")
        points=round(night["close"]-day["close"],2)
        out.update({"nightVsDayPoints":points,"nightVsDayPct":round(points/day["close"]*100,3),
            "quality":"paired-day-night","officialNightChangePoints":night.get("officialChangePoints"),
            "officialNightChangePct":night.get("officialChangePct"),
            "officialNightReference":night.get("officialReference")})
    return out
def main():
    now=datetime.now(ZoneInfo("Asia/Taipei"))
    r=requests.get(ENDPOINT,headers=UA,timeout=40);r.raise_for_status()
    day=day_from_openapi(r.json())
    if date.fromisoformat(day["date"][:4]+"-"+day["date"][4:6]+"-"+day["date"][6:8])>now.date():
        raise RuntimeError("Future TX day session date")
    night=official_night(day,now)
    output=build(day,night,now)
    if OUT.exists():
        prev=json.loads(OUT.read_text(encoding="utf-8"))
        if prev.get("asOfDate","")>output["asOfDate"]:raise RuntimeError("New data older than previously published")
        if prev.get("asOfDate")==output["asOfDate"] and prev.get("quality")=="paired-day-night" and not night:
            raise RuntimeError("Do not replace a paired night with incomplete session data")
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(output,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({"date":output["asOfDate"],"contract":output["contract"],"day":day["close"],
        "night":night and night["close"],"overnightVsDay":output["nightVsDayPoints"],
        "officialNightChange":output.get("officialNightChangePoints"),
        "quality":output["quality"]},ensure_ascii=False))
if __name__=="__main__":main()
