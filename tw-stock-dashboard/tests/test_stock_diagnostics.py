import json,tempfile,unittest
from pathlib import Path
import numpy as np,pandas as pd
from stock_diagnostics import build_snapshot,write_snapshot

def sample(code,market,n=270,offset=0):
    arr=20+np.arange(n,dtype=float)*(0.11+offset)
    h=pd.DataFrame({"date":pd.date_range("2025-01-01",periods=n,freq="B").strftime("%Y-%m-%d"),
                    "close":arr,"volume":np.full(n,1500000)})
    s={"code":code,"name":"測試"+code,"market":market,"industry":"半導體業","capitalB":23}
    return s,h

class StockDiagnosticsTests(unittest.TestCase):
    def test_all_market_and_percentiles_are_distinct_from_strategy_score(self):
        a,ha=sample("2330","上市",270,.15);b,hb=sample("3105","上櫃",270,.01)
        date=str(ha.iloc[-1]["date"])
        result=build_snapshot([a,b],{"2330.TW":ha,"3105.TWO":hb},date,4.5,
                  {"上市_2330":{"foreign":3400,"trust":-1200}},
                  {"G":[a],"D":[a,b]},date)
        self.assertEqual(result["coverage"]["withValidDailyK"],2)
        x=next(z for z in result["stocks"] if z["code"]=="2330")
        y=next(z for z in result["stocks"] if z["code"]=="3105")
        self.assertGreater(x["momentumScore"],y["momentumScore"])
        self.assertEqual(x["foreignToday"],3.4)
        self.assertIsNone(y["foreignToday"])
        self.assertEqual(x["models"],["D","G"])
        self.assertIsNone(x.get("roe"))
        self.assertTrue(x["high252"] is not None)
    def test_incomplete_history_and_stale_quotes_never_enter_profile(self):
        a,ha=sample("2330","上市",40);b,hb=sample("3105","上櫃",20);c,hc=sample("2454","上市",50)
        date=str(ha.iloc[-1]["date"])
        result=build_snapshot([a,b,c],{"2330.TW":ha,"3105.TWO":hb,"2454.TW":hc.iloc[:-1]},date,0)
        self.assertEqual([x["code"] for x in result["stocks"]],["2330"])
        self.assertIsNone(result["stocks"][0]["ret60"])
        self.assertIsNone(result["stocks"][0]["high252"])
    def test_snapshot_json_round_trip(self):
        s,h=sample("2330","上市",61)
        with tempfile.TemporaryDirectory() as d:
            p=write_snapshot(d,[s],{"2330.TW":h},str(h.iloc[-1]["date"]),0)
            saved=json.loads((Path(d)/"stocks"/"latest.json").read_text(encoding="utf-8"))
            self.assertEqual(saved["schema"],p["schema"]);self.assertEqual(saved["stocks"][0]["code"],"2330")

if __name__=="__main__":unittest.main()
