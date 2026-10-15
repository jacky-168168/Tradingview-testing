"""Causal pilot audit of overnight TX score adjustments (market classification only).
Uses the previous official cash score and a completed same-contract night session
attributed by TAIFEX to the following trading day. NO executable P&L claims.
"""
import csv,io,json,math,urllib.request
from collections import defaultdict
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
CASH=ROOT/"docs/data/research/g_regime_3y/market_risk_daily.csv"
OUT=ROOT/"docs/data/research/tx_night_score_pilot"
TX_SHA="436c9782600af47d9a24b2479b7fefd3f4c2d252"
TX_URL=f"https://raw.githubusercontent.com/wenchiehlee-investment/TAIFEX/{TX_SHA}/data/raw_taifex_daily_futures.csv"
FIRST="2026-07-09"
LAST="2026-10-08"
def delta(pct):
    if pct<=-2:return -25
    if pct<=-1:return -15
    if pct<=-.5:return -8
    if pct>=2:return 10
    if pct>=1:return 7
    if pct>=.5:return 4
    return 0
def make_archive(txt):
    out={}
    for r in csv.DictReader(io.StringIO(txt.lstrip("\ufeff"))):
        dt,contract,session=r.get("Date",""),r.get("ContractMonth(Week)",""),r.get("TradingSession","")
        if r.get("Contract")!="TX" or len(dt)!=8 or not contract.isdecimal() or len(contract)!=6 or session not in ("一般","盤後"):continue
        try:
            close=float(r["Last"]);vol=int(float(r["Volume"]))
        except (TypeError,ValueError,KeyError):continue
        if close<=0 or vol<100:continue
        k=(dt,contract,session)
        if k not in out or r.get("process_timestamp","")>=out[k]["stamp"]:
            out[k]={"date":dt,"month":contract,"session":session,"close":close,"volume":vol,"stamp":r.get("process_timestamp","")}
    return out
def test_cases(cash,archive):
    days=[r for r in csv.DictReader(io.StringIO(cash.lstrip("\ufeff"))) if FIRST<=r.get("date","")<=LAST]
    days.sort(key=lambda r:r["date"])
    matched=[];missing=[]
    for i in range(1,len(days)):
        previous,current=days[i-1],days[i]
        prior=previous["date"].replace("-","");today=current["date"].replace("-","")
        # Near-month is chosen by dominant DAY volume from the prior session;
        # never switch contracts between the day and the paired after-hours row.
        candidates=[v for (d,m,s),v in archive.items() if d==prior and s=="一般" and v["volume"]>500]
        leader=max(candidates,key=lambda v:v["volume"],default=None)
        overnight=leader and archive.get((today,leader["month"],"盤後"))
        if not leader or not overnight or overnight["volume"]<100:
            missing.append({"date":current["date"],"previousDate":previous["date"],
                            "reason":"no eligible previous DAY" if not leader else "no following trading-date NIGHT on SAME contract"})
            continue
        pct=(overnight["close"]/leader["close"]-1)*100
        if abs(pct)>12:missing.append({"date":current["date"],"reason":"night/day mismatch beyond 12%"});continue
        base=int(float(previous["score"]));s=max(0,min(100,base+delta(pct)))
        matched.append({"date":current["date"],"previousDate":previous["date"],"contract":leader["month"],
                        "previousDayTX":leader["close"],"overnightTX":overnight["close"],
                        "nightPct":round(pct,4),"cashPreviousRiskScore":base,"txDelta":delta(pct),
                        "nextCashReferenceScore":s,"nextCashCloseRetPct":float(current["dayRet"]),
                        "nextCashBreadthPct":float(current["breadth"]),
                        "originalGate":base>=60,"adjustedGate":s>=60})
    return days,matched,missing
def summary(a):
    n=len(a)
    if not n:return {"n":0}
    nums=lambda f:sum(1 for x in a if f(x))
    down=nums(lambda x:x["nextCashCloseRetPct"]<0)
    return {"n":n,"meanNextDayReturnPct":round(sum(x["nextCashCloseRetPct"] for x in a)/n,3),
            "cashDownDays":down,"cashDownPct":round(100*down/n,1),
            "cashDrop1PctDays":nums(lambda x:x["nextCashCloseRetPct"]<=-1),
            "cashBreadthUnder45Days":nums(lambda x:x["nextCashBreadthPct"]<45),
            "cashBreadthUnder45Pct":round(100*nums(lambda x:x["nextCashBreadthPct"]<45)/n,1)}
