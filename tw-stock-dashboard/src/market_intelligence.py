"""Transparent market entry decision support -- NOT a replacement Risk Score.
Uses date-pinned TWSE market data, transparent breadth/volatility diagnostics and
research-only caution flags. Never places trades or overrides A/D/F/F2/G gates.
"""
from __future__ import annotations
import json,math,statistics
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
VERSION="MARKET_DECISION_SUPPORT_2026_10_V1"
def read(path,default):
    try:return json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:return default
def finite(v):
    try:
        v=float(v)
        return v if math.isfinite(v) else None
    except (ValueError,TypeError):return None
def history(root,risk):
    data=Path(root)/"research"/"g_regime_3y"/"market_risk_daily.json"
    delta=Path(root)/"research"/"market_intelligence"/"history_delta.json"
    original=read(data,[])
    if len(original)<500:raise RuntimeError("Need verified, date-locked TWSE market history")
    if any(not isinstance(x,dict) or x.get("date") is None or x.get("index") is None for x in original):
        raise RuntimeError("Unusable market history")
    asof=str(risk.get("date") or "")
    if not asof or risk.get("score") is None:raise RuntimeError("Current real market Risk Score is absent")
    daily={x["date"]:x for x in original if x["date"]<=asof}
    for x in read(delta,[]):
        if x.get("date") and x["date"]<=asof and x["date"] not in daily:daily[x["date"]]=x
    # The last day's actual dashboard row wins for DISPLAY/DIAGNOSTICS ONLY.
    # Never change the independently frozen 728-day official research archive.
    base=daily.get(asof,{})
    daily[asof]={**base,**dict(risk)}
    ordered=[daily[k] for k in sorted(daily)]
    if len(ordered)<45 or any(finite(x.get("index")) is None for x in ordered):
        raise RuntimeError("Not enough valid market observations")
    return ordered
