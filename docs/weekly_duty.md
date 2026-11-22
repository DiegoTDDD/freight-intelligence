# Declared seven-day duty review

Open **Trip cost and breaks → Seven-day duty review**. Nine explicitly synthetic
examples demonstrate a balanced week, insufficient daily rest, seven workdays and
incomplete history, a cross-midnight night shift, reduced-hour excess and conditional
night extension, plus unknown and collective/exempt regime examples. An optional JSON editor supports other declared scenarios.
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

## Declared employment regime

**X02-T07 is implemented.** The optional `employment_regime` field accepts
`standard_private_employee`, `collective_or_exempt` or `unknown`. Omission is
accepted for older clients and means **unknown**, never an implicit standard
regime. Invalid values, including JSON null, are rejected with 422 by the API.
The published standard examples explicitly declare their comparison profile.

Only an explicitly declared standard profile **and** a supported whole-week date
enable the selected reference checks. For unknown/omitted or collective/exempt
contexts, observed work, timeline, coverage and reference-window overlap remain
available, but shift limits, weekly references, selected rest qualifications,
reduced-hour equivalents and base/conditional comparison verdicts are `null`.
`violations` is empty because the standard profile was not applied; the result is
**manual review required**, never a clean approval. Unsupported dates now withhold
the same selected-policy verdicts instead of displaying dated thresholds.

`regime_assessment` reports `declared_regime`, `reference_checks_enabled` and
`actual_regime_verified: false`. Self-declaration enables a selected calculation
profile; it does not authenticate actual employment, agreements or exemptions.
Unknown and special regimes are not treated as noncompliant just because a
standard-profile threshold would be exceeded. Reference-window overlap is an
observed timestamp quantity, not a legal night-work classification for those regimes.
The dashboard shows a disabled-reference notice and keeps the observed work visible.
Examples: `unknown_regime` and `special_regime`. [Portable special-regime result](examples/duty_regime_report.json).

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
Night/multi-day compliance decisions, collective/exempt regimes and actual operating
acceptance remain outside this release. The base-window accounting below is now
implemented; no result has `dispatch_authorized: true`.

## Night work: real minutes and reduced-hour accounting

