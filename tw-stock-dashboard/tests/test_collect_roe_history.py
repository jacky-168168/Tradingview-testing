"""MOPS quarterly ROE archival parsing: same units, TTM, strict missing fiscal dependencies."""
import unittest
from collect_roe_history import parse_bulk,build_records
from n_fundamental_archive import quarter_safe_date

class RoeCollectionTests(unittest.TestCase):
    def test_income_and_equity_headers(self):
        html='''<table><tr><th>公司代號</th><th>公司名稱</th><th>本期淨利（淨損）</th></tr>
        <tr><td>2330</td><td>台積電</td><td>1,250,000</td></tr>
        <tr><td>3105</td><td>穩懋</td><td>(500,000)</td></tr></table>'''
        z,n=parse_bulk(html,"income","sii",2025,4)
        self.assertEqual(n,1)
        self.assertEqual(z["2330"],1250000)
        self.assertEqual(z["3105"],-500000)
        other=html.replace("本期淨利（淨損）","營業收入")
        self.assertEqual(parse_bulk(other,"income","sii",2025,4)[0],{})
    def test_ttm_and_same_quarter_average_equity(self):
        net={("sii","2330",2025,4):100,("sii","2330",2025,1):20,
             ("sii","2330",2026,1):30}
        equity={("sii","2330",2026,1):350,("sii","2330",2025,1):300}
        rows=build_records(net,equity,"2026-10-08")
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]["netIncomeTTM"],110)
        self.assertEqual(rows[0]["availableFrom"],quarter_safe_date(2026,1))
        self.assertEqual(rows[0]["equityNow"],350)
        self.assertEqual(rows[0]["equityYearAgo"],300)
        self.assertEqual(rows[0]["unit"],"NTD thousands")
    def test_reject_incomplete_prior_year(self):
        net={("sii","2330",2026,1):30}
        equity={("sii","2330",2026,1):350,("sii","2330",2025,1):300}
        self.assertEqual(build_records(net,equity,"2026-10-08"),[])
        self.assertEqual(build_records(net,equity,"2026-05-01"),[])
    def test_no_cross_market_or_asof_future(self):
        net={("sii","2330",2025,4):100,("sii","2330",2025,1):20,("sii","2330",2026,1):30}
        eq={("sii","2330",2026,1):350,("otc","2330",2025,1):300}
        self.assertEqual(build_records(net,eq,"2026-10-08"),[])

if __name__=="__main__":unittest.main()
