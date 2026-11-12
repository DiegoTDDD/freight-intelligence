"""Check proxy-to-API permissions on disposable loopback-only HTTP infrastructure."""

import argparse
import hashlib
import json
import secrets
import subprocess
import time
import urllib.error
import uuid
from pathlib import Path
from tempfile import TemporaryDirectory

from check_api_container import docker, request

PROXY_IMAGE = "caddy:2@sha256:9c1b76fb701c1f77383d3124d9f626e38bcf83bc1255ed47475d4f2420701d03"


def check_proxy(api_image):
    suffix = uuid.uuid4().hex[:12]
    network, api, proxy = (f"loginexus-proxy-{suffix}-{kind}" for kind in ("net", "api", "proxy"))
    edge_network = f"loginexus-proxy-{suffix}-edge"
    analytics_key, transport_key = (secrets.token_urlsafe(32) for _ in range(2))
    with TemporaryDirectory(prefix="loginexus-proxy-") as directory:
        registry = Path(directory) / "users.json"
        registry.write_text(json.dumps({"users": [
            {"id": identity, "key_sha256": hashlib.sha256(key.encode()).hexdigest(),
             "enabled": True, "permissions": permissions}
            for identity, key, permissions in (
                ("analyst", analytics_key, ["analytics"]),
                ("planner", transport_key, ["transport"]),
            )
        ]}), encoding="utf-8")
        config = Path(directory) / "Caddyfile"
        config.write_text("{\n\tadmin off\n}\nhttp://:8080 {\n\treverse_proxy api:8000\n}\n")
        try:
            docker("network", "create", "--internal", network)
            docker("network", "create", edge_network)
            docker("run", "-d", "--name", api, "--network", network, "--network-alias", "api",
                   "--read-only", "--tmpfs", "/tmp", "--cap-drop", "ALL",
                   "--security-opt", "no-new-privileges:true", "--mount",
                   f"type=bind,source={registry.resolve()},target=/run/users.json,readonly",
                   "--env", "LOGINEXUS_API_USERS_FILE=/run/users.json",
                   "--env", "LOGINEXUS_REQUIRE_AUTH=true", api_image)
            docker("run", "-d", "--name", proxy, "--network", edge_network, "--read-only",
                   "--tmpfs", "/tmp", "--tmpfs", "/data", "--tmpfs", "/config",
                   "--cap-drop", "ALL", "--security-opt", "no-new-privileges:true",
                   "--publish", "127.0.0.1::8080", "--mount",
                   f"type=bind,source={config.resolve()},target=/etc/caddy/Caddyfile,readonly",
                   PROXY_IMAGE)
            docker("network", "connect", network, proxy)
            port = docker("port", proxy, "8080/tcp").rsplit(":", 1)[1]
            base = f"http://127.0.0.1:{port}"
            deadline = time.monotonic() + 30
            while True:
                try:
                    if request(base, "/health")[0] == 200:
                        break
                except (urllib.error.URLError, TimeoutError, ConnectionError):
                    pass
                if time.monotonic() > deadline:
                    raise RuntimeError("Temporary proxy/API path did not become healthy")
                time.sleep(0.25)
            assert request(base, "/annual-kpis")[0] == 401
            assert request(base, "/annual-kpis", "incorrect")[0] == 401
            assert request(base, "/annual-kpis", analytics_key)[0] == 503
            assert request(base, "/transport-plan", analytics_key)[0] == 403
            assert request(base, "/transport-plan", transport_key)[0] == 503
            assert request(base, "/annual-kpis", transport_key)[0] == 403
            assert request(base, "/docs")[0] == 200
            schema = request(base, "/openapi.json")[1]
            assert analytics_key not in schema and transport_key not in schema
            api_ports = json.loads(docker("inspect", api))[0]["NetworkSettings"]["Ports"]
            assert all(value is None for value in api_ports.values())
            print("Proxy/API integration passed: headers, scoped permissions and no direct API port.")
        finally:
            for name in (proxy, api):
                subprocess.run(["docker", "rm", "-f", name], capture_output=True, timeout=30, check=False)
            subprocess.run(["docker", "network", "rm", network], capture_output=True, timeout=30, check=False)
            subprocess.run(["docker", "network", "rm", edge_network], capture_output=True, timeout=30, check=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", default="loginexus-api:validated")
    args = parser.parse_args()
    check_proxy(args.image)


if __name__ == "__main__":
    main()
