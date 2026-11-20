# Portfolio evidence without a running server

This report is generated from the repository's hash-checked public snapshots.
It can be read on GitHub or from a local clone while the interactive demo sleeps
or is unavailable. It does not contact Render, download raw sources, train models,
run the solver or execute the large FAF pipeline.

Rebuild: `python scripts/build_portfolio_evidence.py`
Check for drift: `python scripts/build_portfolio_evidence.py --check`

## Bundled coverage

| Public snapshot | Records | Scope |
| --- | --- | --- |
| Five-mode annual atlas | 145 | Separately scoped indicators; incompatible units are not summed |
| ANAC monthly history | 624 | 2000–2025; domestic/international; Brazil-linked stages |
| ANAC monthly airport pairs | 36860 | 2024–2025; reported stages, not unique consignments |
| ANAC airport source codes | 1102 | Reference codes present in the selected pair population |
| ANP gas operator/direction/month | 600 | 2021–2025; coverage changes; not unique national supply |
| ANTAQ references and monthly rows | 55 | 43 annual/regional references plus twelve 2025 port-handling months |
| ANTAQ original monthly port handling | 62 | January 2021–February 2026; five complete years and two partial-year months |
| ANTAQ inland-waterway transport months | 62 | 2021–February 2026; original total and three navigation components, separate from handling |
| ANTAQ inland cargo categories | 117 | 2025; 109 numeric quantities including 46 zeros; eight source dashes remain null |
| ANTAQ paired regional cabotage shares | 21 | 2025 original region-to-region fractions; offshore and undetermined origins retained |
| ANTAQ port-to-port cabotage volumes | 510 | 2025; all 98 reviewed origins and 71 destinations; original numeric tonnes |
| ANTT archived yearbook monthly totals | 12 | 2025 published Chart 45 labels |
| ANTT panel monthly account-category observations | 56 | 28 months, July 2024–October 2026; N/S separated; 2024 and 2026 partial |
| ANTT regional road pairs | 16 | 16 published RGI pairs; not municipalities or truck itineraries |
| ANTT state road pairs | 775 | 2025; 28 origin/destination categories including EX; both independent margins reconcile |

The full local FAF run previously produced 2,503,352 Bronze and 97,630,728 Silver
rows. Those raw/large layers are not checked into Git. The compact public demo
aggregates are versioned in [deployment](../deployment/), with manifests and hashes.

## ANAC observed cargo subtotals

| Year | Nature | Paid cargo (kg) | Free cargo (kg) | Mail (kg) | Missing paid-cargo fields |
| --- | --- | --- | --- | --- | --- |
| 2025 | domestic | 431,833,387 | 8,024,379 | 34,353,463 | 88 |
| 2025 | international | 872,045,868 | 3,363,366 | 9,776,955 | 32 |

Paid cargo, free cargo and mail remain separate. Missing source fields are
excluded from sums and counted, never invented as observed zero cargo. One
consignment can appear on more than one stage. See [scope and sources](brazil_air.md).

## Forecast results, including competing baselines

Training/model selection uses validation through 2022; 2023–2025 are reserved
for the final test. The table includes every candidate, not only the selected one.

| Observed subtotal | Baseline | Selected on validation | Test WAPE |
| --- | --- | --- | --- |
| domestic_free_observed_subtotal | cagr | No | 35.66% |
| domestic_free_observed_subtotal | linear | No | 11.85% |
| domestic_free_observed_subtotal | persistence | Yes | 31.35% |
| domestic_mail_observed_subtotal | cagr | Yes | 18.67% |
| domestic_mail_observed_subtotal | linear | No | 24.38% |
| domestic_mail_observed_subtotal | persistence | No | 21.31% |
| domestic_paid_observed_subtotal | cagr | No | 12.50% |
| domestic_paid_observed_subtotal | linear | Yes | 21.96% |
| domestic_paid_observed_subtotal | persistence | No | 11.61% |
| international_free_observed_subtotal | cagr | No | 19.52% |
| international_free_observed_subtotal | linear | No | 6.94% |
| international_free_observed_subtotal | persistence | Yes | 28.41% |
| international_mail_observed_subtotal | cagr | No | 32.67% |
| international_mail_observed_subtotal | linear | No | 18.16% |
| international_mail_observed_subtotal | persistence | Yes | 26.60% |
| international_paid_observed_subtotal | cagr | No | 6.61% |
| international_paid_observed_subtotal | linear | Yes | 7.32% |
| international_paid_observed_subtotal | persistence | No | 3.79% |

