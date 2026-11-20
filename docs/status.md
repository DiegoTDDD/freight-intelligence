# Current delivery status

Reviewed **2026-11-20**. The original **12 portfolio stages are delivered**.
There are **15 concrete delivered expansion items**, each closed for its stated
source population and period. **Six additional requirements remain unmet**;
they are separate entries with exact completion criteria and dependencies.

The authoritative record is the [delivery checklist](expansion_execution.md):

- **O01–O12:** original roadmap, completion criteria and evidence.
- **E01–E15:** published expansions; completed rows stay closed.
- **X01–X05 and X07:** commercial dispatch, toll/duty compliance, independent
  hosting, real-company outcomes, additional source coverage and additional
  forecast targets. These are not presented as delivered.
- **X06 closed as E15:** the ANAC source now has bounded revision auditing,
  retained changed-source evidence and no automatic promotion.

This replaces the previous open-ended remaining-work list. Additional years or
sources do not silently reopen delivered work. New coverage needs a named source,
population, period, acceptance criterion and its own evidence.

## Latest functional verification

Revision [05ba893](https://github.com/DiegoTDDD/freight-intelligence/commit/05ba893333578e6a2291886e606a56616443dc1f)
passed **474 lightweight tests on Windows and Linux** and all five CI/deployment
jobs. Its published inland API matched 62 monthly rows, six annual totals, three
navigation references and 117 source commodity categories, preserving eight
unavailable dash quantities and 46 explicit zeros. The hosted six-session/eighteen-
render check peaked at **249.9 MiB**, with no OOM events.
[Verification run](https://github.com/DiegoTDDD/freight-intelligence/actions/runs/44656414891).

The heavy FAF pipeline was verified previously: 2,503,352 Bronze and 97,630,728
Silver rows. Routine documentation/small-snapshot changes do not repeat that run.
Verification results are dated evidence, not a permanent zero-error guarantee.

## Review and reproduce

- [Live dashboard](https://loginexus-dashboard-preview.onrender.com/)
- [Public API](https://loginexus-dashboard-preview.onrender.com/api/docs)
- [README inventory and twelve English-interface screenshots](../README.md)
- [Generated static results and source-quality evidence](portfolio_evidence.md)
- [Recovery procedure](recovery.md)
- [Deployment and exact-tested-commit policy](publicacao_continua.md)

The dashboard and public API share a free demonstration service that can sleep or
restart. Screenshots, source code, static results and versioned public aggregates
remain reviewable without it. Independent API hosting and production availability
are explicitly outstanding X03 requirements. No paid services were purchased.
Local hourly development automation remains paused; source-revision audits are separate.
