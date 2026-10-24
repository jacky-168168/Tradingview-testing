# 永久故障知識庫

| 日期 | 症狀 | 根因證據 | 永久防護 | 回歸測試 |
|---|---|---|---|---|
| 2026-10-21～23 | 臺灣盤中 G 隔日資料仍被顯示 | GitHub Actions 盤中 cron 缺席，手動補跑有效；未證實 GitHub 內部缺席成因 | 外部排程與雙層驗證；資料不過期時才顯示正常 | Agent freshness／holiday／missing-run tests |
| 2026-10-24 | 新聞停在 10/21 | \`test_market_events_ui.cjs\` 強制要求顯示已結束 TPCA 展覽，阻擋 publish | 改成固定時間測試及新鮮度限制 | 日期固定的 UI regression |
| 2026-10-21 | 主排程時間由 :00/:30 調整後 CI 失敗 | 舊測試寫死 cron 值 | 排程測試跟實際規格同步、避免過度指定字面值 | \`test_intraday_schedule.cjs\` |

| 2026-10-25 | PTT 來源 HTTPError，LUNA 與 Gemini 仍把 6 篇快取標題當新鮮社群情緒 | [LUNA #40132761799](https://github.com/jacky-168168/Tradingview-testing/actions/runs/40132761799) 成功發布 JSON 但 `sources.PTT.status=error`；[Gemini #40134010005](https://github.com/jacky-168168/Tradingview-testing/actions/runs/40134010005) 的 `sourceSummary.SOCIAL=true` | 不以 JSON `generatedAt` 代替來源擷取成功；UI 將失聯來源標記歷史樣本，LLM 只採用 `sources[platform].status=ok` 的貼文 | `test_six_agent_research.cjs`：PTT 失聯、混合來源、偽網址 |

每次 P1/P2 修復後新增一筆，必須提供 Actions run、原始輸入、可重現步驟與驗收連結；不可自行編造「根本原因」。
