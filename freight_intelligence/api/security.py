"""Optional API-key authentication, configured when the app is created."""

import hashlib
import json
import os
import secrets
from pathlib import Path

from fastapi import Depends, HTTPException, Request, Security
from fastapi.security import APIKeyHeader

ROUTE_PERMISSIONS = {
    "/brazil/indicators": "analytics",
    "/brazil/gas-movements": "analytics",
    "/brazil/water-freight": "analytics",
    "/brazil/road-flows": "analytics",
    "/brazil/road-monthly": "analytics",
    "/ready": "analytics",
    "/annual-kpis": "analytics",
    "/annual-forecast": "analytics",
    "/transport-plan": "transport",
    "/transport-plan/nodes": "transport",
    "/temporal-evaluation": "evaluation",
    "/temporal-evaluation/predictions": "evaluation",
}


def load_users(path):
    try:
        file = Path(path)
        if file.stat().st_size > 65536:
            raise ValueError("User configuration exceeds size limit")
        data = json.loads(file.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or set(data) != {"users"}:
            raise ValueError("Expected users")
        users = data["users"]
        if not isinstance(users, list) or not 1 <= len(users) <= 100:
            raise ValueError("Expected 1-100 users")
        ids, hashes = set(), set()
        for user in users:
            if not isinstance(user, dict) or set(user) != {"id", "key_sha256", "enabled", "permissions"}:
                raise ValueError("Invalid user schema")
            identity, digest = user["id"], user["key_sha256"]
            if not isinstance(identity, str) or not identity.strip() or len(identity) > 100:
                raise ValueError("Invalid user id")
            if not isinstance(digest, str) or len(digest) != 64 or any(
                char not in "0123456789abcdef" for char in digest
            ):
                raise ValueError("Invalid key hash")
            permissions = user["permissions"]
            if type(user["enabled"]) is not bool or not isinstance(permissions, list):
                raise ValueError("Invalid enabled/permissions")
            if any(item not in ("analytics", "transport", "evaluation") for item in permissions):
                raise ValueError("Unknown permission")
            if identity in ids or digest in hashes:
                raise ValueError("Duplicate user or key")
            ids.add(identity)
            hashes.add(digest)
        return users
    except (OSError, ValueError, TypeError) as error:
        raise ValueError("Invalid LOGINEXUS_API_USERS_FILE configuration") from error


def authentication_dependencies():
    flag = os.environ.get("LOGINEXUS_REQUIRE_AUTH", "false").lower()
    if flag not in {"true", "false"}:
        raise ValueError("LOGINEXUS_REQUIRE_AUTH must be true or false")
    key = os.environ.get("LOGINEXUS_API_KEY", "")
    users_file = os.environ.get("LOGINEXUS_API_USERS_FILE", "")
    if key and users_file:
        raise ValueError("Configure a shared key or user file, not both")
    users = load_users(users_file) if users_file else None
    if key and (
        len(key) < 32
        or not key.isascii()
        or not key.isprintable()
        or any(character.isspace() for character in key)
    ):
        raise ValueError(
            "LOGINEXUS_API_KEY must have at least 32 printable ASCII characters without spaces"
        )
    if flag == "true" and not key and users is None:
        raise ValueError("LOGINEXUS_REQUIRE_AUTH requires LOGINEXUS_API_KEY")
    if not key and users is None:
        return []

    header = APIKeyHeader(name="X-API-Key", scheme_name="LogiNexusAPIKey", auto_error=False)

    def require_key(request: Request, provided: str | None = Security(header)):
        principal = None
        if provided is not None and users is not None:
            digest = hashlib.sha256(provided.encode("utf-8")).hexdigest()
            for user in users:
                if secrets.compare_digest(digest, user["key_sha256"]) and user["enabled"]:
                    principal = user
        authenticated = principal is not None if users is not None else (
            provided is not None and secrets.compare_digest(provided.encode("utf-8"), key.encode("utf-8"))
        )
        if not authenticated:
            raise HTTPException(
                status_code=401,
                detail="Invalid or missing API key",
                headers={"WWW-Authenticate": "APIKey"},
            )
        if principal is not None:
            # The matched route is independent of a deployment's mount/root prefix.
            route = request.scope.get("route")
            permission = ROUTE_PERMISSIONS.get(getattr(route, "path", None))
            # New protected routes must be assigned explicitly rather than inheriting access.
            if permission is None or permission not in principal["permissions"]:
                raise HTTPException(status_code=403, detail="Permission denied")
            request.state.principal_id = principal["id"]

    return [Depends(require_key)]
