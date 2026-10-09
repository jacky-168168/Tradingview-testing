"""Publish previously executed, independently verified ETF backtests to GitHub Pages.
Read immutable study data from original research branches (do NOT rerun/tune models).
Creates normalized /docs/data/research/etf_history/index.json, grid and 43 lazy curves.
"""
from __future__ import annotations
import json,math,re,subprocess
from pathlib import Path
from datetime import datetime, timezone

ROOT=Path(__file__).resolve().parents[1]
TARGET=ROOT/"docs"/"data"/"research"/"etf_history"
REPO="https://github.com/jacky-168168/Tradingview-testing"
SRC={
 "00675_2018":("research/00675l-vwma5-vs-sma10-2018-2026","tw-stock-dashboard/docs/data/research/etf_00675l_vwma5_sma10_2018_2026", "summary.json","trades_and_equity.json"),
 "ma_family":("research/00675l-ma-family-2020-2026","tw-stock-dashboard/docs/data/research/etf_00675l_ma_family_2020_2026","summary.json","finalist_trades_daily_equity.json"),
 "qqq_vt":("research/qqq-vt-sma10-vwma5-2018-2026","tw-stock-dashboard/docs/data/research/qqq_vt_sma10_vwma5_2018_2026","summary.json","transactions_equity.json"),
 "qld":("research/qld-2018-2026-sma10-vwma5","tw-stock-dashboard/docs/data/research/qld_sma10_vwma5_2018_2026","summary.json","daily_equity_and_orders.json")
}
def read_branch(branch,path):
    p=subprocess.run(["git","show","origin/"+branch+":"+path],cwd=ROOT,capture_output=True,check=True)
    return json.loads(p.stdout)
def load(id):
    br,dir,s,t=SRC[id]
    return read_branch(br,dir+"/"+s),read_branch(br,dir+"/"+t)
def fmtname(id,asset):
    name={"BUY_HOLD":"買進持有","BUY_HOLD_QLD":"QLD 買進持有",
      "SMA10_index_original_2_1":"台指 SMA10（2%／1%）",
      "VWMA5_index_equal_2_1":"台指 VWMA5（2%／1%）",
      "VWMA5_index_alternative_1_2":"台指 VWMA5（1%／2%）",
      "SMA10_2out_1in_c3":"SMA10（2%／1%）",
      "VWMA5_2out_1in_c3":"VWMA5（2%／1%）",
      "VWMA5_1out_2in_c3":"VWMA5（1%／2%）",
      "QLD_SMA10":"QLD SMA10（2%／1%）",
      "QLD_VWMA5":"QLD VWMA5（2%／1%）",
      "QLD_VWMA5_ALT_1_2":"QLD VWMA5（1%／2%）",
      "QQQ_SIGNAL_SMA10":"用 QQQ SMA10 操作 QLD",
      "QQQ_SIGNAL_VWMA5":"用 QQQ VWMA5 操作 QLD"}.get(id)
    if name:return name
    m=re.match(r"^(SMA|EMA|WMA|VWMA)_(twii|close)_N?(\d+)_OUT(\d+)_RE(\d+)_C(\d+)",id)
    if m:return f"{'台指' if m[2]=='twii' else '00675L自身'} {m[1]}{m[3]}（跌{m[4]}%／回{m[5]}%／{m[6]}日確認）"
    return str(id)
def annual(n):
    out=[]
    for year,v in sorted(n.items()):
        twd=v.get("endAccountTWD",v.get("closingNTD"))
        usd=v.get("endAccountUSD")
        ret=v.get("TWDAnnualReturnPct",v.get("annualNetReturnPct",v.get("returnPct")))
        out.append({"year":year,"pct":ret,"wealthTWD":twd,"wealthUSD":usd,
          "usdPct":v.get("USDAnnualReturnPct")})
    return out
