import unittest
import pandas as pd,numpy as np
from backtest_h_v3 import trade,configs,pick,mask_family,stat,percent_wilson_lower,TRAIN_END,VALID_END
class H3WalkforwardTests(unittest.TestCase):
    def test_stop_first_on_same_bar(self):
        o=np.array([100.]);hi=np.array([110.]);lo=np.array([94.]);c=np.array([101.]);adj=np.array([1.])
        a=trade(o,hi,lo,c,adj,[0],100)
        self.assertEqual(a[0],1);self.assertTrue(a[2]);self.assertFalse(a[1])
    def test_positive_target_net_below_seven(self):
        o=np.array([100.]);hi=np.array([108.]);lo=np.array([99.]);c=np.array([107.]);f=np.array([1.])
        a=trade(o,hi,lo,c,f,[0],100)
        self.assertTrue(a[1]);self.assertTrue(5<a[3]<7)
    def test_gap_skip_without_replacement(self):
        o=np.array([104.]);hi=np.array([109.]);lo=np.array([101.]);c=np.array([105.]);f=np.array([1.])
        a=trade(o,hi,lo,c,f,[0],100)
        self.assertEqual(a[0],0);self.assertEqual(a[-1],"gap_skip")
    def test_all_families_precommitted(self):
        z=list(configs());self.assertTrue(300<len(z)<500)
        self.assertEqual(set(x["family"] for x in z),{"near_high","runup","rebound","flag","contraction","fresh_break","washout"})
    def test_daily_top_three_and_order(self):
        df=pd.DataFrame([{"date":"2026-02-02","turn":i,"p120":.95,"ret5":5,"vrel":1.5,"code":str(i)} for i in range(1,7)])
        p=pick(df,pd.Series([True]*6),0)
        self.assertEqual(len(p),3);self.assertEqual([int(x) for x in p.code], [6,5,4])
    def test_wilson_requires_sample(self):
        self.assertLess(percent_wilson_lower(3,5),.58)
        self.assertGreater(percent_wilson_lower(60,100),.40)
    def test_train_validation_cutoffs(self):
        self.assertLess(TRAIN_END,VALID_END)
if __name__=="__main__":unittest.main()
