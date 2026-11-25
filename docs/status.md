# Current delivery status

Reviewed **2026-11-25**. The original **12 portfolio stages are delivered**.
There are **20 concrete delivered expansion items**, each closed for its stated
source population and period. **Four additional requirements remain unmet**;
they are separate entries with exact completion criteria and dependencies.

**Counter: original 12/12; expansions 20/20; additional requirements 3/7 closed
and 4/7 open. Latest delivered checkpoint: X04-T01.** See the
[marked checkpoints and acceptance gates](expansion_execution.md#x04-checkpoints).

**2026-11-25: X04-T01 delivered.** The local operating-allocation comparison
validates declared flows and reports same-model opportunity, with realized savings
explicitly unavailable. [Contract and example](operating_comparison.md).
[Repository review](repository_review_20261125.md) records the subsequent broad audit.

**2026-11-25: X03-T01/T02/T03 delivered.** The public API now has a separate
Free service, revision/data checks, a configured daily sampled monitor and a
verified planned restart. [Evidence](independent_api.md#observed-deployment).
X03-T04 production availability remains unmet, so the global counter stays 3/7.

The authoritative record is the [delivery checklist](expansion_execution.md):

- **O01–O12:** original roadmap, completion criteria and evidence.
- **E01–E20:** published expansions; completed rows stay closed.
- **X01–X04:** commercial dispatch, toll/duty compliance, independent
  hosting and real-company outcomes. These are not presented as delivered.
- **X06 closed as E15:** the ANAC source now has bounded revision auditing,
  retained changed-source evidence and no automatic promotion.
- **X07 closed as E16:** four additional ANAC free-cargo/mail targets now have
  reserved-test comparisons, forecasts and public report access.
- **X05 closed as E17:** 2023 ANAC airport-pair coverage adds 18,699 reconciled
  monthly records while preserving previous pairs and forecasts.

E18 adds dated toll/daytime planning; E19 adds declared seven-day duty review
with explicit missing data and rule-date support. E20 adds exact base-window
night-work accounting, exact selected shift/weekly reference comparisons and
explicit post-05:00 extension review. X02 remains open for
complete operating acceptance; a synthetic scenario is not driver-log validation.
The separate conditional extension calculation now quantifies the impact of
observed continuation work, without replacing the base result or deciding actual
regime applicability. [Contract and example](weekly_duty.md#conditional-night-extension).

This replaces the previous open-ended remaining-work list. Additional years or
sources do not silently reopen delivered work. New coverage needs a named source,
population, period, acceptance criterion and its own evidence.

## Earlier immutable functional baseline

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
- [Independent public API](https://loginexus-public-api.onrender.com/docs)
- [README inventory and English-interface screenshots](../README.md)
- [Generated static results and source-quality evidence](portfolio_evidence.md)
- [Recovery procedure](recovery.md)
- [Deployment and exact-tested-commit policy](publicacao_continua.md)

The dashboard and independent API use separate Free services in the same Render
workspace, sharing its running-hour quota. The older mounted API remains for
compatibility. Both can sleep/restart. Screenshots, source code, static results
and versioned aggregates remain reviewable without them. Independent API hosting
is delivered; production availability remains the open X03-T04 gate. No paid services were purchased.
Local hourly development automation remains paused; source-revision audits are separate.
