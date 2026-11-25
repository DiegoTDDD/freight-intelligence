"""Independent, stateless public API; no Streamlit server or raw-data ingestion."""

import hashlib
import os
import re
from pathlib import Path

from fastapi import HTTPException
from fastapi.responses import RedirectResponse

from freight_intelligence.api.public_snapshot import PROJECT, snapshot_api


def create_public_app(root=None):
    root = Path(root) if root is not None else PROJECT / "deployment/preview_data"
    app = snapshot_api(root)

    @app.get("/", include_in_schema=False)
    def home():
        return RedirectResponse("/docs")

    @app.get("/version")
    def version():
        try:
            manifest = root / "snapshot_manifest.json"
            if manifest.stat().st_size > 131072:
                raise ValueError("Oversized snapshot manifest")
            digest = hashlib.sha256(manifest.read_bytes()).hexdigest()
        except (OSError, ValueError) as error:
            raise HTTPException(status_code=503, detail="Public snapshot manifest unavailable") from error
        revision = os.environ.get("RENDER_GIT_COMMIT", os.environ.get("LOGINEXUS_BUILD_REVISION", "unknown"))
        return {"service": "loginexus-public-api", "revision": revision if re.fullmatch(r"[0-9a-f]{40}", revision) else "unknown",
                "snapshot_manifest_sha256": digest, "hosting": "independent_api_process"}

    return app


app = create_public_app()
