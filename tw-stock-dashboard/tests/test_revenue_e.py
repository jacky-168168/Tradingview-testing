import unittest
from datetime import date
from revenue_monthly import parse_month_html,RevenueHistory,next_month_day_11,months_between
class TestRevenueE(unittest.TestCase):
    def test_parse_official_header(self):
        html="""<meta charset='big5'><table>
        <tr><th>公司代號</th><th>公司名稱</th><th>當月營收</th><th>上月營收</th><th>去年當月營收</th><th>上月比較增減(%)</th><th>去年同月增減(%)</th><th>本年累計</th><th>去年累計</th></tr>
        <tr><td>1101</td><td>台泥</td><td>13,306,676</td><td>12,214,776</td><td>13,325,249</td><td>8.93</td><td>-0.13</td><td>109,438,297</td><td>105,591,346</td></tr>
        <tr><td>1102</td><td>亞泥</td><td>6,388,217</td><td>5,663,764</td><td>6,496,635</td><td>12.79</td><td>-1.66</td><td>53,149,015</td><td>55,437,813</td></tr>
        <tr><td>合計</td><td></td><td>19,694,893</td><td>17,878,540</td><td>19,821,884</td><td>9.9</td><td>-0.64</td></tr>
        </table>"""
        data=parse_month_html(html)
        self.assertEqual(len(data),2)
        self.assertEqual(data["1101"],{"mom":8.93,"yoy":-0.13})
    def test_asof_no_lookahead_and_or(self):
        rows={("上市","1101"):[{"month":"2025-09","available":"2025-10-11","mom":8.93,"yoy":-0.13}],
              ("上市","1102"):[{"month":"2025-09","available":"2025-10-11","mom":-1.5,"yoy":3.1}],
              ("上櫃","1103"):[{"month":"2025-09","available":"2025-10-11","mom":0.0,"yoy":0.0}]}
        rev=RevenueHistory(rows,[],"asof")
        self.assertIsNone(rev.asof("上市","1101","2025-10-10"))
        self.assertTrue(rev.pass_e("上市","1101","2025-10-11"))
        self.assertTrue(rev.pass_e("上市","1102","2025-10-11"))
        self.assertFalse(rev.pass_e("上櫃","1103","2025-10-11"))
        self.assertFalse(rev.pass_e("上市","1101","2026-02-01"))
    def test_roc_months(self):
        self.assertEqual(next_month_day_11(2025,12),"2026-01-11")
        self.assertEqual(list(months_between(date(2025,12,1),date(2026,2,1))),[(2025,12),(2026,1),(2026,2)])
if __name__=="__main__":unittest.main()
