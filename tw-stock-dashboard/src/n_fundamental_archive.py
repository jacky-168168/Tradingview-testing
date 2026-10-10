"""N (CANSLIM growth-momentum) official historical fundamentals collector.

Source:
- https://mopsov.twse.com.tw/nas/t21/{sii|otc}/t21sc03_{ROC}_{month}_{domestic|foreign}.html
- POST https://mopsov.twse.com.tw/mops/web/ajax_t163sb04
  TYPEK=(sii|otc), year=ROC, season=01..04.
Archive is latest web historical vintage, NOT point-in-time filings. Availability
is conservatively DEFERRED to AFTER legal quarter/month deadlines, not asserted
actual issuer publication time. Fail closed if key months/quarters not verified.
"""
from __future__ import annotations
import csv,io,json,os,re,time
from datetime import date,datetime,timedelta
from pathlib import Path
from collections import Counter,defaultdict
import requests
from bs4 import BeautifulSoup
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"docs"/"data"/"research"/"n_canslim"
CACHE=ROOT/"cache"/"n_fundamental"
HEADERS={"User-Agent":"Mozilla/5.0 (compatible; ResearchArchive/1.0; educational historical tests)","Referer":"https://mopsov.twse.com.tw/mops/web/index"}
MONTHS=[(y,m) for y in range(2022,2027) for m in range(1,13) if (y>2022 or m>=1) and (y<2026 or m<=8)]
QUARTERS=[(y,q) for y in range(2022,2027) for q in range(1,5) if (y<2026 or q<=2)]
MARKETS=("sii","otc")
def text_decode(blob,html=False):
    for coding in (("big5","cp950","utf-8") if html else ("utf-8","big5","cp950")):
        try:
            s=blob.decode(coding)
            if "公司代號" in s or "每股盈餘" in s or "月營收" in s:return s
        except UnicodeDecodeError:continue
    return blob.decode("big5",errors="replace")
def numeric(v):
    raw=str(v).replace(",","").replace(" ","").replace("＋","+").replace("－","-").strip()
    raw=re.sub(r"\(.*?\)$","",raw)
    if not raw or raw in ("-","--","無","不適用","N/A","NA","－"):return None
    if raw.startswith("(") and raw.endswith(")"):raw="-"+raw[1:-1]
    try:return float(raw)
    except ValueError:return None
def valid_code(code):
    s=re.sub(r"\s","",str(code))
    return s if re.fullmatch(r"[0-9]{4,6}",s) else None
def parse_month_html(html,market,year,month,kind):
    soup=BeautifulSoup(html,"html.parser")
    found={};table_scans=0
    # The official file has MANY industry tables and its company code header is
    # often split across two <br> tags ("公司" / "代號"). Parse data rows directly;
    # reject aggregates and human headers using the strict numeric security ID.
    for table in soup.select("table"):
        local=0
        for tr in table.find_all("tr"):
            cells=[c.get_text(" ",strip=True) for c in tr.find_all(["td","th"],recursive=False)]
            if len(cells)<7:continue
            idx=next((i for i in (0,1) if valid_code(cells[i])),None)
            if idx is None or len(cells)<idx+7:continue
            code=valid_code(cells[idx]);rev=numeric(cells[idx+2])
            if rev is None or rev<0:continue
            row={"code":code,"name":cells[idx+1].strip(),"year":year,"month":month,
                 "revenue":rev,"market":market,"domesticType":kind,
                 "src":"MOPS_OFFICIAL_HIST_REVISED","sourceMode":"historical_bulk"}
            if not row["name"] or not re.search(r"[\u4e00-\u9fffA-Za-z]",row["name"]):continue
            if code in found and abs(found[code]["revenue"]-rev)>1e-6:
                raise RuntimeError("Conflicting monthly revenue "+code+" "+str((year,month,market,kind)))
            found[code]=row;local+=1
        if local:table_scans+=1
    return list(found.values()),table_scans
