# 六代理研究實驗室（規則式 MVP）

此頁面是**研究流程與資料整合**，不是用六個付費大語言模型做全天交易；沒有券商金鑰、模擬下單、真實下單或宣稱績效。研究頁面：\`docs/agent-research.html\`；引擎：\`docs/agent-research-core.js\`；測試：\`tests/test_six_agent_research.cjs\`。

## 資料來源及六角色職責

| 角色 | 輸入 | 輸出 | 權限 |
|---|---|---|---|
| ATLAS | G 日／盤中 Top20、RS20、RVOL、成交額 | 前十名研究候選與定量證據 | 不更改 G 排序 |
| VEGA | MA20 斜率、ATR%、相對強弱、既有訊號 | 技術結構與缺失資料 | 不發明支撐、壓力、進出價 |
| ORION | 48 小時內重大新聞、主題／名稱 | 相關報導、來源、發布時間、是否已核實 | 新聞相符≠因果，未核實不得當事實 |
| LUNA | Risk Score、市場廣度、PTT 公開 Atom、經授權 Threads／Instagram、現有新聞 JSON | 分開顯示市場風險與公開輿情；樣本門檻及來源狀態 | 社群不改 Risk Score；無授權不得捏造聲量 |
| TITAN | 行情時效、Risk Score、ATR%、流動性、日期一致性 | **不可覆蓋的硬性否決**及風險資料缺口 | 不提供部位大小或下單 |
| NOVA | 前五個角色的結構化報告 | 否決、等待、研究候選（待人審核） | 永遠不推翻 TITAN／不下單 |

## 最重要的防護
1. 僅在臺灣開市日 09:50～13:45、\`intraday-provisional-allmarket\`、1～20 個合法股票代碼、\`publishedAt\` ≤65 分鐘、全市場 ≥1000 有效報價且 ≥65%、上市與上櫃各 ≥60%，才允許使用盤中資料。
2. 2026 休市日由現有監控規格抄入；2027 年起未核對交易所新行事曆，\`session()\` 一律拒絕盤中模式，避免假開市。日後每年需要更新行事曆，不能直接假定工作日開市。
3. 非盤中時段標示**歷史快照**；即使舊資料可讀也不視為即時推薦。盤中資料失效只能用歷史資料觀察，TITAN 不能放行。
4. 風險資料日須與候選資料日一致（盤中則與來源前一正式收盤日 \`sourceCloseDate\` 一致）。風險分數低於 60、ATR% 超過 12%、資料欄位缺失或成交額不足均由 TITAN 否決。這些是**暫訂研究閘門**，不是 G 策略原始公式，後續必須用樣本外回測確認。
5. 只能比對主題／名稱搜尋新聞；Google News 轉載及一般媒體 \`confirmed:false\` 不可視為官方證據，須人工核實原始來源。新聞發布時間不得晚於研究時間。
6. 沒有收集實際持倉、相關性、資金餘額與明確停損失效價位，故一律不計算部位或真實風報比，\`nova.noTrade===true\`。
7. 研究快照在 GitHub Actions 以 artifact 保存 30 日，不提交公開榜單或改寫正式策略。產生報告不等於回測完成，不得虛構勝率、報酬、MDD。
8. 頁面使用 textContent 呈現外部新聞與股票標題，URL 限定 https，防止把資料當 HTML 指令執行。

## 操作與驗證
- \`node --test tw-stock-dashboard/tests/test_six_agent_research.cjs\`
- \`node tw-stock-dashboard/scripts/build_six_agent_report.cjs six-agent-snapshot.json\`
- GitHub Actions: \`Six Agent Research Snapshot\`，每個臺灣工作日 18:30 UTC+8 自動建立研究快照及測試，也可手動觸發；假日仍只產生標註歷史資料的報告，不代表當日有交易。
- 站上頁面每次開啟會以 cache:no-store 讀取既有的 JSON；上游資料更新即可反映於頁面。錯誤時顯示無法讀取而不憑空補資料。

## 下一階段（尚未啟用）
- 事件資料建立實際最早發布時間、官方公告 ID、個股映射與證據品質分級。
- 使用官方歷史資料重建逐時 point-in-time 快照；樣本外測 TITAN 阻擋對 G 5D/10D/20D 報酬、MDD、績效的影響。不可使用當時尚未發布的新聞／資料。
- 等付費 API 額度可用且驗證權限後，再考慮加入 ORION/NOVA 的 LLM 摘要層；模型不能改硬性風控或交易。

## 公開社群氛圍 v0.2（PTT 為免費基礎來源）
- 正式資料接入腳本：`scripts/collect_social_sentiment.py`。固定 HTTPS 白名單讀取 PTT 股票板官方 Atom 訂閱；同一連結去重，最多保留最近 48 小時的公開標題，嚴格拒絕未來時間。
- 公開資料整理到 `docs/data/social_sentiment/latest.json`，PTT 原文網址與標題提供查核；不存作者個資、不全文爬蟲、不以標題判斷留言區共識。
- 以保守中文看多／看空關鍵詞分類，兩種方向同時出現視為中立／難判；只要有 **1 篇**公開且可核對、48 小時內的有效 PTT／Threads／Instagram 貼文，就顯示「已有樣本」及實際篇數（含中立標題）；絕不使用「樣本不足」當作否定已有資料。資料量少時仍要提醒不代表市場共識；新聞標題另計，不與社群混合成單一投票。
- Threads 官方 `keyword_search` 需要 Meta App 及 `threads_keyword_search` 審核後的 `THREADS_ACCESS_TOKEN`；Instagram Hashtag Discovery 需要合格商業／創作者帳號，`IG_ACCESS_TOKEN` 與 `IG_USER_ID`。未授權時明示 `not_authorized`，絕不繞過登入或偽造覆蓋。
- 每日 09:10、11:10、13:10、17:10、21:10（臺灣時間）執行 `LUNA Public Social Sentiment`，公開來源無法取得時不可將空資料說成中立；保留最多 48 小時可驗證歷史樣本。
- LUNA 只要有 1 篇有效社群貼文就會顯示樣本數；8 小時內更新視為近期觀察，較舊但貼文仍在 48 小時有效期內則明確標示「已有歷史樣本」。來源失聯時不得捏造新資料；大盤風險分數與社群方向彼此獨立，任何社群觀點不能解除 TITAN 否決。

## 重要修正：GitHub Models 已退役（2026-07-30）
- GitHub 官方於 2026-07-01 公告 GitHub Models（包含其推論 API）在 **2026-07-30 全面終止**，官方公告：https://github.blog/changelog/2026-07-01-github-models-is-being-fully-retired-on-july-30-2026/
- 2026-10-25 實測原 GitHub Models 端點只回傳 HTTP 200、`text/plain`、4 位元組 `OK\n`，**不是有效模型推論**。提高 Token、修改 JSON 或更換 GITHUB_TOKEN 都無法恢復已停用的服務。
- 六角色九輪推論引擎**程式已完成、離線測試通過，但真實 LLM 推論沒有成功**；網頁維持 `verifiedModelExecution:false`，不可宣稱模型會議完成。
- 因此停用 `Six Agent LLM Validation (Provider Retired)` 的排程與真正推論工作，僅保留手動及 PR 離線安全測試。之後要真正啟用六位 LLM，必須改接仍在營運、由使用者授權的 LLM 服務，再驗證九次 API 回應與風險閘門。
- **不影響**每日 PTT / 財經新聞蒐集、LUNA 規則式情緒分析、G 選股、原六代理規則式研究與既有的風控。

## 六個真正 LLM 角色及交叉討論 v0.2（設計完成、尚未啟用）
- 原先設計使用 GitHub Models 和 Actions 內建 `GITHUB_TOKEN`，但此服務已於 2026-07-30 退役，**這種無金鑰推論方式不再可用**。目前沒有真正 LLM 供應商，仍需後續授權並改接。
- `scripts/run_six_agent_llm.cjs` 進行 **九次**獨立模型呼叫：ATLAS、VEGA、ORION、LUNA、TITAN 五位首輪 → NOVA 初步整合 → VEGA 與 TITAN 交叉質疑 → NOVA 最後整合。六個角色使用同一底層模型、不同系統提示與上下文；不是六個不同模型。
- 每個輸出必須提供真實存在的來源代碼、明確不確定性及 `noTrade:true`。未完成模型執行或回應格式錯誤時 **不產生成功報告**。
- 原 GitHub Models 的 18:50 自動排程已停止，防止無限故障重試。未來改接可用模型並驗證成功後，才可安排定時發布 `docs/data/agent_llm/latest.json` 及保存 30 日 Artifact。
- 六代理研究頁面會單獨標明「真實 LLM 推論」的時間、資料日期、獨立角色論點及反駁；不存在正式報告時只顯示「尚未驗證」，保留原本規則式六代理的運作。
- 不改 G 選股結果、不重算正式 Risk Score、不自動下單；TITAN 的程式硬否決無法由其他五位 LLM 推翻。每篇文字只是尚待人工核實的研究意見。
- `node tw-stock-dashboard/scripts/run_six_agent_llm.cjs --self-test` 是**模擬傳輸的離線測試**；不能把測試 9 次當成真正完成 9 次模型 API 呼叫。僅正式 GitHub Actions 有 `REAL_SIX_AGENT_MODELS_VERIFIED` 且驗證紀錄時才算實際執行成功。

## 可重現測試
- `python -m unittest discover -s tw-stock-dashboard/tests -p 'test_social_sentiment.py' -v`
- `node --test tw-stock-dashboard/tests/test_six_agent_research.cjs`
- `node tw-stock-dashboard/scripts/run_six_agent_llm.cjs --self-test`

## Gemini 供應商接入 v0.3（可選、預設停用）
- 原 GitHub Models 確定已退役；新增仍受支援的 Google Gemini REST API 轉接：`scripts/gemini_transport.cjs`。驗證回應 JSON，不接受純字串 `OK`、不完整模型輸出、錯誤或缺值充當成功結果。
- `Six Agent Gemini LLM Debate` 工作流程保留離線測試；**真實推論預設停用**。要啟用需由帳戶持有人在 GitHub 儲存庫的 **Settings → Secrets and variables → Actions** 設定 Secret `GEMINI_API_KEY`，並在 Variables 新增 `ENABLE_SIX_AGENT_GEMINI=true`。**不要把金鑰貼在 ChatGPT、Issue、PR 或程式碼裡**。
- 真正啟用後預計每臺灣時間週一至週五 19:00 嘗試產生九次獨立模型呼叫的研究報告（TITAN 硬性風控不可解除）；GitHub Secrets、API 帳戶用量、模型存取權及額度皆需實際驗證後才能宣稱「真實六 LLM 已成功」。
- 預設 Gemini 模型 `gemini-3.5-flash-lite`（新專案可用的穩定模型；舊 2.5 模型可能對新專案回傳 HTTP 404）。免費額度、頻率限制及資料處理政策由 Google 決定，請自行在 AI Studio 確認；此研究管線只使用網站公開市場資料，不送入個人持倉、密碼或帳戶資訊。
- 開發／驗證：`node --test tw-stock-dashboard/tests/test_six_agent_research.cjs tw-stock-dashboard/tests/test_six_agent_gemini.cjs`。使用 Mock 的九輪測試不是正式 API 呼叫，只有實際輸出 `REAL_GEMINI_SIX_AGENT_VERIFIED` 才能當正式執行證據。
