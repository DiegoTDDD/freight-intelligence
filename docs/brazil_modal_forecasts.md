# Evaluated port and oil-pipeline baselines

The water and pipeline atlas views now include a read-only **Port and oil-pipeline
forecast evaluation · 2024 cutoff** panel. A separate portable ZIP contains input
observations, source manifest, model choices, every candidate's scores, reserved
test predictions and six vintage forecast points. Viewing it never trains models.

## Sources and populations

The input is thirty previously reviewed rounded chart labels, fifteen per series
from 2010–2024 in the official Infra S.A./ONTL
[Diagnóstico Logístico 2010–2024](https://ontl.infrasa.gov.br/wp-content/uploads/2025/10/Diagnostico-logistico-2010-2024.pdf).
The source PDF hash is retained in the existing modal snapshot and copied into
the report's provenance. Port handling is from page 78 in **million tonnes**;
Transpetro oil/product pipeline movements are from page 123 in **million m³ at
20°C**. The latter excludes other operators and mineral pipelines. Neither series
counts unique national consignments. Original chart rounding is retained.

Source CSV values are compared with the current validated atlas whenever the
report is loaded. This prevents a report silently surviving a relevant input
revision. Other source editions, including separate 2025 ANTAQ references, are
not appended without reconciling populations, rounding and source vintage.

## Protocol and results

- Eight annual training points at the first expanding-window validation origin.
- Validation targets 2018–2021; model choice uses validation MAE only.
- A final reserved 2022–2024 test from origin 2021, with no refitting or reselection
  on those three test observations.
- Candidates: persistence, linear trend and annualized endpoint CAGR.
- After scoring, the chosen model is refit on the complete 2010–2024 input to
  produce vintage estimates for 2025–2027. There are no uncertainty intervals.

| Indicator | Validation-selected model | Reserved-test WAPE | Comparison |
| --- | --- | --- | --- |
| Port cargo handling | Linear | 2.10% | CAGR scores 1.45%; persistence 5.74% |
| Transpetro oil/product movements | CAGR | 16.91% | Persistence scores 15.35%; linear 27.45% |

Both examples disclose a competitor outperforming the validation-selected model
on the final test. This is a limitation, not a reason to choose on test results.
The [static portfolio report](portfolio_evidence.md) includes every score.

These are **2024-cutoff vintage forecasts**. Because the source ends in 2024,
some forecast years may already be in the past when viewed. Output rows remain
model estimates; passing calendar time never turns them into observations.

## API, rebuild and safeguards

`GET /api/brazil/modal-forecasts` returns the six vintage forecasts. Options:

- `view=scores|predictions|forecast`; forecast is the default.
- `mode=water|pipeline` selects a distinct series/unit.
- `phase=validation|test` applies to scores/predictions only.
- `year` applies to predictions/forecasts only; incompatible filters return 422.
- `limit` (1–500) and `offset` bound responses; existing analytics permissions apply.

Source/report mismatches or absent reports return 503. The reader checks hashes,
bounded ZIP members, source observations, units, numeric values, model flags,
validation selection and the reserved-test boundary. Private plans are not read.

Rebuild only this small report with:

```bash
python scripts/prepare_brazil_modal_forecasts.py
```

It reads the committed 145-row modal atlas; it does not rerun Bronze/Silver/Gold,
download raw data or call routing providers. The normal CI and exact-commit
deployment gate publish a reviewed update. Gas has only five reviewed complete
years and the MDF-e movement snapshot has one; they are not padded with fabricated
annual history to satisfy a forecast training window. Road fleet stock is not
substituted for freight demand.
