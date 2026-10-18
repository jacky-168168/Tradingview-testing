import io,csv,unittest
from update_tdcc_whale_weekly import parse_snapshot,quadrant_of,select_owners,render,parse_listing_day
from datetime import date
class TestTDCCWhales(unittest.TestCase):
    @staticmethod
    def fixture(date="2026-10-16",invalid=False):
        o=io.StringIO();w=csv.writer(o)
        w.writerow(["資料日期","證券代號","持股分級","人數","股數","占集保庫存數比例%"])
        for i in range(3600):
            code=str(1000+i).zfill(4)
            for j in range(1,18):
                d="20261008" if invalid and i==0 else date.replace("-","")
                w.writerow([d,code,j,1,1000 if j==17 else 0,0])
        return o.getvalue().encode("utf-8")
    def test_official_levels_and_date(self):
        x=parse_snapshot(self.fixture(),"2026-10-16")
        self.assertEqual(len(x),3600)
        self.assertEqual(x["1000"]["allShares"] if "allShares" in x["1000"] else x["1000"]["total"],1000)
        self.assertEqual(x["1000"]["ratio"],0)
        with self.assertRaisesRegex(ValueError,"mismatch"):
            parse_snapshot(self.fixture(invalid=True),"2026-10-16")
    def test_quadrants_not_price_direction(self):
        self.assertEqual(quadrant_of(1,2),"續買")
        self.assertEqual(quadrant_of(-3,1.1),"回頭車")
        self.assertEqual(quadrant_of(3,-2),"下車")
        self.assertEqual(quadrant_of(-1.4,-2),"續賣")
        self.assertIsNone(quadrant_of(.99,4))
    def test_400_lot_share_ratio_and_risks(self):
        universe=[{"code":"6278","name":"台表科","market":"上市"}]
        p=[{"6278":{"ratio":65.353,"total":100000000}},{"6278":{"ratio":68.856,"total":100000000}},{"6278":{"ratio":74.337,"total":100000000}}]
        groups,excluded,common=select_owners(p,universe)
        self.assertEqual(common,1)
        self.assertEqual(len(groups["續買"]),1)
        self.assertEqual(groups["續買"][0]["previousPP"],3.50)
        self.assertEqual(groups["續買"][0]["currentPP"],5.48)
        report=render([("2026-10-02","archA"),("2026-10-08","archB"),("2026-10-16","archC")],p,universe,{"6278":20.4},{"paired":1,"attempted":1,"errors":0})
        self.assertEqual(report["quadrants"]["續買"]["rows"][0]["priceReturnPct"],20.4)
    def test_dr_and_recent_ipo_excluded_without_hardcoded_tickers(self):
        self.assertEqual(parse_listing_day("1150922"),date(2026,9,22))
        self.assertEqual(parse_listing_day("2026/09/22"),date(2026,9,22))
        self.assertIsNone(parse_listing_day("invalid"))
        universe=[{"code":"9105","name":"泰金寶-DR","market":"上市"},{"code":"7856","name":"漢測","market":"上櫃"},{"code":"6278","name":"台表科","market":"上市"}]
        versions=[]
        for rate in (40,43,46):
            versions.append({k:{"ratio":rate,"total":100000000} for k in ("9105","7856","6278")})
        groups,reasons,_=select_owners(versions,universe,{"7856":date(2026,9,22),"6278":date(2010,1,1)},date(2026,10,16))
        self.assertEqual([r["code"] for r in groups["續買"]],["6278"])
        self.assertEqual(reasons["depositary_receipt"],1)
        self.assertEqual(reasons["recent_initial_listing_under_30_days"],1)
    def test_total_share_denominator_change_not_turnover(self):
        universe=[{"code":"6278","name":"台表科","market":"上市"}]
        p=[{"6278":{"ratio":50,"total":1000000}},{"6278":{"ratio":53,"total":1200000}},{"6278":{"ratio":56,"total":1200000}}]
        groups,reasons,_=select_owners(p,universe)
        self.assertEqual(sum(len(x) for x in groups.values()),0)
        self.assertEqual(reasons["large_tdcc_depository_change"],1)
if __name__=="__main__":unittest.main()
