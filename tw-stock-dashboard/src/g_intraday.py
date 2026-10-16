"""Provisional all-market G scan during TWSE/TPEx continuous trading.
Keep official EOD models.G and dated gPocketBaseline immutable. The live scan
uses completed historical daily bars + only today's dated MIS OHLCV quotes.
MIS cumulative volume is in lots (1000 shares); Yahoo history is in shares.
Never publish a partial cross-section or silently fill missing quotes.
"""
from __future__ import annotations
import json,sys,time,threading,os
from datetime import datetime,time as clock,timedelta
from concurrent.futures import ThreadPoolExecutor,as_completed
from pathlib import Path
from zoneinfo import ZoneInfo
import pandas as pd,requests
from config import DATA_DIR,UNIVERSE_CACHE,HISTORY_DIR,LATEST_JSON,MIN_LISTED_UNIVERSE,MIN_OTC_UNIVERSE
from yahoo_cache import to_symbol,load_cached
from g_live import select as select_g,prior_pockets
from industry_chain import enrich as enrich_chain
from g_intraday_archive import archive_intraday_payload

TZ=ZoneInfo("Asia/Taipei")
BASE="https://mis.twse.com.tw/stock/"
QUOTE=BASE+"api/getStockInfo.jsp"
OUTPUT=DATA_DIR/"g_intraday"/"latest.json"
STATUS=DATA_DIR/"g_intraday"/"status.json"
THREAD=threading.local()
UA={"User-Agent":"Mozilla/5.0 (compatible; TaiwanQuantResearch/1.0)","Referer":BASE,"Accept":"application/json"}
def number(value):
    try:
        x=float(str(value).replace(",","").strip())
        return x if pd.notna(x) else None
    except (TypeError,ValueError):return None

def top_book_price(v):
    return number(str(v or "").split("_")[0])

def parse_mis(payload,date,now):
    """Return checked same-day quotes keyed by (listed/OTC, 4-digit code)."""
    result={}
    for row in payload.get("msgArray",[]):
        code=str(row.get("c") or "").strip()
        market={"tse":"上市","otc":"上櫃"}.get(row.get("ex"))
        if not(market and len(code)==4 and code.isdigit()):continue
        if str(row.get("d") or "")!=date.replace("-",""):continue
        tm=str(row.get("t") or "")
        if tm and len(tm)>=5 and tm[:5]<"09:00":continue
        stamp=number(row.get("tlong"))
        if stamp:
            at=datetime.fromtimestamp(stamp/1000,TZ)
            if at.date()!=now.date() or at>now+timedelta(minutes=10):continue
        last_trade=number(row.get("z"));previous_trade=number(row.get("pz"))
        high=number(row.get("h"));low=number(row.get("l"))
        op=number(row.get("o"));lots=number(row.get("v"));prev=number(row.get("y"))
        if prev is None or prev<=0:continue
        # MIS also returns same-day quotes for stocks which have not traded yet.
        # An official reference close + NO OHLC/volume means flat zero turnover,
        # NOT a trade at yesterday's price. Such names belong in percentile peers,
        # but can NEVER pass the live G candidate filter.
        untraded=(lots is None or lots==0) and all(v is None or v<=0 for v in (op,high,low))
        if untraded:
            result[(market,code)]={"price":prev,"open":prev,"high":prev,"low":prev,
                                   "volume":0,"previousClose":prev,"time":tm,"priceSource":"no-trade-prevclose"}
            continue
        if any(x is None or x<=0 for x in (high,low,op,lots)):continue
        if not low<=op<=high:continue
        # The latest/previous matched trade can lag a moving intraday OHLC
        # snapshot. Try each only when it fits TODAY'S observed range; then
        # fall through to bounded order-book inference instead of discarding
        # the entire stock despite a valid live quote.
        price=None;source="unknown"
        for candidate,label in ((last_trade,"last-trade"),(previous_trade,"previous-trade")):
            if candidate is not None and low<=candidate<=high:
                price=candidate;source=label;break
        if price is None:
            bid=top_book_price(row.get("b"));ask=top_book_price(row.get("a"))
            if bid and ask and bid>0 and ask>=bid and (ask-bid)/((ask+bid)/2)<=.012:
                price=round((bid+ask)/2,4);source="bid-ask-midpoint"
            elif bid and bid>0 and abs(bid-high)/high<.001:
                price=bid;source="one-sided-high-bid"
            elif ask and ask>0 and abs(ask-low)/low<.001:
                price=ask;source="one-sided-low-ask"
        if price is None or price<=0 or not low<=price<=high:continue
        if abs(price/prev-1)>.12:continue
        result[(market,code)]={"price":price,"open":op,"high":high,"low":low,
                               "volume":round(lots*1000),"previousClose":prev,"time":tm,"priceSource":source}
    return result

