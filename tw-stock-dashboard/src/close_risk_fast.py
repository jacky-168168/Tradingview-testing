"""獨立盤後大盤 Risk Score 更新，不等待全市場近兩千檔股票選股計算。
僅使用與正式風控相同的 risk.build()，且先核對當日 TWSE 指數、漲跌家數、外資資料。
對 F/F2/G、正式 daily/latest.json 不做任何修改。資料不足時 fail closed。
"""
from __future__ import annotations
import json
import math
import re
import sys
from datetime import datetime, timedelta, time
from pathlib import Path
from zoneinfo import ZoneInfo

from config import BENCHMARK, DATA_DIR, RISK_ON, RISK_STRONG, RISK_OFF
from risk import _report, build as build_risk
from yahoo_cache import update_symbol

TZ = ZoneInfo("Asia/Taipei")
TARGET = DATA_DIR / "market_risk_close" / "latest.json"
QUALITY = "official-twse-close-risk-v1"

def parse_twse_day(raw):
    text = str(raw or "").strip()
    match = re.search(r"(?<!\d)(\d{3,4})\s*[年/-]\s*(\d{1,2})\s*[月/-]\s*(\d{1,2})(?:日)?(?!\d)", text)
    if match:
        year, month, day = map(int, match.groups())
        if year < 1911:
            year += 1911
        try:
            return datetime(year, month, day).date().isoformat()
        except ValueError:
            return None
    compact = re.search(r"(?<!\d)(20\d{2})(\d{2})(\d{2})(?!\d)", text)
    if compact:
        try:
            return datetime(*map(int, compact.groups())).date().isoformat()
        except ValueError:
            return None
    return None

def twse_verified_index_close(day):
    report = _report(day, "afterTrading/FMTQIK", {"date":day.replace("-", "")})
    if report.get("stat") != "OK":
        raise RuntimeError("TWSE FMTQIK official index source not ready")
    indices = {}
    for table in [report] + list(report.get("tables") or []):
        fields = [str(x) for x in (table.get("fields") or [])]
        cols = [i for i, label in enumerate(fields) if "發行量加權股價指數" in label]
        if not cols:
            continue
        for row in table.get("data") or []:
            if not isinstance(row, (list,tuple)) or len(row) <= cols[0]:
                continue
            report_day = parse_twse_day(row[0])
            if not report_day:
                continue
            try:
                value = float(str(row[cols[0]]).replace(",", "").strip())
            except (ValueError, TypeError):
                continue
            if math.isfinite(value) and 3000 < value < 100000:
                indices[report_day] = value
    if day not in indices:
        raise RuntimeError(f"TWSE FMTQIK index close not verified for {day}")
    return indices[day]

def compute(now=None):
    now = now or datetime.now(TZ)
    local = now.astimezone(TZ)
    if local.weekday() >= 5 or local.time() < time(17,30):
        print("OFFICIAL_CLOSE_OUT_OF_WINDOW", local.isoformat(), flush=True)
        return None
    day = local.date().isoformat()
    # 如 BFI82U 日期或內容不合格，risk.build() 將直接拒絕資料，不使用舊外資資料。
    official_close = twse_verified_index_close(day)
    end = datetime(local.year,local.month,local.day,local.hour,local.minute)
    start = end - timedelta(days=370)
    _, index, error = update_symbol(BENCHMARK, start, end)
    if error or index is None or len(index) < 120:
        raise RuntimeError("BENCHMARK_HISTORY_NOT_READY: "+str(error))
    index = index.sort_values("date").drop_duplicates("date",keep="last")
    index_day = str(index.iloc[-1].date)
    if index_day != day:
        raise RuntimeError("BENCHMARK_YAHOO_DATE_STALE: latest "+index_day+" expected "+day)
    yahoo_close = float(index.iloc[-1].close)
    if not math.isfinite(yahoo_close) or abs(yahoo_close / official_close - 1) > 0.002:
        raise RuntimeError(f"BENCHMARK_OFFICIAL_CLOSE_MISMATCH: TWSE {official_close}, Yahoo {yahoo_close}")
    risk = build_risk(index, RISK_ON, RISK_STRONG, RISK_OFF)
    if risk.get("date") != day or not isinstance(risk.get("score"),int) or not 0 <= risk["score"] <= 100:
        raise RuntimeError("INVALID_DATED_RISK_SCORE")
    result = {
        "quality":QUALITY,
        "asOfDate":day,
        "publishedAt":local.isoformat(timespec="seconds"),
        "risk":risk,
        "source": {
            "index":"TWSE FMTQIK verified with Yahoo ^TWII daily OHLC",
            "stockBreadth":"TWSE MI_INDEX 股票漲跌家數（排除 ETF／權證）",
            "foreign":"TWSE BFI82U 外資及陸資當日買賣超",
            "formula":"tw-stock-dashboard/src/risk.py build()，與正式 Risk Score 同一公式",
            "officialIndexClose":round(official_close,2),
            "observedIndexClose":round(yahoo_close,2)
        },
        "scope":"獨立首頁大盤 Risk Score；不覆寫正式選股／F/F2/G 門檻",
    }
    return result

def main():
    payload=compute()
    if payload is None:
        return
    TARGET.parent.mkdir(parents=True,exist_ok=True)
    temp = TARGET.with_name("latest.json.tmp")
    text = json.dumps(payload,ensure_ascii=False,indent=2,allow_nan=False)+"\n"
    temp.write_text(text,encoding="utf-8")
    temp.replace(TARGET)
    risk=payload["risk"]
    print("OFFICIAL_CLOSE_RISK_PUBLISHED",payload["asOfDate"],"score",risk["score"],
          "breadth",risk["breadth"],"foreign",risk["foreign"],"index",risk["index"],flush=True)

if __name__=="__main__":
    try:
        main()
    except Exception as exc:
        print("OFFICIAL_CLOSE_RISK_FAILED",type(exc).__name__,str(exc)[:800],file=sys.stderr,flush=True)
        sys.exit(1)
