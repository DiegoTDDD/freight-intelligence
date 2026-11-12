# Consolidated local milestone — 2026-11-12

The implementation remains in the shared working tree, uncommitted and unpushed.
The full FAF pipeline has not been run during this development work.

| Area | Delivered locally |
| --- | --- |
| Windows pipeline | Unicode-safe commodity summaries, isolated regression coverage |
| Pipeline execution | Non-executing JSON plan, dependency-aware reuse, staged Bronze/Silver writes |
| Analytics | Interval/annualized growth distinction and undefined-rate handling |
| Forecasting | Scenario baselines, temporal validation/test, provenance-aware saved readers |
| Historical work | Declared CSV source contract, optional forecasts, archived FAF estimate subset |
| Allocation | Continuous min-cost flow, explanatory infeasibility errors, scenario comparisons |
| Road routing | Supplied directed graph, single-vehicle limits, explicit costs; no verified road source |
| Dashboard | Read-only saved views and explicit session-only simulation/evaluation forms |
| API access | Shared or individual keys, separate permissions, prefix-independent routing |
| Local runtime | Pinned non-root API image, read-only mounts and opt-in users-registry Compose |
| CI configuration | Windows/Linux lightweight matrix, reports, Ruff and Linux container checks |

Latest lightweight regression: **265 passed**, excluding only `tests/test_faf5.py`, which
requires the large real dataset. Ruff passed. One upstream Starlette TestClient deprecation
warning remains; no dependency churn was introduced solely to silence it.
A fresh `loginexus-api:validated` image was built and verified against 38 runtime pins.
This tag is separate from the existing Compose service; no deployed service was replaced.
GitHub checks have not run because changes have not been committed/pushed.

## Remaining external prerequisites

- Verified road-network data, freshness, actual vehicle/routing requirements and measured
  costs are needed before claiming operational driving routes. Current synthetic tests
  validate code, not actual routes.
- An agreed hosting target, domain/HTTPS setup and identity/secret-delivery requirements
  are needed for an actual production deployment. No public exposure is authorized.
- Separately verified historical observations and adequate temporal coverage are needed
  for stronger demand-forecast accuracy claims. The local FAF slice contains five estimated
  annual points per metric and a single final test year.
- Commit, push and heavy pipeline execution still require explicit user authorization.

Continue only with concrete useful work supported by available inputs. Avoid repeatedly
rerunning successful checks or expanding synthetic demonstrations to simulate progress.
Consult `development_handoff.md` for chronology and exact command contracts in topic docs.
