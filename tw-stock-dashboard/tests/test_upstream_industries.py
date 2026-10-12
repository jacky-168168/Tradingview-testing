import unittest
from upstream_industries import read_memberships,stage_group,compile_map,INDUSTRIES

def ind(code):return next(i for i in INDUSTRIES if i["code"]==code)
def sample(code,name,market="上市",close=100):
    return {"code":code,"name":name,"market":market,"industry":"—","close":close,
            "ret5":3,"ret20":5,"momentumScore":76,"turnoverB":3,"models":["G"]}

class UpstreamIndustryTests(unittest.TestCase):
    def test_tpEx_company_chain_html_membership_paths_and_multiple_sectors(self):
        page="""<h4>► 半導體 &gt; 電源管理IC</h4><h4>► 印刷電路板 &gt; 銅箔</h4>
                <h4>► 半導體 &gt; 電源管理IC</h4>"""
        self.assertEqual(read_memberships(page),[
            {"industry":"半導體","subCategory":"電源管理IC"},
            {"industry":"印刷電路板","subCategory":"銅箔"}])
    def test_official_upstream_vs_middle_and_downstream(self):
        self.assertEqual(stage_group(ind("D000"),"電源管理IC"),"IC 設計")
        self.assertEqual(stage_group(ind("D000"),"IP設計/IC設計代工服務"),"IP設計／IC設計代工")
        for name in ("晶圓製造","IC封裝測試","IC通路","其他IC/二極體製造"):
            self.assertIsNone(stage_group(ind("D000"),name),name)
        self.assertEqual(stage_group(ind("L000"),"銅箔"),"銅箔")
        self.assertIsNone(stage_group(ind("L000"),"銅箔基板"))
        self.assertIsNone(stage_group(ind("I000"),"網路設備"))
        self.assertEqual(stage_group(ind("A300"),"鋰電池材料"),"鋰電池材料")
    def test_industry_groups_count_distinct_stocks_no_mislabeled_foundries(self):
        stocks=[sample("3034","聯詠"),sample("2330","台積電"),
                sample("1303","南亞"),sample("3310","佳穎","上櫃")]
        memberships={
         "3034":[{"industry":"半導體","subCategory":"電源管理IC"}],
         "2330":[{"industry":"半導體","subCategory":"晶圓製造"}],
         "1303":[{"industry":"印刷電路板","subCategory":"銅箔"},{"industry":"印刷電路板","subCategory":"環氧樹脂"}],
         "3310":[{"industry":"連接器","subCategory":"金屬材料"},{"industry":"汽車","subCategory":"其他"}]}
        p=compile_map(stocks,memberships,"2026-10-12")
        self.assertEqual(p["dataDate"],"2026-10-12")
        self.assertEqual(p["coverage"]["verifiedCompanyPages"],4)
        self.assertEqual(p["coverage"]["distinctUpstreamStocks"],3)
        self.assertEqual(p["coverage"]["upstreamMemberships"],5)
        sectors={i["code"]:i for i in p["industries"]}
        semi=[x["code"] for group in sectors["D000"]["subgroups"] for x in group["stocks"]]
        self.assertEqual(semi,["3034"])
        self.assertEqual(sectors["L000"]["stockCount"],1)
        self.assertEqual(sectors["K000"]["stockCount"],1)
        self.assertEqual(sectors["3000"]["stockCount"],1)
    def test_bad_html_with_no_arrow_never_assumed_upstream(self):
        self.assertEqual(read_memberships("<html>半導體 晶圓製造 IP設計</html>"),[])
    def test_all_mapped_sectors_have_unique_official_source(self):
        self.assertEqual(len(INDUSTRIES),8)
        self.assertEqual(len({i["code"] for i in INDUSTRIES}),8)
        self.assertTrue(all(i["groups"] and i["keys"] for i in INDUSTRIES))
if __name__=="__main__":unittest.main()
