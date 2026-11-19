# Observed port-to-port cabotage transport

The public view includes **77 reported destination pairs from three origins**
in 2025, from the [official ANTAQ cabotage table](https://aquarela.antaq.gov.br/single/?appid=56c32604-37bd-4993-9904-1b2c87706808&sheet=bgvJm&opt=currsel%2Cctxmenu).
Each export was generated from **GR4.2 - Porto/UF Destino** with exactly one
`Origem Nome` selected, `Carga.NRAno=2025`, all twelve months, `DadosEscala=1`,
`FlagCabotagem=1`, and no destination or cargo filters. Capture: 19 November 2026;
panel edition: 1 April 2026, 08:17. This is a reviewed snapshot, not live traffic.

| Origin | State | Reported destination pairs | XLSX tonnes | Displayed whole tonnes |
| --- | --- | --- | --- | --- |
| Santos | SP | 30 | 8,790,074.053 | 8,790,074 |
| Suape | PE | 34 | 6,531,260.247 | 6,531,260 |
| Manaus | AM | 13 | 2,687,002.543 | 2,687,003 |

This method yields actual conditioned origin/destination volumes. It does not
combine marginal totals or multiply regional shares by an unrelated population.
For example, Santos → Suape is 991,103.005 tonnes in the original export.
Unrounded spreadsheet numbers are retained, including ordinary floating-point
representation; each subtotal reconciles within 0.000001 t and rounds to the
archived headline. No rounding difference is allocated to an invented flow.

Coverage is deliberately limited to the three reviewed origins. Other origins
and unlisted links are unavailable, not zero. A shipment may appear in more than
one transport event; the subtotals are not unique national cargo. A port name
does not supply coordinates, a shipping lane, sailing distance or navigational
clearance. Offshore/terminal names in the original destination data stay intact.

## Download and reproduce

- [All 77 pairs, CSV](../deployment/brazil_water/port_pairs.csv)
- [Source/filter manifest and SHA-256 hashes](../deployment/brazil_water/port_pairs_provenance.json)
- Santos: [original XLSX](../deployment/brazil_water/port_pairs_santos_2025.xlsx), [selected filters and table](../deployment/brazil_water/port_pairs_santos_2025_context.jpg)
- Suape: [original XLSX](../deployment/brazil_water/port_pairs_suape_2025.xlsx), [selected filters and table](../deployment/brazil_water/port_pairs_suape_2025_context.jpg)
- Manaus: [original XLSX](../deployment/brazil_water/port_pairs_manaus_2025.xlsx), [selected filters and table](../deployment/brazil_water/port_pairs_manaus_2025_context.jpg)

The workbooks contain destination names/states and numeric transport quantities;
the origin and period are established by the separately archived UI context.
Both original files and context captures have pinned, reviewed hashes in code.
The reader rejects modified evidence, changed periods, duplicate pairs, invalid
values, or totals/coverage that differ from the reviewed contract.

Rebuild offline: `python -m scripts.prepare_brazil_water_ports`.
Then regenerate `python scripts/build_portfolio_evidence.py`.
No network, retraining or full FAF ingestion is needed to serve this view.

## UI and API

Select **Brazilian freight → All five modes → Water → Port-to-port cabotage
tonnes (2025 · three origins)**. Select an origin, optionally a destination,
and download the filtered CSV. English is the default; Portuguese is available.

`GET /api/brazil/water-port-pairs?origin_port=Santos&destination_port=Suape`
returns the reported pair. `year` accepts 2025 only. Pagination uses `limit`
(default 100, maximum 500) and `offset`. `total` and `filtered_tonnes` describe
the full filtered result before pagination; `count` describes the returned page.
Unknown exact names return no reported records. Invalid/missing source bundles
return 503. The route requires the analytics role when authentication is enabled,
and contains public source data only.
