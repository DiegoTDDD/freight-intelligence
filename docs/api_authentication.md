# API-key authentication

Authentication is optional for the documented loopback-only local setup. When `LOGINEXUS_API_KEY` is set, all data endpoints require the matching `X-API-Key` header, including `/ready`. The key must have at least 32 printable ASCII characters and no whitespace. Generate a random key rather than choosing a password.

`LOGINEXUS_REQUIRE_AUTH=true` additionally prevents startup when no key is configured. Its accepted values are `true` and `false` (case insensitive). A malformed configured key prevents startup even when the flag is false. An empty key with the default false flag preserves anonymous local access.

## Docker Compose configuration

Copy `.env.example` to `.env`, generate a key using `python -c "import secrets; print(secrets.token_urlsafe(32))"`, and set:

```text
LOGINEXUS_REQUIRE_AUTH=true
LOGINEXUS_API_KEY=<your generated key>
```

`.env` is excluded from Git and the image build context. The template contains no credentials. Compose reads this configuration and passes the two variables to the container. Apply changes with `docker compose up -d --wait`; changing or removing a key requires container recreation. If an existing `.env` is present, edit its relevant values rather than overwriting it.

For a direct Uvicorn launch, set the same variables in the process environment. Plain Uvicorn does not automatically load the repository's `.env`; restart the process after changing configuration.

## Requests and documentation

Use the **Authorize** button in `/docs` to supply the key. It is sent as a header, never a URL parameter. Missing and incorrect credentials both return HTTP 401 with the same generic response. A valid key permits the normal endpoint behavior, including HTTP 503 when a dataset is unavailable. Keys are compared using `secrets.compare_digest`; values are not included in error messages or OpenAPI.

`/health`, `/docs`, `/redoc` and `/openapi.json` remain public. They expose process status and interface definitions, not analytical rows. `/health` remains usable by Docker's health check when authentication is enabled. All analytical routes are grouped under the shared authentication dependency so the readiness and transport endpoints follow the same rules.

The shared-key mode uses one credential. Optional individual keys with read permissions are described below; neither mode is a full identity provider. Public hosting still requires a deployment target, HTTPS and a suitable secret delivery mechanism. Docker administrators can inspect container environment variables; an environment variable is not a secret vault. Those deployment choices are outside this local milestone.

Reference: [FastAPI security dependencies](https://fastapi.tiangolo.com/reference/security/).

## Repeatable container checks

After building the image, run:

```bash
python scripts/check_api_container.py --image loginexus-api:local
```

The check uses temporary containers and a generated in-memory key. It verifies local access, protected routes, public health/documentation, valid and invalid credentials, non-root execution and startup refusal without a mandatory key. It does not mount project data, save credentials or alter the running Compose service. Temporary containers are removed afterwards. CI runs the same check against its freshly built image.

## Individual API keys and read permissions

For a direct local Uvicorn process, set `LOGINEXUS_API_USERS_FILE` to a private JSON
registry and unset `LOGINEXUS_API_KEY`. Both modes at once fail startup. Set
`LOGINEXUS_REQUIRE_AUTH=true` for explicit mandatory authentication. A configured users
file enforces authentication even when the flag is false; missing, malformed, oversized
(above 64 KiB), empty or duplicate registries fail startup. There can be at most 100 users.

```json
{
  "users": [
    {
      "id": "analyst",
      "key_sha256": "0000000000000000000000000000000000000000000000000000000000000000",
      "enabled": false,
      "permissions": ["analytics"]
    }
  ]
}
```

This disabled example contains no working credential. Generate a long random token with
`secrets.token_urlsafe(32)` and store only its lowercase SHA-256 hex digest in the registry.
Deliver the actual token privately to its intended holder. This is a random API token,
not a human password; SHA-256 here is not a password-storage scheme. Never commit tokens
or user registries. A `secrets/` directory is ignored by Git; keep it access-controlled.
The Docker build allowlist excludes it. Avoid printing real tokens in shared logs.

All clients still use the `X-API-Key` header. Each user has an independent token digest,
unique id, boolean `enabled`, and a list of these permissions:

| Permission | Endpoints |
| --- | --- |
| `analytics` | `/ready`, `/annual-kpis`, `/annual-forecast` |
| `transport` | `/transport-plan`, `/transport-plan/nodes` |
| `evaluation` | `/temporal-evaluation`, `/temporal-evaluation/predictions` |

An empty permission list grants no data access. Invalid or disabled credentials return 401;
a recognized credential without the required permission returns 403. Health and API docs
remain public. The authenticated id is available internally as `request.state.principal_id`;
tokens and digests are not returned in data responses or OpenAPI. A copied digest is not
itself the client token. This does not implement tenant-specific rows or ownership rules.

Configuration is loaded when the application is created. Disabling a user, rotating their
hash, or changing permissions requires restarting every worker; existing processes retain
their configuration. Never assume editing the registry immediately revokes a live token.
The existing Compose service is unchanged and still supports its shared-key configuration.
Using a registry in a container requires an explicitly configured read-only private mount
and the environment path inside that container; no credentials are included in the image.

This adds local per-user read permissions. Public production deployment, HTTPS, secret
provisioning, audit storage, rate limits and centralized identity remain separate work.


The repeatable container checker also verifies individual-user authentication with an
empty data directory. It creates a temporary registry of token hashes, mounts it read-only,
checks allowed/forbidden permissions and a disabled user, verifies non-root execution,
and removes the temporary container/registry afterwards. CI runs this with the new image;
it never updates the existing local Compose service.

### Mounted APIs and new routes

Individual-user permissions are resolved from the matched API route, not the external URL
prefix. Mounting the app under `/api` therefore preserves the transport/evaluation boundaries.
New protected routes must be added explicitly to `ROUTE_PERMISSIONS` in `api/security.py`;
unclassified routes return 403 for individual-user keys. Shared-key mode retains its single
credential policy. Regression tests cover a mounted app and an unclassified protected route.
