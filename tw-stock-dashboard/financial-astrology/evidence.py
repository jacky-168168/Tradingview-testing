"""Research evidence gates: conservative labels, never an automatic trade recommendation."""
from __future__ import annotations
import math

def evidence_for_horizon(row):
    """Only actual observed returns are eligible for a market-specific evidence label."""
    n = row.get("sampleSize", 0)
    q = row.get("fdrQValue")
    ci = row.get("excessConfidence95")
    hold = row.get("holdout") or {}
    delta = row.get("excessReturn")
    if not isinstance(n,int) or n<=0:
        return {"level":"unavailable","label":"尚無資料","direction":"無法判定",
            "historicalTendency":"無資料","reason":"未取得有效歷史行情與事件樣本，沒有可核實的勝率。"}
    historical = ("歷史平均相對較強" if delta>0 else "歷史平均相對較弱" if delta<0
                  else "歷史平均差異不明顯") if isinstance(delta,(int,float)) and math.isfinite(delta) else "無法比較"
    if n<10:
        level,label,reason="very_low","可信度極低","不足10次歷史事件，無法可靠估計預測能力。"
    elif n<30:
        level,label,reason="low","可信度低","不到30次歷史事件，只能做探索性觀察；不能宣稱具有統計優勢。"
    elif not isinstance(q,(float,int)) or q>=.05:
        level,label,reason="unconfirmed","未通過統計檢定","多重檢定修正後沒有足夠證據支持事件與基準有差異。"
    elif not (isinstance(ci,list) and len(ci)==2 and all(isinstance(v,(float,int)) and math.isfinite(v) for v in ci)):
        level,label,reason="unconfirmed","尚未驗證","尚無可以檢查的超額報酬信賴區間。"
    elif ci[0]<=0<=ci[1]:
        level,label,reason="unconfirmed","尚未驗證","超額報酬的信賴區間包含零，優勢不穩定。"
    elif hold.get("holdoutCount",0)<10:
        level,label,reason="preliminary","初步觀察","統計結果仍缺乏足夠的時間留出樣本；尚非獨立樣本外驗證。"
    elif not isinstance(delta,(float,int)) or not isinstance(hold.get("holdoutMean"),(float,int)):
        level,label,reason="unconfirmed","尚未驗證","缺少時間留出樣本的獨立基準比較。"
    else:
        level,label,reason="preliminary","初步統計關聯","通過部分探索檢驗，但尚未通過預註冊策略與獨立樣本外驗證。"
    return {"level":level,"label":label,"direction":"無法判定",
        "historicalTendency":historical,"reason":reason+
        " 占星事件與股市報酬可能只是相關，不代表因果或交易訊號。"}

def attach_evidence(rows):
    for row in rows:
        row["evidence"]=evidence_for_horizon(row)
    return rows
