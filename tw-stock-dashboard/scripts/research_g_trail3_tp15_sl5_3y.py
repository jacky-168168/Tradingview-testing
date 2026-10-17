"""G Double Persist Top3 / 2024-2026: +3% trailing arm, -3% peak trail, TP+15%, SL-5%.
Compare the SAME A=G signal entry and B=G+own-stock SMA10 entry as previous audit.
At D close select; fill D+1 open. Daily OHLC ambiguity always resolved conservatively.
This is standalone research; never edits dashboard, never markets as forward/live result.
"""
from __future__ import annotations
import collections,json,math,sys,time
from datetime import datetime,timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
sys.path.insert(0,str(ROOT/"scripts"))
import research_g_stock_sma_2026 as engine
from yahoo_cache import update_many,update_symbol
from pipeline import load_universe
from research_g_regime_3y import make_g,finite
START="2024-01-02";WARM_START="2023-10-09"
SIGNAL_END="2026-10-07";MARK_END="2026-10-16"
OUT=ROOT/"docs/data/research/g_trail3_tp15_sl5_3y"
PRINCIPAL=1_000_000.
MAX_WEIGHT=.25;MAX_SLOTS=4
ARM=.03;TRAIL=.03;TAKE=.15;STOP=.05
BUY=1+.001425+.001
SELL=1-.001425-.003-.001
STRATEGIES=("A_G_TOP3","B_G_TOP3_SMA10")
def validate_prices(z):
    if not z:return False
    return z["open"]>0 and z["high"]>=z["low"]>0 and z["high"]>=z["open"]>=z["low"]
def open_exit(p,o):
    """Only gap exits at today's open. Resting levels depend on PRIOR session peak."""
    op=float(o)
    fixed=p["entryPrice"]*(1-STOP)
    trail=p["highest"]*(1-TRAIL) if p["armed"] else None
    if op<=fixed:return op,"gap_fixed_stop"
    if trail is not None and op<=trail:return op,"gap_trailing_stop"
    if op>=p["entryPrice"]*(1+TAKE):return op,"gap_fixed_target"
    return None
def intraday_exit(p,candle):
    """Bar cannot reveal OHLC sequence. Worst feasible exit first; no imagined ideal order."""
    hi=float(candle["high"]);lo=float(candle["low"])
    ent=p["entryPrice"];fixed=ent*(1-STOP);target=ent*(1+TAKE)
    prevHigh=p["highest"];prevArm=p["armed"]
    newPeak=max(prevHigh,hi)
    armed=prevArm or newPeak>=ent*(1+ARM)
    trail=newPeak*(1-TRAIL) if armed else None
    fixedHit=lo<=fixed
    trailHit=(trail is not None and lo<=trail)
    targetHit=hi>=target
    # A low may have occurred before today's intrabar high; choosing trail exit
    # over an available target is intentionally unfavorable on ambiguous bars.
    conflicts=int(bool(fixedHit and (trailHit or targetHit)))+int(bool(trailHit and targetHit))
    newlyArmedAndLow=int(not prevArm and armed and lo<=trail)
    if fixedHit:return fixed,"fixed_stop",armed,newPeak,conflicts,newlyArmedAndLow
    if trailHit:return trail,"trailing_stop",armed,newPeak,conflicts,newlyArmedAndLow
    if targetHit:return target,"fixed_target",armed,newPeak,conflicts,newlyArmedAndLow
    return None,None,armed,newPeak,conflicts,newlyArmedAndLow
