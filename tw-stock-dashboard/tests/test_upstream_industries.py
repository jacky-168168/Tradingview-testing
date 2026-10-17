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
    def test_cpo_research_separate_ninth_sector_does_not_mislabel_fabs_or_switch_systems(self):
        stocks=[sample("3081","聯亞","上櫃"),sample("3163","波若威","上櫃"),sample("3363","上詮","上櫃"),
                sample("4977","眾達-KY","上櫃"),sample("2330","台積電"),sample("2317","鴻海")]
        membership={z["code"]:[] for z in stocks}
        result=compile_map(stocks,membership,"2026-10-12")
        sector=next(x for x in result["industries"] if x["code"]=="CPO")
        self.assertIn("CPO",sector["name"])
        self.assertEqual(len(sector["subgroups"]),3)
        groups={g["name"]:g for g in sector["subgroups"]}
        self.assertEqual({x["code"] for x in groups["InP／GaAs 磊晶及雷射材料（核心上游）"]["stocks"]},{"3081"})
        self.assertEqual({x["code"] for x in groups["FAU／光纖陣列與精密耦合（核心上游）"]["stocks"]},{"3163","3363"})
        self.assertEqual({x["code"] for x in groups["外部雷射 ELS／光主動元件（上游供應）"]["stocks"]},{"4977"})
        self.assertEqual(result["coverage"]["classifiedBySource"]["cpo_industry_research"],4)
        self.assertEqual(result["audit"]["cpoResearchSource"],"https://www.trendforce.com.tw/presscenter/news/20260727-13150.html")
        self.assertEqual(sector["stockCount"],4)
        self.assertNotIn("2330",{z["code"] for g in sector["subgroups"] for z in g["stocks"]})
        self.assertNotIn("2317",{z["code"] for g in sector["subgroups"] for z in g["stocks"]})
        self.assertTrue(all(x["basis"]=="cpo_industry_research" and x["source"].startswith("https://") and "不等於" in x["roleNote"] for g in sector["subgroups"] for x in g["stocks"]))
    def test_research_splits_substrate_maker_and_pcb_material_drill_from_official_upstream(self):
        stocks=[sample("8021","尖點"),sample("2383","台光電"),sample("3037","欣興"),
                sample("8046","南電"),sample("3189","景碩"),sample("1303","南亞"),
                sample("2313","華通"),sample("3491","昇達科","上櫃"),sample("2330","台積電")]
        memberships={x["code"]:[] for x in stocks}
        memberships["1303"]=[{"industry":"印刷電路板","subCategory":"玻璃纖維/玻纖布"}]
        r=compile_map(stocks,memberships,"2026-10-16")
        groups={x["code"]:x for x in r["industries"]}
        self.assertEqual(len(groups),11)
        pcb={g["name"]:g for g in groups["L000"]["subgroups"]}
        ccl=pcb["銅箔基板 CCL／高速基材（中游延伸）"]
        drill=pcb["PCB 精密鑽針／鑽孔耗材（製程上游供應）"]
        self.assertEqual({x["code"] for x in ccl["stocks"]},{"2383","1303"})
        self.assertEqual({x["code"] for x in drill["stocks"]},{"8021"})
        self.assertIn("中游",ccl["stage"])
        self.assertNotIn("8021",{x["code"] for x in pcb["玻璃纖維／玻纖布"]["stocks"]})
        subs={g["name"]:g for g in groups["IC_SUB"]["subgroups"]}
        self.assertEqual({x["code"] for x in subs["ABF／BT IC 載板製造（中游）"]["stocks"]},{"3037","8046","3189"})
        self.assertIn("中游",subs["ABF／BT IC 載板製造（中游）"]["stage"])
        self.assertNotIn("3037",{x["code"] for x in subs["載板用樹脂／材料（上游跨應用）"]["stocks"]})
        leo={g["name"]:g for g in groups["LEO"]["subgroups"]}
        self.assertEqual({x["code"] for x in leo["衛星用高頻 PCB／HDI（製板）"]["stocks"]},{"2313"})
        self.assertEqual({x["code"] for x in leo["衛星射頻／毫米波／天線零組件（上游）"]["stocks"]},{"3491"})
        self.assertNotIn("2330",{x["code"] for g in groups["LEO"]["subgroups"] for x in g["stocks"]})
        research=[v for sec in groups.values() for g in sec["subgroups"] for v in g["stocks"] if v["basis"]=="industry_theme_research"]
        self.assertTrue(all(z["source"].startswith("https://") and "不等於" in z["roleNote"] for z in research))
        self.assertEqual(len(research),9)
        self.assertEqual(r["coverage"]["classifiedBySource"]["industry_theme_research"],9)
        self.assertEqual(r["coverage"]["verifiedCompanyPages"],9)
    def test_curated_codes_name_market_must_match_actual_archive(self):
        with self.assertRaisesRegex(RuntimeError,"Research stock code/name/market conflict"):
            compile_map([sample("8021","台積電")],{"8021":[]},"2026-10-16")
    def test_bad_html_with_no_arrow_never_assumed_upstream(self):
        self.assertEqual(read_memberships("<html>半導體 晶圓製造 IP設計</html>"),[])
    def test_all_mapped_sectors_have_unique_official_source(self):
        self.assertEqual(len(INDUSTRIES),11)
        self.assertEqual(len({i["code"] for i in INDUSTRIES}),11)
        self.assertTrue(all(i["groups"] for i in INDUSTRIES))
        self.assertTrue(all(i["keys"] for i in INDUSTRIES if i["code"] not in ("CPO","LEO","IC_SUB")))
        self.assertFalse(next(i for i in INDUSTRIES if i["code"]=="CPO")["keys"],"CPO must not masquerade as an official TPEx sector")
if __name__=="__main__":unittest.main()