def session():
    x=getattr(THREAD,"session",None)
    if x is None:
        x=requests.Session();x.headers.update(UA)
        try:x.get(BASE+"fibest.jsp",timeout=12)
        except requests.RequestException:pass
        THREAD.session=x
    return x

def query_batch(batch,today,now):
    channels=["tse_" + code + ".tw" if market=="上市" else "otc_" + code + ".tw" for market,code in batch]
    merged={};errors=[]
    # MIS intermittently drops items from a successful HTTP 200. A partial
    # payload must not be mistaken for a complete exchange response.
    for attempt in range(3):
        try:
            r=session().get(QUOTE,params={"ex_ch":"|".join(channels),"json":1,"delay":0,"_":int(time.time()*1000)},
                            timeout=22);r.raise_for_status()
            payload=r.json();parsed=parse_mis(payload,today,now)
            merged.update(parsed)
            if len(merged)>=len(batch)*.82:break
            if attempt==2 or len(merged)<len(batch)*.4:
                raw=payload.get("msgArray") or []
                sample=[{k:x.get(k) for k in ("c","ex","d","t","z","pz","a","b","o","h","l","v","y")} for x in raw[:3]]
                print("MIS_PARTIAL_COVERAGE",str(batch[0]),"requested",len(batch),"returned",len(raw),"accepted",len(merged),"sample",json.dumps(sample,ensure_ascii=False),flush=True)
        except (requests.RequestException,ValueError,KeyError) as e:
            errors.append(repr(e))
        if attempt<2:time.sleep(.4*(attempt+1))
    if errors and len(merged)<len(batch)*.4:
        print("MIS_BATCH_ERRORS",str(batch[0]),len(batch),errors,file=sys.stderr,flush=True)
    return merged

def fetch_quotes(universe,today,now):
    items=list(dict.fromkeys((row["market"],row["code"]) for row in universe if row.get("market") in ("上市","上櫃")))
    chunks=[items[i:i+45] for i in range(0,len(items),45)]
    out={}
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures={pool.submit(query_batch,b,today,now):b for b in chunks}
        for future in as_completed(futures):out.update(future.result())
    need={m:sum(x[0]==m for x in items) for m in ("上市","上櫃")}
    got={m:sum(x[0]==m for x in out) for m in need}
    coverage={m:round(got[m]/need[m],4) if need[m] else 0 for m in need}
    no_trade={m:sum(market==m and q["priceSource"]=="no-trade-prevclose" for (market,_),q in out.items()) for m in need}
    traded={m:got[m]-no_trade[m] for m in need}
    detail="上市 "+str(got["上市"])+"/"+str(need["上市"])+"（當日未成交 "+str(no_trade["上市"])+"）、上櫃 "+str(got["上櫃"])+"/"+str(need["上櫃"])+"（當日未成交 "+str(no_trade["上櫃"])+"）"
    # Still require broad SAME-DAY MIS coverage from BOTH exchanges: a missing
    # or stale quote is never filled from Yahoo's previous close.
    if len(out)<1000 or len(out)/max(1,len(items))<.65 or min(coverage.values())<.60:
        raise RuntimeError("全市場同日有效即時報價不足，不發布偏樣本G排行；"+detail)
    return out,{"total":len(items),"valid":len(out),"traded":sum(traded.values()),"noTrade":sum(no_trade.values()),
                "exchange":{m:{"valid":got[m],"total":need[m],"coverage":coverage[m],"traded":traded[m],"noTrade":no_trade[m]} for m in need}}

def provisional_breadth(quotes):
    """Intraday SAME-DAY trade-only market breadth. Never count reference-close
    no-trade peers or bid/ask proxy prices as actual advancing issues."""
    markets={"上市":{"up":0,"down":0,"flat":0},"上櫃":{"up":0,"down":0,"flat":0}}
    for (market,code),q in quotes.items():
        if market not in markets or q.get("priceSource") not in ("last-trade","previous-trade"):continue
        price=number(q.get("price"));prev=number(q.get("previousClose"))
        if price is None or prev is None or prev<=0 or q.get("volume",0)<=0:continue
        change=price/prev-1
        direction="up" if change>0.000001 else "down" if change< -0.000001 else "flat"
        markets[market][direction]+=1
    total={field:sum(m[field] for m in markets.values()) for field in ("up","down","flat")}
    for m in [total,*markets.values()]:
        n=sum(m.values());m["sample"]=n;m["upPct"]=round(m["up"]/n*100,1) if n else None
    return {"quality":"verified-trade-only","source":"TWSE MIS today trade prices vs prior official reference; proxy and untraded excluded",
            "total":total,"exchange":markets}

