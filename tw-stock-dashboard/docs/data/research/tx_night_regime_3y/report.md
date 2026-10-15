# TX 夜盤 × Risk Score 三年回測

結論狀態：COMPARATIVE_RESEARCH_ONLY
正式風控日數：728
有效配對夜盤：718/727（98.76%）
缺值原因：{"near_month_roll_mismatch": 9}
錯誤：None

## 研究限制
- Risk classification only. Next cash close-to-close outcome is NOT executable trade P&L.
- Historical FinMind must be crosschecked against sample dated TAIFEX reports.
- No historical intraday 09:30 veto was tested; minute-index data not present.
- Survivorship and G stock strategies are NOT part of this index-only study.
- 2026 has been researched before and is not a pristine untouched holdout.
- All score thresholds predeclared; compare false blocked up days as well as avoided loss days.

## train2023_2024
| 規則 | 允許天數 | 大跌2%日通過率 | 避開全部大跌2%日比例 | 錯過上漲日比例 |
|---|---:|---:|---:|---:|
| official60 | 162 | 1.23% | 80.0% | 43.2% |
| TXadjust60 | 155 | 0.65% | 90.0% | 43.2% |
| official60_and_TX_better_minus1 | 156 | 0.0% | 100.0% | 43.2% |
| TXadjust60_and_TX_better_minus1 | 150 | 0.0% | 100.0% | 43.2% |
| TXadjust55 | 167 | 0.6% | 90.0% | 38.46% |
| TXadjust65 | 146 | 0.68% | 90.0% | 46.15% |
| TXadjust60_and_TX_better_minus2 | 155 | 0.65% | 90.0% | 43.2% |
| TXadjust60_and_TX_better_minusHalf | 143 | 0.0% | 100.0% | 43.79% |

## evaluate2025_2026
| 規則 | 允許天數 | 大跌2%日通過率 | 避開全部大跌2%日比例 | 錯過上漲日比例 |
|---|---:|---:|---:|---:|
| official60 | 234 | 1.28% | 86.96% | 42.32% |
| TXadjust60 | 230 | 0.87% | 91.3% | 39.83% |
| official60_and_TX_better_minus1 | 212 | 0.94% | 91.3% | 43.15% |
| TXadjust60_and_TX_better_minus1 | 219 | 0.91% | 91.3% | 40.25% |
| TXadjust55 | 257 | 1.56% | 82.61% | 35.68% |
| TXadjust65 | 209 | 0.96% | 91.3% | 45.64% |
| TXadjust60_and_TX_better_minus2 | 230 | 0.87% | 91.3% | 39.83% |
| TXadjust60_and_TX_better_minusHalf | 202 | 0.99% | 91.3% | 41.49% |

## all
| 規則 | 允許天數 | 大跌2%日通過率 | 避開全部大跌2%日比例 | 錯過上漲日比例 |
|---|---:|---:|---:|---:|
| official60 | 396 | 1.26% | 84.85% | 42.68% |
| TXadjust60 | 385 | 0.78% | 90.91% | 41.22% |
| official60_and_TX_better_minus1 | 368 | 0.54% | 93.94% | 43.17% |
| TXadjust60_and_TX_better_minus1 | 369 | 0.54% | 93.94% | 41.46% |
| TXadjust55 | 424 | 1.18% | 84.85% | 36.83% |
| TXadjust65 | 355 | 0.85% | 90.91% | 45.85% |
| TXadjust60_and_TX_better_minus2 | 385 | 0.78% | 90.91% | 41.22% |
| TXadjust60_and_TX_better_minusHalf | 345 | 0.58% | 93.94% | 42.44% |
