"""Validate deployment template without starting a proxy or contacting certificate issuers."""

import json
import os
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory


def main():
    with TemporaryDirectory(prefix="loginexus-production-") as directory:
        empty = Path(directory) / "empty.env"
        empty.write_text("")
        registry = Path(directory) / "users.json"
        registry.write_text('{"users": []}')
        environment = {**os.environ, "LOGINEXUS_USERS_FILE": str(registry),
                       "LOGINEXUS_DOMAIN": "example.invalid", "LOGINEXUS_BIND_ADDRESS": "127.0.0.1"}
        command = ["docker", "compose", "--env-file", str(empty), "-f", "compose.yaml",
                   "-f", "compose.production.yaml", "config", "--format", "json"]
        result = subprocess.run(command, env=environment, capture_output=True, text=True,
                                check=True, timeout=30)
        config = json.loads(result.stdout)
        api, proxy = config["services"]["api"], config["services"]["proxy"]
        assert not api.get("ports")
        assert api["environment"]["LOGINEXUS_REQUIRE_AUTH"] == "true"
        assert api["environment"]["LOGINEXUS_API_KEY"] == ""
        assert api["environment"]["LOGINEXUS_API_USERS_FILE"] == "/run/loginexus/users.json"
        assert set(api["networks"]) == {"backend"}
        assert config["networks"]["backend"]["internal"]
        assert all(port["host_ip"] == "127.0.0.1" for port in proxy["ports"])
        assert "@sha256:" in proxy["image"]
        assert all(mount.get("read_only") for mount in api["volumes"])
        environment.pop("LOGINEXUS_DOMAIN")
        missing = subprocess.run(command, env=environment, capture_output=True, text=True,
                                 check=False, timeout=30)
        assert missing.returncode != 0 and "LOGINEXUS_DOMAIN" in missing.stderr
    print("Deployment merge verified: no direct API port, required auth, internal backend; no deployment.")


if __name__ == "__main__":
    main()
