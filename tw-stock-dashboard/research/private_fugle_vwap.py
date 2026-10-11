"""Personal-use Fugle stock VWAP/average-price probe for 0050 + frozen G Top3.

Run locally with FUGLE_API_KEY; NEVER put keys, raw quotes or derived live data in
public GitHub Pages. The public GitHub Actions job reports validation counts only.
Stock intraday candle 'average' is session-cumulative. Do not reuse futopt candle
average (per-bar VWAP) as a cumulative VWAP.
"""
from __future__ import annotations
import argparse,json,math,os,re,time
from datetime import datetime,time as dtime,timedelta,timezone
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.error import HTTPError,URLError
from zoneinfo import ZoneInfo
TZ=ZoneInfo("Asia/Taipei")
API="https://api.fugle.tw/marketdata/v1.0/stock/intraday"
ROOT=Path(__file__).resolve().parents[1]/"docs"/"data"
SCHEMA="PRIVATE_FUGLE_0050_G3_VWAP_V1"
MAX_TRADE_AGE_SECONDS=300
def timestamp(value):
    """Fugle exchange lastTrade.time is epoch microseconds; support ms/s too."""
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or value<=0:return None
    seconds=value/(1e6 if value>=1e14 else 1e3 if value>=1e11 else 1)
    try:return datetime.fromtimestamp(seconds,TZ)
    except (ValueError,OverflowError,OSError):return None
def numeric(value):
    if isinstance(value,bool):return None
    try:
        result=float(value)
        return result if math.isfinite(result) else None
    except (ValueError,TypeError):return None
def sym_list(latest):
    """Freeze picks from confirmed, completed D-close G ranking, NOT intraday reranking."""
    date=str(latest.get("dataDate") or "")
    g=latest.get("gSelection") or {}
    if not re.fullmatch(r"20\d{2}-\d{2}-\d{2}",date) or g.get("dataDate")!=date or g.get("variant")!="G_DOUBLE_PERSIST":
        raise ValueError("G selection not same official close date")
    rows=(latest.get("models") or {}).get("G") or []
    picked=["0050"]
    for r in rows:
        code=str(r.get("code") or "")
        if re.fullmatch(r"\d{4,6}",code) and code not in picked:
            picked.append(code)
            if len(picked)==4:break
    if len(picked)!=4:raise ValueError("Need G Top3 to compare with 0050")
    return picked,date
def quote_analysis(quote,symbol,now):
    """Reject trial-only, old, future, mismatched date, malformed prices."""
    trading_date=now.date().isoformat()
    if quote.get("symbol")!=symbol or quote.get("date")!=trading_date:
        return {"symbol":symbol,"valid":False,"reason":"date_or_symbol_mismatch"}
    if quote.get("isTrial") is True or quote.get("lastTrade") is None:
        return {"symbol":symbol,"valid":False,"reason":"trial_or_no_actual_trade"}
    last=quote["lastTrade"]
    px=numeric(last.get("price"));average=numeric(quote.get("avgPrice"))
    at=timestamp(last.get("time"))
    if px is None or px<=0 or average is None or average<=0 or at is None:
        return {"symbol":symbol,"valid":False,"reason":"invalid_trade_or_cumulative_average"}
    if at.date()!=now.date() or not (dtime(9,0)<=at.timetz().replace(tzinfo=None)<=dtime(13,30)):
        return {"symbol":symbol,"valid":False,"reason":"trade_not_in_cash_session"}
    lag=(now-at).total_seconds()
    if lag<0 or lag>MAX_TRADE_AGE_SECONDS:
        return {"symbol":symbol,"valid":False,"reason":"stale_or_future_trade","ageSeconds":round(lag)}
    vol=numeric((quote.get("total") or {}).get("tradeVolume"))
    if vol is None or vol<=0:return {"symbol":symbol,"valid":False,"reason":"no_reported_volume"}
    return {"symbol":symbol,"valid":True,"date":trading_date,
        "tradeAt":at.isoformat(timespec="seconds"),"ageSeconds":round(lag),
        "tradeVsSessionAveragePct":round((px/average-1)*100,4),
        "aboveCumulativeAverage":px>average,"atCumulativeAverage":px==average,
        "source":"Fugle stock intraday/quote avgPrice (session cumulative)"}
def opening_range(candles,symbol,now):
    """15 fully elapsed one-minute bars from 09:00 through 09:14 inclusive."""
    if candles.get("symbol")!=symbol or candles.get("date")!=now.date().isoformat():
        return {"valid":False,"reason":"date_or_symbol_mismatch"}
    rows={}
    for c in candles.get("data") or []:
        try:at=datetime.fromisoformat(c["date"])
        except (KeyError,ValueError,TypeError):continue
        if at.tzinfo is None:continue
        at=at.astimezone(TZ)
        # Open range stops strictly at 09:14; elapsed bar requires time >= bar start + 1min.
        if at.date()!=now.date() or at.hour!=9 or not (0<=at.minute<15) or now<at+timedelta(minutes=1):continue
        hi=numeric(c.get("high"));lo=numeric(c.get("low"));vol=numeric(c.get("volume"))
        if hi is None or lo is None or vol is None or hi<lo or lo<=0 or vol<0:continue
        rows[at.minute]=(hi,lo,vol)
    if len(rows)<15:return {"valid":False,"reason":"incomplete_09_00_to_09_14_bars","observed":len(rows)}
    hi=max(v[0] for v in rows.values());lo=min(v[1] for v in rows.values())
    return {"valid":True,"rangeHigh":hi,"rangeLow":lo,"rangeMinutes":15,
        "warning":"Opening-range high/low are price levels, not a backtested entry rule"}
