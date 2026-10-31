# 永久故障知識庫

| 日期 | 症狀 | 根因證據 | 永久防護 | 回歸測試 |
|---|---|---|---|---|
| 2026-10-27 | 六代理頁的 Gemini 報告來源仍為 10/22，卻與今日 ORION／LUNA 資料並列；自動九輪曾失敗 | [Gemini #40364926573](https://github.com/jacky-168168/Tradingview-testing/actions/runs/40364926573) 的 inference 步驟因逾時中止；正式 G 日榜 10/22、模型報告來源日 10/22，新聞／社群 10/27 | 顯示六角色各自來源日期及狀態，Gemini 報告另列真正完成時間／來源日；傳輸逾時最多重試一次，失敗仍不發布 | `test_six_agent_freshness.cjs`、`test_six_agent_gemini.cjs`；PR 獨立 CI 與正式 Pages 仍需審核驗收 |
| 2026-10-21～23 | 臺灣盤中 G 隔日資料仍被顯示 | GitHub Actions 盤中 cron 缺席，手動補跑有效；未證實 GitHub 內部缺席成因 | 外部排程與雙層驗證；資料不過期時才顯示正常 | Agent freshness／holiday／missing-run tests |
| 2026-10-24 | 新聞停在 10/21 | \`test_market_events_ui.cjs\` 強制要求顯示已結束 TPCA 展覽，阻擋 publish | 改成固定時間測試及新鮮度限制 | 日期固定的 UI regression |
| 2026-10-21 | 主排程時間由 :00/:30 調整後 CI 失敗 | 舊測試寫死 cron 值 | 排程測試跟實際規格同步、避免過度指定字面值 | \`test_intraday_schedule.cjs\` |

每次 P1/P2 修復後新增一筆，必須提供 Actions run、原始輸入、可重現步驟與驗收連結；不可自行編造「根本原因」。
