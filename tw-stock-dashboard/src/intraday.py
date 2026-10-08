from __future__ import annotations
import json,time
from concurrent.futures import ThreadPoolExecutor,as_completed
from datetime import datetime
from zoneinfo import ZoneInfo
import requests
from config import LATEST_JSON
from yahoo_cache import to_symbol
UA={"User-Agent":"Mozilla/5.0 tw-stock-dashboard/4.0"}

def quote(symbol):
    url=f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
    try:
        r=requests.get(url,params={"range":"1d","interval":"1m","includePrePost":"false"},headers=UA,timeout=15);r.raise_for_status()
        z=((r.json().get("chart") or {}).get("result") or [None])[0]
        if not z:return symbol,None
        meta=z.get("meta") or {};px=meta.get("regularMarketPrice")
        if px is None:
            q=((z.get("indicators") or {}).get("quote") or [{}])[0].get("close") or []
            px=next((x for x in reversed(q) if x is not None),None)
        return symbol,float(px) if px is not None else None
    except Exception:return symbol,None

def main():
    if not LATEST_JSON.exists():
        from pipeline import main as full_main
        full_main()
    d=json.loads(LATEST_JSON.read_text(encoding="utf-8"))
    if not any((d.get("models") or {}).get(m) for m in ["A","D","F","F2"]):
        from pipeline import main as full_main
        full_main();d=json.loads(LATEST_JSON.read_text(encoding="utf-8"))
    if not d.get("gSelection"):
        from pipeline import main as full_main
        full_main();d=json.loads(LATEST_JSON.read_text(encoding="utf-8"))
    rows=[]
    for model in ["A","D","F","F2","G"]:rows.extend((d.get("models") or {}).get(model) or [])
    uniq={(x.get("code"),x.get("market")) for x in rows if x.get("code") and x.get("market")}
    prices={}
    with ThreadPoolExecutor(max_workers=8) as ex:
        fs=[ex.submit(quote,to_symbol(c,m)) for c,m in uniq]
        for f in as_completed(fs):
            s,p=f.result()
            if p is not None:prices[s]=p
    for x in rows:
        p=prices.get(to_symbol(x["code"],x["market"]));close=float(x.get("close") or 0)
        if p is not None:
            x["currentPrice"]=round(p,2);x["currentPct"]=round((p/close-1)*100,2) if close else None
        else:x["currentPrice"]=None;x["currentPct"]=None
    d["intradayUpdatedAt"]=datetime.now(ZoneInfo("Asia/Taipei")).isoformat(timespec="seconds");d["intradayQuoteOk"]=len(prices);d["intradayUniverse"]=len(uniq);d["updateMode"]="intraday-fast"
    LATEST_JSON.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({"intradayUpdatedAt":d["intradayUpdatedAt"],"quoteOk":len(prices),"symbols":len(uniq)},ensure_ascii=False))
if __name__=="__main__":main()
