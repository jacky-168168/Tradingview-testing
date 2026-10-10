"""Tests for published daily Top-list repeat counting without invented history."""
import json,tempfile,unittest
from pathlib import Path
from repeated_rankings import build,months_before

class RepeatArchiveTests(unittest.TestCase):
    def write(self,folder,days):
        index=[]
        for d,models in days:
            (folder/(d+".json")).write_text(json.dumps({"dataDate":d,"models":models},ensure_ascii=False),encoding="utf-8")
            row={"date":d}
            for key,field in (("G","gCount"),("G Pro","gProCount"),("D","dCount"),("A","aCount")):
                if key in models:row[field]=len(models[key])
            index.append(row)
        (folder/"index.json").write_text(json.dumps(index,ensure_ascii=False),encoding="utf-8")
    def test_G_missing_versus_empty_and_previous_seen(self):
        with tempfile.TemporaryDirectory() as t:
            folder=Path(t)
            s=lambda code,name="甲",market="上市":{"code":code,"name":name,"market":market,"close":100,"total":90}
            self.write(folder,[("2026-10-06",{"D":[s("1111"),s("2222")],"A":[s("3333")]}),
              ("2026-10-07",{"D":[s("1111"),s("2222")],"G":[]}),
              ("2026-10-08",{"D":[s("1111")],"G":[s("2330","台積電"),s("1111")],"G Pro":[]})])
            x=build(folder,"2026-10-08")
            self.assertEqual(x["windowStart"],"2026-08-08")
            self.assertEqual(x["models"]["G"]["snapshotDays"],2)
            self.assertEqual(x["models"]["G"]["signalDays"],1)
            self.assertEqual(x["models"]["G"]["repeatedSymbols"],0)
            self.assertEqual(x["models"]["G Pro"]["snapshotDays"],1)
            self.assertEqual(x["models"]["G Pro"]["signalDays"],0)
            self.assertEqual(x["models"]["D"]["stocks"][0]["code"],"1111")
            a=x["models"]["D"]["stocks"][0]
            self.assertEqual(a["count"],3)
            self.assertEqual(a["lastSeen"],"2026-10-08")
            self.assertEqual(a["previousSeen"],"2026-10-07")
            self.assertTrue(a["onReferenceDate"])
            self.assertEqual(a["dates"],["2026-10-06","2026-10-07","2026-10-08"])
    def test_distinct_market_codes_not_conflated(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)
            one={"code":"1234","market":"上市","name":"上市甲"}
            two={"code":"1234","market":"上櫃","name":"上櫃甲"}
            self.write(p,[("2026-10-06",{"G":[one,two]}),("2026-10-08",{"G":[one,two]})])
            rows=build(p,"2026-10-08")["models"]["G"]["stocks"]
            self.assertEqual(len(rows),2)
            self.assertEqual({r["market"] for r in rows},{"上市","上櫃"})
            self.assertTrue(all(r["count"]==2 for r in rows))
    def test_duplicate_snapshot_stock_fails_closed(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t);row={"code":"2330","market":"上市"}
            self.write(p,[("2026-10-08",{"G":[row,row]})])
            with self.assertRaisesRegex(RuntimeError,"Duplicate stock"):build(p)
    def test_older_than_two_calendar_months_excluded(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t);row={"code":"2330","market":"上市"}
            self.write(p,[("2026-08-07",{"G":[row]}),("2026-08-08",{"G":[row]}),
                          ("2026-09-08",{"G":[row]}),("2026-10-08",{"G":[row]})])
            r=build(p,"2026-10-08")
            self.assertEqual(r["models"]["G"]["stocks"][0]["count"],3)
            self.assertEqual(r["models"]["G"]["stocks"][0]["firstSeen"],"2026-08-08")
            self.assertEqual(r["calendarDaysAvailable"],3)
    def test_index_snapshot_mismatch_blocks_publication(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t);self.write(p,[("2026-10-08",{"G":[]})])
            (p/"index.json").write_text('[{"date":"2026-10-08","gCount":20}]',encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError,"mismatch"):build(p)
    def test_reconstruction_supplements_missing_G_only_never_replaces_frozen(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)
            old={"code":"2330","market":"上市","name":"原始真榜","total":99}
            recovered={"code":"2330","market":"上市","name":"歷史回推","total":80,
                "dataOrigin":"retrospectively_reconstructed_not_historical_snapshot"}
            self.write(p,[("2026-10-06",{"D":[{"code":"1111","market":"上市"}]}),
                          ("2026-10-08",{"G":[old],"G Pro":[]})])
            archive={"version":"G_LIVE_DOUBLE_PERSIST_HISTORICAL_RECONSTRUCTION_V1",
                "model":"G","referenceDate":"2026-10-08",
                "days":{"2026-10-06":{"dataDate":"2026-10-06","source":"reconstructed","stocks":[recovered]},
                        "2026-10-08":{"dataDate":"2026-10-08","source":"reconstructed","stocks":[recovered]}}}
            x=build(p,"2026-10-08",archive)
            self.assertEqual(x["version"],"TWO_CALENDAR_MONTHS_FROZEN_PLUS_RECONSTRUCTED_G_V2")
            g=x["models"]["G"]
            self.assertEqual(g["snapshotDays"],1)
            self.assertEqual(g["reconstructedDays"],1)
            self.assertEqual(g["repeatedSymbols"],1)
            record=g["stocks"][0]
            self.assertEqual(record["name"],"原始真榜")
            self.assertEqual(record["lastSeenSource"],"original_frozen")
            self.assertEqual(record["count"],2)
            self.assertEqual(record["reconstructedCount"],1)
            self.assertEqual(record["frozenCount"],1)
            self.assertEqual(record["previousSeen"],"2026-10-06")
            self.assertEqual(x["models"]["G Pro"]["reconstructedDays"],0)
            self.assertEqual(x["models"]["D"]["snapshotDays"],1)
    def test_end_of_month_window(self):
        self.assertEqual(months_before("2026-10-31"),"2026-08-31")
        self.assertEqual(months_before("2026-04-30"),"2026-02-28")
if __name__=="__main__":unittest.main()
