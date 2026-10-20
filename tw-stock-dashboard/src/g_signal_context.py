"""Date-locked research context recorded together with each real G intraday snapshot.

The official Risk Score is previous COMPLETE close, not a score recomputed from
intraday prices. Intraday peers use validated same-day trade prices only.
No independent entry/exit events or forward returns are fabricated.
"""
from __future__ import annotations
import math
from statistics import mean

TRADE={"last-trade","previous-trade"}

def finite(value):
    if isinstance(value,bool):return None
    try:
        n=float(value)
        return n if math.isfinite(n) else None
    except (TypeError,ValueError):return None

def peer_changes(quotes):
    grouped={"上市":[],"上櫃":[]}
    for key,q in (quotes or {}).items():
        if not isinstance(key,tuple) or len(key)!=2 or key[0] not in grouped:continue
        if not isinstance(q,dict) or q.get("priceSource") not in TRADE:continue
        price=finite(q.get("price"));base=finite(q.get("previousClose"));volume=finite(q.get("volume"))
        if None in (price,base,volume) or min(price,base,volume)<=0:continue
        ret=(price/base-1)*100
        if abs(ret)>12:continue
        grouped[key[0]].append(ret)
    return {market:{"sample":len(vals),"equalWeightMeanPct":round(mean(vals),3) if len(vals)>=30 else None,
                    "meaning":"有效當日實際成交價個股的簡單平均漲跌幅，非加權或櫃買指數"}
            for market,vals in grouped.items()}

def build_context(asof,published_at,source_close_date,base,quotes,breadth,rows,coverage):
    previous=(base or {}).get("risk") or {}
    prev_date=str(previous.get("date") or "")
    prev_score=finite(previous.get("score"))
    verified_close=prev_date==source_close_date and bool(source_close_date and source_close_date<asof)
    score=round(prev_score,1) if verified_close and prev_score is not None and 0<=prev_score<=100 else None
    previous_close={"date":source_close_date,"score":score,"state":str(previous.get("state") or "") if score is not None else None,
                    "available":score is not None,
                    "note":"這是上一個完整交易日的正式風險分數，不是訊號當下的即時大盤分數"}
    peers=peer_changes(quotes)
    exchange=(breadth or {}).get("exchange") or {}
    snapshots={}
    for market in ("上市","上櫃"):
        e=exchange.get(market) or {}
        sample=e.get("sample")
        sample=sample if isinstance(sample,int) and not isinstance(sample,bool) else 0
        pct=finite(e.get("upPct"))
        snapshots[market]={"tradedSample":sample,"upPct":pct if sample>=30 and pct is not None else None,
                            "peerMeanPct":peers[market]["equalWeightMeanPct"],
                            "peerSample":peers[market]["sample"]}
    total=(breadth or {}).get("total") or {}
    total_sample=total.get("sample") if isinstance(total.get("sample"),int) else 0
    up_pct=finite(total.get("upPct")) if total_sample>=1000 else None
    band=("弱勢" if up_pct<35 else "偏弱" if up_pct<50 else "偏強" if up_pct<65 else "強勢") if up_pct is not None else "資料不足"
    top=[]
    for rank,row in enumerate(rows[:20],1):
        market=row.get("market");code=str(row.get("code") or "");q=(quotes or {}).get((market,code)) or {}
        pct=finite(row.get("currentPct"))
        verified=q.get("priceSource") in TRADE
        benchmark=peers.get(market,{}).get("equalWeightMeanPct")
        rel=round(pct-benchmark,3) if verified and pct is not None and benchmark is not None else None
        top.append({"rank":rank,"code":code,"name":str(row.get("name") or code),"market":market,
                    "intradayPct":round(pct,3) if verified and pct is not None else None,
                    "relativeToEqualWeightPeersPct":rel,
                    "priceQuality":"verified-trade" if verified else "price-proxy-not-comparable"})
    return {"version":"g-intraday-market-context-v1","asOfDate":asof,"publishedAt":published_at,
            "sourceCloseDate":source_close_date,"previousCloseRisk":previous_close,
            "market":{"source":"TWSE MIS 當日已驗證實際成交價","breadth":snapshots,
                      "allMarketTradedSample":total_sample,"allMarketUpPct":up_pct,
                      "breadthBand":band,
                      "coverageValid":(coverage or {}).get("valid"),
                      "note":"上漲家數占比使用實際成交價樣本；上一日正式風險分數與本輪盤中廣度不同時點，不合成新的 Risk Score"},
            "top20":top,
            "researchOnly":True,"note":"每輪只是時間快照，同日股票重複入榜不代表多個獨立買進訊號；未計算未來報酬、勝率或即時指數相對強弱"}
