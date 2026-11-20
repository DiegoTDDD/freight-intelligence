# Reviewed corridor tolls and selected duty checks

The **Trip cost and breaks** workspace and `GET /api/brazil/trip-planning`
calculate a dated planning scenario. They do not authorize dispatch or certify
complete legal compliance. **X02 remains open** for operating acceptance and the
unimplemented weekly/night-work/collective-agreement checks.

## Toll contract

The operator's [2026 commercial-per-axle PDF](https://rodovias.motiva.com.br/content/dam/projetos/rodovias/canal-site-rodovias-grupoccr/pt/transparencia/autoban/pdf/transp_regulatoria_autoban_2026.pdf)
was visually checked against its 2026 block. Eight plaza rows retain original
north/south chainages and integer BRL cents. The calculation supports continuous
travel on **one of SP-330/SP-348, between km 20 and km 100**, loaded trucks with
2–9 billable axles, no intermediate exits, discounts or exemptions. It does not
infer crossings from the Valhalla map. Perus/Campo Limpo cost 1,450 cents per axle;
Valinhos/Itupeva cost 1,430. Exact-plaza endpoints are rejected as ambiguous.

The [operator's effective-date notice](https://rodovias.motiva.com.br/autoban/noticias/2026/junho/novas-tarifas-de-pedagio-entram-em-vigor-no-dia-1--de-julho/)
sets 2026-07-01. The snapshot was reviewed on 2026-11-20; dates outside that
reviewed interval return an unavailable price (`null`), never a free trip.
The default API/UI scenario explicitly uses the review date. This is a dated
estimate, not a live-price promise. JSON keeps currency and integer-cent amounts.

## Selected daytime duty policy

For a single employed freight driver, [CTB 67-C](https://www.planalto.gov.br/ccivil_03/leis/l9503compilado.htm)
informs the 330-minute driving-block ceiling and 30-minute driving pauses.
[CLT 235-C](https://www.planalto.gov.br/ccivil_03/decreto-lei/del5452compilado.htm)
informs 480 work minutes, or up to 600 when two overtime hours are explicitly
authorized. The simulator conservatively inserts one full 60-minute meal even
for short trips, with work after the meal. This is a planning policy, not a
claim that every short shift legally requires that exact meal duration.

[STF ADI 5322](https://noticias.stf.jus.br/postsnoticias/stf-invalida-dispositivos-da-lei-dos-caminhoneiros-sobre-tempo-de-espera-jornada-e-descanso/)
is reflected by counting loading/waiting as work and requiring a declared
uninterrupted prior daily rest of 660 minutes. An elapsed shift over 780 minutes
is flagged because it leaves less than eleven hours in a 24-hour cycle. A
loading/waiting activity never masquerades as a qualifying driving break.

Inputs for earlier driving/work belong to the same shift; prior daily rest is
before that shift. Timeline offsets start at shift start, not trip departure.
Earlier continuous driving reduces the next driving block's remaining capacity.
The display includes every work/break interval. Invalid input is rejected;
exceeded selected limits are flagged. Night/multi-day context requires separate
review. This is not payroll, tachograph verification, weekly-rest validation,
a legal opinion or evidence that a particular stopping place is safe/available.
Every result has `dispatch_authorized: false`, including apparently feasible ones.
No driver identity or uploaded log is collected. The API is stateless; the dashboard
keeps the last scenario only in session memory. Nothing is written to scenario
files or sent to a routing provider.

## Reviewed example and tests

| Declared example input/output | Value |
| --- | --- |
| Highway / chainage / direction | SP-330 / km 20 to 100 / north |
| Loaded billable axles | 2 |
| Toll crossings | Perus + Valinhos |
| Toll estimate, review date 2026-11-20 | BRL 57.60 |
| Driving / loading / waiting / delivery | 120 / 30 / 60 / 30 minutes |
| Work including waiting | 240 minutes |
| Meal / total shift elapsed | 60 / 300 minutes |
| Previous uninterrupted rest | 660 declared minutes |

These are explicitly **synthetic planning inputs**, not an observed company
operation or a travel-time guarantee. [Portable example](examples/trip_planning.json)
includes the full timeline, amounts, limitations and source references.
Tests cover directional Valinhos chainage, ambiguous endpoints, zero crossed
plazas versus unknown prices, work/overtime boundaries, missing prior rest,
continuous-driving carryover, long/night scenarios, permissions and failed audits.

## API and source maintenance

```text
GET /api/brazil/trip-planning?highway=SP-330&origin_km=20&destination_km=100&axles=2
GET /api/brazil/trip-planning?waiting_minutes=421&overtime_authorized=true
GET /api/brazil/trip-planning?as_of=2026-11-21
```

The OpenAPI document lists all bounds. Malformed inputs return 422; unavailable
or inconsistent reviewed rules return 503. Existing analytics permissions apply.
The same pinned rules are bundled in the hosted image and recovery archive.

A [weekly audit](../.github/workflows/audit-trip-tariffs.yml) checks the fixed
operator PDF on Monday at 10:07 UTC (07:07 Sao Paulo), with a 1-MiB limit,
30-second request timeout, no redirects and a three-minute job timeout. Changed,
unchanged and failure reports are retained for fourteen days, separately per run
attempt. Prices and review dates are never promoted automatically. The audit
covers tariff-PDF bytes only: legal sources, exceptions and actual operating
records still require separate review. Revisions must be sourced, reviewed,
tested and published through CI before expanding the accepted date interval.
