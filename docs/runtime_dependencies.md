# Versioned API runtime

The Docker API uses `requirements/api-linux-py313.lock`, captured from the tested Linux x86_64 / CPython 3.13 image. It pins the runtime's direct and transitive Python dependencies. The Python base image is also pinned to a registry digest in `Dockerfile`.

Dependency installation occupies a separate build layer before application code is copied. Code-only edits reuse that layer. A BuildKit pip cache further reduces repeated downloads. The application is installed with `--no-deps` after the pinned dependencies; `pip check` and the runtime manifest verifier then run as part of the build.

```bash
docker compose build api
docker run --rm loginexus-api:local python -m freight_intelligence.utils.runtime_lock
python scripts/check_api_container.py --image loginexus-api:local
```

The verifier rejects missing packages, version differences and extra unpinned runtime packages. Package-name punctuation/case is normalized. The application itself and pip/setuptools/wheel are excluded from the runtime comparison. Invalid/ambiguous manifest entries and duplicate normalized names are rejected. CI runs this verification and the API/authentication container checks on the newly built image.

This lock targets the Linux API container, not the Windows Conda environment, development tools or optional XGBoost/OR-Tools integrations. Development installation requirements in `pyproject.toml` retain their compatibility ranges. Unit tests check that every directly declared base/API requirement is represented in the runtime lock and that its pin satisfies the declared range.

## Updating deliberately

Update pins in a separate reviewable change. Resolve desired versions in a disposable Linux x86_64 / CPython 3.13 environment, run dependency consistency checks, regenerate its noneditable runtime package list, then rebuild and validate the API container before accepting the resulting manifest. Keep the manifest synchronized when changing base/API dependencies in `pyproject.toml`. Changing the base image digest likewise requires rebuilding and validation.

The manifest fixes package versions; it does not currently include wheel hashes. Build tools are resolved separately during the editable application build. This provides runtime version consistency rather than a claim of byte-identical image builds or a vulnerability-free dependency set.
