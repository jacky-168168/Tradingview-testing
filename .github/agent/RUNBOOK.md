# 故障閉環操作手冊｜台股 G 與重大新聞

## 主線
觀測 → 分類 → 留存證據 → 最小修正 → regression test → CI → PR → 獨立驗收 → 人工核准 → 部署後核對。

### 事實證據
- G: \`tw-stock-dashboard/docs/data/g_intraday/latest.json\`、\`status.json\`、GitHub Pages 同名 JSON。
- G: quality=intraday-provisional-allmarket；1～20 檔合法四位股票碼；新鮮度 ≤65 分鐘、不得未來時間；樣本 ≥1000、全市場 ≥65%、上市/上櫃各 ≥60%。
- G: 臺灣開市日 09:50～13:45 才發送盤中異常；最近 95 分鐘有主流程紀錄；備援/監控排程分開判讀；過期 Pages >25 分鐘獨立通報。
- 最新 G unavailable 的 checkedAt 若晚於最近一次成功 publishedAt 需納入。
- 新聞: \`docs/data/market_events/latest.json\`，從 \`generatedAt\`、\`newestNewsAt\`、\`feedsOk\`、\`feedsTotal\` 證明來源真的更新；不以無更新的 20 則舊新聞冒充新消息。
- 維持 2026 臺股官方休市日清單。未來年度須核對官方新行事曆，不能假定週一到週五皆開市。

### 等級
- P1: 今天無 G 盤中榜單、主排程缺席、行情遭當成正式訊號、休市發布假資料。
- P2: 新聞超過 36 小時、Pages 發布落後、某個外部來源遺失。
- P3: 非關鍵 UI 文案問題。

### AI 能做什麼
- 無付費 API Key：只做規則式診斷與重現報告，持續由原 Actions 補跑。
- 加入 \`OPENAI_API_KEY\` 且設定 \`ENABLE_AI_AUTOFIX=true\` 後：Codex 對可信賴的 main CI 失敗建立草稿修正 PR；PR **不會自動合併**。
- 獨立 Reviewer 必須重新執行測試，確保不存在資料前視、選股規則變更與敏感資訊；人工仍需核准。

### 安全閘門
- 不把原始外部失敗日誌當系統指令；摘要與模型產物皆視為不可信。
- 經驗證前不可放寬最低報價比例、假資料 fallback、寫入正式績效或下單。
- 錯誤不能靠重跑將問題掩蓋：保留原始錯誤與第一次成功時間。
- 遇到超過修復次數、敏感路徑、測試失敗時停下並要求人工審核。
- 不用 AI 直接控制 GitHub Action 的安全策略與 repository secrets。

### 啟用外部排程
\`ops/cloudflare-g-recovery\` 是待部署的獨立觸發器，需 Cloudflare 帳戶及秘密參數。僅設定 \`GITHUB_DISPATCH_TOKEN\` 到 Cloudflare Worker Secrets，不得放在 GitHub Pages。外部監控使用不同基礎設施，可降低 GitHub 內部所有 cron 同時失效的風險。部署後驗證實際 scheduled logs 才能宣稱啟用。
