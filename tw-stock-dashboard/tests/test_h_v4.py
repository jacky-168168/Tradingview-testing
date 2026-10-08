import unittest
import numpy as np,pandas as pd
from backtest_h_v4 import INPUTS,TRAIN_START,TRAIN_END,VALID_START,VALID_END,TEST_START,TOP,pick
from backtest_h_v3 import features,stat
class TestH4(unittest.TestCase):
    def test_feature_schema_not_based_on_previous_models(self):
        self.assertEqual(len(INPUTS),21)
        self.assertFalse(set(INPUTS)&{"sar","marketGate","score_d","score_g","fGate"})
    def test_chronological_splits_no_overlap(self):
        self.assertLess(TRAIN_END,VALID_START)
        self.assertLess(VALID_END,TEST_START)
    def test_prob_rank_top3_per_day(self):
        frame=pd.DataFrame({"date":["2026-03-02"]*6,"code":list("ABCDEF"),"score":[.6,.1,.9,.2,.8,.7],"turn":[4]*6,"p120":[.95]*6})
        selected=pick(frame,.4,1.5,.8)
        self.assertEqual(list(selected.code),["C","E","F"])
    def test_gap_skipped_signals_not_replaced(self):
        frame=pd.DataFrame({"date":["2026-03-02"]*4,"code":list("ABCD"),"score":[.9,.8,.7,.6],"turn":[4]*4,"p120":[.95]*4,"status":[0,1,1,1],"tp":[0,1,0,1],"stop":[0,0,1,0],"net":[np.nan,6.2,-4.1,6.2]})
        result=pick(frame,.4,1.5,.8)
        self.assertEqual(list(result.code),["A","B","C"])
        self.assertEqual(stat(result)["n"],2)
if __name__=="__main__":unittest.main()
