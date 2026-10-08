import unittest
import pandas as pd
from h5_ladder import levels,simulate
class H5LadderTest(unittest.TestCase):
    def bars(self,rows):
        return pd.DataFrame([{"date":f"2026-06-{i+1:02d}","open":o,"high":h,"low":l,"close":c} for i,(o,h,l,c) in enumerate(rows)])
    def test_prices_linear_from_first_fill(self):
        self.assertEqual(levels(100,97.5),[97.5,95.55,93.6,91.65,89.7])
        self.assertEqual(levels(100,98),[98.0,96.04,94.08,92.12,90.16])
    def test_no_first_limit_touch_means_no_trade(self):
        r=simulate(self.bars([(100,101,99,100)]),100,2.5,1)
        self.assertEqual(r["status"],"unfilled")
    def test_five_orders_and_dynamic_average_cost(self):
        r=simulate(self.bars([(100,101,97.2,98),(98,99,95.3,96),(96,97,93.3,94),
                             (94,95,91.4,92),(92,93,89.6,91)]),100,2.5,5)
        self.assertEqual(r["status"],"filled")
        self.assertEqual(r["trancheCount"],5)
        self.assertEqual(r["filledPrices"],[97.5,95.55,93.6,91.65,89.7])
        self.assertAlmostEqual(r["targetPrice"],r["averageCost"]*1.07,places=2)
        self.assertAlmostEqual(r["stopPrice"],r["averageCost"]*.85,places=2)
        self.assertEqual(r["exitReason"],"timeout")
    def test_target_from_actual_weighted_average(self):
        r=simulate(self.bars([(97,106,96.5,104)]),100,2.5,1)
        self.assertEqual(r["trancheCount"],1)
        self.assertEqual(r["exitReason"],"tp")
        self.assertLess(r["netReturnOnDeployedPct"],7)
    def test_intraday_first_fill_disallows_same_day_high_as_tp(self):
        r=simulate(self.bars([(100,111,97.4,103)]),100,2.5,1)
        self.assertEqual(r["status"],"filled")
        self.assertEqual(r["exitReason"],"timeout")
    def test_gap_stop_before_add(self):
        r=simulate(self.bars([(97,98,96,97),(80,83,75,81)]),100,2.5,2)
        self.assertEqual(r["exitReason"],"stop_gap")
        self.assertEqual(r["trancheCount"],1)
        self.assertLess(r["netReturnOnFiveTrancheBudgetPct"],0)
    def test_stop_on_average_cost_with_all_adds(self):
        r=simulate(self.bars([(100,103,70,76)]),100,2.5,1)
        self.assertEqual(r["status"],"filled")
        self.assertEqual(r["trancheCount"],5)
        self.assertEqual(r["exitReason"],"stop")
        self.assertLess(r["netReturnOnDeployedPct"],-15)
    def test_initial_discounts_always_2_to_3(self):
        for z in [2,2.5,3]:
            x=simulate(self.bars([(100,100,95,96)]),100,z,1)
            self.assertEqual(x["discountPct"],z)
        with self.assertRaises(ValueError):simulate(self.bars([(100,101,98,99)]),100,1.5,1)
if __name__=="__main__":unittest.main()
