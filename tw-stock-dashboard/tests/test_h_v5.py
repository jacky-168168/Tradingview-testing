import unittest,numpy as np
from backtest_h_v5 import trade,LIMIT_OFFSET,configs,percent_wilson_lower
class H5Tests(unittest.TestCase):
    def a(self,o,h,l,c,signal=100):
        return trade(np.array([o],dtype=float),np.array([h],dtype=float),np.array([l],dtype=float),np.array([c],dtype=float),np.array([1.]),[0],signal)
    def test_precommitted_entry_variations(self):
        self.assertIn(LIMIT_OFFSET,(0,-1,-2,-3))
        self.assertEqual(len(list(configs())),338)
    def test_unfilled_limit_remains_cash(self):
        lim=100*(1+LIMIT_OFFSET/100)
        self.assertEqual(self.a(lim+2,lim+5,lim+1,lim+3)[0],0)
    def test_open_fill_and_stop_first(self):
        lim=100*(1+LIMIT_OFFSET/100)
        res=self.a(lim,lim*1.11,lim*.94,lim*1.04)
        self.assertEqual(res[0],1)
        self.assertFalse(res[1]);self.assertTrue(res[2])
    def test_intraday_limit_fill_never_claims_earlier_high(self):
        lim=100*(1+LIMIT_OFFSET/100)
        res=self.a(lim+1,lim*1.2,lim*.99,lim*1.02)
        self.assertEqual(res[0],1)
        self.assertFalse(res[1]);self.assertEqual(res[-1],"timeout")
    def test_7_pct_tp_net_less_than_7(self):
        lim=100*(1+LIMIT_OFFSET/100)
        res=self.a(lim,lim*1.09,lim*.99,lim*1.08)
        self.assertTrue(res[1])
        self.assertTrue(5<res[3]<7)
if __name__=="__main__":unittest.main()
