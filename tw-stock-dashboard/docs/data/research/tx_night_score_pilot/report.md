# TX 夜盤調整 Risk Score：短期因果性試驗 V1

**研究期間：** 2026-07-09～2026-10-08｜**配對有效交易日：** 58/62
**基準：** 前一交易日正式 Risk Score；以當日凌晨可得的同月份夜盤，評估當日現貨收盤漲跌及市場廣度。

| 夜盤情境 | 樣本 | 隔日現貨下跌 | 隔日平均漲跌 |
|---|---:|---:|---:|
| 跌幅 ≥1% | 9 | 8/9（88.9%） | -2.02% |
| 其餘夜盤 | 49 | 18/49（36.7%） | +0.59% |

隔夜跌 ≥1% 組隔日下跌率 95% Wilson 區間：[56.5, 98.0]%；僅探索性單尾 Fisher p=0.004988，不代表預註冊檢驗或可交易績效。
**實際改變 >=60 進場門檻的日數：0。** 原始允許 28 天，調整後仍允許 28 天，沒有已測得的交易門檻改善。

## 原則性結論
- 夜盤急跌的**方向性警報有歷史支持**，但以固定 -15 分得到 55 分的絕對刻度**尚未被驗證**。
- 應將 **55 分視為「昨收＋夜盤參考基準」**，當 TX 跌幅≤-1% 時維持獨立重大風險警示（暫緩追價與一般新倉）。
- 沒有經過真實個股 G 進出場、成本、停損及至少一年以上獨立樣本外測試，不能聲稱 G 選股報酬提高。

## 可稽核分組
- night<=-2: 2 天；收跌 1 天；平均 -2.925%
- -2<night<=-1: 7 天；收跌 7 天；平均 -1.761%
- -1<night<=-0.5: 7 天；收跌 5 天；平均 -0.123%
- -0.5<night<=0.5: 19 天；收跌 8 天；平均 0.215%
- 0.5<night<=1: 10 天；收跌 4 天；平均 0.291%
- night>1: 13 天；收跌 1 天；平均 1.763%

## 來源與限制
- 期貨交易資料固定於 [公開累積資料 Git commit](https://raw.githubusercontent.com/wenchiehlee-investment/TAIFEX/436c9782600af47d9a24b2479b7fefd3f4c2d252/data/raw_taifex_daily_futures.csv)。
- TAIFEX 夜盤交易日歸屬與日盤不同，須以 **前交易日一般盤與今天歸屬夜盤** 配對同一契約。
- 現貨 Risk Score 取本庫正式市場歷史 csv，使用前一日分數。
- 未有隔日開盤可成交價，不能把本報告當成策略交易損益。

其餘限制：Pilot July-October only; NOT the full 728-day score archive.; No fresh holdout; buckets were examined post hoc, so p-value is exploratory.; The severe-night subgroup is small and has low prior Risk Scores. Zero gate changes means NO measured gain in G entry gating.; Index close-to-close next-day return is NOT a tradable transaction price or a P&L backtest.; No 10/15 realized cash outcome has been used: current risk history stops at 10/08.; Futures were aggregated by an external open-source collector from exchange OpenAPI; need archival and independent official reconciliation.; Missing expiry/mismatched pairs are excluded, never synthesized.; Absolute +/- score points are heuristic: neither 15 nor 60 is empirically calibrated on an independent G performance holdout.
