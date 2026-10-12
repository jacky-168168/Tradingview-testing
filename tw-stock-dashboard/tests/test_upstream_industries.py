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
        self.assertIsNone(stage_group(ind("D000"),"不明IC"),"Never infer unverified IC suffix as fabless design")
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
    def test_all_eight_official_stages_are_explicitly_limited_to_upstream(self):
        cases=[("D000","IP設計/IC設計代工服務","IC封裝測試"),
               ("L000","玻璃纖維/玻纖布","銅箔基板"),
               ("I000","網路IC","網路設備"),
               ("F000","中央處理器","伺服器"),
               ("K000","金屬材料","連接器"),
               ("3000","車燈","整車組裝"),
               ("A100","材料","太陽能電池模組"),
               ("A300","鋰電池材料","零組件")]
        for code,up,down in cases:
            with self.subTest(sector=code):
                self.assertIsNotNone(stage_group(ind(code),up))
                self.assertIsNone(stage_group(ind(code),down))
    def test_6488_and_three_peers_are_material_upstream_but_fabs_not_added(self):
        stocks=[sample("6488","環球晶","上櫃"),sample("3532","台勝科"),
                sample("6182","合晶","上櫃"),sample("3016","嘉晶"),
                sample("2330","台積電")]
        m={x["code"]:[{"industry":"半導體","subCategory":"晶圓製造"}] for x in stocks}
        p=compile_map(stocks,m,"2026-10-12")
        sector=next(z for z in p["industries"] if z["code"]=="D000")
        material=next(z for z in sector["subgroups"] if "半導體用矽晶圓" in z["name"])
        self.assertEqual({r["code"] for r in material["stocks"]},{"6488","3532","6182","3016"})
        self.assertTrue(all(r["basis"]=="independent_industry_material" for r in material["stocks"]))
        self.assertEqual({r["source"] for r in material["stocks"]},{"https://www.itis.org.tw/NetReport_Detail.aspx?rpno=613160445"})
        self.assertNotIn("2330",{r["code"] for g in sector["subgroups"] for r in g["stocks"]})
        self.assertEqual(p["audit"]["extendedMaterials"],["3016","3532","6182","6488"])
        self.assertEqual(p["schema"],"tw-upstream-industries-v2")
    def test_solar_paste_is_cross_sector_material_not_a_pure_play_label(self):
        k=sample("4760","勤凱科技","上櫃")
        p=compile_map([k],{"4760":[{"industry":"太陽能產業","subCategory":"材料"}]},"2026-10-12")
        sun=next(x for x in p["industries"] if x["code"]=="A100")
        g=next(g for g in sun["subgroups"] if "太陽能材料" in g["name"])
        self.assertEqual(g["stocks"][0]["code"],"4760")
        self.assertIn("非純太陽能股",g["stocks"][0]["roleNote"])
        self.assertIn("非",g["note"])
        self.assertEqual(g["stocks"][0]["basis"],"tpex_official")
    def test_comm_active_passive_and_uncertain_not_automatically_guessed(self):
        stocks=[sample("3081","聯亞","上櫃"),sample("3026","禾伸堂"),
                sample("2476","鉅祥"),sample("2327","國巨*"),
                sample("6284","佳邦","上櫃")]
        m={
         "3081":[{"industry":"通信網路","subCategory":"主/被動元件"}],
         "3026":[{"industry":"通信網路","subCategory":"主/被動元件"},{"industry":"被動元件","subCategory":"電容器"}],
         "2476":[{"industry":"通信網路","subCategory":"主/被動元件"}],
         "2327":[{"industry":"被動元件","subCategory":"電阻器"},{"industry":"被動元件","subCategory":"電容器"}],
         "6284":[{"industry":"通信網路","subCategory":"主/被動元件"}]
        }
        p=compile_map(stocks,m,"2026-10-12")
        comm=next(x for x in p["industries"] if x["code"]=="I000")
        groups={g["name"]:g for g in comm["subgroups"]}
        self.assertNotIn("主／被動元件",groups)
        active=groups["主動元件（光主動／晶片）"]
        passive=groups["被動元件（電阻電容／濾波等）"]
        pending=groups["待核對（官方混合分類）"]
        self.assertEqual({z["code"] for z in active["stocks"]},{"3081"})
        self.assertEqual({z["code"] for z in passive["stocks"]},{"3026","2327","6284"})
        self.assertEqual({z["code"] for z in pending["stocks"]},{"2476"})
        y=next(z for z in passive["stocks"] if z["code"]=="2327")
        self.assertEqual(y["basis"],"tpex_cross_industry")
        self.assertIn("被動元件產業本身屬中游",y["roleNote"])
        self.assertTrue(y["source"].endswith("stk_code=2327"))
        self.assertEqual(p["coverage"]["distinctUpstreamStocks"],5)
    def test_passive_microwave_supplier_and_active_laser_packager(self):
        stocks=[sample("3491","昇達科","上櫃"),sample("3152","璟德","上櫃"),sample("3450","聯鈞")]
        m={x["code"]:[{"industry":"通信網路","subCategory":"主/被動元件"}] for x in stocks}
        comm=next(x for x in compile_map(stocks,m,"2026-10-12")["industries"] if x["code"]=="I000")
        p=next(g for g in comm["subgroups"] if g["name"].startswith("被動元件"))
        a=next(g for g in comm["subgroups"] if g["name"].startswith("主動元件"))
        self.assertEqual({z["code"] for z in p["stocks"]},{"3491","3152"})
        self.assertEqual({z["code"] for z in a["stocks"]},{"3450"})
        self.assertTrue(all(z["basis"]=="company_product_verified" for z in p["stocks"]+a["stocks"]))
    def test_communications_component_without_verified_product_stays_pending(self):
        stocks=[sample("6470","宇智","上櫃")]
        m={"6470":[{"industry":"通信網路","subCategory":"主/被動元件"}]}
        comm=next(x for x in compile_map(stocks,m,"2026-10-12")["industries"] if x["code"]=="I000")
        self.assertEqual(next(g["count"] for g in comm["subgroups"] if g["name"].startswith("待核對")),1)
    def test_yageo_cannot_be_added_without_official_j000_proof(self):
        with self.assertRaisesRegex(RuntimeError,"missing TPEx J000"):
            compile_map([sample("2327","國巨*")],{"2327":[]}, "2026-10-12")
    def test_bad_html_with_no_arrow_never_assumed_upstream(self):
        self.assertEqual(read_memberships("<html>半導體 晶圓製造 IP設計</html>"),[])
    def test_all_mapped_sectors_have_unique_official_source(self):
        self.assertEqual(len(INDUSTRIES),8)
        self.assertEqual(len({i["code"] for i in INDUSTRIES}),8)
        self.assertTrue(all(i["groups"] and i["keys"] for i in INDUSTRIES))
if __name__=="__main__":unittest.main()