def entry(study,id,title,endTWD,ret,mdd,exitN,rebuyN,cashN,years,detail,period,unit="TWD",notes="",group=""):
    safe=re.sub(r"[^a-zA-Z0-9_-]","_",study+"__"+id)
    assert safe==study+"__"+id,("Invalid ID",id)
    curvefile="curves/"+safe+".json"
    points=detail["points"];orders=detail["orders"]
    assert points and points[-1].get("date")==period[1]
    assert len(points)==detail["sessions"]
    end_val=float(points[-1]["equity"])
    if unit=="TWD":assert math.isclose(end_val,endTWD,abs_tol=.10),(study,id,end_val,endTWD)
    else:assert abs(end_val-detail["endUSD"])<.10
    compactpoints=[[x["date"],round(float(x["equity"]),2)] for x in points]
    compactorders=[]
    for x in orders:compactorders.append([x.get("date"),x.get("side"),x.get("phase"),
          x.get("units"),x.get("openPrice"),x.get("cashFlow"),x.get("accountCash")])
    TARGET.joinpath("curves").mkdir(parents=True,exist_ok=True)
    TARGET.joinpath(curvefile).write_text(json.dumps({"study":study,"id":id,"currency":unit,
      "columns":["date","equity"],"points":compactpoints,
      "tradeColumns":["date","side","phase","units","unitPrice","cashFlow","cashAfter"],
      "trades":compactorders},ensure_ascii=False,separators=(",",":")),encoding="utf-8")
    return {"id":id,"name":title,"group":group,"endTWD":round(float(endTWD),2),
      "returnPct":round(float(ret),3),"mddPct":round(float(mdd),3),
      "sells":int(exitN),"rebuys":int(rebuyN),"cashDays":int(cashN),
      "sessions":len(points),"annual":annual(years),
      "curve":curvefile,"curveCurrency":unit,"notes":notes}
def record(study,title,description,period,sessions,models,br,data_dir,run,warnings,extra=None):
    assert models and len(set(m["id"] for m in models))==len(models),(study,"duplicate models")
    for m in models:assert m["sessions"]==sessions,(study,m["id"],m["sessions"],sessions)
    v={"id":study,"title":title,"description":description,
      "period":period,"sessions":sessions,"models":models,"warnings":warnings[:6],
      "sourceBranch":br,
      "sourceSummary":REPO+"/blob/"+br+"/"+data_dir+"/summary.json",
      "sourceExecution":REPO+"/actions/runs/"+str(run)}
    if extra:v.update(extra)
    return v
