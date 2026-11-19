# ANP gas source revision audit

The repository workflow **Audit Brazilian gas source revisions** runs on Mondays
at 09:17 UTC (06:17 America/Sao_Paulo) and can also be started manually in GitHub
Actions. It runs on a GitHub-hosted runner, independently of the owner's PC. This
does not reactivate the paused hourly local development automation.

The audit covers the reviewed ANP gas reports for **2021–2025**: twelve fixed
monthly URLs per year, sixty reports in total. Five isolated jobs run with at most
two years in parallel. It does not discover unreviewed years or update every
Brazilian source. Historical years use their reviewed calendar, exact-duplicate
policy and explicit unit contracts. For 2021, the official unit dictionary is
re-fetched and must retain its pinned SHA-256; changed units stop the audit.

## What happens on each run

1. For each selected year, fetch all twelve reports again, bypassing cached source bytes. Each request has
   a 30-second timeout and an 8-MiB bound; unexpected redirects are rejected.
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
responses fail with a report. Outputs cannot be written into serving snapshots.

The workflow is read-only and does not use a deployment secret. Reports and changed
PDFs are retained as GitHub artifacts for 14 days. GitHub schedules may be delayed
or disabled for inactive repositories; this is revision detection, not guaranteed
real-time refresh. The local hourly development automation remains paused.

## Separately reviewed road panel history

The [28-month Power BI capture](brazil_road_history.md) is versioned with its
rendered-table transcription and source-context hashes. Its source header date
predates its last table month and is not a freshness guarantee. The weekly road
PDF audit does not update this separate panel edition. A future panel refresh
requires explicit evidence review, exact reconstruction and the normal CI gate.