def compute(risk,records):
    d=risk["date"];rows=[x for x in records if x["date"]<=d]
    if rows[-1]["date"]!=d:raise RuntimeError("Must not use future-day market history")
    closes=[float(x["index"]) for x in rows]
    breadth=[finite(x.get("breadth")) for x in rows]
    scores=[finite(x.get("score")) for x in rows]
    if any(x is None for x in breadth[-21:]+scores[-6:]):raise RuntimeError("Incomplete recent official breadth/score values")
    last=len(rows)-1
    mean=lambda a:statistics.mean(a)
    b5=mean(breadth[-5:]);b10=mean(breadth[-10:]);prev5=mean(breadth[-10:-5])
    ad10=sum(float(x.get("up") or 0)-float(x.get("down") or 0) for x in rows[-10:])
    per10=100*(closes[-1]/closes[-11]-1) if len(closes)>11 else None
    v20=[(closes[i]/closes[i-1]-1)*100 for i in range(len(closes)-20,len(closes))]
    annual=statistics.pstdev(v20)*math.sqrt(252)
    pastvol=[]
    for i in range(max(20,len(closes)-271),len(closes)):
        v=[(closes[j]/closes[j-1]-1)*100 for j in range(i-19,i+1)]
        pastvol.append(statistics.pstdev(v)*math.sqrt(252))
    volrank=sum(v<=annual for v in pastvol)/len(pastvol)*100
    priorClose120=max(closes[-121:-1]) if len(closes)>121 else None
    closeHighDistance=100*(closes[-1]/priorClose120-1) if priorClose120 else None
    actualHighDist=finite(risk.get("distHigh120Pct"))
    highDist=actualHighDist if actualHighDist is not None else closeHighDistance
    highType="盤中最高價" if actualHighDist is not None else "收盤高點"
    smoothed=mean(scores[-3:])
    scoreChange=round(scores[-1]-scores[-6],1)
    gap=finite(risk.get("distMA20"))
    if gap is None:gap=100*(closes[-1]/float(risk["ma20"])-1)
    # Divergence is a monitoring condition; it has NOT proved that vetoing buys
    # improves A/D/F/G realized portfolio outcomes.
    divergence=per10 is not None and per10>=2 and b10<50
    flags=[]
    def flag(code,severity,short,detail):
        flags.append({"code":code,"severity":severity,"title":short,"detail":detail})
    if divergence:flag("NARROW_BREADTH","caution","指數上漲但市場廣度不足","10日加權指數上漲≥2%，但10日平均上漲家數占比不足50%，須防權值股獨強。")
    if b5<45:flag("WEAK_BREADTH","caution","市場參與度偏弱","近5交易日上漲家數平均不足45%，強勢股追價需要更謹慎。")
    if breadth[-1]<45:flag("DAY_BREADTH_WEAK","caution","當日上漲家數偏少","今天只有不到45%的上市股票上漲；這是一日風險訊號，不能單獨作為禁止買進依據。")
    if scoreChange<=-20:flag("SCORE_DECELERATION","caution","五日大盤分數快速下降","Risk Score 相較5個交易日前下降至少20分；需留意多頭動能轉弱，但原分數和策略門檻不變。")
    if volrank>=90:flag("HIGH_VOLATILITY","caution","波動位於歷史高區","20日年化波動率位於可觀察滾動歷史的前10%；較易放大停損與隔夜跳空風險。")
    if highDist is not None and -2<=highDist<=0 and risk.get("mode")=="TOP":
        flag("NEAR_HIGH_TOP","watch","接近120日高點＋Top Watch","距前120交易日"+highType+"不足2%，又處於頂部觀察；屬尚未證實有效的追價警示，不是確認頂部。")
    if gap>=6 and float(risk.get("ret5") or 0)>=8:
        flag("STRETCHED_MA","watch","短線漲幅過急","距MA20達6%以上、近5日漲幅8%以上；先審視拉回風險，此門檻尚未通過獨立回測。")
    if float(risk.get("foreign") or 0)<-300:
        flag("FOREIGN_OUTFLOW","info","單日外資明顯賣超","外資單日賣超超過300億，可能造成分數跳動；不可用單日法人數據推論長期走勢。")
    score=float(risk["score"]);top=str(risk.get("topState") or "");bottom=str(risk.get("bottomState") or "")
    strongTop=top in ("🔴 Strong Top Reversal","🟠 Top Reversal Attempt")
    extremeHeat=top=="🔴 Extreme Overbought"
    strongBottom=bottom=="🟢 Strong Bottom Reversal"
    # Priority determines action; pure research-only flags do not silently
    # replace documented F/F2 gate logic.
    if strongTop:
        level,head,action="STOP","⛔ 暫緩新倉｜頂部反轉警戒","先控制追價風險，待轉弱訊號解除再確認個股。"
    elif extremeHeat:
        level,head,action="CAUTION","🟠 過熱，避免追高","市場過熱；等待個股整理或風險降低，並非強制全部出清。"
    elif score<60 and strongBottom:
        level,head,action="REVERSAL","🟣 超跌反轉候選","僅能個別評估 Bottom 及停損，不是一般強勢股進場許可。"
    elif score<40 and (finite(risk.get("oversoldScore")) or 0)>=3:
        level,head,action="REVERSAL","🟣 超跌觀察｜尚未確認反轉","低分可能持續下跌，先等 Strong Bottom Reversal 與個股訊號。"
    elif score<50:
        level,head,action="STOP","🔴 暫不建議一般新倉","市場尚未達到60分基準；等待趨勢回升或另行確認反轉。"
    elif score<60:
        level,head,action="WAIT","🟡 觀察等待｜未達進場門檻","50–59分屬中性偏弱，先觀察市場參與度與個股訊號。"
    elif any(x["code"] in ("NEAR_HIGH_TOP","STRETCHED_MA") for x in flags) or volrank>=90 or (scoreChange<=-20 and b5<50):
        level,head,action="CAUTION","🟠 趨勢合格，但不宜立即追高","Risk Score已過60，但短線過熱、近壓力或高波動，優先等可控的個股買點。"
    elif score>=80:
        level,head,action="READY","🟢 強勢｜可評估新倉","市場趨勢符合條件；仍需個股 G/D 訊號、進場價、停損與部位控管。"
    else:
        level,head,action="READY","🟢 達基準｜可評估新倉","趨勢分數≥60，未見上述主要風險否決；仍需個股訊號確認。"
    historical=rows[-2] if len(rows)>1 else {}
    output={"version":VERSION,"asOf":d,"riskScore":risk["score"],"originalRiskState":risk.get("state"),"marketMode":risk.get("mode"),
        "marketHealth":{"breadthTodayPct":round(breadth[-1],1),"breadth5Pct":round(b5,1),
            "breadth10Pct":round(b10,1),"breadthChangeVsPrev5Pts":round(b5-prev5,1),
            "advanceDecline10Sum":int(ad10),"indexRet10Pct":round(per10,2) if per10 is not None else None,
            "indexBreadthDivergence":bool(divergence),"riskScore3MA":round(smoothed,1),
            "riskScore5SessionChange":scoreChange,"realizedVol20AnnualPct":round(annual,1),
            "volatilityHistoryPercentile":round(volrank,1),
            "distancePrior120HighPct":round(highDist,2) if highDist is not None else None,
            "prior120HighType":highType,"distanceMA20Pct":round(gap,2),
            "previousScore":historical.get("score"),"sourceHistoryDays":len(rows)},
        "decision":{"level":level,"headline":head,"action":action,
            "primaryGate":">=60 Risk Score, with separate Strong Bottom exception",
            "flags":flags,
            "scope":"盤後下一交易日的個股進場評估，不是當日即時交易許可"},
        "research":{"model":"Market ML v1 2026 chronological study",
            "mlNotUsedToGate":True,
            "cautionFiltersValidatedForStockBuying":False,
            "reason":"Original score weights and A/D/F/G production gates must remain unchanged until independent portfolio tests prove added edge"}}
    return output
