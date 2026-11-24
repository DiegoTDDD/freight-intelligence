# Brazilian source revision audits

The repository workflow **Audit Brazilian gas source revisions** runs on Mondays
at 09:17 UTC (06:17 America/Sao_Paulo) and can also be started manually in GitHub
Actions. It runs on a GitHub-hosted runner, independently of the owner's PC. This
does not reactivate the paused hourly local development automation.

The audit covers the reviewed ANP gas reports for **2021–2025**: twelve fixed
monthly URLs per year, sixty reports in total. Five isolated jobs run one year at a
time, because parallel bursts made gov.br reset connections from the hosted runner. It does not discover unreviewed years or update every
Brazilian source. Historical years use their reviewed calendar, exact-duplicate
policy and explicit unit contracts. For 2021, the official unit dictionary is
re-fetched and must retain its pinned SHA-256; changed units stop the audit.

## What happens on each run

1. For each selected year, fetch all twelve reports again, bypassing cached source bytes. Each request has
   a 30-second timeout and an 8-MiB bound; unexpected redirects are rejected. A connection reset, timeout or
   HTTP 408/425/429/5xx is retried after 5, 15 and 45 seconds. If the server is still unreachable, the report
   status is `source_unreachable`, the run shows a warning instead of failing, and nothing is compared.
2. Validate schema, calendar, identifiers, duplicate records and number formats;
   aggregate realized receipts and deliveries separately, keeping missing/signed
   values explicit. Validate the generated bundle and annual/monthly consistency.
3. Compare source SHA-256 values with the reviewed baseline. If none changed,
   report `unchanged` without producing a promotion candidate.
4. If source bytes changed, build and validate an isolated per-year bundle.
   For 2025 only, also build the dependent current modal snapshot. Historical
   candidates live under `deployment/historical-year-review/YEAR`, and are not
   drop-in replacements for the combined historical serving snapshot. Rebuild
   that combined snapshot after reviewing a historical candidate.
   The report compares coverage and observed subtotals. A verified candidate ZIP
   contains only the derived snapshots and report, with its own SHA-256.
5. Preserve the report/candidate as a GitHub artifact for 14 days. Schema failures
   fail the workflow and retain a failure report; no candidate is published.

The workflow has **read-only repository permissions**, no deployment secret and
no ability to replace the public data. A source revision can change scope or
quality: review the differences before applying the derived files through the
normal tested main-branch deployment. This is automatic collection, validation
and revision reporting, not unattended promotion of unreviewed source data.

## Local execution

From an installed project environment:

```text
python -m scripts.audit_brazil_gas --year 2024 --output NEW_AUDIT_DIRECTORY --cache-dir YEAR_SPECIFIC_RAW_CACHE_DIRECTORY
```

The year defaults to 2025; only reviewed years 2021–2025 are accepted.
Use a new output directory for each audit and a year-specific raw cache. Output/cache paths inside deployment
snapshots are rejected. The audit never runs the large FAF pipeline, model training,
an optimizer or routing requests. Raw files stay in the cache and outside the ZIP.

Live verification on 2026-11-19 re-fetched all 60 monthly files for 2021–2025 and
the 2021 unit dictionary. All source hashes matched the reviewed baseline;
no promotion candidate was produced.

GitHub schedules may be delayed, and inactive public repositories can have their
schedules disabled. Artifact retention is not a permanent backup; keep reviewed
recovery/source archives separately. See [GitHub scheduling](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule)
and [artifact retention](https://docs.github.com/en/actions/tutorials/store-and-share-data).

## ANTT road source revision audit

The `Audit Brazilian road source revisions` workflow runs on Mondays at 09:27 UTC
(06:27 in São Paulo), on demand, and when its script/preparation contract changes.
It validates the reviewed 12-month sum and downloads the fixed official PDF with
a 30-second request timeout and 8 MiB size cap. Matching bytes produce an unchanged
report. Changed PDF bytes are kept as an **unreviewed source**, with the old/new
hashes; values are never extracted, approved or deployed automatically. Invalid
responses fail with a report. Connection resets, timeouts and HTTP 408/425/429/5xx
are retried after 5, 15 and 45 seconds; a server still unreachable after four
attempts gives a `source_unreachable` report and a warning, not a failed run. Outputs cannot be written into serving snapshots.

The workflow is read-only and does not use a deployment secret. Reports and changed
PDFs are retained as GitHub artifacts for 14 days. GitHub schedules may be delayed
or disabled for inactive repositories; this is revision detection, not guaranteed
real-time refresh. The local hourly development automation remains paused.

## ANAC air source revision audit

Checklist item X06 is closed by delivery E15 for this named source.

The separate **Audit Brazilian air source revisions** workflow runs Mondays at
09:37 UTC (06:37 America/Sao_Paulo), on demand, and when its retrieval contract or
reviewed baseline changes. It covers one named source: the official consolidated
ANAC `Dados_Estatisticos.csv` used by the published 2000–2025 aggregate and
2024–2025 pair snapshots. It does not discover new datasets or extend their scope.

The download streams to disk in at most 1-MiB chunks, retaining at most a 64-KiB
header prefix in memory. Limits: 450 MiB total, 30-second socket timeout, and a
900-second elapsed budget checked between reads (a blocked read may consume its
socket timeout before the next check). Unexpected redirects, invalid/truncated
lengths, missing/duplicate source columns, invalid update dates and malformed
header responses fail with a retained report. Partial files are removed.

The detector compares SHA-256 with the reviewed source. Matching bytes produce
`unchanged` and remove the downloaded temporary file. Changed bytes are retained
as `unreviewed-source.csv`, with before/after hashes and the source update line.
This is **header validation and revision detection**, not full row validation or
approval of new observations. Reports explicitly set `full_data_rows_validated`
and `automatic_promotion` to false. No aggregate, forecast or serving file is
replaced by the audit. Changed observations need ingestion and source review.

The read-only workflow has no deployment secret. Reports and changed CSV files
are kept as Actions artifacts for 14 days; normal schedules/retention limits apply.
The original CSV can be hundreds of megabytes, so the job runs on GitHub rather
than in the 512-MiB dashboard service. Local command:

```text
python -m scripts.audit_brazil_air --output NEW_AIR_AUDIT_DIRECTORY
```

The first live local run on 2026-11-20 detected a 361,057,599-byte file revision.
A separate manual comparison with the exact previously reviewed raw CSV proved
that every byte after the first update-date line was unchanged. Only the date
changed from 2026-11-13 to 2026-11-20. Source hash/date provenance was reviewed
and updated through the normal CI path; all Parquet and forecast bytes were
preserved. [Audit and comparison evidence](evidence/anac_source_review_20261120.json).

This closes X06 for the named ANAC source. Other providers require separately
named audit contracts; they do not silently reopen this completed requirement.

## Separately reviewed road panel history

The [28-month Power BI capture](brazil_road_history.md) is versioned with its
rendered-table transcription and source-context hashes. Its source header date
predates its last table month and is not a freshness guarantee. The weekly road
PDF audit does not update this separate panel edition. A future panel refresh
requires explicit evidence review, exact reconstruction and the normal CI gate.

ANAC report artifact names include the workflow run and attempt number, so a
manual retry retains the earlier failure report and can upload its own result
without replacing or colliding with the first attempt.
