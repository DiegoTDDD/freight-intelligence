# Reported monthly road movement history

The reviewed [ANTT movement panel](https://www.gov.br/antt/pt-br/assuntos/cargas/dadostrc/movimentacao-de-cargas)
publishes **28 observed months, July 2024–October 2026**, split by its own-account
flag `Carga Própria?`: **N = non-own-account**, **S = own-account**.
There are 56 monthly account-category records, each retaining tonnes and MDF-e
document counts. No period is fabricated before July 2024 or after October 2026.

The public [Power BI report](https://app.powerbi.com/view?r=eyJrIjoiYWNhMTRjYmQtZjczYy00OGJkLThiZWQtOTAwYjEwMmNjOWY4IiwidCI6Ijg3YmJlOWRlLWE4OTItNGNkZS1hNDY2LTg4Zjk4MmZiYzQ5MCJ9)
was reviewed on 19 November 2026. All date/source account categories were included;
vehicle, cargo, geographic and subcontracting filters were unfiltered. This
includes the source's `EX`/exterior category when reported. Do not call this a
domestic-only or complete national shipment census.

## Observed coverage and totals

| Year | Months | Complete calendar | N tonnes | S tonnes | Observed tonnes | MDF-e documents |
| --- | --- | --- | --- | --- | --- | --- |
| 2024 | July–December, 6 | No | 591,729,835 | 103,289,674 | 695,019,509 | 44,573,360 |
| 2025 | January–December, 12 | Yes | 1,164,978,181 | 203,649,523 | 1,368,627,704 | 90,060,010 |
| 2026 | January–October, 10 | No | 1,099,010,747 | 191,491,774 | 1,290,502,521 | 84,223,450 |

2024 and 2026 values are **observed-period subtotals**, not full annual totals.
Missing months are never imputed as zero or annualized. Annual-view rows include
both component categories and their `all` subtotal; do not add the subtotal to
its components. Tonnes and document counts are different measures and are never
added together. A single physical trip or cargo can appear in multiple MDF-e
documents. The official MDF-e exemptions described by ANTT also apply.

## Capture method and source precision

The official **Show as table** view was opened for **Toneladas por mês** and
**Emissão mensal de MDFes**. Rendered row headers and N/S cells were read from
the table, including the later rows reached through normal table scrolling.
No hidden report state, guessed endpoints, chart pixel estimation or rounded
million-scale bar labels were used.

The archived JSON is a **UI transcription**, not an original raw download from
ANTT. Strings preserve the source table's integer displays and Portuguese
thousands separators. Tonnes are published integer display values, not unrounded
individual measurements. Screenshots of the first/last table sections and the
unfiltered report context corroborate the capture. Every evidence file has a
reviewed SHA-256 pinned in code. Derived CSVs must reconstruct those source rows
exactly; manifest rehashing alone cannot approve altered values or evidence.

- [Archived source-table transcription](../deployment/brazil_road/history_capture.json)
- [Archived source overview text](../deployment/brazil_road/history_overview.txt)
- [Unfiltered source context](../deployment/brazil_road/history_context.jpg)
- Tonnes table: [first section](../deployment/brazil_road/history_tonnes_first.jpg), [last section](../deployment/brazil_road/history_tonnes_last.jpg)
- MDF-e table: [first section](../deployment/brazil_road/history_mdfe_first.jpg), [last section](../deployment/brazil_road/history_mdfe_last.jpg)
- [Monthly account-category observations](../deployment/brazil_road/monthly_history.csv)
- [Observed-period subtotals and completeness flags](../deployment/brazil_road/annual_history.csv)
- [Twelve-month edition comparison](../deployment/brazil_road/yearbook_comparison.csv)
- [Manifest, units, filters and hashes](../deployment/brazil_road/history_provenance.json)

The source header displays **SUROC última atualização: mar/26**, despite table
labels extending through October 2026. This inconsistent stamp is preserved and
is not used as a guarantee of freshness. The reviewed capture date and actually
observed period labels establish this snapshot's coverage.

## Editions and reporting changes

The separately archived 2025 yearbook's twelve published monthly totals sum to
**1,368,699,651 tonnes**. The reviewed panel sum is **1,368,627,704 tonnes**, a
difference of **−71,947 tonnes**. Both observations and their provenance remain
available; no month is overwritten and the editions are not spliced. The source
does not establish a cause for this inter-edition difference.

The panel's explicit N subtotal, **1,164,978,181 tonnes**, rounds to **1.165
billion** at million-tonne precision. It numerically agrees with the yearbook's
regional-table reference. This provides a directly observed N/S composition for
the panel, but does not retrospectively prove the exact scope of the older
regional denominator. Rounded yearbook percentage shares are not inverted into
invented exact values.

ANTT also notes that the October 2025 MDF-e decline may reflect adaptation to a
new reporting layout effective 6 October 2025 (Technical Note 2025.001), with
expected behavior returning after 17 October. A reported fall is not proof of
lower physical freight demand. This short, structurally affected window is not
used to claim a validated forecasting model.

## UI, API and rebuild

In **Brazilian freight → All five modes → Road**, choose **Monthly road history
· reviewed panel**. Filters cover year, account category and tonnes/documents.
Partial-year warnings and the edition comparison remain explicit. English is
the default and Portuguese is optional. The archived yearbook and its 16 RGI
flows remain available through the same dataset selector.

`GET /api/brazil/road-history` defaults to the 56 `monthly` rows.
`view=annual` supplies nine component/subtotal rows with `months_observed` and
`full_year`. `view=editions` supplies twelve 2025 comparisons. Optional `year`
accepts 2024–2026. `account_type=non_own_account` or `own_account` filters monthly
or annual rows; `account_type=all` is an annual subtotal only. It is rejected
for monthly/edition views rather than ambiguously doubling components.
Pagination uses `limit` (default 100, maximum 500) and zero-based `offset`.
Authenticated mode requires analytics permission; invalid/missing evidence
returns 503. The older `/brazil/road-monthly` endpoint retains its yearbook data.

Rebuild offline: `python -m scripts.prepare_brazil_road_history`.
The source transcription, all evidence hashes, exact calendar/category contract,
annual sums, completeness flags and old/new comparison are verified. Regenerate
the static report with `python scripts/build_portfolio_evidence.py`.
Refreshing the Power BI capture requires a new documented review; the existing
weekly PDF audit does not silently refresh this separate panel edition.
