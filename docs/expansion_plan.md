# Portfolio expansion: review and acceptance criteria

Current delivery and outstanding work: [status.md](status.md).

Owner clarification: this is a personal portfolio project, with professional
engineering quality. It is not being commissioned for live fleet dispatch.
English remains the default interface language. No paid hosting or API contract
is authorized.

## Public API

- Keep the dashboard URL working and expose documented read-only HTTP endpoints.
- Serve reviewed public snapshots only; never fall back to local/private outputs.
- Preserve configured authentication and per-user permission checks under mounting.
- Validate missing data, invalid queries, OpenAPI prefix and actual container startup.
- Review and pass CI before deployment; verify the published endpoints afterward.

Published revision `424216e` passed all five CI checks. Public health, OpenAPI
documentation and annual indicators were verified over HTTPS. Later revisions
published the Brazilian indicator and gas-movement endpoints, verified against
their reviewed snapshots. The API shares hosting with the dashboard.

## Truck routing

- Use a genuine truck costing engine, with explicit editable demonstration profiles.
- Pass gross weight, dimensions, axle load/count and hazardous-material settings.
- Never substitute a car route or a synthetic line when the truck engine fails.
- Preserve geometry, maneuvers, provider provenance and vehicle inputs in exports.
- Bound request rate, response size, timeouts and coordinate transmission.
- Document map restriction gaps, missing live traffic and provider availability.
- Observe provider usage policy; a free demo does not supply operational certification.

Valhalla integration and editable profiles are published; engine and UI
contract tests passed. A new live query was verified through the public dashboard.
One real truck request
returned 98.771 km for the saved rigid-truck example. Public live use remains
controlled by an operator switch. The owner approved the provider notice, which
was published as [Valhalla discussion #6503](https://github.com/valhalla/valhalla/discussions/6503)
on 2026-11-13; the hosting image enables live requests after this notice.

## Brazilian modes

- Cover road, rail, water, air and pipeline as distinct datasets/indicators.
- Record official source, reference period, unit, scope and observed/estimated status.
- Preserve raw-source hashes and reproducible preparation wherever available.
- Do not sum incompatible units, confuse port throughput with transport work,
  or claim complete national coverage from partial concession/operator records.
- Validate transformations, displayed values, downloads and API contracts.

The reviewed expansion contains 119 annual records across all five modes, plus
120 ANP monthly gas operator/direction records, with
integrity validation, UI filtering, CSV export and a read-only API endpoint.
Road coverage includes fleet history, MDF-e cargo trips and derived transport
work, excluding unresolved road tonnage. National shipment coverage
for every mode remains incomplete; see [precise coverage and source issues](brazil_modes.md).

Passing tests reduces risk; it does not prove that software or source data contain
zero errors. No commercial completeness claim is made by this expansion plan.