def run_one(name,dates,picks,bars):
    cash=PRINCIPAL;positions={};closed=[];curve=[]
    exit_types=collections.Counter();entry_types=collections.Counter();skips=collections.Counter()
    same_day_conflicts=0;newly_armed_same_day_stop=0;peak=PRINCIPAL;worst=0.;worstDay=None;peakDay=None
    date_lookup={d:i for i,d in enumerate(dates)}
    for i,d in enumerate(dates):
        if d<START or d>MARK_END:continue
        prev=dates[i-1] if i>0 else None
        # Opening phase 1: process gaps ONLY; a gap exit releases real open-session cash.
        banned=set()
        for sym,p in list(positions.items()):
            today=bars.get(sym,{}).get(d)
            if today is None:continue
            if not validate_prices(today):raise RuntimeError("Invalid bar "+sym+" "+d)
            gap=open_exit(p,today["open"])
            if gap is None:continue
            px,why=gap
            income=round(p["qty"]*px*SELL,8);cash+=income
            pnl=income-p["cost"]
            closed.append({"code":p["code"],"name":p["name"],"sym":sym,
                "entryDate":p["entryDate"],"exitDate":d,"entryPrice":round(p["entryPrice"],5),
                "exitPrice":round(px,5),"exit":why,"grossPct":round((px/p["entryPrice"]-1)*100,4),
                "netPct":round(100*pnl/p["cost"],4),"netTWD":round(pnl,2),
                "qty":p["qty"],"heldSessions":i-p["entryIdx"],"entryType":p["entryType"]})
            exit_types[why]+=1;del positions[sym];banned.add(sym)
        # Opening phase 2: buy from previous day's G Top3 and PREVIOUS known SMA10.
        prevPicks=picks.get(prev,[]) if prev else []
        for x in prevPicks:
            sym=x["sym"]
            if sym in positions or sym in banned:continue
            if len(positions)>=MAX_SLOTS:break
            prevBar=bars.get(sym,{}).get(prev)
            current=bars.get(sym,{}).get(d)
            if prevBar is None or current is None:
                skips["entry_no_bar"]+=1;continue
            if not validate_prices(current):raise RuntimeError("Invalid candidate bar "+sym+" "+d)
            if name=="B_G_TOP3_SMA10":
                ma=prevBar["sma10"]
                if ma is None or float(prevBar["close"])<=float(ma)*1.01:
                    skips["entry_sma10_rejected"]+=1;continue
            # Position value at opening using *only* prices known at today's opening.
            value=cash
            for held_sym,z in positions.items():
                q=bars.get(held_sym,{}).get(d)
                if q is None:q=bars.get(held_sym,{}).get(prev)
                if q is None:raise RuntimeError("Cannot value position "+held_sym+" "+d)
                value+=z["qty"]*float(q["open"])*SELL
            px=float(current["open"])
            cap=min(MAX_WEIGHT*value,cash)
            qty=int((cap+1e-10)//(px*BUY))
            if qty<1:
                skips["no_buying_power"]+=1;continue
            cost=qty*px*BUY
            if cost>cash+1e-5:raise RuntimeError("Margin used accidentally")
            cash-=cost
            positions[sym]={"code":x["code"],"name":x["name"],"qty":qty,"cost":cost,
                "entryIdx":i,"entryDate":d,"entryPrice":px,
                "armed":False,"highest":px,"entryType":name}
            entry_types["G_top3"]+=1
        # Intraday phase: AFTER all open fills. Cash from these exits cannot be
        # reused on the same day's open (prevents intraday lookahead).
        for sym,p in list(positions.items()):
            today=bars.get(sym,{}).get(d)
            if today is None:
                skips["missing_daily_candle"]+=1;continue
            ans=intraday_exit(p,today)
            px,why,armed,highest,ambiguous,newarm=ans
            same_day_conflicts+=ambiguous
            newly_armed_same_day_stop+=newarm
            if why:
                income=p["qty"]*px*SELL;cash+=income
                pnl=income-p["cost"]
                closed.append({"code":p["code"],"name":p["name"],"sym":sym,
                    "entryDate":p["entryDate"],"exitDate":d,"entryPrice":round(p["entryPrice"],5),
                    "exitPrice":round(px,5),"exit":why,"grossPct":round((px/p["entryPrice"]-1)*100,4),
                    "netPct":round(100*pnl/p["cost"],4),"netTWD":round(pnl,2),
                    "qty":p["qty"],"heldSessions":i-p["entryIdx"],"entryType":p["entryType"]})
                exit_types[why]+=1;del positions[sym]
            else:
                p["armed"]=armed;p["highest"]=highest
        # Mark using current day's completed close, or last known close for suspended stocks.
        val=cash
        for sym,p in positions.items():
            today=bars.get(sym,{}).get(d)
            if today is None:
                possible=[v for date,v in bars.get(sym,{}).items() if date<=d]
                if not possible:raise RuntimeError("Missing mark "+sym+" "+d)
                today=possible[-1];skips["stale_daily_mark"]+=1
            val+=p["qty"]*today["close"]*SELL
        peak=max(peak,val)
        draw=1-val/peak
        if draw>worst:
            worst=draw;worstDay=d
        curve.append({"date":d,"equity":round(val,2),"cash":round(cash,2),"openPositions":len(positions)})
    if not curve:raise RuntimeError("No portfolio curve")
    positives=[z for z in closed if z["netTWD"]>0]
    negatives=[z for z in closed if z["netTWD"]<=0]
    profit=sum(z["netTWD"] for z in positives)
    loss=-sum(z["netTWD"] for z in negatives)
    yearly={}
    for year in ("2024","2025","2026"):
        barsY=[x for x in curve if x["date"].startswith(year)]
        if not barsY:raise RuntimeError("Missing year "+year)
        before=[z for z in curve if z["date"]<year+"-01-01"]
        prevValue=before[-1]["equity"] if before else PRINCIPAL
        annualHigh=prevValue;annualDD=0.
        for z in barsY:
            annualHigh=max(annualHigh,z["equity"])
            annualDD=max(annualDD,1-z["equity"]/annualHigh)
        t=[x for x in closed if x["exitDate"].startswith(year)]
        yearly[year]={"startEquity":round(prevValue,2),"endEquity":barsY[-1]["equity"],
            "returnPct":round((barsY[-1]["equity"]/prevValue-1)*100,3),
            "maxDrawdownPct":round(-annualDD*100,3),
            "closedTrades":len(t),"winRatePct":round(sum(x["netTWD"]>0 for x in t)/len(t)*100,2) if t else None}
    summary={"model":name,"startCapital":PRINCIPAL,"endEquity":curve[-1]["equity"],
        "totalReturnPct":round((curve[-1]["equity"]/PRINCIPAL-1)*100,3),
        "maxDrawdownPct":round(-100*worst,3),"maxDrawdownDate":worstDay,
        "trades":len(closed),"wins":len(positives),"losses":len(negatives),
        "winRatePct":round(100*len(positives)/len(closed),2) if closed else None,
        "profitFactor":round(profit/loss,3) if loss>0 else None,
        "avgWinPct":round(sum(x["netPct"] for x in positives)/len(positives),3) if positives else None,
        "avgLossPct":round(sum(x["netPct"] for x in negatives)/len(negatives),3) if negatives else None,
        "avgHoldSessions":round(sum(x["heldSessions"] for x in closed)/len(closed),3) if closed else None,
        "openAtEnd":len(positions),"entryCounts":dict(entry_types),
        "exitCounts":dict(exit_types),"conflictingSameDayStopAndTarget":same_day_conflicts,
        "sameBarTrailActivationAndStop":newly_armed_same_day_stop,
        "skips":dict(skips),"yearly":yearly}
    if any(v<0 for v in [summary["trades"],summary["wins"],summary["losses"]]):raise RuntimeError("Negative trade count")
    if summary["wins"]+summary["losses"]!=summary["trades"]:raise RuntimeError("Trade classification mismatch")
    if sum(exit_types.values())!=summary["trades"]:raise RuntimeError("Exit conservation mismatch")
    if curve[-1]["equity"]<=0:raise RuntimeError("Account underwater")
    return summary,closed,curve
def unit_tests():
    p={"entryPrice":100.0,"highest":100.0,"armed":False}
    z=intraday_exit(p,{"high":102.,"low":95.})
    assert z[1]=="fixed_stop" and z[0]==95.0,z
    z=intraday_exit(p,{"high":103.5,"low":101.0})
    assert z[1] is None and z[2] is True,z
    z=intraday_exit(p,{"high":103.5,"low":100.0})
    assert z[1]=="trailing_stop" and abs(z[0]-100.395)<1e-6,z
    z=intraday_exit(p,{"high":116.,"low":95.})
    assert z[1]=="fixed_stop",z
    z=intraday_exit(p,{"high":116.,"low":110.})
    assert z[1]=="trailing_stop" and z[4]>0,z
    z=intraday_exit(p,{"high":116.,"low":114.})
    assert z[1]=="fixed_target" and abs(z[0]-115)<1e-6,z
    p2={"entryPrice":100.,"highest":110.,"armed":True}
    assert open_exit(p2,102.)==(102.,"gap_trailing_stop")
    assert open_exit(p2,94.)==(94.,"gap_fixed_stop")
    assert open_exit(p2,116.)==(116.,"gap_fixed_target")
    print("UNIT_TESTS_PASSED stop/gap/activation/samebar/target")
def main():
    t0=time.monotonic();unit_tests()
    engine.START=START;engine.MARKET_END=MARK_END
    universe=[u for u in load_universe() if finite(u.get("capitalB")) and float(u["capitalB"])>0]
    if len(universe)<1750:raise RuntimeError("Insufficient universe")
    pullfrom=datetime.fromisoformat(WARM_START)-timedelta(days=430)
    pullto=datetime.fromisoformat(MARK_END)+timedelta(days=3)
    print("DOWNLOAD_UNIVERSE",len(universe),pullfrom.date(),pullto.date(),flush=True)
    hist,errors=update_many([(x["code"],x["market"]) for x in universe],pullfrom,pullto)
    _,idx,indexError=update_symbol("^TWII",pullfrom,pullto)
    if indexError or idx is None or idx.empty:raise RuntimeError("Index missing "+str(indexError))
    idx=idx.sort_values("date").drop_duplicates("date",keep="last")
    calendar=sorted(set(idx.date.astype(str)))
    gDates=[d for d in calendar if WARM_START<=d<=SIGNAL_END]
    simulationDates=[d for d in calendar if "2023-12-01"<=d<=MARK_END]
    if len(gDates)<680 or len([d for d in simulationDates if START<=d<=MARK_END])<660:
        raise RuntimeError("Calendar incomplete")
    if simulationDates[-1]!=MARK_END:raise RuntimeError("Latest session missing: "+simulationDates[-1])
    if len(errors)>len(universe)*.1:raise RuntimeError("Stock history source coverage low "+str(len(errors)))
    picksRaw,_,audit=make_g(gDates,idx,universe,hist)
    picks={d:[{"code":str(x["code"]),"name":x["name"],"market":x["market"],"sym":x["sym"],"rank":j+1}
          for j,x in enumerate(picksRaw.get(d,[])[:3])] for d in gDates}
    # Sanity check 2026 reconstruction against separately archived signal ranking.
    p=ROOT/"docs/data/backtest_g/g_persistence_2026.json"
    archival=json.loads(p.read_text(encoding="utf-8"))["models"]["G_DOUBLE_PERSIST"]["signals"]
    reference=collections.defaultdict(list)
    for r in archival:
        if r["signalDate"]<=SIGNAL_END:reference[r["signalDate"]].append(str(r["code"]))
    compare=sum(len(set(reference[d])&set(x["code"] for x in picks.get(d,[]))) for d in reference)
    total=sum(len(v) for v in reference.values())
    if compare!=total:raise RuntimeError(f"2026 parity failed: {compare}/{total}")
    symbols={r["sym"] for rows in picks.values() for r in rows}
    bars={sym:engine.compile_bars(hist.get(sym)) for sym in symbols}
    usable=sum(len(x)>=60 for x in bars.values())
    if usable<len(symbols)*.98:raise RuntimeError(f"Selected stock bar coverage {usable}/{len(symbols)}")
    rows=[];allTrades={};allCurves={}
    for s in STRATEGIES:
        result,trades,curve=run_one(s,simulationDates,picks,bars)
        rows.append(result);allTrades[s]=trades;allCurves[s]=curve
        print("RESULT",json.dumps(result,ensure_ascii=False),flush=True)
    output={"version":"G_TRAIL3_ARM3_TP15_SL5_3Y_V1",
      "generatedAt":datetime.now(ZoneInfo("Asia/Taipei")).isoformat(timespec="seconds"),
      "period":{"start":START,"signalEnd":SIGNAL_END,"markEnd":MARK_END},
      "rules":{"entryA":"G double-break and 10-day persistence Top3 D-close => buy D+1 open",
      "entryB":"Entry A AND individual stock prior close > prior SMA10*1.01",
      "trailArmPct":3,"trailFromHighestPct":3,"takeProfitPct":15,"hardStopPct":-5,
      "trailReference":"highest intraday price observed since acquisition",
      "sameCandleOrder":"fixed stop first, trailing stop second, +15% target third; conservative intrabar ordering",
      "gapStop":"fill at true daily opening when open crosses resting stop; can lose more than 5%",
      "positionCapPct":25,"maximumConcurrentPositions":4,"initialCapitalTWD":PRINCIPAL,
      "commissionBuyPct":(BUY-1)*100,"commissionSellTaxSlippagePct":(1-SELL)*100},
      "sample":{"listedOtcUniverse":len(universe),"stockHistoryErrors":len(errors),
        "historicGSignalDays":sum(bool(v) for v in picks.values()),
        "gRankRows":sum(len(v) for v in picks.values()),"differentRankedSymbols":len(symbols),
        "symbolOHLCUsable":usable,"g2026ParitySignals":total,
        "g2026ParityCorrect":compare,"dailyGScannerAudit":audit},
      "limitations":[
        "2024-2025 historical G ranks reconstructed retrospectively from CURRENT stock universe and capital; survivorship and historical float bias.",
        "A/B entry at next session opening; exits simulated with daily OHLC not tick sequence.",
        "When multiple levels crossed inside one day, worst (lower) available exit is chosen; actual ordering unobservable.",
        "Trailing activation and stop both occurring inside one day may be impossible in actual price path order.",
        "Brokerage 0.1425% each side, stock sell tax 0.3%, slippage 0.1% each side.",
        "Daily OHLC stock splits/dividends not fully corporate-action adjusted, no daily limit up/down/queue simulation.",
        "Fixed exit +15% on single stock may take longer than one Taiwan daily 10% price-limit session.",
        "Output is retrospective research, not walk-forward independently verified and not a live record."],
      "models":rows,"elapsedSeconds":round(time.monotonic()-t0,2)}
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/"summary.json").write_text(json.dumps(output,ensure_ascii=False,indent=2),encoding="utf-8")
    (OUT/"trades.json").write_text(json.dumps({"version":output["version"],"models":allTrades},ensure_ascii=False),encoding="utf-8")
    (OUT/"equity.json").write_text(json.dumps({"version":output["version"],"models":allCurves},ensure_ascii=False),encoding="utf-8")
    print("AUDITED_G_TRAILING_3Y_COMPLETE",len(rows),"models",len(symbols),"selected symbols",flush=True)
if __name__=="__main__":main()
