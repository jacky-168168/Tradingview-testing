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


## Orca 式多代理可觀測性 v0.4（來源參考：stablyai/orca）
- 借鏡 Orca 的隔離工作區、Agents Feed 及人工審查概念；只改造台股六代理研究協調器，**沒有直接將 Orca Electron 桌面產品／CLI 部署在 GitHub Pages**。
- 五角色首輪使用 **角色範圍內的獨立證據快照**：ATLAS G／風險、VEGA 技術／風險、ORION 個股與新聞、LUNA 社群／風險、TITAN 量價與硬否決。首輪互不看別人的文字，降低跟風與引用非職責資料。
- NOVA 初稿、VEGA/TITAN 交叉質疑與 NOVA 結論仍使用完整證據，維持九次 Gemini 連線；循序執行避免對免費 API 突發 429。不是六種不同基礎模型。
- 真實報告新增九輪 `executionTrace`（角色、階段、完成狀態、執行耗時、完成時間）與 `reviewAudit`（反駁是否與自身首輪逐字重複、最終稿是否照抄初稿）。**僅能辨識文字完全重複，不是語意品質分數**，有警訊必須人工審核。
- 網頁預設收合逐輪紀錄，手機可展開。未更新的歷史快照不會假稱有執行軌跡，沒有金鑰、下單權限、持倉資訊或假績效。
- 參考：[Orca README](https://github.com/stablyai/orca)、[Worktrees](https://github.com/stablyai/orca/blob/main/docs/site/content/docs/model/worktrees.mdx)、[Agents Feed](https://github.com/stablyai/orca/blob/main/docs/site/content/docs/activity.mdx)。

## LUNA 社群情緒與可核對熱度 v0.5（2026-10-25）
- 抓取次序：PTT 股票板官方小寫 Atom URL → 官方大寫 Atom URL → PTT 公開看板 HTML → 第三方公開 RSS 橋接（feed.cqd.tw，只接受 PTT 原文網址）。HTML 備援使用永久文章網址中的 Unix 時間戳**推算**貼文時間，JSON 標示 `timestampBasis`，不能宣稱為已查核的正式發布時間。來源失敗時保留 48 小時內的有效歷史原文，否則發布空樣本及失敗狀態，**不補假的中立、偏多或偏空**。
- 標題分類：將 `[新聞]` 等轉載歸類為「新聞轉載」並維持中立；含反諷、反指標、求救等不確定字詞時保留「語意不明」。沒有自動擷取留言全文，仍是保守關鍵字判讀，不宣稱 Gemini 已對每篇留言做語意分類。
- 從正式 G 前 20 名建立 `stockHeat`；股票比對僅接受完整四碼代號或正確公司名稱，顯示過去 24h、前 24h 的可核對標題及原文連結。無提及即缺值，不代表沒人討論。
- `overheatWatch` 只是研究警示：近 24 小時至少三篇、其中至少三篇非新聞轉載，且個股 20 日漲幅超過 25%、量比 >= 2 或 MA20 斜率 >= 5 之一。研究頁還會驗證樣本、時間是否一致，異常來源不標榜即時訊號。不得更改 G 名次、正式大盤分數、TITAN 風控或下單。
- Gemini 九輪的 LUNA 首輪只解釋實際已取得的社群與大盤資料，新增的 `contentType`、`tone`、`stockHeat` 僅在社群資料新鮮且有效時提交。新聞和社群分開計數。
- Threads／Instagram 仍需各自官方授權。未授權就是 `not_authorized`，不可假裝取得 IG/Threads 輿情。此版本沒有加入完整留言分析、語意級 LLM 分類、完整市場情緒勝率回測。

## 多社群來源可行性實測 v0.6（2026-10-25）
- **Bluesky**：使用官方 `https://public.api.bsky.app/xrpc/app.bsky.feed.searchPosts` 公開 GET，不需提供登入資訊，依臺股、台積電、CPO 台股三項搜尋，每次最多 25 筆且去重；查核官方 `at://` 原始貼文 ID、公開作者 handle、`record.createdAt`，只保留貼文中有臺股相關上下文、48 小時內的原始連結。若被拒絕或出現 API 錯誤則顯示 `error` 而不是捏造貼文。官方參考：https://bsky.network/docs/api-directory/ 和 https://github.com/bluesky-social/atproto/blob/main/lexicons/app/bsky/feed/searchPosts.json 。
- **CMoney 股市爆料同學會**：商業資料 API 已確認存在，**未證實公開訂閱包含社群貼文與再利用權**。不能將一般金融行情資料 API 當作股市爆料社群授權；聯絡 https://cmoney.com.tw/product/api 後方可納入。
- **Reddit**：雲端主機 Data API 需 OAuth，現有 GitHub Actions 無用戶批准的 OAuth 應用，因此尚未呼叫。官方依據：https://support.reddithelp.com/hc/en-us/articles/14945211791892-Developer-Platform-Accessing-Reddit-Data 。
- **YouTube**：可透過官方 Data API 讀取授權範圍內資料，必須有使用者同意的 API Key 與符合衍生情緒統計的政策；本版無金鑰，不使用 HTML 爬蟲替代。官方依據：https://developers.google.com/youtube/terms/derived-metrics-policy 。
- **Mobile01**：使用授權與自動化蒐集規則未核實，暫不嘗試直接抓取貼文；可人工研究或取得正式資料授權。
- **Dcard**：使用條款限制自動化蒐集其他使用者內容，本版禁用爬蟲。來源：https://www.dcard.tw/terms 。
- **TradingView 投資想法**：官方明確禁止自動化蒐集，禁止把公開投資想法當資料 API 抓取；來源：https://tw.tradingview.com/support/solutions/43000674726/ 。
- **PTT**：既有四組來源仍獨立執行，當連線失敗時保留 48h 內曾核實的歷史貼文並標示錯誤；Bluesky 的成功不代表 PTT 正常。
- 限制：目前所有成功新資料仍需觀察實際公開貼文數是否足以代表台股散戶，無資料不代表中立。**新功能由單元測試與 GitHub Runner 真實連線診斷分別驗證**；沒有任何社群來源能修改正式 G 排名或 TITAN 否決。


## LUNA 社群投資意圖與來源韌性 v0.7（2026-10-25）
- 將 Bluesky 查詢擴增為 9 組台股相關主題（台股、台積電、台指期、加權指數、台股 ETF、當沖、正二、CPO 股票、台灣股票），另從已存檔正式 G Top20 讀取最多 3 個公司名稱作為研究查詢。每組最多 25 篇，不累計重複原文；官方 AppView API 限流會停止額外查詢，任何來源不能因此解除 TITAN 風控。
- `investmentEligible` 是以保守字詞規則判斷是否具有投資語境，不宣稱 Gemini 已逐篇進行語意分類。社群貼文保留最多 80 則原文摘要及日期以供核對，但只有 `investmentEligible=true` 且 `contentType=投資討論` 的貼文計入多空樣本與 G 個股熱度。
- 媒體轉載、台積電員工獎金、運動會、與股價無關的公司資訊仍可稽核，但統計上分成 `repostedNews` 或 `unrelated`，不得灌入看多、看空。公告及活動含實質買賣用語時仍需人工複核；不將這種簡單規則當完整語意理解。
- `social.rawSample` 為 48 小時內公開貼文的可查證件數；`social.sample` 為真正符合投資語境的件數；`platformCounts`、`investmentDiscussion`、`repostedNews`、`unrelated` 分開列示。無投稿不代表中立，沒有拿到授權的平台持續顯示未授權。
- Bluesky API 若只有部分查詢成功，會顯示 `partial` 和 `queryHealth`（嘗試、成功、失敗、是否限流），仍保留已核實貼文；若全部失敗，仍標示 `error`。對已確認的新貼文可使用 `partial`，但不能把其他來源失聯時的快取當成最新。
- 舊版歷史報告繼續相容，九次 Gemini 獨立 API 推論、TITAN 硬性否決、G 正式排名、既有金融資料來源與風險計分保持不變。


## LUNA v0.8｜每日社群研究資料庫與 Gemini 語意稽核（2026-10-25）
- 只處理已合法取得、48 小時內、可對照原文、標記為投資討論的公開摘要。保留舊的規則式標籤，但 **Gemini 逐篇結果獨立存為 `items[].semantic` 與 `semantic` 統計**，不覆寫行情、社群規則值與 TITAN 風控。
- `scripts/classify_luna_semantic.cjs` 向 Google Gemini 正式 `generateContent` 送出最多 16 篇新貼文、每批最多 8 篇，需 GitHub Secret `GEMINI_API_KEY`，使用結構化輸出。逐篇 `intent`、`stance`、`emotion`、`confidence`、`evidence`；證據文字必須逐字出現在來源摘要中、貼文 ID 必須完全對應，否則整批失敗。模型僅分析公開摘要，**未抓取留言全文**，沒有真實績效或操作建議。
- 相同 URL／標題／發文時間的先前成功語意判讀可在 48 小時內快取重用，避免每 2 小時重複花 API 額度；只有實際完成 HTTP Gemini 呼叫才增加 `inferenceCalls`。金鑰缺失、API 429、逾時、拒答與輸出格式失敗均顯示 `unavailable`／`error`／`partial`，不輸出假的已驗證結果。
- `scripts/archive_luna_history.py` 每次蒐集後更新 `docs/data/social_sentiment/history/YYYY-MM-DD.json`，同日原文網址去重並保留首次見到／最後見到時間、最近 24 次執行與來源狀態。`history/index.json` 保存近 30 個臺灣日期的每日摘要供手機頁面閱讀；沒有儲存登入權杖、私人帳戶資料或留言全文。
- 公開 GitHub **有 Git 歷史**，即使工作樹刪除超過 30 日的 JSON 檔，Git 歷史未必同步清除；這是可稽核的有限期研究快照，不應稱為可完全刪除的私人資料庫。
- 六代理的 LUNA 首輪會額外看到已驗證語意統計與逐篇可查核證據，但不提供任何直接下單訊號。頁面將規則式樣本、Gemini 逐篇判讀、每日歷史索引分開呈現。
- 自動化：`LUNA Public Social Sentiment` 原排程先蒐集社群→Gemini 判讀→封存每日檔→驗證一致性→提交 GitHub→自動部署 Pages；原 `Six Agent Gemini LLM Debate` 工作日 19:00 九輪研究排程獨立，不因社群判讀自動改風控或觸發交易。
- 測試：`python -m unittest discover -s tw-stock-dashboard/tests -p 'test_luna_archive.py' -v` 與 `node --test tw-stock-dashboard/tests/test_luna_semantic.cjs`。這些測試用 mock API，**不代表真實模型已成功**；只有 main 正式 run 顯示大於 0 的 `inferenceCalls` 與 `status=verified` 才能宣布實際跑通。


## LUNA v0.9 與 ORION 財經新聞資料庫（2026-10-25）
### LUNA：YouTube／Facebook 官方來源
- YouTube：使用正式 YouTube Data API search.list，搜尋最近 48 小時內的台股、台積電股票、台指期等影片標題，保存頻道名稱、影片標題、時間與原文連結。需要 GitHub Actions Secret YOUTUBE_API_KEY（Google Cloud 啟用 YouTube Data API v3），缺少時明確 not_configured。這是影片創作者內容，不是影片字幕、留言或散戶情緒。
- Facebook：只讀取 Meta Graph API 已授權粉專的公開貼文。需要 Secret FACEBOOK_PAGE_ACCESS_TOKEN 及 Variable FACEBOOK_PAGE_IDS（最多 5 個以逗號分隔的數字粉專 ID），並須確保應用取得對應的 Page 權限。缺少授權即 not_authorized；不爬個人動態、社團、一般網友留言或全站公開粉專。
- 二者獨立存 creatorMedia，絕不納入 PTT/Bluesky 的 social.sample、G 個股過熱判讀或散戶多空投票。頁面提供可核對原文與授權狀態。
### ORION：多家台灣財經媒體新聞風向
- 已設定的 RSS 來源：中央通訊社產經證券／科技、自由時報財經、ETtoday 財經、Yahoo 股市台股／國際財經，共 6 個訂閱端點、4 家主要發布機構；另參考既有市場事件 JSON。不是全部台灣媒體，會逐來源顯示 ok/empty/error 與涵蓋率。
- 每篇最多存 145 字標題、來源、發布時間、原始文章 URL 與題材，不抓全文、不繞付費牆。來源應遵守 RSS 條款（個人、非商業用途與明確標示出處）；不得未獲授權重製內文。
- Gemini 對新標題最多每輪分析 24 篇、每批 8 篇，分偏利多報導／偏利空報導／中性資訊難判，並列 AI/半導體、資金法人、總體利率、能源原物料、政策地緣、ETF 投資、台股行情等題材。模型必須引用原標題的逐字證據，分類不代表股價未來方向。沒有實際成功 Gemini 呼叫就不能顯示經驗證風向。
- 獨立 ORION Taiwanese Financial News 排程：台灣每天 08:15 至 22:15，每兩小時更新一次，保存 docs/data/orion_news/latest.json、history/YYYY-MM-DD.json 及 history/index.json 的 30 日索引；更新成功會自動部署 GitHub Pages。Git 歷史不保證永久刪除。
- 六代理 ORION 可參考真實最新的多媒體標題與獨立模型報導語氣，TITAN 風控否決及 G 排名完全不受新聞風向改寫。報導語氣統計不是市場群眾民調，也不是交易訊號。
- 來源條款：中央社 https://www.cna.com.tw/about/rss.aspx；自由時報 https://service.ltn.com.tw/RSS；Yahoo 股市 https://tw.finance.yahoo.com/rss-index；YouTube https://developers.google.com/youtube/data/reference/rest/v3/search/list 。


## ORION 全量 Gemini 分批判讀與快取（2026-10-25）
- 移除最初每輪僅判讀 24 則新聞的硬性限制；改為分析該次公開來源資料集內最多 180 則有效標題（依目前 RSS 收藏上限），以每批 8 則、批次間約 4.2 秒的安全間隔處理。若超過可用 API 速率、發生 HTTP 429 或後端錯誤，該輪立即停止但保留前面所有已核實判讀，下輪排程繼續。
- 使用原本的 GitHub Secret GEMINI_API_KEY 和既有 gemini-3.5-flash-lite 模型，不額外收費開 OpenAI API；ChatGPT 在對話中可額外人工綜合分析矛盾新聞，但它不會在 GitHub Actions 裡免費、自主定時執行。
- 已核實文章只要 ID、標題、發稿時間與 URL 完全匹配就沿用上輪 Gemini 判讀；來源不同但文章標題完全一致也可經引文檢核後複用判讀，標記 reusedIdenticalHeadline。不同標題、不同事件、相似題材不會強行當作相同；跨媒體轉載的同事件不同寫法仍可能重複，不能宣稱完成語意事件去重。
- ORION semantic 新增 coveragePct、unclassified、attemptedCalls、quotaLimited、headlineReuse、distinctHeadlineGroups、repeatedHeadlineCount。完整模型判讀以前狀態為 partial，頁面僅顯示已判讀樣本的語氣比例，不應視為所有新聞或市場共識。
- 現有 ORION 30 日標題歷史、時間查核、GitHub Pages 圖表及六代理 TITAN 風控全部保留；Actions publish timeout 由 10 分鐘增為 14 分鐘，以支援多批次正式判讀。
