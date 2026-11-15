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
