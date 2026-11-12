# Truck-aware routing

The real-road workspace offers separate OSRM car-reference and Valhalla truck
engines. The truck request uses `costing=truck` and sends explicit loaded gross
weight (metric tonnes), height/width/length (metres), maximum axle load (tonnes),
axle count and hazardous-material status. Example rigid and articulated profiles
are editable demonstration inputs, not legal vehicle categories or certificates.

Truck access is not relaxed: `hgv_no_access_penalty=43200`; access, one-way,
closure and other restriction-ignore flags remain false. Invalid profiles fail
before any network access. Provider warnings about ignored/clamped parameters
fail closed. Responses must contain a valid kilometre summary, consistent leg
totals, bounded geometry, instructions and road endpoints within 1 km of the
submitted coordinates. Failures never substitute an OSRM car route.

The saved São Paulo–Campinas truck example was requested on 2026-11-12 with the
16-tonne rigid demonstration profile. It returned 98.771 km and 96.71705 estimated
minutes. This differs from the saved car route, but that difference alone does
not establish restriction completeness or legal suitability. GeoJSON preserves
the vehicle, inputs, request/response hashes, retrieval time and limitations.
The route manifest separately verifies the exported file bytes.

## External service and availability

The only live endpoint is the fixed FOSSGIS Valhalla demo URL; browser input cannot
select another host. Requests require explicit coordinate/profile sharing consent,
are cached for 24 hours (64 entries), have a 20-second timeout, a 2-MiB response
limit, no redirects/retries, at least two seconds between calls and at most 100
uncached attempts per UTC day per server process. Restarts reset the in-memory
counter; this is a single-process portfolio deployment, not a distributed quota.
The app identifies itself with `X-Client-Id` and a project-bearing User-Agent.

Live requests are disabled unless the operator sets
`LOGINEXUS_TRUCK_DEMO_ENABLED=true`. The provider asks published applications to
notify its maintainers in GitHub Discussions. Owner approval for that external
notice is pending; the saved demonstration and local integration remain usable.

OpenStreetMap may omit or contain stale truck restrictions. This integration does
not provide legal clearance, live traffic, current closure verification, toll
prices, driver-hours compliance or navigation certification. A company dispatch
deployment would require verified regional data, operational procedures and an
appropriate provider/service agreement.

Primary references:

- [Valhalla truck costing and options](https://valhalla.github.io/valhalla/api/route/api-reference/)
- [Valhalla demo policy and client identification](https://github.com/valhalla/valhalla/blob/master/README.md)
- [OpenStreetMap attribution](https://www.openstreetmap.org/copyright)
