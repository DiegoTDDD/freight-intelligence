"""Check local and authenticated container modes without source data or saved secrets."""

import argparse
import hashlib
import json
import os
import secrets
import subprocess
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from tempfile import TemporaryDirectory


def docker(*arguments, environment=None):
    return subprocess.run(
        ["docker", *arguments],
        env=environment,
        capture_output=True,
        text=True,
        check=True,
        timeout=60,
    ).stdout.strip()


def request(base, path, key=None):
    headers = {"X-API-Key": key} if key is not None else {}
    try:
        with urllib.request.urlopen(
            urllib.request.Request(base + path, headers=headers), timeout=3
        ) as response:
            return response.status, response.read().decode()
    except urllib.error.HTTPError as error:
        return error.code, error.read().decode()


def check_mode(image, authenticated):
    name = "loginexus-check-" + uuid.uuid4().hex[:12]
    key = secrets.token_urlsafe(32) if authenticated else ""
    environment = {**os.environ, "LOGINEXUS_API_KEY": key}
    try:
        docker(
            "run",
            "-d",
            "--name",
            name,
            "--read-only",
            "--tmpfs",
            "/tmp",
            "--publish",
            "127.0.0.1::8000",
            "--env",
            "LOGINEXUS_API_KEY",
            "--env",
            f"LOGINEXUS_REQUIRE_AUTH={'true' if authenticated else 'false'}",
            image,
            environment=environment,
        )
        port = docker("port", name, "8000/tcp").rsplit(":", 1)[1]
        base = f"http://127.0.0.1:{port}"
        deadline = time.monotonic() + 30
        while True:
            try:
                status, _ = request(base, "/health")
                if status == 200:
                    break
            except (urllib.error.URLError, TimeoutError, ConnectionError):
                pass
            if time.monotonic() >= deadline:
                raise RuntimeError("Container did not become healthy")
            time.sleep(0.25)
        assert request(base, "/docs")[0] == 200
        status, schema = request(base, "/openapi.json")
        assert status == 200
        if key:
            assert key not in schema
        for path in (
            "/ready",
            "/annual-kpis",
            "/annual-forecast",
            "/transport-plan",
            "/transport-plan/nodes",
            "/temporal-evaluation",
            "/temporal-evaluation/predictions",
        ):
            expected = 401 if authenticated else 503
            assert request(base, path)[0] == expected, path
            if authenticated:
                assert request(base, path, "incorrect-key")[0] == 401, path
                assert request(base, path, key)[0] == 503, path
        if authenticated:
            assert "LogiNexusAPIKey" in json.loads(schema)["components"]["securitySchemes"]
        assert docker("exec", name, "id", "-u") == "10001"
        print(f"Container mode passed: {'authenticated' if authenticated else 'local'}")
    finally:
        subprocess.run(["docker", "rm", "-f", name], capture_output=True, timeout=30, check=False)


def check_users(image):
    name = "loginexus-users-" + uuid.uuid4().hex[:12]
    analytics, transport, disabled = (secrets.token_urlsafe(32) for _ in range(3))
    with TemporaryDirectory(prefix="loginexus-users-") as directory:
        registry = Path(directory) / "users.json"
        registry.write_text(json.dumps({"users": [
            {"id": identity, "key_sha256": hashlib.sha256(key.encode()).hexdigest(),
             "enabled": enabled, "permissions": permissions}
            for identity, key, enabled, permissions in (
                ("analyst", analytics, True, ["analytics"]),
                ("planner", transport, True, ["transport", "evaluation"]),
                ("disabled", disabled, False, ["analytics"]),
            )
        ]}), encoding="utf-8")
        try:
            docker(
                "run", "-d", "--name", name, "--read-only", "--tmpfs", "/tmp",
                "--publish", "127.0.0.1::8000", "--mount",
                f"type=bind,source={registry.resolve()},target=/run/loginexus-users.json,readonly",
                "--env", "LOGINEXUS_API_USERS_FILE=/run/loginexus-users.json",
                "--env", "LOGINEXUS_REQUIRE_AUTH=true", image,
            )
            port = docker("port", name, "8000/tcp").rsplit(":", 1)[1]
            base = f"http://127.0.0.1:{port}"
            deadline = time.monotonic() + 30
            while True:
                try:
                    if request(base, "/health")[0] == 200:
                        break
                except (urllib.error.URLError, TimeoutError, ConnectionError):
                    pass
                if time.monotonic() >= deadline:
                    raise RuntimeError("Users container did not become healthy")
                time.sleep(0.25)
            for endpoint in ("/annual-kpis", "/transport-plan", "/temporal-evaluation"):
                assert request(base, endpoint)[0] == 401
                assert request(base, endpoint, disabled)[0] == 401
            assert request(base, "/annual-kpis", analytics)[0] == 503
            assert request(base, "/transport-plan", analytics)[0] == 403
            assert request(base, "/annual-kpis", transport)[0] == 403
            assert request(base, "/transport-plan", transport)[0] == 503
            assert request(base, "/temporal-evaluation", transport)[0] == 503
            schema = request(base, "/openapi.json")[1]
            assert all(key not in schema for key in (analytics, transport, disabled))
            assert docker("exec", name, "id", "-u") == "10001"
            mounts = json.loads(docker("inspect", name))[0]["Mounts"]
            assert any(item["Destination"] == "/run/loginexus-users.json" and not item["RW"]
                       for item in mounts)
            print("Individual users passed: scoped access, disabled key and read-only registry.")
        finally:
            subprocess.run(["docker", "rm", "-f", name], capture_output=True, timeout=30, check=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", default="loginexus-api:local")
    args = parser.parse_args()
    check_mode(args.image, authenticated=False)
    check_mode(args.image, authenticated=True)
    check_users(args.image)
    result = subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "--env",
            "LOGINEXUS_REQUIRE_AUTH=true",
            "--env",
            "LOGINEXUS_API_KEY=",
            args.image,
        ],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode != 0
    assert "LOGINEXUS_REQUIRE_AUTH requires LOGINEXUS_API_KEY" in result.stderr
    print("Missing mandatory key prevented startup; no test credentials saved.")


if __name__ == "__main__":
    main()
