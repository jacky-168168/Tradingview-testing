#!/usr/bin/env python3
"""盤後更新「散戶存活率」資料：第三方估算維持率 + Yahoo TAIEX 真實 OHLC。
注意：不將融資餘額視為維持率，不把只有收盤的資料偽裝成日 K。
"""
from __future__ import annotations
import json, math, re, sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "docs/data/retail_survival/latest.json"
SOURCE = "https://www.istock.tw/post/twmarginrequirement_more"
CHART = "https://query1.finance.yahoo.com/v8/finance/chart/%5ETWII"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; TaiwanMarketDashboard/1.0)", "Accept": "text/html,application/json"}
TZ = ZoneInfo("Asia/Taipei")
DATE_RE = re.compile(r"^20\d\d-\d\d-\d\d$")

def valid(row):
    try:
        day = str(row["date"])
        datetime.strptime(day, "%Y-%m-%d")
        if not DATE_RE.fullmatch(day) or day > datetime.now(TZ).date().isoformat():
            return False
        nums = [float(row[k]) for k in ("listed", "otc", "overall", "indexClose")]
        return all(math.isfinite(v) for v in nums) and all(75 < v < 400 for v in nums[:3]) and 3000 < nums[3] < 100000
    except (KeyError, ValueError, TypeError):
        return False

def parse_source(html):
    soup = BeautifulSoup(html, "html.parser")
    rows = []
    for tr in soup.select("tr"):
        cols = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
        if len(cols) < 5 or not DATE_RE.fullmatch(cols[0].strip()):
            continue
        try:
            r = {"date": cols[0].strip(), "listed": float(cols[1].replace(",", "").replace("%","")),
                 "otc": float(cols[2].replace(",", "").replace("%","")),
                 "overall": float(cols[3].replace(",", "").replace("%","")),
                 "indexClose": float(cols[4].replace(",", ""))}
            if valid(r):
                rows.append(r)
        except ValueError:
            continue
    if len(rows) < 12:
        # 針對可能使用非表格 DOM 的頁面，僅接受完整連續五欄資料。
        text = soup.get_text(" ", strip=True)
        pattern = r"(20\d{2}-\d{2}-\d{2})\s+([\d,]+(?:\.\d+)?)\s+([\d,]+(?:\.\d+)?)\s+([\d,]+(?:\.\d+)?)\s+([\d,]+(?:\.\d+)?)"
        for m in re.finditer(pattern, text):
            try:
                day, a, b, c, d = m.groups()
                r = {"date":day,"listed":float(a.replace(",","")),"otc":float(b.replace(",","")),
                     "overall":float(c.replace(",","")),"indexClose":float(d.replace(",",""))}
                if valid(r):
                    rows.append(r)
            except ValueError:
                continue
    unique = {r["date"]:r for r in rows}
    out = sorted(unique.values(), key=lambda r: r["date"])
    if len(out) < 12:
        raise RuntimeError(f"資料來源格式變更或不足：可解析 {len(out)} 筆，拒絕發布")
    return out

def get_candles():
    try:
        response = requests.get(CHART, params={"range":"1y","interval":"1d"}, headers=HEADERS, timeout=25)
        response.raise_for_status()
        result = (response.json().get("chart", {}).get("result") or [None])[0]
        if not result:
            raise ValueError("Yahoo 指數 OHLC 無資料")
        quote = result["indicators"]["quote"][0]
        candles = {}
        for i, timestamp in enumerate(result.get("timestamp") or []):
            try:
                vals = [float(quote[k][i]) for k in ("open","high","low","close")]
                if not all(math.isfinite(v) for v in vals) or min(vals) <= 0:
                    continue
                op, hi, lo, close = vals
                if not (lo <= min(op,close) <= max(op,close) <= hi):
                    continue
                day = datetime.fromtimestamp(timestamp, TZ).date().isoformat()
                candles[day] = {"indexOpen":round(op,2),"indexHigh":round(hi,2),
                                "indexLow":round(lo,2),"indexOhlcClose":round(close,2)}
            except (TypeError, ValueError, IndexError, KeyError):
                continue
        return candles
    except Exception as exc:
        print("OHLC 備用模式：真實 K 線暫無法同步，僅顯示收盤線：", repr(exc))
        return {}

def main():
    existing = {}
    if TARGET.exists():
        try:
            existing = json.loads(TARGET.read_text("utf-8"))
        except (OSError, ValueError):
            pass
    old = {r["date"]:r for r in existing.get("rows", []) if isinstance(r, dict) and valid(r)}
    r = requests.get(SOURCE, headers=HEADERS, timeout=35)
    r.raise_for_status()
    incoming = parse_source(r.text)
    if old and incoming[-1]["date"] < max(old):
        raise RuntimeError(f"來源資料倒退：來源 {incoming[-1]['date']}，現有 {max(old)}；拒絕覆寫")
    candles = get_candles()
    for row in incoming:
        day = row["date"]
        old_record = old.get(day, {})
        # 同一天比對公開來源與 Yahoo 收盤，不吻合時不接入 K 棒。
        candle = candles.get(day)
        if candle and abs(candle["indexOhlcClose"] / row["indexClose"] - 1) <= 0.015:
            row.update(candle)
        elif all(k in old_record for k in ("indexOpen","indexHigh","indexLow","indexOhlcClose")):
            row.update({k:old_record[k] for k in ("indexOpen","indexHigh","indexLow","indexOhlcClose")})
        old[day] = row
    # 補齊尚未收錄的舊資料 OHLC，不能取代融資維持率。
    for day, row in old.items():
        candle = candles.get(day)
        if candle and "indexOpen" not in row and abs(candle["indexOhlcClose"]/row["indexClose"]-1)<=.015:
            row.update(candle)
    rows = [old[d] for d in sorted(old)[-260:]]
    payload = {
        "schema":"retail-survival-v1",
        "source":{
            "name":"愛玩股大盤融資維持率歷史資料（依TWSE與TPEx公開資料估算）",
            "url":SOURCE,
            "method":"各市場融資股票市值／融資金額餘額；非券商個別整戶維持率",
            "classification":"第三方估算、盤後",
            "indexOhlcSource":"Yahoo Finance ^TWII，與資料源指數收盤核對後採用"
        },
        "asOf":rows[-1]["date"],
        "updatedAt":datetime.now(timezone.utc).isoformat(),
        "rows":rows
    }
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    new = json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False)+"\n"
    temp = TARGET.with_suffix(".json.tmp")
    temp.write_text(new, encoding="utf-8")
    temp.replace(TARGET)
    print("RET_SURVIVAL_OK",payload["asOf"],"records",len(rows),
          "trueOhlc",sum("indexOpen" in x for x in rows),"source",SOURCE)
if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("RET_SURVIVAL_SOURCE_FAILED:",str(e),file=sys.stderr)
        sys.exit(1)
