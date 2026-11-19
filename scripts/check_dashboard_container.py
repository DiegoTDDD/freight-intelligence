"""Exercise the shipped dashboard image and bundled data under hosting limits."""

import argparse
import hashlib
import json
import subprocess
import uuid
from pathlib import Path


def check_http_server(image):
    """Exercise the actual shipped ASGI entry point, without external network access."""
    name = "loginexus-http-check-" + uuid.uuid4().hex[:12]
    probe = r'''
import json
import time
import urllib.error
import urllib.request

base = "http://127.0.0.1:8501"
deadline = time.monotonic() + 45
while True:
    try:
        with urllib.request.urlopen(base + "/_stcore/health", timeout=2) as response:
            assert response.status == 200
        break
    except (OSError, urllib.error.URLError):
        if time.monotonic() >= deadline:
            raise RuntimeError("Hosted server did not start") from None
        time.sleep(0.25)

for path in ("/", "/api/docs", "/api/health", "/api/ready",
             "/api/annual-kpis?metric_type=tons", "/api/annual-forecast",
             "/api/temporal-evaluation", "/api/brazil/indicators?mode=air",
             "/api/brazil/gas-movements?month=12&point_type=receipt",
             "/api/brazil/water-freight?dataset=coastal_state_endpoints",
             "/api/brazil/water-pairs?origin_region=Norte",
             "/api/brazil/water-port-pairs?origin_port=Santos&destination_port=Suape",
             "/api/brazil/modal-forecasts?mode=water&view=scores&phase=test",
             "/api/brazil/road-flows?origin_state=MT", "/api/brazil/road-monthly?month=1",
             "/api/brazil/road-history?year=2024",
             "/api/brazil/water-history?view=annual&year=2026",
             "/api/brazil/road-state-pairs?origin_state=SP&destination_state=MG",
             "/api/brazil/air-freight?view=pairs&year=2025&origin=SBGR",
             "/api/brazil/gas-movements?year=2022&include_diagnostics=true&diagnostics_limit=1",
             "/api/brazil/gas-movements?year=2024&include_diagnostics=true&diagnostics_limit=1"):
    with urllib.request.urlopen(base + path, timeout=10) as response:
        assert response.status == 200, path
        response.read()
with urllib.request.urlopen(base + "/api/openapi.json", timeout=10) as response:
    assert {"url": "/api"} in json.load(response)["servers"]
try:
    urllib.request.urlopen(base + "/api/transport-plan", timeout=10)
except urllib.error.HTTPError as error:
    assert error.code == 503
else:
    raise RuntimeError("Unexpected private transport plan exposure")
print("Hosted dashboard + API HTTP checks passed offline within 512 MiB")
'''
    try:
        subprocess.run([
            "docker", "run", "-d", "--name", name, "--network", "none", "--read-only",
            "--memory", "512m", "--cpus", "1", "--cap-drop", "ALL",
            "--security-opt", "no-new-privileges", "--tmpfs", "/tmp:rw,nosuid,size=128m",
            "--mount", f"type=bind,source={Path(__file__).with_name('check_dashboard_sessions.py').resolve()},target=/check_sessions.py,readonly",
            image,
        ], check=True, timeout=60, stdout=subprocess.DEVNULL)
        subprocess.run(["docker", "exec", name, "python", "-c", probe], check=True, timeout=90)
        subprocess.run(
            ["docker", "exec", name, "python", "/check_sessions.py"], check=True, timeout=180,
        )
    finally:
        subprocess.run(
            ["docker", "rm", "-f", name], check=False, timeout=30,
            stdout=subprocess.DEVNULL,
        )


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
    if app.selectbox(key="language").value != "en":
        raise RuntimeError("New sessions must default to English")
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
        if heading not in [element.value for element in app.subheader]:
            raise RuntimeError(f"{workspace}: expected content missing")
        if not app.dataframe or not app.metric:
            raise RuntimeError(f"{workspace}: expected data and metrics missing")
        print(f"Dashboard workspace passed: {workspace}")
    app.selectbox(key="workspace").select("Real road routes").run()
    app.button[1].click().run()
    if app.exception or not app.metric or app.metric[0].value != "93.17":
        raise RuntimeError("Saved real-road route failed offline")
    app.button[2].click().run()
    if app.exception or not app.metric or app.metric[0].value != "98.77":
        raise RuntimeError("Saved truck route failed offline")
    app.selectbox(key="workspace").select("Brazilian freight").run()
    app.selectbox(key="brazil_view").select("All five modes").run()
    for mode in ("road", "rail", "water", "air", "pipeline"):
        app.selectbox(key="brazil_mode").select(mode).run()
        if app.exception or app.error or not app.metric:
            raise RuntimeError(f"Brazil modal view failed: {mode}")
        if mode == "road":
            app.selectbox(key="road_reference_dataset").select("state_pairs").run()
            if app.exception or app.error or not any(
                item.label == "Reported OD pairs" and item.value == "775" for item in app.metric
            ):
                raise RuntimeError("Reconciled state road pairs failed offline")
        if mode == "water":
            app.selectbox(key="brazil_water_dataset").select("port_history").run()
            if app.exception or app.error or not any(
                item.label == "Observed port months" and item.value == "62" for item in app.metric
            ):
                raise RuntimeError("Monthly ANTAQ history failed offline")
    app.selectbox(key="brazil_gas_year").select(2024).run()
    if app.exception or app.error:
        raise RuntimeError("Historical gas coverage view failed")
    app.selectbox(key="workspace").select("Real road routes").run()
    app.selectbox(key="language").select("pt").run()
    if app.exception or app.subheader[0].value != translate("Routes on real roads"):
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
    check_http_server(args.image)


if __name__ == "__main__":
    main()
