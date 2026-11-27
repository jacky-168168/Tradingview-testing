import sys, unittest
from pathlib import Path
from datetime import date,timedelta
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"research"))
from short_a_candidates import candidate,two_months_before
class TestCandidate(unittest.TestCase):
    def test_date_window(self):
        self.assertEqual(two_months_before(date(2026,11,27)),date(2026,9,27))
    def test_only_past(self):
        d=date(2026,11,27);p=[d-timedelta(days=i) for i in range(22,0,-1)]
        days={x:(100,103,98,100,5e6) for x in p};days[p[-6]]=(105,108,102,105,5e6)
        b={x:(100,101,99,100,1e6) for x in p};op={x:(100,1000) for x in p};op[d]=(99,1500)
        ok,row=candidate(d,p,days,op,b);self.assertTrue(ok);self.assertIsNotNone(row)
        days[d]=(500,500,500,500,1e9)
        self.assertEqual(candidate(d,p,days,op,b),(ok,row))
        self.assertEqual(candidate(d,p,days,{},b),(False,None))
    def test_no_fill_to_ten(self):
        d=date(2026,11,27);p=[d-timedelta(days=i) for i in range(22,0,-1)]
        ds={x:(100,103,98,100,5e6) for x in p};op={x:(100,1000) for x in p};op[d]=(100,1500)
        self.assertEqual(candidate(d,p,ds,op,ds),(True,None))
