import unittest
from datetime import datetime,timedelta
from update_us_fear_greed import VERSION,parse_wantgoo,to_archive,score
SAMPLE="""<html><h2>恐懼與貪婪指數</h2><table><tr><th>日期</th><th>恐懼與貪婪指數</th><th>S&P500</th></tr>
<tr><td>2026/10/21</td><td>恐懼 <strong>29</strong></td><td>7,751.95</td></tr>
<tr><td>2026/10/20</td><td>恐懼 <span>27</span></td><td>7,712.57</td></tr>
<tr><td>2026/10/19</td><td>極度恐懼 23</td><td>7,690.73</td></tr>
<tr><td>2026/10/16</td><td>極度恐懼 18</td><td>7,659.44</td></tr>
<tr><td>2026/10/15</td><td>恐懼 32</td><td>7,744.06</td></tr></table></html>"""
class TestUSFearGreed(unittest.TestCase):
    def fixture(self):
        start=datetime(2026,1,1)
        rows=[[(start+timedelta(days=i)).date().isoformat(),float(i%100),7600+i] for i in range(294)]
        return {"version":"US_CNN_FEAR_GREED_SPX_V1","sourceLink":"https://edition.cnn.com/markets/fear-and-greed",
                "spxSource":"SqueezeMetrics","columns":["date","fearGreed","spx"],"rows":rows}
    def test_extract_confirmed_public_table(self):
        got=parse_wantgoo(SAMPLE)
        self.assertEqual(len(got),5)
        self.assertEqual(got[-1],["2026-10-21",29,7751.95])
        self.assertEqual(got[0][1],32)
    def test_parse_without_table_markup(self):
        html="<html>恐懼與貪婪指數<div>2026/10/21</div><span>恐懼 29</span><div>7,751.95</div><div>2026/10/20 恐懼 27 7,712.57</div></html>"
        self.assertEqual(len(parse_wantgoo(html)),2)
    def test_keep_attributed_legacy_and_replace_overlaps(self):
        d=to_archive(SAMPLE,self.fixture())
        self.assertEqual(d["version"],VERSION)
        self.assertEqual(d["sourceLink"],"https://www.wantgoo.com/global/macroeconomics/fearandgreed")
        self.assertEqual(d["legacyThrough"],"2026-10-14")
        self.assertIn("cnn.com",d["legacyHistorySource"])
        self.assertEqual(d["asOf"],"2026-10-21")
        self.assertEqual(d["rows"][-1],["2026-10-21",29,7751.95])
        self.assertEqual(len(d["rows"]),294)
    def test_incremental_update_keeps_original_boundary(self):
        d=to_archive(SAMPLE,self.fixture())
        d2=to_archive(SAMPLE,d)
        self.assertEqual(d2["legacyThrough"],"2026-10-14")
        self.assertEqual(d["rows"],d2["rows"])
    def test_fail_closed_when_page_changes(self):
        with self.assertRaisesRegex(ValueError,"heading"):parse_wantgoo("<html>broken</html>")
        with self.assertRaisesRegex(ValueError,"table"):parse_wantgoo("<html>恐懼與貪婪指數 2026/10/21 恐懼 29</html>")
    def test_reject_stale_and_bad_history(self):
        old=self.fixture()
        old["rows"][-1][0]="2026-10-22"
        with self.assertRaisesRegex(ValueError,"BEHIND_ARCHIVE"):to_archive(SAMPLE,old)
        bad=self.fixture();bad["columns"]=["date","spx","fearGreed"]
        with self.assertRaisesRegex(ValueError,"incompatible"):to_archive(SAMPLE,bad)
        self.assertIsNone(score(-1))
        self.assertIsNone(score(101))
        self.assertIsNone(score("nan"))
if __name__=="__main__":unittest.main()
