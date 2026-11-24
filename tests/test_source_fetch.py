import http.client
import json
import urllib.error

import pytest

from freight_intelligence.ingestion.source_fetch import (
    SourceUnavailable,
    is_transient,
    with_retries,
)

URL = "https://www.gov.br/source.csv"


def flaky(failures, error, result=b"ok"):
    calls = []

    def download():
        calls.append(1)
        if len(calls) <= failures:
            raise error
        return result

    return download, calls


@pytest.mark.parametrize("error", [
    urllib.error.URLError(ConnectionResetError(104, "Connection reset by peer")),
    ConnectionResetError(104, "Connection reset by peer"),
    TimeoutError("timed out"),
    http.client.RemoteDisconnected("closed"),
    urllib.error.HTTPError(URL, 503, "Service Unavailable", {}, None),
    urllib.error.HTTPError(URL, 429, "Too Many Requests", {}, None),
])
def test_transient_errors_are_retried_until_success(error):
    download, calls = flaky(2, error)
    pauses = []
    assert with_retries(URL, download, sleep=pauses.append) == b"ok"
    assert len(calls) == 3
    assert pauses == [5, 15]


@pytest.mark.parametrize("error", [
    ValueError("Unexpected ANP source redirect"),
    urllib.error.HTTPError(URL, 404, "Not Found", {}, None),
    urllib.error.URLError("unknown url type"),
])
def test_definitive_errors_are_not_retried(error):
    download, calls = flaky(5, error)
    with pytest.raises(type(error)):
        with_retries(URL, download, sleep=lambda _: pytest.fail("must not wait"))
    assert len(calls) == 1
    assert not is_transient(error)


def test_exhausted_retries_raise_source_unavailable():
    download, calls = flaky(10, urllib.error.URLError(ConnectionResetError(104, "reset")))
    pauses = []
    with pytest.raises(SourceUnavailable) as caught:
        with_retries(URL, download, sleep=pauses.append)
    assert len(calls) == 4 and pauses == [5, 15, 45]
    assert (caught.value.url, caught.value.attempts, caught.value.last_error) == (URL, 4, "URLError")


def unreachable(url):
    raise SourceUnavailable(url, 4, ConnectionResetError(104, "Connection reset by peer"))


def test_road_audit_reports_unreachable_source_without_failing(tmp_path):
    from freight_intelligence.brazil_road import DEFAULT_ROOT
    from scripts.audit_brazil_road import audit

    before = (DEFAULT_ROOT / "monthly.csv").read_bytes()
    report = audit(tmp_path / "audit", fetch=unreachable)
    assert report["status"] == "source_unreachable"
    assert report["attempts"] == 4 and report["failure_type"] == "ConnectionResetError"
    saved = json.loads((tmp_path / "audit/report.json").read_bytes())
    assert saved["status"] == "source_unreachable"
    assert not (tmp_path / "audit/unreviewed-source.pdf").exists()
    assert (DEFAULT_ROOT / "monthly.csv").read_bytes() == before


def test_gas_audit_reports_unreachable_source_without_candidate(tmp_path):
    from scripts.audit_brazil_gas import audit
    from tests.test_source_audit import fetcher, prepare

    baseline = tmp_path / "baseline"
    prepare(tmp_path / "cache", baseline, fetch=fetcher())
    before = {p.name: p.read_bytes() for p in baseline.iterdir()}
    report = audit(tmp_path / "audit", tmp_path / "audit-cache", fetch=unreachable, baseline=baseline)
    assert report["status"] == "source_unreachable" and report["source_revisions"] == []
    assert json.loads((tmp_path / "audit/report.json").read_bytes())["status"] == "source_unreachable"
    assert not (tmp_path / "audit/review-candidate.zip").exists()
    assert {p.name: p.read_bytes() for p in baseline.iterdir()} == before
