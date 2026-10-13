# Discord → Bottom/Top 交易雷達（Cloudflare Worker）

> **狀態：GitHub 草稿分支，尚未雲端部署。** Bot 加入 Discord 不等於程式已開始接收。不要將 Bot Token、讀取金鑰或券商憑證傳到聊天、Discord 頻道或公開 GitHub。

## 已設定的 Discord 頻道

| 頻道 | Channel ID | 週期 |
|---|---|---|
| #day-trading | `1540171776418390038` | **未確認，不能假定是 2 分鐘** |
| #5-min小波段通知 | `1541319920007254066` | 5 分鐘 |

訊號文字解析：

- `6533 SS bottom alert triggered, price: 324.0` → **Bottom 且 Trend >70 已確認**；沒有確切 Trend 數字。
- `2413 bottom alert triggered, price: 52.0` → **普通 Bottom**，不能從文字推定 Trend 大於或小於 70。
- `2413 top alert triggered, price: 54.0` → **Top**，與 Trend 無關，能作為多單退出參考。
- 同股同時、同價的 `SS bottom` 與 `bottom` 會在前端合併展示；後端保留兩個原始訊號，紙上交易僅算一次進場。
- 不會猜測 G 選股排名。A 收 Bottom，B/C 預設需 SS Bottom 或數值 Trend>70；C 才加入後續價格事件分批加碼。**SS 只證明超過 70：若進場門檻改成 75，沒有實際分數便不能通過。**

## 只用手機完成 Cloudflare 部署

1. 先到 [Cloudflare Dashboard](https://dash.cloudflare.com/)，建立自己的帳戶。手機瀏覽器可選「電腦版網站」。
2. 在 Cloudflare **Storage & databases → D1** 建立 `tw-stock-discord-events`，把新建立的 Database ID 複製到 `wrangler.jsonc`，替換 `REPLACE_WITH_YOUR_D1_DATABASE_ID`。
3. 將本目錄的 `schema.sql` 套到 D1：可在 Cloudflare D1 SQL Console 貼上 SQL，或使用 `npx wrangler d1 execute tw-stock-discord-events --remote --file=./schema.sql`。
4. 建立一個 Cloudflare Worker，使用本 GitHub 專案的 `tw-stock-dashboard/discord-worker` 當 Worker 專案目錄，`npx wrangler deploy` 部署。若 Cloudflare 網站無法直接選取子目錄，可能需要在電腦或遠端開發環境執行 Wrangler，這部分的 UI 依 Cloudflare 平台實際支援為準。
5. 在 Worker → **Settings → Variables and Secrets** 中新增以下 *Secret*：
   - `DISCORD_BOT_TOKEN`：從 Discord Developer Portal → Bot 取得，**僅填 Cloudflare Secrets**。
   - `DASHBOARD_READ_TOKEN`：自行產生獨立、至少 32 個隨機字元的密鑰，給使用者登入網頁讀取事件。
   - `SYNC_TOKEN`：另一組不相同的獨立密鑰，給管理者手動發起同步。
6. Worker 一般環境變數 `ALLOWED_ORIGIN` 預設是 `https://jacky-168168.github.io`；`CHANNELS_CONFIG` 已填入上述兩個頻道。**只有在確認 #day-trading 確實全部是 2 分鐘訊號後**，才把該頻道的 `timeframe` 由 `null` 改成 `"2"`。
7. Discord Bot 必須可以看見上述頻道、具備 View Channels + Read Message History，並在 Discord Developer Portal 啟用 Message Content Intent。如果兩個頻道不在同一個伺服器，Bot 需要分別加入。
8. Workers 的 Cron 設定為 `* * * * *`：每分鐘抓取 Discord 最新文字，存入 D1。此為**分鐘級輪詢**而非秒級訊號。
9. 網頁端開發分支 `docs/bottom-top-trader.html` 的「Discord 自動訊號匯入」輸入 Worker HTTPS 網址和 **DASHBOARD_READ_TOKEN**，按連接 Worker；網頁只保留 Worker URL，**不把 Token 寫入 localStorage**。
10. 先在測試環境驗證實際發言者、時間及訊號對應正確，再考慮合併進正式 GitHub Pages。ChatGPT 不具有你 Cloudflare 帳戶的登入權，程式提交不代表自動部署。

## API 與權限

- `GET /api/events`：需 `Authorization: Bearer <DASHBOARD_READ_TOKEN>`。回傳含 `variant`、`trendGt70`、`timeframe`、`channel` 等資訊。
- `GET /api/status`：需同一唯讀 Token，查看頻道同步狀態與錯誤。
- `POST /api/sync`：需 `Authorization: Bearer <SYNC_TOKEN>`，手動同步用；Cron 自動同步不需要。
- CORS 只允許預設 GitHub Pages 來源，但 **CORS 不能取代授權**；請勿把讀取金鑰寫進 GitHub 或前端原始碼。

## 限制與風控

- 第一次同步抓最近 100 則 Discord 訊息，後續保存每個頻道的 Snowflake 游標；每分鐘最多向前分頁 1500 則新訊息，若超過上限則不前進游標，需人工排查。Discord API 429 或 Worker 執行延遲，可能使訊號延後。
- 目前僅以訊息格式解析，**尚未加入 Alert bot 作者 ID 白名單**；不要讓未受信任者在警報頻道發送相同格式假訊號。
- 未提供完整 Trend 數值時，SS 只代表 >70；普通 Bottom 不代表 ≤70，也不表示一定 >70。
- `#day-trading` 的時間框架仍待核對；不會因為有 SS 就自行當作 2 分鐘 K。
- 網頁上的交易績效是事件價格的紙上模擬，非可成交的實際回測；沒有串接券商下單。
- 真正的單檔 G 選股交叉比對、G 群組自動導入及提醒推播尚未接上。

## 開發測試

```bash
cd tw-stock-dashboard/discord-worker
npm install
npm test
npm run dev
```

相鄰網站端回歸測試：`node --test tw-stock-dashboard/tests/bottom-top-trader.test.cjs`。

