# Brazilian multimodal indicators

The five-mode view covers road, rail, water, air and pipelines with **119 scoped
annual indicator records**. It complements the detailed railway workspace.
Coverage is deliberately heterogeneous:

| Mode | Indicators | Period | Important boundary |
| --- | --- | --- | --- |
| Road | Registered truck fleet; MDF-e cargo trips and derived transport work | Fleet 2010–2024; operations 2025 | Excludes within-city trips; no reconciled national cargo tonnage |
| Rail | Net tonnes and tonne-kilometres | 2006–2025 | ANTT federal concessions; repeated cargo movements possible |
| Water | Port cargo throughput | 2010–2024 | Port handling, not unique shipments or complete inland transport work |
| Air | Domestic and international paid cargo | 2010–2024 | ANAC paid cargo; international is linked to Brazil |
| Pipeline | ANP gas receipt/delivery subtotals; Transpetro oil/product volume | Gas 2025; oil 2010–2024 | Gas missing cells and inter-operator transfers disclosed; oil excludes other operators/mineral pipelines |

This provides indicators for all five modes, **not full national cargo-flow
coverage for every mode**. Units cannot be added or used to derive modal shares.
Charts keep their published rounding. No synthetic values or projections are
inserted into the observed series.

## Sources and reproducibility

The principal source is the official Infra S.A./ONTL
[Diagnóstico Logístico 2010–2024](https://ontl.infrasa.gov.br/wp-content/uploads/2025/10/Diagnostico-logistico-2010-2024.pdf),
pages 40, 78, 110 and 123. Chart labels were transcribed and reviewed;
this is a curated snapshot, not an automatic live data feed. The exact reviewed
PDF SHA-256 is pinned in the preparation script and provenance. Rail records
come from the existing verified ANTT snapshot, whose input hash is also retained.
The ANTT TRC 2025 yearbook (physical PDF page 61, printed page 53) separately
reports 80.4 million MDF-e cargo trips and 749.4 billion tonne-kilometres. These
rounded indicators are curated separately, with transport work marked as derived
from source distance estimation. The official PDF was reviewed, but automated
raw download returned HTTP 403; its source-file hash is not claimed.

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

The former ONTL gas series is **excluded**, not merely footnoted. Its 2024 value
of 153.1 million m³/day is identified as national gas production in the official
[EPE BEN 2025](https://www.epe.gov.br/sites-pt/publicacoes-dados-abertos/publicacoes/PublicacoesArquivos/publicacao-885/topico-771/Relat%C3%B3rio%20Final_BEN%202025.pdf),
printed page 16. Production is not evidence of pipeline throughput. The excluded
indicator remains identifiable in provenance and Git history, but is no longer
returned by the analytical API.

It is replaced by the twelve official ANP gas movement CSVs for 2025: 120 monthly
operator/direction aggregates across GOM, NTS, TAG, TBG and TSB. Source hashes,
calendar validation and observed/missing counts are preserved. Receipt and
delivery subtotals are separate: the same gas can cross multiple operators.
There are 31 missing receipt cells and 2 missing delivery cells; none are filled
with zero. 118 signed negative source cells are retained and counted, not clipped.
Annual observed subtotals are 33,538.538272 million m³ received and 32,054.468279
million m³ delivered; neither is unique national supply or a reconciled balance.

Rebuild the gas snapshot first with `python scripts/prepare_brazil_gas.py`
(bounded monthly downloads, raw files cached outside the published snapshot),
then `python scripts/prepare_brazil_modes.py`. The gas detail and CSV download
appear in the pipeline mode view. The API endpoint is
`GET /api/brazil/gas-movements`, with month, point type and operator-id filters.
The reduction from 132 to 119 annual records reflects removal of 15 ambiguous
gas values and addition of two explicitly scoped ANP subtotals, not loss of the
new 120 monthly movement records.

The oil series remains explicitly operator-scoped. The source's prose growth-rate
calculations are not imported; charts display the underlying published values only.

The public API exposes `GET /api/brazil/indicators`, with mode and year filters,
source references, interpretation and quality notes. Missing/corrupt snapshots
return HTTP 503; invalid filters return 422.