def wilson(k,n):
    if not n:return None
    z=1.959963984540054;p=k/n;den=1+z*z/n;mid=(p+z*z/(2*n))/den
    rad=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/den
    return [round(100*(mid-rad),1),round(100*(mid+rad),1)]
def fisher_right(a,b,c,d):
    # One-sided exact hypergeometric P[X >= observed severe-night down count].
    n=a+b+c+d;downs=a+c;severe=a+b
    allways=math.comb(n,severe)
    return sum(math.comb(downs,x)*math.comb(n-downs,severe-x)
               for x in range(a,min(downs,severe)+1)
               if 0<=severe-x<=n-downs)/allways
def render(cash,futures):
    cashDays,matched,missing=test_cases(cash,make_archive(futures))
    if len(cashDays)<50 or len(matched)<40:raise RuntimeError("Pilot coverage insufficient; refuse to print a success summary")
    severe=[x for x in matched if x["nightPct"]<=-1]
    other=[x for x in matched if x["nightPct"]>-1]
    downs=lambda arr:sum(x["nextCashCloseRetPct"]<0 for x in arr)
    windows=[("night<=-2",lambda x:x["nightPct"]<=-2),("-2<night<=-1",lambda x:-2<x["nightPct"]<=-1),
      ("-1<night<=-0.5",lambda x:-1<x["nightPct"]<=-.5),
      ("-0.5<night<=0.5",lambda x:-.5<x["nightPct"]<=.5),
      ("0.5<night<=1",lambda x:.5<x["nightPct"]<=1),
      ("night>1",lambda x:x["nightPct"]>1)]
    buckets={label:summary([x for x in matched if f(x)]) for label,f in windows}
    change=[x for x in matched if x["originalGate"]!=x["adjustedGate"]]
    p=fisher_right(downs(severe),len(severe)-downs(severe),downs(other),len(other)-downs(other))
    result={"version":"TX_NIGHT_RISK_PILOT_V1","asOf":"2026-10-15","period":{"start":FIRST,"end":LAST,"cashDays":len(cashDays),"joinedDays":len(matched),"joinMissing":missing},
     "source":{"risk":"tw-stock-dashboard/docs/data/research/g_regime_3y/market_risk_daily.csv",
               "tx":"wenchiehlee-investment/TAIFEX aggregated official TAIFEX OpenAPI historical DAY/NIGHT",
               "txPinnedCommit":TX_SHA,"txFile":TX_URL,
               "taifexTradingDateNote":"The 15:00 NIGHT of cash date D is attributed to the next trading date T. Do not match Date(D) DAY and Date(D) NIGHT."},
     "overnightThresholdDelta":{"lte-2":-25,"lte-1":-15,"lte-0.5":-8,"gte0.5":4,"gte1":7,"gte2":10},
     "marketSummary":summary(matched),"buckets":buckets,
     "severeNight":summary(severe),"otherNights":summary(other),
     "severeCashDownWilson95Pct":wilson(downs(severe),len(severe)),
     "othersCashDownWilson95Pct":wilson(downs(other),len(other)),
     "severeCashDownFisherOneSidedExploratoryP":round(p,6),
     "officialGate60Sessions":sum(x["originalGate"] for x in matched),
     "adjustedGate60Sessions":sum(x["adjustedGate"] for x in matched),
     "changedGateCount":len(change),"changedGateDates":[x["date"] for x in change],
     "cases":matched,
     "limits":["Pilot July-October only; NOT the full 728-day score archive.","No fresh holdout; buckets were examined post hoc, so p-value is exploratory.",
       "The severe-night subgroup is small and has low prior Risk Scores. Zero gate changes means NO measured gain in G entry gating.",
       "Index close-to-close next-day return is NOT a tradable transaction price or a P&L backtest.",
       "No 10/15 realized cash outcome has been used: current risk history stops at 10/08.",
       "Futures were aggregated by an external open-source collector from exchange OpenAPI; need archival and independent official reconciliation.",
       "Missing expiry/mismatched pairs are excluded, never synthesized.",
       "Absolute +/- score points are heuristic: neither 15 nor 60 is empirically calibrated on an independent G performance holdout."]}
    return result
