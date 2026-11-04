#!/usr/bin/env python3
"""Official TAIFEX Taiwan VIX daily closes; never infer intraday or trade signals."""
from __future__ import annotations

import json
import math
import os
import re
from datetime import datetime, timedelta
from pathlib import Path
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "docs/data/research/tw_vix/latest.json"
SOURCE = "https://www.taifex.com.tw/cht/7/vixDaily3MNew"
FILE_ROOT = "https://www.taifex.com.tw/file/taifex/Dailydownload/vix/log2data/"
TZ = ZoneInfo("Asia/Taipei")
VERSION = "TW_VIX_TAIFEX_DAILY_V1"
MAX_BYTES = 100_000


def month_keys(today):
    first = today.year*12+today.month-1
    return [f"{(first-i)//12:04d}{(first-i)%12+1:02d}" for i in range(4)]


def parse_month(raw: bytes, expected_month: str, now: datetime) -> list[dict]:
    # Official public TXT is Big5-encoded, with numeric ASCII rows:
    # YYYYMMDD <tab> 13450000 <tab> VIX <tab> previous-minute average.
    text = raw.decode("big5",errors="replace")
    result=[]
    today = now.astimezone(TZ).date()
    for line in text.splitlines():
        t=line.strip()
        if not re.match(r"^20\d{6}\b",t):
            continue
        cols=t.split()
        if len(cols)!=4 or not re.fullmatch(r"20\d{6}",cols[0]) or not re.fullmatch(r"\d{8}",cols[1]):
            raise ValueError("期交所 VIX 日期／欄位格式異常，拒絕資料")
        date=datetime.strptime(cols[0],"%Y%m%d").date()
        if cols[0][:6]!=expected_month or date>today:
            raise ValueError("期交所官方 VIX 資料日期不符或在未來")
        if cols[1] not in ("13450000","13440000"):
            raise ValueError("期交所官方 VIX 欄位不是正常收盤時間")
        try:
            value=float(cols[2]);avg=float(cols[3])
        except ValueError as e:
            raise ValueError("期交所 VIX 值無法解析") from e
        if not (math.isfinite(value) and math.isfinite(avg) and 5<=value<=150 and 5<=avg<=150 and abs(value-avg)<10):
            raise ValueError("期交所 VIX 指數或一分鐘平均值異常")
        result.append({"date":date.isoformat(),"time":cols[1][:2]+":"+cols[1][2:4],
                       "value":round(value,2),"closeMinuteAverage":round(avg,2)})
    if not result:
        raise ValueError(f"期交所 {expected_month} 未取得有效每日收盤資料")
    dates=[r["date"] for r in result]
    if len(dates)!=len(set(dates)):
        raise ValueError("期交所 VIX 重複交易日期")
    return sorted(result,key=lambda x:x["date"])


def daily_rows(months: list[list[dict]]) -> list[dict]:
    by_date={}
    for month in months:
        for row in month:
            if row["date"] in by_date and by_date[row["date"]] != row:
                raise ValueError("期交所 VIX 跨檔同一日期數值不符")
            by_date[row["date"]]=dict(row)
    ordered=[by_date[d] for d in sorted(by_date)][-260:]
    for i,r in enumerate(ordered):
        if i==0:
            r["change"]=None
            r["changePct"]=None
        else:
            prev=ordered[i-1]["value"]
            r["change"]=round(r["value"]-prev,2)
            r["changePct"]=round((r["value"]/prev-1)*100,2)
    return ordered


def validate(payload):
    if payload.get("version")!=VERSION or payload.get("sourceUrl")!=SOURCE:
        raise ValueError("台股 VIX 正式來源或版本錯誤")
    rows=payload.get("rows")
    if not isinstance(rows,list) or len(rows)<2:
        raise ValueError("台股 VIX 至少需要兩筆已核對官方收盤資料")
    last=""
    for i,r in enumerate(rows):
        day=r.get("date")
        if not isinstance(day,str) or not re.fullmatch(r"20\d{2}-\d{2}-\d{2}",day) or day<=last:
            raise ValueError("期交所 VIX 交易日次序錯誤")
        if not (isinstance(r.get("value"),(int,float)) and 5<=r["value"]<=150 and
                isinstance(r.get("closeMinuteAverage"),(int,float)) and 5<=r["closeMinuteAverage"]<=150):
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


def main():
    now=datetime.now(TZ)
    monthly=[]
    for key in month_keys(now.date()):
        url=FILE_ROOT+key+"new.txt"
        request=Request(url,headers={"User-Agent":"Mozilla/5.0 (compatible; Tradingview-testing-TaiwanVIX/1.0)"})
        with urlopen(request,timeout=24) as response:
            raw=response.read(MAX_BYTES+1)
        if len(raw)>MAX_BYTES:
            raise ValueError("期交所 VIX 月資料檔過大")
        month=parse_month(raw,key,now)
        monthly.append(month)
        print("TAIFEX_VIX_MONTH",key,"days",len(month),"latest",month[-1]["date"],flush=True)
    rows=daily_rows(monthly)
    if len(rows)<20:
        raise RuntimeError("期交所 VIX 有效收盤樣本未達 20 筆，不能生成歷史統計")
    last=rows[-1]
    old={}
    if DEST.exists():
        old=json.loads(DEST.read_text("utf-8"))
    if old.get("version")==VERSION and old.get("asOfDate","")>last["date"]:
        raise ValueError("期交所來源日期倒退，拒絕以舊檔覆寫最新觀測")
    payload={"version":VERSION,"quality":"official-taifex-daily-close",
             "sourceName":"臺灣期貨交易所｜臺指選擇權波動率指數",
             "sourceUrl":SOURCE,
             "sourceFile":FILE_ROOT+last["date"][:7].replace("-","")+"new.txt",
             "method":"官方日收盤 13:45 VIX 值，另附最後1分鐘平均；非盤中即時報價",
             "updatedAt":now.isoformat(timespec="seconds"),
             "asOfDate":last["date"],
             "sourceObservationAt":last["date"]+"T"+last["time"]+":00+08:00",
             "rows":rows}
    validate(payload)
    DEST.parent.mkdir(parents=True,exist_ok=True)
    tmp=DEST.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    os.replace(tmp,DEST)
    print("TW_VIX_OFFICIAL_OK",last["date"],last["value"],"observations",len(rows),flush=True)


if __name__=="__main__":
    main()
