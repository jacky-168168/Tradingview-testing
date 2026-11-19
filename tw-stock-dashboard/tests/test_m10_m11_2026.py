import unittest
from research_m10_m11_2026 import parse_margin,growing_five,select_models,run_one
class TestM10M11(unittest.TestCase):
    def test_twse_margin_date_and_balances(self):
        rows=[[str(1000+i),"名",str(i+100),str(i+5)] for i in range(510)]
        p={"date":"20261015","tables":[{"fields":["代號","名稱","今日餘額","今日餘額"],"data":rows}]}
        v=parse_margin(p,"上市","2026-10-15")
        self.assertEqual(v["上市_1000"],[100,5])
        with self.assertRaisesRegex(ValueError,"wrong date"):
            parse_margin(p,"上市","2026-10-14")
    def test_tpex_field_names_and_date(self):
        rows=[[str(2000+i),"名",str(i+11),str(i+3)] for i in range(330)]
        p={"tables":[{"date":"115/10/15","fields":["代號","名稱","資餘額","券餘額"],"data":rows}]}
        v=parse_margin(p,"上櫃","2026-10-15")
        self.assertEqual(v["上櫃_2000"],[11,3])
        p["date"]="20261015"
        v=parse_margin(p,"上櫃","2026-10-15")
        self.assertEqual(v["上櫃_2000"],[11,3])
        p["date"]="20261014"
        with self.assertRaisesRegex(ValueError,"wrong date"):parse_margin(p,"上櫃","2026-10-15")
    def test_five_consecutive_rises_not_only_endpoints(self):
        days=[f"2026-01-{i:02d}" for i in range(2,8)]
        full={d:{"上市_1234":[20+i,7+i]} for i,d in enumerate(days)}
        self.assertTrue(growing_five(5,days,"上市_1234",full))
        full[days[2]]["上市_1234"]=[20,9]
        self.assertFalse(growing_five(5,days,"上市_1234",full))
        full[days[2]]["上市_1234"]=[22,9]
        del full[days[3]]["上市_1234"]
        self.assertFalse(growing_five(5,days,"上市_1234",full))
    def test_m10_industry_ratio_denominator_and_individual_gain(self):
        days=["2026-10-14"];universe=[]
        hist={};credits={days[0]:{}};inst={days[0]:{}}
        for i in range(10):
            code=str(2000+i);key="上市_"+code
            universe.append({"code":code,"name":"test","market":"上市","industry":"半導體業","capitalB":20})
            hist[key]={days[0]:{"close":35,"turnoverB":2,"ret5":11+i}}
            credits[days[0]][key]=[100,20]
            inst[days[0]][key]={"trust":1 if i<3 else 0}
        s=select_models(days,universe,hist,credits,inst)
        self.assertEqual(len(s["M10"][days[0]]),10)
        inst[days[0]]["上市_2002"]["trust"]=0
        s=select_models(days,universe,hist,credits,inst)
        self.assertEqual(s["M10"][days[0]],[])
    def test_entry_next_open_and_sell_cost(self):
        days=[f"2026-10-{i:02d}" for i in range(1,17)]
        stock={"date":days[0],"market":"上市","code":"1234","name":"a"}
        hist={"上市_1234":{d:{"adjOpen":20,"adjClose":20} for d in days}}
        s={days[0]:[stock]}
        x=run_one("M10",days,s,hist,hold=10)
        tr=x["trades10D"][0]
        self.assertEqual(tr["entryDate"],days[1])
        self.assertEqual(tr["exitDate"],days[10])
        self.assertLess(tr["netPct"],0)
        self.assertEqual(x["portfolio10D"]["closedTrades"],1)
if __name__=="__main__":unittest.main()
