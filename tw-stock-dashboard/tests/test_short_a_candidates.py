import sys, unittest
from pathlib import Path
from datetime import date,timedelta
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"research"))
from short_a_candidates import capital_allowed,parse_company_capital,candidate,premarket,two_months_before,official_daily_rows
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
    def test_premarket_never_claims_open_confirmation(self):
        d=date(2026,11,27);p=[d-timedelta(days=i) for i in range(22,0,-1)]
        days={x:(100,103,98,100,5e6) for x in p};days[p[-6]]=(105,108,102,105,5e6)
        b={x:(100,101,99,100,1e6) for x in p}
        ok,row=premarket(d,p,days,b)
        self.assertTrue(ok);self.assertIsNotNone(row);self.assertIsNone(row["rvol"]);self.assertIsNone(row["gap_pct"])
        self.assertEqual(candidate(d,p,days,{},b),(False,None))
    def test_official_benchmark_parser(self):
        payload={"stat":"OK","data":[["115/11/26","1,000","10,000","60","62","59","61"],["115/11/27","1,000","10,000","61","63","60","62"],["115/10/26","100","100","60","62","59","61"]]}
        self.assertEqual(official_daily_rows(payload,date(2026,11,27),(2026,11)),{date(2026,11,26):(60.,62.,59.,61.,1000.)})
    def test_capital_is_paid_in_and_strictly_below_200_100m(self):
        self.assertTrue(capital_allowed(19_999_999_999))
        for value in (None,0,-1,20_000_000_000,20_000_000_001):
            self.assertFalse(capital_allowed(value))
        self.assertEqual(parse_company_capital([{"公司代號":"1234","實收資本額":"19,900,000,000"}],".TW"),{"1234.TW":19_900_000_000.})
