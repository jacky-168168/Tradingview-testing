import unittest
from datetime import datetime,timedelta,timezone
from update_us_fear_greed import cnn_series,to_archive,valid_score
class TestUSFearGreed(unittest.TestCase):
    def fixtures(self):
        start=datetime(2025,1,1,tzinfo=timezone.utc)
        dates=[(start+timedelta(days=i)).date().isoformat() for i in range(255)]
        raw={"fear_and_greed_historical":{"data":[{"x":int((start+timedelta(days=i)).timestamp()*1000),"y":float((i*3)%100)} for i in range(255)]},
             "fear_and_greed":{"timestamp":"2025-09-12T21:00:00+00:00","score":45}}
        spx={"columns":["date","spx","dixPct","gex"],"rows":[[d,5000+i,45,1000] for i,d in enumerate(dates)]}
        # Source price minimum for quality gate is 500, expand earlier archive
        earlier=[[(start-timedelta(days=400-i)).date().isoformat(),4200+i,44,1000] for i in range(400)]
        spx["rows"]=earlier+spx["rows"]
        return raw,spx
    def test_date_alignment(self):
        c,s=self.fixtures();o=to_archive(c,s)
        self.assertEqual(o["version"],"US_CNN_FEAR_GREED_SPX_V2")
        self.assertEqual(o["columns"],["date","fearGreed","spx"])
        self.assertEqual(len(o["rows"]),255)
        self.assertEqual(o["rows"][-1][0],o["asOf"])
    def test_missing_score_not_fake_zero(self):
        c,s=self.fixtures();c["fear_and_greed_historical"]["data"][12]["y"]=None
        o=to_archive(c,s)
        self.assertEqual(len(o["rows"]),255)
        self.assertIsNone(o["rows"][12][1])
    def test_one_source_can_be_newer(self):
        c,s=self.fixtures()
        last=s["rows"][-1][0]
        s["rows"]=[r for r in s["rows"] if r[0]!=last]
        o=to_archive(c,s)
        self.assertEqual(o["asOf"],last)
        self.assertEqual(o["rows"][-1],[last,valid_score(c["fear_and_greed_historical"]["data"][-1]["y"]),None])
        self.assertEqual(o["spxLast"],s["rows"][-1][0])
    def test_reject_schema_and_nans(self):
        c,s=self.fixtures();s["columns"]=["date","spx","gex","dixPct"]
        with self.assertRaisesRegex(ValueError,"schema"):to_archive(c,s)
        self.assertIsNone(valid_score("NaN"))
        self.assertIsNone(valid_score(150))
        self.assertIsNone(valid_score(-1))
        self.assertIsNone(valid_score(True))
    def test_reject_too_short_history(self):
        c,s=self.fixtures()
        c["fear_and_greed_historical"]["data"]=c["fear_and_greed_historical"]["data"][:30]
        with self.assertRaisesRegex(ValueError,"insufficient"):cnn_series(c)
if __name__=="__main__":unittest.main()
