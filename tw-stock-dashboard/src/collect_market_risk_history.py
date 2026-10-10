"""Standalone, resumable historical TWSE market Risk Score collector.
Does NOT fetch stock-universe/G selections. Never fills missing official values.
Usage: PYTHONPATH=src python -u src/collect_market_risk_history.py --max-days 60
The public JSON archive and per-date failure audit are durable across GH runs.
"""
from __future__ import annotations
import argparse,csv,json,math,os,re,time
from collections import Counter
from datetime import datetime,timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
import pandas as pd,requests
from config import BENCHMARK,DATA_DIR
from yahoo_cache import update_symbol
from risk import build_historical

START="2023-10-09";END="2026-10-08"
OUT=DATA_DIR/"research"/"g_regime_3y"
CACHE=OUT/"risk_inputs.json"
UA={"User-Agent":"Mozilla/5.0 (historical TWSE research; date-locked)","Accept":"application/json"}
HOSTS=("https://www.twse.com.tw","https://wwwc.twse.com.tw")
class ArchiveError(RuntimeError):pass

def atomic_json(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_name(path.name+".tmp")
    with tmp.open("w",encoding="utf-8") as f:
        json.dump(data,f,ensure_ascii=False,indent=2,allow_nan=False)
        f.flush();os.fsync(f.fileno())
    tmp.replace(path)

def iso_from_text(text):
    if not text:return None
    s=str(text)
    m=re.search(r"(?<!\d)(\d{2,4})\s*[年/\-]\s*(\d{1,2})\s*[月/\-]\s*(\d{1,2})",s)
    if m:
        y,mo,dd=map(int,m.groups())
        if y<1911:y+=1911
        try:return f"{y:04d}-{mo:02d}-{dd:02d}" if 2000<=y<=2100 else None
        except ValueError:return None
    m=re.search(r"(?<!\d)(20\d{6}|1\d{6})(?!\d)",s)
    if m:
        t=m.group(1)
        if len(t)==8:return t[:4]+"-"+t[4:6]+"-"+t[6:8]
        return str(int(t[:3])+1911)+"-"+t[3:5]+"-"+t[5:7]
    return None

def verify_report_date(data,day):
    # Data date or original report title must explicitly equal the requested trading date.
    candidates=[data.get("date"),data.get("title"),data.get("subtitle")]
    candidates += [t.get("title") for t in (data.get("tables") or [])[:4]]
    dated=[d for d in (iso_from_text(x) for x in candidates) if d]
    if dated and dated[0]==day:return
    if dated:raise ArchiveError(f"DATE_MISMATCH requested={day} reported={dated[:3]}")
    raise ArchiveError(f"REPORT_DATE_UNVERIFIED requested={day}")

def fetch_json(session,path,day,params,timeout=16):
    problems=[]
    for host in HOSTS:
        for attempt in range(2):
            try:
                r=session.get(host+"/rwd/zh/"+path,params={"response":"json",**params},headers=UA,timeout=timeout)
                if r.status_code in (429,500,502,503,504):raise ArchiveError(f"HTTP_{r.status_code}")
                r.raise_for_status()
                j=r.json()
                if j.get("stat")!="OK":raise ArchiveError("TWSE_STAT_"+str(j.get("stat"))[:70])
                verify_report_date(j,day)
                return j,host+"/rwd/zh/"+path
            except (requests.RequestException,ValueError,ArchiveError) as e:
                problems.append(type(e).__name__+":"+str(e)[:135])
                # Data/format problems cannot be fixed by repeating the same URL.
                if isinstance(e,ArchiveError) and not str(e).startswith("HTTP_"):break
                if attempt==0:time.sleep(1.2)
    raise ArchiveError("; ".join(problems[-4:]))

def parse_breadth(data):
    for tab in data.get("tables") or []:
        if "漲跌證券數合計" not in str(tab.get("title") or ""):continue
        fields=[str(x).strip() for x in tab.get("fields") or []]
        if "股票" not in fields:continue
        col=fields.index("股票");up=down=None
        for row in tab.get("data") or []:
            if len(row)<=col:continue
            label=str(row[0]).strip();value=str(row[col]).split("(",1)[0].replace(",","").strip()
            try:n=int(value)
            except ValueError:continue
            if label.startswith("上漲"):up=n
            elif label.startswith("下跌"):down=n
        if up is not None and down is not None and up+down>=400:return up,down
    raise ArchiveError("BREADTH_TABLE_OR_STOCK_COLUMN_MISSING")

def parse_foreign(data):
    tables=[data]+list(data.get("tables") or [])
    for tab in tables:
        for row in tab.get("data") or []:
            if len(row)<4:continue
            label=str(row[0]).strip()
            if "外資及陸資" not in label or label.startswith("外資自營商"):continue
            value=str(row[-1]).replace(",","").replace("+","").strip()
            if not re.fullmatch(r"-?\d+(?:\.\d+)?",value):continue
            amount=float(value)/100_000_000
            if math.isfinite(amount) and -5000<amount<5000:return round(amount,8)
    raise ArchiveError("FOREIGN_NET_ROW_MISSING")

def fetch_breadth(session,day,timeout=16):
    errors=[]
    # ALL keeps the official aggregate table; ALLBUT0999 is a validated backup.
    for typ in ("ALL","ALLBUT0999"):
        try:
            data,source=fetch_json(session,"afterTrading/MI_INDEX",day,{"date":day.replace("-",""),"type":typ},timeout)
            up,down=parse_breadth(data)
            return {"up":up,"down":down,"breadthSource":source+"?type="+typ}
        except Exception as e:errors.append(typ+":"+str(e)[:240])
    raise ArchiveError(" | ".join(errors))

def fetch_foreign(session,day,timeout=16):
    data,source=fetch_json(session,"fund/BFI82U",day,{"dayDate":day.replace("-",""),"type":"day"},timeout)
    return {"foreign":parse_foreign(data),"foreignSource":source}

def valid_saved(row):
    if not isinstance(row,dict):return False
    try:
        up=int(row["up"]);down=int(row["down"]);f=float(row["foreign"])
        return bool(row.get("ok")) and up>=0 and down>=0 and up+down>=500 and math.isfinite(f) and -5000<f<5000
    except (ValueError,TypeError,KeyError):return False

def update_day(session,day,row,timeout=16):
    z=dict(row or {});errors={}
    if not (isinstance(z.get("up"),int) and isinstance(z.get("down"),int) and z["up"]+z["down"]>=500):
        try:z.update(fetch_breadth(session,day,timeout))
        except Exception as e:errors["breadth"]=str(e)[:700]
    if not isinstance(z.get("foreign"),(int,float)) or not math.isfinite(z["foreign"]):
        try:z.update(fetch_foreign(session,day,timeout))
        except Exception as e:errors["foreign"]=str(e)[:700]
    # Incomplete records cannot pass a later rerun until BOTH components exist.
    z["ok"]=False;z["error"]=errors
    try:
        if int(z["up"])+int(z["down"])>=500 and math.isfinite(float(z["foreign"])):z["ok"]=True;z.pop("error",None)
    except (KeyError,ValueError,TypeError):pass
    z["checkedAt"]=datetime.now(ZoneInfo("Asia/Taipei")).isoformat()
    return z

def export(index,dates,cache,start,end):
    ix=index.sort_values("date").drop_duplicates("date").reset_index(drop=True)
    ix["date"]=ix.date.astype(str)
    pos={d:i for i,d in enumerate(ix.date)}
    ready=[];failures=[]
    for day in dates:
        z=cache.get(day) or {};i=pos[day]
        if not valid_saved(z):
            failures.append({"date":day,"missing":["breadth" if not isinstance(z.get("up"),int) or not isinstance(z.get("down"),int) else None,
               "foreign" if not isinstance(z.get("foreign"),(int,float)) else None],"error":z.get("error")})
            continue
        if i<25:failures.append({"date":day,"error":"INSUFFICIENT_INDEX_WARMUP"});continue
        try:
            result=build_historical(ix.iloc[:i+1],breadth_value=z["up"]/(z["up"]+z["down"])*100,foreign_value=z["foreign"])
            if not (0<=result["score"]<=100):raise ValueError("Invalid Risk Score")
            result.update({"up":z["up"],"down":z["down"],"breadthSource":z.get("breadthSource","cached_official"),
               "foreignSource":z.get("foreignSource","cached_official")})
            ready.append(result)
        except Exception as e:failures.append({"date":day,"error":"RISK_SCORE:"+str(e)[:200]})
    coverage={"period":{"start":start,"end":end},"tradingDays":len(dates),"officialValidDays":sum(valid_saved(cache.get(d)) for d in dates),
      "riskScoredDays":len(ready),"missingDays":len(dates)-len(ready),"coveragePct":round(len(ready)/max(1,len(dates))*100,3),
      "complete":len(ready)==len(dates),"generatedAt":datetime.now(ZoneInfo("Asia/Taipei")).isoformat(),
      "calendar":"Yahoo ^TWII close sessions; index warmup precedes requested start",
      "sources":{"breadth":"TWSE MI_INDEX official daily stock advances/declines","foreign":"TWSE BFI82U official date-pinned foreign net","index":"Yahoo ^TWII daily OHLCV"},
      "warning":"Incomplete dates have no score. Do not use this dataset as a fully validated three-year backtest until complete."}
    atomic_json(OUT/"market_risk_daily.json",ready)
    atomic_json(OUT/"risk_errors.json",failures)
    atomic_json(OUT/"coverage.json",coverage)
    if ready:
        with (OUT/"market_risk_daily.csv").open("w",encoding="utf-8-sig",newline="") as fp:
            writer=csv.DictWriter(fp,fieldnames=list(ready[0]),extrasaction="ignore");writer.writeheader();writer.writerows(ready)
    print("COVERAGE",json.dumps(coverage,ensure_ascii=False),flush=True)
    print("ERROR_SAMPLE",json.dumps(failures[:3],ensure_ascii=False)[:1600],flush=True)
    return coverage

def main(args):
    if args.end>datetime.now(ZoneInfo("Asia/Taipei")).date().isoformat():raise ValueError("Future data not allowed")
    OUT.mkdir(parents=True,exist_ok=True)
    begin=datetime.fromisoformat(args.start)-timedelta(days=110)
    end=datetime.fromisoformat(args.end)+timedelta(days=1)
    print("INDEX_ONLY",BENCHMARK,begin.date(),end.date(),flush=True)
    _,index,error=update_symbol(BENCHMARK,begin,end)
    if error or index is None or index.empty:raise RuntimeError("Index calendar not available: "+str(error))
    index=index.sort_values("date").drop_duplicates("date").reset_index(drop=True)
    dates=[d for d in index.date.astype(str) if args.start<=d<=args.end]
    if len(dates)<500 and not args.allow_short:raise RuntimeError(f"Unexpectedly short historical index calendar: {len(dates)}")
    cache=json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}
    todo=[d for d in dates if not valid_saved(cache.get(d))]
    attempted=0
    with requests.Session() as session:
        for day in todo[:args.max_days]:
            item=update_day(session,day,cache.get(day),timeout=args.timeout)
            cache[day]=item;attempted+=1
            # A date is the atomic checkpoint; GitHub workflow commits on failure.
            atomic_json(CACHE,cache)
            print(f"DAY {attempted}/{min(len(todo),args.max_days)} {day} {'OK' if item['ok'] else 'MISSING'} "
                  +json.dumps(item.get("error",{}),ensure_ascii=False)[:380],flush=True)
            if args.delay:time.sleep(args.delay)
    result=export(index,dates,cache,args.start,args.end)
    print(f"COLLECTOR_DONE attempted={attempted} validated={result['officialValidDays']}/{result['tradingDays']}",flush=True)
    # Partial progress is expected; coverage.json.complete is authoritative.
    return 0

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--start",default=START);p.add_argument("--end",default=END)
    p.add_argument("--max-days",type=int,default=60)
    p.add_argument("--timeout",type=int,default=16)
    p.add_argument("--delay",type=float,default=.8)
    p.add_argument("--allow-short",action="store_true")
    a=p.parse_args()
    if a.max_days<1:raise SystemExit("--max-days must be positive")
    raise SystemExit(main(a))