def main():
    TARGET.mkdir(parents=True,exist_ok=True)
    records=[]

    # Taiwan 00675L with 2018 inception window.
    s,e=load("00675_2018");br,dir,*_=SRC["00675_2018"]
    period=["2018-01-02","2026-10-07"]
    models=[]
    for c in s["cases"]:
        id=c["id"];detail=e["cases"][id];a=c["continuous2018_2026"]
        models.append(entry("00675_2018",id,fmtname(id,"00675L"),
            a["endNTD"],a["returnPct"],a["mddPct"],a["riskOffSells"],a["riskOnReentries"],
            a["riskOffSessions"],c["calendarYearsContinuous"],
            {"points":detail["dailyEquity"],"orders":detail["orders"],
             "sessions":a["sessions"]},period,
            notes="以台股加權指數 ^TWII 為均線訊號；成交標的為 00675L。" if id!="BUY_HOLD" else "00675L 買進持有，最後一日假設平倉。",group="00675L"))
    assert next(m for m in models if m["id"]=="SMA10_index_original_2_1")["returnPct"]==4110.755
    records.append(record("00675_2018","00675L｜2018～2026 SMA10 vs VWMA5",
        "台股每日正2｜100萬台幣本金、不跨年重置；加權指數計算均線，隔日開盤操作 00675L。",
        period,s["quality"]["totalTradingDays"],models,br,dir,37873221410,s["warnings"],
        {"dataQuality":"^TWII 2018～2026 有8日缺成交量；VWMA5 因滾動缺值而暫停產生訊號的交易日數為29。"}))

    # 2020-26 MA family; prior 4,320 fits in training-only grid; 24 frozen candidates validated.
    s,e=load("ma_family");br,dir,*_=SRC["ma_family"];period=["2020-01-02","2026-10-07"]
    models=[]
    baseline=s["baseline"]["buyHold2020_2026"]
    detail=e["buyhold"]
    models.append(entry("ma_family","BUY_HOLD","買進持有",baseline["endNTD"],
        baseline["returnPct"],baseline["mddPct"],0,0,0,s["baseline"]["buyHoldCompoundedYears"],
        {"points":detail["equity"],"orders":detail["transactions"],"sessions":baseline["sessions"]},period,
        group="00675L"))
    for c in s["finalists"]:
        id=c["id"];stats=c["continuous2020_2026"];detail=e["candidates"][id]
        models.append(entry("ma_family",id,fmtname(id,"00675L"),
            stats["endNTD"],stats["returnPct"],stats["mddPct"],
            stats["riskOffSells"],stats["riskOnReentries"],stats["riskOffSessions"],
            c["compoundedYears"],
            {"points":detail["equity"],"orders":detail["transactions"],"sessions":stats["sessions"]},period,
            notes=("與原 SMA10 相同門檻，僅更換 MA 公式／訊號來源" if c["selection"]=="apples_to_apples" else
                 "以2020～2023訓練結果挑選候選，再檢驗2024～2026；需留意過度擬合。"),
            group="台指" if c["signalSource"]=="twii" else "00675L自身"))
    assert len(models)==25 and s["nTrainModels"]==4320
    training=read_branch(br,dir+"/all_training_results.json")
    grid={"version":"00675L_MA_2020_2023_TRAINING_V1",
       "note":"只有2020～2023訓練期績效，4,320組並非完整2020～2026各自逐日驗證；2024～2026僅驗證24組凍結候選。",
       "cols":["id","family","signalSource","window","sellPct","rebuyPct","confirmDays","trainReturnPct","trainMddPct","trainSellN","trainScore"],
       "rows":[[z["id"],z["maType"],z["signalSource"],z["window"],z["sellBufferPct"],z["rebuyBufferPct"],
             z["confirmationDays"],z["training2020_2023"]["returnPct"],z["training2020_2023"]["mddPct"],
             z["training2020_2023"]["riskOffSells"],z["score2020_23"]] for z in training["results"]]}
    assert len(grid["rows"])==4320
    TARGET.joinpath("grid.json").write_text(json.dumps(grid,ensure_ascii=False,separators=(",",":")),encoding="utf-8")
    records.append(record("ma_family","00675L｜2020～2026 SMA／EMA／WMA／VWMA",
        "四類均線、台指與 ETF 訊號；4,320組只用2020～2023訓練選參數，24組凍結候選檢驗到2026。",
        period,s["sessions2020_2026"],models,br,dir,37872432516,s["warnings"],
        {"trainingGrid":"grid.json","trainingModels":s["nTrainModels"],
         "extraSource":REPO+"/actions/runs/37872656678",
         "dataQuality":"台指 VWMA 使用台股加權指數自身成交量，不與00675L成交量混用。"}))

    # QQQ and VT: already tested with FX, take TWD performance and USD curve.
    s,e=load("qqq_vt");br,dir,*_=SRC["qqq_vt"];period=["2018-01-02","2026-10-07"]
    models=[]
    for c in s["results"]:
        id=c["ticker"]+"__"+c["strategy"];detail=e["traces"][c["ticker"]][c["strategy"]]
        models.append(entry("qqq_vt",id,c["ticker"]+"｜"+fmtname(c["strategy"],c["ticker"]),
            c["finalTWD"],c["netReturnTWD"],c["maxDDTWD"],
            c["riskOffSells"],c["riskOnReentries"],c["riskOffSessions"],c["yearlyContinuous"],
            {"points":detail["equityUSD"],"orders":detail["ordersUSD"],"sessions":c["sessions"],
             "endUSD":c["finalUSD"]},period,unit="USD",
            notes="使用 "+c["ticker"]+" 自身 ETF 收盤價與成交量作訊號；圖表為美元帳戶，總績效與年度表為換算台幣。",
            group=c["ticker"]))
    assert len(models)==8
    records.append(record("qqq_vt","QQQ＋VT｜2018～2026 買入持有與均線",
        "美股非槓桿ETF｜100萬台幣先換美元，全額複投；年度報酬及期末資產已依美元／台幣匯率換算。",
        period,s["assets"]["QQQ"]["nSessions"],models,br,dir,37884654679,s["warnings"],
        {"dataQuality":"資金曲線顯示美元帳戶；表格報酬與年度資產顯示台幣。未扣海外股息預扣稅或實際換匯價差。"}))

    # QLD daily 2x, own-price or QQQ market signal, equity denominated USD.
    s,e=load("qld");br,dir,*_=SRC["qld"];period=["2018-01-02","2026-10-07"]
    models=[]
    for c in s["strategies"]:
        id=c["id"];detail=e["simulations"][id]
        models.append(entry("qld",id,fmtname(id,"QLD"),
            c["endTWD"],c["totalReturnTWD"],c["maxDrawdownTWD"],
            c["riskOffSells"],c["riskOnReentries"],c["daysInCash"],
            c["yearByYearCompounded"],
            {"points":detail["dailyEquityUSD"],"orders":detail["ordersUSD"],
             "sessions":c["sessions"],"endUSD":c["endUSD"]},period,
            unit="USD",group=c["signalTicker"],
            notes="使用 "+c["signalTicker"]+" 計算均線進出場，真正交易 QLD；每日正2，不等於長期QQQ兩倍。圖表為美元帳戶，總績效為台幣。"))
    assert len(models)==6
    records.append(record("qld","QLD｜2018～2026 美股正2",
        "Nasdaq-100 每日正2｜比較長抱、QLD 自身均線、使用 QQQ 均線操作 QLD。",
        period,s["USSessions"],models,br,dir,37886431920,s["warnings"],
        {"dataQuality":"每日兩倍槓桿；最大回撤很大。圖表是美元現金權益，年度表與總報酬換算台幣。"}))

    # Cross-study audit; all have same calendar start/end except MA archive.
    assert all(x["period"]==["2018-01-02","2026-10-07"] for x in records if x["id"]!="ma_family")
    assert next(v for v in models if v["id"]=="BUY_HOLD_QLD")["returnPct"]==1069.663
    assert next(v for v in records if v["id"]=="qqq_vt")["models"][0]["returnPct"]==444.202
    index={"version":"ETF_ARCHIVE_2026_10_09_V1","generatedAtUTC":datetime.now(timezone.utc).isoformat(),
      "purpose":"Static read-only existing research; not automatic new trading signals",
      "currencyPolicy":"臺灣ETF曲線為新臺幣；美股ETF曲線為美元。美股每年及總績效已以美元/臺幣即期匯率換算臺幣。",
      "assumptions":"本金新臺幣100萬，全額複投；訊號收盤後產生、下一交易日開盤成交；每側券商費0.1425%、模擬滑價0.1%；00675L另有賣出ETF稅0.1%，美股無此台灣ETF稅。",
      "allocationBacktestStatus":"00675L+QQQ+VT (30/25/45) 投資組合尚未執行，請勿將個別策略收益視為組合績效。",
      "studyOrder":["00675_2018","ma_family","qld","qqq_vt"],"studies":records}
    TARGET.joinpath("index.json").write_text(json.dumps(index,ensure_ascii=False,separators=(",",":")),encoding="utf-8")
    sample=list(TARGET.rglob("*.json"))
    assert len(sample)==1+1+4+25+8+6,len(sample)
    print("PASS ETF_ARCHIVE_GENERATED "+json.dumps({"studies":len(records),"models":[(r["id"],len(r["models"])) for r in records],
      "fullTrainingGrid":len(grid["rows"]),"publishedJsonFiles":len(sample),
      "archiveBytes":sum(z.stat().st_size for z in sample)},ensure_ascii=False),flush=True)
if __name__=="__main__":main()