def md(r):
    s=r["severeNight"];o=r["otherNights"];v=r["marketSummary"]
    lines=["# TX 夜盤調整 Risk Score：短期因果性試驗 V1","",
       "**研究期間：** 2026-07-09～2026-10-08｜**配對有效交易日：** "+str(r["period"]["joinedDays"])+"/"+str(r["period"]["cashDays"]-1),
       "**基準：** 前一交易日正式 Risk Score；以當日凌晨可得的同月份夜盤，評估當日現貨收盤漲跌及市場廣度。","",
       "| 夜盤情境 | 樣本 | 隔日現貨下跌 | 隔日平均漲跌 |",
       "|---|---:|---:|---:|",
       f"| 跌幅 ≥1% | {s['n']} | {s['cashDownDays']}/{s['n']}（{s['cashDownPct']}%） | {s['meanNextDayReturnPct']:+.2f}% |",
       f"| 其餘夜盤 | {o['n']} | {o['cashDownDays']}/{o['n']}（{o['cashDownPct']}%） | {o['meanNextDayReturnPct']:+.2f}% |",
       "",
       f"隔夜跌 ≥1% 組隔日下跌率 95% Wilson 區間：{r['severeCashDownWilson95Pct']}%；僅探索性單尾 Fisher p={r['severeCashDownFisherOneSidedExploratoryP']}，不代表預註冊檢驗或可交易績效。",
       f"**實際改變 >=60 進場門檻的日數：{r['changedGateCount']}。** 原始允許 {r['officialGate60Sessions']} 天，調整後仍允許 {r['adjustedGate60Sessions']} 天，沒有已測得的交易門檻改善。","",
       "## 原則性結論",
       "- 夜盤急跌的**方向性警報有歷史支持**，但以固定 -15 分得到 55 分的絕對刻度**尚未被驗證**。",
       "- 應將 **55 分視為「昨收＋夜盤參考基準」**，當 TX 跌幅≤-1% 時維持獨立重大風險警示（暫緩追價與一般新倉）。",
       "- 沒有經過真實個股 G 進出場、成本、停損及至少一年以上獨立樣本外測試，不能聲稱 G 選股報酬提高。",
       "",
       "## 可稽核分組"]
    for k,v in r["buckets"].items():
        lines.append(f"- {k}: {v['n']} 天；收跌 {v.get('cashDownDays','—')} 天；平均 {v.get('meanNextDayReturnPct','—')}%")
    lines+=["","## 來源與限制",f"- 期貨交易資料固定於 [公開累積資料 Git commit]({r['source']['txFile']})。","- TAIFEX 夜盤交易日歸屬與日盤不同，須以 **前交易日一般盤與今天歸屬夜盤** 配對同一契約。",
             "- 現貨 Risk Score 取本庫正式市場歷史 csv，使用前一日分數。","- 未有隔日開盤可成交價，不能把本報告當成策略交易損益。","",
             "其餘限制："+ "; ".join(r["limits"])]
    return "\n".join(lines)+"\n"
def main():
    req=urllib.request.Request(TX_URL,headers={"User-Agent":"G-TX-night-risk-research/1.0"})
    with urllib.request.urlopen(req,timeout=120) as x: futures=x.read().decode("utf-8-sig")
    cash=CASH.read_text(encoding="utf-8-sig")
    r=render(cash,futures)
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/"summary.json").write_text(json.dumps(r,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    (OUT/"report.md").write_text(md(r),encoding="utf-8")
    print(json.dumps({k:r[k] for k in ("period","severeNight","otherNights","changedGateCount","officialGate60Sessions","adjustedGate60Sessions","severeCashDownFisherOneSidedExploratoryP")},ensure_ascii=False))
if __name__=="__main__":main()
