"""Append genuine PLTR Sep 2020-Oct 2026 model runs to the already-published
ETF/asset research index without changing or rerunning existing 43 strategies.
Requires fetched origin/research/pltr-2020-2026-rotation-comparison branch.
"""
from pathlib import Path
import subprocess,json,math,re
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/"docs"/"data"/"research"/"etf_history"
REF="research/pltr-2020-2026-rotation-comparison"
PATH="tw-stock-dashboard/docs/data/research/pltr_2020_2026/"
REPO="https://github.com/jacky-168168/Tradingview-testing/"
def load(relative):
    p=subprocess.run(["git","show",f"origin/{REF}:{PATH}{relative}"],cwd=ROOT,capture_output=True,check=True)
    return json.loads(p.stdout)
def humanize(model):
    id=model["id"];c=model["config"]
    if id=="BUY_HOLD":return "PLTR 買進持有（上市首日開始）"
    if id.startswith("DONCHIAN"):return "唐奇安通道｜跌破20日低點賣、站上55日高點買"
    if id.startswith("TRAIL"):return f'移動停利｜回撤{int(c["trailPct"]*100)}%出場、EMA{c["ema"]}買回'
    if id.startswith("DUAL"):return f'雙均線｜EMA{c["fast"]}／EMA{c["slow"]}趨勢輪動'
    down=round(c["down"]*100);up=round(c["up"]*100)
    return f'PLTR {c["family"]}{c["window"]}｜跌{down}%／回{up}%／確認{c["confirm"]}日'
def run():
    s=load("summary.json");full=load("daily_equity_orders.json")
    assert s["version"]=="PLTR_2020_2026_FULL_100W_TWD_V1"
    assert s["unsupportedYears"]==["2018","2019"]
    assert s["period"]==["2020-09-30","2026-10-08"]
    indexPath=BASE/"index.json";idx=json.loads(indexPath.read_text(encoding="utf-8"))
    old=[z for z in idx["studies"] if z["id"]!="pltr"]
    assert len(old)==4,("Existing ETF history must be intact",len(old))
    assert sum(len(z["models"]) for z in old)==43
    models=[]
    for m in s["models"]:
        id=m["id"];data=full["cases"][id];funds=data["equity"];orders=data["orders"]
        q=m["full"];years=m["years"]
        assert len(funds)==s["totalSessions"]==1513
        assert math.isclose(funds[-1]["accountTWD"],q["endTWD"],abs_tol=.05)
        assert math.isclose(funds[-1]["accountUSD"],q["endUSD"],abs_tol=.05)
        assert len(years)==7
        file=f"curves/pltr__{id}.json"
        lastcash=float(s["assumptions"]["startingCapitalUSD"])
        hist=[]
        for t in orders:
            cash=float(t["cashUSD"])
            hist.append([t["date"],t["side"],t["phase"],t["units"],t["price"],round(cash-lastcash,2),cash])
            lastcash=cash
        BASE.joinpath(file).write_text(json.dumps({
            "study":"pltr","id":id,"currency":"USD","columns":["date","equity"],
            "points":[[t["date"],round(float(t["accountUSD"]),2)] for t in funds],
            "tradeColumns":["date","side","phase","units","unitPrice","cashFlow","cashAfter"],
            "trades":hist},ensure_ascii=False,separators=(",",":")),encoding="utf-8")
        annual=[{"year":year,"pct":z["returnTWD"],"wealthTWD":z["endTWD"],
                "wealthUSD":z["endUSD"],"usdPct":z["returnUSD"]} for year,z in years.items()]
        is_train=m["selection"]=="training_2020_2023"
        models.append({"id":id,"name":humanize(m),"group":"早期訓練選出" if is_train else "事先固定比較",
            "endTWD":q["endTWD"],"returnPct":q["returnTWD"],"mddPct":q["mddTWD"],
            "sells":q["sells"],"rebuys":q["rebuys"],"cashDays":q["daysCash"],"sessions":q["sessions"],
            "annual":annual,"curve":file,"curveCurrency":"USD",
            "notes":("2020～2023年選出的候選規則，之後才檢查2024～2026。"
              if is_train else "未用2024～2026調參的固定比較規則。")+
              " PLTR只有2020/9/30上市後資料；曲線與交易是美元、績效已換算台幣。"})
    assert len(models)==len(s["models"])==23
    assert next(z for z in models if z["id"]=="BUY_HOLD")["returnPct"]==2078.847
    assert next(z for z in models if z["id"]=="WMA200_D10_U0_C3")["returnPct"]==4153.868
    study={"id":"pltr","title":"PLTR｜2020上市～2026 個股趨勢策略",
       "description":"Palantir 美股單一公司｜2018～2019尚未上市，從2020/9/30首次公開交易日開始回測。100萬台幣先換美元，全額複投；比較長抱、短中長均線、移動停利、唐奇安通道。",
       "period":s["period"],"sessions":s["totalSessions"],"models":models,
       "warnings":s["warnings"][:6],"sourceBranch":REF,
       "sourceSummary":REPO+"blob/"+REF+"/"+PATH+"summary.json",
       "sourceExecution":REPO+"actions/runs/37909045646",
       "dataQuality":"2020/9/30上市；2026/10/8收盤結束；共1513交易日。固定比較與2020～23訓練選出的候選分開顯示。2,400組網格中有2,370組符合至少2次風險賣出；最好的歷史組合存在過度擬合風險。美股曲線為美元，表格報酬已換算台幣。"}
    idx["studies"]=old+[study]
    idx["studyOrder"]= [z["id"] for z in idx["studies"]]
    idx["version"]="ASSET_ARCHIVE_2026_10_09_PLTR_V2"
    idx["purpose"]="Permanent read-only ETF and individual-stock backtest archives; not realtime trading advice"
    idx["currencyPolicy"]="台股ETF曲線新臺幣；美股ETF與PLTR曲線美元；美股期末資產、逐年績效以當日美元/新臺幣匯率計算。"
    indexPath.write_text(json.dumps(idx,ensure_ascii=False,separators=(",",":")),encoding="utf-8")
    assert sum(len(z["models"]) for z in idx["studies"])==66
    assert all(len(z["models"])==k for z,k in zip(idx["studies"],[4,25,8,6,23]))
    print("PASS PLTR_WEB_ARCHIVE "+json.dumps({"newStudy":"pltr",
       "publishedModels":len(models),"totalStudies":len(idx["studies"]),
       "totalModels":sum(len(z["models"]) for z in idx["studies"]),
       "allDailyPLTR":len(models)*1513,"existingUntouched":43,
       "dataEnd":"2026-10-08"},ensure_ascii=False))
if __name__=="__main__":run()