The two paid-cargo validation-selected models have worse reserved-test errors than
persistence. The four additional free-cargo/mail targets retain every competing score. This is a disclosed result, not a reason to select again on test
data. Future forecasts are point estimates without accuracy guarantees.
The [portable report ZIP](../deployment/brazil_air/forecast.zip) contains scores,
predictions, forecasts and source/split metadata.

The independent [ANTT railway evaluation](brasil.md) covers 2006–2025;
validation-selected reserved-test WAPE is 4.75% TU and 1.61% TKU. Railway,
airport-stage and FAF scenario populations must not be treated as equivalent.

## Port and oil-pipeline evaluation with a 2024 observation cutoff

Each series contains fifteen reviewed rounded annual values, 2010–2024.
Validation ends in 2021; 2022–2024 are reserved for test. Port handling uses
million tonnes and Transpetro oil/product movements use million m³ at 20°C.
They are neither added together nor treated as unique national shipments.

| Rounded historical indicator | Baseline | Selected on validation | Test WAPE |
| --- | --- | --- | --- |
| port_throughput | cagr | No | 1.45% |
| port_throughput | linear | Yes | 2.10% |
| port_throughput | persistence | No | 5.74% |
| transpetro_oil_pipeline_movement | cagr | Yes | 16.91% |
| transpetro_oil_pipeline_movement | linear | No | 27.45% |
| transpetro_oil_pipeline_movement | persistence | No | 15.35% |

The validation-selected port model loses to CAGR on the reserved test; the
selected oil model loses to persistence. No choices are changed after seeing
these results. The bundled forecasts for **2025–2027 are vintage estimates from
a 2024 cutoff**, even for calendar years already past. They are not newly
observed data and are not spliced with a newer source edition.
[Method and scope](brazil_modal_forecasts.md) ·
[portable scores, predictions and source observations](../deployment/brazil_modal_forecasts/forecast.zip).

## Monthly port handling

| Month | Displayed port handling (tonnes) |
| --- | --- |
| 2025-01 | 93,028,512 |
| 2025-02 | 97,302,008 |
| 2025-03 | 115,287,326 |
| 2025-04 | 110,124,907 |
| 2025-05 | 120,338,848 |
| 2025-06 | 121,998,232 |
| 2025-07 | 126,842,293 |
| 2025-08 | 134,234,671 |
| 2025-09 | 121,822,158 |
| 2025-10 | 122,459,471 |
| 2025-11 | 119,549,800 |
| 2025-12 | 119,743,606 |

Displayed monthly sum: **1,402,731,832 tonnes**. The panel's annual
headline is **1,402,731,833 tonnes**. The one-tonne display discrepancy is retained,
with no invented allocation to a month. These are handling movements in both
directions, not unique cargo or paired OD routes. The rounded annual report is
a separate edition. See [the source and filters](brazil_water.md) and
[downloadable source-derived table](../deployment/brazil_water/water.csv).

## Paired regional cabotage distribution

