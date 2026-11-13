# ANTAQ navigation and regional references

The water-mode view adds 43 reviewed reference records from the official
[ANTAQ Desempenho Aquaviário 2025](https://www.gov.br/antaq/pt-br/central-de-conteudos/publicacoes-da-antaq/Anuario2025.pdf)
and its [official annual release](https://www.gov.br/antaq/pt-br/central-de-conteudos/noticias/2026/setor-aquaviario-brasileiro-movimentou-em-2025-1-4-bi-de-toneladas/).

| Table | Records | Scope |
| --- | --- | --- |
| Navigation totals | 3 | 2025 port throughput, coastal cabotage and Interior navigation category |
| Leading inland cargo | 10 | Labeled cargo categories from report page 22; not all cargo |
| Coastal state endpoints | 22 | Eleven labeled states, origin/destination separately, in thousand TEU |
| Grain regions | 8 | Arco Norte/rest-of-Brazil maize/soybean movements and exports, 2024/2025 |

The preparation uses **labeled figures only**. Unlabeled points on the historical
charts are not estimated from pixel positions. The PDF source hash is
`75a258baeb9267d1cf1c0be8b9353aa31850b950b55197e79b9072e484961e2e`.
The reviewed release HTML bytes have a separate hash; changing navigation/site
markup need not mean the underlying published statistic changed.

Coastal state figures are marginal endpoints, not an origin/destination matrix.
The app does not infer links such as SP–AM from these numbers. Unlabeled states
remain unavailable rather than being filled with zeros. TEU is container capacity,
not tonnes; no density or payload conversion is inferred.

Navigation categories, port handling and exports overlap. Their sum is not a
national unique-shipment total. The Interior category differs from all traffic
that happens to use inland waterways, which can also include other navigation
categories. Grain region aggregates do not describe an operational corridor or
provide a navigable itinerary. Regional comparisons retain source rounding.

Rebuild with `python scripts/prepare_brazil_water.py`; optionally pass
`--source-pdf PATH` to require the exact reviewed edition. Then regenerate modal
indicators with `python scripts/prepare_brazil_modes.py`. The 2025 port total is
kept under a separate indicator from the older ONTL series, whose historical
rounding/revisions differ. Raw ANTAQ downloads remain outside the hosted image.

The generic five-mode snapshot includes three additional 2025 water indicators,
bringing it to 122 annual records. The detailed 43-row table is separately available
in the dashboard, CSV export and `GET /api/brazil/water-freight`, filtered by dataset,
reference year and direction. Reader checks enforce hashes, units, populations,
direction, year coverage and duplicate keys; invalid/missing bundles return 503.

This closes the absence of inland/coastal reference analyses, not complete raw
waterway-flow coverage. Monthly records, paired OD flows and fuller corridor
detail remain future work. The legacy ANTAQ download page returned 502 during
source discovery; the reviewed official report remains reproducible independently.
