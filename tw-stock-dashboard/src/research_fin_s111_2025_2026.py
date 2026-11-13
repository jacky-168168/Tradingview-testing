"""Exact public FinPilot S111 screening recipe, NOT a surrogate.
See https://github.com/hu0937/FinPilot/blob/main/agents/strategies/
Requires FINLAB_API_TOKEN and FinLab datasets including paid broker balance_index.
Runs independently of G-R1..4 and never fills missing BI/operating-income/dividend fields.
"""
from __future__ import annotations
import json,os,traceback
from datetime import datetime
from zoneinfo import ZoneInfo
from config import DATA_DIR
OUT=DATA_DIR/"research"/"g_r_fin_2024_2026"
FIRST="2025-01-01";LAST="2026-10-12"
def make_record(status,reason=None,results=None,coverage=None):
    OUT.mkdir(parents=True,exist_ok=True)
    record={"strategy":"Fin","version":"FINPILOT_S111_ORIGINAL_RULES_V1",
      "period":{"start":FIRST,"end":LAST},
      "generatedAt":datetime.now(ZoneInfo("Asia/Taipei")).isoformat(),
      "status":status,"reason":reason,"source":"hu0937/FinPilot agents/strategies/s111",
      "conditions":["20D average shares traded > 100000","operating profit growth > 0",
        "close >= highest prior 40 close","average recent 3m revenue / prior 12m revenue > 1.1",
        "broker balance_index > 0.52"],
      "ranking":"Dividend yield descending, top 5",
      "execution":{"rebalance":"monthly M","tradeAt":"next open as FinLab engine implements","positionLimit":0.2,
         "brokerFeeEachSide":0.001425,"sellTax":0.003},
      "statistics":results,"coverage":coverage,
      "note":"Exact source strategy formula; 2025-2026 results do not inherit author claimed 2018-2022/OOS metrics"}
    (OUT/"fin_s111.json").write_text(json.dumps(record,ensure_ascii=False,indent=2,default=str),encoding="utf-8")
    print("FIN_S111_"+status.upper(),reason or (results or {}).get("full",""),flush=True)
def main():
    token=os.environ.get("FINLAB_API_TOKEN")
    if not token:
        make_record("not_run","FINLAB_API_TOKEN absent; paid historical BI cannot be reconstructed from price/volume")
        return
    try:
        import finlab
        from finlab import data
        from finlab.backtest import sim
        finlab.login(token)
        close=data.get("price:收盤價")
        volume=data.get("price:成交股數")
        operating=data.get("fundamental_features:營業利益成長率")
        revenue=data.get("monthly_revenue:當月營收")
        bi=data.get("etl:broker_transactions:balance_index")
        yield_pct=data.get("price_earning_ratio:殖利率(%)")
        cond=(volume.average(20)>100000)&(operating>0)&(
            close>=close.rolling(40).max().shift(1))&(
            revenue.average(3)/revenue.average(12)>1.1)&(bi>0.52)
        pos=yield_pct[cond].is_largest(5)
        pos=pos.loc[(pos.index>=FIRST)&(pos.index<=LAST)]
        if pos.empty or int(pos.fillna(False).sum().sum())<3:
            raise RuntimeError("FinPilot S111 has insufficient matched historical candidate rows")
        coverage={"candidateSecurityDays":int(pos.fillna(False).sum().sum()),
                  "candidateSignalDates":int(pos.fillna(False).any(axis=1).sum()),
                  "lastSignalDate":str(pos.index[-1])}
        # Re-run historical annual windows with separate starting equity; not linked compound.
        windows={"full":(FIRST,LAST),"2025":(FIRST,"2025-12-31"),
          "2026":("2026-01-01",LAST)}
        results={}
        for key,(start,end) in windows.items():
            p=pos.loc[(pos.index>=start)&(pos.index<=end)]
            if p.empty or int(p.fillna(False).sum().sum())<1:
                results[key]={"status":"no_qualified_signals"};continue
            report=sim(p,resample="M",fee_ratio=1.425/1000,
                tax_ratio=3/1000,position_limit=.2,
                trade_at_price="open",upload=False)
            stats=report.get_stats()
            fields=("cagr","monthly_sharpe","max_drawdown","win_ratio","total_profit","total_trades")
            results[key]={k:float(stats[k]) if k in stats and stats[k] is not None else None for k in fields}
            results[key]["status"]="complete"
        make_record("complete",results=results,coverage=coverage)
    except Exception as exc:
        # Must never publish success based on incomplete BI, invalid token or feed failure.
        make_record("failed",str(exc)[:800])
        print("FIN_S111_ERROR",traceback.format_exc(limit=3),flush=True)
if __name__=="__main__":main()
