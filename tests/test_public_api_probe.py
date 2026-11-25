import hashlib

import pytest

from scripts.probe_public_api import ROOT, probe


def version():
    return {"service": "loginexus-public-api", "revision": "a" * 40,
            "snapshot_manifest_sha256": hashlib.sha256((ROOT / "deployment/preview_data/snapshot_manifest.json").read_bytes()).hexdigest()}


def response(url, timeout):
    if url.endswith("/version"):
        return 200, version()
    if url.endswith("/ready"):
        return 200, {"status": "ready"}
    if "/annual-kpis?" in url:
        return 200, {"count": 1, "data": [{"year": 2023, "metric_type": "tons"}]}
    return 503, None


def test_probe_records_identity_data_and_private_plan_boundary():
    result = probe("https://example.onrender.com", expected_revision="a" * 40, fetch=response)
    assert result["status"] == "passed"
    assert [c["status"] for c in result["checks"]] == [200, 200, 503]


@pytest.mark.parametrize("defect", ["revision", "manifest", "service", "redirect", "ready", "private_plan"])
def test_wrong_revision_snapshot_identity_and_permission_boundary_fail(defect):
    def fetch(url, timeout):
        code, data = response(url, timeout)
        if url.endswith("/version"):
            if defect == "redirect":
                return 302, None
            data = dict(data)
            if defect in {"revision", "service"}:
                data[defect] = "wrong"
            if defect == "manifest":
                data["snapshot_manifest_sha256"] = "0" * 64
        if defect == "ready" and url.endswith("/ready"):
            return 503, None
        if defect == "private_plan" and url.endswith("/transport-plan"):
            return 200, {"data": "must never be exposed"}
        return code, data
    with pytest.raises(RuntimeError):
        probe("https://example.onrender.com", fetch=fetch)


def test_cold_start_is_bounded_and_retried_without_creating_a_keepalive():
    current, calls = [0], []

    def pause(seconds):
        current[0] += seconds

    def fetch(url, timeout):
        calls.append(url)
        if url.endswith("/version") and current[0] < 10:
            return 503, None
        return response(url, timeout)

    assert probe("https://example.onrender.com", fetch=fetch, clock=lambda: current[0], pause=pause)["status"] == "passed"
    assert sum(url.endswith("/version") for url in calls) == 3
    current[0] = 0
    with pytest.raises(TimeoutError):
        probe("https://example.onrender.com", fetch=lambda url, timeout: (503, None), clock=lambda: current[0], pause=pause)
    assert current[0] == 180


@pytest.mark.parametrize("base", ["http://example.com", "https://user:password@example.com", "https://example.com/a", "https://example.com?key=x"])
def test_probe_rejects_insecure_or_ambiguous_targets(base):
    with pytest.raises(ValueError):
        probe(base, fetch=response)
