# 台股量化選股 Dashboard — GitHub/Python 正式版

這個目錄是 Google Apps Script V12.2 的 GitHub/Python 正式移植版本。主運算已改由 GitHub Actions + Python 執行；Google Apps Script 暫時保留作備援與交叉驗證。

## 正式架構
- **D 技術強勢模型：主模型**
- **A 原始多因子模型：備用 / 對照模型**
- A / D 每次完整掃描會同時產生並寫入同一份 JSON，前端切換模型不需重新計算。
- 09:00 / 10:30 / 12:30 / 13:00：只更新現有 A/D Top20 盤中價格。
- 18:30 / 21:30：完整市場重掃，更新 K 線、Risk、Top/Bottom Watch、SAR、法人、題材與歷史快照。
- 長區間回測使用 **TW Stock Backtest** 手動 Workflow，可輸入自訂開始 / 結束日期。
- Yahoo 日 K 使用 Parquet 雙向增量快取；重疊區間不重抓。
- GitHub Pages 直接讀取已產生 JSON，不再等待 Apps Script 現場運算。

## 已完成
- 上市＋上櫃股票池。
- A / D 完整選股與 Top20。
- Market Risk Score。
- Bottom / Top Watch。
- Parabolic SAR（上一根已確認日 K）。
- TWSE T86 法人與同買 / 同賣 Top5。
- 題材熱度與 TPEx 產業價值鏈。
- 盤中 Top20 快速刷新。
- 每日歷史快照。
- 自訂日期回測。
- 1D / 3D / 5D / 10D / 20D Edge Audit。
- Expectancy、PF、Sharpe、Sortino、MDD、t-test、bootstrap、OOS、Monte Carlo。
- Python 單元測試與 GAS V12.2 parity 驗證。
- GitHub Pages 正式 UI。

## 2026-10-07 對齊驗證
- A Top20：20/20 重疊，名次完全相同，Score MAD = 0。
- D：10/10 重疊，名次完全相同，Score MAD = 0。
- Market Risk：60 vs 60，差異 0。
- Production：1950 / 1950 檔歷史 K 成功，historyErrors = 0。
- Python CI 與 Full Parity workflow 通過。

## 網頁
- 主選股：`tw-stock-dashboard/docs/index.html`
- 歷史快照：`tw-stock-dashboard/docs/history.html`
- 回測 / Edge：`tw-stock-dashboard/docs/backtest.html`

## 手動回測
GitHub → Actions → **TW Stock Backtest** → Run workflow → 輸入開始 / 結束日期。

結果會寫入：
- `docs/data/backtest/latest.json`
- `docs/data/backtest/YYYY-MM-DD_YYYY-MM-DD.json`
- `docs/data/backtest/index.json`

## 注意
目前 repository 是公開的，因此 GitHub Pages 與產出的 JSON 也是公開內容。不要把真正的密碼、API key 或券商憑證寫進前端或 repository。

原 Apps Script V12.2 先保留作備援；正式主線以 GitHub/Python 為準。
