#!/usr/bin/env python3
"""Collect official TAIFEX Taiwan VIX closes; never invent intraday or trade signals.

Backfill: public TAIFEX index portal, which supports up to three years.
Cross-check: four published official monthly daily-close TXT files.
"""
from __future__ import annotations

import json
import math
import os
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[1]
DEST=ROOT/"docs/data/research/tw_vix/latest.json"
SOURCE="https://www.taifex.com.tw/cht/7/vixDaily3MNew"
HISTORY_PAGE="https://www.taifex.com.tw/indes/index.aspx"
HISTORY_API=HISTORY_PAGE+"/GetStockDayPrices"
FILE_ROOT="https://www.taifex.com.tw/file/taifex/Dailydownload/vix/log2data/"
TZ=ZoneInfo("Asia/Taipei")
VERSION="TW_VIX_TAIFEX_DAILY_V1"
MAX_BYTES=1_500_000

def month_keys(today: date, count: int = 4) -> list[str]:
    """Recent published monthly TXT files only; older files are not retained."""
    first=today.year*12+today.month-1
    return [f"{(first-i)//12:04d}{(first-i)%12+1:02d}" for i in range(count)]

def parse_month(raw: bytes, expected_month: str, now: datetime) -> list[dict]:
    text=raw.decode("big5",errors="replace")
    result=[]
    today=now.astimezone(TZ).date()
    for line in text.splitlines():
        t=line.strip()
        if not re.match(r"^20\d{6}\b",t):continue
        cols=t.split()
        if len(cols)!=4 or not re.fullmatch(r"20\d{6}",cols[0]) or not re.fullmatch(r"\d{8}",cols[1]):
            raise ValueError("期交所 VIX 日期／欄位格式異常，拒絕資料")
        day=datetime.strptime(cols[0],"%Y%m%d").date()
        if cols[0][:6]!=expected_month or day>today:
            raise ValueError("期交所官方 VIX 資料日期不符或在未來")
        if cols[1] not in ("13450000","13440000"):
            raise ValueError("期交所官方 VIX 欄位不是正常收盤時間")
        try:value=float(cols[2]);avg=float(cols[3])
        except ValueError as e:raise ValueError("期交所 VIX 值無法解析") from e
        if not (math.isfinite(value) and math.isfinite(avg) and 5<=value<=150 and 5<=avg<=150 and abs(value-avg)<10):
            raise ValueError("期交所 VIX 指數或一分鐘平均值異常")
        result.append({"date":day.isoformat(),"time":cols[1][:2]+":"+cols[1][2:4],
                       "value":round(value,2),"closeMinuteAverage":round(avg,2)})
    if not result:raise ValueError(f"期交所 {expected_month} 未取得有效每日收盤資料")
    dates=[r["date"] for r in result]
    if len(dates)!=len(set(dates)):raise ValueError("期交所 VIX 重複交易日期")
    return sorted(result,key=lambda x:x["date"])

def parse_portal(raw: bytes, now: datetime) -> list[dict]:
    """Validate official index portal Time/Price data (NOT synthetic closes)."""
    try:
        obj=json.loads(raw.decode("utf-8-sig"))
        dataset=json.loads(obj["d"])
        trend=dataset["TrendData"]
    except (TypeError,ValueError,KeyError) as exc:
        raise ValueError("期交所指數專區歷史資料格式不符") from exc
    if not isinstance(trend,list) or len(trend)<360 or len(trend)>1100:
        raise ValueError(f"期交所指數專區可用樣本不足 360 筆或異常：{len(trend) if isinstance(trend,list) else 'N/A'}")
    rows=[];last="";today=now.astimezone(TZ).date()
    for item in trend:
        key=str(item.get("Time",""))
        if not re.fullmatch(r"20\d{6}",key):raise ValueError("期交所指數專區交易日期格式錯誤")
        day=datetime.strptime(key,"%Y%m%d").date()
        iso=day.isoformat()
        if iso<=last or day>today or day.weekday()>=5:
            raise ValueError("期交所指數專區交易日不遞增／未來日或非交易日")
        try:value=float(item["Price"])
        except (TypeError,ValueError,KeyError) as exc:
            raise ValueError("期交所指數專區 VIX 值遺失") from exc
        if not math.isfinite(value) or not 5<=value<=150:
            raise ValueError("期交所指數專區 VIX 值超出合理範圍")
        rows.append({"date":iso,"time":"13:45","value":round(value,2),
                     "closeMinuteAverage":None})
        last=iso
    return rows

def reconcile_portal_to_months(portal: list[dict],months: list[list[dict]]) -> list[dict]:
    """Verify every recent official monthly close matches the longer public chart."""
    by_date={r["date"]:dict(r) for r in portal}
    verified=0
    for group in months:
        for row in group:
            other=by_date.get(row["date"])
            if not other:
                raise ValueError(f"期交所指數專區缺少已公布之月檔交易日：{row['date']}")
            if not math.isclose(other["value"],row["value"],abs_tol=.011):
                raise ValueError(f"期交所指數專區／官方日收盤數值不符：{row['date']} "+str(other["value"])+" vs "+str(row["value"]))
            other["closeMinuteAverage"]=row["closeMinuteAverage"]
            other["time"]=row["time"]
            verified+=1
    if verified<40:
        raise ValueError(f"近月官方日收盤交叉驗證樣本不足：{verified}")
    last_monthly=max(row["date"] for group in months for row in group)
    # If the chart includes a newer session not yet in the published official
    # monthly file, do not publish that unverified same-day point.
    verified_rows=[row for row in portal if row["date"]<=last_monthly]
    for row in verified_rows:
        if row["date"] in by_date:row.update(by_date[row["date"]])
    if len(verified_rows)<360:
        raise ValueError(f"核對正式收盤後未達 360 個交易日：{len(verified_rows)}")
    return verified_rows

