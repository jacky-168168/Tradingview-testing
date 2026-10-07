from __future__ import annotations
import html,json,re,requests
from datetime import datetime
from config import CACHE_DIR
UA={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/154 Safari/537.36","Accept":"application/json,text/plain,*/*","Accept-Language":"zh-TW,zh;q=0.9"}

def institution_flow(inst,names):
    buy=[];sell=[]
    for key,x in (inst or {}).items():
        f=float(x.get("foreign",0) or 0);t=float(x.get("trust",0) or 0);tot=f+t;code=key.split("_")[-1];it={"code":code,"name":names.get(key,code),"lots":round(tot/1000),"foreignLots":round(f/1000),"trustLots":round(t/1000)}
        if f>0 and t>0:buy.append(it)
        elif f<0 and t<0:sell.append(it)
    buy.sort(key=lambda x:-x["lots"]);sell.sort(key=lambda x:x["lots"]);return {"buy":buy[:5],"sell":sell[:5]}

def stockisland_topic_heat(market_date=""):
    try:
        r=requests.get("https://www.twstockisland.com/api/concept/gains?periods=1,10,20",headers={**UA,"Referer":"https://www.twstockisland.com/dashboard"},timeout=25);r.raise_for_status();j=r.json();cats=j.get("categories") or [];stocks=j.get("stocks") or {}
        if len(cats)<8:return []
        out=[];now=datetime.now().isoformat(timespec="seconds")
        for c in cats:
            name=str(c.get("category") or "").strip();arr=stocks.get(name) or [];vals=[]
            for s in arr:
                try:
                    v=float((s.get("gains") or {}).get("1"))
                    if v==v:vals.append(v)
                except:pass
            if not vals:
                try:vals=[float((c.get("gains") or {}).get("1"))]
                except:pass
            if name and vals:out.append({"theme":name,"avgRet":round(sum(vals)/len(vals),2),"ret":round(sum(vals)/len(vals),2),"count":len(vals),"source":"股島盤後","updated":now,"dataDate":str(j.get("latest_date") or market_date)})
        return sorted(out,key=lambda x:-x["avgRet"])[:8]
    except Exception:return []

def danny_topic_heat():
    try:
        r=requests.get("https://www.dannyquant.com/industry-map",headers={"User-Agent":UA["User-Agent"],"Accept-Language":"zh-TW,zh;q=0.9"},timeout=25);r.raise_for_status();s=r.text;a=s.find("題材熱度")
        if a<0:return []
        b=s.find("今日頭條新聞",a);b=b if b>=0 else s.find("產業熱力圖",a);part=s[a:(b if b>=0 else min(len(s),a+80000))];out=[];seen=set()
        for m in re.finditer(r'<a\b[^>]*href=["\'][^"\']*/industry-map/concepts/[^"\']+["\'][^>]*>([\s\S]*?)</a>',part,re.I):
            text=html.unescape(re.sub(r"<[^>]+>"," ",m.group(1)));text=re.sub(r"\s+"," ",text).strip();pm=re.search(r"([+-]?\d+(?:\.\d+)?)\s*%",text)
            if not pm:continue
            name=text.replace(pm.group(0),"").strip("▲▼ "); 
            if not name or name in seen:continue
            seen.add(name);v=float(pm.group(1));out.append({"theme":name,"avgRet":v,"ret":v,"count":0,"source":"DannyQuant備援","updated":datetime.now().isoformat(timespec="seconds")})
        return sorted(out,key=lambda x:-x["avgRet"])[:8]
    except Exception:return []

def topic_heat(market_date=""):
    cache=CACHE_DIR/"topic_heat.json"
    x=stockisland_topic_heat(market_date)
    if not x:x=danny_topic_heat()
    if x:
        cache.parent.mkdir(parents=True,exist_ok=True)
        cache.write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding="utf-8")
        return x
    if cache.exists():
        try:
            old=json.loads(cache.read_text(encoding="utf-8"))
            if isinstance(old,list) and old:return old
        except:pass
    return []
