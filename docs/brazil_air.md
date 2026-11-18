# ANAC airport and stage freight

This snapshot comes from the [official ANAC statistical CSV](https://sistemas.anac.gov.br/dadosabertos/Voos%20e%20opera%C3%A7%C3%B5es%20a%C3%A9reas/Dados%20Estat%C3%ADsticos%20do%20Transporte%20A%C3%A9reo/Dados_Estatisticos.csv)
and its [data dictionary](https://www.anac.gov.br/acesso-a-informacao/dados-abertos/areas-de-atuacao/voos-e-operacoes-aereas/dados-estatisticos-do-transporte-aereo/48-dados-estatisticos-do-transporte-aereo).
The reviewed edition was retrieved on 2026-11-13, contains 1,102,983 source rows,
and has SHA-256 `54986d51004d8a0cb326d0898492d8576486cb041bbd0819331092755a7b6480`.
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

Paid-cargo observed subtotals use 2010–2025. Training begins with eight years;
validation through 2022 selects persistence, linear or CAGR baselines. The years
2023–2025 are reserved for the final test. Selected models are then refit to all
observations for point forecasts in 2026–2028. The selected linear models have
reserved-test WAPE of about 21.96% domestically and 7.32% internationally. These are
measured errors, not future guarantees. The forecasts retain the partial observed
population and do not estimate missing cargo or complete national demand.

The report is pinned to its annual input; changing the annual data without
rebuilding its evaluation fails validation. No forecast is trained in an HTTP request.

## Use and rebuild

In the dashboard: **Brazilian freight → All five modes → air**. Choose monthly
history, airport pairs, airport rankings or forecast evaluation. English remains
the default; visible controls and core notices also support Portuguese. Downloads
retain original column identifiers so downstream consumers are stable.

`GET /api/brazil/air-freight` supports `view=monthly|annual|pairs|airports|forecast|scores`,
`year`, `month`, `nature`, and pair-only `origin`/`destination` source airport codes.
Responses are paginated (`limit` up to 1000, `offset`), with population/source metadata.
Inapplicable filters return 422; missing or inconsistent snapshots return 503.
Existing analytics permissions apply. Pair queries before 2024 correctly return
no rows, without inventing an airport history.

Rebuild with `python -m scripts.prepare_brazil_air --source ARCHIVED_CSV --retrieved-at YYYY-MM-DD`.
The generator does not download the source or run the large FAF pipeline.
