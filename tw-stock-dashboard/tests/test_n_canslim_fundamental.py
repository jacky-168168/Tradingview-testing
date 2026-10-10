"""N official MOPS point-in-time deadline proxy, fundamental joins and CANSLIM tests."""
from __future__ import annotations
import unittest
from datetime import date
import pandas as pd
from n_fundamental_archive import (parse_month_html,parse_quarter_html,month_safe_date,quarter_safe_date)
from n_canslim_features import FundamentalIndex,RULES,technical_panel
class NFundamentalTests(unittest.TestCase):
    def test_revenue_from_MOPS_bulk_table(self):
        html=('<html><table><tr><td>公司</td><td>名稱</td></tr><tr>'
            '<td>2330</td><td>台積電</td><td>120,000</td><td>110,000</td><td>100,000</td><td>9.1</td><td>20</td><td>2</td></tr></table></html>')
        rows,n=parse_month_html(html,"sii",2024,5,0)
        self.assertEqual(n,1);self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]["revenue"],120000)
    def test_EPS_YTD_and_market_parser(self):
        html=('<html><table><tr><th>公司 代號</th><th>公司名稱</th><th>基本每股盈餘（元）</th></tr>'
            '<tr><td>2330</td><td>台積電</td><td>17.26</td></tr></table></html>')
        rows,n,_=parse_quarter_html(html,"sii",2024,2)
        self.assertEqual(n,1);self.assertEqual(rows[0]["epsYtd"],17.26)
    def _idx(self):
        rev=[]
        for y in (2023,2024):
            for m in range(1,13):
                rev.append({"code":"2330","market":"sii","year":y,"month":m,
                    "revenue":100 if y==2023 else 130,
                    "availableFrom":month_safe_date(y,m)})
        ep=[]
        for y,eps in ((2023,10.),(2024,15.)):
            for q in range(1,5):
                ep.append({"code":"2330","market":"sii","year":y,"quarter":q,
                    "epsYtd":eps*q,"availableFrom":quarter_safe_date(y,q)})
        return FundamentalIndex(rev,ep)
    def test_no_2024_may_month_known_before_june_16(self):
        idx=self._idx()
        before=idx.at("sii","2330","2024-06-15")
        after=idx.at("sii","2330","2024-06-16")
        self.assertIsNotNone(before);self.assertIsNotNone(after)
        self.assertEqual(before["revFiscal"],"2024-04")
        self.assertEqual(after["revFiscal"],"2024-05")
        self.assertAlmostEqual(after["revenueYoYPct"],30)
        self.assertEqual(after["epsYtdGrowthPct"],50)
    def test_no_EPS_visible_on_fiscal_end(self):
        idx=self._idx()
        before=idx.at("sii","2330","2024-08-21")
        after=idx.at("sii","2330","2024-08-22")
        self.assertEqual(before["epsFiscal"],"2024Q1")
        self.assertEqual(after["epsFiscal"],"2024Q2")
        self.assertLessEqual(after["epsAvailableFrom"],after["asOf"])
    def test_missing_previous_earnings_returns_none_not_zero(self):
        idx=FundamentalIndex(
            [{"code":"2330","market":"sii","year":2024,"month":5,"revenue":120,
              "availableFrom":month_safe_date(2024,5)}],
            [{"code":"2330","market":"sii","year":2024,"quarter":2,"epsYtd":2,
              "availableFrom":quarter_safe_date(2024,2)}])
        self.assertIsNone(idx.at("sii","2330","2024-09-01"))
    def test_near52_week_uses_only_asof_signal_day(self):
        ds=pd.bdate_range("2024-01-02",periods=350)
        df=pd.DataFrame({"date":[x.strftime("%Y-%m-%d") for x in ds],
            "open":[100.]*350,"high":[101.]*350,"low":[99.]*350,
            "close":[100.]*350,"volume":[2_000_000]*350})
        all_dates=list(df.date)
        panel=technical_panel(df,all_dates)
        dt=all_dates[320];before=panel[panel.date==dt].iloc[0]
        df.loc[df.index[-1],"high"]=500
        changed=technical_panel(df,all_dates)
        after=changed[changed.date==dt].iloc[0]
        self.assertAlmostEqual(float(before["high52"]),float(after["high52"]),places=9)
    def test_conservative_dates_are_later_than_underlying_fiscal_dates(self):
        self.assertEqual(month_safe_date(2024,12),"2025-01-16")
        self.assertEqual(quarter_safe_date(2024,4),"2025-04-12")
        self.assertGreater(quarter_safe_date(2024,2),"2024-06-30")
if __name__=="__main__":unittest.main()