| Origin region | Destination region | Share of full panel population |
| --- | --- | --- |
| ZEE/Plat. Continental | Sudeste | 51.213125% |
| ZEE/Plat. Continental | Sul | 7.256645% |
| Norte | Nordeste | 5.071061% |
| Nordeste | Nordeste | 5.059674% |
| Sudeste | Sudeste | 4.933407% |
| ZEE/Plat. Continental | Nordeste | 4.847250% |
| Sudeste | Nordeste | 4.010315% |
| Nordeste | Sudeste | 3.786131% |
| Sudeste | Sul | 2.876315% |
| Sul | Nordeste | 2.005669% |
| Norte | Norte | 1.945592% |
| Nordeste | Norte | 1.705459% |
| Sudeste | Norte | 1.287457% |
| Norte | Sudeste | 1.049922% |
| Sul | Sul | 0.823380% |
| Nordeste | Sul | 0.794430% |
| Sul | Sudeste | 0.649243% |
| Sul | Norte | 0.422194% |
| Norte | Sul | 0.246249% |
| Indeterminado | Sudeste | 0.016438% |
| Indeterminado | Sul | 0.000043% |

These 21 pairs are read directly from the original ANTAQ Sankey export, not
constructed from separate origin/destination totals. Stored fractions reconcile
to one; table percentages are rounded for display. Filtering keeps the original
full-population denominator. They do not identify individual ports or nautical
itineraries and must not be scaled by a different annual/handling total.
The [original XLSX export](../deployment/brazil_water/cabotage_region_pairs_2025.xlsx)
and [unrounded derived CSV](../deployment/brazil_water/coastal_region_pairs.csv)
are versioned with hashes and [reviewed filter/period context](brazil_water.md#paired-regional-cabotage-shares).

## Port-to-port cabotage volumes

| Reviewed origin | Reported destination pairs | Transport tonnes |
| --- | --- | --- |
| A.D.S. Reparos Navais | 1 | 8,183.984 |
| Altamira | 1 | 4.500 |
| Angra dos Reis | 3 | 216,532.933 |
| Aratu | 15 | 2,216,973.276 |
| Areia Branca | 5 | 702,407.500 |
| Bacia Sedimentar Pernambuco-Paraíba | 2 | 35,913.220 |
| Bacia Sedimentar SEAL | 1 | 7,933.415 |
| Bacia Sedimentar de Camamu-Almada | 1 | 13,269.740 |
| Bacia Sedimentar de Campos | 8 | 29,909,502.293 |
| Bacia Sedimentar de Santos | 8 | 100,690,052.897 |
| Barra do Riacho | 3 | 54,782.243 |
| Belém | 4 | 113,826.665 |
| Brasbunker | 1 | 4,999.782 |
| Brasil Logística Offshore e Estaleiro Naval | 1 | 6,223.558 |
| Cabedelo | 5 | 160,302.192 |
| Cachoeira do Sul | 1 | 7,284.637 |
| Cattalini Terminais Marítimos | 1 | 4,964.846 |
| Coari | 3 | 49,011.545 |
| Estaleiro Atlântico Sul - EAS | 1 | 14,539.693 |
| Estaleiro Renave | 1 | 1,811.517 |
| FPSO Brasil | 2 | 18,048.906 |
| FPSO Cidade de Angra dos Reis | 1 | 155,029.326 |
| FPSO Cidade de Ilha Bela | 1 | 135,612.016 |
| FPSO Cidade de Itaguaí | 1 | 1,722,236.455 |
| FPSO Cidade de Mangaratiba | 1 | 1,761,263.221 |
| FPSO Cidade de Maricá | 1 | 1,494,278.034 |
| FPSO Cidade de Paraty | 1 | 760,913.178 |
| FPSO Cidade de Sao Paulo | 1 | 635,769.780 |
| FPSO Cidade de Saquarema | 1 | 1,056,514.725 |
| FPSO Espírito Santo | 6 | 4,020,515.797 |
| FPSO Frade | 1 | 5.100 |
| FPSO PIONEIRO DE LIBRA | 1 | 486,779.395 |
| Fortaleza | 17 | 925,961.280 |
| IP4 Itacoatiara | 2 | 4,525.478 |
| Imbituba | 12 | 790,373.157 |
| Itaguaí | 13 | 804,816.933 |
| Itajaí | 14 | 1,026,822.794 |
| Itaqui | 12 | 1,891,925.057 |
| Maceió | 10 | 1,881,512.173 |
| Manaus | 13 | 2,687,002.543 |
| Natal | 1 | 60,047.765 |
| Niterói | 3 | 3,230.165 |
| Não Identificado | 1 | 96.000 |
| Paranaguá | 19 | 1,430,473.721 |
| Pelotas | 1 | 11,340.413 |
| Porto Alegre | 1 | 8,889.391 |
| Porto Chibatão | 4 | 636,622.095 |
| Porto Engenheiro Zephyrino Lavanère Machado Filho | 1 | 641.508 |
| Porto Itapoá Terminais Portuários | 13 | 1,698,805.886 |
| Porto Sudeste do Brasil S/A | 1 | 41,310.685 |
| Porto de Santo Antônio (IP4 Fernando de Noronha) | 1 | 3,569.410 |
| Porto do Açu - Terminal TMULT e TCAR | 4 | 13,440.874 |
| Porto do Açu - Terminal de Minério | 1 | 5,461.432 |
| Portocel - Terminal Especializado de Barra do Riacho | 1 | 126.000 |
| Portonave - Terminais Portuários de Navegantes | 10 | 1,014,770.479 |
| Recife | 4 | 31,706.744 |
| Rio Grande | 18 | 1,918,645.664 |
| Rio de Janeiro | 31 | 6,236,692.922 |
| Salinas (Rio Grande do Norte) | 1 | 6,000.000 |
| Salvador | 21 | 1,570,957.583 |
| Santos | 30 | 8,790,074.053 |
| Suape | 34 | 6,531,260.247 |
| São Francisco do Sul | 4 | 372,516.296 |
| São Sebastião | 10 | 1,822,180.659 |
| TUP ALISEO | 2 | 2,114.100 |
| TUP TMB - Terminal Marítimo de Belmonte | 1 | 1,090,628.000 |
| TUP da Salina Guanabara | 1 | 226,072.300 |
| Teporti | 1 | 21,749.360 |
| Terminais Fluviais do Brasil | 1 | 232.780 |
| Terminais Interiores | 2 | 36,652.705 |
| Terminal Aquaviário da Ilha Comprida | 2 | 96,097.358 |
| Terminal Aquaviário da Ilha D'Água | 5 | 632,911.292 |
| Terminal Aquaviário de Angra dos Reis | 1 | 1,003,950.580 |
| Terminal Aquaviário de Aracaju | 1 | 19,894.740 |
| Terminal Aquaviário de Barra do Riacho | 1 | 1,883.059 |
| Terminal Aquaviário de Guamaré | 3 | 87,477.552 |
| Terminal Aquaviário de Ilha Redonda e Terminal Aquaviário da Ilha Comprida | 2 | 10,203.619 |
| Terminal Aquaviário de Madre de Deus | 8 | 395,831.503 |
| Terminal Aquaviário de Manaus | 4 | 201,264.742 |
| Terminal Aquaviário de Osório | 5 | 389,641.317 |
| Terminal Aquaviário de São Sebastião (Almirante Barroso) | 8 | 669,230.280 |
| Terminal Fluvial de Juruti | 1 | 7,160,305.000 |
| Terminal Hidroviário Cimbagé | 1 | 848.900 |
| Terminal Marítimo Dow | 1 | 13,316.274 |
| Terminal Marítimo Inácio Barbosa - TMIB | 1 | 275,077.224 |
| Terminal Marítimo de Ponta da Madeira | 2 | 3,236,892.686 |
| Terminal Portuário Privativo da Alumar | 5 | 62,935.202 |
| Terminal Portuário de São Luis | 1 | 138,377.790 |
| Terminal Portuário do Pecém | 18 | 2,529,409.823 |
| Terminal Trombetas | 2 | 6,936,233.310 |
| Terminal de Embarque Marítimo da Salina Diamante Branco | 1 | 241,404.600 |
| Terminal de Praia Mole | 2 | 52,559.587 |
| Terminal de Regaseificação de GNL da Bahia - TRBA | 1 | 17,848.047 |
| Terminal de Tubarão | 1 | 34,098.407 |
| Terminal de Uso Privado de Macau | 1 | 591,674.300 |
| Tup da Salina Francisco Menescal | 1 | 387,425.900 |
| Vila do Conde | 10 | 746,526.525 |
| Vitória | 21 | 6,977,381.740 |

These **510 observed pairs** come from 98 separate original destination-table
exports, each with exactly one origin selected and the full 2025 calendar.
The XLSX retains fractional tonnes; every origin subtotal rounds to the
whole-tonne headline in the archived filter context. Both origin and destination margins reconcile the population. This is complete origin
coverage for the reviewed cabotage table, not unique cargo or a navigable itinerary. Unlisted pairs are
unavailable, not zero. [Full CSV and original evidence](brazil_water_ports.md).

## Road movement history from a separately reviewed panel edition

| Year | Observed months | Full calendar year | N: non-own-account tonnes | S: own-account tonnes | Observed total tonnes | MDF-e documents |
| --- | --- | --- | --- | --- | --- | --- |
| 2024 | 6 | No | 591,729,835 | 103,289,674 | 695,019,509 | 44,573,360 |
| 2025 | 12 | Yes | 1,164,978,181 | 203,649,523 | 1,368,627,704 | 90,060,010 |
| 2026 | 10 | No | 1,099,010,747 | 191,491,774 | 1,290,502,521 | 84,223,450 |

The 28 observed months cover July 2024–October 2026. 2024 and 2026 subtotals
are **not annual totals**; missing months are not zero-filled or extrapolated.
These are published integer display values read through the official panel's
**Show as table** interface. MDF-e document counts do not identify unique trips
or consignments. All source geographic categories remain included.

The 2025 panel sum is **1,368,627,704 tonnes**, which is **71,947 tonnes lower**
than the archived yearbook sum. Both editions are preserved; a cause for their
difference is not invented. The N subtotal of **1,164,978,181 tonnes** rounds to
the yearbook's 1.165-billion regional reference, but numerical agreement alone
does not prove identical populations. The source documents an October 2025
reporting-layout change, so a reported decrease is not proof of lower demand.
[Source evidence, periods and edition comparison](brazil_road_history.md).

### Reconciled state origin–destination movements · 2025

775 reported pairs sum to **1,368,627,704 integer tonnes**, including paid and
own-account movements. All 28 independent origin and destination margins
reconcile exactly. EX means exterior. Unlisted pairs are unavailable, not zero;
same-state does not mean within-municipality. These are not truck itineraries.

| Origin UF | Reported destination pairs | Published tonnes |
| --- | --- | --- |
| AC | 28 | 519,586 |
| AL | 27 | 5,419,332 |
| AM | 28 | 3,835,843 |
| AP | 27 | 200,467 |
| BA | 28 | 59,593,473 |
| CE | 28 | 21,628,387 |
| DF | 28 | 6,416,386 |
| ES | 28 | 28,768,066 |
| EX | 24 | 141,482 |
| GO | 28 | 82,835,095 |
| MA | 28 | 24,771,655 |
| MG | 28 | 149,878,146 |
| MS | 28 | 65,884,183 |
| MT | 28 | 182,440,330 |
| PA | 28 | 28,631,705 |
| PB | 27 | 14,986,904 |
| PE | 28 | 31,326,313 |
| PI | 27 | 11,933,855 |
| PR | 28 | 141,725,364 |
| RJ | 28 | 42,571,014 |
| RN | 28 | 14,736,501 |
| RO | 28 | 10,770,784 |
| RR | 28 | 657,882 |
| RS | 28 | 106,898,445 |
| SC | 28 | 80,305,808 |
| SE | 27 | 7,563,272 |
| SP | 28 | 226,912,707 |
| TO | 28 | 17,274,719 |

[Source evidence, filters and API](brazil_road_od.md) ·
[Complete paired observations (CSV)](../deployment/brazil_road/state_od.csv).

### Monthly port handling history · 2021–2026

Original numeric ANTAQ exports retain 62 observed months. Both handling directions
and all navigation categories are included; cargo can repeat across port events.
2026 is partial and is not annualized. All exported sums reconcile with the
independently displayed annual/partial-period totals within whole-tonne rounding.

| Year | Observed months | Full year | Exported tonnes (formatted) | Displayed source total (whole tonnes) |
| --- | --- | --- | --- | --- |
| 2021 | 12 | Yes | 1,209,207,335.297 | 1,209,207,335 |
| 2022 | 12 | Yes | 1,220,619,267.036 | 1,220,619,267 |
| 2023 | 12 | Yes | 1,305,105,576.675 | 1,305,105,577 |
| 2024 | 12 | Yes | 1,322,436,996.505 | 1,322,436,997 |
| 2025 | 12 | Yes | 1,402,731,832.755 | 1,402,731,833 |
| 2026 | 2 | No | 205,539,907.438 | 205,539,907 |

For 2025, rounding the original monthly sum gives 1,402,731,833 t; summing the
twelve individually rounded month labels gives 1,402,731,832 t. The one-tonne
difference is explained without adjusting a month. Source numeric precision is
preserved in downloads; displayed decimals do not imply measurement accuracy.

[Original exports, coverage and API](brazil_water_history.md) ·
[All observed months (CSV)](../deployment/brazil_water/history_monthly.csv).

### Inland-waterway transport and cargo detail

62 months retain international shipping, cabotage with inland navigation and the
Inland Navigation category. These are transport observations, separate from port
handling. Monthly totals reconcile with components, and annual/partial totals
round to the independent source headlines. 2026 has only January and February.

| Year | Observed months | Full year | Transport tonnes (formatted) | Independent headline (whole tonnes) |
| --- | --- | --- | --- | --- |
| 2021 | 12 | Yes | 110,751,767.793 | 110,751,768 |
| 2022 | 12 | Yes | 120,527,603.737 | 120,527,604 |
| 2023 | 12 | Yes | 130,950,418.859 | 130,950,419 |
| 2024 | 12 | Yes | 128,907,185.685 | 128,907,186 |
| 2025 | 12 | Yes | 144,893,597.202 | 144,893,597 |
| 2026 | 2 | No | 21,024,623.989 | 21,024,624 |

The 2025 commodity export contains 117 categories: 109 numeric quantities,
including 46 explicit zeros, and eight source dashes kept as null. Original
shares retain the full denominator after filtering. This is not a paired OD
matrix or an operational routing dataset.

[Original exports, reconciliation and API](brazil_inland.md) ·
[Monthly navigation components (CSV)](../deployment/brazil_water/inland_monthly.csv) ·
[Commodity quantities and status (CSV)](../deployment/brazil_water/inland_commodities_2025.csv).

## Gas source quality and archived road reconciliation

| 2025 point direction | Missing daily cells |
| --- | --- |
| delivery | 2 |
| receipt | 31 |

The 2025 missing cells trace to Garuva receipts on January 1–31 and RPBC/São
Bernardo do Campo deliveries on May 31. The source leaves them blank; no cause
or volume is inferred. [Historical coverage and quality](brazil_gas_history.md).

The twelve archived yearbook road-month labels sum to **1,368,699,651 tonnes**.
The separate regional-reference denominator is preserved without guessing
its scope. [Road source reconciliation](brazil_road.md).

## Inspect and reproduce

- [Scenario input example](examples/transport_scenario.json): explicit synthetic
  costs/capacities, balance constraints and infeasibility checks; no actual savings claim.
- [Solver and result exports](transport_optimization.md) and [scenario comparison](scenario_planner.md).
- [Public API contracts](api.md) and [local API authentication](api_authentication.md).
- [Saved truck geometry](../deployment/route_examples/sao_paulo_campinas_truck.geojson)
  and [vehicle/map limitations](truck_routing.md).
- [Current verification runs](https://github.com/DiegoTDDD/freight-intelligence/actions/workflows/ci_pipeline.yml).
- [Recovery instructions](recovery.md): source/data archives can be kept independently of Render.
- [Open expansion items](expansion_execution.md): this report does not mark them complete.
