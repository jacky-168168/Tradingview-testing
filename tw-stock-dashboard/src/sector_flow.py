from __future__ import annotations
import json,time
from datetime import datetime
from zoneinfo import ZoneInfo
import pandas as pd,requests
from config import CACHE_DIR,REQUEST_TIMEOUT
from yahoo_cache import to_symbol

DIR=CACHE_DIR/"sector_flow";UA={"User-Agent":"Mozilla/5.0 tw-stock-dashboard/8.0","Accept":"application/json"}

def _num(v):
    try:return float(str(v).replace(",","").replace("--","0").strip() or 0)
    except:return 0.0

def _norm(s):return str(s or "").replace(" ","").strip()

def _idx(fields,exact=(),contains=()):
    f=[_norm(x) for x in fields]
    for x in exact:
        x=_norm(x)
        if x in f:return f.index(x)
    for i,x in enumerate(f):
        if any(_norm(k) in x for k in contains):return i
    return -1

def classify(flow5,accel):
    if flow5>=0 and accel>=0:return "漲潮"
    if flow5>=0 and accel<0:return "輪動"
    if flow5<0 and accel>=0:return "觀望"
    return "退潮"

def _read_cache(path):
    if not path.exists():return None
    try:
        x=json.loads(path.read_text(encoding="utf-8"))
        return x if isinstance(x,dict) and x else None
    except:return None

def _write_cache(path,x):
    path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(x,ensure_ascii=False),encoding="utf-8")

def _parse_twse(j):
    out={}
    if not j or not isinstance(j.get("data"),list):return out
    f=j.get("fields") or []
    ci=_idx(f,exact=("證券代號",));fi=_idx(f,exact=("外陸資買賣超股數(不含外資自營商)","外資及陸資買賣超股數(不含外資自營商)"),contains=("外陸資買賣超股數",));fsi=_idx(f,exact=("外資自營商買賣超股數",));ti=_idx(f,exact=("投信買賣超股數",));di=_idx(f,exact=("自營商買賣超股數",))
    dself=_idx(f,exact=("自營商買賣超股數(自行買賣)",));dhedge=_idx(f,exact=("自營商買賣超股數(避險)",))
    for row in j["data"]:
        if ci<0 or ci>=len(row):continue
        code=str(row[ci]).strip()
        if len(code)!=4 or not code.isdigit():continue
        foreign=(_num(row[fi]) if fi>=0 else 0)+(_num(row[fsi]) if fsi>=0 else 0);trust=_num(row[ti]) if ti>=0 else 0
        dealer=_num(row[di]) if di>=0 else (_num(row[dself]) if dself>=0 else 0)+(_num(row[dhedge]) if dhedge>=0 else 0)
        out[f"上市_{code}"]={"foreign":foreign,"trust":trust,"dealer":dealer,"total":foreign+trust+dealer}
    return out

def _roc_date(date):
    d=datetime.fromisoformat(date).date();return f"{d.year-1911:03d}/{d.month:02d}/{d.day:02d}"

def _parse_tpex(j):
    out={};tables=(j or {}).get("tables") or []
    if not tables:return out
    rows=tables[0].get("data") or []
    for r in rows:
        if not r or len(r)<24:continue
        code=str(r[0]).strip().strip("=").strip('"')
        if len(code)!=4 or not code.isdigit():continue
        foreign=_num(r[10]);trust=_num(r[13]);dealer=_num(r[22])
        out[f"上櫃_{code}"]={"foreign":foreign,"trust":trust,"dealer":dealer,"total":foreign+trust+dealer}
    return out

def fetch_twse(date,retries=3):
    p=DIR/"twse"/f"{date}.json";old=_read_cache(p)
    if old:return old,None
    url="https://www.twse.com.tw/rwd/zh/fund/T86";params={"date":date.replace("-",""),"selectType":"ALLBUT0999","response":"json"};err=None
    for n in range(retries):
        try:
            r=requests.get(url,params=params,headers=UA,timeout=REQUEST_TIMEOUT);r.raise_for_status();x=_parse_twse(r.json())
            if x:_write_cache(p,x);return x,None
        except Exception as e:err=e
        time.sleep(.8+n*.5)
    return {},str(err or "empty TWSE T86")

