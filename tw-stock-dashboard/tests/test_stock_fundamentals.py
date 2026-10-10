"""不可偷看未公告財報；年度累計 EPS 拆季度、低估值分位與缺值處理。"""
import unittest
from unittest.mock import patch
from datetime import date
from stock_fundamentals import MopsArchive,enrich_profiles
from n_fundamental_archive import month_safe_date,quarter_safe_date
import pandas as pd

class FundamentalStockProfileTests(unittest.TestCase):
    def fixtures(self):
        m=[]
        for y in [2025,2026]:
            for month in range(1,13 if y==2025 else 9):
                m.append({"code":"2330","market":"sii","year":y,"month":month,
                         "revenue":100000 if y==2025 else 120000+month*1000,
                         "availableFrom":month_safe_date(y,month)})
        eps=[]
        for y,vals in [(2024,[1,3,6,10]),(2025,[2,5,9,14]),(2026,[3,7])]:
            for q,v in enumerate(vals,1):
                eps.append({"code":"2330","market":"sii","year":y,"quarter":q,
                           "epsYtd":v,"availableFrom":quarter_safe_date(y,q)})
        return MopsArchive(m,eps)
    def test_no_future_month_or_quarter(self):
        a=self.fixtures()
        p=a.profile("上市","2330","2026-08-21",200)
        self.assertEqual(p["epsFiscal"],"2026Q1")
        self.assertEqual(p["revenueFiscal"],"2026-07")
        self.assertFalse(p["epsTurnaround"])
        p=a.profile("上市","2330","2026-09-15",200)
        self.assertEqual(p["revenueFiscal"],"2026-07")
        self.assertEqual(p["epsFiscal"],"2026Q2")
        p=a.profile("上市","2330","2026-10-08",200)
        self.assertEqual(p["revenueFiscal"],"2026-08")
    def test_quarterly_ttm_and_growth(self):
        a=self.fixtures()
        p=a.profile("上市","2330","2026-10-08",200)
        # 2025Q3=4, Q4=5, 2026Q1=3, Q2=4 => 16
        self.assertEqual(p["ttmEPS"],16)
        self.assertAlmostEqual(p["peTTM"],12.5)
        self.assertEqual(p["epsYtd"],7)
        self.assertEqual(p["epsYtdYoYPct"],40.0)
        self.assertEqual(p["revenueYoYPct"],28.0)
        self.assertAlmostEqual(p["revenueYi"],1.28)
        self.assertTrue(p["revenue12mHighRatioPct"] is not None)
    def test_negative_eps_no_fake_pe_or_growth(self):
        a=self.fixtures()
        a.quarters[("sii","2330")][(2025,2)]["value"]=-2
        a.quarters[("sii","2330")][(2026,2)]["value"]=-50
        p=a.profile("上市","2330","2026-10-08",200)
        self.assertIsNone(p["epsYtdYoYPct"])
        self.assertIsNone(p["peTTM"])
        self.assertIsNone(p["peHistoryPercentile120D"])
    def test_cross_section_coverage_and_missing_roe(self):
        archive=self.fixtures()
        date="2026-10-08"
        days=pd.bdate_range("2026-04-01",periods=150).strftime("%Y-%m-%d").tolist()
        days=[d for d in days if d<=date]
        if len(days)<120:days=pd.bdate_range(end=date,periods=120).strftime("%Y-%m-%d").tolist()
        hist=pd.DataFrame({"date":days,"close":[190+i/10 for i in range(len(days))]})
        payload={"schema":"stock-diagnostics-v1","dataDate":date,
                 "method":{},"coverage":{"withValidDailyK":2},
                 "stocks":[{"code":"2330","market":"上市","close":200.0},{"code":"3105","market":"上櫃","close":50.0}]}
        with patch("stock_fundamentals.read_archive",return_value=(archive,None)):
            out=enrich_profiles(payload,"unused",{"2330.TW":hist})
        self.assertEqual(out["schema"],"stock-diagnostics-v2")
        self.assertEqual(out["coverage"]["revenueAvailable"],1)
        self.assertEqual(out["coverage"]["epsAvailable"],1)
        self.assertEqual(out["coverage"]["peAvailable"],1)
        self.assertEqual(out["stocks"][0]["roePct"],None)
        self.assertIsNone(out["stocks"][1]["revenueYi"])
    def test_no_verified_archive_marks_missing(self):
        p={"schema":"stock-diagnostics-v1","dataDate":"2026-10-08","method":{},"coverage":{},"stocks":[]}
        with patch("stock_fundamentals.read_archive",return_value=(None,"missing")):
            enrich_profiles(p,"unused",{})
        self.assertFalse(p["coverage"]["financialsIncluded"])
        self.assertEqual(p["coverage"]["financialArchiveError"],"missing")

if __name__=="__main__":unittest.main()
