from __future__ import annotations
import json,re,time
from concurrent.futures import ThreadPoolExecutor,as_completed
from datetime import datetime
from pathlib import Path
import pandas as pd,requests
from config import CACHE_DIR,REQUEST_TIMEOUT

DIR=CACHE_DIR/"sar_official";UA={"User-Agent":"Mozilla/5.0 tw-stock-dashboard/5.0","Accept":"application/json,text/plain,*/*","Accept-Language":"zh-TW,zh;q=0.9"}

def _num(v):
    try:return float(str(v).replace(",","").replace("--","").strip())
    except:return 0.0

def _date(s):
    s=str(s or "").strip().replace(".","/")
    m=re.match(r"^(\d{2,4})/(\d{1,2})/(\d{1,2})$",s)
    if not m:return ""
    y=int(m.group(1));y=y+1911 if y<1911 else y
    return f"{y:04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"

def _months_back(date_str,count=4):
    d=datetime.strptime(date_str,"%Y-%m-%d");out=[]
    y,m=d.year,d.month
    for i in range(count):
        z=m-i;yy=y
        while z<=0:z+=12;yy-=1
        out.append(f"{yy:04d}-{z:02d}-01")
    return list(reversed(out))

def _parse_twse(j):
    out=[]
    for r in (j or {}).get("data") or []:
        if len(r)<7:continue
        d=_date(r[0]);o=_num(r[3]);h=_num(r[4]);l=_num(r[5]);c=_num(r[6]);v=_num(r[1])
        if d and h>0 and l>0 and c>0:out.append({"date":d,"open":o,"high":h,"low":l,"close":c,"volume":v})
    return out

def _field(fields,names):
    compact=[re.sub(r"\s+","",str(x or "")) for x in fields]
    for i,x in enumerate(compact):
        if any(n in x for n in names):return i
    return -1

def _parse_tpex(j):
    rows=[];fields=[]
    for t in (j or {}).get("tables") or []:
        data=t.get("data") or [];f=t.get("fields") or [];c=[re.sub(r"\s+","",str(x or "")) for x in f]
        if data and any("日期" in x for x in c) and any("收盤" in x for x in c):rows=data;fields=f;break
    if not rows:rows=(j or {}).get("aaData") or []
    di=_field(fields,["日期"]);oi=_field(fields,["開盤"]);hi=_field(fields,["最高"]);li=_field(fields,["最低"]);ci=_field(fields,["收盤"]);vi=_field(fields,["成交股數","成交千股","成交張數"])
    out=[]
    for r in rows:
        try:
            d=_date(r[di if di>=0 else 0]);o=_num(r[oi if oi>=0 else 3]);h=_num(r[hi if hi>=0 else 4]);l=_num(r[li if li>=0 else 5]);c=_num(r[ci if ci>=0 else 6]);v=_num(r[vi if vi>=0 else 1])
            if d and h>0 and l>0 and c>0:out.append({"date":d,"open":o,"high":h,"low":l,"close":c,"volume":v})
        except:pass
    return out

def _month(stock,month,retries=3):
    if stock["market"]=="上櫃":
        url="https://www.tpex.org.tw/www/zh-tw/afterTrading/tradingStock";params={"code":stock["code"],"date":month.replace("-","/"),"response":"json"};parser=_parse_tpex
    else:
        url="https://www.twse.com.tw/rwd/zh/afterTrading/STOCK_DAY";params={"date":month[:7].replace("-","")+"01","stockNo":stock["code"],"response":"json"};parser=_parse_twse
    err=None
    for n in range(retries):
        try:
            r=requests.get(url,params=params,headers=UA,timeout=REQUEST_TIMEOUT);r.raise_for_status();return parser(r.json())
        except Exception as e:err=e;time.sleep(1+n)
    return []

def _cache_path(stock):
    DIR.mkdir(parents=True,exist_ok=True);return DIR/f'{stock["market"]}_{stock["code"]}.json'

