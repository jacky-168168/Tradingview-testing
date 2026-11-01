import sys
import unittest
from pathlib import Path
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import retail_tpex as t

class FakeResponse:
    def __init__(self, data=None, text=""):
        self.data=data
        self.text=text
    def raise_for_status(self):pass
    def json(self):return self.data

class Session:
    def __init__(self, data, quotes, html):
        self.data=data
        self.quotes=quotes
        self.html=html
    def get(self,url,params=None,headers=None,timeout=None):
        if url==t.MARGIN_URL:return FakeResponse(data=self.data)
        if url==t.QUOTE_URL:return FakeResponse(data=self.quotes)
        if url==t.TOTAL_URL:return FakeResponse(text=self.html)
        raise AssertionError(url)

def fixture(day="1151030", price="10", omit_last=False, report_day="115/10/30"):
    data=[{"Date":day,"SecuritiesCompanyCode":f"{i:04d}","MarginPurchaseBalance":"70000"} for i in range(1000,1550)]
    quotes=[{"Date":day,"SecuritiesCompanyCode":f"{i:04d}","Close":price} for i in range(1000,1550-(1 if omit_last else 0))]
    html=f"""<html><body>資料日期: {report_day}<table><tr><td>融資金(仟元)</td><td>210000000</td><td>200000</td><td>140000</td><td>15000</td><td>205301000</td></tr></table></body></html>"""
    return Session(data,quotes,html)

class TPExTests(unittest.TestCase):
    def test_loan_parse_requires_exact_date(self):
        self.assertEqual(t.parse_loan_html(fixture().html,"2026-10-30"),205301000000)
        with self.assertRaisesRegex(RuntimeError,"日期"):
            t.parse_loan_html(fixture(report_day="115/10/29").html,"2026-10-30")
    def test_daily_data_date_must_match(self):
        with self.assertRaisesRegex(RuntimeError,"日期"):
            t.main("2026-10-30",fixture(day="1151029"))
    def test_market_ratio_is_collateral_over_loan(self):
        result=t.main("2026-10-30",fixture())
        expected=round(550*70000*1000*10/205301000000*100,2)
        self.assertEqual(result["otc"],expected)
        self.assertEqual(result["otcLoanTwd"],205301000000)
        self.assertEqual(result["otcMatched"],550)
        self.assertEqual(result["otcCoverage"],1)
    def test_quote_coverage_is_checked(self):
        f=fixture()
        f.quotes=f.quotes[:350]
        with self.assertRaisesRegex(RuntimeError,"涵蓋不足"):
            t.main("2026-10-30",f)
    def test_roc_day(self):
        self.assertEqual(t.roc_to_iso("1151030"),"2026-10-30")
        self.assertEqual(t.iso_to_roc("2026-10-30"),"115/10/30")
        with self.assertRaises(ValueError):t.roc_to_iso("1151031")
if __name__=="__main__":unittest.main()
