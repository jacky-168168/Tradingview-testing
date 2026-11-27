"""Research-only TW stock intraday short A/B pilot with REAL Yahoo 5-minute OHLCV.

Not an executable short-sale list: historical TWSE/TPEx day-trading eligibility,
stock-specific suspension, broker borrow availability and limit-up inability to
cover are NOT available from this source. Never publish as an eligible stock pick.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import date, datetime, time, timedelta
import json
import math
from pathlib import Path
import statistics
import sys
import time as clock
from zoneinfo import ZoneInfo

TZ=ZoneInfo("Asia/Taipei")
SCHEMA="TW_DAYTRADE_SHORT_AB_PILOT_V1"
# Fixed ex-ante candidate pool only: NOT historical top-turnover whole market.
SYMBOLS=(
 "2330.TW","2317.TW","2454.TW","2303.TW","3231.TW","2382.TW","2357.TW",
 "2360.TW","2376.TW","2345.TW","3711.TW","3037.TW","3661.TW","3443.TW",
 "2408.TW","2603.TW","2609.TW","2615.TW","2610.TW","2618.TW","2881.TW",
 "2882.TW","2884.TW","2885.TW","2886.TW","2891.TW","1301.TW","1303.TW",
 "1326.TW","2002.TW","2014.TW","3481.TW","2409.TW","2301.TW","2324.TW",
 "3034.TW","3017.TW","2379.TW","1504.TW","1519.TW","1605.TW","2356.TW",
 "2492.TW","5269.TW","3324.TWO","8299.TWO",
 "2327.TW","2337.TW","2344.TW","2347.TW","2352.TW","2353.TW","2354.TW",
 "2368.TW","2371.TW","2377.TW","2383.TW","2385.TW","2392.TW","2404.TW",
 "2412.TW","2449.TW","2451.TW","2458.TW","2474.TW","2481.TW","2498.TW",
 "3005.TW","3006.TW","3008.TW","3013.TW","3023.TW","3035.TW","3042.TW",
 "3044.TW","3045.TW","3059.TW","3189.TW","3227.TWO","3374.TWO","3406.TW",
 "3532.TW","3533.TW","3653.TW","3706.TW","3715.TW","4904.TW","4919.TW",
 "4958.TW","4966.TWO","5274.TWO","5347.TWO","5439.TWO","5483.TWO",
 "6147.TWO","6182.TWO","6213.TW","6223.TWO","6274.TWO","6414.TW",
 "6442.TW","6669.TW","6756.TW","8046.TW","8150.TW","8210.TW","8996.TW"
)
BENCHMARK="0050.TW"
MODES=("A_WEAK_CONTINUATION","B_GAPUP_FAILURE")
# Public cost benchmark: full standard brokerage commission each side, 0.15%
# sale-side day-trading transaction tax, conservative fixed price slippage.
STANDARD_COMMISSION=0.001425
DISCOUNT_COMMISSION=0.000498
DAYTRADE_SELL_TAX=0.0015
SLIPPAGE=0.0005
MIN_AVG_TURNOVER_TWD=3e8
MAX_TRADES_PER_DAY=3
STOP_MULTIPLE=0.1
TARGET_R=1.8
STRICT_PROFILE=False
EXIT_CLOCK="13:20"
ENTRY_CUTOFF="12:15"

def finite(x):
    try:
        x=float(x)
        return x if math.isfinite(x) else None
    except (TypeError,ValueError,OverflowError):
        return None

def is_cash_bar(dt):
    return dt.weekday()<5 and time(9,0)<=dt.time()<time(13,30) and dt.minute%5==0

def load_yahoo_5m(ticker,attempts=2):
    import yfinance as yf
    errors=[]
    for attempt in range(attempts):
        try:
            df=yf.Ticker(ticker).history(period="60d",interval="5m",
                 auto_adjust=False,prepost=False,raise_errors=True,timeout=18)
            if df is None or df.empty:raise ValueError("Empty response")
            rows=[]
            for at,item in df.iterrows():
                stamp=at.to_pydatetime()
                if stamp.tzinfo is None:continue
                stamp=stamp.astimezone(TZ)
                if stamp.date()>=datetime.now(TZ).date() or not is_cash_bar(stamp):continue
                vals=[finite(item.get(col)) for col in ("Open","High","Low","Close","Volume")]
                if any(v is None for v in vals):continue
                o,h,l,c,v=vals
                if not (0<l<=min(o,c)<=max(o,c)<=h and v>=0):continue
                rows.append({"at":stamp,"o":o,"h":h,"l":l,"c":c,"v":v})
            if not rows:raise ValueError("No completed TW cash-session 5m bars")
            return rows,None
        except Exception as exc:
            errors.append(type(exc).__name__+":"+str(exc)[:130])
            if attempt+1<attempts:clock.sleep(1.5*(attempt+1))
    return [],";".join(errors[-2:])

def load_yahoo_daily(ticker,attempts=2):
    """Independent daily close, includes the TW closing auction missing in some 5m feeds."""
    import yfinance as yf
    errors=[]
    for attempt in range(attempts):
        try:
            frame=yf.Ticker(ticker).history(period="6mo",interval="1d",
                auto_adjust=False,prepost=False,raise_errors=True,timeout=18)
            if frame is None or frame.empty:raise ValueError("No daily OHLCV")
            out={}
            for at,item in frame.iterrows():
                stamp=at.to_pydatetime()
                if stamp.tzinfo is None:continue
                stamp=stamp.astimezone(TZ)
                d=stamp.date()
                if d>=datetime.now(TZ).date() or d.weekday()>=5:continue
                vals=[finite(item.get(k)) for k in ("Open","High","Low","Close","Volume")]
                if any(v is None for v in vals):continue
                o,h,l,c,v=vals
                if not (0<l<=min(o,c)<=max(o,c)<=h and v>0):continue
                out[d]={"o":o,"h":h,"l":l,"c":c,"v":v}
            if len(out)<25:raise ValueError("Fewer than 25 valid independent daily closes")
            return out,None
        except Exception as exc:
            errors.append(type(exc).__name__+":"+str(exc)[:130])
            if attempt+1<attempts:clock.sleep(1.2*(attempt+1))
    return {}, ";".join(errors[-2:])

def group_daily(rows,daily_closes=None):
    byday=defaultdict(dict)
    for bar in rows:
        key=bar["at"].date()
        clockkey=bar["at"].strftime("%H:%M")
        byday[key][clockkey]=bar
    out={}
    for d,bars in sorted(byday.items()):
        opening=("09:00","09:05","09:10")
        # Refuse partial sessions and stale/unsynchronized timestamps.
        if len(bars)<45 or any(x not in bars for x in opening) or "13:20" not in bars:continue
        # Yahoo sometimes has no 13:25 minute bar because the exchange uses a closing auction.
        # Do NOT use 13:20 close as an official EOD close: attach independent daily OHLC.
        ref=(daily_closes or {}).get(d)
        if daily_closes is not None and ref is None:continue
        arr=[bars[k] for k in sorted(bars)]
        first=arr[0];last=arr[-1]
        day_h=ref["h"] if ref is not None else max(b["h"] for b in arr)
        day_l=ref["l"] if ref is not None else min(b["l"] for b in arr)
        day_c=ref["c"] if ref is not None else last["c"]
        day_v=ref["v"] if ref is not None else sum(b["v"] for b in arr)
        # Different split/corporate-action price scales should never be silently mixed.
        if ref is not None and abs(last["c"]/day_c-1)>.06:continue
        out[d]={"bars":bars,"seq":arr,"o":first["o"],
            "h":day_h,"l":day_l,"c":day_c,"v":day_v,
            "turnover":day_c*day_v,
            "open15volume":sum(bars[k]["v"] for k in opening)}
    return out

def prev_features(d,days,market,benchmark):
    prev=[x for x in days if x<d]
    if len(prev)<22:return None
    p=prev[-1]
    prior5=prev[-6]
    recent=prev[-20:]
    prev20_twd=statistics.mean(market[x]["turnover"] for x in recent)
    close=market[p]["c"]
    if not (10<=close<=(300 if STRICT_PROFILE else 350) and prev20_twd>=(5e8 if STRICT_PROFILE else MIN_AVG_TURNOVER_TWD)):return None
    trs=[]
    for i in range(-14,0):
        cur=market[prev[i]]
        prior=market[prev[i-1]]
        trs.append(max(cur["h"]-cur["l"],abs(cur["h"]-prior["c"]),abs(cur["l"]-prior["c"])))
    atr=statistics.mean(trs)
    atr_pct=atr/close
    if not ((.03 if STRICT_PROFILE else .018)<=atr_pct<=(.08 if STRICT_PROFILE else .11)):return None
    bdays=sorted(x for x in benchmark if x<d)
    if len(bdays)<6 or bdays[-1]!=p:return None
    bnow=benchmark[bdays[-1]]["c"];bold=benchmark[bdays[-6]]["c"]
    if bnow<=0 or bold<=0:return None
    relative5=(market[p]["c"]/market[prior5]["c"]-1)-(bnow/bold-1)
    recentopen=[market[x]["open15volume"] for x in recent if market[x]["open15volume"]>0]
    if len(recentopen)<15:return None
    return {"prev_close":close,"atr":atr,"atr_pct":atr_pct,
        "turnover20":prev20_twd,"rel5":relative5,
        "open15median":statistics.median(recentopen),
        "prev_return":close/market[prev[-2]]["c"]-1}

def simulate_exit(seq,entry_clock,sell_px,stop,tp,commission,slip):
    """Entry next 5m open; exit at first stop/TP touch, stop FIRST if both touch.
    Forced end-of-day cover 13:20 open, strictly before 13:30 close.
    """
    idx=next((i for i,b in enumerate(seq) if b["at"].strftime("%H:%M")==entry_clock),None)
    if idx is None:return None
    for bar in seq[idx:]:
        when=bar["at"].strftime("%H:%M")
        if when>=EXIT_CLOCK:
            cover=bar["o"]*(1+slip);reason="time_exit_"+EXIT_CLOCK.replace(":","")
            break
        # Overnight / gap through stop: use adverse opening, not stop price.
        if bar["o"]>=stop:
            cover=bar["o"]*(1+slip);reason="stop_gap"
            break
        if bar["h"]>=stop:
            cover=stop*(1+slip);reason="stop_first"
            break
        if bar["o"]<=tp:
            cover=tp*(1+slip);reason="target_limit"
            break
        if bar["l"]<=tp:
            cover=tp*(1+slip);reason="target_limit"
            break
    else:return None
    # No tax on the later buyback; sell-side cash day-trading tax is 0.15%.
    net=(sell_px-cover - commission*(sell_px+cover) - DAYTRADE_SELL_TAX*sell_px)/sell_px
    gross=(sell_px-cover)/sell_px
    return {"gross_pct":round(gross*100,5),"net_pct":round(net*100,5),
        "exit_time":when,"exit_reason":reason}

def one_day(symbol,d,day,features,commission=STANDARD_COMMISSION,slip=SLIPPAGE):
    candles=day["bars"]
    opening=[candles.get(x) for x in ("09:00","09:05","09:10")]
    if any(x is None or x["v"]<=0 for x in opening):return []
    first15hi=max(x["h"] for x in opening)
    first15lo=min(x["l"] for x in opening)
    firstopen=opening[0]["o"]
    gap=firstopen/features["prev_close"]-1
    rv=day["open15volume"]/features["open15median"]
    if rv<(1.5 if STRICT_PROFILE else 1.3):return []
    has_upper_wick=any(
        (x["h"]-max(x["o"],x["c"]))/max(x["h"]-x["l"],1e-10)>=.27
        for x in opening)
    a_gate=-.035<=gap<=.01 and features["rel5"]<=(-.03 if STRICT_PROFILE else -.02)
    b_gate=.015<=gap<=.065 and first15hi>=firstopen*1.005 and has_upper_wick
    if STRICT_PROFILE:b_gate=b_gate and features.get("prev_return",0)>=.03
    if not(a_gate or b_gate):return []
    seq=day["seq"]
    cumulative_pv=0.;cumulative_vol=0.
    outcomes=[]
    for i,bar in enumerate(seq[:-1]):
        cumulative_pv+=((bar["h"]+bar["l"]+bar["c"])/3)*bar["v"]
        cumulative_vol+=bar["v"]
        when=bar["at"].strftime("%H:%M")
        if when<"09:15" or when>("10:55" if STRICT_PROFILE else ENTRY_CUTOFF) or cumulative_vol<=0:continue
        if bar["c"]>=first15lo or bar["c"]>=cumulative_pv/cumulative_vol:continue
        nextbar=seq[i+1]
        next_time=nextbar["at"].strftime("%H:%M")
        if (nextbar["at"]-bar["at"])!=timedelta(minutes=5) or next_time>=EXIT_CLOCK:continue
        # No signal-bar close fill: this order is placed only for next 5min opening.
        next_o=nextbar["o"]
        if not .992<=next_o/bar["c"]<=1.008:continue
        vwap=cumulative_pv/cumulative_vol
        short_fill=next_o*(1-slip)
        stop=max(first15hi,bar["h"],vwap)+features["atr"]*STOP_MULTIPLE
        risk=(stop-short_fill)/short_fill
        if not .006<=risk<=.045:continue
        target=short_fill-(stop-short_fill)*TARGET_R
        if target<=0:continue
        exit_=simulate_exit(seq,next_time,short_fill,stop,target,commission,slip)
        if exit_ is None:continue
        mode="A_WEAK_CONTINUATION" if a_gate else "B_GAPUP_FAILURE"
        score=(abs(features["rel5"])*100 if a_gate else gap*100)+0.3*min(rv,5)
        return [{"mode":mode,"symbol":symbol,"date":d.isoformat(),
           "signal_time":when,"entry_time":next_time,"signal_at_bar_close":True,
           "entry_next_bar_open":True,"prior20d_turnover_twd":round(features["turnover20"]),
           "prior_atr14_pct":round(100*features["atr_pct"],3),
           "relative5_pctpt":round(100*features["rel5"],3),
           "gap_pct":round(gap*100,3),"first15_rvol":round(rv,3),
           "score":round(score,4),"entry_gross_price":round(short_fill,4),
           "stop":round(stop,4),"target":round(target,4),**exit_}]
    return outcomes

def metrics(trades,capital_per_trade=100000):
    if not trades:
        return {"trades":0,"net_twd":0,"net_pct_per_trade_mean":None,
                "win_rate_pct":None,"profit_factor":None,"max_drawdown_twd":None,
                "max_drawdown_pct_of_300k":None,"worst_trade_pct":None}
    ordered=sorted(trades,key=lambda x:(x["date"],x["entry_time"],x["symbol"]))
    net=[x["net_pct"]/100*capital_per_trade for x in ordered]
    positive=sum(x for x in net if x>0);negative=-sum(x for x in net if x<0)
    e=MAX_TRADES_PER_DAY*capital_per_trade;top=e;mdd=0
    for v in net:
        e+=v;top=max(top,e);mdd=min(mdd,e-top)
    return {"trades":len(ordered),"net_twd":round(sum(net),2),
      "net_pct_per_trade_mean":round(statistics.mean(x["net_pct"] for x in ordered),4),
      "win_rate_pct":round(100*sum(x>0 for x in net)/len(net),2),
      "profit_factor":round(positive/negative,4) if negative>0 else None,
      "max_drawdown_twd":round(mdd,2),
      "max_drawdown_pct_of_300k":round(mdd/(MAX_TRADES_PER_DAY*capital_per_trade)*100,3),
      "worst_trade_pct":round(min(x["net_pct"] for x in ordered),4),
      "reason_counts":dict((why,sum(x["exit_reason"]==why for x in ordered))
                         for why in sorted(set(x["exit_reason"] for x in ordered)))}

def evaluate(raw,official_daily=None):
    daily={sym:group_daily(bars,(official_daily or {}).get(sym) if official_daily is not None else None)
           for sym,bars in raw.items()}
    benchmark=daily.get(BENCHMARK,{})
    days=sorted(set().union(*(set(v) for k,v in daily.items() if k!=BENCHMARK)))
    if len(benchmark)<23 or len(days)<25:
        return {"status":"unavailable","reason":"Fewer than 25 complete valid session days or benchmark history",
                "days_seen":len(days),"benchmark_complete_days":len(benchmark)}
    split=days[max(1,int(len(days)*.7))]
    observed=[]
    counts={"candidate_day_checks":0,"valid_lagged_features":0}
    for ticker,byday in daily.items():
        if ticker==BENCHMARK:continue
        dates=sorted(byday)
        for d in dates:
            counts["candidate_day_checks"]+=1
            features=prev_features(d,dates,byday,benchmark)
            if features is None:continue
            counts["valid_lagged_features"]+=1
            observed.extend(one_day(ticker,d,byday[d],features))
    # Execution ordering: first three actual chronological entries per mode/day;
    # no ex-post ranking of later opportunities ahead of earlier fills.
    picked=[]
    bymode=defaultdict(list)
    for item in observed:bymode[(item["mode"],item["date"])].append(item)
    for items in bymode.values():
        picked.extend(sorted(items,key=lambda x:(x["entry_time"],-x["score"],x["symbol"]))
                      [:MAX_TRADES_PER_DAY])
    sections={}
    for mode in MODES:
        vals=[x for x in picked if x["mode"]==mode]
        train=[x for x in vals if x["date"]<split.isoformat()]
        validation=[x for x in vals if x["date"]>=split.isoformat()]
        sections[mode]={"full":metrics(vals),"train":metrics(train),
                        "validation":metrics(validation),
                        "status":"exploratory" if len(validation)>=12 and len(vals)>=30 else "insufficient_sample",
                        "trades":vals}
    return {"status":"exploratory_only","source":"Yahoo Finance 5-minute OHLCV plus independently fetched daily OHLCV via yfinance",
        "daily_close_source":"Yahoo independent daily OHLCV, not 13:20 five-minute proxy",
        "period_start":days[0].isoformat(),"period_end":days[-1].isoformat(),
        "split_date":split.isoformat(),"bar_interval":"5m",
        "trading_eligibility_historically_verified":False,
        "liquidity_universe_historically_complete":False,
        "capital_per_trade_twd":100000,"max_daily_entries_per_mode":MAX_TRADES_PER_DAY,
        "full_roundtrip_commission_pct":2*100*STANDARD_COMMISSION,
        "sell_side_tax_pct":100*DAYTRADE_SELL_TAX,
        "slippage_pct_per_side":SLIPPAGE*100,
        "cost_model":"gross sell fill - adverse entry and exit slippage - both commissions - sell tax",
        "entry":"after completed 5m signal at next 5m bar open; stops evaluated on next and following bars",
        "exit":f"{TARGET_R}R take-profit, worst-case intrabar stop-first; force buyback {EXIT_CLOCK} open",
        "scope_warning":"Fixed present-day symbol pool; survivorship and selection bias. 5m OHLC cannot reproduce tick execution, limit-up unfillable cover, broker availability, or historical eligibility.",
        "selection_counts":counts,"models":sections}

def round2_profiles(raw, official_daily):
    """Fixed candidate profiles, chronological train selection, untouched holdout reporting.
    All profiles are exploratory; reused pilot dates are not a fresh independent OOS.
    """
    global STRICT_PROFILE, TARGET_R, EXIT_CLOCK, ENTRY_CUTOFF
    profiles=[]
    configs=[("expanded_baseline",False,1.8,"13:20","12:15")]
    configs += [(f"{'strict' if strict else 'pilot'}_R{r}_{exit_at.replace(':','')}",
                 strict,r,exit_at,"12:15")
                for strict in (False,True) for r in (1.0,1.3,1.8)
                for exit_at in ("11:30","12:30","13:20")
                if (strict,r,exit_at)!=(False,1.8,"13:20")]
    try:
        for name,strict,r,exit_at,cutoff in configs:
            STRICT_PROFILE,TARGET_R,EXIT_CLOCK,ENTRY_CUTOFF=strict,r,exit_at,cutoff
            report=evaluate(raw,official_daily)
            profiles.append({"profile":name,"strict":strict,"target_r":r,
                "force_exit":exit_at,"status":report["status"],
                "models":{k:{seg:v[seg] for seg in ("full","train","validation","status")}
                          for k,v in report.get("models",{}).items()}})
        selected={}
        for mode in MODES:
            eligible=[x for x in profiles if mode in x["models"]
                      and x["models"][mode]["train"]["trades"]>=20]
            if eligible:
                best=max(eligible,key=lambda x:x["models"][mode]["train"]["net_twd"])
                selected[mode]={"profile":best["profile"],**best["models"][mode]}
            else:selected[mode]={"status":"insufficient_train_trades"}
        return {"profiles":profiles,"selected_using_train_only":selected,
                "caveat":"Pilot-period holdout already examined; expanded current candidate pool is not a point-in-time universe. No production approval. Strict profile approximates original criteria with opening-range breakdown only, and prior-day rise >=3% for B.",
                "strict_parameters":{"price":[10,300],"turnover20_min":500000000,
                    "atr_pct":[3,8],"first15_rvol_min":1.5,"A_relative5_pctpt_max":-3,
                    "B_previous_day_return_pct_min":3,"last_signal":"10:55"}}
    finally:
        STRICT_PROFILE,TARGET_R,EXIT_CLOCK,ENTRY_CUTOFF=False,1.8,"13:20","12:15"

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--output",type=Path,required=True)
    p.add_argument("--max-symbols",type=int,default=46)
    p.add_argument("--sleep",type=float,default=.15)
    args=p.parse_args()
    raw={}
    official_daily={}
    failures={}
    symbols=[BENCHMARK]+list(SYMBOLS[:max(0,min(args.max_symbols,len(SYMBOLS)))])
    for i,ticker in enumerate(symbols,1):
        bars,error=load_yahoo_5m(ticker)
        daily_quotes,daily_error=load_yahoo_daily(ticker) if not error else ({}, "5m_missing")
        if error or daily_error:
            failures[ticker]=(error or "")+"; daily: "+(daily_error or "")
        else:
            raw[ticker]=bars
            official_daily[ticker]=daily_quotes
        print("DATA_COVERAGE",i,"of",len(symbols),ticker,
              "completed_5m_bars",len(bars),"independent_1d_days",len(daily_quotes),
              "error",error or daily_error or "none",flush=True)
        if args.sleep:clock.sleep(args.sleep)
    bench_bars=raw.get(BENCHMARK,[])
    audit_dates=sorted({x["at"].date() for x in bench_bars})
    last_sample=[]
    for d in audit_dates[-3:]:
        labels=sorted(x["at"].strftime("%H:%M") for x in bench_bars if x["at"].date()==d)
        last_sample.append({"day":d.isoformat(),"count":len(labels),
            "last_bar_clocks":labels[-6:],"first_bar_clocks":labels[:3]})
    print("BENCHMARK_5M_AUDIT",json.dumps({
        "n_raw_bars":len(bench_bars),"calendar_dates":len(audit_dates),
        "complete_days_by_current_policy":len(group_daily(bench_bars,official_daily.get(BENCHMARK))),
        "clock_samples":last_sample},ensure_ascii=False),flush=True)
    report=evaluate(raw,official_daily)
    round2=round2_profiles(raw,official_daily)
    print("SHORT_AB_ROUND2",json.dumps(round2,ensure_ascii=False,allow_nan=False),flush=True)
    output={"schema":SCHEMA,"generated_at_utc":datetime.now(TZ).astimezone(ZoneInfo("UTC")).isoformat(),
        "source_universe":list(SYMBOLS[:args.max_symbols]),"source_symbols_requested":len(symbols),
        "symbols_with_actual_complete_bars":len(raw),"download_failures":failures,
        "unverified_trade_permission":True,"price_history_not_redistributed":True,
        "not_approved_for_production":True,"round2":round2,**report}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(output,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    print("SHORT_AB_RESEARCH_SUMMARY",json.dumps({
        "status":report["status"],"reason":report.get("reason"),"days_seen":report.get("days_seen"),
        "benchmark_complete_days":report.get("benchmark_complete_days"),"source_coverage":len(raw),
        "date_span":[report.get("period_start"),report.get("period_end")],
        "split_date":report.get("split_date"),
        "models":{k:{seg:v[seg] for seg in ("full","train","validation","status")}
                  for k,v in report.get("models",{}).items()}},ensure_ascii=False))
    if report["status"]=="unavailable":
        print("::warning::Insufficient external REAL 5-minute data; NOT a backtest result.")
    elif not any(v["full"]["trades"] for v in report["models"].values()):
        print("::warning::No A/B entries passed strict 5-minute and prior-session gates; no profit claim.")
if __name__=="__main__":main()
