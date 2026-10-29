# 永久故障知識庫

| 日期 | 症狀 | 根因證據 | 永久防護 | 回歸測試 |
|---|---|---|---|---|
| 2026-10-21～23 | 臺灣盤中 G 隔日資料仍被顯示 | GitHub Actions 盤中 cron 缺席，手動補跑有效；未證實 GitHub 內部缺席成因 | 外部排程與雙層驗證；資料不過期時才顯示正常 | Agent freshness／holiday／missing-run tests |
| 2026-10-24 | 新聞停在 10/21 | \`test_market_events_ui.cjs\` 強制要求顯示已結束 TPCA 展覽，阻擋 publish | 改成固定時間測試及新鮮度限制 | 日期固定的 UI regression |
| 2026-10-21 | 主排程時間由 :00/:30 調整後 CI 失敗 | 舊測試寫死 cron 值 | 排程測試跟實際規格同步、避免過度指定字面值 | \`test_intraday_schedule.cjs\` |

| 2026-10-25（P2） | TDCC 週報在 main 更新到 10/22，但 Pages 最近驗證仍是 10/16 | [TDCC 收集成功 #40169846688](https://github.com/jacky-168168/Tradingview-testing/actions/runs/40169846688) 14:40 臺灣時間提交；[Pages #40167463878](https://github.com/jacky-168168/Tradingview-testing/actions/runs/40167463878) 13:59 已先完成。Pages 的星期日固定備援先於晚跑的收集，且缺少 TDCC `workflow_run` 觸發；Actions 的 `GITHUB_TOKEN` 推送不會觸發另一個 `push` workflow。**16:38** 延遲備援 [Pages #40177368940](https://github.com/jacky-168168/Tradingview-testing/actions/runs/40177368940) 成功，live 已恢復 **2026-10-22**，此項為防止再次延遲的預防性 PR | Pages 增加 TDCC 完成事件，保留成功且 main 才部署的安全條件；未經審核不觸發正式部署 | `.github/agent/test_tdcc_pages_trigger.py`；PR 獨立驗收與合併後 Pages 真實驗證待完成 |

| 2026-10-29（P2，待驗證） | 歷史市場研究 JSON 在 05:53～06:33 更新 main，但最近確認的 Pages 仍是 03:33 部署，研究資料可能延遲對外發布 | [歷史重試成功 #40780415668](https://github.com/jacky-168168/Tradingview-testing/actions/runs/40780415668) 更新研究摘要；[Pages #40755307916](https://github.com/jacky-168168/Tradingview-testing/actions/runs/40755307916) 先完成。部署 SHA `dfda0d62` 至 main `8ea10055` 差 3 筆研究資料提交；Pages 原 `workflow_run` 未監聽歷史重試，而 Actions `GITHUB_TOKEN` 推送不會觸發下游 `push`。公開 Pages JSON 尚未完成獨立 HTTP 讀取，不宣稱已證實線上內容落後 | 延伸既有草稿 PR #164：新增每日歷史重試完成事件與研究資料路徑監聽，保留成功且 main 才部署的閘門；避免監聽每半小時的收集器造成過度部署；未經審核不部署 | `.github/agent/test_history_pages_trigger.py`、`.github/agent/test_tdcc_pages_trigger.py`，PR CI 與合併後 Pages 實際讀取待驗證 |

每次 P1/P2 修復後新增一筆，必須提供 Actions run、原始輸入、可重現步驟與驗收連結；不可自行編造「根本原因」。
