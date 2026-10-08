import unittest
from backtest_candle import WEIGHTS,base_score,structure,bar_state,build_flags

class TestGCandle2026(unittest.TestCase):
    def row(self):
        return {"ret20P":90,"slopeP":91,"atrP":87,"range20P":92,"turnoverP":91,"breakoutPct":-3}
    def test_no_features_equals_broad(self):
        score=base_score(self.row())
        self.assertEqual(structure(score,{}),score)
    def test_bonus_is_monotone(self):
        s=base_score(self.row())
        self.assertGreater(structure(s,{"break3":True}),s)
        self.assertGreater(structure(s,{"break3":True,"eng18":True}),structure(s,{"break3":True}))
    def test_confirmed_bar_cannot_break_own_high(self):
        confirmed=[
            {"date":"2026-09-01","open":90,"close":95,"high":100,"low":86},
            {"date":"2026-09-04","open":93,"close":109,"high":110,"low":90}
        ]
        ends=[x["date"] for x in confirmed]
        out=bar_state(confirmed,ends,"2026-09-04",109)
        self.assertTrue(out["break"])
        self.assertTrue(out["bull"])
    def test_forming_day_references_last_confirmed_high(self):
        bars=[{"date":"2026-09-04","open":96,"close":101,"high":106,"low":92}]
        state=bar_state(bars,["2026-09-04"],"2026-09-07",108)
        self.assertTrue(state["break"])
    def test_empty_18d_no_engulf(self):
        f=build_flags([],[],[],[],"2026-01-12",101)
        self.assertFalse(any(f.values()))

if __name__=="__main__":unittest.main()
