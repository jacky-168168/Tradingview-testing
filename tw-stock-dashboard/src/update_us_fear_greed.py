#!/usr/bin/env python3
"""CNN Fear & Greed plus dated S&P500: display only, never a TW stock trading gate.
Source is CNN page's public, undocumented graphdata endpoint.
No interpolation, no made-up values, no API score advertised as real-time.
"""
from __future__ import annotations
import json,math,urllib.request
from datetime import datetime,timezone
from pathlib import Path

BASE=Path(__file__).resolve().parents[1]
SOURCE="https://production.dataviz.cnn.io/index/fearandgreed/graphdata/2022-01-01"
SPX=BASE/"docs/data/research/us_options/history.json"
OUT=BASE/"docs/data/research/us_fear_greed/history.json"
HEADERS={
    "Accept":"application/json, text/plain, */*",
    "Referer":"https://edition.cnn.com/markets/fear-and-greed",
    "Origin":"https://edition.cnn.com",
    "User-Agent":"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
}
COMPONENTS={
    "market_momentum_sp500":"市場動能",
    "stock_price_strength":"股價強弱",
    "stock_price_breadth":"市場廣度",
    "put_call_options":"Put／Call選擇權",
    "market_volatility_vix":"VIX波動",
    "safe_haven_demand":"避險需求",
    "junk_bond_demand":"高收益債需求",
}
def source_date(epoch):
    """CNN historical x is Unix milliseconds; daily US market date recorded in UTC."""
    return datetime.fromtimestamp(float(epoch)/1000,timezone.utc).date().isoformat()
def valid_score(v):
    if isinstance(v,bool):return None
    try:n=float(v)
    except (TypeError,ValueError):return None
    return round(n,3) if math.isfinite(n) and 0<=n<=100 else None
def cnn_series(doc):
    hist=doc.get("fear_and_greed_historical") if isinstance(doc,dict) else None
    if not isinstance(hist,dict) or not isinstance(hist.get("data"),list):
        raise ValueError("CNN fear_and_greed_historical.data missing")
    rows={}
    for x in hist["data"]:
        if not isinstance(x,dict):continue
        try:
            d=source_date(x["x"]);score=valid_score(x.get("y"))
            if score is not None and "2021-01-01"<=d<=datetime.now(timezone.utc).date().isoformat():
                rows[d]=score
        except (KeyError,OverflowError,TypeError,ValueError):continue
    if len(rows)<150:raise ValueError("CNN Fear & Greed insufficient historical points")
    return rows
def to_archive(cnn,spx):
    points=cnn_series(cnn)
    if not isinstance(spx,dict) or spx.get("columns")!=["date","spx","dixPct","gex"]:
        raise ValueError("Existing S&P500 historical data missing or schema changed")
    us={}
    for r in spx.get("rows",[]):
        if not isinstance(r,list) or len(r)!=4:continue
        try:
            d=str(r[0]);v=float(r[1])
            if math.isfinite(v) and v>100:us[d]=round(v,3)
        except (TypeError,ValueError):continue
    if len(us)<500:raise ValueError("S&P500 archive too short")
    common=sorted(set(us)&set(points))
    if len(common)<150:raise ValueError("CNN and S&P500 overlap too short")
    cnn_latest=max(points)
    spx_latest=max(us)
    if abs((datetime.fromisoformat(spx_latest)-datetime.fromisoformat(cnn_latest)).days)>10:
        raise ValueError("CNN and SPX latest dates materially inconsistent")
    last=common[-1]
    if (datetime.fromisoformat(spx_latest)-datetime.fromisoformat(last)).days>8:
        raise ValueError("Joined data stale against S&P500")
    components={}
    for key,title in COMPONENTS.items():
        raw=cnn.get(key) or {}
        score=valid_score(raw.get("score")) if isinstance(raw,dict) else None
        if score is not None:components[key]={"label":title,"score":score}
    # Latest headline is separate from the confirmed end-of-day, aligned history.
    headline=cnn.get("fear_and_greed") or {}
    src_ts=str(headline.get("timestamp") or "") if isinstance(headline,dict) else ""
    rows=[[d,points[d],us[d]] for d in common]
    return {
        "version":"US_CNN_FEAR_GREED_SPX_V1","source":SOURCE,
        "sourceLink":"https://edition.cnn.com/markets/fear-and-greed",
        "spxSource":"SqueezeMetrics DIX.csv / indexed S&P 500 settlement (display only)",
        "updatedAt":datetime.now(timezone.utc).isoformat(),
        "cnnTimestamp":src_ts,"cnnHistoricalLast":cnn_latest,"spxLast":spx_latest,
        "asOf":last,"columns":["date","fearGreed","spx"],"rows":rows,
        "components":components,
        "disclaimer":"Confirmed matched US market daily observations; no same-day forward fill, no TA stock Risk Score integration.",
    }
def fetch_cnn():
    req=urllib.request.Request(SOURCE,headers=HEADERS,method="GET")
    with urllib.request.urlopen(req,timeout=40) as res:
        if res.status!=200:raise RuntimeError("CNN HTTP "+str(res.status))
        raw=res.read(8_000_001)
    if len(raw)>8_000_000:raise ValueError("CNN response unexpectedly large")
    try:return json.loads(raw)
    except json.JSONDecodeError as exc:raise ValueError("CNN response not JSON") from exc
def main():
    cnn=fetch_cnn()
    spx=json.loads(SPX.read_text(encoding="utf-8"))
    result=to_archive(cnn,spx)
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(result,ensure_ascii=False,separators=(",",":"))+"\n",encoding="utf-8")
    print("US CNN fear&greed verified history",len(result["rows"]),"sessions",
          "asOf",result["asOf"],"CNN",result["cnnHistoricalLast"],"SPX",result["spxLast"])
if __name__=="__main__":main()
