"""Safety checks for read-only G factor study; no market network needed."""
import unittest
import numpy as np,pandas as pd
from research_g_factor_ic_3y import valid_for_fold,boot_ci,factor_report,ablate
class AuditTests(unittest.TestCase):
    def test_mature_labels_do_not_cross_fold(self):
        self.assertTrue(valid_for_fold("2025-12-20","2025-12-31","validation"))
        self.assertFalse(valid_for_fold("2025-12-29","2026-01-02","validation"))
        self.assertFalse(valid_for_fold("2026-01-02","2026-01-10","train"))
        self.assertFalse(valid_for_fold("2026-10-07",None,"holdout"))
    def test_month_bootstrap_requires_multiple_independent_months(self):
        self.assertIsNone(boot_ci([("2026-01-01",.2),("2026-01-02",.4)]))
        ci=boot_ci([("2026-0"+str(i)+"-01",.1*i) for i in range(1,5)])
        self.assertIsNotNone(ci)
        self.assertGreater(ci[0],0)
        self.assertGreater(ci[1],ci[0])
    def test_rank_ic_and_quintiles_are_directional(self):
        g={}
        for month in range(1,7):
            d=f"2026-{month:02}-02"
            z=pd.DataFrame({"code":[str(n) for n in range(25)],
                "ret20P":np.arange(25,dtype=float),"net5":np.arange(25,dtype=float)/100,
                "score":np.arange(25,dtype=float),"base":np.arange(25,dtype=float)})
            z.attrs["exits"]={5:f"2026-{month:02}-18"}
            g[d]=z
        z=factor_report(g,"ret20P",5,"holdout",{d:75 for d in g},0)
        self.assertEqual(z["daysIC"],6)
        self.assertAlmostEqual(z["rankIC"],1,places=4)
        self.assertGreater(z["Q5MinusQ1NetPct"],0)
        self.assertEqual(z["evidence"],"insufficient")
    def test_ablation_is_matched_and_does_not_mutate_original(self):
        d="2026-02-02"
        df=pd.DataFrame({"code":["1","2","3","4"],"score":[94.,93.,92.,91.],"base":[94.,93.,92.,91.],
            "ret20P":[99.,98.,97.,96.],"near":[100.,100.,100.,100.],"bonus":[0.,0.,0.,0.],
            "net5":[.02,.01,.03,.04]})
        df.attrs["exits"]={5:"2026-02-10"}
        out=ablate({d:df},"ret20P",5,"holdout",{d:75},0)
        self.assertEqual(out["matchedDays"],1)
        self.assertEqual(list(df.code),["1","2","3","4"])
if __name__=="__main__":unittest.main()