def daily_rows(months: list[list[dict]]) -> list[dict]:
    by_date={}
    for month in months:
        for row in month:
            if row["date"] in by_date and by_date[row["date"]]!=row:
                raise ValueError("期交所 VIX 跨檔同一日期數值不符")
            by_date[row["date"]]=dict(row)
    ordered=[by_date[d] for d in sorted(by_date)][-400:]
    for i,r in enumerate(ordered):
        if not i:r["change"]=None;r["changePct"]=None
        else:
            prev=ordered[i-1]["value"]
            r["change"]=round(r["value"]-prev,2)
            r["changePct"]=round((r["value"]/prev-1)*100,2)
    return ordered

def validate(payload):
    if payload.get("version")!=VERSION or payload.get("sourceUrl")!=SOURCE:
        raise ValueError("台股 VIX 正式來源或版本錯誤")
    rows=payload.get("rows")
    if not isinstance(rows,list) or len(rows)<2 or len(rows)>400:
        raise ValueError("台股 VIX 样本筆數不合理")
    last=""
    for i,r in enumerate(rows):
        day=r.get("date")
        if not isinstance(day,str) or not re.fullmatch(r"20\d{2}-\d{2}-\d{2}",day) or day<=last:
            raise ValueError("期交所 VIX 交易日次序錯誤")
        avg=r.get("closeMinuteAverage")
        if not (isinstance(r.get("value"),(int,float)) and 5<=r["value"]<=150 and
                (avg is None or isinstance(avg,(int,float)) and 5<=avg<=150 and abs(avg-r["value"])<=10)):
            raise ValueError("期交所 VIX 收盤值缺漏")
        if i:
            prev=rows[i-1]["value"]
            if not (math.isclose(r["change"],round(r["value"]-prev,2),abs_tol=.011) and
                    math.isclose(r["changePct"],round((r["value"]/prev-1)*100,2),abs_tol=.011)):
                raise ValueError("期交所 VIX 當日漲跌與相鄰官方收盤值不符")
        last=day
    if payload.get("asOfDate")!=last or not str(payload.get("sourceObservationAt") or "").startswith(last+"T"):
        raise ValueError("期交所 VIX 最新資料日不一致")
    return rows

def fetch_history(now):
    start=(now.date()-timedelta(days=700)).strftime("%Y/%m/%d")
    end=now.date().strftime("%Y/%m/%d")
    args=json.dumps({"syid":"TAIWANVIX","flag":"MS","startDate":start,"endDate":end}).encode("utf-8")
    req=Request(HISTORY_API,data=args,method="POST",headers={
        "User-Agent":"Mozilla/5.0 (compatible; Tradingview-testing-TaiwanVIX/1.0)",
        "Content-Type":"application/json; charset=utf-8","Accept":"application/json",
        "Referer":HISTORY_PAGE})
    with urlopen(req,timeout=35) as response:raw=response.read(MAX_BYTES+1)
    if len(raw)>MAX_BYTES:raise ValueError("期交所指數專區資料檔超出限制")
    return parse_portal(raw,now)

def main():
    now=datetime.now(TZ)
    portal=fetch_history(now)
    print("TAIFEX_VIX_PORTAL",len(portal),"from",portal[0]["date"],"to",portal[-1]["date"],flush=True)
    def fetch_month(key):
        url=FILE_ROOT+key+"new.txt"
        req=Request(url,headers={"User-Agent":"Mozilla/5.0 (compatible; Tradingview-testing-TaiwanVIX/1.0)"})
        with urlopen(req,timeout=24) as response:raw=response.read(100001)
        if len(raw)>100000:raise ValueError("期交所 VIX 月資料檔過大："+key)
        return key,parse_month(raw,key,now)
    with ThreadPoolExecutor(max_workers=4) as executor:
        batches=list(executor.map(fetch_month,month_keys(now.date())))
    for key,month in batches:
        print("TAIFEX_VIX_MONTH",key,"days",len(month),"latest",month[-1]["date"],flush=True)
    joined=reconcile_portal_to_months(portal,[v for _,v in batches])
    rows=daily_rows([joined])
    if len(rows)<360:raise RuntimeError("期交所 VIX 沒有足夠的 360 筆已驗證交易日")
    last=rows[-1]
    if last["closeMinuteAverage"] is None:
        raise ValueError("最新期交所官方收盤未經月檔交叉核對")
    old={}
    if DEST.exists():old=json.loads(DEST.read_text("utf-8"))
    if old.get("version")==VERSION and old.get("asOfDate","")>last["date"]:
        raise ValueError("期交所來源日期倒退，拒絕以舊檔覆寫最新觀測")
    payload={"version":VERSION,"quality":"official-taifex-daily-close",
             "sourceName":"臺灣期貨交易所｜指數專區長期日線與近月正式收盤",
             "sourceUrl":SOURCE,"historySourceUrl":HISTORY_PAGE,
             "sourceFile":FILE_ROOT+last["date"][:7].replace("-","")+"new.txt",
             "method":"期交所公開指數專區三年收盤歷史，與近月日收盤官方檔逐日交叉核對；非盤中即時報價",
             "updatedAt":now.isoformat(timespec="seconds"),
             "asOfDate":last["date"],
             "sourceObservationAt":last["date"]+"T"+last["time"]+":00+08:00",
             "rows":rows}
    validate(payload)
    DEST.parent.mkdir(parents=True,exist_ok=True)
    tmp=DEST.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    os.replace(tmp,DEST)
    print("TW_VIX_OFFICIAL_360_OK",last["date"],last["value"],"days",len(rows),flush=True)

if __name__=="__main__":
    main()
