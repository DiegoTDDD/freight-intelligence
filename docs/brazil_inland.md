# Transport using inland waterways

This reviewed ANTAQ dataset contains **62 observed months**, January 2021–February
2026, with original monthly totals and three navigation components. Five years
are complete (2021–2025); 2026 contains January and February only. Separate 2025
exports provide three navigation totals and **117 cargo categories**.

## Scope and source

Source: [ANTAQ Estatístico Aquaviário, Transporte Vias Interiores](https://aquarela.antaq.gov.br/single/?appid=56c32604-37bd-4993-9904-1b2c87706808&sheet=dUKM&bookmark=f57a2dcf-21bc-4446-bdcc-78915e0597a2&opt=currsel%2Cctxmenu),
reviewed on 2026-11-19. Monthly **GR5.8 – Evolução por Tipo de Navegação** exports
preserve `Total`, `Longo Curso em vias interiores`, `Cabotagem em vias interiores`
and `Navegação Interior`. The [table section](https://aquarela.antaq.gov.br/single/?appid=56c32604-37bd-4993-9904-1b2c87706808&sheet=kFxB&bookmark=f57a2dcf-21bc-4446-bdcc-78915e0597a2&opt=currsel%2Cctxmenu)
supplies **GR5.1** navigation composition and **GR5.6** simplified commodity names.

The source bookmark initially selects January/February 2026. Acquisition
explicitly removes the month filter and selects exactly one year per export,
retaining scale `DadosEscala=1` and no cargo, geographic or navigation restriction.
Monthly workbooks omit a year column: each year is attributed through its pinned
filter-context screenshot, full rendered overview and exact original XLSX hash.
The source edition says updated 2026-04-01 08:17; this is reviewed historical data,
not a live feed.

**Transport on inland waterways includes international shipping and cabotage
using those waterways, as well as the Inland Navigation category.** It differs
from port handling and from the Interior category in a port-handling report.
Do not add these overlapping populations together. The data does not establish
unique physical cargo, operational routes, navigable itineraries or a paired OD
matrix. The separate regional/port cabotage pairs retain their own scope.

## Reconciliation and missing quantities

Every monthly source total agrees with its three components within 0.0001 tonnes,
an allowance for numeric export summation artifacts, not measurement accuracy.
Each annual/partial-period total rounds to the independently displayed headline.
The independent 2025 navigation and commodity exports also reconcile with the
monthly source total within that numerical allowance.

| Year | Observed months | Displayed source transport total (whole tonnes) |
| --- | --- | --- |
| 2021 | 12 | 110,751,768 |
| 2022 | 12 | 120,527,604 |
| 2023 | 12 | 130,950,419 |
| 2024 | 12 | 128,907,186 |
| 2025 | 12 | 144,893,597 |
| 2026 | 2, partial | 21,024,624 |

2025 has **109 numeric commodity quantities**, including **46 explicit numeric
zeros**. Eight other quantities are shown as **dash** in the original export:
they remain null with `quantity_status=source_dash`, not zero. Numeric records
use `reported_numeric`. The original numeric shares are preserved even for dash
quantities; a zero share does not supply a missing quantity. Shares retain the
full 2025 denominator and are never renormalized after filtering.

Soja, for example, retains 36,369,997.212 displayed tonnes and its original
approximately 25.101% share. Original Portuguese commodity/navigation labels
remain source data; UI navigation supports English and Portuguese. Displayed
decimal places are formatting; downloaded values preserve the original numeric
export, including floating-point artifacts.

## Dashboard, API and reproduction

In **Brazilian freight → All five modes → Water**, choose **Inland-waterway
transport · history and cargo**. Views cover monthly history, 2025 commodities
and 2025 navigation composition. The year selection filters monthly rows and CSV;
the navigation selector chooses the metric/chart series while the full original
monthly components remain in the table/CSV. Commodity filtering retains original
shares and availability. The chart shows at most twenty numeric cargo categories;
the table and CSV retain every matching record, including nulls and zeros.

`GET /api/brazil/inland-transport` defaults to `view=monthly`. Other views:
`annual`, `navigation`, `commodities`. `year=2021..2026`; the last two views
accept only 2025. `month=1..12` is available only for monthly observations;
`commodity` is an exact original label, available only in the commodity view.
Pagination: `limit=1..500` (default 100), nonnegative `offset`. Unobserved months
return no records. Invalid filter/view combinations return 422; missing or changed
evidence returns 503. The analytics permission protects configured private APIs.

Original exports, screenshots, source context and four derived CSV tables are
pinned in [inland_provenance.json](../deployment/brazil_water/inland_provenance.json).
The reader fixes that review contract's own hash and invalidates its bounded cache
when any evidence file changes. Rewriting a manifest hash cannot approve modified
data. Rebuild offline with `python -m scripts.prepare_brazil_inland`; no bulk FAF
pipeline, network download or source-year inference runs during preparation.
