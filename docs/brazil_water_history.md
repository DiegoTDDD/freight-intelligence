# Monthly ANTAQ port handling history

The reviewed original exports contain **62 months**, January 2021–February 2026:
five complete calendar years (2021–2025) and two observed months in 2026.
No missing month is filled with zero and the partial year is never annualized.

Source: [ANTAQ Estatístico Aquaviário, Movimentação Portuária](https://aquarela.antaq.gov.br/single/?appid=56c32604-37bd-4993-9904-1b2c87706808&sheet=bb5c2c57-9e0e-46d4-a2bb-006e1de59add&opt=currsel%2Cctxmenu),
**GR1.6 – Evolução da Movimentação**, object `hxpsVb`, exported on 2026-11-19.
Each export selects one year only, scale `DadosEscala=1`, with month,
geography, cargo, navigation and direction unfiltered. The original XLSX files
explicitly contain month and year columns. Each year retains its export-context
screenshot and rendered overview, including the independently displayed total.
The source edition says data through February 2026, updated 2026-04-01 08:17;
the review date does not make these live observations.

The scope is **port handling**, both directions and all navigation categories.
Cargo can appear at successive handling events. These values are not unique
shipments, Brazilian modal demand or paired transport links. They must not be
added to cabotage transport tonnes, TEU or the overlapping annual references.

## Original precision and annual reconciliation

The original numeric XLSX values, including their floating-point artifacts,
are preserved in the CSV/API. Three decimal places in the UI are formatting,
not a claim of physical measurement accuracy. All six export sums round to the
independently displayed total within half a displayed tonne; residuals are retained.

| Year | Observed months | Exported monthly sum (t, display only) | Source headline (whole t) |
| --- | --- | --- | --- |
| 2021 | 12 | 1,209,207,335.297 | 1,209,207,335 |
| 2022 | 12 | 1,220,619,267.036 | 1,220,619,267 |
| 2023 | 12 | 1,305,105,576.675 | 1,305,105,577 |
| 2024 | 12 | 1,322,436,996.505 | 1,322,436,997 |
| 2025 | 12 | 1,402,731,832.755 | 1,402,731,833 |
| 2026 | 2, partial | 205,539,907.438 | 205,539,907 |

For **2025**, rounding each exported month individually exactly reproduces the
archived twelve integer chart labels, whose sum is **1,402,731,832 t**. Summing
the original numbers first and then rounding gives **1,402,731,833 t**, matching
the panel headline. This demonstrates the one-tonne display-rounding difference;
no balancing amount or invented monthly adjustment is applied. The older integer
view remains available and the separate annual-report/ONTL editions are unchanged.

## Reproduction and use

[history_provenance.json](../deployment/brazil_water/history_provenance.json)
pins the original exports, context images, overviews and derived CSV files.
Its own SHA-256 is fixed in the reader. Altering a file and rewriting its manifest
hash cannot approve a different source edition. Rebuild offline using
`python -m scripts.prepare_brazil_water_history`; this only reads the six small
reviewed workbooks. The hosted reader needs no spreadsheet parser or raw bulk data.

In **Brazilian freight → All five modes → Water**, choose **Monthly port handling
history · 2021–2026**. The year selector includes all reviewed months or a single
year. The chart, table and CSV follow that selection; the annual table retains
observed-month counts, completeness and rounding residuals. English is the default
and Portuguese is optional.

`GET /api/brazil/water-history` returns monthly observations by default.
Use `view=annual` for the six observed-period totals. Optional `year=2021..2026`;
`month=1..12` applies only to the monthly view. Pagination uses `limit=1..500`
(default 100) and nonnegative `offset`. Unobserved March–December 2026 returns
an empty selection. Invalid filters return 422; modified/missing evidence returns
503 only for this dataset. The analytics permission applies in protected deployments.

The source history is too short to extend the existing minimum-eight-year annual
forecast protocol; this delivery adds observations and reconciliation, not a
forecast fitted to an incomplete year.
