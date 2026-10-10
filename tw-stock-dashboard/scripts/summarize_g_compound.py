"""Compact decision-grade audit for published G Compound, no re-fitting.
Read fully published 1728-scenario JSON, publish small highlights for people
and public Pages without fetching 5.6 MB summary on every page load.
"""
from __future__ import annotations
import csv,json,math
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"docs/data/research/g_compound_3y"
def slim(m):
    return {k:m.get(k) for k in ("capitalEnd","netReturnPct","maxDDPct","entryOffers","filledBuys",
      "closedTrades","wins","losses","winPct","avgNetPct","avgWinPct",
      "avgLossPct","avgHoldSessions","openAtEnd","cashAtEnd","netUnrealizedTWD")}
def brief(x):
    return {"id":x["id"],"params":x["params"],
       "train":slim(x["byPeriod"]["train"]),
       "validation":slim(x["byPeriod"]["validation"]),
       "audit2026":slim(x["byPeriod"]["audit2026"]),
       "authorWindow2026":slim(x["byPeriod"]["authorWindow2026"]),
       "full":slim(x["byPeriod"]["all"])}
def main():
    s=json.loads((OUT/"summary.json").read_text(encoding="utf-8"))
    t=json.loads((OUT/"trades.json").read_text(encoding="utf-8"))
    e=json.loads((OUT/"equity.json").read_text(encoding="utf-8"))
    assert s["totalCases"]==1728 and len(s["models"])==1728
    assert s["riskScoreCoverage"]==728
    assert t["version"]==e["version"]==s["version"]
    sel=s["selectionFromTrainValidationOnly"]
    chosen=next((x for x in s["models"] if x["id"]==sel.get("id")),None)
    if sel["status"]=="selected_without_2026" and chosen is None:raise RuntimeError("Selected model missing")
    seq=list(s["models"])
    period="authorWindow2026"
    o=sorted(seq,key=lambda x:x["byPeriod"][period]["netReturnPct"],reverse=True)
    author=s["authorDisclosure"]
    target=author["impliedWealthWithoutNetDepositsTWD"]
    claim_t=author["claimedClosedTickets"];claim_w=author["claimedWinningTickets"]
    reached=[x for x in seq if x["byPeriod"][period]["capitalEnd"]>=target]
    near_records=[x for x in seq if x["byPeriod"][period]["closedTrades"]>=claim_t]
    win_match=[x for x in seq if x["byPeriod"][period]["wins"]>=claim_w and x["byPeriod"][period]["closedTrades"]>=claim_t]
    realistic_200=[x for x in o if x["params"]["maxPerEntryTWD"]==200000]
    realistic_500=[x for x in o if x["params"]["maxPerEntryTWD"]==500000]
    worst_o=sorted(seq,key=lambda x:x["byPeriod"][period]["netReturnPct"])[:3]
    baseline=[x for x in seq if x["params"]["riskGate"]=="SCORE60"
      and x["params"]["targetPct"]==5 and x["params"]["stopPct"]==8
      and x["params"]["maxHoldTradingDays"]==5]
    # include exactly the 3 selectors x 3 capacity types at unoptimized common baseline
    assert len(baseline)==9
    report={"version":"G_COMPOUND_HIGHLIGHTS_FROM_LOCKED_V1",
      "mainVersion":s["version"],"generatedFrom":s["createdAt"],
      "riskScoreCoverage":s["riskScoreCoverage"],
      "modelCount":s["totalCases"],"stockHistoryErrors":s["stockHistoryErrors"],
      "selectorSignalDays":s["selectorSignalDays"],
      "authorWindow":s["trainingWindows"]["authorWindow2026"],
      "author":author,"selectedTrainValidationOnly":brief(chosen) if chosen else None,
      "selectedStatus":sel["status"],"selectorThresholds":sel,
      "hindsightTop5":[brief(x) for x in o[:5]],
      "hindsightWorst3":[brief(x) for x in worst_o],
      "hindsightTop200k":brief(realistic_200[0]),
      "hindsightTop500k":brief(realistic_500[0]),
      "standardBaselines":[brief(x) for x in baseline],
      "authorAchievementCounts":{"startingCapitalTWD":500000.,
        "targetFinalAssetTWD":target,"claim52ClosedTrades":claim_t,
        "claim51Winners":claim_w,"casesWithFinalAssetAtLeastClaim":len(reached),
        "casesWithAtLeast52ClosedTrades":len(near_records),
        "casesWithAtLeast51WinnersFromAtLeast52ClosedTrades":len(win_match),
        "casesTested":len(seq)},
      "warnings":["The article's secret ranking, risk score, target, loss, and sizing are not known.",
        "Hindsight-best 2026 is not a viable investment forecast.",
        "Selected family was tuned during earlier G research; temporal split is not a new genuinely blind study.",
        "Historical Yahoo daily adjusted OHLC cannot resolve exact intraday order queuing and fills.",
        "Current universe excludes delisted stocks and present paid-in-capital induces survivorship bias.",
        "Cash at period end and net-valued open positions distinguish realized from unrealized gains.",
        "As-of historical risk score excludes unverified night futures."]}
    (OUT/"highlights.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    with (OUT/"comparison.csv").open("w",encoding="utf-8-sig",newline="") as fp:
        w=csv.writer(fp)
        w.writerow(["id","selector","riskGate","targetPct","stopPct","maxHoldTradingDays","capacityTWD",
            "2023_24_netReturnPct","2025_netReturnPct","2026_authorPeriod_netReturnPct",
            "2026_authorPeriod_endingTWD","2026_authorPeriod_closedTrades",
            "2026_authorPeriod_winPct","2026_authorPeriod_maxDDPct",
            "2026_authorPeriod_unclosedPositions"])
        for x in seq:
            p=x["params"];v=x["byPeriod"][period]
            w.writerow([x["id"],p["selector"],p["riskGate"],p["targetPct"],p["stopPct"],
              p["maxHoldTradingDays"],p["maxPerEntryTWD"],
              x["byPeriod"]["train"]["netReturnPct"],x["byPeriod"]["validation"]["netReturnPct"],
              v["netReturnPct"],v["capitalEnd"],v["closedTrades"],v["winPct"],v["maxDDPct"],v["openAtEnd"]])
    print("G_COMPOUND_HIGHLIGHTS",json.dumps({"selected":report["selectedTrainValidationOnly"],
      "authorAchievementCounts":report["authorAchievementCounts"],"top200k":report["hindsightTop200k"],
      "top500k":report["hindsightTop500k"],"bestHindsight":report["hindsightTop5"][0],
      "standardBaselines":report["standardBaselines"]},ensure_ascii=False),flush=True)
if __name__=="__main__":main()