def fetch_tpex(date,retries=3):
    p=DIR/"tpex"/f"{date}.json";old=_read_cache(p)
    if old:return old,None
    url="https://www.tpex.org.tw/www/zh-tw/insti/dailyTrade";params={"type":"Daily","sect":"EW","date":_roc_date(date),"id":"","response":"json"};err=None
    for n in range(retries):
        try:
            r=requests.get(url,params=params,headers=UA,timeout=REQUEST_TIMEOUT);r.raise_for_status();j=r.json();tables=j.get("tables") or []
            rd=str((tables[0].get("date") if tables else "") or j.get("date") or "").strip()
            if rd and rd!=_roc_date(date):raise RuntimeError(f"TPEX wrong date {rd}")
            x=_parse_tpex(j)
            if x:_write_cache(p,x);return x,None
        except Exception as e:err=e
        time.sleep(.8+n*.5)
    return {},str(err or "empty TPEX institution")

def _close_map(histories,dates):
    wanted=set(dates);out={}
    for sym,df in (histories or {}).items():
        if df is None or df.empty:continue
        q=df[df["date"].astype(str).isin(wanted)]
        if q.empty:continue
        out[sym]={str(r["date"]):_num(r["close"]) for _,r in q.iterrows()}
    return out

def build(universe,histories,index_df,market_date,lookback=20):
    dates=[str(x) for x in index_df[index_df["date"].astype(str)<=market_date]["date"].astype(str).tolist()][-lookback:]
    if not dates:return {"dataDate":market_date,"sectors":[],"error":"no trading dates"}
    inst={};tw_ok=tp_ok=0;errors=[]
    for d in dates:
        tw,e1=fetch_twse(d);tp,e2=fetch_tpex(d)
        if tw:tw_ok+=1
        if tp:tp_ok+=1
        if e1:errors.append(f"TWSE {d}: {e1}")
        if e2:errors.append(f"TPEX {d}: {e2}")
        inst[d]={**tw,**tp}
        if e1 or e2:time.sleep(.15)
    close=_close_map(histories,dates);meta={f'{x["market"]}_{x["code"]}':x for x in universe};daily={};stock5={}
    last5=set(dates[-5:])
    for d in dates:
        for key,x in inst.get(d,{}).items():
            s=meta.get(key)
            if not s:continue
            sector=str(s.get("industry") or "未分類").strip() or "未分類"
            if sector=="未分類":continue
            px=close.get(to_symbol(s["code"],s["market"]),{}).get(d,0)
            if px<=0:continue
            amount=_num(x.get("total"))*px/100_000_000
            daily.setdefault(sector,{z:0.0 for z in dates})[d]+=amount
            if d in last5:
                q=stock5.setdefault(sector,{}).setdefault(key,{"code":s["code"],"name":s["name"],"amount5":0.0})
                q["amount5"]+=amount
    sectors=[]
    for sector,m in daily.items():
        vals=[float(m.get(d,0)) for d in dates];n=len(vals);d1=vals[-1];d5=sum(vals[-5:]);d20=sum(vals);base5=(d20/n*5) if n else 0;accel=d5-base5;gross20=sum(abs(v) for v in vals)
        leaders=sorted(stock5.get(sector,{}).values(),key=lambda z:-abs(z["amount5"]))[:3]
        sectors.append({"sector":sector,"state":classify(d5,accel),"flow1":round(d1,2),"flow5":round(d5,2),"flow20":round(d20,2),"accel5":round(accel,2),"gross20":round(gross20,2),"stocks":len(stock5.get(sector,{})),"leaders":[{**x,"amount5":round(x["amount5"],2)} for x in leaders]})
    sectors.sort(key=lambda x:-x["flow5"]);counts={k:sum(x["state"]==k for x in sectors) for k in ("漲潮","輪動","觀望","退潮")}
    return {"dataDate":dates[-1],"generatedAt":datetime.now(ZoneInfo("Asia/Taipei")).isoformat(timespec="seconds"),"source":"TWSE T86 + TPEx 三大法人公開資料；淨流入金額以買賣超股數×當日收盤價估算","formula":{"x":"近5交易日三大法人估算淨流入(億)","y":"近5日淨流入－近20日平均5日淨流入(億)","size":"近20日每日板塊淨流入絕對值合計(億)"},"coverage":{"tradingDays":len(dates),"twseDays":tw_ok,"tpexDays":tp_ok,"errors":errors[-8:]},"counts":counts,"sectors":sectors}
