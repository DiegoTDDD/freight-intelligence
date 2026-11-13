import calendar
import csv
import io
import json
from zipfile import ZipFile

import pytest

from freight_intelligence.ingestion.brazil_gas import HEADERS
from scripts.audit_brazil_gas import audit
from scripts.prepare_brazil_gas import BASE, FILES, prepare


def monthly_source(month, value="1"):
    days = calendar.monthrange(2025, month)[1]
    rows = [[*HEADERS, *[f"{day:02}/{month:02}/2025" for day in range(1, days + 1)]]]
    for operator in range(5):
        for point_type in ("Ponto de Recebimento", "Ponto de Entrega"):
            rows.append(["1", "Pipe", "Point", point_type + str(operator), point_type,
                         "City", "SP", f"Operator {operator}", str(operator), "Shipper",
                         "123", "contract", "Volume Realizado (mil m³)", *[value] * days])
    output = io.StringIO(newline="")
    csv.writer(output, delimiter=";", lineterminator="\n").writerows(rows)
    return output.getvalue().encode("cp1252")


def fetcher(value="1"):
    sources = {BASE + file: monthly_source(month, value)
               for month, file in enumerate(FILES, 1)}
    return lambda url: sources[url]


def test_cache_refresh_fetches_new_source_bytes(tmp_path):
    cache, output = tmp_path / "cache", tmp_path / "gas"
    first = prepare(cache, output, fetch=fetcher())
    retained = prepare(cache, output, fetch=lambda url: pytest.fail("unexpected network"))
    assert retained == first
    refreshed = prepare(cache, output, refresh=True, fetch=fetcher("2"))
    assert refreshed["receipt"] == first["receipt"] * 2


@pytest.mark.parametrize("changed", [False, True])
def test_source_audit_creates_candidate_only_for_revisions_without_changing_baseline(tmp_path, changed):
    baseline = tmp_path / "baseline"
    cache = tmp_path / "cache"
    prepare(cache, baseline, fetch=fetcher())
    before = {p.name: p.read_bytes() for p in baseline.iterdir()}
    output = tmp_path / "audit"
    report = audit(output, cache, fetch=fetcher("2" if changed else "1"), baseline=baseline)
    assert report["status"] == ("candidate_requires_review" if changed else "unchanged")
    assert len(report["source_revisions"]) == (12 if changed else 0)
    assert {p.name: p.read_bytes() for p in baseline.iterdir()} == before
    archive = output / "review-candidate.zip"
    assert archive.exists() == changed
    if changed:
        with ZipFile(archive) as bundle:
            assert bundle.testzip() is None
            assert "deployment/brazil_gas/annual.json" in bundle.namelist()
            assert not any("cache" in name or "gn_" in name for name in bundle.namelist())
            assert json.loads(bundle.read("audit-report.json"))["status"] == report["status"]


def test_invalid_upstream_report_fails_without_publishing_candidate(tmp_path):
    baseline = tmp_path / "baseline"
    cache = tmp_path / "cache"
    prepare(cache, baseline, fetch=fetcher())
    output = tmp_path / "audit"
    with pytest.raises(ValueError):
        audit(output, cache, fetch=lambda url: b"broken", baseline=baseline)
    assert json.loads((output / "report.json").read_text())["status"] == "validation_failed"
    assert not (output / "review-candidate.zip").exists()


def test_audit_cannot_target_served_snapshot():
    from scripts.audit_brazil_gas import ROOT

    with pytest.raises(ValueError, match="outside deployment"):
        audit(ROOT / "deployment/brazil_gas", ROOT / "data/raw/anp/audit")