def fetch_quotes_with_retries(universe,today,now,attempts=3,pause=50):
    """Retry failed whole-market coverage during the opening auction.
    Keep both-market safeguards; never use old-day quotes as replacements.
    """
    for n in range(attempts):
        try:return fetch_quotes(universe,today,datetime.now(TZ))
        except RuntimeError as exc:
            if "全市場同日有效即時報價不足" not in str(exc):raise
            remaining=(datetime.now(TZ).replace(hour=13,minute=42,second=0)-datetime.now(TZ)).total_seconds()
            if n==attempts-1 or remaining<pause+15:raise
            print("G_QUOTE_COVERAGE_RETRY",n+1,attempts,str(exc),"wait",pause,flush=True)
            time.sleep(pause)
    raise RuntimeError("全市場報價重試未完成")

def make_intraday_frame(history,quote,today):
    if history is None or history.empty:return None
    h=history.loc[history.date.astype(str)<today].copy().sort_values("date").drop_duplicates("date",keep="last").tail(130)
    if len(h)<59:return None
    last=str(h.date.iloc[-1])
    if (datetime.fromisoformat(today).date()-datetime.fromisoformat(last).date()).days>12:return None
    lastclose=number(h.close.iloc[-1])
    if not lastclose or abs(lastclose/quote["previousClose"]-1)>.03:return None
    row={"date":today,"open":quote["open"],"high":quote["high"],"low":quote["low"],
         "close":quote["price"],"volume":quote["volume"],"adjclose":quote["price"]}
    return pd.concat([h,pd.DataFrame([row])],ignore_index=True)

def write_status(now,status,details=""):
    STATUS.parent.mkdir(parents=True,exist_ok=True)
    STATUS.write_text(json.dumps({"asOfDate":now.date().isoformat(),"checkedAt":now.isoformat(timespec="seconds"),
                                  "status":status,"message":details},ensure_ascii=False,indent=2),encoding="utf-8")

