import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import pandas as pd
from g_live import _previous_structure,prior_pockets,latest_structure,select

class TestLiveG(unittest.TestCase):
    def calendar(self,n=60):
        return [d.strftime("%Y-%m-%d") for d in pd.bdate_range("2026-01-01",periods=n)]
    def history(self,days,code="1000"):
        return pd.DataFrame({"date":days,"open":[100.]*len(days),"high":[105.]*len(days),"low":[95.]*len(days),"close":[101.]*len(days),"volume":[10000000.]*len(days)})
    def metrics(self):
        return {"close":101.,"volume":10_000_000.,"ret20":12.,"ret5":6.,"ma20Slope":4.,"atrPct":3.,"breakoutPct":2.,"rvol":2.,"rvol10":2.,"mom10Pct":7.,"dayRet":1.,"volD":10.}
    def test_complete_3d_18d_structure_no_lookahead(self):
        days=self.calendar(54)
        h=self.history(days)
        h.loc[h.index[-1],"high"]=126.
        h.loc[h.index[-1],"close"]=120.
        f=latest_structure(h,days,days[-1],120.)
        self.assertTrue(f["break3"]);self.assertTrue(f["break18"])
        self.assertEqual(f["prior3High"],105.)
        self.assertEqual(f["prior18High"],105.)
        # Earliest day of a new forming 18D bar cannot reference its own high.
        days2=self.calendar(55)
        h2=self.history(days2)
        h2.loc[h2.index[-1],"close"]=120.
        h2.loc[h2.index[-1],"high"]=121.
        f=latest_structure(h2,days2,days2[-1],120.)
        self.assertTrue(f["break18"])
        self.assertEqual(f["prior18High"],105.)
    def test_calendar_pocket_snapshots_no_future_and_missing_days(self):
        days=self.calendar(12)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/"daily").mkdir()
            for i in (2,7,9,11):
                (root/"daily"/f"{days[i]}.json").write_text(json.dumps({"gPocketBaseline":[{"code":"1000","rank":1,"baselineScore":94+i}]}))
            pockets,n=prior_pockets(root,days,days[-1])
            self.assertEqual(len(pockets),10)
            self.assertEqual(n,3)
            self.assertEqual(sum("1000" in x for x in pockets),3)
            self.assertEqual(pockets[-1],{})
            self.assertEqual(pockets[0],{})
            self.assertEqual(pockets[1],{"1000":{"rank":1,"score":96.}})
    def test_live_selection_prior_pocket_bonus_separate_from_baseline(self):
        dates=self.calendar(54);day=dates[-1]
        symbols=[{"code":x,"market":"上市","name":x,"industry":"其他","capitalB":20} for x in ("1000","1001","1002")]
        history={f'{s["code"]}.TW':self.history(dates) for s in symbols}
        # Histories, absolute score and capital are identical: persistent 1001
        # must lead while original raw double-break pocket still sorts 1000.
        prior=[{"1001":{"rank":1,"score":98}} for _ in range(10)]
        flags={"break3":True,"break18":True,"eng3":False,"eng18":False,"bull3":True,"bull18":True}
        with patch("g_live.g_eligible",return_value=True),patch("g_live.latest_structure",return_value=flags):
            top,base,meta=select(symbols,history,dates,day,previous_pockets=prior,known_metrics={k:self.metrics() for k in history})
        self.assertEqual(base[0]["code"],"1000")
        self.assertEqual(top[0]["code"],"1001")
        self.assertEqual(meta["doubleBreakCandidates"],3)
        self.assertEqual(meta["percentileUniverse"],3)
        self.assertEqual(top[0]["gPast10"],10)
        self.assertGreater(top[0]["total"],top[0]["gScore"])
        self.assertTrue(all(x["gBreak3"] and x["gBreak18"] for x in top))
        self.assertEqual(len({x["code"] for x in top}),3)
    def test_no_double_break_means_empty_not_d_substitution(self):
        dates=self.calendar(54);s={"code":"1000","market":"上市","name":"test","capitalB":20}
        with patch("g_live.g_eligible",return_value=True),patch("g_live.latest_structure",return_value={"break3":True,"break18":False}):
            top,baseline,meta=select([s],{"1000.TW":self.history(dates)},dates,dates[-1],known_metrics={"1000.TW":self.metrics()})
        self.assertEqual(top,[]);self.assertEqual(baseline,[])
        self.assertEqual(meta["doubleBreakCandidates"],0)
    def test_missing_current_stock_candles_not_stale_pocket(self):
        days=self.calendar(54);s={"code":"1000","market":"上市","name":"test","capitalB":20}
        with self.assertRaisesRegex(RuntimeError,"no valid same-day"):
            select([s],{"1000.TW":self.history(days[:-1])},days,days[-1])
    def test_index_defaults_to_real_g_daily_data(self):
        src=Path(__file__).resolve().parents[1]/"docs"/"index.html"
        text=src.read_text(encoding="utf-8")
        self.assertIn('var DATA=null,MODEL="G"',text)
        self.assertIn('id="tabG"',text)
        self.assertIn('id="gNote"',text)
        self.assertIn('x.gPast10',text)

if __name__=="__main__":unittest.main()
