#!/usr/bin/env python3
"""Official TWSE EOD credit-balance backfill, checkpointed for GitHub Actions.
No external packages; no trading orders; no Risk Score writes.
Use original TWSE summary ONLY for TWSE-listed market, not TWSE+TPEx.
Input trading days come from validated site's archive. Supports daily revisions.
"""
import argparse, json, pathlib, sys, time, random, urllib.request, urllib.parse
from datetime import date

ROOT=pathlib.Path(__file__).resolve().parents[1]
ARCHIVE=ROOT/"docs/data/research/g_regime_3y/market_risk_daily.json"
DELTA=ROOT/"docs/data/research/market_intelligence/history_delta.json"
TARGET=ROOT/"docs/data/research/margin_short_audit/official_twse_history.json"
STATUS=ROOT/"docs/data/research/margin_short_audit/fetch_status.json"
ENDPOINTS=[
 "https://www.twse.com.tw/rwd/zh/marginTrading/MI_MARGN",
 "https://www.twse.com.tw/exchangeReport/MI_MARGN",
]
def integer(value):
 v=str(value or "").replace(",","").replace(" ","").strip()
 if not v or not v.lstrip("-").isdigit():raise ValueError("TWSE invalid credit number")
 return int(v)
def parse_payload(payload,requested_date):
 if payload.get("stat")!="OK":raise ValueError("TWSE not OK: "+str(payload.get("stat"))[:100])
 stated=str(payload.get("date","")).strip()
 if stated and stated.replace("/","").replace("-","")!=requested_date.replace("-",""):
  raise ValueError("TWSE mismatched credit report date "+stated)
 candidates=[]
 for collection in ["creditList","data"]:
  c=payload.get(collection)
  if isinstance(c,list):candidates.extend([x for x in c if isinstance(x,list)])
 for t in payload.get("tables") or []:
  if isinstance(t,dict) and isinstance(t.get("data"),list):
   candidates.extend([x for x in t["data"] if isinstance(x,list) and x])
 found={}
 for row in candidates:
  name=str(row[0]).replace(" ","").replace("　","")
  try:
   nums=[integer(v) for v in row[1:6]]
   if len(nums)!=5:continue
  except ValueError:continue
  if "融資金額" in name and "仟元" in name:found["margin_amount"]=nums
  elif name.startswith("融資(") and "交易" in name:found["margin_lots"]=nums
  elif name.startswith("融券(") and "交易" in name:found["short_lots"]=nums
 if set(found)!={"margin_amount","margin_lots","short_lots"}:
  raise ValueError("Missing exact credit summary rows: "+",".join(sorted(found)))
 amount,margin,short=found["margin_amount"],found["margin_lots"],found["short_lots"]
 if not (0<amount[4]<10**12 and margin[4]>0 and 0<=short[4]<10**9):raise ValueError("Out-of-range TWSE credit balance")
 # TWSE summary credit columns: buys, sells, cash/stock repayments, previous, current.
 # New reports can revise 'previous' balance; use same report's previous/current.
 balance=amount[4]/100000
 change=(amount[4]-amount[3])/100000
 return {"date":requested_date,"margin_balance_100m_twd":round(balance,5),
  "margin_delta_100m_twd":round(change,5),"margin_lots":margin[4],
  "short_balance_lots":short[4],"short_delta_lots":short[4]-short[3],
  "short_margin_ratio_pct":round(short[4]/margin[4]*100,6),
  "margin_maintenance_pct":None,"origin":"twse_official_credit_summary",
  "knowledge_after":"EOD_TWSE_publication_after_market_close"}
def get_day(day,retry=3,wait=1.2):
 query=urllib.parse.urlencode({"date":day.replace("-",""),"response":"json","selectType":"MS"})
 errors=[]
 for endpoint in ENDPOINTS:
  url=endpoint+"?"+query
  for attempt in range(retry):
   try:
    req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0 (compatible; TWSE historical audit; public research)","Accept":"application/json"})
    with urllib.request.urlopen(req,timeout=22) as response:
     if response.status!=200:raise OSError("HTTP "+str(response.status))
     payload=json.load(response)
    entry=parse_payload(payload,day)
    entry["source_url"]=url
    return entry
   except Exception as exc:
    errors.append(type(exc).__name__+": "+str(exc)[:120])
    if attempt+1<retry:time.sleep(min(8,(attempt+1)*wait+random.random()))
 raise RuntimeError("; ".join(errors[-4:])[:390])
def load(path,default):
 if not path.exists():return default
 with open(path,encoding="utf-8") as f:return json.load(f)
def save(path,obj):
 path.parent.mkdir(parents=True,exist_ok=True)
 temp=path.with_suffix(path.suffix+".tmp")
 with open(temp,"w",encoding="utf-8") as f:json.dump(obj,f,ensure_ascii=False,indent=2);f.write("\n")
 temp.replace(path)
def run():
 ap=argparse.ArgumentParser(description=__doc__)
 ap.add_argument("--max-days",type=int,default=150,help="Maximum missing official sessions to request this run (cap 800)")
 ap.add_argument("--from-date",default="2023-10-11")
 ap.add_argument("--to-date",default="2026-10-13")
 ap.add_argument("--delay",type=float,default=1.2)
 args=ap.parse_args()
 if not (1<=args.max_days<=800) or args.delay<.75:ap.error("max-days 1..800; delay>=.75")
 archive=load(ARCHIVE,[])+load(DELTA,[])
 days=sorted(set(x["date"] for x in archive if isinstance(x,dict) and args.from_date<=str(x.get("date",""))<=args.to_date))
 if len(days)<200:raise SystemExit("No independently validated TWSE trading-day calendar; refusing calendar-date guesses")
 existing=load(TARGET,{"schema":"twse_margin_market_credit_v1","market":"TWSE_LISTED_ONLY","rows":[],"notes":"Official daily AFTER-CLOSE summaries; today and previous may be revised. Maintenance rate not included."})
 stored={x["date"]:x for x in existing.get("rows",[]) if isinstance(x,dict) and x.get("origin")=="twse_official_credit_summary"}
 failures=load(STATUS,{}).get("failed",{})
 todo=[x for x in days if x not in stored][:args.max_days]
 completed=0
 for i,day in enumerate(todo):
  try:
   got=get_day(day);stored[day]=got;failures.pop(day,None);completed+=1
  except Exception as e:
   failures[day]=str(e)[:390]
   print("FAILED",day,failures[day],file=sys.stderr)
  if (i+1)%20==0 or i==len(todo)-1:
   existing["rows"]=[stored[k] for k in sorted(stored)]
   save(TARGET,existing)
   save(STATUS,{"requestedPeriod":[args.from_date,args.to_date],"calendarSessions":len(days),"fetchedOfficial":len(stored),"remainingMissing":sum(d not in stored for d in days),"lastBatchAttempted":i+1,"lastBatchCompleted":completed,"failed":failures})
  if i<len(todo)-1:time.sleep(args.delay)
 print(json.dumps({"tradingDays":len(days),"officialRows":len(stored),"remaining":sum(d not in stored for d in days),"attempted":len(todo),"completed":completed},ensure_ascii=False))
if __name__=="__main__":run()
