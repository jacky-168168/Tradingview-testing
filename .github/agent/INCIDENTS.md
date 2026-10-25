# 永久故障知識庫

| 日期 | 症狀 | 根因證據 | 永久防護 | 回歸測試 |
|---|---|---|---|---|
| 2026-10-21～23 | 臺灣盤中 G 隔日資料仍被顯示 | GitHub Actions 盤中 cron 缺席，手動補跑有效；未證實 GitHub 內部缺席成因 | 外部排程與雙層驗證；資料不過期時才顯示正常 | Agent freshness／holiday／missing-run tests |
| 2026-10-24 | 新聞停在 10/21 | \`test_market_events_ui.cjs\` 強制要求顯示已結束 TPCA 展覽，阻擋 publish | 改成固定時間測試及新鮮度限制 | 日期固定的 UI regression |
| 2026-10-21 | 主排程時間由 :00/:30 調整後 CI 失敗 | 舊測試寫死 cron 值 | 排程測試跟實際規格同步、避免過度指定字面值 | \`test_intraday_schedule.cjs\` |

| 2026-10-25（P2） | TDCC 週報在 main 更新到 10/22，但 Pages 最近驗證仍是 10/16 | [TDCC 收集成功 #40169846688](https://github.com/jacky-168168/Tradingview-testing/actions/runs/40169846688) 14:40 臺灣時間提交；[Pages #40167463878](https://github.com/jacky-168168/Tradingview-testing/actions/runs/40167463878) 13:59 已先完成。Pages 的星期日固定備援先於晚跑的收集，且缺少 TDCC `workflow_run` 觸發；Actions 的 `GITHUB_TOKEN` 推送不會觸發另一個 `push` workflow | Pages 增加 TDCC 完成事件，保留成功且 main 才部署的安全條件；未經審核不觸發正式部署 | `.github/agent/test_tdcc_pages_trigger.py`；PR 獨立驗收與合併後 Pages 真實驗證待完成 |

每次 P1/P2 修復後新增一筆，必須提供 Actions run、原始輸入、可重現步驟與驗收連結；不可自行編造「根本原因」。
