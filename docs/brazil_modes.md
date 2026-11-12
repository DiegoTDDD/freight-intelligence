# Brazilian multimodal indicators

The five-mode view covers road, rail, water, air and pipelines with **130 scoped
annual indicator records**. It complements the detailed railway workspace.
Coverage is deliberately heterogeneous:

| Mode | Indicators | Period | Important boundary |
| --- | --- | --- | --- |
| Road | Registered truck fleet | 2010–2024 | Vehicle stock; not cargo volume or active capacity |
| Rail | Net tonnes and tonne-kilometres | 2006–2025 | ANTT federal concessions; repeated cargo movements possible |
| Water | Port cargo throughput | 2010–2024 | Port handling, not unique shipments or complete inland transport work |
| Air | Domestic and international paid cargo | 2010–2024 | ANAC paid cargo; international is linked to Brazil |
| Pipeline | Daily gas average; oil/product volume | 2010–2024 | Gas source attribution caveat; oil series covers Transpetro, not all operators/mineral pipelines |

This provides indicators for all five modes, **not full national cargo-flow
coverage for every mode**. Units cannot be added or used to derive modal shares.
Charts keep their published rounding. No synthetic values or projections are
inserted into the observed series.

## Sources and reproducibility

The principal source is the official Infra S.A./ONTL
[Diagnóstico Logístico 2010–2024](https://ontl.infrasa.gov.br/wp-content/uploads/2025/10/Diagnostico-logistico-2010-2024.pdf),
pages 40, 78, 110, 120 and 123. Chart labels were transcribed and reviewed;
this is a curated snapshot, not an automatic live data feed. The exact reviewed
PDF SHA-256 is pinned in the preparation script and provenance. Rail records
come from the existing verified ANTT snapshot, whose input hash is also retained.

Rebuild with `python scripts/prepare_brazil_modes.py`. To additionally verify
the downloaded edition, provide `--source-pdf PATH`; a changed PDF is rejected
until its figures are reviewed. The generated CSV has deterministic ordering
and LF bytes, and its manifest hash is checked by both UI and API readers.
The recovery package verifies these additional data files too.

## Unresolved source quality issues

The [ANTT TRC 2025 yearbook](https://www.gov.br/antt/pt-br/assuntos/cargas/dadostrc/anuario_trc_2025_antt.pdf)
cites approximately 1.4 billion tonnes on printed page 53 and 1.165 billion on
page 56. Its published scopes must be reconciled before promoting one number as
the national road cargo total. The interface includes this issue rather than
silently choosing a value. Road freight tonnage coverage remains incomplete.

The gas narrative attributes the series to ANP, while chart 69 attributes it to
MME. We retain the chart's attribution and disclose the discrepancy. The oil
series is explicitly operator-scoped. The source's prose growth-rate calculations
are not imported; charts display the underlying published values only.

The public API exposes `GET /api/brazil/indicators`, with mode and year filters,
source references, interpretation and quality notes. Missing/corrupt snapshots
return HTTP 503; invalid filters return 422.
