# Operating allocation comparison — X04-T01

The local command validates declared observed flows and compares them with the
minimum-cost allocation under the **same supplied costs and constraints**.
It checks every arc ID, finite nonnegative flows, capacities and node balances.
Zero-flow arcs must be explicit. Parallel arcs and transshipment are supported.

```bash
python -m freight_intelligence.optimization.operating_comparison --case docs/examples/operating_comparison_case.json --output comparison.json
```

The committed example is synthetic: observed-allocation model cost **290**, optimal
model cost **190**, modeled opportunity **100** (approximately **34.48%**). These
are teaching values, not company savings. Reports contain input SHA-256, period,
units, declared provenance and per-arc flows. The command preserves input and
existing report files. Invalid input produces no report. No upload is performed.

## Input contract

Use the [complete example](examples/operating_comparison_case.json):

- `scenario`: the existing [network contract](transport_optimization.md#scenario-contract).
- `period_start`, `period_end`: ISO calendar dates, start no later than end.
  All balances, capacities, costs and observations must apply to this period.
- `observed_flows`: one `{arc_id, flow}` object for every scenario arc.
- `provenance`: `kind` (`synthetic` or `declared_operating_records`) and a nonempty
  `reference` identifying a locally retained source. Use anonymized references;
  do not commit customer records, invoices or confidential networks.

The caller must align currency, period, units and cost basis. A source label cannot
authenticate records or disclose omitted constraints. `source_authenticity` stays
`not_independently_verified`, including for declared operating records. The hash
identifies the input case; it does not authenticate its underlying source records.

## Results and remaining acceptance

`observed_allocation_model_cost` re-prices observed flows with scenario unit costs;
it is not an invoice total. `modeled_opportunity` is the difference from
`optimized_model_cost`. Its percentage is null for a zero-cost baseline.
`realized_savings` is always null. Flows are divisible, and vehicle schedules or
other omitted constraints are outside the comparison.

**X04-T01 is implemented; X04 remains open.** Completion still needs authenticated
operating inputs, reviewed constraints/cost basis and comparable realized outcomes
from an actual operation. Synthetic cases and provenance labels cannot close it.
