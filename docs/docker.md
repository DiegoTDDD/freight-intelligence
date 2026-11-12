# Local API with Docker

Docker Desktop must be running with its Linux engine enabled. The container serves existing outputs; it never runs the pipeline or fits models.

From the repository root, after generating Gold and the optional annual forecast:

```bash
docker compose up --build -d --wait
```

Open `http://127.0.0.1:8000/docs`. The local port can be changed with the `LOGINEXUS_PORT` environment variable. For example, in PowerShell:

```powershell
$env:LOGINEXUS_PORT = "8001"
docker compose up -d --wait
```

The image contains only the Python package, package configuration and README. Raw data, Silver, Gold, models, optimization outputs, Git history and environment files are excluded from the build context. Existing `data/gold/faf5/`, `models/` and `artifacts/` directories are mounted read-only. Compose fails if any source directory is absent, rather than silently creating it. If optional outputs do not exist yet, create empty `models/` and `artifacts/` directories. Their forecast/transport endpoints then return HTTP 503 while annual indicators remain available.

The process runs as user 10001, with a read-only container filesystem and writable temporary storage. The service is exposed only on the host's loopback address. This is a local runtime, not a public deployment.

The health check uses `/health` to confirm the process responds. Data availability is checked separately through `/ready`. A healthy container can still return HTTP 503 for missing or invalid analytical data.

Inspect or stop this project's service without deleting source data:

```bash
docker compose ps
docker compose logs --tail 50 api
docker compose stop
```

Restart it with `docker compose up -d --wait`. Rebuild after source changes because application code is copied into the image, not mounted from the host. The API runtime uses a version manifest and a pinned Python base image digest. See [runtime dependency management](runtime_dependencies.md) for the target platform, verification and update process.

Reference: [Docker Compose service configuration](https://docs.docker.com/reference/compose-file/services/).

## Individual-user Compose override

`compose.users.yaml` provides an opt-in, reviewable configuration for the individual-key
registry. It does not alter the existing service unless explicitly included in an `up` command.
Set `LOGINEXUS_USERS_FILE` to the private registry's absolute host path, then preview:

```bash
docker compose -f compose.yaml -f compose.users.yaml config --quiet
```

The override requires authentication, clears the shared key to avoid ambiguous modes, and
mounts the registry read-only at `/run/loginexus/users.json`. A missing path variable fails
configuration; a missing host file fails startup instead of creating a directory. The base
configuration's loopback port, read-only data mounts and restricted runtime are retained.
Actual startup would use the same file arguments with `up --build -d --wait`; do this only
when intentionally applying the new configuration. To change/revoke a user, update the
registry and recreate the container using both Compose files. Keep registry permissions
restricted to authorized operators. No working keys are shipped.

`python scripts/check_users_compose.py` validates configuration merging and the required
path without starting a service or needing real credentials. It captures configuration
output without printing secrets. This is configuration validation, not a production deploy.
