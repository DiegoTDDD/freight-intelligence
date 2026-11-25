"""Bounded on-demand service check; never keeps a free instance continuously awake."""

import argparse
import hashlib
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def request_json(url, timeout):
    try:
        response = urllib.request.build_opener(NoRedirect()).open(url, timeout=timeout)
    except urllib.error.HTTPError as error:
        return error.code, None
    with response:
        raw = response.read(262145)
        if len(raw) > 262144:
            raise RuntimeError("Service response exceeds 256 KiB")
        return response.status, json.loads(raw)


def probe(base, *, expected_revision=None, fetch=request_json, clock=time.monotonic, pause=time.sleep):
    url = urllib.parse.urlsplit(base)
    local = url.scheme == "http" and url.hostname in {"127.0.0.1", "localhost"}
    if (url.scheme != "https" and not local) or not url.hostname or url.username or url.password or url.query or url.fragment or url.path not in {"", "/"}:
        raise ValueError("Use an HTTPS origin, or loopback HTTP for container checks")
    if expected_revision is not None and not re.fullmatch(r"[0-9a-f]{40}", expected_revision):
        raise ValueError("Expected revision must be a full Git SHA")
    base = base.rstrip("/")
    started = clock()
    deadline = started + 180
    while True:
        remaining = deadline - clock()
        if remaining <= 0:
            raise TimeoutError("API did not become ready within the 180-second on-demand target")
        try:
            code, version = fetch(base + "/version", min(10, remaining))
        except (OSError, ValueError):
            code, version = 503, None
        if code == 200:
            if not isinstance(version, dict) or version.get("service") != "loginexus-public-api":
                raise RuntimeError("Unexpected service identity")
            revision = version.get("revision")
            if not isinstance(revision, str) or not re.fullmatch(r"[0-9a-f]{40}", revision):
                raise RuntimeError("Missing or invalid deployed revision")
            if expected_revision and revision != expected_revision:
                raise RuntimeError("Deployed revision differs from the expected tested revision")
            expected = hashlib.sha256((ROOT / "deployment/preview_data/snapshot_manifest.json").read_bytes()).hexdigest()
            if version.get("snapshot_manifest_sha256") != expected:
                raise RuntimeError("Published snapshot manifest differs from the reviewed repository")
            break
        if code not in {408, 425, 429, 500, 502, 503, 504}:
            raise RuntimeError(f"Unexpected version response: HTTP {code}")
        pause(min(5, max(0, deadline - clock())))
    checks = []
    for path, expected_status in (("/ready", 200), ("/annual-kpis?metric_type=tons&start_year=2023&end_year=2023", 200),
                                  ("/transport-plan", 503)):
        begin = clock()
        code, data = fetch(base + path, 10)
        elapsed = clock() - begin
        if code != expected_status or elapsed > 10:
            raise RuntimeError(f"Probe failed its status/10-second response target: {path}")
        if path == "/ready" and (not isinstance(data, dict) or data.get("status") != "ready"):
            raise RuntimeError("API snapshot not ready")
        if path.startswith("/annual-kpis") and (not isinstance(data, dict) or data.get("count") != 1
                or data["data"][0].get("year") != 2023 or data["data"][0].get("metric_type") != "tons"):
            raise RuntimeError("Unexpected reviewed annual data")
        checks.append({"path": path, "status": code, "elapsed_seconds": round(elapsed, 3)})
    return {"status": "passed", "base_url": base, "version": version, "checks": checks,
            "wake_ready_observed_seconds": round(clock() - started, 3),
            "target": "On-demand version within 180s; subsequent sampled responses within 10s; not an uptime SLA"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--expected-revision")
    parser.add_argument("--output", type=Path, default=Path("public-api-probe.json"))
    args = parser.parse_args()
    try:
        report = probe(args.base_url, expected_revision=args.expected_revision)
    except (OSError, ValueError, RuntimeError, KeyError, TypeError, IndexError) as error:
        report = {"status": "failed", "error": str(error)}
    report["observed_at_utc"] = datetime.now(UTC).isoformat()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
