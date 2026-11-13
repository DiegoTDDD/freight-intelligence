# Published regional road freight flows

The road view adds Table 12 of the official [ANTT TRC 2025 yearbook](https://www.gov.br/antt/pt-br/assuntos/cargas/dadostrc/anuario_trc_2025_antt.pdf),
PDF page 64 (printed page 56): 16 leading flows between Immediate Geographic
Regions (RGIs), with reported tonnes and rounded source shares. RGIs group
municipalities. A same-RGI flow can still cross municipal boundaries; it must not
be interpreted as a within-city trip. MDF-e does not cover within-municipality trips.

The selected pairs retain their published direction. No reverse flow, complete
OD matrix, road geometry or truck access permission is inferred. Unlisted pairs
are unavailable, not zero. The displayed shares retain the publication's
denominator and rounding; they are not shares of the filtered table.

## Annual indicator reconstructed from monthly totals

Chart 45 on PDF page 63 (printed page 55) labels all 12 monthly total-tonnage
values. Their sum is **1,368,699,651 tonnes**, which rounds to **1.4 billion** at
the summary's precision (PDF page 61). This supplies the annual all-transport
MDF-e indicator without choosing between inconsistent prose totals. The monthly
series includes paid and own-account transport; it is administrative reported
tonnage, not a complete census of unique national cargo. All MDF-e exemptions apply.

The **1.165 billion** figure on page 64 is retained only as the regional table's
published reference. Page 63's 543 million identifiable plus 622 million
unidentified tonnes also sum to that reference. The source does not explicitly
explain this denominator's scope difference from Chart 45. Rounded paid shares
are not sufficient to identify an exact paid-only total, so no such total is
invented. Regional shares are never rescaled against the monthly all-transport sum.

The snapshot contains both CSVs. Validation requires exactly one row per month,
positive integer tonnes, and agreement between the monthly sum, annual metadata
and rounded summary. A partial series or changed sum is rejected.

The source PDF was downloaded and visually reviewed. Its SHA-256 is
`db96f4a5e779261a28e050b165ef84236ddd92d3ac0f0801a12fb04306e03e0b`.
Rebuild with `python -m scripts.prepare_brazil_road --source-pdf PATH`; another
edition is rejected until reviewed. The small CSV has its own integrity manifest,
strict period/unit/duplicate checks, and is included in recovery packages.

In the dashboard: **Brazilian freight → All five modes → road**. Filters cover
origin state, destination state and same/different region. CSV download retains
all 16 published rows. English remains the default.

API: `GET /api/brazil/road-flows`, with optional `origin_state`,
`destination_state` (Brazilian state abbreviations), and `same_region` filters.
Valid unlisted pairs return an empty list; invalid states return 422; missing or
inconsistent data returns 503. Existing analytics permissions apply.

`GET /api/brazil/road-monthly` exposes all 12 monthly rows, the annual
reconciliation and chart provenance. Optional `month=1` selects January; the
annual metadata still explicitly refers to all 12 months. The generic modal
endpoint also includes `mdfe_recorded_tonnes` with this annual sum.

The [source audit](source_refresh.md) checks the official PDF weekly and keeps
changed editions for review. It cannot silently replace the reviewed monthly values.
