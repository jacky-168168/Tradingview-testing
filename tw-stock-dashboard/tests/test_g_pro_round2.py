"""Round 2: no lookahead, stable filters, and train/validation-only selection."""
import unittest
from research_g_pro_round2 import FAMILIES,passes,select_prefrozen,build_variants
class Round2Tests(unittest.TestCase):
    def test_rule_boundary(self):
        s={"sym":"1234.TW","code":"1234","close":113,"ret20P":73,"slopeP":78,"turnoverP":72,"previousTop20":1}
        x={"ema20":100,"ema60":90,"rvol":1.05}
        self.assertTrue(passes(s,x,FAMILIES["G Pro balanced"]))
        self.assertFalse(passes({**s,"previousTop20":0},x,FAMILIES["G Pro balanced"]))
        self.assertFalse(passes({**s,"close":130},x,FAMILIES["G Pro balanced"]))
        self.assertFalse(passes(s,{**x,"ema60":101},FAMILIES["G Pro balanced"]))
    def test_g_never_mutated(self):
        stock={"sym":"1234.TW","code":"1234","close":113,"ret20P":73,"slopeP":78,"turnoverP":72,"previousTop20":1}
        d="2025-01-02";base={d:[stock]};pool={d:[stock]}
        ind={"1234.TW":{d:{"ema20":100,"ema60":90,"rvol":1.05}}}
        out=build_variants([d],base,pool,ind)
        self.assertIs(out["G"],base)
        self.assertEqual(len(out["G Pro balanced"][d]),1)
        self.assertEqual(out["G Pro v1"][d],[])
    def test_selection_rejects_insufficient_train_or_validation(self):
        row={"name":"G Pro balanced","threshold":60,"horizon":20,
           "byPeriod":{"train":{"signal":{"n":35,"meanNetPct":1.0},"portfolio":{"dailyMaxDrawdownPct":-10}},
                       "validation":{"signal":{"n":10,"meanNetPct":2.0},"portfolio":{"dailyMaxDrawdownPct":-15}},
                       "holdout":{"signal":{"n":100,"meanNetPct":99.0},"portfolio":{"dailyMaxDrawdownPct":0}}}}
        self.assertEqual(select_prefrozen([row])["status"],"no_valid_candidate")
        row["byPeriod"]["validation"]["signal"]["n"]=25
        sel=select_prefrozen([row])
        self.assertEqual(sel["threshold"],60)
        self.assertEqual(sel["name"],"G Pro balanced")
        row["byPeriod"]["holdout"]["signal"]["meanNetPct"]=-50
        self.assertEqual(select_prefrozen([row])["threshold"],60)
if __name__=="__main__":unittest.main()
