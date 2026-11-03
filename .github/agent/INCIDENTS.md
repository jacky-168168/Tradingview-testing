# 永久故障知識庫

| 日期 | 症狀 | 根因證據 | 永久防護 | 回歸測試 |
|---|---|---|---|---|
| 2026-11-03 | 上市維持率計算意外上升、與獨立同日資料明顯不符 | main JSON 11/02 與 11/03 上市融資擔保市值均為 1,069,196,079,360 元，配對樣本與涵蓋率亦完全相同，但融資借款總額已變；OpenAPI 逐檔資料無正式日期驗證，疑似把昨日融資／報價搭配今日借款金額 | 上市逐檔融資改讀指定日期 TWSE 官方歷史報表且驗證回傳日期；逐檔收盤行情每筆 Date 都要與融資金額日期相同；混日／無日期 fail closed；不自動改寫歷史值 | `test_retail_twse_freshness.py`（9 項）；PR #179：TW Stock Python CI #41731052084 與獨立驗收 #41731051974 成功 |
| 2026-11-03 | 散戶存活率正式資料仍為 11/02，預定 22:20 更新未被觀測到 | GitHub Actions 所有工作流程在 11/03 14:10～14:30 UTC 查詢為 0 筆，正式 `retail_survival/latest.json` 的 `asOf=2026-11-02`；cron 遺漏的內部成因尚未證實 | 補增 17:35／19:35／21:35 臺灣時間重試，保留 22:20／23:20；正式日榜單已確認當日後拒絕將昨日／缺少整體比率當成更新成功；不上線假資料 | `tw-stock-dashboard/tests/test_retail_survival_freshness.py`（7 項固定時鐘測試）；待 PR CI 與 Pages 驗證 |
| 2026-10-21～23 | 臺灣盤中 G 隔日資料仍被顯示 | GitHub Actions 盤中 cron 缺席，手動補跑有效；未證實 GitHub 內部缺席成因 | 外部排程與雙層驗證；資料不過期時才顯示正常 | Agent freshness／holiday／missing-run tests |
| 2026-10-24 | 新聞停在 10/21 | \`test_market_events_ui.cjs\` 強制要求顯示已結束 TPCA 展覽，阻擋 publish | 改成固定時間測試及新鮮度限制 | 日期固定的 UI regression |
| 2026-10-21 | 主排程時間由 :00/:30 調整後 CI 失敗 | 舊測試寫死 cron 值 | 排程測試跟實際規格同步、避免過度指定字面值 | \`test_intraday_schedule.cjs\` |

每次 P1/P2 修復後新增一筆，必須提供 Actions run、原始輸入、可重現步驟與驗收連結；不可自行編造「根本原因」。
