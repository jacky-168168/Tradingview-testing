"""依櫃買中心同一交易日的官方資料計算上櫃融資維持率。

分子：上櫃每檔融資今日餘額（張）×1000×收盤價。
分母：櫃買中心當日融資金(仟元)之資餘額×1000。
日期不同、股票報價涵蓋不足、分母不存在皆拒絕發佈。不使用比例倒推分母。
"""
from __future__ import annotations

import math
import re
from datetime import datetime
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

ROOT = "https://www.tpex.org.tw"
API = ROOT + "/openapi/v1/"
MARGIN_URL = API + "tpex_mainboard_margin_balance"
QUOTE_URL = API + "tpex_mainboard_quotes"
DAILY_URL = API + "tpex_mainboard_daily_close_quotes"
TOTAL_URL = ROOT + "/web/stock/margin_trading/margin_balance/margin_bal_result.php"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; Taiwan Stock Dashboard/1.0)",
           "Accept": "application/json,text/html"}
TW = ZoneInfo("Asia/Taipei")
DAY_CODE = re.compile(r"^1\d{6}$")
NUMBER = re.compile(r"-?[\d,]+(?:\.\d+)?")

def decimal(v):
    try:
        n = float(str(v).replace(",", "").strip())
        return n if math.isfinite(n) else None
    except (TypeError, ValueError):
        return None

def roc_to_iso(raw):
    value = str(raw or "").strip()
    if not DAY_CODE.fullmatch(value):
        raise ValueError(f"TPEx 日期格式不正確：{value!r}")
    year = int(value[:3]) + 1911
    day = f"{year:04d}-{value[3:5]}-{value[5:7]}"
    datetime.strptime(day, "%Y-%m-%d")
    return day

def iso_to_roc(day):
    d = datetime.strptime(day, "%Y-%m-%d")
    if d.year < 2012 or d.year > 2100:
        raise ValueError("交易日超出檢查區間")
    return f"{d.year-1911:03d}/{d.month:02d}/{d.day:02d}"

def check_payload_rows(rows, field, expected_day, minimum):
    if not isinstance(rows, list) or len(rows) < minimum:
        raise RuntimeError(f"TPEx {field} 資料筆數不足")
    days = {roc_to_iso(r.get("Date")) for r in rows if isinstance(r, dict)}
    if days != {expected_day}:
        raise RuntimeError(f"TPEx {field} 資料日期不符：{sorted(days)}，預期 {expected_day}")
    return rows

def get_json(session, url):
    r = session.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    return r.json()

def parse_loan_html(html, expected_day):
    soup = BeautifulSoup(html, "html.parser")
    flat = soup.get_text(" ", strip=True).replace("\u3000", " ")
    roc = iso_to_roc(expected_day)
    # 網頁可能忽略日期參數，務必核對畫面上的實際資料日期。
    dt = re.search(r"資料日期\s*[:：]\s*(\d{3}/\d{1,2}/\d{1,2})", flat)
    if not dt:
        raise RuntimeError("櫃買報表無資料日期，拒絕合併")
    y, m, d = (int(x) for x in dt.group(1).split("/"))
    report_day = f"{y+1911:04d}-{m:02d}-{d:02d}"
    if report_day != expected_day:
        raise RuntimeError(f"櫃買融資金額日期 {report_day} 不等於 {expected_day}")
    for tr in soup.find_all("tr"):
        vals = [v.get_text(" ", strip=True).replace("\u3000", " ") for v in tr.find_all(["td", "th"])]
        if len(vals) < 6:
            continue
        label = re.sub(r"\s+", "", vals[0])
        if "融資金" not in label or "仟元" not in label:
            continue
        # 舊版欄位：前資餘額、資買、資賣、現償、資餘額（索引 1..5）
        balance = decimal(vals[5])
        if balance is None or not 50_000_000 < balance < 1_000_000_000:
            raise RuntimeError(f"櫃買融資金額超出合理範圍：{vals[5]}")
        return balance * 1000
    raise RuntimeError("櫃買報表未找到「融資金(仟元)」今日餘額")

def main(expected_day=None, session=None):
    session = session or requests.Session()
    balances = get_json(session, MARGIN_URL)
    if not isinstance(balances, list) or len(balances) < 500:
        raise RuntimeError("櫃買融資餘額資料不足")
    if expected_day is None:
        expected_day = roc_to_iso(balances[0].get("Date"))
    if expected_day > datetime.now(TW).date().isoformat():
        raise RuntimeError("櫃買資料日期在未來")
    check_payload_rows(balances, "融資", expected_day, 500)
    quotes = check_payload_rows(get_json(session, QUOTE_URL), "行情", expected_day, 500)
    bycode = {}
    for r in balances:
        code = str(r.get("SecuritiesCompanyCode") or "").strip()
        lots = decimal(r.get("MarginPurchaseBalance"))
        if not code or lots is None or lots < 0 or code in bycode:
            if code in bycode:
                raise RuntimeError(f"櫃買重複融資代碼 {code}")
            continue
        bycode[code] = lots
    prices = {}
    for r in quotes:
        code = str(r.get("SecuritiesCompanyCode") or "").strip()
        price = decimal(r.get("Close"))
        if code and price and price > 0:
            prices[code] = price
    positive = {c:v for c,v in bycode.items() if v>0}
    matched = {c:v for c,v in positive.items() if c in prices}
    coverage = len(matched) / len(positive) if positive else 0
    if len(matched)<500 or coverage<0.95:
        raise RuntimeError(f"櫃買融資市值涵蓋不足 {len(matched)}/{len(positive)}={coverage:.2%}")
    roc=iso_to_roc(expected_day)
    response = session.get(TOTAL_URL, params={"l":"zh-tw","o":"htm","d":roc}, headers=HEADERS, timeout=35)
    response.raise_for_status()
    loan = parse_loan_html(response.text, expected_day)
    collateral = sum(lots*1000*prices[c] for c,lots in matched.items())
    ratio = round(collateral/loan*100,2)
    if not 95 < ratio < 350:
        raise RuntimeError(f"上櫃推算融資維持率異常 {ratio}%")
    out = {"date":expected_day,"otc":ratio,"otcLoanTwd":round(loan),
           "otcCollateralTwd":round(collateral),"otcCoverage":round(coverage,6),
           "otcMatched":len(matched),"otcPositive":len(positive),
           "otcSource":"TPEx OpenAPI 上櫃融資＋收盤行情；TPEx 融資金額報表"}
    print("TPEX_DERIVED",out,flush=True)
    return out

if __name__=="__main__":
    print(main())
