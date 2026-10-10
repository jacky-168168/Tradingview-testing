"""Backfill official historical TWSE/TPEx daily P/B. Never substitute current P/B for past dates.
Example: python src/collect_pb_history.py --start 2026-10-01 --end 2026-10-08
Source: TWSE afterTrading/BWIBBU_d; TPEx peratio_analysis/pera_result.php.
Large archives are gzipped to avoid exceeding GitHub's single-file size limit.
"""
import argparse,gzip,json,re,time
from datetime import date,timedelta
from pathlib import Path
import requests
from config import DATA_DIR

OUT=DATA_DIR/"research"/"quality"/"pb_daily.json.gz"
UA={"User-Agent":"Mozilla/5.0 (compatible; ResearchArchive/1.0)"}
def n(v):
    try:return float(str(v).strip().replace(",",""))
    except (ValueError,TypeError):return None
def code(x):
    s=str(x).strip()
    return s if re.fullmatch(r"\d{4,6}",s) else None
def twse(session,dt):
    url="https://www.twse.com.tw/rwd/zh/afterTrading/BWIBBU_d"
    j=session.get(url,params={"date":dt.strftime("%Y%m%d"),"selectType":"ALL","response":"json"},headers=UA,timeout=40)
    j.raise_for_status();obj=j.json()
    if "data" not in obj:return []
    names=[str(x).replace(" ","") for x in obj.get("fields",[])]
    ix=next((i for i,x in enumerate(names) if "證券代號" in x or "股票代號" in x),None)
    pb=next((i for i,x in enumerate(names) if "股價淨值比" in x),None)
    if ix is None or pb is None:raise ValueError("TWSE field mapping changed: "+str(names))
    out=[]
    for row in obj["data"]:
        if len(row)<=max(ix,pb):continue
        c=code(re.sub("<[^>]*>","",str(row[ix])));v=n(row[pb])
        if c and v is not None and .03<=v<=200:out.append({"market":"sii","code":c,"date":dt.isoformat(),"pb":v,"source":"TWSE_BWIBBU_d"})
    return out
def tpex(session,dt):
    url="https://www.tpex.org.tw/web/stock/aftertrading/peratio_analysis/pera_result.php"
    roc=dt.year-1911
    r=session.get(url,params={"l":"zh-tw","o":"json","d":f"{roc}/{dt.month:02d}/{dt.day:02d}"},headers=UA,timeout=40)
    r.raise_for_status();j=r.json();raw=j.get("aaData",[])
    if not isinstance(raw,list):raise ValueError("TPEx schema changed")
    out=[]
    for row in raw:
        if not isinstance(row,list) or len(row)<7:continue
        c=code(row[0]);v=n(row[6])
        if c and v is not None and .03<=v<=200:out.append({"market":"otc","code":c,"date":dt.isoformat(),"pb":v,"source":"TPEX_peQryDate"})
    return out
def load():
    if not OUT.exists():return {}
    with gzip.open(OUT,"rt",encoding="utf8") as f:items=json.load(f)
    return {(x["market"],x["code"],x["date"]):x for x in items}
def run(start,end,sleep_sec=1):
    if end>date.today():raise ValueError("cannot archive future dates")
    known=load();sess=requests.Session();done=0;fail=[]
    if start>end:raise ValueError("start > end")
    known_days={(k[0],k[2]) for k in known}
    market_file=DATA_DIR/"research"/"g_regime_3y"/"market_risk_daily.json"
    try:expected={x["date"] for x in json.loads(market_file.read_text(encoding="utf8"))}
    except (OSError,ValueError,KeyError,TypeError):expected=set()
    d=start
    while d<=end:
        if d.weekday()<5:
            if all((m,d.isoformat()) in known_days for m in ("sii","otc")):
                d+=timedelta(days=1);continue
            try:
                a=twse(sess,d);b=tpex(sess,d)
                if not a and not b:
                    if d.isoformat() in expected:raise RuntimeError("official sources empty on verified trading date")
                    print("HOLIDAY_OR_NO_REPORT",d,flush=True)
                elif len(a)<150 or len(b)<100:
                    raise RuntimeError(f"insufficient stocks TWSE={len(a)} TPEx={len(b)}")
                else:
                    for x in a+b:known[(x["market"],x["code"],x["date"])]=x
                    known_days.add(("sii",d.isoformat()));known_days.add(("otc",d.isoformat()))
                    done+=1
                    if done%10==0:save(known)
                print("PB_DAY",d,len(a),len(b),flush=True)
            except (requests.RequestException,ValueError,RuntimeError) as ex:
                fail.append((d.isoformat(),str(ex)));print("PB_FAILED",d,ex,flush=True)
            time.sleep(max(.2,sleep_sec))
        d+=timedelta(days=1)
    save(known)
    if fail:raise RuntimeError(f"PB archive incomplete {len(fail)} days; first={fail[:3]}")
    if not known:raise RuntimeError("PB historical endpoint returned no verifiable observations")
    print("PB_ARCHIVE_SUCCESS",len(known),"rows",flush=True)
def save(records):
    OUT.parent.mkdir(parents=True,exist_ok=True)
    items=[records[k] for k in sorted(records)]
    tmp=OUT.with_suffix(".tmp")
    with gzip.open(tmp,"wt",encoding="utf8",compresslevel=7) as f:json.dump(items,f,ensure_ascii=False,separators=(",",":"))
    tmp.replace(OUT)
if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--start",required=True);p.add_argument("--end",required=True)
    args=p.parse_args();run(date.fromisoformat(args.start),date.fromisoformat(args.end))
