# TradingView 串接 API 探索筆記

更新：2026-08-10。範圍是官方文件與 TradingView 的公開 GitHub 專案；不把未公開的 TradingView 網站資料端點視為可依賴的 API。

## 先選對產品

| 目標 | 建議產品 | 資料從哪裡來 | 可否使用自訂 Pine | 適用情境 |
| --- | --- | --- | --- | --- |
| 快速嵌入現成圖表 | Financial Widgets（Advanced Chart、Technical Analysis 等） | TradingView | 否 | 行銷頁、資訊頁、最快上線 |
| 自有行情＋完整圖表與內建指標 | Advanced Charts / Charting Library | 自己的後端或第三方資料商 | 否；可用 JavaScript custom studies | 交易平台、需要自己的商品與即時行情 |
| 自有畫面與輕量 K 線 | Lightweight Charts | 完全由應用程式提供 | 不適用；自行計算指標 | 自訂前端、低負載、最高控制權 |
| 策略訊號送到後端 | Pine Script Alert + Webhook | TradingView 在伺服器端執行腳本 | 是，在 TradingView 圖表內 | 通知、交易訊號、由後端再串接券商／交易所 |

重要限制：**TradingView 的圖表元件不提供市場資料**。若使用 Advanced Charts 或 Lightweight Charts，必須自行接資料商或交易所；不要以未公開的 TradingView 網站端點作為正式資料來源。

## 1. 圖表嵌入／Widget

### Financial Widgets：免後端、最快上線

