# G 盤中選股：外部備援排程（選用）
這份程式放在版本庫，但**不會因 GitHub 合併就自行部署到 Cloudflare**。正式啟用前須完成 Cloudflare 帳號連線與安全憑證設定。原有 GitHub Actions 排程會繼續運作。

## 用途
- 台灣平日 09:04、09:19、09:34、09:49……13:34，Cloudflare Worker 檢查主分支最新 G 盤中榜單。
- 如本時段已成功發布或 GitHub 有同一時段仍在執行中的工作，就不重複派工。
- 如未更新且沒在執行，使用 GitHub `workflow_dispatch` 啟動 `mode=intraday`。
- 逾期超過 12 分鐘的 Cron、休市日或已超過交易時段不補造盤中數據。
- **這是外部觸發 GitHub 執行器，不是獨立選股運算主機**。GitHub runner、TWSE MIS 或 GitHub Pages 故障時仍可能延遲；網站必須顯示真實時間及失敗提示。

## 安全設定
1. 建立限定 **jacky-168168/Tradingview-testing 單一儲存庫**、只有 **Actions: Read and write** 的 GitHub fine-grained token（不需要 Contents write 權限）。
2. Cloudflare 安裝 Wrangler，在本資料夾執行 `npx wrangler secret put GH_ACTIONS_TOKEN`，依命令提示貼上權杖。**切勿將 token 貼入程式碼或 GitHub 公開檔案**。
3. 執行 `npx wrangler deploy`。Wrangler 設定包含 `workers_dev:false`，Worker 只透過 Cron 觸發，沒有公開 HTTP 入口。
4. 於 Cloudflare Worker 記錄確認 `dispatched` 或 `skip`，並在 GitHub Actions 確認 `workflow_dispatch` 執行成功及對應歷史快照。
5. 建議每季重新確認證券交易所休市表及 Cron 時段；例外補班日／休市日必須維護。
6. 如不希望持續運作，可移除 Cron Trigger 或停用 Worker；GitHub 排程依舊存在。

## 限制
Cron 與 GitHub Actions 皆為盡力執行，並非保證秒級啟動。每一輪歷史榜單會保留**真實發布時間**，不將延遲行情冒充整點行情。原本 10/16 上午漏跑的資料不能真實回補。
