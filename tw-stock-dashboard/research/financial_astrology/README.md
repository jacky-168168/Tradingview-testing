# Financial Astrology Research Lab / 全球金融占星研究中心

## Status (V1.0)
- **Astronomical calculations**: 10 bodies, geocentric apparent ecliptic longitudes (true ecliptic-of-date, tropical), Moon phases, 0/60/90/120/180 degree aspects and retrograde stations.
- **Presentation**: main-page research card and independent researcher page. Traditional cultural interpretations are clearly isolated from statistical evidence.
- **Market predictive claims**: **NONE**. No source-audited historical US/EU/TW market series has been committed. Do **not** publish a win rate or market directional forecast until a separate audited study is completed.
- **No integrations** with G selectors, risk score, trading orders or news classifiers.
- **Not yet implemented**: official exchange calendars, price bars with opening fills, confidence intervals, HAC/FDR, walk-forward cross-validation, event-clustered bootstrap, MFE/MAE (need intraday/high-low price data), house cusps, eclipses and Bradley replica. Do not describe V1 as completing those.

## Reproducibility
Node.js 22+:
\`\`\`sh
cd tw-stock-dashboard
npm ci --ignore-scripts
npm run astro:test
npm run astro:generate
node src/financial_astrology/historical.cjs  # expensive; 2000..current-year
node src/financial_astrology/research.cjs
\`\`\`

Source: [Astronomy Engine](https://github.com/cosinekitty/astronomy), pinned \`2.1.19\`, MIT. The browser version is fetched from a version-pinned jsDelivr public CDN only for on-demand time calculations; the Pages snapshot works offline when the CDN is unavailable. Browser libraries are an availability dependency, not financial price data.

### Coordinate and time conventions
- Every event stores UTC ISO time; local display is \`Intl.DateTimeFormat\` by exchange time zone.
- Earth-centered \`GeoVector\` in EQJ, converted by \`Ecliptic\` to geocentric true ecliptic-of-date (ECT). Do **not** substitute heliocentric \`EclipticLongitude\`.
- Longitude is [0,360), zodiac starts 0 Aries, 30-degree tropical sections.
- Apparent retrograde uses central-difference geocentric longitude velocity with signed angular wrap. Stations use root search of this velocity.
- Main aspect events require the **actual angular-difference root**, found by bracketed bisection; 0/360 crossing is not a false event. Times are rounded to 1 minute and include an unrounded-orb residual.
- Fixed default main aspect orb = 2 degrees. Different orb thresholds must be treated as independent exploratory hypotheses.

## Adding audited market data (NOT automatic in V1)
Provide CSVs in \`tw-stock-dashboard/research/financial_astrology/markets/\` named:
\`SPX.csv\`, \`IXIC.csv\`, \`NDX.csv\`, \`SOX.csv\`, \`DAX.csv\`, \`FTSE.csv\`, \`CAC.csv\`, \`STOXX50.csv\`, \`TAIEX.csv\`.

Each CSV uses \`date,close\` columns, with one **exchange trading session** per row, chronological ISO dates, close >0 and no synthetic rows. Any prices must be legally distributable: do not commit licensed paid data to a public repository.

Each market also requires a \`MARKET.source.json\` document:
\`\`\`json
{
  "url": "https://source.example/verified-price-dataset",
  "retrievedAt": "YYYY-MM-DDTHH:mm:ssZ",
  "priceType": "price-index or total-return-index or adjusted-etf",
  "licenseReviewed": true,
  "coverageStart": "YYYY-MM-DD",
  "coverageEnd": "YYYY-MM-DD",
  "methodology": "describe splits, dividends, missing sessions, revisions"
}
\`\`\`
The example values above are documentation placeholders, **not** a real dataset.

Run the **Financial Astrology Research** workflow manually with \`regenerate_history=true\` to generate a dated astronomical event catalogue for 2000–present, independent from any market prices. Once source-audited price CSVs are supplied, run \`research.cjs\` for exploratory close-to-close event statistics.

### Backtest caveats / TODO for V1.1
- Currently uses a conservative next-exchange-session **closing price** after the event and a closing exit after h further sessions. This is *not* a realistic next-open fill; trading simulations require verified open/transaction costs.
- Deduplicates exact same entry session, but does not remove overlapping forward holding windows or control for seasonal/day-of-week/year/market regime confounders.
- Uses chronological 70/30 descriptive holdout statistics; does **not** optimize on the train set or certify OOS significance.
- No HAC standard errors, block bootstrap confidence interval, false-discovery-rate correction, event-by-event causality analysis, or proper rolling walk-forward yet.
- A rolling-index benchmark is calculated for orientation only. \`status: exploratory\` must **not** become \`verified\` until these controls pass independent review.
- If data is absent, output \`unavailable\` and UI shows N/A, never numbers.
- Source metadata alone cannot prove data provenance: data lineage, checksums and calendar reconciliation still require independent audit.

## GitHub Actions and Pages
\`.github/workflows/financial-astrology.yml\` runs on a standalone schedule and can manually regenerate historical events. Its write step commits **only** \`docs/data/financial_astrology/\` and, when deliberately requested, \`research/financial_astrology/historical-events.json\`. It does not change G data, dashboard scores or issue orders.

\`.github/workflows/tw-stock-pages.yml\` has a dedicated \`workflow_run\` trigger for this workflow: token-generated data commits do not themselves trigger ordinary push workflows. The existing Pages deployment remains shared but the research compute job and data folder are isolated. Verify the Pages URL after merge and deployment; passing CI alone is insufficient.

Follow root \`AGENTS.md\`: propose via PR and do not merge without separate approval and regression evidence.
