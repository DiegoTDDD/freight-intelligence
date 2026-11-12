"""Validate the opt-in users Compose merge without starting services or loading .env."""

import json
import os
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory


def main():
    with TemporaryDirectory(prefix="loginexus-compose-") as directory:
        empty_env = Path(directory) / "empty.env"
        empty_env.write_text("")
        command = ["docker", "compose", "--env-file", str(empty_env), "-f", "compose.yaml",
                   "-f", "compose.users.yaml", "config", "--format", "json"]
        environment = dict(os.environ)
        environment.pop("LOGINEXUS_USERS_FILE", None)
        missing = subprocess.run(command, env=environment, capture_output=True, text=True,
                                 check=False, timeout=30)
        assert missing.returncode != 0
        assert "LOGINEXUS_USERS_FILE" in missing.stderr
        registry = Path(directory) / "users.json"
        registry.write_text('{"users": []}')
        environment["LOGINEXUS_USERS_FILE"] = str(registry)
        result = subprocess.run(command, env=environment, capture_output=True, text=True,
                                check=True, timeout=30)
        service = json.loads(result.stdout)["services"]["api"]
        assert service["environment"]["LOGINEXUS_REQUIRE_AUTH"] == "true"
        assert service["environment"]["LOGINEXUS_API_KEY"] == ""
        assert service["environment"]["LOGINEXUS_API_USERS_FILE"] == "/run/loginexus/users.json"
        mount = next(row for row in service["volumes"] if row["target"] == "/run/loginexus/users.json")
        assert mount["read_only"] and not mount["bind"]["create_host_path"]
        assert service["ports"][0]["host_ip"] == "127.0.0.1"
        assert service["read_only"]
    print("Compose users override verified; missing registry rejected; no service started.")


if __name__ == "__main__":
    main()