從 [Widgets 文件](https://www.tradingview.com/widget-docs/getting-started/) 選取產生器，將產生的 HTML 或 React 程式碼貼進網站即可。推薦由 **Advanced Chart Widget** 開始：它內建圖表型態、繪圖工具與大量指標；設定 `autosize: true` 時，外層容器必須有明確高度。

```html
<div class="tradingview-widget-container" style="height:500px;width:100%">
  <div class="tradingview-widget-container__widget" style="height:100%;width:100%"></div>
  <script type="text/javascript"
    src="https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js"
    async>
    {
      "autosize": true,
      "symbol": "NASDAQ:AAPL",
      "interval": "D",
      "timezone": "Asia/Taipei",
      "theme": "dark",
      "locale": "zh_TW",
      "allow_symbol_change": true
    }
  </script>
</div>
```

Widget 適合顯示 TradingView 可用的商品與指標；它**不能加入自訂 Pine Script 或策略**。Widget 不設 cookies，但 TradingView 為正常運作會短期處理嵌入頁 URL、widget 型態、商品代號及 IP。

### Advanced Charts：有自有行情時使用

[Charting Library / Advanced Charts](https://www.tradingview.com/charting-library-docs/latest/getting_started/quick-start/) 透過 `new TradingView.widget({...})` 初始化。核心設定是 `container`、`symbol`、`interval`、`library_path`、`datafeed`。

```js
new TradingView.widget({
  container: 'tv-chart',
  library_path: '/charting_library/',
  symbol: 'BTCUSDT',
  interval: '15',
  datafeed: myDatafeed,
  locale: 'zh_TW',
  timezone: 'Asia/Taipei',
});
```

需要先取得 Charting Library 存取權；完整公開實作範例在 [tradingview/charting-library-tutorial](https://github.com/tradingview/charting-library-tutorial)。該套件面向可公開提供的網站，並受其授權條款約束。

### Lightweight Charts：官方開源替代方案

官方公開 GitHub 存放庫是 [tradingview/lightweight-charts](https://github.com/tradingview/lightweight-charts)，目前主線為 v5 API。安裝：`npm install lightweight-charts`。

```js
import { createChart, CandlestickSeries } from 'lightweight-charts';

const chart = createChart(document.getElementById('chart'), { width: 900, height: 500 });
const candles = chart.addSeries(CandlestickSeries);
candles.setData([
  { time: '2026-08-07', open: 100, high: 106, low: 98, close: 104 },
]);
// 收到新一根／更新中的 K 線：candles.update(bar)
```

重點 API：`createChart` 建立圖表；`chart.addSeries` 新增 K 線、折線、區域等序列；`series.setData` 初始／重設資料；`series.update` 串流最新資料；`chart.timeScale().fitContent()` 調整可視區。它只負責呈現，不含資料源、交易功能或內建技術指標。需遵守 Apache-2.0 及其 NOTICE 的 TradingView 歸屬要求。

## 2. 市場資料與技術指標

### Datafeed API（Advanced Charts）

把 JavaScript `datafeed` 物件傳入 widget。最小實作應提供：

- `onReady(callback)`：回傳支援的 resolution、交易所、商品型別等設定。
- `searchSymbols(userInput, exchange, symbolType, onResult)`：商品搜尋（實務上強烈建議）。
- `resolveSymbol(symbolName, onResolve, onError)`：回傳商品 metadata，例如 timezone、session、價格精度。
- `getBars(symbolInfo, resolution, periodParams, onHistory, onError)`：回傳遞增時間排序的 OHLCV 歷史 K 線。
- `subscribeBars(symbolInfo, resolution, onRealtime, subscriberUID, onReset)`：向後端訂閱實時 K 線。
- `unsubscribeBars(subscriberUID)`：解除訂閱。

所有 callback 都必須非同步呼叫（例如 `setTimeout(..., 0)`）。日／週／月 K 的 `time` 應是交易日 **00:00:00 UTC**；不要直接傳可被 library 改寫的同一個陣列。可改用內建 UDF adapter 走 HTTP，但原生不含即時串流。

若使用 Trading Platform 的報價／深度功能，還要實作 `getQuotes`、`subscribeQuotes`、`unsubscribeQuotes`，以及可選的 `subscribeDepth`／`unsubscribeDepth`。

### 指標策略

- **Widget**：使用其已提供的指標與設定；不可載入自訂 Pine 或策略。
- **Advanced Charts**：內建超過 100 個指標。圖表就緒後可呼叫 `widget.activeChart().createStudy('MACD', false, false, inputs)`，並以 `getStudyInputs('MACD')` 查詢輸入參數。自訂指標是 JavaScript `custom_indicators_getter`／PineJS，不是 Pine Script。
- **Lightweight Charts**：在後端或前端自己算 SMA、EMA、RSI、MACD 等，將結果用額外 line / histogram series 畫出；確保計算週期、時區與 OHLCV 資料一致。
- **Pine Script**：僅在 TradingView 平台內執行，適合產生指標、策略與警報，不可直接嵌進 Widget、Advanced Charts 或 Lightweight Charts。

## 3. Pine Script 策略警報 → Webhook

### 建議的可靠流程

```text
Pine 指標／策略 → 使用者在 TradingView UI 建立 Alert 並填 webhook URL
→ TradingView HTTP POST → 你的 webhook 驗證與去重 → 風控／下單服務 → 券商或交易所 API
```

TradingView 不會因為 Pine 程式碼自動建立執行中的 alert；使用者仍須在圖表 UI 的「Create Alert」選擇條件、頻率與 Webhook URL。警報只在即時 K 線觸發；建立時會保存腳本、輸入、商品和時間框架的快照，後續改腳本／參數後要刪除並重建 alert。

### Pine Script v6 範例：收盤確認訊號

```pine
//@version=6
indicator("EMA Cross Webhook", overlay = true)
fast = ta.ema(close, 9)
slow = ta.ema(close, 21)
longSignal = ta.crossover(fast, slow) and barstate.isconfirmed

if longSignal
    alert('{"event":"ema_cross","side":"buy","symbol":"{{ticker}}","close":{{close}},"time":{{time}}}',
          alert.freq_once_per_bar_close)

plot(fast, color = color.teal)
plot(slow, color = color.orange)
```

註：實作時請先在 Pine Editor 檢查 JSON 字串。採 `alert.freq_once_per_bar_close` 與 `barstate.isconfirmed` 可減少盤中重繪／提前觸發。

三種事件方式：

- `alert(message, freq)`：指標與策略都可用；訊息是動態 `series string`，最適合 JSON webhook payload。
- `alertcondition(condition, title, message)`：僅 indicator 有效；每個呼叫在 UI 是一個獨立條件，訊息須為常數字串（可用 placeholders）。
- 策略 order-fill alert：策略的下單函式可自訂 `alert_message`；在 UI 選「Order fills」或同時包含 `alert()`。`alertcondition()` 對策略不能建立 alert。

策略預設只在每根即時 K 的收盤時計算；若啟用 `calc_on_every_tick = true` 才可能在盤中呼叫 `alert()`，但必須自行評估回測與即時行為差異。

### Webhook 合約與安全

- TradingView 以 **HTTP POST** 把 Alert Message 放在 body；合法 JSON 會帶 `Content-Type: application/json`，否則為 `text/plain`。
- 必須啟用帳號 **雙因素驗證（2FA）** 才能使用 webhooks。
- 僅接受連接埠 **80 / 443**、不支援 IPv6，伺服器超過 **3 秒**未回應會取消請求；在 Alert Log 的 Webhook status 監控投遞。
- 不要將交易所 API key、密碼或長期祕密放進 payload。以 HTTPS endpoint、短效簽章或可撤銷的隨機 webhook token 驗證；驗證 schema、限制來源、設計 idempotency key，並在下單前重做風控與去重。
- Webhook 是訊號傳遞，不是保證成交。下單服務應能安全處理重送、延遲、失敗、部位不同步與熔斷。

## 建議落地順序

1. 若只要網站行情展示，先用 Advanced Chart Widget；不用建立 Datafeed。
2. 若要顯示自有／付費資料，選 Advanced Charts + Datafeed API，或用 Lightweight Charts 自建圖表。
3. 在 TradingView 寫 Pine 指標或策略，以 `alert()` 在收盤確認時輸出結構化 JSON。
4. 先將 webhook 接至僅記錄事件的測試 endpoint，再加入驗證、去重、風控與模擬下單；最後才串接真實券商／交易所。

## 官方來源

- [Financial Widgets 文件](https://www.tradingview.com/widget-docs/getting-started/) 與 [Widget FAQ（Pine／策略限制）](https://www.tradingview.com/widget-docs/faq/general/)
- [Advanced Charts：Widget Constructor](https://www.tradingview.com/charting-library-docs/latest/core_concepts/Widget-Constructor/)；[Datafeed API](https://www.tradingview.com/charting-library-docs/latest/connecting_data/datafeed-api/)；[內建／自訂指標](https://www.tradingview.com/charting-library-docs/latest/ui_elements/indicators/)
- [Lightweight Charts GitHub](https://github.com/tradingview/lightweight-charts) 與 [API 文件](https://tradingview.github.io/lightweight-charts/)
- [Pine Script v6 文件](https://www.tradingview.com/pine-script-docs/)；[Alerts](https://www.tradingview.com/pine-script-docs/concepts/alerts/)
- [Webhook 設定與限制](https://www.tradingview.com/support/solutions/43000529348-how-to-configure-webhook-alerts/)
