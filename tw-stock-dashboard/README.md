# 台股量化選股 Dashboard — GitHub/Python 正式版

這個目錄是 Google Apps Script V12.2 的 GitHub/Python 正式移植版本。主運算已改由 GitHub Actions + Python 執行；Google Apps Script 暫時保留作備援與交叉驗證。

## 正式架構
- **D 技術強勢模型：主模型**
- **F 大盤濾網模型：D + Market Regime Gate**
- **A 原始多因子模型：備用 / 對照模型**
- A / D / F 每次完整掃描會同時產生並寫入同一份 JSON，前端切換模型不需重新計算。
- F 規則：Risk Score >= 60 才允許 D 訊號；唯一例外為 Strong Bottom Reversal，該狀態只接受 D Top1～Top3。
- 09:00 / 10:30 / 12:30 / 13:00：只更新現有 A/D Top20 盤中價格。
- 18:30 / 21:30：完整市場重掃，更新 K 線、Risk、Top/Bottom Watch、SAR、法人、題材與歷史快照。
- 長區間回測使用 **TW Stock Backtest** 手動 Workflow，可輸入自訂開始 / 結束日期。
- Yahoo 日 K 使用 Parquet 雙向增量快取；重疊區間不重抓。
- GitHub Pages 直接讀取已產生 JSON，不再等待 Apps Script 現場運算。
- 完整更新加入交易日單調保護：若 Yahoo / benchmark 暫時回傳較舊交易日，不會覆蓋較新的已發布快照。

## 已完成
- 上市＋上櫃股票池。
- A / D / F 完整選股；F 由 D 加大盤 Gate 派生。
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
- GAS parity 改為手動的 2026-10-07 固定快照稽核，避免未來日期用即時行情誤比舊 fixture 造成假失敗。
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

## F 模型與回測可信度
- 歷史 F Risk 使用當日以前的加權指數、上市 breadth 與 T86 外資淨買賣估值重建，不使用未來資料。
- 回測報酬優先使用 Yahoo adjusted close factor 修正公司行動；舊快取若無 adjclose，會排除明顯價格尺度跳變的報酬。
- 法人 API 失敗日期會低速序列重試，仍失敗會保留 missing 標記而非假裝資料完整。
- A 歷史排序補上 SAR bullish trend bonus 作同分排序，與正式排序邏輯更一致。

## G 強勢突破候選模型（2026 年研究版）
- 專屬頁面：`docs/g-backtest.html`。原 A/D/F/F2 選股模型、回測仍保持不變。
- 輸入資料：全市場上市櫃當日已有的已完成日K，逐日計算20D漲幅、MA20斜率、ATR%、20日高低波幅、成交額的全市場百分位。
- G_BASE 硬篩：股本 <500億、股價 >=10元；20D ≥75、MA20斜率 ≥85、ATR ≥70、波幅 ≥80、成交額 ≥80 的百分位；距離先前20日高點 ≥-18%。
- G Score = 30%×20D百分位 + 25%×斜率百分位 + 15%×波幅百分位 + 15%×成交額百分位 + 10%×ATR百分位 + 5%×高點接近度（距前高從−18%到0%線性映射0–100，突破前高算100）。
- G_RELAXED / G_STRICT 只用於敏感度比較，正式研究基準為 G_BASE。
- 回測區間固定為2026/01/01～2026/10/07；日K收盤選股→下一交易日開盤買入Top3，計算1D/3D/5D/10D/20D績效。
- 20筆發文樣本以**發文日前最後一個已完整收盤的交易日**判斷是否通過硬篩、排名Top20/Top3；周末及盤中訊號不使用當日收盤資料。
- 2026 回測 workflow：`.github/workflows/g-2026.yml`，成功後輸出`docs/data/backtest_g/2026-01-01_2026-10-07.json`。
- **研究限制**：G 由已知20筆訊號逆向推估，樣本命中不等於前瞻預測；下一交易日開盤買入與發文者的突破價掛單不同；公司母檔是現在的存續名單，有存活者偏差。

