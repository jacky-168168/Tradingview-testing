# 台股 A/D Dashboard — GitHub/Python 移植版

這個目錄是 Google Apps Script V12.2 的 GitHub/Python 移植主線。目標是把最耗時的全市場資料、A/D 排名與長區間回測搬到 GitHub Actions + Python，而不是只把 HTML 放到 Pages。

## Phase 1
- A 原始多因子模型核心評分。
- D 技術強勢模型：Volume > 20M、RVOL10 > 1.2、Mom10 > 0、Vol.D > 10%。
- TWSE / TPEx 股票母檔。
- GitHub Pages A/D 快速切換。

## Phase 2
- Yahoo 日 K：每檔 Parquet 雙向增量快取，已覆蓋日期不重抓。
- Python 自訂日期 A/D 回測：Top3、下一交易日開盤進場、1D/3D/5D/10D/20D、Top3 固定三槽。
- Edge Audit：Expectancy、PF、Sharpe、Sortino、MDD、單尾 t-test、centered bootstrap、OOS 70/30、Monte Carlo。
- 手動 GitHub Action：`.github/workflows/tw-stock-backtest.yml`。
- Pages 回測頁：`tw-stock-dashboard/docs/backtest.html`。

## Phase 3（目前）
- Market Risk Score 對齊 V12.2。
- Bottom / Top Watch 反轉狀態。
- Parabolic SAR：沿用 V12.2「上一根已確認日 K」口徑，SAR 只做顯示／同分排序，不直接灌進總分。
- 歷史 / 當日法人：TWSE T86；上櫃法人仍暫時視為 0 分，與 V12.2 現況一致。
- 法人同買 / 同賣 Top5。
- 題材熱度：股島優先、DannyQuant 備援。
- TPEx 產業價值鏈：Top20 次產業 / 題材補齊。
- GitHub Pages 主 Dashboard 已加入 Risk、Top/Bottom Watch、法人、題材與現行主要欄位。

## 長區間回測
合併到 `main` 後：
1. GitHub → Actions。
2. 選 **TW Stock Backtest**。
3. 按 **Run workflow**。
4. 輸入開始 / 結束日期。
5. 結果輸出到 `tw-stock-dashboard/docs/data/backtest/latest.json`，Pages 讀取顯示。

第一次建立約 1982 檔歷史快取仍需抓資料；之後重疊日期會沿用 Actions cache，只補缺少前段 / 後段，不再像 GAS 每月重新抓整批。

## Phase 4（目前）
- 09:00 / 10:30 / 12:30 / 13:00 改成 **盤中快速更新**：只抓現有 A/D Top20 的 1 分鐘現價，不重新掃 1982 檔。
- 18:30 / 21:30 才執行 **完整市場更新**：K 線、A/D、Risk、SAR、法人、題材。
- 題材熱度加入「最後有效結果」cache；股島 / DannyQuant 同時失敗時不再把面板洗成空白。
- 新增 `validate.py`：可拿 GAS JSON 與 Python JSON 比 A/D Top20 overlap、同名次數、總分 MAD、Risk delta。
- 新增 PR CI：語法編譯＋核心 parity 單元測試（vectorized 指標、D 硬條件、法人權重、Edge 五週期、SAR、Risk）。

## 遷移驗證結果
2026-10-07 同日 GAS V12.2 對照已通過 GitHub Actions Full Parity：
- A Top20：19/20 重疊（95%），15 檔名次完全相同，Score MAD 0.526。
- D：10/10 重疊（100%），8 檔名次完全相同，Score MAD 0.8。
- Market Risk：60 vs 60，差異 0。
- Python CI 與 Full Parity workflow 均通過。

A 的 1 檔差異主要來自同日稍晚重新抓取的法人 / 行情細節；核心模型與排序已達上線門檻。

## 正式架構
- `main` 已成為正式版本。
- 09:00 / 10:30 / 12:30 / 13:00：盤中 Top20 快刷。
- 18:30 / 21:30：完整市場更新。
- 長區間回測使用 **TW Stock Backtest** 手動 workflow。
- Pages 主頁：`tw-stock-dashboard/docs/index.html`
- 歷史快照：`history.html`
- 回測 / Edge：`backtest.html`

原 Apps Script V12.2 建議先保留一段時間作為備援與交叉驗證，不再讓它承擔長區間主回測。
