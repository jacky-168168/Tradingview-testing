# 0050 + G Top3 私人 VWAP／當日均價驗證（Fugle）
> 狀態：**程式與排程已建立；未取得授權行情之前，沒有任何真實 VWAP 訊號。** 不改正式 G／F／F2，公開主頁不顯示受授權限制的即時行情。
## 實際資料
- 使用已收盤的 `docs/data/latest.json`：`models.G` 前三檔＋0050，固定當日研究名單，不能盤中用未收盤資料偷換股票池。
- 股票日內 `/stock/intraday/quote/{symbol}`：取成交 `lastTrade.price`、`lastTrade.time` 及 `avgPrice`。均價是**當日成交均價（自開盤累計）**，區別於期貨的單根分 K VWAP。
- 0050 另查 `/stock/intraday/candles/0050?timeframe=1`，只從**已完整結束**的 09:00～09:14 十五根 K 棒算第一段開盤區間。
- 研究條件 `FOLLOW_THROUGH_15M`：0050 最新實際成交價 > 當日累計均價且突破前 15 分鐘高點，並且 G Top3 **至少兩檔**成交價高於當日累計均價。這**尚未證明能增加獲利**；不是可下單指令。
- 警戒：0050 跌破前 15 分鐘低點、低於當日均價，且 G 候選站上均價比例 ≤1/3。仍是待回測的風險研究條件。
## 安全與資料品質
- 拒絕試撮 `isTrial`、非正式成交、日期錯誤、成交量為零、未滿 15 根完整分 K、超過五分鐘的成交、未在 09:00～13:30 發生的成交。
- 盤後、例假日、前一盤後 G 榜單資料不對齊、API 無權限時，都不輸出交易建議。
- 公開 Actions logs **僅顯示成功驗證檔數／資料品質狀態**；絕不輸出完整行情、均價、衍生買賣訊號。GitHub Pages 也不能重新發布個人授權的即時行情或衍生指數。
- 請先向資料提供者確認個人授權及公開重播權限。單純的 GitHub Pages 密碼頁屬前端顯示，**不等於安全的資料授權保護**。
## 在 GitHub 啟用（不必把金鑰傳給 ChatGPT）
1. 先依 [Fugle 金鑰申請說明](https://developer.fugle.tw/docs/key/) 申請個人 API Key。
2. 在 GitHub Repository → **Settings → Secrets and variables → Actions → New repository secret**，名稱輸入 `FUGLE_API_KEY`，Value 貼入你的 API Key。**不要提交檔案或把 key 放在聊天裡**。
3. 到 [Personal Fugle VWAP Probe](https://github.com/jacky-168168/Tradingview-testing/actions/workflows/personal-fugle-vwap.yml) 手動執行或等週一排程。GitHub 排程會延後，**不適合當秒級即時交易系統**。
4. Actions 只能驗證串接狀態，並非公開可讀的報價頁面。用私人主機／本機跑完整驗證時，使用環境變數 `FUGLE_API_KEY`，例如：
   `python tw-stock-dashboard/research/private_fugle_vwap.py --private-json /tmp/g_private_vwap.json`
   這個私人 JSON 保留成交價和時戳供你自己分析，**不可提交至公開 repo**。
5. 如需把即時衍生判斷顯示在公開 GitHub Pages，必須先取得行情供應商對該使用方式的明確授權；否則應以受保護的**私人** dashboard／backend 呈現。這是下一階段，不可直接寫入公開 `docs/data`。
## 回測需求（待有真實歷史分 K）
需要 0050 及每日 **當時的** G Top3 的分鐘 K，不可拿今天的 G 股票去回測 2023 年；買進時間要使用訊號後成交價，扣手續費、證交稅、滑價，並以 2025 年選參數，2026 年僅驗證（先前看過 2026，不能稱作完全未見）。
每日保留候選股排名「as-of」，按當時已知資料去歷史 minute OHLC 對齊，並測試 09:05、09:15、09:30 的成交差異，不得拿收盤價當早盤買價。
## 官方文件
- [股票即時 Quote／avgPrice](https://developer.fugle.tw/docs/data/http-api/intraday/quote/)
- [股票盤中分 K／average](https://developer.fugle.tw/docs/data/http-api/intraday/candles/)
- [免費方案](https://developer.fugle.tw/docs/pricing/)
- [使用規範／轉傳限制](https://developer.fugle.tw/docs/data/intro/)
