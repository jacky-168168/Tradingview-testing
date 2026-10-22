#!/usr/bin/env python3
"""Refresh the public WantGoo Fear & Greed / S&P 500 daily chart.
WantGoo supplies new readings; pre-switch records remain explicitly attributed
to the existing archived CNN and SqueezeMetrics series. Never invent values.
"""
from __future__ import annotations
import json,math,re,urllib.request
from datetime import date,datetime,timezone
from html.parser import HTMLParser
from pathlib import Path

BASE=Path(__file__).resolve().parents[1]
SOURCE="https://www.wantgoo.com/global/macroeconomics/fearandgreed"
OUT=BASE/"docs/data/research/us_fear_greed/history.json"
VERSION="US_WANTGOO_FEAR_GREED_SPX_V2"
HEADERS={"User-Agent":"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
         "Accept":"text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
         "Accept-Language":"zh-TW,zh;q=0.9,en;q=0.8"}
MOOD=r"(?:極度恐懼|極度貪婪|恐懼|貪婪|中立)"
RECORD=re.compile(r"(20\d{2}/\d{1,2}/\d{1,2})\s+"+MOOD+r"\s+(\d{1,3}(?:\.\d+)?)\s+([\d,]+(?:\.\d+)?)")
class VisibleText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.hidden=0
        self.tokens=[]
    def handle_starttag(self,tag,attrs):
        if tag in ("script","style","noscript"):self.hidden+=1
    def handle_endtag(self,tag):
        if tag in ("script","style","noscript") and self.hidden:self.hidden-=1
    def handle_data(self,data):
        if not self.hidden and data.strip():self.tokens.append(data.strip())

def score(v):
    if isinstance(v,bool):return None
    try:n=float(v)
    except (ValueError,TypeError):return None
    return round(n,3) if math.isfinite(n) and 0<=n<=100 else None

def parse_wantgoo(html):
    """Extract only explicitly dated score + S&P 500 rows, not headline guesses."""
    if not isinstance(html,str) or "恐懼與貪婪指數" not in html:
        raise ValueError("WantGoo Fear & Greed heading missing")
    p=VisibleText();p.feed(html)
    flat=re.sub(r"\s+"," "," ".join(p.tokens))
    rows={}
    for match in RECORD.finditer(flat):
        try:
            d=datetime.strptime(match.group(1),"%Y/%m/%d").date().isoformat()
            v=score(match.group(2))
            spx=float(match.group(3).replace(",",""))
            if v is None or not math.isfinite(spx) or not 100<spx<100000:continue
            if d>datetime.now(timezone.utc).date().isoformat():continue
            row=[d,v,round(spx,3)]
            if d in rows and rows[d]!=row:raise ValueError("Conflicting WantGoo records for "+d)
            rows[d]=row
        except (ValueError,OverflowError):
            continue
    if len(rows)<2:
        raise ValueError("WantGoo dated Fear & Greed / S&P 500 table not found (must have >=2 rows)")
    return [rows[d] for d in sorted(rows)]

def to_archive(wantgoo_html,previous):
    incoming=parse_wantgoo(wantgoo_html)
    if not isinstance(previous,dict) or previous.get("columns")!=["date","fearGreed","spx"]:
        raise ValueError("Published historical archive missing or incompatible")
    records={}
    for r in previous.get("rows",[]):
        if not isinstance(r,list) or len(r)!=3:continue
        try:
            d=str(r[0]);f=score(r[1]);spx=float(r[2])
            if re.fullmatch(r"20\d{2}-\d{2}-\d{2}",d) and f is not None and math.isfinite(spx) and spx>100:records[d]=[d,f,round(spx,3)]
        except (TypeError,ValueError):continue
    if len(records)<150:raise ValueError("Published historic archive too short")
    old_last=max(records)
    new_last=incoming[-1][0]
    if new_last<old_last:raise ValueError("WANTGOO_BEHIND_ARCHIVE: WantGoo="+new_last+" archive="+old_last)
    if (datetime.now(timezone.utc).date()-date.fromisoformat(new_last)).days>6:
        raise ValueError("WANTGOO_SOURCE_STALE: "+new_last)
    if previous.get("version")==VERSION:
        legacy_through=previous.get("legacyThrough")
        legacy_source=previous.get("legacyHistorySource")
        legacy_spx=previous.get("legacySpxSource")
    else:
        legacy_through=max((d for d in records if d<incoming[0][0]),default=None)
        legacy_source=previous.get("sourceLink") or previous.get("source")
        legacy_spx=previous.get("spxSource")
    # Keep older observations, but overwrite overlapping dates with WantGoo's
    # actual quoted daily scores and S&P prices, including any revisions.
    for r in incoming:records[r[0]]=r
    rows=[records[d] for d in sorted(records)]
    return {"version":VERSION,"source":SOURCE,"sourceLink":SOURCE,
            "spxSource":"WantGoo (new rows); legacy source documented separately",
            "legacyThrough":legacy_through,"legacyHistorySource":legacy_source,
            "legacySpxSource":legacy_spx,"wantgooLast":new_last,
            "spxLast":new_last,"asOf":rows[-1][0],
            "updatedAt":datetime.now(timezone.utc).isoformat(),
            "columns":["date","fearGreed","spx"],"rows":rows,
            "components":{},
            "disclaimer":"WantGoo daily scores and SPX from its public dated table. Records on/before legacyThrough were retained from the previous CNN + SqueezeMetrics archive; no interpolation, invented readings or trading signals."}

def fetch_wantgoo():
    req=urllib.request.Request(SOURCE,headers=HEADERS,method="GET")
    with urllib.request.urlopen(req,timeout=40) as resp:
        if resp.status!=200:raise RuntimeError("WantGoo HTTP "+str(resp.status))
        data=resp.read(3_000_001)
    if len(data)>3_000_000:raise ValueError("WantGoo response unexpectedly large")
    return data.decode("utf-8")

def main():
    previous=json.loads(OUT.read_text(encoding="utf-8"))
    result=to_archive(fetch_wantgoo(),previous)
    OUT.write_text(json.dumps(result,ensure_ascii=False,separators=(",",":"))+"\n",encoding="utf-8")
    print("WANTGOO_FEAR_GREED_VALID",result["wantgooLast"],"rows",len(result["rows"]),
          "legacyThrough",result["legacyThrough"])
if __name__=="__main__":main()
