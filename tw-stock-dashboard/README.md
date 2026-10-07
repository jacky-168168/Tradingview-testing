# 台股 A/D Dashboard — GitHub/Python 移植版

這個目錄是 Google Apps Script V12.2 的 GitHub/Python 移植主線。目標是把最耗時的全市場資料、A/D 排名與長區間回測搬到 GitHub Actions + Python，而不是只把 HTML 放到 Pages。

## Phase 1
- A 原始多因子模型核心評分。
- D 技術強勢模型：Volume > 20M、RVOL10 > 1.2、Mom10 > 0、Vol.D > 10%。
- TWSE / TPEx 股票母檔。
- GitHub Pages A/D 快速切換。

## Phase 2（目前）
- Yahoo 日 K：每檔 Parquet **雙向增量快取**，已覆蓋日期不重抓。
- A/D Python 自訂日期回測：Top3、下一交易日開盤進場、1D/3D/5D/10D/20D、Top3 固定三槽。
- Edge Audit：Expectancy、PF、Sharpe、Sortino、MDD、單尾 t-test、centered bootstrap、OOS 70/30、Monte Carlo。
- 歷史法人回測沿用 V12.2 口徑：TWSE T86；上櫃法人暫時視為 0 分。
- 手動 GitHub Action：`.github/workflows/tw-stock-backtest.yml`。
- Pages 回測頁：`tw-stock-dashboard/docs/backtest.html`。

## 如何跑長區間回測
合併到 `main` 後：
1. GitHub → Actions。
2. 選 **TW Stock Backtest**。
3. 按 **Run workflow**。
4. 輸入開始 / 結束日期。
5. 結果輸出到 `tw-stock-dashboard/docs/data/backtest/latest.json`，Pages 會讀取顯示。

第一次建立約 1982 檔歷史快取仍需抓資料；之後重疊日期會沿用 Actions cache，只補缺少前段 / 後段，不再像 GAS 每月重新抓整批。

## 尚未完全移植
- 即時法人面板
- Market Risk
- Top Watch
- 題材熱度
- SAR 顯示與現行 Dashboard 所有欄位 1:1 對齊

驗證 GitHub 版前，原 Apps Script 先保留。
