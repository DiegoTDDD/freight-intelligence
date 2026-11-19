# Observed cabotage origin–destination transport

The public snapshot contains **510 reported links, all 98 origins and 71
destinations** in the reviewed 2025 [ANTAQ cabotage table](https://aquarela.antaq.gov.br/single/?appid=56c32604-37bd-4993-9904-1b2c87706808&sheet=bgvJm&opt=currsel%2Cctxmenu).
It replaces the initial three-origin sample. Ports, terminals, offshore basins,
platforms and undetermined source categories are retained under their original
names. These points do not all represent ports.

Each original XLSX was generated from **GR4.2 - Porto/UF Destino** with exactly
one `Origem Nome` selected, `Carga.NRAno=2025`, all months, `DadosEscala=1`,
`FlagCabotagem=1`, and no destination or cargo filters. The original unfiltered
origin and destination tables were independently exported for reconciliation.
Capture: 19 November 2026; panel edition: 1 April 2026, 08:17. This is a reviewed
edition, not live traffic or a claim about every Brazilian water-navigation mode.

## Reconciliation and examples

| Check | Reviewed result |
| --- | --- |
| Individual single-origin destination exports | 98 |
| Unique reported source origin points | 98 |
| Unique reported source destination points | 71 |
| Observed origin/destination links | 510 |
| Sum of unrounded original XLSX values | 222,975,436.378 tonnes |
| Whole-tonne headline in the source panel | 222,975,436 tonnes |
| Difference from headline | +0.378 tonnes, retained as display precision |

Every origin subtotal reconciles to the independent unfiltered origin export.
Every destination subtotal also reconciles to the independent unfiltered
destination export, within **0.000001 tonne**. No difference is allocated to an
invented flow. Source numeric precision, including floating-point representation,
is retained; display rounding is not a new observation.

Examples preserved from the first reviewed exports:

| Source origin | Reported destination links | Transport tonnes |
| --- | --- | --- |
| Santos | 30 | 8,790,074.053 |
| Suape | 34 | 6,531,260.247 |
| Manaus | 13 | 2,687,002.543 |

Santos → Suape is **991,103.005 tonnes** in the original export. The largest
origin category, **Bacia Sedimentar de Santos**, remains an offshore basin, not
the port of Santos. `Terminais Interiores` and `Não Identificado` remain source
categories; neither is converted to a guessed location.

These are paired volumes because every destination export is conditioned on a
single actual source origin. No links are inferred from separate marginal totals,
and regional percentages are not multiplied by an unrelated handling population.
The independent margins are used only to validate the reconstructed OD matrix.

Coverage is complete **for this reviewed cabotage table**, not all national
waterway movements or unique cargo. A shipment may appear in multiple transport
events. Unlisted links are unavailable, not fabricated zero flows. Source point
names do not provide coordinates, navigable geometry, sailing distance or clearance.

The 222.975436 million tonnes here measure **cabotage transport** in
`Quantidade Transportada`. They are not the annual report's rounded 303.7 million
tonnes of cabotage handling. Handling events and transport populations differ;
neither total is substituted for the other or added to national port handling.

## Download and reproduce

- [All 510 pairs, CSV](../deployment/brazil_water/port_pairs.csv)
- [Source/filter manifest and every original/context hash](../deployment/brazil_water/port_pairs_provenance.json)
- [Reviewed contract, per-origin totals and independent destination margins](../deployment/brazil_water/port_pairs_contract.json)
- [All source origins, original XLSX](../deployment/brazil_water/port_pairs_all_origins_2025.xlsx), [filter context](../deployment/brazil_water/port_pairs_all_origins_2025_context.jpg)
- [All source destinations, original XLSX](../deployment/brazil_water/port_pairs_all_destinations_2025.xlsx), [filter context](../deployment/brazil_water/port_pairs_all_destinations_2025_context.jpg)
- Santos: [original XLSX](../deployment/brazil_water/port_pairs_santos_2025.xlsx), [filter context](../deployment/brazil_water/port_pairs_santos_2025_context.jpg)
- Suape: [original XLSX](../deployment/brazil_water/port_pairs_suape_2025.xlsx), [filter context](../deployment/brazil_water/port_pairs_suape_2025_context.jpg)
- Manaus: [original XLSX](../deployment/brazil_water/port_pairs_manaus_2025.xlsx), [filter context](../deployment/brazil_water/port_pairs_manaus_2025_context.jpg)

All 98 original single-origin workbooks and their corresponding screenshots
are versioned in the same directory. Exact filenames for every point are listed
in the contract and manifest. The workbooks contain destination names/states and
numeric quantities; the separately archived UI context establishes origin/year.

The contract has a reviewed SHA-256 pinned in code. It pins every original export,
every context capture, both independent catalogue exports and the exact derived
CSV. Missing/modified evidence, changed periods, duplicate links, invalid values,
wrong populations and reconciliation differences fail validation. A bounded
read-only cache is invalidated by changes to any evidence file.

Rebuild offline: `python -m scripts.prepare_brazil_water_ports`.
Regenerate the static report: `python scripts/build_portfolio_evidence.py`.
Serving this view requires neither network access nor the full FAF pipeline.

## UI and API

Select **Brazilian freight → All five modes → Water → Cabotage origin–destination
tonnes (2025 · 98 origins)**. Choose a source origin or **All reported origins**,
then optionally a destination. The chart shows up to 20 destination subtotals;
the table and downloadable CSV retain every filtered link. English is the default;
Portuguese is available.

`GET /api/brazil/water-port-pairs?origin_port=Santos&destination_port=Suape`
returns the observed pair. The existing `origin_port`/`destination_port` filter
and column names are preserved for compatibility; values also include terminals,
offshore and undetermined categories. They do not certify a physical port.

`year` accepts 2025 only. `limit` defaults to 100 (maximum 500), and `offset`
starts at zero. `total` and `filtered_tonnes` describe the complete filtered
population before pagination; `count` describes the returned page. Unknown
exact names return no reported rows. Invalid/missing evidence returns 503.
Authenticated mode requires the analytics role; only public source data is served.
