# Review-only HTTPS deployment configuration

`compose.production.yaml` is a portable draft for a future Docker host. It has not been
deployed, and no server/domain, DNS, firewall or certificate request has been configured.
The default proxy bindings remain `127.0.0.1`; do not interpret a validated template as a
public production service or a complete operational/security assessment.

It merges with the base Compose file and requires `LOGINEXUS_USERS_FILE` and
`LOGINEXUS_DOMAIN`. The shared key is cleared and individual-key authentication is mandatory.
The API has no host-published port and joins only an internal backend network. Caddy joins
that backend and an edge network, forwarding requests to the API; the dashboard is not
published. Its official image is pinned by digest, resolved on 2026-11-12. Its administration
API is disabled. Certificates/config use named volumes; the certificate volume contains
private keys and must be protected and backed up appropriately.

## Review without starting anything

```bash
python scripts/check_production_config.py
```

This uses a temporary empty environment file and dummy registry/domain, validates Compose
merging, asserts API port removal, required authentication, internal backend and loopback
proxy bindings, and checks refusal when the domain is absent. No service is started and no
credentials or certificates are created. CI runs the same check. Real registry validation
still happens during API startup; the empty dummy registry is only for configuration parsing.

To review your intended deployment variables locally:

```bash
docker compose -f compose.yaml -f compose.production.yaml config --quiet
```

Full `config` output may contain private configuration, so do not publish it. Actual
`up` is a deployment and remains subject to the user's authorization. No `up` is included
in the automated validation. A future public bind would require an explicitly chosen
`LOGINEXUS_BIND_ADDRESS`, reviewed host/firewall settings, actual DNS pointing to that host,
and reachable HTTP/HTTPS ports for certificate validation. Loopback defaults will not make
a public domain reachable. Do not use a URL scheme or path as the domain value.

Caddy's automatic HTTPS requires suitable DNS, ports and persistent writable certificate
storage. See [official HTTPS requirements](https://caddyserver.com/docs/automatic-https).
The explicit removal of the base API port uses Compose's `!reset` merge semantics;
see [Docker's merge documentation](https://docs.docker.com/reference/compose-file/merge/).
The default `compose.yaml` and `compose.users.yaml` remain local configurations.

This draft does not choose a hosting vendor, provide centralized identity, enforce rate
limits, configure external monitoring/backups, or establish disaster-recovery policies.
Those depend on the real target and requirements. Do not publish the service until these
choices and the private registry are reviewed. Key changes require recreating API workers.

## Disposable proxy/API integration check

```bash
python scripts/check_proxy_runtime.py --image loginexus-api:validated
```

This checks request forwarding and user permissions through the pinned Caddy proxy with
temporary containers, an isolated internal network and random in-memory credentials. Only
a random loopback HTTP port is published; the API has no direct host port. It checks missing
and invalid credentials, scoped 403 responses, permitted requests reaching normal 503
responses on empty datasets, public health/docs and absence of credentials from OpenAPI.
Cleanup removes only the temporary named containers/network and registry.

The integration test intentionally uses HTTP on localhost. It neither validates a real
public TLS certificate nor obtains one, changes DNS, modifies an existing service or
publishes to the internet. Certificate issuance and external HTTPS remain untested until
an actual authorized host/domain is available. CI runs this check after building its API.
