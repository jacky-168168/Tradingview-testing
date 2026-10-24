# Codex 啟用驗證（僅限測試 PR）

這是一個不修改任何正式執行程式或選股資料的臨時測試檔案，用於驗證 GitHub Actions 的 `Loop Independent PR Acceptance` 和可選的 `optional-codex-review` 工作。

驗收：
- 基本 deterministic-acceptance 成功。
- `optional-codex-review` 若被設定為啟用，應真正進入 Codex Action，並正常結束。
- 不測試交易、不修改 `main`、不自動合併。

完成測試後直接關閉 PR，此檔不併入正式網站。
