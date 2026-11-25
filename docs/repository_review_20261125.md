# Repository review — 2026-11-25

## Conclusion and scope

The original portfolio scope is delivered: **12/12 stages**, with **20/20 named
expansions**. Additional operating requirements remain **3/7 closed, 4/7 open**.
This review found and corrected defects; previous green tests did not establish
that every failure mode was covered. The project is a portfolio demonstration,
not a certified dispatch, employment-compliance or commercial-availability service.

Reviewed areas: packaging/configuration, pipeline ordering and failure propagation,
Bronze/Silver/Gold writes, isolated commodity transformation, analytics edge cases,
forecast split/selection interpretation, optimization comparisons, route limits,
API permissions and public-data isolation, bounded source retries, dashboard test
coverage/caches, container CI, recovery manifests and documentation consistency.
This is a scoped engineering review, not proof that every possible defect is absent.

## Findings corrected

| Finding | Correction and verification |
| --- | --- |
| Heavy workflow still piped the pipeline into `tail`, allowing producer failure to be hidden | Explicit Bash shell; pipeline and pytest preserve complete logs and return their original failure codes; injected exit-17 tests verify downstream commands are not reached |
| Editing that workflow could automatically launch the approximately 100-million-row run | Heavy workflow now requires manual dispatch; lightweight CI tests shell success/failure without downloading FAF or executing the heavy pipeline |
| Gold and commodity-lookup writes could truncate existing Parquets during a failed write | All eleven analytical/lookup outputs stage on the same filesystem and replace each destination only after writer success; interrupted-write tests cover four Gold sinks, five downstream writers and lookup |
| Commodity CAGR divided by zero for a zero starting volume or no elapsed year | Undefined CAGR is null, consistent with annual CAGR; null values sort last in generated commodity growth; endpoint regressions cover both cases |
| README/status still described X03 as the latest checkpoint after X04-T01 delivery | Current summaries now link to the delivered operating-comparison tool and retain all outstanding acceptance gates |

Atomic replacement is **per file**, not a transaction across the entire pipeline.
An interrupted multi-output rebuild can leave individually complete files from
different runs. `--skip-existing` checks presence/dependencies, not source freshness
or a common run identity. After an interrupted source-changing rebuild, perform a
reviewed full rebuild before promoting outputs; bundled serving snapshots remain
separately versioned and hash-checked. This review did not regenerate them.

## Validation and observed services

- Baseline: 690 lightweight tests passed locally before changes. The corrected
  revision adds regression tests for workflow failure propagation, undefined CAGR
  and interrupted writes. The corrected local suite passed 707 tests; an additional
  end-to-end fixture test then passed separately. It runs all nine real transforms
  on two temporary CSV rows, producing 78 Silver rows and all eleven Gold outputs.
  Its required CI runs Windows/Linux tests and both API
  and dashboard container checks before the existing dashboard deploy step.
- Ruff and generated static portfolio evidence checks passed. `pip check` found
  no broken installed dependency requirements; this is not a CVE audit.
- Documentation links were checked for local file existence, including URL-encoded
  filenames. A limited tracked-file scan found no GitHub-token, AWS-access-key or
  private-key-header pattern matches; this is not an exhaustive secret audit.
- The independent public API passed its bounded live check: reviewed revision
  `5a6c4c74cf7474a5bbcf3d3f1c62944ff695342e`, matching manifest, readiness and
  sampled annual data returned 200; unavailable private plans returned 503.
  Identity/readiness was observed after about 23.24 seconds; subsequent sampled
  requests took about 0.25–0.28 seconds. This is one observation, not an uptime SLA.
- The live dashboard root, health, readiness and sampled annual API returned 200;
  the initial health response took about 29.48 seconds and subsequent requests
  about 0.25-0.41 seconds. HTTP checks alone do not prove every browser interaction.
- Docker Desktop was not running locally. Container acceptance therefore depends
  on the corrected revision's GitHub CI, not a claimed new local Docker run.
- The existing Unicode/cp1252 regression remains covered; the removed table print
  was not restored. ANP/ANTT retry and `source_unreachable` warning behavior were
  preserved without modification.

The full FAF dataset was **not** reprocessed, source tariffs/rules were not
extended to new dates, and no paid services or new operational certifications
were introduced. The known upstream Starlette/httpx test deprecation warning
remains separate from test failures.

## Remaining external acceptance

| ID | Required evidence still missing |
| --- | --- |
| X01 | Verified operating region/vehicles, current route restrictions and dispatch acceptance |
| X02 | Actual employment/collective terms, authenticated driver records and reviewed operating/legal acceptance |
| X03 | Accepted and demonstrated production-availability requirement; separate Free API delivery is already complete |
| X04 | Authenticated company inputs, reviewed modeling assumptions and comparable realized outcomes |

These gates cannot be replaced by additional synthetic examples or a repeated
test run. [Authoritative marked checklist](expansion_execution.md).

[Machine-readable review observations](evidence/repository_review_20261125.json).
