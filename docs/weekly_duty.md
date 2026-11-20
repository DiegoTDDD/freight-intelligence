# Declared seven-day duty review

Open **Trip cost and breaks → Seven-day duty review**. Four explicitly synthetic
examples demonstrate a balanced week, insufficient daily rest, seven workdays and
incomplete history. An optional JSON editor supports other declared scenarios.
This is selected-rule screening, not authentication of driver records or a legal,
payroll or dispatch decision. **X02 remains open** for complete operating acceptance.

## Data contract and missing history

A window starts at Monday midnight in Sao Paulo (UTC-03 in this reviewed period).
`events` contains 1–300 consecutive records, each with exactly `activity` and
positive integer `minutes`. Allowed activities are `rest`, `driving`, `work`,
`waiting`, `meal` and `driving_break`. `rest` specifically declares uninterrupted
between-shift off-duty time; use meal/driving_break for intrashift pauses.
Adjacent rest records are merged. Waiting remains work.

A complete window contains exactly **10,080 minutes**. Shorter input remains
incomplete; it is not extended with invented rest. Entirely unobserved days have
`work_minutes: null`, not zero. Partially observed days report observed subtotals
and explicit coverage. More than seven days, unknown fields (including names),
duplicate JSON fields, Boolean/negative durations and invalid dates are rejected.

`carry_in_rest_minutes` declares uninterrupted rest immediately preceding the
window. `carry_in_consecutive_workdays` declares prior workdays before any
qualifying reset. Either can be `null` when unknown; unknown context prevents a
clean result. Declare `overtime_authorized` as Boolean. This is self-declaration,
not verification of an agreement or a tachograph. No driver identifier is accepted.

## Selected policy and source period

The November 2026 snapshot uses the reviewed standard private daytime freight
profile. [CLT 66/67/235-C](https://www.planalto.gov.br/ccivil_03/decreto-lei/del5452compilado.htm),
[CTB 67-C](https://www.planalto.gov.br/ccivil_03/leis/l9503compilado.htm),
[STF ADI 5322](https://noticias.stf.jus.br/postsnoticias/stf-invalida-dispositivos-da-lei-dos-caminhoneiros-sobre-tempo-de-espera-jornada-e-descanso/)
and [TST Theme 265](https://www.tst.jus.br/documents/d/guest/irr265-2-pdf)
are linked in the hashed policy.

- Declared intershift rest is checked against eleven uninterrupted hours.
- A 35-hour continuous block is the selected combined weekly/daily-rest policy.
  Weekly workday counting is reset only by a qualifying block; a seventh worked
  local date before that reset is flagged. Rest at the right window boundary that
  has not yet reached the selected duration needs the next window.
- The existing conservative policy checks 330 driving minutes without a full
  30-minute break, one full 60-minute meal with work before/after, 480 work minutes
  per shift or 600 with the daily overtime flag, and a 780-minute shift span.
  Lawful fragmented breaks, special/collective regimes and payroll are not resolved
  by this simplified policy; these flags are not legal verdicts.
- The normal weekly reference is 44 hours **only for the supported reviewed
  dates**. An excess requests agreement/payroll review; the daily overtime flag
  never automatically approves weekly excess. The engine does not compute wages.

The [EC 141/2026 official text](https://www.planalto.gov.br/ccivil_03/constituicao/emendas/emc/emc141.htm)
contains staged weekly-hours/rest changes and differentiated transitional regimes.
A whole reviewed week must fall between 2023-07-12 and 2026-11-20. Outside this
period, the weekly normal-hour reference is `null` and separate review is required;
the engine does not apply an old 44-hour ceiling to future periods. Updating the
version requires a new source/date review, policy hash and regression tests.
Night/multi-day duty, collective/exempt regimes and actual operating acceptance
also remain outside this release. No result has `dispatch_authorized: true`.

## Portable results

| Synthetic scenario | Observed work | Selected result |
| --- | --- | --- |
| Balanced 2026-11-09 week | 44 hours | Within selected weekly planning limits |
| Short daily rest | 44 hours | 659-minute intershift rest flagged |
| Seven workdays | 48 hours | Seventh workday flagged; weekly excess needs review |
| Incomplete week | 44 observed hours | Missing coverage remains explicit; no clean result |

The balanced example has five eight-hour workdays and one four-hour workday,
with a full meal per shift. Its final declared rest is exactly 2,100 minutes.
[Input JSON](examples/weekly_duty_input.json) and
[full review](examples/weekly_duty_report.json) remain readable without Render.

## API, permissions and resource bounds

`GET /api/brazil/duty-review?example=balanced_week` returns a published synthetic
`input` and its `review`. Other example names are `short_daily_rest`,
`seven_workdays` and `incomplete_week`.

`POST /api/brazil/duty-review` accepts the same input object as application/json
and returns a stateless calculation. It does not create/update a record and
returns `records_saved: false`. Existing analytics permissions protect both
methods when authentication is enabled. Body reception is bounded at 64 KiB and
ten seconds; oversized requests return 413, wrong content type 415, malformed
history 422 and missing/inconsistent policy 503. The OpenAPI document includes
the request schema. Dataset routes retain their existing read-only methods.

```bash
curl -H "Content-Type: application/json" --data-binary @docs/examples/weekly_duty_input.json \
  https://loginexus-dashboard-preview.onrender.com/api/brazil/duty-review
```

The dashboard keeps the last scenario only in session memory. Neither endpoint
writes histories to disk or sends them to a routing/source provider. Declared
records still require independent operational authentication. The hosted image
and recovery archive include the hash-checked policy; viewing results trains no
model and runs no large pipeline.
