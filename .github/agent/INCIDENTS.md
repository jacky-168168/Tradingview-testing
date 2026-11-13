# 永久故障知識庫

| 日期 | 症狀 | 根因證據 | 永久防護 | 回歸測試 |
|---|---|---|---|---|
| 2026-11-08 | 集保大戶四象限週報停在 10/30 | [TDCC Weekly #42460449407](https://github.com/jacky-168168/Tradingview-testing/actions/runs/42460449407) API 索引 2026 回 HTTP 429；一次嘗試後整批停止，沒有可靠的 11/06 新版 | 僅對固定 GitHub 封存索引使用既有工作流程短期權杖，429 有上限重試且終究 fail closed；不得用舊週或不完整快照冒充新資料 | `test_tdcc_whale_weekly.py` 429 成功重試／超限拒絕／Token 不外送；CI 待驗證 |
| 2026-10-21～23 | 臺灣盤中 G 隔日資料仍被顯示 | GitHub Actions 盤中 cron 缺席，手動補跑有效；未證實 GitHub 內部缺席成因 | 外部排程與雙層驗證；資料不過期時才顯示正常 | Agent freshness／holiday／missing-run tests |
| 2026-10-24 | 新聞停在 10/21 | \`test_market_events_ui.cjs\` 強制要求顯示已結束 TPCA 展覽，阻擋 publish | 改成固定時間測試及新鮮度限制 | 日期固定的 UI regression |
| 2026-10-21 | 主排程時間由 :00/:30 調整後 CI 失敗 | 舊測試寫死 cron 值 | 排程測試跟實際規格同步、避免過度指定字面值 | \`test_intraday_schedule.cjs\` |

每次 P1/P2 修復後新增一筆，必須提供 Actions run、原始輸入、可重現步驟與驗收連結；不可自行編造「根本原因」。
