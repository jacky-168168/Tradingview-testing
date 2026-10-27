import sys, unittest
from datetime import datetime, timedelta
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from futures_preopen import parse_quote, QuoteUnavailable
NOW=datetime.fromisoformat("2026-10-27T08:55:00+08:00")
def fixture(day="2026/10/27",when="08:53:12"):
    return """<html><body><h2>即時期指報價</h2><div>資料時間：%s</div>
    <table><tr><td>商品</td></tr><tr><td>台指期近一</td><td>WTX&</td>
    <td>45,652.00</td><td>45,665.00</td><td>45,654.00</td>
    <td>580.00</td><td>1.25%%</td><td>39,363</td>
    <td>46,270.00</td><td>46,399.00</td><td>45,523.00</td>
    <td>401.43</td><td>46,234.00</td><td>115,258</td><td>%s</td></tr>
    <tr><td>台指期近二</td><td>WTX@</td></tr></table></body></html>""" %(day,when)
class TestVerifiedQuote(unittest.TestCase):
    def test_valid_date_and_change(self):
        q=parse_quote(fixture(),NOW)
        self.assertEqual(q["status"],"ok")
        self.assertEqual(q["asOfDate"],"2026-10-27")
        self.assertEqual(q["last"],45654)
        self.assertEqual(q["reference"],46234)
        self.assertEqual(q["changePoints"],-580)
        self.assertEqual(q["quoteTime"],"2026-10-27T08:53:12+08:00")
    def test_old_date_rejected(self):
        with self.assertRaises(QuoteUnavailable):parse_quote(fixture(day="2026/10/22"),NOW)
    def test_old_quote_rejected(self):
        with self.assertRaises(QuoteUnavailable):parse_quote(fixture(when="08:20:00"),NOW)
    def test_future_quote_rejected(self):
        with self.assertRaises(QuoteUnavailable):parse_quote(fixture(when="08:56:00"),NOW)
    def test_preopen_auction_not_last_trade(self):
        with self.assertRaises(QuoteUnavailable):parse_quote(fixture(when="08:30:00"),NOW)
if __name__=="__main__":unittest.main()
