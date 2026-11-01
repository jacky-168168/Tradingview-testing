# 永久故障知識庫

| 日期 | 症狀 | 根因證據 | 永久防護 | 回歸測試 |
|---|---|---|---|---|
| 2026-10-21～23 | 臺灣盤中 G 隔日資料仍被顯示 | GitHub Actions 盤中 cron 缺席，手動補跑有效；未證實 GitHub 內部缺席成因 | 外部排程與雙層驗證；資料不過期時才顯示正常 | Agent freshness／holiday／missing-run tests |
| 2026-10-24 | 新聞停在 10/21 | \`test_market_events_ui.cjs\` 強制要求顯示已結束 TPCA 展覽，阻擋 publish | 改成固定時間測試及新鮮度限制 | 日期固定的 UI regression |
| 2026-10-21 | 主排程時間由 :00/:30 調整後 CI 失敗 | 舊測試寫死 cron 值 | 排程測試跟實際規格同步、避免過度指定字面值 | \`test_intraday_schedule.cjs\` |

每次 P1/P2 修復後新增一筆，必須提供 Actions run、原始輸入、可重現步驟與驗收連結；不可自行編造「根本原因」。

| 2026-11-01 | ORION 最新新聞 174 篇，僅 152 篇判讀；第 6 次 Gemini 批次遇到未逐字出現在標題的 evidence，後續 22 篇未處理（[Actions #41310371001](https://github.com/jacky-168168/Tradingview-testing/actions/runs/41310371001)） | `infer()` 對單篇不合格 evidence 直接 throw，`classify()` 對整批失敗立即 break，造成一筆模型引文錯誤放大成批次中斷；外部 Gemini 為何生成該引文未確認 | 保留逐字來源驗證；只拒絕該篇，不讓其他有效判讀及後續批次被丟棄，仍標 `partial` 且不補造中性標籤 | `test_orion_news.cjs`：單篇錯引文隔離與後續批次；PR CI 需獨立驗收 |
