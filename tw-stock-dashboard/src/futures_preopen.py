"""Read a dated, recent TX near-month quote from Yahoo Taiwan's public quote page.
This is an indicative third-party display, NOT TAIFEX's completed official report,
a licensed low-latency market feed, or a formal cash-market Risk Score.
Fail closed when the date, trade time, price, or reference cannot be verified.
"""
from __future__ import annotations
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
import json
import os
import re
import requests
from bs4 import BeautifulSoup
from config import DATA_DIR

URL = "https://tw.stock.yahoo.com/future/futures.html?fumr=futurefull"
FUGLE_URL = "https://api.fugle.tw/marketdata/v1.0/futopt/intraday/quote/TXF1!"
OUT = DATA_DIR / "futures" / "intraday.json"
TZ = ZoneInfo("Asia/Taipei")
MAX_AGE = timedelta(minutes=25)
USER_AGENT = {"User-Agent": "Mozilla/5.0 (compatible; TXResearch/1.0)", "Accept-Language": "zh-TW,zh;q=0.9"}

class QuoteUnavailable(ValueError):
    pass

def parse_quote(html: str, now: datetime) -> dict:
    """Require an explicit current-date header and an 08:45+ transaction time."""
    now = now.astimezone(TZ)
    soup = BeautifulSoup(html, "html.parser")
    txt = " ".join(soup.stripped_strings)
    # Restrict date to the futures quotation section, not unrelated news dates.
    section = txt.find("即時期指報價")
    if section < 0:
        raise QuoteUnavailable("找不到台指期報價區塊")
    body = txt[section:]
    m = re.search(r"資料時間\s*[:：]\s*(20\d{2})[/-](\d{1,2})[/-](\d{1,2})", body)
    if not m:
        raise QuoteUnavailable("報價缺少可驗證的資料日期")
    day = f"{int(m[1]):04d}-{int(m[2]):02d}-{int(m[3]):02d}"
    if day != now.date().isoformat():
        raise QuoteUnavailable(f"供應商報價資料日 {day}，不是今天 {now.date()}")
    # Yahoo's nearby WTX& row must identify the contract, not the cash WTX00.
    row_match = re.search(r"台指期近一\s*WTX&\s*(.*?)(?=台指期近二\s*WTX@|金融期近一|台指期26\d{2}|$)", body, re.S)
    if not row_match:
        raise QuoteUnavailable("找不到台指期近一 WTX& 報價")
    row = row_match.group(1)
    tokens = re.findall(r"\d{2}:\d{2}:\d{2}|\d{1,3}(?:,\d{3})*(?:\.\d+)?%?", row)
    # Yahoo table: bid, ask, last, change, change%, volume, open, high,
    # low, basis, reference, open-interest, execution-time.
    if len(tokens) < 13:
        raise QuoteUnavailable("台指期報價欄位數不足")
    def price(v):
        try: return float(v.replace(",", ""))
        except ValueError: raise QuoteUnavailable("無效的報價數字")
    last, reference = price(tokens[2]), price(tokens[-3])
    if not (10000 <= last <= 100000 and 10000 <= reference <= 100000):
        raise QuoteUnavailable("台指期成交價或參考價異常")
    tm = next((re.fullmatch(r"\d{2}:\d{2}:\d{2}", v) for v in tokens if ":" in v), None)
    if not tm:
        raise QuoteUnavailable("找不到台指期成交時刻")
    try:
        observed = datetime.fromisoformat(f"{day}T{tm.group()}+08:00")
    except ValueError:
        raise QuoteUnavailable("成交時間無效")
    since = now - observed
    if not (timedelta(0) <= since <= MAX_AGE):
        raise QuoteUnavailable(f"非當前日盤成交或報價已過期：{observed.isoformat()}")
    if observed.hour < 8 or (observed.hour == 8 and observed.minute < 45) or observed.hour >= 14:
        raise QuoteUnavailable("成交時刻不在 08:45～13:45 日盤內")
    if observed.hour == 13 and observed.minute >= 45:
        raise QuoteUnavailable("成交時刻不在 08:45～13:45 日盤內")
    points = round(last-reference, 2)
    return {
        "status": "ok", "quality": "dated-third-party-snapshot",
        "asOfDate": day, "symbol": "WTX&", "product": "TX-near-month",
        "last": last, "reference": reference,
        "changePoints": points, "changePct": round(points/reference*100, 3),
        "quoteTime": observed.isoformat(), "fetchedAt": now.isoformat(timespec="seconds"),
        "maxAgeMinutes": int(MAX_AGE.total_seconds()/60),
        "source": "Yahoo奇摩股市期指近一（第三方公開頁面，可能延遲）", "sourceUrl": URL,
        "disclaimer": "非期交所授權即時API，僅為第三方當日報價快照；不寫回現貨正式風控／F2。"
    }

