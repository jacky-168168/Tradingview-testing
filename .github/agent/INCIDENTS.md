# 永久故障知識庫

| 日期 | 症狀 | 根因證據 | 永久防護 | 回歸測試 |
|---|---|---|---|---|
| 2026-10-26 22:29（臺灣） | 休市日主分支 push 觸發完整日榜單，EOD readiness gate 回報 failure，誤當資料發布異常 | [Actions #40340069382](https://github.com/jacky-168168/Tradingview-testing/actions/runs/40340069382) 的 `Wait for actual official-close publication`；`fund/BFI82U` 當天無報表，10/26 為已確認休市日；既有 gate 只排除週末未排除平日休市 | 在 gate 使用 2026 已確認休市清單，休市時 `ready=false`、步驟正常完成、不抓資料、不發布舊日榜單；正常交易日 17:30 後缺報仍須失敗 | `test_official_ready.py` 固定時鐘驗證休市、交易日缺報、有效報表與 cutoff |
| 2026-10-21～23 | 臺灣盤中 G 隔日資料仍被顯示 | GitHub Actions 盤中 cron 缺席，手動補跑有效；未證實 GitHub 內部缺席成因 | 外部排程與雙層驗證；資料不過期時才顯示正常 | Agent freshness／holiday／missing-run tests |
| 2026-10-24 | 新聞停在 10/21 | \`test_market_events_ui.cjs\` 強制要求顯示已結束 TPCA 展覽，阻擋 publish | 改成固定時間測試及新鮮度限制 | 日期固定的 UI regression |
| 2026-10-21 | 主排程時間由 :00/:30 調整後 CI 失敗 | 舊測試寫死 cron 值 | 排程測試跟實際規格同步、避免過度指定字面值 | \`test_intraday_schedule.cjs\` |

每次 P1/P2 修復後新增一筆，必須提供 Actions run、原始輸入、可重現步驟與驗收連結；不可自行編造「根本原因」。
