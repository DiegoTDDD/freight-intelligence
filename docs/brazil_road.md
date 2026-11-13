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

The national tonnage discrepancy remains unresolved: the summary on PDF page 61
reports approximately 1.4 billion tonnes, while page 64 uses 1.165 billion. Page 63
also reports 543 million identifiable and 622 million unidentified tonnes, which
sum to 1.165 billion; this arithmetic consistency does not explain the difference
from the summary. The project does not promote either as a reconciled national total.

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
