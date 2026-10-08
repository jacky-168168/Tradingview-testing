from __future__ import annotations
import json,math,sys
from datetime import datetime,timedelta
from zoneinfo import ZoneInfo
import pandas as pd
from config import DATA_DIR
from institution import fetch_many
from yahoo_cache import update_many,to_symbol

def classify(x5,accel):
    if x5>=0 and accel>=0:return "漲潮"
    if x5>=0 and accel<0:return "輪動"
    if x5<0 and accel>=0:return "觀望"
    return "退潮"

def _num(v,default=0.0):
    try:
        x=float(v);return x if math.isfinite(x) else default
    except:return default

def _history_index(df):
    if df is None or df.empty:return {}
    out={}
    for _,r in df.iterrows():
        d=str(r.get("date") or "")
        c=_num(r.get("close"),0)
        if d and c>0:out[d]=c
    return out

def build(universe,histories,index_df,market_date,playback_days=20):
    idx=index_df.copy().sort_values("date");dates=[str(x) for x in idx["date"].astype(str) if str(x)<=market_date]
    need=max(40,playback_days+20);dates=dates[-need:]
    if len(dates)<20:raise RuntimeError("bubble chart requires at least 20 trading days")
    listed=[x for x in universe if x.get("market")=="上市" and str(x.get("code","")).isdigit() and len(str(x.get("code","")))==4]
    missing=[(x["code"],x["market"]) for x in listed if to_symbol(x["code"],x["market"]) not in histories]
    extra={}
    if missing:
        s=datetime.fromisoformat(dates[0])-timedelta(days=7);e=datetime.fromisoformat(dates[-1])+timedelta(days=2)
        extra,_=update_many(missing,s,e)
    hmap={}
    for s in listed:
        sym=to_symbol(s["code"],s["market"]);df=histories.get(sym)
        if df is None or df.empty:df=extra.get(sym)
        hmap[s["code"]]=_history_index(df)
    inst,inst_errors=fetch_many(dates)
    day_sector={d:{} for d in dates};day_stock={d:{} for d in dates};names={x["code"]:x.get("name",x["code"]) for x in listed};industries={x["code"]:x.get("industry") or "未分類" for x in listed}
    for d in dates:
        iday=inst.get(d,{})
        for s in listed:
            code=s["code"];ii=iday.get(f"上市_{code}")
            if not ii:continue
            close=hmap.get(code,{}).get(d)
            if not close:continue
            shares=_num(ii.get("foreign"))+_num(ii.get("trust"))+_num(ii.get("dealer"))
            amount=shares*close/100_000_000
            sector=industries.get(code,"未分類")
            if sector=="未分類":continue
            day_sector[d][sector]=day_sector[d].get(sector,0.0)+amount
            day_stock[d][code]=amount
    sectors=sorted({s for x in day_sector.values() for s in x})
    frames=[]
    start_i=max(19,len(dates)-playback_days)
    for i in range(start_i,len(dates)):
        d=dates[i];w20=dates[i-19:i+1];w5=dates[i-4:i+1]
        points=[]
        for sector in sectors:
            v20=[day_sector[x].get(sector,0.0) for x in w20];v5=[day_sector[x].get(sector,0.0) for x in w5]
            x5=sum(v5);avg5=x5/len(v5);avg20=sum(v20)/len(v20);accel=avg5-avg20;scale=sum(abs(x) for x in v20);today=day_sector[d].get(sector,0.0)
            if scale<0.05:continue
            members=[s for s in listed if (s.get("industry") or "未分類")==sector]
            contrib=[]
            for s in members:
                code=s["code"];v=sum(day_stock[x].get(code,0.0) for x in w5)
                if abs(v)>=0.01:contrib.append({"code":code,"name":names.get(code,code),"flow5":round(v,2)})
            contrib.sort(key=lambda z:abs(z["flow5"]),reverse=True)
            points.append({"sector":sector,"x5":round(x5,2),"accel":round(accel,2),"scale20":round(scale,2),"today":round(today,2),"state":classify(x5,accel),"memberCount":len(members),"leaders":contrib[:5]})
        points.sort(key=lambda z:z["scale20"],reverse=True)
        for n,p in enumerate(points,1):p["sizeRank"]=n;p["hot"]=n<=12
        counts={k:sum(p["state"]==k for p in points) for k in ["漲潮","輪動","觀望","退潮"]}
        frames.append({"date":d,"counts":counts,"points":points})
    out={"version":"BUBBLE-V1","generatedAt":datetime.now(ZoneInfo("Asia/Taipei")).isoformat(timespec="seconds"),"dataDate":frames[-1]["date"] if frames else market_date,
         "source":"TWSE T86 三大法人買賣超 × 收盤價估算；目前泡泡聚合以上市股票官方產業分類為主",
         "method":{"x":"近5交易日三大法人估算淨買賣超金額（億元）","y":"近5日平均淨流量 − 近20日平均淨流量（億元/日）","size":"近20日每日法人淨流量絕對值合計（億元）","quadrants":{"漲潮":"流入且加速","輪動":"流入但放緩","觀望":"流出但放緩","退潮":"流出且加速"}},
         "institutionErrors":inst_errors,"frames":frames}
    p=DATA_DIR/"bubbles";p.mkdir(parents=True,exist_ok=True);(p/"latest.json").write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding="utf-8")
    return {"dataDate":out["dataDate"],"frames":len(frames),"sectors":len(frames[-1]["points"]) if frames else 0,"institutionErrors":len(inst_errors)}

if __name__=="__main__":
    from pipeline import load_universe
    from yahoo_cache import update_symbol
    from config import BENCHMARK
    now=datetime.now(ZoneInfo("Asia/Taipei")).replace(tzinfo=None);_,idx,e=update_symbol(BENCHMARK,now-timedelta(days=120),now)
    if e:raise RuntimeError(e)
    u=load_universe();hist,_=update_many([(x["code"],x["market"]) for x in u if x.get("market")=="上市"],now-timedelta(days=120),now)
    print(json.dumps(build(u,hist,idx,str(idx.iloc[-1]["date"])),ensure_ascii=False))