def interpret(data,opening=None):
    """Experimental 4-symbol condition, never an automatic execution command."""
    records=data.get("symbols") or []
    if len(records)!=4 or any(not x.get("valid") for x in records):
        return {"state":"NO_SIGNAL","reason":"missing_or_stale_quotes","claimBuyPermission":False}
    ref=records[0];g=records[1:]
    if ref["symbol"]!="0050":return {"state":"NO_SIGNAL","reason":"benchmark_is_not_0050","claimBuyPermission":False}
    count=sum(x["aboveCumulativeAverage"] for x in g)
    if opening is None or not opening.get("valid"):
        return {"state":"VWAP_ONLY","GAboveAverageCount":count,"benchAboveAverage":ref["aboveCumulativeAverage"],
            "claimBuyPermission":False,"reason":"no_confirmed_15minute_opening_range"}
    nowAbove=ref["aboveCumulativeAverage"];p=ref["tradeVsSessionAveragePct"]
    if nowAbove and count>=2:
        state="BREADTH_CONFIRMED_4_SYMBOLS" if count==3 else "BREADTH_PARTIAL_4_SYMBOLS"
    elif not nowAbove and count<=1:state="WEAK_4_SYMBOLS"
    else:state="DIVERGENT_4_SYMBOLS"
    return {"state":state,"GAboveAverageCount":count,"benchAboveAverage":nowAbove,
        "benchVsAveragePct":p,"openingRangeOnly":True,"claimBuyPermission":False,
        "warning":"Only 0050 + G Top3, not whole TWSE breadth; NOT backtested or execution-ready"}
def get_json(url,key):
    if not url.startswith(API+"/"):raise RuntimeError("Blocked non-Fugle stock URL")
    req=Request(url,headers={"X-API-KEY":key,"Accept":"application/json","User-Agent":"personal-G-VWAP-research/1.0"})
    try:
        with urlopen(req,timeout=12) as stream:return json.load(stream)
    except HTTPError as e:raise RuntimeError(f"Fugle HTTP {e.code} ({'rate limited' if e.code==429 else 'check API permissions'})") from None
    except (URLError,TimeoutError) as e:raise RuntimeError("Fugle request timeout or network error") from None
def run(now=None,key=None):
    now=now or datetime.now(TZ)
    if now.tzinfo is None:raise ValueError("Timezone-aware clock required")
    now=now.astimezone(TZ)
    if now.weekday()>4 or not dtime(9,0)<=now.time()<dtime(13,30):
        return {"schema":SCHEMA,"status":"outside_cash_session","timestamp":now.isoformat(),"symbols":[]}
    latest=json.loads((ROOT/"latest.json").read_text(encoding="utf-8"))
    symbols,signal_date=sym_list(latest)
    if signal_date>=now.date().isoformat() or (now.date()-datetime.fromisoformat(signal_date).date()).days>8:
        return {"schema":SCHEMA,"status":"stale_or_non_prior_G_rank","timestamp":now.isoformat(),"symbols":[]}
    if not key:return {"schema":SCHEMA,"status":"missing_private_FUGLE_API_KEY","timestamp":now.isoformat(),"symbols":[]}
    observations=[quote_analysis(get_json(f"{API}/quote/{s}",key),s,now) for s in symbols]
    if any(not s["valid"] for s in observations):range_15=None
    else:range_15=opening_range(get_json(f"{API}/candles/0050?timeframe=1",key),"0050",now)
    return {"schema":SCHEMA,"status":"evaluated_private" if all(x["valid"] for x in observations) else "data_not_tradable",
        "timestamp":now.isoformat(),"GAsOf":signal_date,"symbols":observations,
        "range0050":range_15,"condition":interpret({"symbols":observations},range_15),
        "disclaimer":"Personal private research only; no public redistribution. No measured 09:30 alpha and NO trade execution."}
def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--private-json",type=Path,help="LOCAL-ONLY private data file; do not commit or publish")
    args=parser.parse_args()
    result=run(key=os.environ.get("FUGLE_API_KEY"))
    # Public repo Actions logs deliberately exclude both raw quotes and private signal values.
    print("PRIVATE_FUGLE_VWAP_STATUS",json.dumps({"status":result["status"],
        "timestamp":result["timestamp"],"validSymbols":sum(x.get("valid",False) for x in result.get("symbols",[])),
        "configured":bool(os.environ.get("FUGLE_API_KEY"))},ensure_ascii=False))
    if args.private_json:
        p=args.private_json.resolve()
        if "docs" in p.parts or p.is_relative_to(ROOT):raise RuntimeError("Refuse writing licensed quote derivations under public site root")
        p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
if __name__=="__main__":main()
