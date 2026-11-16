# 全球金融占星研究中心 V1.0（獨立研究）

> 對照組與金融占星傳統解讀獨立顯示。**沒有任何事件被當成已驗證交易訊號。**

- 天文計算：Astronomy Engine `2.1.19`（MIT）固定版本，採 GeoVector + Ecliptic 的地心真黃道 of date；月球使用 EclipticGeoMoon。**禁止把 EclipticLongitude 的日心結果當作地心黃經**。
- 十大天體地心黃經、黃緯、12星座、視速度、逆行／順行。正負速度由跨越 0° 的 signed wrap 差分算出。
- 五大相位，2° Orb；Mars–Jupiter 0° 歷史事件以每 6 小時掃描及二分法求根，發布精確 UTC 與可辨識的 Orb 視窗。
- `docs/data/financial_astrology/latest.json`、`calendar.json`、`mars_jupiter_conjunction.json` 與 `report.json` 僅由獨立研究 workflow 管理。
- Nasdaq 指數 `^IXIC` 與 S&P 500、DAX、FTSE 100、CAC 40、台灣加權指數的歷史報酬，**只有讀取真實日線資料後才會寫入結果**。使用 Yahoo Finance/yfinance 做研究用途；無行情會明確標示 `unavailable`。
- 保守進場口徑：事件精確時間轉交易所當地日期，之後的第一個完整交易日**收盤**進場，H 個交易日後收盤出場。未到期樣本 censor，不用未來資料。
- 研究期間 1/3/5/10/20/60/90/180/360 個交易日。對照為相同年份每日可能進場點抽樣，bootstrap 95% CI、置換 p 值、BH-FDR；樣本不足 8 次不估計 p 值，少於 20 次不標榜樣本外績效，少於 30 次僅標探索性結果。
- 1°、3° Orb 對行情結果的敏感度目前**尚未驗證**；0° 精確合相的主結果不因 Orb 改變。網頁有明確不宣稱高勝率與因果關係的說明。
- 現有 Risk Score、選股策略與盤中榜單無資料／執行耦合，無券商下單。

## 本地執行

```bash
cd tw-stock-dashboard/financial-astrology
npm ci
npm test
node build.cjs --now=2026-11-15T08:00:00.000Z --output=/tmp/financial_astrology
python3 -m unittest discover -s tests -p 'test_*.py' -v
python3 backtest.py --events=/tmp/financial_astrology/mars_jupiter_conjunction.json \
  --prices=/path/to/real-NASDAQ-prices.csv --market=NASDAQ --output=/tmp/financial_astrology/report.json
```

CSV 格式：`date,close`，日期 ISO 8601，各資料列為真實交易日收盤價。測試使用合成價格 fixture，**不允許將 fixture 當作網站績效發布**。

預設 `--prices` 省略時，會由 yfinance 擷取六市場日線；若網路、API 或授權不可用，該市場應標 `unavailable`，不可沿用人工績效。

## 部署與品質門檻

新增 `financial-astrology.yml` 與原 TW Stock Dashboard 工作流隔離；只寫 `docs/data/financial_astrology/`。自動日更時間避開台股盤中監控時段。GitHub Pages 沿用現有 `tw-stock-pages.yml` 部署。

檢查工作流、JSON、Pages HTTP 實際取得與 UI 均通過**才可以宣稱發布成功**。專用 PR 可直接回滾，不得直接提交 main。

## V1.1：書籍導讀式星盤解釋

- 以使用者提供的《占星其實很簡單！1：入門篇》做**概念與章節導讀**，使用原創文字改寫，不儲存或公開 PDF 及書中大段內容。
- 對應章節：2-3 分類法（火土風水／開創固定變動）、2-4 十二星座、2-6 行星系統與逆行、2-7 五大相位、2-8 解盤法則（不能只看單一項目）。
- 新增 `docs/financial-astrology-explain.js`，純資料表及可測試的 `describe(data)`，接收**使用者目前選定的任何歷史時間星盤**，即時輸出十大行星＋星座組合、順逆行、相位、月相與元素分布的繁體中文解釋。
- 頁面新增「行星＝何種力量；星座＝如何呈現；相位＝怎樣互動；宮位＝哪個領域」的入門導讀，並提示**行運天空快照不是個人本命盤**，沒有指定出生地點／時間不計算宮位。
- 所有金融含義標記為傳統占星概念衍生的研究假說。沒有歷史績效或 OOS 統計，不判定必然漲跌、不擅自修改市場 Risk Score。
- `tests/test_financial_astrology_ui.cjs` 覆蓋十行星、十二星座、五大相位、動態導讀及不出現絕對化股市結論。


