#!/usr/bin/env python3
"""Public WantGoo VIXTWN observation; not TAIFEX official closing data.

Values are observed quotes, not extrapolated OHLC or risk-score inputs.
Never claim an old quote is a current session observation.
"""
from __future__ import annotations

import json
import math
import os
import re
from datetime import datetime, timedelta
from html.parser import HTMLParser
from pathlib import Path
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "docs/data/research/tw_vix/latest.json"
SOURCE = "https://www.wantgoo.com/index/vixtwn"
OFFICIAL = "https://www.taifex.com.tw/cht/7/vixDaily3MNew"
TZ = ZoneInfo("Asia/Taipei")
MAX_BYTES = 2_000_000

class VisibleText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript"):
            self.skip += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript") and self.skip:
            self.skip -= 1

    def handle_data(self, data):
        if not self.skip and data.strip():
            self.parts.append(data.strip())


def parse_wantgoo(raw: str, now: datetime | None = None) -> dict:
    now = (now or datetime.now(TZ)).astimezone(TZ)
    text = VisibleText()
    text.feed(raw)
    flat = " ".join(text.parts)
    matches = list(re.finditer(r"\bVIXTWN\s+(20\d{2}-\d{2}-\d{2})\s+([012]\d:[0-5]\d)\b", flat, re.I))
    if not matches:
        raise ValueError("WantGoo 缺少 VIXTWN 的原始報價日期與時間")
    for match in matches:
        segment = flat[match.end():match.end()+220]
        quote = re.search(r"(?<![\d.])([1-9]\d{0,2}\.\d{1,2})\s+([+-]?\d{1,3}\.\d{1,2})\s+([+-]?\d{1,3}\.\d{1,2})\s*%", segment)
        if not quote:
            continue
        value, delta, pct = (float(v) for v in quote.groups())
        at = datetime.strptime(match.group(1)+" "+match.group(2), "%Y-%m-%d %H:%M").replace(tzinfo=TZ)
        previous = value-delta
        if not (5 <= value <= 150 and previous > 0 and abs(delta) <= 70 and abs(pct) <= 90):
            raise ValueError("VIXTWN 變動或報價超出合理範圍")
        if not math.isclose(pct, delta/previous*100, abs_tol=0.25):
            raise ValueError("VIXTWN 指數、漲跌值與百分比不一致")
        if at > now + timedelta(minutes=5):
            raise ValueError("VIXTWN 來源時間在未來")
        if (now-at) > timedelta(days=7):
            raise ValueError("VIXTWN 來源資料已過期超過七天")
        return {"date":at.date().isoformat(),"time":at.strftime("%H:%M"),
                "value":round(value,2),"change":round(delta,2),"changePct":round(pct,2)}
    raise ValueError("WantGoo VIXTWN 報價欄位無法辨識；拒絕發布")

def validate_rows(rows: list) -> list:
    if not isinstance(rows,list):
        raise ValueError("歷史格式錯誤")
    dates = set()
    out = []
    for item in rows:
        if not isinstance(item,dict):
            raise ValueError("歷史紀錄格式錯誤")
        day,clock = item.get("date"),item.get("time")
        v,d,p = (item.get(k) for k in ("value","change","changePct"))
        if (not isinstance(day,str) or not re.fullmatch(r"20\d{2}-\d{2}-\d{2}",day)
            or not isinstance(clock,str) or not re.fullmatch(r"(?:0\d|1\d|2[0-3]):[0-5]\d",clock)
            or day in dates or not all(isinstance(n,(int,float)) and math.isfinite(n) for n in (v,d,p))
            or not 5<=v<=150 or v-d<=0 or not math.isclose(p,100*d/(v-d),abs_tol=.25)):
            raise ValueError("歷史日期、來源及數值無法驗證")
        datetime.strptime(day,"%Y-%m-%d")
        dates.add(day);out.append({"date":day,"time":clock,"value":v,"change":d,"changePct":p})
    return sorted(out,key=lambda x:x["date"])[-260:]


def update(existing: dict, observation: dict, now: datetime | None = None) -> dict:
    now = (now or datetime.now(TZ)).astimezone(TZ)
    if existing and existing.get("version") != "TW_VIX_WANTGOO_QUOTES_V1":
        raise ValueError("不允許把其他波動指數歷史冒充 VIXTWN")
    rows = validate_rows(existing.get("rows",[]) if existing else [])
    latest = rows[-1] if rows else None
    if latest and observation["date"] < latest["date"]:
        raise ValueError("來源交易日期倒退")
    if latest and observation["date"]==latest["date"]:
        if observation["time"] < latest["time"]:
            raise ValueError("同日來源時間倒退，拒絕以舊值覆寫")
        rows.pop()
    rows = validate_rows([*rows,observation])
    last=rows[-1]
    return {"version":"TW_VIX_WANTGOO_QUOTES_V1",
            "sourceName":"玩股網 VIXTWN 公開報價（非期交所正式收盤）",
            "sourceUrl":SOURCE,"officialReference":OFFICIAL,
            "method":"每日最後一次成功擷取的公開報價；非官方每日收盤價、不保證即時",
            "updatedAt":now.isoformat(timespec="seconds"),
            "asOfDate":last["date"],"sourceObservationAt":last["date"]+"T"+last["time"]+":00+08:00",
            "rows":rows}


def main():
    now = datetime.now(TZ)
    request = Request(SOURCE,headers={"User-Agent":"Mozilla/5.0 (compatible; TaiwanMarketDashboard/1.0)","Accept":"text/html"})
    with urlopen(request,timeout=30) as response:
        data=response.read(MAX_BYTES+1)
    if len(data)>MAX_BYTES:
        raise ValueError("VIXTWN 報價頁面過大")
    observation=parse_wantgoo(data.decode("utf-8-sig",errors="replace"),now)
    # Do not report yesterday's quote as a live intraday observation.
    if now.weekday()<5 and (9,45)<=(now.hour,now.minute)<=(13,45):
        at=datetime.fromisoformat(observation["date"]+"T"+observation["time"]+":00+08:00")
        if (now-at)>timedelta(minutes=65):
            raise ValueError("盤中 VIXTWN 超過 65 分鐘未更新")
    old={}
    if DEST.exists():
        old=json.loads(DEST.read_text("utf-8"))
    payload=update(old,observation,now)
    DEST.parent.mkdir(parents=True,exist_ok=True)
    tmp=DEST.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    os.replace(tmp,DEST)
    print("TW_VIX_OK",payload["asOfDate"],payload["sourceObservationAt"],
          payload["rows"][-1]["value"],"observations",len(payload["rows"]))

if __name__=="__main__":
    main()