def parse_fugle_quote(data: dict, now: datetime) -> dict:
    """Fugle authenticated futures REST quote, real executed trade only (no auction)."""
    now = now.astimezone(TZ)
    if not isinstance(data, dict) or data.get("date") != now.date().isoformat():
        raise QuoteUnavailable("富果期貨資料日不符今日")
    if data.get("exchange") != "TAIFEX" or not re.fullmatch(r"TXF[A-L]\d", str(data.get("symbol",""))):
        raise QuoteUnavailable("富果回應非 TXF 近月月份合約")
    if data.get("isTrial"):
        raise QuoteUnavailable("富果只提供試撮盤，尚無正式成交")
    stamp = data.get("closeTime") or (data.get("lastTrade") or {}).get("time")
    if not isinstance(stamp, (int, float)) or stamp <= 0:
        raise QuoteUnavailable("富果缺少可核對的正式成交時間")
    observed = datetime.fromtimestamp(stamp / 1000000, tz=TZ)
    age = now - observed
    if observed.date() != now.date() or not timedelta(0) <= age <= MAX_AGE:
        raise QuoteUnavailable("富果今日 TX 報價過期或為未來時間")
    mins = observed.hour*60+observed.minute
    if not (8*60+45 <= mins < 13*60+45):
        raise QuoteUnavailable("富果成交時間不在當日日盤")
    try:
        last = float(data.get("closePrice") or (data.get("lastTrade") or {}).get("price"))
        reference = float(data.get("previousClose"))
    except (TypeError, ValueError):
        raise QuoteUnavailable("富果成交價或前收盤價缺失")
    if not (10000 <= last <= 100000 and 10000 <= reference <= 100000):
        raise QuoteUnavailable("富果成交價／前收盤價異常")
    points = round(last - reference, 2)
    return {
        "status":"ok", "quality":"dated-third-party-snapshot",
        "asOfDate": now.date().isoformat(), "symbol":"WTX&",
        "contract":data["symbol"], "product":"TX-near-month",
        "last":last, "reference":reference, "changePoints":points,
        "changePct":round(points/reference*100,3),
        "quoteTime":observed.isoformat(), "fetchedAt":now.isoformat(timespec="seconds"),
        "maxAgeMinutes":25, "source":"富果期貨行情 API（正式成交資料）",
        "sourceUrl":"https://developer.fugle.tw/docs/data-futopt/http-api/intraday/quote/",
        "disclaimer":"第三方期貨報價；正式現貨 Risk Score／F2 不隨此資料改寫。"
    }

def run(now: datetime | None = None):
    now = (now or datetime.now(TZ)).astimezone(TZ)
    mins = now.hour*60+now.minute
    if now.weekday() >= 5 or not (8*60+45 <= mins <= 13*60+45):
        print("TX_INTRADAY_OUTSIDE_DAY_SESSION", now.isoformat())
        return
    result = None
    errors = []
    key = os.environ.get("FUGLE_API_KEY","").strip()
    if key:
        try:
            r = requests.get(FUGLE_URL, headers={"X-API-KEY":key}, timeout=15)
            r.raise_for_status()
            result = parse_fugle_quote(r.json(), now)
        except (requests.RequestException, QuoteUnavailable, ValueError, KeyError, TypeError) as exc:
            errors.append("Fugle: "+str(exc)[:110])
    else:
        errors.append("未設定 FUGLE_API_KEY")
    if result is None:
        for target in (URL,"https://tw.finance.yahoo.com/future/futures.html?fumr=futurefull"):
            try:
                r = requests.get(target, headers=USER_AGENT, timeout=15, params={"t":str(int(now.timestamp()))})
                r.raise_for_status()
                result = parse_quote(r.text, now)
                result["sourceUrl"] = target
                break
            except (requests.RequestException, QuoteUnavailable, ValueError, IndexError) as exc:
                errors.append("Yahoo: "+str(exc)[:100])
    if result is None:
        result = {
            "status": "unavailable", "quality": "no-valid-current-quote",
            "asOfDate": now.date().isoformat(), "checkedAt": now.isoformat(timespec="seconds"),
            "reason": "；".join(errors)[:240], "sourceUrl":FUGLE_URL if key else URL
        }
        print("TX_INTRADAY_UNAVAILABLE", result["reason"])
    else:
        print("TX_INTRADAY_VERIFIED", result["quoteTime"], result["last"], result["changePct"], result["source"])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    if OUT.exists():
        old = json.loads(OUT.read_text(encoding="utf-8"))
        # Do not regress from a newer verified observation to an older response.
        if old.get("status") == "ok" and old.get("asOfDate") == result["asOfDate"]:
            if result["status"] != "ok" and now-datetime.fromisoformat(old["quoteTime"]) <= MAX_AGE:
                print("TX_INTRADAY_KEEP_RECENT_VERIFIED_QUOTE")
                return
            if result["status"] == "ok" and result["quoteTime"] <= old.get("quoteTime",""):
                print("TX_INTRADAY_NO_NEW_TICK")
                return
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")

if __name__ == "__main__":
    run()
