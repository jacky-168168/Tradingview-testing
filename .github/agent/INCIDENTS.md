# 永久故障知識庫

| 日期 | 症狀 | 根因證據 | 永久防護 | 回歸測試 |
|---|---|---|---|---|
| 2026-10-27 | TX Futures Day Night Dashboard 在 12:57 執行時，已通過台指即時報價驗證，但假日復市 UI 測試中斷，後續正式期貨同步與發布被跳過 | [Actions #40452561071](https://github.com/jacky-168168/Tradingview-testing/actions/runs/40452561071) 的 `test_market_holiday_hero.cjs:30` 仍要求 `commandCashReference` 顯示 `46,809`，但目前此欄位明確顯示非正式 18/100 參考試算，成交點數改在 `commandFullFlags` 的已驗證證據中呈現 | 不修改風險分數或交易邏輯；讓測試檢查實際證據位置與非正式標示，且過期報價不得殘留；將測試納入獨立 TW Stock Python CI | `test_market_holiday_hero.cjs`（固定 2026-10-27 09:08 時鐘） |
| 2026-10-21～23 | 臺灣盤中 G 隔日資料仍被顯示 | GitHub Actions 盤中 cron 缺席，手動補跑有效；未證實 GitHub 內部缺席成因 | 外部排程與雙層驗證；資料不過期時才顯示正常 | Agent freshness／holiday／missing-run tests |
| 2026-10-24 | 新聞停在 10/21 | \`test_market_events_ui.cjs\` 強制要求顯示已結束 TPCA 展覽，阻擋 publish | 改成固定時間測試及新鮮度限制 | 日期固定的 UI regression |
| 2026-10-21 | 主排程時間由 :00/:30 調整後 CI 失敗 | 舊測試寫死 cron 值 | 排程測試跟實際規格同步、避免過度指定字面值 | \`test_intraday_schedule.cjs\` |

每次 P1/P2 修復後新增一筆，必須提供 Actions run、原始輸入、可重現步驟與驗收連結；不可自行編造「根本原因」。