## V1.4 三段式結論／真實市場研究／可信度

主畫面只顯示：①傳統占星的簡短結論 ②六個市場的實際歷史報酬 ③含樣本數的可信程度。日期預設取台灣時間；頁面每分鐘更新，歷史查詢可暫停。

### 研究資料與來源
- Yahoo Finance (yfinance) 每日指數收盤價優先；Nasdaq 或 SP500 無法下載時改向 FRED NASDAQCOM / SP500 公開資料下載。FRED SP500 日線通常僅有近10年，不能冒稱30年。網站只公開統計，並不重新發行原始指數日線。
- 每個市場記錄實際行情起訖、報價筆數、價格來源、事件筆數及缺漏原因；行情超過14日未更新判定 unavailable，當日尚未完成的日線不得冒充收盤。
- 精確火星木星合相時間以 UTC 記錄；事件後第一個完整交易日收盤為研究起點，觀察1/3/5/10/20/60/90/180/360個交易日後的結果。
- 統計：事件有效樣本數、上漲率、平均報酬、年份相近交易日平均報酬、平均超額報酬、期內最大回撤、95% bootstrap 區間、近似同年度重抽樣 p 值、9期間 BH-FDR q 值、時間留出觀察。
- 可信度：0次顯示無資料；不足10次為極低；10～29次為低；超過30次也需統計檢定與時間留出資料才能標示初步觀察。所有等級的交易方向維持無法判定，不把觀察性相關當成可交易訊號。
- 選定時間若沒有火星木星合相，歷史事件報表只能作為獨立研究，不能當作所選星盤的多空預測。
- PR 預覽工作流採唯讀下載真實行情，輸出 JSON artifact 與各市場有效樣本數摘要；只有經審核合併後才由既有工作流更新 GitHub Pages。

### 來源說明
- FRED NASDAQCOM: https://fred.stlouisfed.org/series/NASDAQCOM
- FRED SP500: https://fred.stlouisfed.org/series/SP500
- 天文資料：Astronomy Engine 2.1.19 (MIT)。
- 不修改 G 盤中、A/D/F/G/G Pro 交易邏輯、Risk Score、原始行情或交易資料。

## V1.6: Data publication, expanded research and conservative comparisons

- Release: Financial Astrology Research V1 succeeds on main and triggers TW Stock Pages through workflow_run. Pages smoke validates report.json generatedAt and linked main/detail pages. No direct agent merge to main. All generated astronomy/market JSON stays in the isolated astrology data folder.
- Event catalog: eight preregistered categories: Mars/Jupiter conjunction, Venus/Jupiter conjunction, Mars/Saturn square, Jupiter/Saturn conjunction, Saturn/Uranus square, new moon, full moon, Mercury retrograde starts. Astronomy Engine generates exact UTC times in event_catalog.json. Additional events have descriptive-only research, no significance or independent OOS claim.
- Statistical protections: six markets × nine horizons get global BH-FDR; add same-year MA60-trend and realized-volatility matched regimes, event-window purging, independent-event bootstrap and permutation. If regime controls are insufficient, display insufficient rather than claiming success. None of these imply causation.
- Price basis: the commonly quoted DAX ^GDAXI is a dividend-reinvested performance index; other included indices are typically price-only. Each result carries indexReturnBasis and a warning that cross-market return levels are not directly comparable. FRED SP500 fallback covers about ten years.
- Offline strategy experiment: compare buy/hold, MA20 long/flat, and MA20+event-window long/flat using only close(t) info for t→t+1, 5 bps per side, fixed 20 trading-session event window. Report CAGR, Sharpe, Sortino, MDD, Calmar, exposure and entry count. Exploratory, not tradeable index replication.
- Existing G overlay is read-only. It reads the archive selected G model and historical closed tickets, and only reports sample counts and descriptive performance when enough event windows exist. It does not re-run G cash accounting, modify original selection or Risk Score, and is not a comparable portfolio Sharpe/CAGR. Full G+astronomy strategy would require a frozen-parameter cash-ledger run with blind OOS.
- Failure handling: all failed quote sources remain explicitly unavailable, no invented values. PR preview stores research JSON artifact only, and main daily workflow publishes actual data after review/merge.
- Tests: npm test, python -m unittest discover -s tw-stock-dashboard/financial-astrology/tests -p test_*.py, python -m unittest discover -s .github/agent -p test_*.py, and Pages live smoke.
