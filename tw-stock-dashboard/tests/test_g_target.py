import unittest
import numpy as np
from g_target import PRIOR,eligible,features,fit,score,FEATURES

class TestGTarget(unittest.TestCase):
    def row(self,code="A",r20=95):
        return {"code":code,"capitalB":15,"close":100,"breakoutPct":-4,"ret20P":r20,"slopeP":90,"atrP":80,"range20P":88,"turnoverP":86,"ret5P":60,"mom10P":62,"range10P":73,"rvol10P":70,"positionP":70,"dayP":70,"emaSlopeP":80,"v520P":65}
    def test_feature_shapes(self):
        x=features(self.row());self.assertEqual(len(x),len(FEATURES));self.assertTrue(np.all(np.isfinite(x)))
    def test_gate(self):
        self.assertTrue(eligible(self.row()))
        x=self.row();x["close"]=9;self.assertFalse(eligible(x))
        x=self.row();x["turnoverP"]=60;self.assertFalse(eligible(x))
        x=self.row();x["breakoutPct"]=-26;self.assertFalse(eligible(x))
        x=self.row();x["capitalB"]=755;self.assertTrue(eligible(x))
    def test_fit_never_reads_stock_code_as_feature(self):
        a,b=self.row("X"),self.row("Y")
        self.assertTrue(np.allclose(features(a),features(b)))
        self.assertEqual(score(a,PRIOR),score(b,PRIOR))
    def test_train_chronological_conditional_ranker(self):
        a=self.row("POS",99);b=self.row("NO",60);c=self.row("N2",62)
        weights,info=fit([([a,b,c],{"POS"})])
        self.assertEqual(info["trainPosts"],1)
        self.assertEqual(info["groups"],1)
        self.assertEqual(len(weights),len(FEATURES))
        self.assertGreater(score(a,weights),score(b,weights))
    def test_high_momentum_scores_do_not_saturate_into_ties(self):
        high=self.row("A",99);low=self.row("B",89)
        hi=score(high,PRIOR);lo=score(low,PRIOR)
        self.assertLess(hi,100)
        self.assertGreater(hi,lo)
    def test_empty_train_falls_back_prior(self):
        w,info=fit([]);self.assertTrue(np.allclose(w,PRIOR));self.assertFalse(info["optimized"])

if __name__=="__main__":unittest.main()