## G_TARGET：嘗試複製已公布 20 筆強勢股訊號（限 2026 年）
- 網頁：`docs/g-target.html`。保留 G_BASE、D、F、F2、A 既有模型。
- 目標不是盲目放寬強勢股條件，而是把每筆發文日前最後一個完整交易日的股票與**同一天全市場候選股**進行特徵對照，以小樣本規則化條件式排名學習。
- G_TARGET 研究候選門檻：股價≥10、20D百分位≥60、MA20斜率≥70、ATR≥55、20日波幅≥65、成交額≥65、距前20日高點≥−25%、有有效股本。比 G_BASE 寬，是為了讓模型先辨別類型。沒有寫死任何股票代碼，股本不設500億上限，避免直接排除樣本中的 2409 友達。
- G_TARGET 以 2026/8/24～9/20 發布的前 11 筆訓練（最後訓練基準日9/18）；2026/10/2～10/8 的後 9 筆作為時間順序留出驗證。資料標籤僅依日期、代碼核對已知發訊樣本，評分特徵**不含代碼、股票名稱與未來行情**。
- 使用全市場每日13種百分位 + 距20日高點 + log股本，對當日候選股票進行有正則化的 conditional softmax 排名；單一股票不可能僅憑20筆正例保證可被唯一辨識。
- 提供 G_TARGET_FULL20 僅供**樣本內擬合診斷**，絕不可把已參與訓練的20/20命中當成樣本外預測成功。
- 結果：`docs/data/backtest_g/target_2026.json`，隨`.github/workflows/g-2026.yml`在同一次 GitHub Action 重跑。保留1D/3D/5D/10D/20D、Top3績效、訓練/留出命中、G_BASE同日名次對照與每筆失誤。
- 2026全年回測屬**回顧性研究**，因模型權重來自2026年8～9月，不能把2026年初的績效宣稱為真正可在當時運行的前瞻績效；訓練截止後才有少量真正的時間樣本外資料。

## G 2026 3D／18D 紅吞與突破假說
- 研究頁：`docs/g-candles.html`；原始 G_BASE/G_TARGET 保留，沒有直接覆蓋。
- **真正 3D、18D**：依 TradingView 多日週期從每年一月第一個交易日重新計算，每3/18個交易日 OHLC 合併成一根 K；不是每日滑動視窗的3/18根日K。
- **發訊時點**：20筆全部只用發文前最後一個已結束的日K；形成中的3D/18D可觀察方向，但不算已確認紅吞。
- **紅吞**：前一根跌K、後一根漲K，後一根的實體從開盤到收盤完整吞過前一根實體，與純粹收紅不同。另列穿透前根完整高低範圍的「全幅吞噬」供診斷。
- 個別研究：`src/research_multiday.py`，輸出`docs/data/research/g_multiday_2026.json`與CSV；同日強勢候選對照：`src/research_multiday_controls.py`，輸出`docs/data/research/g_multiday_controls_2026.json`。
- 年度比較：`src/backtest_candle.py`比較G_BROAD純強勢、G_CANDLE型態加分、G_TRIGGER前高突破或紅吞觸發，輸出`docs/data/backtest_g/g_candle_2026.json`，2026日K收盤選股後下一交易日開盤模擬進場，1/3/5/10/20D。
- 基於僅20筆已知訊號設計的參數都屬回顧性探索；市場對照組並非與發訊者的非發訊決策完全一致，尚需未來新發文訊號作時間上真正未見資料驗證。沒有複製作者的指定突破價格與停損算法。

## 網站進入密碼（瀏覽器端；非資料保密機制）
- 所有 8 個 `docs/*.html` 頁面均載入 `docs/site-access.js`，直接開啟子頁也會出現密碼畫面；沿用原選股應用的網站通行碼（檔案只存驗證雜湊，不存明碼）。
- 首次輸入正確後，這台裝置／瀏覽器使用 `localStorage` 保留 48 小時，下方「🔒 鎖定網站」可立即登出；清除瀏覽器儲存資料也會重新要求通行碼。
- 驗證在瀏覽器內完成；**這不是伺服器身分驗證**。任何人仍可直接取得 GitHub Pages 上的 HTML、JS、JSON，以及公開 GitHub 倉庫原始碼；瀏覽器端檢查也能被技術性繞過。不能用來保護個人資料、交易秘密或商業機密。
- 要真正限制訪客及資料下載，必須改為伺服器端驗證（例如搬到支援會員登入／存取政策的託管服務），並將需要保護的資料移離公開 GitHub 倉庫；只有前端登入頁是不夠的。
- 修改網站密碼應先計算 `SHA-256(SITE_SALT + ":" + 新密碼)`，更新 `docs/site-access.js` 的 `SITE_PASS_SHA256`；換密碼時也應更換 `ACCESS_KEY`，使舊瀏覽器登入記錄失效。測試：`node tw-stock-dashboard/tests/test_site_access.cjs`。
