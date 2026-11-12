# Portfolio expansion: review and acceptance criteria

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

Implementation is under review. Local mounted API tests and the actual hosted
HTTP server passed; publication has not yet been performed for this expansion.

## Truck routing

- Use a genuine truck costing engine, with explicit editable demonstration profiles.
- Pass gross weight, dimensions, axle load/count and hazardous-material settings.
- Never substitute a car route or a synthetic line when the truck engine fails.
- Preserve geometry, maneuvers, provider provenance and vehicle inputs in exports.
- Bound request rate, response size, timeouts and coordinate transmission.
- Document map restriction gaps, missing live traffic and provider availability.
- Observe provider usage policy; a free demo does not supply operational certification.

Provider research is in progress; current published routing is still a car reference.

## Brazilian modes

- Cover road, rail, water, air and pipeline as distinct datasets/indicators.
- Record official source, reference period, unit, scope and observed/estimated status.
- Preserve raw-source hashes and reproducible preparation wherever available.
- Do not sum incompatible units, confuse port throughput with transport work,
  or claim complete national coverage from partial concession/operator records.
- Validate transformations, displayed values, downloads and API contracts.

Official source discovery is in progress. The currently shipped detailed Brazilian
dataset remains ANTT railway reports; other modes are not yet delivered.

Passing tests reduces risk; it does not prove that software or source data contain
zero errors. No commercial completeness claim is made by this expansion plan.
