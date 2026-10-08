"""As-of revenue filter for exploratory E = D + (MoM>0 or YoY>0).
Official MOPS historical monthly snapshots do NOT include a reliable first-publication
timestamp. Conservative signal availability: month M becomes usable on M+1 day 11.
This is a point-in-time approximation, not timestamp-verified company announcements.
"""
from __future__ import annotations
from datetime import date
from calendar import monthrange
from pathlib import Path
import json,re,time
import requests
from bs4 import BeautifulSoup

HOSTS=("https://mopsov.twse.com.tw","https://mops.twse.com.tw")
UA={"User-Agent":"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36","Accept-Language":"zh-TW,zh;q=0.9"}
def _numeric(v):
    s=str(v or "").strip().replace(",","").replace("%","").replace("＋","+").replace("－","-")
    if not s or s in {"--","-","—","N/A"}:return None
    try:return float(s)
    except ValueError:return None
def parse_month_html(content):
    """Read first 7 columns in real company rows; ignore subtotals and nested header tables."""
    html=content.decode("cp950",errors="replace") if isinstance(content,bytes) else content
    soup=BeautifulSoup(html,"html.parser")
    data={}
    for tr in soup.select("tr"):
        cols=tr.find_all(["th","td"],recursive=False)
        if len(cols)<7 or len(cols)>12:continue
        cells=[c.get_text(" ",strip=True).replace("\u3000"," ").strip() for c in cols]
        code=cells[0].split()[0] if cells[0] else ""
        if not re.fullmatch(r"[0-9]{4}",code):continue
        # MOPS columns: code, name, this-month, prior-month, last-year,
        # growth over prior month (%), growth over last year (%).
        mom=_numeric(cells[5]);yoy=_numeric(cells[6])
        if mom is None and yoy is None:continue
        data[code]={"mom":mom,"yoy":yoy}
    return data
def months_between(start,end):
    y,m=start.year,start.month
    while (y,m)<=(end.year,end.month):
        yield y,m
        y,m=(y+1,1) if m==12 else (y,m+1)
def next_month_day_11(year,month):
    return (f"{year+1}-01-11" if month==12 else f"{year}-{month+1:02d}-11")
class RevenueHistory:
    def __init__(self,rows,coverage,policy):
        self.rows=rows;self.coverage=coverage;self.policy=policy
    def asof(self,market,code,asof_date):
        key=(str(market),str(code))
        for v in reversed(self.rows.get(key,[])):
            if v["available"]<=asof_date:
                # Do not silently fall back many months if a company lacks current reports.
                year,month=map(int,v["month"].split("-"))
                ey,em=map(int,asof_date[:7].split("-"))
                age=(ey-year)*12+em-month
                return v if age<=3 else None
        return None
    def pass_e(self,market,code,asof_date):
        x=self.asof(market,code,asof_date)
        return bool(x and ((x["mom"] is not None and x["mom"]>0) or (x["yoy"] is not None and x["yoy"]>0)))
def fetch_mops_monthly(start,end,cache_dir,delay=0.4,minimum_companies=450):
    """Monthly reports cover both TWSE and TPEx, including foreign incorporations.
    Both _0/_1 are fetched; only _0 is expected to pass the count threshold.
    Reject incomplete market-month coverage to avoid optimistic missing-data filtering.
    """
    start=date.fromisoformat(start);end=date.fromisoformat(end);cache_dir=Path(cache_dir)
    cache_dir.mkdir(parents=True,exist_ok=True)
    # 11th rule: first usable at signal-day start is two months before start month.
    y=start.year;m=start.month-2
    while m<=0:y-=1;m+=12
    from_month=date(y,m,1)
    # No need for reports whose conservative availability is later than the end date.
    end_y,end_m=end.year,end.month-1 if end.day<11 else end.month
    if end_m<=0:end_y-=1;end_m=12
    to_month=date(end_y,end_m,1)
    rows={};coverage=[];errors=[]
    for year,month in months_between(from_month,to_month):
        for market,folder in [("上市","sii"),("上櫃","otc")]:
            combined={};source_stats=[]
            for flag in [0,1]:
                filename=f"t21sc03_{year-1911}_{month}_{flag}.html"
                cached=cache_dir/f"{folder}_{filename}"
                content=cached.read_bytes() if cached.exists() else None
                parsed=parse_month_html(content) if content else {}
                if not parsed:
                    last_error=""
                    for host in HOSTS:
                        url=f"{host}/nas/t21/{folder}/{filename}"
                        try:
                            resp=requests.get(url,headers=UA,timeout=45);resp.raise_for_status()
                            if len(resp.content)<1000:raise RuntimeError("response too small")
                            candidate=parse_month_html(resp.content)
                            if not candidate:raise RuntimeError("no company rows")
                            content=resp.content;parsed=candidate;cached.write_bytes(content);break
                        except Exception as e:last_error=str(e);time.sleep(1)
                    if not parsed:
                        if flag==0:errors.append(f"{market} {year}-{month:02d}: {last_error}")
                        source_stats.append({"flag":flag,"n":0})
                        continue
                    time.sleep(delay)
                combined.update(parsed);source_stats.append({"flag":flag,"n":len(parsed)})
            coverage.append({"market":market,"month":f"{year}-{month:02d}","companies":len(combined),"source":source_stats})
            if len(combined)<minimum_companies:
                errors.append(f"{market} {year}-{month:02d} only {len(combined)} companies")
                continue
            for code,p in combined.items():
                x={"market":market,"code":code,"month":f"{year}-{month:02d}",
                   "available":next_month_day_11(year,month),"mom":p["mom"],"yoy":p["yoy"]}
                rows.setdefault((market,code),[]).append(x)
            print(f"revenue {market} {year}-{month:02d}: {len(combined)} companies",flush=True)
    if errors:raise RuntimeError("Revenue history incomplete; no backtest allowed: "+"; ".join(errors[:12]))
    for r in rows.values():r.sort(key=lambda x:x["month"])
    return RevenueHistory(rows,coverage,"M+1 day 11, after monthly reporting deadline; approximate announcement timing")
