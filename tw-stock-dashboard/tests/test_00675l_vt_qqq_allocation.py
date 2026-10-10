"""Cash sleeve allocation, rolling five-year, fee and calendar audit."""
import sys,unittest
from pathlib import Path
import numpy as np,pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from research_00675l_vt_qqq_allocation import CONFIGS,curve_summary,portfolio,align_curves,START,END
class AllocationTests(unittest.TestCase):
    def test_weights_fixed_before_history(self):
        self.assertEqual(CONFIGS["L2_SMA10_100"]["L2_SMA10"],1.)
        self.assertEqual(CONFIGS["L2_SMA10_50_VT30_QQQ20"],{"L2_SMA10":.5,"VT":.3,"QQQ":.2})
        self.assertEqual(CONFIGS["L2_SMA10_30_VT50_QQQ20"],{"L2_SMA10":.3,"VT":.5,"QQQ":.2})
        for m in CONFIGS.values():self.assertAlmostEqual(sum(m.values()),1)
    def test_static_sleeve_no_money_created(self):
        dates=pd.to_datetime(["2018-01-02","2018-12-31","2019-01-02"])
        nav={"L2_SMA10":pd.Series([1e6,2e6,2e6],index=dates),
             "VT":pd.Series([1e6,1e6,1e6],index=dates)}
        w={"L2_SMA10":.5,"VT":.5}
        fixed,end,events=portfolio(dates,nav,w,"none")
        self.assertAlmostEqual(fixed[-1],1500000)
        self.assertEqual(len(events),0)
        annual,end,events=portfolio(dates,nav,w,"annual")
        self.assertEqual(len(events),1)
        self.assertLess(annual[-1],fixed[-1])
        self.assertGreater(annual[-1],1000000)
        self.assertAlmostEqual(sum(end.values()),100,places=1)
    def test_synthetic_no_future_fx(self):
        dates=pd.to_datetime(["2018-01-02","2018-01-03","2018-01-04"])
        raw={"L2_SMA10":pd.Series([1e6,1e6,1e6],index=dates),
             "VT":pd.Series([35000,35000,35000],index=dates)}
        fx=pd.Series([30.0,32.0],index=pd.to_datetime(["2018-01-02","2018-01-04"]))
        cal,aligned,spot=align_curves(raw,fx)
        self.assertEqual(len(cal),3)
        self.assertAlmostEqual(float(spot.iloc[1]),30)
        self.assertAlmostEqual(float(spot.iloc[-1]),32)
    def test_rolling_five_year_minimum_uses_calendar(self):
        d=pd.date_range("2018-01-02","2024-01-10",freq="7D")
        values=np.linspace(1e6,2e6,len(d))
        stats=curve_summary(d,values)
        self.assertGreater(stats["rollingFiveYear"]["n"],20)
        self.assertGreater(stats["rollingFiveYear"]["worst"]["returnPct"],0)
        self.assertLessEqual(stats["maxDrawdownPct"],0)
        self.assertIsNone(stats["underwaterAtEnd"])
if __name__=="__main__":unittest.main()
