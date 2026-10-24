# 臺股 G：真正獨立於 GitHub 排程的備援時鐘

此目錄提供 **可部署但尚未部署** 的 Cloudflare Worker。Worker 不修正選股演算法、不修改 JSON、不觸及券商／交易；只在臺灣交易日、指定時段、當日 G 缺失或過期而主工作流程沒有近期執行時，呼叫原有 \`workflow_dispatch(mode=intraday)\`。

## 安全部署（需使用者自己的 Cloudflare 帳戶）

1. 登入 Cloudflare，先核對帳戶是否有 Workers Cron 權限及目前配額。
2. 建立一個範圍限定為 **此儲存庫 Actions: read/write、Contents: read** 的 fine-grained GitHub PAT。儘量只授予 workflow dispatch 所需權限，不要給全帳戶 repo 寫入權。
3. 在終端安裝 Wrangler 或使用 npx，於本目錄執行 \`npx wrangler login\`。
4. 執行 \`npx wrangler secret put GITHUB_DISPATCH_TOKEN\`，秘密只存 Cloudflare Worker Secret，絕不可提交 GitHub。
5. 先用 \`node --test test_worker.mjs\` 驗證時間、假日、資料品質、冷卻、防止重複補跑。
6. 執行 \`npx wrangler deploy\`，再檢查 Cloudflare Cron Triggers 與實際執行日誌。首次**成功接到 Cron 實際事件**後，才能稱為已啟用。
7. 於實際開市日核對 GitHub Actions 對應 \`workflow_dispatch\` 紀錄及 \`latest.json\` 的當日時間；必要時在 Cloudflare 停用 Cron 或撤銷 PAT 以回滾。

## 排程與驗收
- 排程採 UTC 工作日 01:17、01:47 起每 30 分鐘（臺灣 09:17、09:47 起），並於臺灣 13:17 與 13:38 再查核；程式內另設 09:35～13:42 邊界，09:17 不執行。
- 最早 09:45 判斷；不在休市日執行（2026 年清單依現有監控器，跨年度須更新）。
- 資料須今日、合法 1～20 檔、quality 正確、發布時間非未來且 55 分鐘內、有效報價 ≥1000、全市場 ≥65%、上市與上櫃各 ≥60%。
- 最近 20 分鐘有主更新、或最近 95 分鐘仍在執行時不再補跑；回傳 204 才記錄 dispatch accepted，**不等於榜單恢復**。
- Worker 不暴露可由任何人呼叫的 HTTP 補跑端點（普通 GET 回 404）。
- Cloudflare 仍可能延遲，且 GitHub API 服務故障時無法自行修好；原本健康監控與人工驗收仍必須存在。

## 費用及故障處理
Worker、API、Codex 費用與免費配額依供應商當期計價；這份程式碼本身不等於你已購買方案或部署成功。檢查 Worker Logs 的 \`CLOUDFLARE_G_CLOCK\`、\`CLOUDFLARE_G_CLOCK_ERROR\`，禁止把 PAT 印到日誌。
