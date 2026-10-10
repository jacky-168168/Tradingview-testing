"""Regression checks for frozen G Pro gating and cash portfolio accounting."""
import unittest
import pandas as pd
from research_g_pro_3y import pro_pass,simulate_cash,G_PRO_RULES
class GProTests(unittest.TestCase):
    def test_gate_passes_only_strict_persistent_trend(self):
        s={"close":110,"ret20P":82,"slopeP":90,"turnoverP":83,"previousTop20":3}
        x={"ema20":103,"ema60":95,"rvol":1.6}
        self.assertEqual(pro_pass(s,x),(True,"passed"))
        self.assertEqual(pro_pass({**s,"previousTop20":1},x),(False,"persistence"))
        self.assertEqual(pro_pass(s,{**x,"rvol":0.9}),(False,"rvol"))
        self.assertEqual(pro_pass({**s,"close":125},x),(False,"overextended"))
        self.assertEqual(pro_pass(s,{"ema20":103,"ema60":107,"rvol":1.6}),(False,"ema_trend"))
    def test_cash_nonoverlap_and_close_to_close_drawdown(self):
        dates=["2026-01-05","2026-01-06","2026-01-07","2026-01-08","2026-01-09"]
        p=pd.DataFrame({"date":dates,"adjOpen":[100,100,100,100,100],"adjClose":[100,100,75,90,110]}).set_index("date",drop=False)
        stock={"sym":"1234.TW","code":"1234"}
        picks={d:[stock] for d in dates}
        score={d:80 for d in dates}
        result,curve,deals=simulate_cash(dates,picks,{"1234.TW":p},score,60,3)
        self.assertEqual(len(curve),len(dates))
        self.assertEqual(len(deals),1)
        self.assertEqual(deals[0]["buy"],dates[1])
        self.assertEqual(deals[0]["sell"],dates[3])
        self.assertLess(result["dailyMaxDrawdownPct"],-20)
        self.assertEqual(result["unclosedStockPositions"],0)
if __name__=="__main__":unittest.main()
