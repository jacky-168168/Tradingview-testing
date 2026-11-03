"""Regression: 11/03 sourced maintenance rates must not be replaced by stale collateral."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import update_retail_survival as mod

DAYS = ["2026-10-16","2026-10-19","2026-10-20","2026-10-21",
        "2026-10-22","2026-10-27","2026-10-28","2026-10-29",
        "2026-10-30","2026-11-02","2026-11-03"]
LOAN_LISTED = 599774466000
LOAN_OTC = 196562898000


def html(last="2026-11-03", index=43307.5, overall=161.22):
    days = ["2026-10-14", "2026-10-15"] + DAYS
    rows = []
    for day in days:
        a,b,c,ix = (162.67,156.80,overall,index) if day=="2026-11-03" else (171.70,167.25,170.60,44920.1)
        rows.append(f"<tr><td>{day}</td><td>{a}</td><td>{b}</td><td>{c}</td><td>{ix}</td></tr>")
        if day == last:
            break
    return "<html><table>" + "".join(rows) + "</table></html>"


def old_payload():
    return {"rows": [
        {"date":"2026-11-02","listed":171.7,"otc":167.23,"overall":170.6,
         "indexClose":44920.14,"listedLoanTwd":622699365000,"otcLoanTwd":204411530000},
        {"date":"2026-11-03","listed":178.27,"otc":156.76,"overall":172.96,
         "indexClose":43307.54,"listedCollateralTwd":1069196079360,
         "listedLoanTwd":599774466000,"otcLoanTwd":196562898000,
         "listedCoverage":0.995157}
    ]}


class FakeResponse:
    def __init__(self, body):
        self.text = body

    def raise_for_status(self):
        pass


class SameDaySourcedRateTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.target = Path(self.temp.name) / "latest.json"
        self.target.write_text(json.dumps(old_payload()), encoding="utf-8")
        self.p = patch.object(mod,"TARGET",self.target)
        self.p.start()
        self.addCleanup(self.p.stop)

    def refresh(self, body, otc=156.76, official_index=43307.54):
        with patch.object(mod.requests,"get",return_value=FakeResponse(body)), \
             patch("retail_twse_fallback.official_summary",
                   return_value={"date":"2026-11-03","listedLoanTwd":LOAN_LISTED,"indexClose":official_index}), \
             patch("retail_tpex.main",
                   return_value={"date":"2026-11-03","otc":otc,"otcLoanTwd":LOAN_OTC}), \
             patch.object(mod,"get_candles",return_value={}):
            mod.main()
        return json.loads(self.target.read_text(encoding="utf-8"))

    def test_source_corrects_11_03_all_market_ratio_and_discards_stale_collateral(self):
        result = self.refresh(html())
        row = result["rows"][-1]
        self.assertEqual(result["asOf"],"2026-11-03")
        self.assertEqual((row["listed"],row["otc"],row["overall"]),(162.67,156.80,161.22))
        self.assertEqual(row["listedLoanTwd"],LOAN_LISTED)
        self.assertEqual(row["otcLoanTwd"],LOAN_OTC)
        self.assertNotIn("listedCollateralTwd",row)
        self.assertNotIn("listedCoverage",row)
        self.assertEqual(row["ratioSourceDate"],"2026-11-03")
        self.assertIn("istock.tw",row["ratioSource"])
        self.assertAlmostEqual((LOAN_LISTED*row["listed"]+LOAN_OTC*row["otc"])/(LOAN_LISTED+LOAN_OTC),row["overall"],places=1)

    def test_stale_third_party_date_rejected(self):
        with self.assertRaisesRegex(RuntimeError,"尚未更新"):
            self.refresh(html(last="2026-11-02"))

    def test_wrong_index_day_rejected(self):
        with self.assertRaisesRegex(RuntimeError,"加權指數不符"):
            self.refresh(html(index=44000))

    def test_otc_independent_rate_disagreement_rejected(self):
        with self.assertRaisesRegex(RuntimeError,"差距過大"):
            self.refresh(html(),otc=161.0)

    def test_weighted_allmarket_disagreement_rejected(self):
        with self.assertRaisesRegex(RuntimeError,"加權對帳失敗"):
            self.refresh(html(overall=171.22))


if __name__=="__main__":
    unittest.main()