def main():
    now=datetime.now(TZ);today=now.date().isoformat()
    if now.weekday()>=5 or not clock(9,0)<=now.time()<clock(13,45):
        write_status(now,"closed","僅於臺灣交易日09:00–13:45產生盤中G暫估");return
    try:
        session_slot=now.replace(minute=30 if now.minute>=30 else 0,second=0,microsecond=0).strftime("%H:%M")
        # Multiple independent schedulers can fire in one half-hour. Scheduled
        # recoveries must not create duplicate archived rankings for the same slot.
        # Manual dispatches remain free to recompute on demand.
        if os.environ.get("GITHUB_EVENT_NAME")=="schedule" and OUTPUT.exists():
            try:
                last=json.loads(OUTPUT.read_text(encoding="utf-8"))
                last_time=datetime.fromisoformat(str(last.get("publishedAt","")))
                old_slot=str(last.get("sessionSlot") or last_time.replace(minute=30 if last_time.minute>=30 else 0,second=0,microsecond=0).strftime("%H:%M"))
                if last.get("quality")=="intraday-provisional-allmarket" and last.get("asOfDate")==today and old_slot==session_slot and now>=last_time and now-last_time<timedelta(minutes=30):
                    print("INTRADAY_G_ALREADY_CURRENT",today,session_slot,last["publishedAt"],flush=True)
                    return
            except (OSError,ValueError,TypeError,KeyError):
                pass
        if not(LATEST_JSON.exists() and UNIVERSE_CACHE.exists()):raise RuntimeError("缺少正式收盤快照或完整上市櫃公司母檔")
        base=json.loads(LATEST_JSON.read_text(encoding="utf-8"))
        source=str(base.get("dataDate") or "")
        if not source or source>=today:raise RuntimeError("無可用的前一個已完成交易日，請使用正式G；不以盤中資料覆蓋正式歷史")
        universe=json.loads(UNIVERSE_CACHE.read_text(encoding="utf-8"))
        nlisted=sum(x.get("market")=="上市" for x in universe)
        notc=sum(x.get("market")=="上櫃" for x in universe)
        if nlisted<MIN_LISTED_UNIVERSE or notc<MIN_OTC_UNIVERSE:raise RuntimeError("上市櫃公司母檔覆蓋不足")
        benchmark=load_cached("^TWII")
        if benchmark.empty:raise RuntimeError("找不到已完成交易日的大盤交易日曆")
        calendar=sorted(set(str(x) for x in benchmark.date if str(x)<today and str(x).startswith(today[:4])))
        if not calendar or calendar[-1]!=source:raise RuntimeError("大盤已完成交易日與正式快照日期不吻合")
        quotes,coverage=fetch_quotes_with_retries(universe,today,now)
        quote_captured_at=datetime.now(TZ).isoformat(timespec="seconds")
        history={};rejected=0
        for stock in universe:
            key=(stock["market"],stock["code"]);q=quotes.get(key)
            if q is None:continue
            sym=to_symbol(stock["code"],stock["market"])
            frame=make_intraday_frame(load_cached(sym),q,today)
            if frame is not None:history[sym]=frame
            else:rejected+=1
        # Percentile ranking requires most of BOTH markets to have valid 60-day bars.
        historical=min(len(history)/len(universe),len(history)/max(1,len(quotes)))
        if len(history)<1000 or historical<.60:raise RuntimeError("具完整歷史K線的當日股票樣本不足："+str(len(history))+"/"+str(len(universe)))
        calendar.append(today)
        pockets,found=prior_pockets(DATA_DIR,calendar,today)
        rows,snapshot,meta=select_g(universe,history,calendar,today,previous_pockets=pockets,market_ret20=number(base.get("benchmarkRet20")) or 0,intraday=True)
        enrich_chain(rows)
        for row in rows:
            row["sarText"]="未確認（正式日K）"
            row["foreignToday"]=None
            row["trustToday"]=None
            row["currentPrice"]=row["close"]
            row["intradayPriceSource"]=quotes.get((row["market"],row["code"]),{}).get("priceSource","unknown")
            q=quotes.get((row["market"],row["code"]))
            row["currentPct"]=round((row["close"]/q["previousClose"]-1)*100,2) if q else None
            row["signal"]="🟠 盤中暫估｜"+str(row.get("signal") or "")
        meta["pocketSnapshotsFound"]=found
        meta["pocketWarmup"]=found<min(10,len(calendar)-1)
        meta["isProvisional"]=True
        meta["note"]="盤中依未完成日K、當日累積成交量與當日MIS報價重選。當日未成交股票以核對過的昨收價及0成交量納入排名母體，不得入選G；無成交價但有買賣揭示者以經價差篩選的中間價估算。非正式G日K訊號，法人及SAR均未確認。"
        payload={"asOfDate":today,"publishedAt":datetime.now(TZ).isoformat(timespec="seconds"),"scanStartedAt":now.isoformat(timespec="seconds"),"quoteCapturedAt":quote_captured_at,"sessionSlot":session_slot,
                 "sourceCloseDate":source,"quality":"intraday-provisional-allmarket",
                 "quoteSource":"TWSE MIS same-day listed+OTC; trade price if available, otherwise validated order-book midpoint proxy; cumulative lots × 1000 shares",
                 "coverage":coverage,"marketBreadth":provisional_breadth(quotes),"quotePriceSources":{kind:sum(q.get("priceSource")==kind for q in quotes.values()) for kind in ("last-trade","previous-trade","bid-ask-midpoint","one-sided-high-bid","one-sided-low-ask","no-trade-prevclose")},"historicalBarCoverage":len(history),"historyRejected":rejected,
                 "market20Reference":"previous completed cash-market return (not live index)",
                 "rows":rows,"selection":meta}
        OUTPUT.parent.mkdir(parents=True,exist_ok=True)
        OUTPUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
        archived=archive_intraday_payload(DATA_DIR,payload)
        print("INTRADAY_G_ARCHIVED",archived,flush=True)
        write_status(now,"ok","G盤中重新篩選 "+str(len(rows))+" 檔；有效全市場報價 "+str(coverage["valid"])+"/"+str(coverage["total"]))
        print(json.dumps({"intradayG":"ok","dataDate":today,"sourceCloseDate":source,
                          "candidates":meta["doubleBreakCandidates"],"top20":len(rows),
                          "coverage":coverage},ensure_ascii=False),flush=True)
    except Exception as exc:
        write_status(now,"unavailable",str(exc))
        print("INTRADAY_G_UNAVAILABLE",type(exc).__name__,str(exc),file=sys.stderr,flush=True)
        # Allow ordinary A/D/F/G previous-close refresh to finish; never make up a live G list.
if __name__=="__main__":main()