The dated standard-profile policy now records [CLT article 73](https://www.planalto.gov.br/ccivil_03/decreto-lei/del5452compilado.htm):
the base night window is 22:00 inclusive to 05:00 exclusive and the nominal night
hour is 52 minutes 30 seconds. This is a selected calculation profile, not a
determination of an actual employment regime, wages or collective terms.

Only `driving`, `work` and `waiting` in that window are converted. Meals, breaks
and rest are excluded. Real minutes remain unchanged for elapsed time, rest and
continuous-driving checks. Work crossing midnight is split over its observed local
dates; missing history is not filled. Exact equivalent minutes are exported as
an integer numerator and denominator, using `day_minutes + night_minutes * 8/7`.
Rounding to two decimals happens only in the displayed hours. The equivalent is
compared separately with selected shift references and the normal weekly
reference, preserving the existing real-minute checks. An above-reference shift
with observed night work adds `selected_reduced_hour_shift_reference_exceeded`.
Weekly equivalent excess requests agreement review; daily overtime authorization
does not approve weekly excess. Comparisons export the exact equivalent excess,
reference and Boolean `exceeded`, and show real/equivalent/reference hours in the
dashboard. Outside the reviewed period all comparison verdicts, references and
equivalent excesses are `null`. The comparison covers observed input only; it
does not fill missing history, approve the regime, automatically extend conversion past 05:00,
compute remuneration or turn a night scenario into dispatch authorization.

For example, 22:06–05:07 contains 414 night and seven day work minutes:
`3361/7` equivalent minutes exceeds 480 by `1/7` minute, even though both display
as 8.00 hours. The reference verdict is made using integers before display
rounding. Meals/rest remain excluded from both work totals and their comparisons.

Work continuing after 05:00 within a shift that has work before 05:00 is
conservatively marked for extension review. The engine does not decide whether
extension treatment applies or convert the post-05:00 work automatically. The
window's left boundary cannot authenticate an earlier shift. Actual payroll,
premiums, rotating/collective/exempt regimes and full night-duty compliance are
not calculated. Outside the reviewed whole-week date range the observed window
counts remain available, but equivalent minutes and nominal-hour conversion are
`null`. A night example always requires review and never authorizes dispatch.
The separate conditional sensitivity below does not replace these base results.

**Synthetic example:** Monday 22:00–Tuesday 06:00, with a 01:00–02:00 meal,
contains 420 real work minutes, 360 night work minutes and 60 day work minutes.
Its base-window equivalent is exactly `3300/7` minutes, displayed as **7.86 hours**.
Waiting at 02:00–05:00 is work. The final 05:00–06:00 hour retains its real length
and triggers extension review. [Input](examples/night_duty_input.json),
[full report](examples/night_duty_report.json) and the README screenshot remain
available when hosting sleeps. This advances **X02** without closing its operating
acceptance requirements.

**Above-reference example:** the `night_limit_exceeded` fixture extends that
scenario to 07:00. It has **480 real work minutes** and `3720/7` equivalent
minutes (**8.86 hours**), exceeding the selected 480-minute shift reference by
exactly `360/7` minutes. It is flagged even though the real-work threshold is not
exceeded; elapsed time stays 540 real minutes. [Input](examples/night_limit_input.json)
and [report](examples/night_limit_report.json) are portable evidence of the
**2026-11-21 E20 enhancement**. The rule-period snapshot remains reviewed through
2026-11-20; this calculation update does not extend its legal date coverage.

## Conditional night extension

The **If night extension applies** section now calculates an explicitly conditional
scenario alongside the base result. [CLT 73 paragraphs 4–5](https://www.planalto.gov.br/ccivil_03/decreto-lei/del5452compilado.htm)
addresses mixed schedules and night extensions; actual applicability still needs
the employment regime, collective terms and an operating/legal review. This
calculation is a sensitivity assumption, not a ruling on entitlement or wages.

The hash-pinned profile `observed_night_continuation_05_to_22_if_applicable_v1`
counts only observed work between 05:00 and 22:00 in the same declared shift,
after observed work in the preceding 22:00–05:00 window. Meals, driving breaks
and rest are excluded. Between-shift rest ends a shift; later daytime work is not
silently attached to the previous night. Disjoint continuation windows prevent
double counting across midnight/multiple days and never count base night work twice.

The conditional equivalent is exactly `base_equivalent + candidate_minutes/7`:
each candidate real minute already counted once in the base would count as 8/7
instead. Exact shift and normal-week comparisons accompany the alternative.
Daily overtime authorization does not approve weekly excess. The window records
whether its complete 22:00–05:00 shift span was observed; **that Boolean is context,
not legal eligibility**. Partial nights are not declared eligible or ineligible.
Unknown carry-in, missing coverage and open shifts remain review reasons.

`extension_sensitivity.applicability` is always `not_determined` and
`replaces_base_result` is always false. A conditional excess adds a review reason,
never an authoritative violation. The parent `extension_conversion_applied`
remains false. Beyond the existing reviewed whole-week period, observed candidate
minutes remain available, while conditional equivalents/references/verdicts are
null. No assumed rest, remuneration or dispatch approval is produced.

**Synthetic example:** `night_extension_sensitive` is 22:00–06:01 with a full
01:00–02:00 meal. It contains **421 real work minutes**, 360 base night work
minutes and **61 continuation work minutes**. The base equivalent is `3307/7`
minutes (**7.87 hours**, below 480). If extension treatment applies, the equivalent
would be `3368/7` minutes (**8.02 hours**, above 480). The base comparison remains
false, the conditional comparison is true, violations remain empty and the result
is **manual review required**. [Input](examples/night_extension_input.json) and
[full report](examples/night_extension_report.json) are portable evidence. This
enhances E20's arithmetic without asserting that X02's actual-regime or operating
acceptance requirements have been met. Profile arithmetic reviewed 2026-11-21;
the underlying supported rule period remains unchanged.

## Portable results

| Synthetic scenario | Observed work | Selected result |
| --- | --- | --- |
| Balanced 2026-11-09 week | 44 hours | Within selected weekly planning limits |
| Short daily rest | 44 hours | 659-minute intershift rest flagged |
| Seven workdays | 48 hours | Seventh workday flagged; weekly excess needs review |
| Incomplete week | 44 observed hours | Missing coverage remains explicit; no clean result |
| Night shift with extension | 7 real work hours; 6 in the night window | 7.86 base-window equivalent hours; extension/regime review required |
| Reduced-hour reference exceeded | 8 real work hours; 6 in the night window | 8.86 equivalent hours; selected shift reference exceeded |
| Extension changes the comparison | 7.02 real work hours; 61 continuation minutes | Base 7.87 hours; conditional 8.02 hours; applicability needs review |

The balanced example has five eight-hour workdays and one four-hour workday,
with a full meal per shift. Its final declared rest is exactly 2,100 minutes.
[Input JSON](examples/weekly_duty_input.json) and
[full review](examples/weekly_duty_report.json) remain readable without Render.

## API, permissions and resource bounds

`GET /api/brazil/duty-review?example=balanced_week` returns a published synthetic
`input` and its `review`. Other example names are `short_daily_rest`,
`seven_workdays`, `incomplete_week`, `night_shift`, `night_limit_exceeded` and
`night_extension_sensitive`.

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
