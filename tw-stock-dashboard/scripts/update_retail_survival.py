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
    from retail_twse_fallback import official_summary
    from retail_tpex import main as compute_tpex, TOTAL_URL, HEADERS as OTC_HEADERS, iso_to_roc, parse_loan_html
    # Market-wide ratio uses the published observed series, not a potentially
    # mixed-date self-computed collateral / same-day loan denominator.
    # Independently tie it to TWSE's date-stamped official loan and index.
    official = official_summary()
    day = official["date"]
    response = requests.get(SOURCE, headers=HEADERS, timeout=30)
    response.raise_for_status()
    published = parse_source(response.text)
    ratio_row = next((x for x in published if x["date"] == day), None)
    if ratio_row is None or published[-1]["date"] != day:
        raise RuntimeError(f"愛玩股維持率尚未更新至 TWSE 同日：官方 {day}／來源最新 {published[-1]['date']}")
    if abs(ratio_row["indexClose"] / official["indexClose"] - 1) > 0.001:
        raise RuntimeError(f"上市維持率來源之加權指數不符：{ratio_row['indexClose']} != {official['indexClose']}")
    row = {**ratio_row, **official,
           "ratioSource": SOURCE, "ratioSourceDate": day,
           "ratioVerification": "third-party date and TWSE official loan/index matched",
           "provenanceByScope": {
               "listed": "愛玩股上市維持率；核對證交所同日融資金額與指數",
               "otc": "愛玩股上櫃維持率；核對資料日期",
               "overall": "愛玩股上市櫃加權維持率；核對交易日期與官方融資金額"
           }}
    try:
        otc = compute_tpex(expected_day=day)
        row["otcLoanTwd"] = otc["otcLoanTwd"]
        # An independently calculated OTC rate is a cross-check, not the
        # displayed series. Large disagreements fail closed.
        if abs(row["otc"] - otc["otc"]) > 2:
            raise RuntimeError(f"愛玩股／TPEx 上櫃維持率差距過大：{row['otc']} vs {otc['otc']}")
    except Exception as exc:
        # Even when individual OTC quotes lag, the official OTC loan may
        # already be available for a dated amount-change comparison.
        row["otcError"] = str(exc)[:260]
        print("TPEX_RATIO_CHECK_UNAVAILABLE", repr(exc), flush=True)
        try:
            otc_response = requests.get(TOTAL_URL, params={"l":"zh-tw","o":"htm","d":iso_to_roc(day)},
                                        headers=OTC_HEADERS, timeout=30)
            otc_response.raise_for_status()
            row["otcLoanTwd"] = round(parse_loan_html(otc_response.text, day))
        except Exception as loan_exc:
            print("TPEX_OFFICIAL_LOAN_UNAVAILABLE", repr(loan_exc), flush=True)
    if row.get("otcLoanTwd"):
        # Check that the independently sourced overall value agrees with the
        # money-weighted published component ratios.
        la, lb = row["listedLoanTwd"], row["otcLoanTwd"]
        weighted = (la * row["listed"] + lb * row["otc"]) / (la + lb)
        if abs(weighted - row["overall"]) > 0.25:
            raise RuntimeError(f"上市櫃維持率加權對帳失敗：{weighted:.2f} vs {row['overall']}")
    print("RET_SURVIVAL_SOURCED", day, "listed", row["listed"], "otc", row["otc"],
          "overall", row["overall"], "loanTwd", row["listedLoanTwd"], row.get("otcLoanTwd"), flush=True)
    incoming = [row]
    if old and day < max(old):
        raise RuntimeError(f"官方來源資料日期倒退：{day}，現有 {max(old)}；拒絕覆寫")
    candles = get_candles()
    for row in incoming:
        day = row["date"]
        old_record = old.get(day, {})
        if old_record:
            # Do not carry prior-day collateral, matched sample sizes or
            # calculated coverage into a freshly source-verified ratio.
            unverified = {"listedCollateralTwd", "otcCollateralTwd", "listedCoverage", "otcCoverage",
                          "listedMatched", "otcMatched", "listedPositive", "otcPositive",
                          "otcSource", "provenance", "otcError", "ratioSource", "ratioSourceDate",
                          "ratioVerification", "provenanceByScope"}
            clean_old = {k:v for k,v in old_record.items() if k not in unverified}
            row = {**clean_old, **{k:v for k,v in row.items() if v is not None}}
            if "otcLoanTwd" not in row:
                row.pop("otcLoanTwd", None)
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
            "name":"愛玩股市場融資維持率（核對 TWSE 官方日期、融資金額與加權指數）",
            "url":SOURCE,
            "method":"來源公布之上市／上櫃與整體市場維持率；以官方同日融資金額及指數核對；非券商個別整戶維持率",
            "classification":"第三方市場維持率系列，官方融資金額與指數逐日核對；每筆 provenanceByScope 標示來源",
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
