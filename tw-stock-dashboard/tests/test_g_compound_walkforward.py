"""Causal label maturation, train cutoff, capital and model-choice tests."""
import unittest
from unittest.mock import patch
import numpy as np
from research_g_compound_walkforward import (PLANS,FEATURES,BUY_FACTOR,SELL_FACTOR,
    historical_label,assert_training_past,rank_monthly_walkforward,
    model_preference,id_for,MIN_TRAIN)
class WalkForwardTests(unittest.TestCase):
    def _bar(self,day,o=100,h=103,l=98,c=100):
        return day,(o,h,l,c,o,h,l,c,100_000.)
    def test_tp_maturity_is_exit_not_signal(self):
        ds=["2024-12-27","2024-12-30","2024-12-31"]
        bars={"A.TW":dict([self._bar(ds[1],h=108),self._bar(ds[2])])}
        row={"date":ds[0],"sym":"A.TW","close":100}
        label=historical_label(ds,{d:i for i,d in enumerate(ds)},row,bars,PLANS["FAST"])
        self.assertEqual(label["maturity"],ds[1])
        self.assertEqual(label["exit"],"target_limit")
        self.assertGreater(label["pnl"],0)
        self.assertAlmostEqual(label["pnl"],1.05*SELL_FACTOR/BUY_FACTOR-1,places=7)
    def test_plus3_cap_no_hindsight_fill(self):
        ds=["2024-12-27","2024-12-30"]
        bars={"A.TW":dict([self._bar(ds[1],o=103.01,h=110)])}
        row={"date":ds[0],"sym":"A.TW","close":100}
        self.assertIsNone(historical_label(ds,{d:i for i,d in enumerate(ds)},row,bars,PLANS["FAST"]))
    def test_simultaneous_touch_stop_before_profit(self):
        ds=["2024-12-27","2024-12-30","2024-12-31"]
        bars={"A.TW":dict([self._bar(ds[1],h=112,l=90),self._bar(ds[2])])}
        z=historical_label(ds,{d:i for i,d in enumerate(ds)},{"date":ds[0],"sym":"A.TW","close":100},bars,PLANS["FAST"])
        self.assertEqual(z["exit"],"intraday_stop")
        self.assertLess(z["pnl"],0)
    def test_exit_maturity_must_precede_month_first_session(self):
        good={"date":"2024-12-20","maturity":"2024-12-31"}
        bad={"date":"2024-12-20","maturity":"2025-01-02"}
        assert_training_past([good],"2025-01-02")
        with self.assertRaises(AssertionError):assert_training_past([bad],"2025-01-02")
        with self.assertRaises(AssertionError):assert_training_past([
            {"date":"2025-01-02","maturity":"2024-12-31"}],"2025-01-02")
    def test_monthly_recursion_adds_only_newly_matured_labels(self):
        day1="2025-01-02";day2="2025-02-03"
        features=[1.]*len(FEATURES)
        pool={day1:[{"date":day1,"code":"1111","sym":"1111.TW",
                      "name":"A","close":100,"features":features}],
              day2:[{"date":day2,"code":"1111","sym":"1111.TW",
                      "name":"A","close":100,"features":features}]}
        past=[{"date":"2024-12-15","maturity":"2024-12-30",
               "pnl":.02 if i%2 else -.03,"features":features} for i in range(200)]
        newly={"date":"2025-01-06","maturity":"2025-01-27",
               "pnl":.06,"features":features}
        future={"date":"2025-01-10","maturity":"2025-02-25",
                "pnl":-.20,"features":features}
        visits=[]
        def stub(kind,X,y):
            visits.append(len(y))
            return lambda x:np.ones(len(x))*1.0
        with patch("research_g_compound_walkforward.trainer",side_effect=stub):
            picks,log=rank_monthly_walkforward([day1,day2],pool,
                {"FAST":past+[newly,future]},"Ridge","FAST",True)
        self.assertEqual(visits,[200,201])
        self.assertEqual(log[0]["latestMaturedLabel"],"2024-12-30")
        self.assertEqual(log[1]["latestMaturedLabel"],"2025-01-27")
        self.assertEqual(len(picks[day1]),1)
        self.assertEqual(len(picks[day2]),1)
    def test_validation_only_selection_is_invariant_to_2026(self):
        v={"closedTrades":24,"netReturnPct":20.,"maxDDPct":-15.}
        row={"id":"Ridge__FAST__ALWAYS__CAP200","periods":{
            "validation2025":v.copy(),"audit2026":{"netReturnPct":-90.},
            "authorWindow2026":{"netReturnPct":-100.}}}
        a=model_preference([row]);self.assertEqual(a["id"],row["id"])
        row["periods"]["audit2026"]["netReturnPct"]=1200
        row["periods"]["authorWindow2026"]["netReturnPct"]=1200
        b=model_preference([row]);self.assertEqual(a["id"],b["id"])
        row["periods"]["validation2025"]["netReturnPct"]=-1
        self.assertEqual(model_preference([row])["status"],"no_model_passed_validation_gate")
    def test_all_configuration_identity_is_stable(self):
        self.assertNotEqual(id_for("Ridge","FAST","ALWAYS",200000),
                            id_for("Ridge","FAST","ALWAYS",None))
        self.assertEqual(len(FEATURES),28)
        self.assertNotIn("futureClose",FEATURES)
if __name__=="__main__":unittest.main()
