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
        nums = [float(row[k]) for k in ("listed", "otc", "overall") if row.get(k) is not None]
        ix = float(row["indexClose"])
        return bool(nums) and all(math.isfinite(v) and 75 < v < 400 for v in nums) and math.isfinite(ix) and 3000 < ix < 100000
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
    from retail_twse_fallback import main as compute_twse
    from retail_tpex import main as compute_tpex
    # TWSE 為錨點，且與加權指數收盤必須為相同交易日。
    listed = compute_twse()
    day = listed["date"]
    row = {**listed, "otc":None, "overall":None,
           "provenanceByScope":{"listed":"TWSE 原始資料自行計算"}}
    try:
        otc = compute_tpex(expected_day=day)
        row.update(otc)
        loan_total = listed["listedLoanTwd"] + otc["otcLoanTwd"]
        collateral_total = listed["listedCollateralTwd"] + otc["otcCollateralTwd"]
        if loan_total <= 0:
            raise RuntimeError("上市櫃合併融資金額無效")
        total_ratio = round(collateral_total / loan_total * 100, 2)
        if not 95 < total_ratio < 350:
            raise RuntimeError("上市櫃整體維持率異常")
        row["overall"] = total_ratio
        row["provenanceByScope"] = {
            "listed":"TWSE 原始資料自行計算",
            "otc":"TPEx 原始資料自行計算",
            "overall":"TWSE + TPEx 融資金額加權計算"}
        print("ALL_MARKET_DERIVED",day,"listed",row["listed"],"otc",row["otc"],
              "overall",total_ratio,"loanTwd",loan_total,flush=True)
    except Exception as exc:
        # OTC 源不可用時可保留已公開的上市數據，但不可用上市值代替整體值。
        row["otcError"] = str(exc)[:260]
        print("TPEx_UPDATE_FAILED",repr(exc),"; 不捏造上櫃／整體維持率",flush=True)
    incoming = [row]
    if old and day < max(old):
        raise RuntimeError(f"官方來源資料日期倒退：{day}，現有 {max(old)}；拒絕覆寫")
    candles = get_candles()
    for row in incoming:
        day = row["date"]
        old_record = old.get(day, {})
        if old_record:
            # 同日期仍保留來源相符的歷史 OHLC；缺失的 OTC 不能冒稱為新一日官方計算。
            row = {**old_record, **{k:v for k,v in row.items() if v is not None}}
            if row.get("otcError"):
                row["provenanceByScope"] = {
                    "listed":"TWSE 原始資料自行計算",
                    "otc":"既有歷史資料（本輪 TPEx 無法驗證）" if old_record.get("otc") is not None else "未確認",
                    "overall":"既有歷史資料（本輪 TPEx 無法驗證）" if old_record.get("overall") is not None else "未確認"}
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
            "name":"TWSE 上市與 TPEx 上櫃原始資料；上市櫃整體以融資金額加權計算",
            "url":SOURCE,
            "method":"各市場融資股票市值／融資金額餘額；非券商個別整戶維持率",
            "classification":"盤後公開資料自行計算；每筆 provenanceByScope 標示來源",
            "listedSource":"https://www.twse.com.tw/exchangeReport/MI_MARGN?selectType=MS",
            "otcSource":"https://www.tpex.org.tw/web/stock/margin_trading/margin_balance/margin_bal_result.php?l=zh-tw&o=htm",
            "tpexOpenApi":"https://www.tpex.org.tw/openapi/",
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
          "trueOhlc",sum("indexOpen" in x for x in rows),"sources","TWSE+TPEx")
if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("RET_SURVIVAL_SOURCE_FAILED:",str(e),file=sys.stderr)
        sys.exit(1)
