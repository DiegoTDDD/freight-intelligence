# ANP gas source revision audit

The repository workflow **Audit Brazilian gas source revisions** runs on Mondays
at 09:17 UTC (06:17 America/Sao_Paulo) and can also be started manually in GitHub
Actions. It runs on a GitHub-hosted runner, independently of the owner's PC. This
does not reactivate the paused hourly local development automation.

The first supported source is the fixed twelve-file ANP gas dataset for **2025**.
The audit does not discover new years or update every Brazilian source yet.

## What happens on each run

1. Fetch all twelve reports again, bypassing cached source bytes. Each request has
   a 30-second timeout and an 8-MiB bound; unexpected redirects are rejected.
2. Validate schema, calendar, identifiers, duplicate records and number formats;
   aggregate realized receipts and deliveries separately, keeping missing/signed
   values explicit. Validate the generated bundle and annual/monthly consistency.
3. Compare source SHA-256 values with the reviewed baseline. If none changed,
   report `unchanged` without producing a promotion candidate.
4. If source bytes changed, build and validate isolated gas and modal snapshots.
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
python -m scripts.audit_brazil_gas --output NEW_AUDIT_DIRECTORY --cache-dir RAW_CACHE_DIRECTORY
```

Use a new output directory for each audit. Output/cache paths inside deployment
snapshots are rejected. The audit never runs the large FAF pipeline, model training,
an optimizer or routing requests. Raw files stay in the cache and outside the ZIP.

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