def parse_quarter_html(html,market,year,quarter):
    soup=BeautifulSoup(html,"html.parser")
    result={};eps_tables=0;headers_seen=[]
    for table in soup.select("table"):
        grid=[[c.get_text(" ",strip=True) for c in tr.find_all(["td","th"],recursive=False)] for tr in table.select("tr")]
        head_ind=None;ep_index=None
        for i,row in enumerate(grid[:9]):
            if not row:continue
            ix=next((j for j,col in enumerate(row) if ("基本每股盈餘" in col or ("每股盈餘" in col and "稀釋" not in col))),None)
            if ix is not None:
                ep_index=ix;head_ind=i;headers_seen.append(row[:20]);break
        if ep_index is None:continue
        eps_tables+=1
        for row in grid[head_ind+1:]:
            if len(row)<=ep_index:continue
            code_i=next((j for j in (0,1) if j<len(row) and valid_code(row[j])),None)
            if code_i is None:continue
            code=valid_code(row[code_i]);eps=numeric(row[ep_index])
            if eps is None or not -300<=eps<=300:continue
            result[code]={"code":code,"market":market,"year":year,"quarter":quarter,"epsYtd":eps,
                           "src":"MOPS_OFFICIAL_HIST_REVISED","sourceMode":"quarter_report_aggregate"}
    return list(result.values()),eps_tables,headers_seen[:2]
def month_safe_date(year,month):
    # Monthly MOPS deadline is generally the 10th of the next month;
    # safe-use on 16th, including weekend/holiday (first later session).
    y=year+(month==12);m=(month%12)+1
    return f"{y:04d}-{m:02d}-16"
def quarter_safe_date(year,q):
    # Proxy conservatively AFTER standard calendar deadlines for nonfinancial firms.
    if q==1:return f"{year}-05-22"
    if q==2:return f"{year}-08-22"
    if q==3:return f"{year}-11-22"
    return f"{year+1}-04-12"
def fetch_binary(sess,url,post=None,tries=4):
    err=""
    for i in range(tries):
        try:
            if post is None:r=sess.get(url,headers=HEADERS,timeout=35)
            else:r=sess.post(url,data=post,headers=HEADERS,timeout=55)
            r.raise_for_status()
            if len(r.content)<250:raise RuntimeError("Tiny MOPS response "+str(len(r.content)))
            return r.content
        except (requests.RequestException,RuntimeError) as ex:
            err=str(ex);time.sleep(min(2*(i+1),7))
    raise RuntimeError("OFFICIAL_SOURCE_UNAVAILABLE "+url+" "+err)
def collect_month(sess,year,month,market,kind):
    CACHE.mkdir(parents=True,exist_ok=True)
    path=CACHE/f"month_{year}{month:02d}_{market}_{kind}.html"
    url=f"https://mopsov.twse.com.tw/nas/t21/{market}/t21sc03_{year-1911}_{month}_{kind}.html"
    if path.exists():raw=path.read_bytes()
    else:
        raw=fetch_binary(sess,url);path.write_bytes(raw)
    rows,tables=parse_month_html(text_decode(raw,True),market,year,month,kind)
    # Empty foreign corp tables are valid only if the page at least has heading.
    if len(rows)<180:
        soup=BeautifulSoup(text_decode(raw,True),"html.parser")
        diagnostic=[]
        for tr in soup.select("tr"):
            cells=[z.get_text(" ",strip=True) for z in tr.find_all(["td","th"],recursive=False)]
            if len(cells)>=5:
                diagnostic.append({"n":len(cells),"head":cells[:6]})
            if len(diagnostic)>=18:break
        print("N_MONTH_DIAGNOSTIC",json.dumps({"year":year,"month":month,"market":market,
            "kind":kind,"tables":len(soup.select("table")),"rows":len(soup.select("tr")),
            "sample":diagnostic},ensure_ascii=False)[:5000],flush=True)
    if kind==0 and (len(rows)<180 or tables==0):
        raise RuntimeError(f"MOPS monthly bulk insufficient {year}-{month} {market} len={len(rows)} tables={tables} bytes={len(raw)}")
    if kind==1 and tables==0 and not any(x in text_decode(raw,True) for x in ("查無資料","無資料","未有資料","目前尚無")):raise RuntimeError(f"MOPS foreign monthly table unparseable {year}-{month} {market}")
    for r in rows:r["availableFrom"]=month_safe_date(year,month)
    return rows,{"url":url,"bytes":len(raw),"tables":tables,"rows":len(rows),"cached":path.exists()}
