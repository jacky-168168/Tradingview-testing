import unittest,sys,copy
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from market_intelligence import compute
class MarketIntelligenceTests(unittest.TestCase):
    @staticmethod
    def series(n=150,score=75):
        data=[]
        for i in range(n):
            data.append({"date":f"2024-{i//28+1:02d}-{i%28+1:02d}","index":10000+i*10,
              "score":score,"breadth":55,"up":550,"down":450,"mode":"NORMAL",
              "topState":"⚪ Inactive","bottomState":"⚪ Inactive","distMA20":2,
              "ret5":1,"dayRet":1,"foreign":10,"closePosition":60})
        return data
    def test_score_unchanged_and_normal_ready(self):
        a=self.series();out=compute(a[-1],a)
        self.assertEqual(out["decision"]["level"],"READY")
        self.assertEqual(out["riskScore"],75)
        self.assertEqual(out["marketHealth"]["sourceHistoryDays"],150)
    def test_extra_future_days_never_change_report(self):
        a=self.series();p=compute(a[109],a[:110])
        future=self.series(145,10)[110:]
        self.assertEqual(p,compute(a[109],a[:110]+future))
    def test_low_risk_stop(self):
        a=self.series(score=46);self.assertEqual(compute(a[-1],a)["decision"]["level"],"STOP")
    def test_overbought_has_priority(self):
        a=self.series();a[-1]["topState"]="🔴 Extreme Overbought"
        self.assertEqual(compute(a[-1],a)["decision"]["level"],"CAUTION")
    def test_strong_bottom_is_not_normal_ready(self):
        a=self.series(score=29);a[-1]["bottomState"]="🟢 Strong Bottom Reversal"
        self.assertEqual(compute(a[-1],a)["decision"]["level"],"REVERSAL")
    def test_divergence_is_watch_not_invented_buy_veto(self):
        a=self.series(score=72)
        for x in a[-10:]:x["breadth"]=39
        for x in a[-10:]:x["index"]=x["index"]*1.04
        out=compute(a[-1],a)
        self.assertIn("NARROW_BREADTH",[f["code"] for f in out["decision"]["flags"]])
        self.assertEqual(out["decision"]["level"],"READY")
if __name__=="__main__":unittest.main()