def build_for_live(risk,root):
    return compute(risk,history(root,risk))
def save_for_live(risk,root,diagnostics=None):
    """Call only when official *new* market session is successfully published."""
    root=Path(root);directory=root/"research"/"market_intelligence";directory.mkdir(parents=True,exist_ok=True)
    archive=read(root/"research"/"g_regime_3y"/"market_risk_daily.json",[])
    frozen_dates={x["date"] for x in archive}
    delta=[x for x in read(directory/"history_delta.json",[]) if x.get("date") and x["date"] not in frozen_dates]
    if risk["date"] not in frozen_dates:
        delta=[x for x in delta if x["date"]!=risk["date"]]+[dict(risk)]
        delta.sort(key=lambda x:x["date"])
        (directory/"history_delta.json").write_text(json.dumps(delta,ensure_ascii=False,indent=2),encoding="utf-8")
    diagnostics=diagnostics or build_for_live(risk,root)
    (directory/"latest.json").write_text(json.dumps(diagnostics,ensure_ascii=False,indent=2,allow_nan=False),encoding="utf-8")
    return diagnostics
if __name__=="__main__":
    root=Path(__file__).resolve().parents[1]/"docs"/"data"
    latest=read(root/"latest.json",{})
    risk=latest.get("risk")
    if not isinstance(risk,dict):raise RuntimeError("No published risk snapshot")
    v=build_for_live(risk,root)
    out=root/"research"/"market_intelligence";out.mkdir(parents=True,exist_ok=True)
    (out/"latest.json").write_text(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False),encoding="utf-8")
    print("MARKET_INTELLIGENCE_BUILT",json.dumps({"asOf":v["asOf"],"risk":v["riskScore"],"decision":v["decision"]["level"],
       "marketHealth":v["marketHealth"],"flags":[z["code"] for z in v["decision"]["flags"]]},ensure_ascii=False),flush=True)
