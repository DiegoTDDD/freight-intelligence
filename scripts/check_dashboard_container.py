"""Exercise the shipped dashboard image and bundled data under hosting limits."""

import argparse
import hashlib
import json
import subprocess
from pathlib import Path


def check_inside_container():
    from streamlit.testing.v1 import AppTest

    from freight_intelligence.dashboard_i18n import translate
    from freight_intelligence.utils.runtime_lock import main as verify_runtime

    verify_runtime(["--lock", "/app/requirements/dashboard-linux-py313.lock"])
    snapshot = Path("/app/preview-data")
    manifest = json.loads((snapshot / "snapshot_manifest.json").read_text())
    for record in manifest["files"]:
        data = (snapshot / record["path"]).read_bytes()
        if hashlib.sha256(data).hexdigest() != record["sha256"]:
            raise RuntimeError(f"Snapshot mismatch: {record['path']}")
    app = AppTest.from_file("/app/dashboards/app.py", default_timeout=45).run()
    expectations = {
        "Freight analytics": "Annual Freight Evolution",
        "Scenario extrapolations": "Annual scenario extrapolations",
        "Temporal evaluation": "Temporal model evaluation",
        "Brazilian freight": "Brazilian railway freight",
    }
    for workspace, heading in expectations.items():
        app.selectbox(key="workspace").select(workspace).run()
        if app.exception or app.error:
            raise RuntimeError(f"{workspace}: {list(app.exception)} {list(app.error)}")
        if translate(heading) not in [element.value for element in app.subheader]:
            raise RuntimeError(f"{workspace}: expected content missing")
        if not app.dataframe or not app.metric:
            raise RuntimeError(f"{workspace}: expected data and metrics missing")
        print(f"Dashboard workspace passed: {workspace}")
    app.selectbox(key="workspace").select("Real road routes").run()
    app.button[1].click().run()
    if app.exception or not app.metric or app.metric[0].value != "93.17":
        raise RuntimeError("Saved real-road route failed offline")
    app.selectbox(key="language").select("en").run()
    if app.exception or app.subheader[0].value != "Routes on real roads":
        raise RuntimeError("Language switch failed")
    print(f"Verified {len(manifest['files'])} snapshot files; no network or writable app data")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", default="loginexus-dashboard:ci")
    parser.add_argument("--inside-container", action="store_true")
    args = parser.parse_args()
    if args.inside_container:
        check_inside_container()
        return
    subprocess.run([
        "docker", "run", "--rm", "--network", "none", "--read-only",
        "--memory", "512m", "--cpus", "1", "--cap-drop", "ALL",
        "--security-opt", "no-new-privileges", "--tmpfs", "/tmp:rw,nosuid,size=128m",
        "--mount", f"type=bind,source={Path(__file__).resolve()},target=/check_dashboard.py,readonly",
        args.image, "python", "/check_dashboard.py", "--inside-container",
    ], check=True, timeout=240)


if __name__ == "__main__":
    main()