def official_history(stock,market_date,months=4):
    p=_cache_path(stock)
    if p.exists():
        try:
            a=json.loads(p.read_text(encoding="utf-8"))
            if isinstance(a,list) and len(a)>=30 and str(a[-1].get("date",""))>=market_date:return a[-100:]
        except:pass
    bars=[]
    for m in _months_back(market_date,months):bars.extend(_month(stock,m))
    merged={x["date"]:x for x in bars if x.get("date") and x["date"]<=market_date}
    out=[merged[k] for k in sorted(merged)][-100:]
    if len(out)>=30:p.write_text(json.dumps(out,ensure_ascii=False),encoding="utf-8")
    return out

def parabolic_sar(df,start=.02,inc=.02,max_af=.2):
    h=df.reset_index(drop=True)
    if len(h)<10:return None
    n=len(h);sar=[None]*n;bull=[None]*n;result=maxmin=af=None;below=False
    for i in range(n):
        first=False
        if i==1:
            if float(h.loc[i,"close"])>float(h.loc[i-1,"close"]):below=True;maxmin=float(h.loc[i,"high"]);result=float(h.loc[i-1,"low"])
            else:below=False;maxmin=float(h.loc[i,"low"]);result=float(h.loc[i-1,"high"])
            first=True;af=start
        if i==0 or result is None:continue
        result=result+af*(maxmin-result)
        if below:
            if result>float(h.loc[i,"low"]):first=True;below=False;result=max(float(h.loc[i,"high"]),maxmin);maxmin=float(h.loc[i,"low"]);af=start
        else:
            if result<float(h.loc[i,"high"]):first=True;below=True;result=min(float(h.loc[i,"low"]),maxmin);maxmin=float(h.loc[i,"high"]);af=start
        if not first:
            if below and float(h.loc[i,"high"])>maxmin:maxmin=float(h.loc[i,"high"]);af=min(af+inc,max_af)
            elif (not below) and float(h.loc[i,"low"])<maxmin:maxmin=float(h.loc[i,"low"]);af=min(af+inc,max_af)
        if below:
            result=min(result,float(h.loc[i-1,"low"]))
            if i>1:result=min(result,float(h.loc[i-2,"low"]))
        else:
            result=max(result,float(h.loc[i-1,"high"]))
            if i>1:result=max(result,float(h.loc[i-2,"high"]))
        sar[i]=result;bull[i]=result<float(h.loc[i,"close"])
    ci=n-2
    if ci<1 or sar[ci] is None:return None
    flip=-1
    for i in range(ci,1,-1):
        if bull[i]!=bull[i-1]:flip=i;break
    trend=ci-flip+1 if flip>=0 else 1
    return {"value":round(float(sar[ci]),4),"bullish":bool(bull[ci]),"trendBars":max(1,int(trend)),"confirmedDate":str(h.loc[ci,"date"])}

def apply(rows,market_date,candidate_n=50):
    cand=rows[:max(0,candidate_n)];hist={}
    with ThreadPoolExecutor(max_workers=10) as ex:
        fut={ex.submit(official_history,{"code":r["code"],"market":r["market"]},market_date):r for r in cand}
        for q in as_completed(fut):
            r=fut[q]
            try:hist[(r["market"],r["code"])]=q.result()
            except:hist[(r["market"],r["code"])]=[]
    for r in cand:
        bars=hist.get((r["market"],r["code"])) or [];x=parabolic_sar(pd.DataFrame(bars)) if len(bars)>=30 else None
        r["sarBonus"]=0;r["sarText"]="SAR資料不足"
        if x:
            t=x["trendBars"];r["sarText"]=("多 " if x["bullish"] else "空 ")+f"{t} 根K"
            if x["bullish"]:r["sarBonus"]=5 if t==1 else 4 if t==2 else 3 if t==3 else 2 if t==4 else 1 if t in (5,6) else 0
    return rows
