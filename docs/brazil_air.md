# ANAC airport and stage freight

This snapshot comes from the [official ANAC statistical CSV](https://sistemas.anac.gov.br/dadosabertos/Voos%20e%20opera%C3%A7%C3%B5es%20a%C3%A9reas/Dados%20Estat%C3%ADsticos%20do%20Transporte%20A%C3%A9reo/Dados_Estatisticos.csv)
and its [data dictionary](https://www.anac.gov.br/acesso-a-informacao/dados-abertos/areas-de-atuacao/voos-e-operacoes-aereas/dados-estatisticos-do-transporte-aereo/48-dados-estatisticos-do-transporte-aereo).
The original reviewed edition was retrieved on 2026-11-13, contains 1,102,983 source
rows, and had SHA-256 `54986d51004d8a0cb326d0898492d8576486cb041bbd0819331092755a7b6480`.
On 2026-11-20 a bounded source audit detected a changed update-date line. A complete
body-hash comparison with that exact original CSV proved the row/header body was
identical. The reviewed current source hash is
`d8b5e856ce56a355727132e8e0868766c8f16d539d817cb240f20390c7bf7730`;
only source date/hash provenance was updated. All aggregate and forecast bytes
remained unchanged during that source review. The subsequent forecast expansion
below preserves aggregate bytes and the original paid-cargo results. [Source review evidence](evidence/anac_source_review_20261120.json)
and [scheduled audit contract](source_refresh.md) document the distinction.
The 361 MB raw source is kept locally, outside the hosted image and repository.

## Published scope

- 624 monthly aggregates and 52 annual aggregates: 2000–2025, domestic and international.
- 36,860 monthly airport-pair aggregates: 2024–2025.
- 1,102 airport reference codes/names, preserved as reported rather than inferred geocodes.
- Paid cargo, free cargo and mail remain separate, in kilograms. Baggage is excluded.

Only source records with at least one Brazilian endpoint are included. All reported
flight groups are retained. Foreign-to-foreign stages and 2026's incomplete year
are excluded and counted. Airport-pair stages can repeat cargo across legs; they
are not unique consignments, passenger itineraries or bookable routes. Source
fields that are absent are counted and excluded from sums, never silently treated
as reported zeroes. Airport origin and destination rankings overlap.

The detailed source supersedes the older rounded ONTL air references in the
five-mode atlas. New indicator names explicitly identify observed stage subtotals;
the old names remain listed in excluded-series metadata. Different source editions
and the Brazilian-endpoint filter must not be confused with measurement errors.

## Forecast evaluation

Six separate targets use 2010–2025: paid cargo, free cargo and mail, each split
by domestic/international stages. All remain observed **kilogram subtotals**,
with absent source values excluded and counted. This expands X07 with four named
additional targets; it does not turn missing fields into complete national demand.
Training begins with eight years; expanding validation through 2022 selects
persistence, linear or CAGR by MAE. The 2023–2025 reserved test is predicted from
a single 2022 origin, without reselection or refitting on those three years.
Only after scoring is each chosen model refit for 2026–2028 point forecasts.

| Additional target | Validation-selected model | Reserved-test WAPE | Competing test results |
| --- | --- | --- | --- |
| Domestic free cargo | Persistence | 31.35% | Linear 11.85%; CAGR 35.66% |
| International free cargo | Persistence | 28.41% | Linear 6.94%; CAGR 19.52% |
| Domestic mail | CAGR | 18.67% | Persistence 21.31%; linear 24.38% |
| International mail | Persistence | 26.60% | Linear 18.16%; CAGR 32.67% |

Three of the four selected models lose to another candidate on the final test.
That result remains visible; test results never choose a replacement model.
Previous paid-cargo results are exactly preserved: selected linear test WAPE
21.96% domestically and 7.32% internationally, both worse than persistence.
These are measured historical errors, not future guarantees. Point forecasts
have no prediction intervals. See [every candidate score](portfolio_evidence.md)
and [machine-readable evaluation evidence](evidence/anac_additional_forecasts_20261120.json).

The report is pinned to its annual input; changing the annual data without
rebuilding its evaluation fails validation. No forecast is trained in an HTTP request.

## Use and rebuild

In the dashboard: **Brazilian freight → All five modes → air**. Choose monthly
history, airport pairs, airport rankings or forecast evaluation. English remains
the default; visible controls and core notices also support Portuguese. Downloads
retain original column identifiers so downstream consumers are stable.

`GET /api/brazil/air-freight` supports `view=monthly|annual|pairs|airports|forecast|scores|predictions`,
`year`, `month`, `nature`, and pair-only `origin`/`destination` source airport codes.
Responses are paginated (`limit` up to 1000, `offset`), with population/source metadata.
Inapplicable filters return 422; missing or inconsistent snapshots return 503.
Existing analytics permissions apply. Pair queries before 2024 correctly return
no rows, without inventing an airport history.

Rebuild with `python -m scripts.prepare_brazil_air --source ARCHIVED_CSV --retrieved-at YYYY-MM-DD`.
The generator does not download the source or run the large FAF pipeline.

Forecast, scores and predictions accept `measure=paid_cargo_kg|free_cargo_kg|mail_kg`.
The default remains paid cargo for existing API clients. Scores/predictions also
accept `phase=validation|test`; incompatible filters return 422. For example:

```text
GET /api/brazil/air-freight?view=scores&measure=mail_kg&nature=domestic&phase=test
GET /api/brazil/air-freight?view=predictions&measure=free_cargo_kg&nature=international&phase=test
```

Rebuild only the small report in a **new** staging directory:

```bash
python -m scripts.prepare_brazil_air_forecasts --output work/anac-evaluation-review
```

This reads validated committed aggregates, preserves the original source retrieval
date, compares all six targets and validates the staged bundle. It does not
redownload ANAC, rerun raw ingestion, replace serving files or run FAF. A reviewed
forecast ZIP/provenance change is published through the normal CI gate. Units,
source observations, reserved-test boundaries, model flags and numeric outputs
are checked on load; HTTP requests do not train models.