def collect_quarter(sess,year,quarter,market):
    CACHE.mkdir(parents=True,exist_ok=True)
    path=CACHE/f"eps_{year}Q{quarter}_{market}.html"
    url="https://mopsov.twse.com.tw/mops/web/ajax_t163sb04"
    form={"encodeURIComponent":"1","step":"1","firstin":"1","off":"1","TYPEK":market,
          "year":str(year-1911),"season":f"{quarter:02d}"}
    if path.exists():raw=path.read_bytes()
    else:
        raw=fetch_binary(sess,url,post=form);path.write_bytes(raw)
    rows,tables,heads=parse_quarter_html(text_decode(raw),market,year,quarter)
    if tables==0 or len(rows)<180:raise RuntimeError(
       f"MOPS EPS bulk insufficient {year}Q{quarter} {market} n={len(rows)} tables={tables} headers={str(heads)[:400]} bytes={len(raw)}")
    for r in rows:r["availableFrom"]=quarter_safe_date(year,quarter)
    return rows,{"url":url,"year":year,"quarter":quarter,"market":market,
         "bytes":len(raw),"tables":tables,"rows":len(rows),"headersSample":heads,"cached":path.exists()}
def run_probe():
    OUT.mkdir(parents=True,exist_ok=True)
    sess=requests.Session();tests=[];failures=[]
    for market in MARKETS:
        for typ in ("month","quarter"):
            try:
                if typ=="month":rows,proof=collect_month(sess,2024,5,market,0)
                else:rows,proof=collect_quarter(sess,2024,2,market)
                tests.append({"type":typ,"market":market,"n":len(rows),"first":rows[:2],"proof":proof})
                print("N_PROBE_OK",typ,market,len(rows),json.dumps(proof,ensure_ascii=False)[:450],flush=True)
            except Exception as ex:
                failures.append({"type":typ,"market":market,"error":str(ex)})
                print("N_PROBE_FAIL",typ,market,str(ex),flush=True)
    report={"version":"N_MOPS_HISTORICAL_PROBE","result":"pass" if not failures else "failed",
       "checks":tests,"failures":failures,"pointInTimePublicationDateKnown":False}
    (OUT/"source_probe.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    if failures:raise RuntimeError("N OFFICIAL HISTORICAL DATA SOURCE PROBE FAILED "+str(failures))
def main():
    import sys
    mode=sys.argv[1] if len(sys.argv)>1 else "probe"
    if mode=="probe":return run_probe()
    if mode!="collect":raise ValueError("expected probe or collect")
    OUT.mkdir(parents=True,exist_ok=True);CACHE.mkdir(parents=True,exist_ok=True)
    sess=requests.Session();months=[];eps=[];coverage=[];errors=[]
    # Every month is a reusable checkpoint; do not silently fabricate missing rows.
    for year,month in MONTHS:
        for market in MARKETS:
            for typ in (0,): # MOPS _0 historical page states 'includes domestic and foreign firms'; avoid unnecessary duplicate _1 request
                key=f"month_{year}{month:02d}_{market}_{typ}"
                try:
                    rows,proof=collect_month(sess,year,month,market,typ)
                    months.extend(rows);coverage.append({"id":key,**proof})
                except Exception as ex:
                    errors.append({"id":key,"error":str(ex)})
                    print("N_MONTH_FAILED",key,str(ex),flush=True)
        print("N_MONTH_DONE",year,month,"rows",len(months),"fails",len(errors),flush=True)
    for year,q in QUARTERS:
        for market in MARKETS:
            key=f"eps_{year}Q{q}_{market}"
            try:
                rows,proof=collect_quarter(sess,year,q,market)
                eps.extend(rows);coverage.append({"id":key,**proof})
            except Exception as ex:
                errors.append({"id":key,"error":str(ex)})
                print("N_EPS_FAILED",key,str(ex),flush=True)
        print("N_QUARTER_DONE",year,q,"rows",len(eps),"fails",len(errors),flush=True)
    report={"version":"N_MOPS_HISTORICAL_COVERAGE_V1","revenueRows":len(months),"epsRows":len(eps),
        "coverage":coverage,"failures":errors,"monthsRequested":len(MONTHS),
        "quartersRequested":len(QUARTERS),"availability":"conservative deadline based proxy",
        "vintage":"latest historically available MOPS aggregation, not point-in-time immutable disclosures"}
    (OUT/"fundamental_coverage.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    if errors or len(months)<20000 or len(eps)<5000:
        raise RuntimeError("N cannot backtest without complete official EPS and revenue history; missing "+str(len(errors))+" slices")
    for name,rows in (("monthly_revenue.json",months),("eps_ytd.json",eps)):
        (OUT/name).write_text(json.dumps(rows,ensure_ascii=False,separators=(",",":")),encoding="utf-8")
    print("N_FUNDAMENTALS_COLLECTED",len(months),len(eps),flush=True)
if __name__=="__main__":main()
