import unittest,tempfile,json
from datetime import datetime,timedelta,timezone
from pathlib import Path
from unittest.mock import patch
import numpy as np,pandas as pd
from scoring import calc_metrics,precompute_features,d_pass,institution_score,ema
from edge import build
from sar import parabolic_sar
from institution import parse_twse
import pipeline
from pipeline import _normalize_company,published_data_date,previous_f2_state
from industry_chain import looks_mojibake,parse as parse_chain
import risk,yahoo_cache
from backtest import _portfolio_stats,_has_unadjusted_scale_jump,effective_backtest_end
from bubbles import classify as bubble_classify

class CoreTests(unittest.TestCase):
    def frame(self,n=100):
        x=np.arange(n,dtype=float);c=50+x*.35+np.sin(x/5);o=c-.2;h=c+1.2;l=c-1.0;v=1_000_000+x*10000
        return pd.DataFrame({"date":pd.date_range("2026-01-01",periods=n).strftime("%Y-%m-%d"),"open":o,"high":h,"low":l,"close":c,"volume":v})
    def test_vector_features_match_scalar_last_bar(self):
        d=self.frame();a=calc_metrics(d);b=precompute_features(d).iloc[-1]
        for k in ["dayRet","ret5","ret20","ma20","ma60","ma20Slope","rvol","rvol10","mom10Pct","ema20","ema50","ema20Slope5","prevHigh20","breakoutPct","atrPct","volD","closePosition"]:
            self.assertAlmostEqual(float(a[k]),float(b[k]),places=7,msg=k)
    def test_120_bar_ema_window_matches_gas_slice(self):
        d=self.frame(220);x=precompute_features(d).iloc[-1];c=d["close"].astype(float)
        self.assertAlmostEqual(float(x["ema20"]),ema(c.iloc[-120:],20),places=7)
        self.assertAlmostEqual(float(x["ema50"]),ema(c.iloc[-120:],50),places=7)
        self.assertAlmostEqual(float(x["ema20Slope5"]),(ema(c.iloc[-120:],20)/ema(c.iloc[-120:-5],20)-1)*100,places=7)
    def test_tpex_company_field_mapping(self):
        x=_normalize_company({"SecuritiesCompanyCode":"6147","CompanyAbbreviation":"頎邦","Paidin.Capital.NTDollars":"7445775390","SecuritiesIndustryCode":"24"},"上櫃")
        self.assertEqual(x["code"],"6147");self.assertEqual(x["name"],"頎邦");self.assertAlmostEqual(x["capitalB"],74.4577539);self.assertEqual(x["industry"],"半導體業")
    def test_legacy_t86_field_match_parity(self):
        j={"fields":["證券代號","外陸資買賣超股數(不含外資自營商)","外資自營商買賣超股數","投信買賣超股數","自營商買賣超股數"],"data":[["6278","3474693","0","59000","362826"]]}
        x=parse_twse(j)["上市_6278"];self.assertEqual(x["foreign"],3474693);self.assertEqual(x["trust"],59000);self.assertEqual(x["dealer"],0)
    def test_d_thresholds_are_strict(self):
        base={"volume":20_000_001,"rvol10":1.2001,"mom10Pct":.01,"volD":10.01};self.assertTrue(d_pass(base))
        for k,v in [("volume",20_000_000),("rvol10",1.2),("mom10Pct",0),("volD",10)]:
            x=base.copy();x[k]=v;self.assertFalse(d_pass(x),k)
    def test_institution_weight_v122(self):
        self.assertEqual(institution_score({"foreign":1,"trust":1,"dealer":1}),10);self.assertEqual(institution_score({"foreign":1,"trust":0,"dealer":0}),5);self.assertEqual(institution_score({"foreign":0,"trust":1,"dealer":0}),7)
    def test_edge_all_horizons(self):
        m={}
        for mid in ["A","D","F","F2"]:m[mid]={h:[{"date":str(i),"ret":(1.5 if i%4 else -1.0)+(0.2 if mid in ("D","F") else 0)} for i in range(1,121)] for h in [1,3,5,10,20]}
        x=build(m)
        for mid in ["A","D","F","F2"]:
            for h in [1,3,5,10,20]:
                z=x["models"][mid][f"d{h}"];self.assertGreater(z["n"],0);self.assertIn(z["verdict"],{"gambling","insufficient","luck_suspected","fragile_edge","statistical_edge"})
    def test_sar_uptrend(self):
        x=parabolic_sar(self.frame(80));self.assertIsNotNone(x);self.assertIn("bullish",x);self.assertGreaterEqual(x["trendBars"],1)
    def test_industry_chain_utf8_guard(self):
        self.assertTrue(looks_mojibake("å¹³é¢é¡¯ç¤ºå¨"));self.assertFalse(looks_mojibake("平面顯示器"))
        x=parse_chain("<div>► 電子零組件 > 連接器</div>");self.assertEqual(x["subIndustry"],"電子零組件");self.assertEqual(x["theme"],"連接器")
    def test_yahoo_future_only_fetch_skips_network(self):
        future=datetime.now(timezone.utc).replace(tzinfo=None)+timedelta(days=1)
        with patch("yahoo_cache.requests.get") as get:
            x=yahoo_cache._fetch("^TWII",future,future+timedelta(hours=1))
            self.assertTrue(x.empty);get.assert_not_called()
    def test_adjusted_cache_backfill_detection(self):
        d=self.frame(40);start=datetime(2026,1,5);end=datetime(2026,2,5)
        self.assertTrue(yahoo_cache._needs_adj_backfill(d,start,end))
        d["adjclose"]=d["close"];self.assertFalse(yahoo_cache._needs_adj_backfill(d,start,end))
    def test_scale_jump_guard_even_with_adjclose(self):
        d=self.frame(6);d["close"]=[100,101,102,5,5.2,5.4];d["open"]=d["close"];d["high"]=d["close"]*1.01;d["low"]=d["close"]*.99;d["adjclose"]=d["close"]
        self.assertTrue(_has_unadjusted_scale_jump(d,d.iloc[0]["date"],d.iloc[-1]["date"]))
    def test_portfolio_stats_cost_aware(self):
        dates=pd.date_range("2026-01-01",periods=12).strftime("%Y-%m-%d").tolist();idx=pd.DataFrame({"date":dates});pos={d:i for i,d in enumerate(dates)}
        px=pd.DataFrame({"date":dates,"open":[100+i for i in range(12)],"high":[101+i for i in range(12)],"low":[99+i for i in range(12)],"close":[101+i for i in range(12)],"adjclose":[101+i for i in range(12)],"volume":[1_000_000]*12}).set_index("date",drop=False)
        ranks={"D":{d:[{"code":"2330","market":"上市","rank":1}] for d in dates}}
        x=_portfolio_stats(dates,idx,pos,ranks,{"2330.TW":px},"D",1)
        self.assertGreater(x["investedPeriods"],0);self.assertIn("cagr",x);self.assertIn("maxDrawdown",x);self.assertAlmostEqual(x["costPct"],.585,places=3)
    def test_effective_backtest_end_excludes_today(self):
        now=datetime(2026,10,8,10,30,tzinfo=timezone.utc)
        self.assertEqual(effective_backtest_end("2026-10-08",now),"2026-10-07")
        self.assertEqual(effective_backtest_end("2026-10-07",now),"2026-10-07")
        with self.assertRaises(ValueError):effective_backtest_end("2026-10-09",now)
    def test_previous_f2_state_rebuilds_legacy_hysteresis(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);daily=root/"daily";daily.mkdir()
            (daily/"index.json").write_text(json.dumps([{"date":"2026-10-02"},{"date":"2026-10-01"}]),encoding="utf-8")
            (daily/"2026-10-01.json").write_text(json.dumps({"risk":{"score":60,"activeState":"⚪ Normal"}}),encoding="utf-8")
            (daily/"2026-10-02.json").write_text(json.dumps({"risk":{"score":57,"activeState":"⚪ Normal"}}),encoding="utf-8")
            with patch.object(pipeline,"DATA_DIR",root):
                self.assertTrue(previous_f2_state("2026-10-03"))
    def test_bubble_quadrants(self):
        self.assertEqual(bubble_classify(1,1),"漲潮")
        self.assertEqual(bubble_classify(1,-1),"輪動")
        self.assertEqual(bubble_classify(-1,1),"觀望")
        self.assertEqual(bubble_classify(-1,-1),"退潮")
    def test_published_date_never_regresses(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);latest=root/"latest.json";daily=root/"daily";daily.mkdir()
            latest.write_text(json.dumps({"dataDate":"2026-10-06"}),encoding="utf-8")
            (daily/"index.json").write_text(json.dumps([{"date":"2026-10-07"},{"date":"2026-10-05"}]),encoding="utf-8")
            with patch.object(pipeline,"LATEST_JSON",latest),patch.object(pipeline,"DATA_DIR",root):
                self.assertEqual(published_data_date(),"2026-10-07")
    def test_f_gate_rules(self):
        self.assertTrue(risk.f_gate({"score":60,"bottomState":"⚪ Bottom Watch"})["allowed"])
        x=risk.f_gate({"score":30,"bottomState":"🟢 Strong Bottom Reversal"});self.assertTrue(x["allowed"]);self.assertTrue(x["exception"])
        self.assertFalse(risk.f_gate({"score":59,"bottomState":"🟣 Extreme Oversold"})["allowed"])
    def test_f2_gate_hysteresis_and_veto(self):
        x=risk.f2_gate({"score":60,"activeState":"⚪ Normal"},False,60,55);self.assertTrue(x["allowed"]);self.assertTrue(x["stateOn"]);self.assertEqual(x["reason"],"RISK_ON_ENTRY")
        x=risk.f2_gate({"score":57,"activeState":"⚪ Normal"},True,60,55);self.assertTrue(x["allowed"]);self.assertEqual(x["reason"],"HYSTERESIS_HOLD")
        x=risk.f2_gate({"score":54,"activeState":"⚪ Normal"},True,60,55);self.assertFalse(x["allowed"]);self.assertFalse(x["stateOn"])
        x=risk.f2_gate({"score":80,"activeState":"🔴 Strong Top Reversal","topState":"🔴 Strong Top Reversal"},True,60,55);self.assertFalse(x["allowed"]);self.assertTrue(x["topVeto"]);self.assertFalse(x["stateOn"])
        x=risk.f2_gate({"score":35,"activeState":"🟢 Strong Bottom Reversal","bottomState":"🟢 Strong Bottom Reversal"},False,60,55);self.assertTrue(x["allowed"]);self.assertTrue(x["exception"]);self.assertFalse(x["stateOn"])
    def test_historical_risk_no_network(self):
        x=risk.build_historical(self.frame(80),breadth_value=60,foreign_value=10)
        self.assertGreaterEqual(x["score"],0);self.assertLessEqual(x["score"],100);self.assertIn("activeState",x)
    @patch("risk.breadth",return_value=(650,350))
    @patch("risk.foreign_market_net",return_value=25.0)
    def test_risk_build(self,_f,_b):
        x=risk.build(self.frame(80));self.assertGreaterEqual(x["score"],0);self.assertLessEqual(x["score"],100);self.assertIn(x["mode"],{"NORMAL","BOTTOM","TOP"})
if __name__=="__main__":unittest.main()
