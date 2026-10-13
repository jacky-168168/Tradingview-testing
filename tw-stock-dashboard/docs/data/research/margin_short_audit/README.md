# 融資融券與大盤預測力：研究狀態（2026-10-13）

## 已核對

- 使用者提供的「證券進出行情」截圖：2026/09/08～2026/10/13，共 **23 個交易日**，含融資金額（億元）、增減、融資維持率、融券張數、增減、券資比、指數收盤及日漲跌。
- 23 日加權指數收盤均與本站獨立歷史資料核對一致（允差 0.05 點）。
- 在 4 指標 × 3 個時間窗口（當日、隔日、未來五日）中共做 12 個探索性相關測試。最強的隔日名目值：券資比 r=+0.469、n=22、未校正 p≈0.028，但 12 組 Bonferroni 校正後 p≈0.336，**不具充分穩健性**。
- 融資增減與當日報酬 r≈+0.405、隔日報酬 r≈+0.035，顯示「同日資金跟隨行情」的合理可能性，**不能視為隔日預測力**。
- 相鄰融資融券餘額差不必恰好等於網站顯示的當日增減，官方明示有跨日改帳與資料更正；我們保留異常而不偷偷更正。2026/10/01 融資增減差額約 0.45 億元。

## 官方資料來源

- 證交所：<https://www.twse.com.tw/zh/trading/margin/mi-margn.html>
- 歷史查詢：`rwd/zh/marginTrading/MI_MARGN` 或 `exchangeReport/MI_MARGN`，`selectType=MS`。
- 融資金額官方報表單位為「仟元」；除以 100,000 才是「億元」。
- 同一官方報表有「前日餘額」「今日餘額」，增減應先以同報表兩欄計算，因為歷史次日修正會使隔日餘額快照相減出現不同數字。
- 官方**不提供**這張截圖的「融資維持率」長期序列；不得由融資金額或券資比代算維持率。
- 官方只涵蓋 TWSE 上市，不應宣稱已取得全部上櫃資料。
- TWSE 使用條款：<https://www.twse.com.tw/zh/terms/use.html>。公開版本發布研究摘要及統計，不直接散布官方完整歷史原始數列，以避免未經確認的轉載授權。

## 三年資料回補

程式：`tw-stock-dashboard/scripts/backfill_margin_short.py`

手動參考：
```bash
python tw-stock-dashboard/scripts/backfill_margin_short.py --from-date 2023-10-11 --to-date 2026-10-13 --max-days 800 --delay 1.4
node tw-stock-dashboard/scripts/evaluate_margin_short_history.cjs
```
官方歷史回補工作由 `.github/workflows/twse-margin-backfill.yml` 執行；產生完整統計報告時，只將 `official_study.json` 和缺口統計 `fetch_status.json` 寫入 GitHub；原始官方每日資料僅暫存在 Actions Runner，**不公開整包原始資料**。

本研究頁在資料完整前顯示「待回補」，不推測三年相關係數。即使取得完整資料，仍需以訓練期 2023–2025 / 後驗期 2026，檢查樣本量、缺口、同期/隔日關係、多重比較、交易成本與原版 Risk Score 增量效果，並考慮事後更正造成的不完全 point-in-time 問題。

**符合任何單一正相關條件都不足以自動調整風控評分。**

## 尚未影響正式交易分析

- `market-command.js` Risk Score、原版大盤信號、G 選股、F/F2、`dynamic-exposure.js` 逆向資金水位均保持原公式。
- 首頁只增加「融資券研究（未納入）」連結。沒有使用 T 日收盤後才公布的信用資料去偽造 T 日買點。
