# Brazilian railway freight and historical forecasts

The **Brazilian freight** workspace presents movements reported to ANTT/SIADE for
federally conceded Brazilian railways, covering 2006–2025. It does not cover all
Brazilian freight modes or count unique shipments: cargo can appear in successive
flows or in reports from more than one railway operator.

## Official source and preparation

- [ANTT/SIADE catalogue](https://dados.antt.gov.br/dataset/438a5184-09db-49a3-88c8-0bad418b4409).
- [Official data dictionary](https://dados.antt.gov.br/dataset/438a5184-09db-49a3-88c8-0bad418b4409/resource/5eb3b609-29c8-4108-a5ac-0d55950a0064/download/producao_origem_destino_dicionario_dados.pdf).
- Attribution: Agência Nacional de Transportes Terrestres. The catalogue declares
  Creative Commons Attribution. Retrieved on 2026-11-12.

Twenty yearly files containing all twelve reported months were accepted. The partial
2026 archive was excluded. Month presence does not prove every operator's reports are
complete or final. Administrative records may be revised and coverage may change.

The parser accepts semicolon-separated UTF-8/Windows-1252 text and Brazilian numbers:
`1.234,5` becomes 1234.5. Negative values, ambiguous formats, invalid months and year
mismatches fail validation. Raw files stay outside Git.

**TU** denotes net tonnes and **TKU** net tonne-kilometres. These are kept separate
from FAF's thousands of source tons and millions of ton-miles. Aggregates retain
year, month, commodity, railway and flow origin/destination states.
`deployment/brazil_data/provenance.json` records source URLs, hashes, sizes and rows.

Create another snapshot without replacing the existing one:

```text
python scripts/prepare_brazil_rail.py --output NEW_OUTPUT_DIRECTORY --raw NEW_RAW_DIRECTORY
```

## Forecast evaluation

Persistence, linear trend and endpoint CAGR are compared. Training starts with
2006–2013; expanding validation uses targets through 2022. Selection uses validation
MAE only. **2023–2025** form a reserved final test predicted from a fixed origin.
Those test errors never change the selected model.

| Metric | Validation-selected model | Test WAPE, 2023–2025 |
| --- | --- | --- |
| TU | CAGR | 4.75% |
| TKU | CAGR | 1.61% |

Linear trend achieved a lower TU test error, about 1.96%. It was not promoted using
that result, which would reuse the reserved test for model selection. The dashboard
shows all model scores, MAE, RMSE, WAPE and predictions for inspection.

After test scoring, the already-selected model is refit on the complete history to
estimate 2026–2028. These are point forecasts, not observations, without prediction
intervals or a future accuracy guarantee. Revisions, coverage and structural changes
limit interpretation. The downloadable ZIP contains observations, source manifest,
evaluation settings, predictions, scores and forecasts. Opening this workspace reads
verified saved results and does not download the raw archives again.
