"""Collect MOPS historical quarterly consolidated ROE inputs (research, revised vintage).

Bulk sources:
 POST https://mopsov.twse.com.tw/mops/web/ajax_t163sb04  cumulative income
 POST https://mopsov.twse.com.tw/mops/web/ajax_t163sb05  ending equity
Both values are reported in NTD 1,000 units. Reject unrecognized captions,
missing fiscal comparisons, and incomplete source coverage; never estimate ROE.
MOPS historical bulk may have revisions; conservative quarter deadline dates
are used as NOT-BEFORE proxies, not the genuine first filing timestamps.
"""
from __future__ import annotations
import argparse,json,re,time
from collections import defaultdict
from datetime import date
from pathlib import Path
import requests
from bs4 import BeautifulSoup
from n_fundamental_archive import quarter_safe_date,fetch_binary,text_decode
from config import DATA_DIR,ROOT

OUT=DATA_DIR/"research"/"quality"
CACHE=ROOT/"cache"/"quality_mops"
URL="https://mopsov.twse.com.tw/mops/web/ajax_t163sb"
MARKETS=("sii","otc")
CAPTIONS={
 "income":{"本期淨利淨損","本期淨利損","本期稅後淨利淨損"},
 "equity":{"權益總計","權益總額","權益合計"}
}
def caption(x):
    return re.sub(r"[\s\u3000()（）\-—]", "",str(x))
def asnumber(x):
    s=str(x).strip().replace(",","").replace(" ","")
    if s.startswith("(") and s.endswith(")"):s="-"+s[1:-1]
    if not re.fullmatch(r"-?\d+(?:\.\d+)?",s):return None
    return float(s)
def parse_bulk(html,kind,market,year,q):
    """Extract only tables with an explicit unique caption. Never assume fixed column offsets."""
    soup=BeautifulSoup(html,"html.parser")
    result={};valid=0
    for table in soup.select("table"):
        grid=[[c.get_text(" ",strip=True) for c in tr.find_all(["td","th"],recursive=False)] for tr in table.select("tr")]
        location=None
        for i,head in enumerate(grid[:12]):
            matches=[j for j,h in enumerate(head) if caption(h) in CAPTIONS[kind]]
            if len(matches)==1:
                location=(i,matches[0]);break
        if location is None:continue
        hrow,index=location
        count=0
        for row in grid[hrow+1:]:
            if len(row)<=index:continue
            code=next((str(row[j]).strip() for j in (0,1) if j<len(row) and re.fullmatch(r"\d{4,6}",str(row[j]).strip())),None)
            if code is None:continue
            amount=asnumber(row[index])
            if amount is None or abs(amount)>1e16:continue
            if code in result and result[code]!=amount:raise RuntimeError(f"conflicting MOPS {kind} {market} {year}Q{q} {code}")
            result[code]=amount;count+=1
        if count:valid+=1
    return result,valid
def retrieve(session,kind,market,y,q):
    CACHE.mkdir(parents=True,exist_ok=True)
    file=CACHE/f"{kind}_{market}_{y}Q{q}.html"
    post={"encodeURIComponent":"1","step":"1","firstin":"1","off":"1","TYPEK":market,
          "year":str(y-1911),"season":f"{q:02d}"}
    if file.exists():blob=file.read_bytes()
    else:
        blob=fetch_binary(session,URL+("04" if kind=="income" else "05"),post=post)
        file.write_bytes(blob)
    rows,tables=parse_bulk(text_decode(blob),kind,market,y,q)
    if len(rows)<120 or tables<1:
        raise RuntimeError(f"insufficient verified {kind} {market} {y}Q{q}, rows={len(rows)} tables={tables}")
    return rows,{"market":market,"type":kind,"year":y,"quarter":q,"rows":len(rows),"tables":tables}
def build_records(income,equity,final_date):
    """TTM current YTD - prior-year comparable YTD + prior-year annual net."""
    rows=[]
    for market,code,y,q in sorted(equity):
        if quarter_safe_date(y,q)>final_date:continue
        cur_eq=equity.get((market,code,y,q))
        old_eq=equity.get((market,code,y-1,q))
        current=income.get((market,code,y,q))
        prev=income.get((market,code,y-1,q))
        annual=income.get((market,code,y-1,4))
        if any(v is None for v in (cur_eq,old_eq,current)):continue
        if q==4:ttm=current
        elif prev is None or annual is None:continue
        else:ttm=current+annual-prev
        if not (0<cur_eq<1e16 and 0<old_eq<1e16 and -1e16<ttm<1e16):continue
        value=100*ttm/((cur_eq+old_eq)/2)
        if not -200<=value<=300:continue
        rows.append({"market":market,"code":code,"year":y,"quarter":q,
            "availableFrom":quarter_safe_date(y,q),"netIncomeTTM":round(ttm,3),
            "equityNow":round(cur_eq,3),"equityYearAgo":round(old_eq,3),
            "source":"MOPS_CONSOLIDATED_QUARTER",
            "equityScope":"consolidated_total","netIncomeScope":"consolidated_total",
            "unit":"NTD thousands","vintage":"revised historical bulk",
            "publicationTiming":"conservative quarter deadline proxy"})
    return rows
def run(start_year,end_year,asof):
    session=requests.Session();income={};equity={};provenance=[];fail=[]
    start=max(2021,start_year-1)
    quarters=[(y,q,m) for y in range(start,end_year+1) for q in range(1,5)
              if quarter_safe_date(y,q)<=asof for m in MARKETS]
    for y,q,m in quarters:
        for kind,dest in (("income",income),("equity",equity)):
            key=f"{m}_{y}Q{q}_{kind}"
            try:
                vals,audit=retrieve(session,kind,m,y,q)
                dest.update({(m,code,y,q):v for code,v in vals.items()})
                provenance.append(audit)
                print("ROE_SOURCE_OK",key,len(vals),flush=True)
            except (requests.RequestException,RuntimeError,ValueError) as ex:
                fail.append({"key":key,"error":str(ex)})
                print("ROE_SOURCE_FAIL",key,ex,flush=True)
            time.sleep(.6)
    records=build_records(income,equity,asof)
    checks={"version":"ROE_MOPS_REVISED_ARCHIVE_V1","startYear":start_year,
        "endYear":end_year,"asOf":asof,"quarterSlices":len(quarters),
        "successfulSlices":len(provenance),"records":len(records),
        "failures":fail,"sliceCoverage":provenance,
        "pointInTimeImmutable":False,
        "warning":"MOPS revised reports with conservative release-date proxy; not original-filing as-of database"}
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/"roe_coverage.json").write_text(json.dumps(checks,ensure_ascii=False,indent=2),encoding="utf8")
    if fail or len(provenance)!=len(quarters)*2 or len(records)<300:
        raise RuntimeError("ROE official history incomplete; refusing to publish unverified roe_quarter.json")
    (OUT/"roe_quarter.json").write_text(json.dumps(records,ensure_ascii=False,separators=(",",":")),encoding="utf8")
    print("ROE_ARCHIVE_SUCCESS",len(records),flush=True)
if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--start-year",type=int,default=2023)
    p.add_argument("--end-year",type=int,default=2026)
    p.add_argument("--asof",default=date.today().isoformat())
    a=p.parse_args()
    if a.end_year<a.start_year or a.end_year>date.today().year:raise ValueError("invalid fiscal range")
    run(a.start_year,a.end_year,a.asof)
