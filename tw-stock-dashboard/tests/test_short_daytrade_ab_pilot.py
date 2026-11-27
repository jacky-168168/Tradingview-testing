"""Synthetic regression tests only; synthetic figures NEVER reported as market results."""
import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"research"))
from short_daytrade_ab_pilot import tick,good_days,indicators,vwap,simulate,metrics,scan
class ABTests(unittest.TestCase):
    def test_tick_and_fee_and_stop_priority(self):
        self.assertEqual(tick(50),.1)
        rows=[{"day":"2026-11-01","time":"09:20","o":50,"h":55,"l":40,"c":46,"v":2000}]
        trade={"day":"2026-11-01","symbol":"TEST","mode":"A","rawEntry":50,
               "stop":52,"entryIndex":0,"entryTime":"09:20"}
        t=simulate(trade,rows)
        self.assertEqual(t["exitReason"],"stop_first")
        self.assertLess(t["netTwd"],t["grossTwd"])
        self.assertGreater(t["taxTwd"],0)
        self.assertGreater(t["feesTwd"],0)
    def test_does_not_forward_fill_missing_5m_rows(self):
        rows=[{"day":"2026-11-01","time":f"{9+i//12:02d}:{i%12*5:02d}",
               "o":50,"h":51,"l":49,"c":50,"v":1000} for i in range(54)]
        self.assertIn("2026-11-01",good_days(rows))
        self.assertNotIn("2026-11-01",good_days(rows[:30]))
    def test_daily_indicators_use_only_previous_session(self):
        d=[{"day":f"2026-11-{i+1:02d}","o":50,"h":52,"l":48,"c":50+i*.1,"v":20000000}
           for i in range(23)]
        v=indicators(d,22,d,22)
        self.assertEqual(v["prev"],d[21]["c"])
        d[22]["c"]=999
        self.assertEqual(indicators(d,22,d,22),v)
    def test_vwap_is_observed_only(self):
        r=[{"h":52,"l":48,"c":50,"v":1000},{"h":62,"l":58,"c":60,"v":1000}]
        self.assertLess(vwap(r,0),vwap(r,1))
    def test_no_trade_reports_no_win_rate(self):
        m=metrics([],[])
        self.assertEqual(m["n"],0)
        self.assertIsNone(m["winRate"])
        self.assertIsNone(m["PF"])
    def test_standalone_never_imports_live_selector(self):
        s=(Path(__file__).resolve().parents[1]/"research"/"short_daytrade_ab_pilot.py").read_text()
        self.assertIn('"integrationApproved":False',s)
        self.assertIn('"eligibilityByHistoricalDateVerified":False',s)
        self.assertNotIn("from g_live import",s)
        self.assertNotIn("from pipeline import",s)
if __name__=="__main__":unittest.main()
