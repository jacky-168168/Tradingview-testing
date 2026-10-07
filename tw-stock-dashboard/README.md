# 台股 A/D Dashboard — GitHub 移植版

這個目錄是現行 Google Apps Script V12.1 的 GitHub/Python 移植主線。目標不是只把 HTML 丟到 Pages，而是把最耗時的歷史 K、A/D 全市場掃描與長區間回測搬到 GitHub Actions + Python。

## Phase 1（本次）
- A 原始多因子模型：核心技術評分已移植。
- D 技術強勢模型：Volume > 20M、RVOL10 > 1.2、Mom10 > 0、Vol.D > 10% 與健康強勢分已移植。
- Yahoo 日 K：每檔獨立 Parquet 增量快取；已存在的歷史不重抓，只補新日期。
- TWSE / TPEx 股票母檔：官方來源＋本地快取 fallback。
- 靜態 JSON：`docs/data/latest.json`。
- GitHub Pages 前端：A/D 即時切換，不重新計算。

## 下一階段
1. 法人歷史與每日快取。
2. Risk / Top Watch。
3. 題材熱度。
4. A/D 自訂日期回測、1D/3D/5D/10D/20D、Edge Audit。
5. K 快取與回測結果長期保存策略（避免 repo 體積失控）。
6. 與現有 V12.1 欄位完全對齊。

## 本機執行
```bash
cd tw-stock-dashboard
python -m pip install -r requirements.txt
python src/pipeline.py
```

> `cache/` 由 Actions cache 保存，不直接把 1982 檔 Parquet 全部 commit 到 repo；網頁只 commit/部署必要的 JSON。
