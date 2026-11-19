import calendar
import csv
import hashlib
import io
import json
from zipfile import ZipFile

import pytest

from freight_intelligence.ingestion.brazil_gas import (
    HEADERS,
    LEGACY_UNITS_FILE,
    LEGACY_UNITS_SHA256,
    LEGACY_UNITS_URL,
)
from scripts.audit_brazil_gas import audit
from scripts.prepare_brazil_gas import BASE, FILES, prepare


def monthly_source(month, value="1", year=2025):
    days = calendar.monthrange(year, month)[1]
    rows = [[*HEADERS, *[f"{day:02}/{month:02}/{year}" for day in range(1, days + 1)]]]
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
            metadata = json.loads(bundle.read("deployment/brazil_modes/provenance.json"))
            assert any("0 missing daily cells" in note for note in metadata["quality_notes"])


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


def history_fixture(root, year):
    urls = [BASE.replace("/2025/", f"/{year}/") + f"gn_{month}.csv" for month in range(1, 13)]
    sources = {url: monthly_source(month, year=year) for month, url in enumerate(urls, 1)}
    annual = prepare(root.parent / "initial-cache", root, year=year, source_urls=urls,
                     fetch=sources.__getitem__, deduplicate_identical=True,
                     legacy_unit_contract=LEGACY_UNITS_SHA256 if year == 2021 else None)
    metadata = json.loads((root / "provenance.json").read_bytes())
    for source in metadata["sources"]:
        source["missing_groups"] = []
    metadata["years"] = [year]
    (root / "annual.json").write_text(json.dumps([annual]))
    if year == 2021:
        from freight_intelligence.brazil_gas_history import DEFAULT_ROOT
        raw = (DEFAULT_ROOT / LEGACY_UNITS_FILE).read_bytes()
        (root / LEGACY_UNITS_FILE).write_bytes(raw)
        sources[LEGACY_UNITS_URL] = raw
        metadata["legacy_unit_contract"] = {"url": LEGACY_UNITS_URL, "sha256": LEGACY_UNITS_SHA256,
                                            "file": LEGACY_UNITS_FILE, "version": "2026-06-12", "page": 2,
                                            "year": 2021, "variable": "Volume Realizado", "unit": "thousand_m3"}
    metadata["files"] = [{"path": name, "sha256": hashlib.sha256((root / name).read_bytes()).hexdigest()}
                         for name in ("monthly.csv", "annual.json", *([LEGACY_UNITS_FILE] if year == 2021 else []))]
    (root / "provenance.json").write_text(json.dumps(metadata))
    return urls, sources


@pytest.mark.parametrize("year", [2021, 2024])
@pytest.mark.parametrize("changed", [False, True])
def test_historical_audit_isolates_year_preserves_baseline_and_reviews_revisions(tmp_path, year, changed):
    baseline = tmp_path / "history"
    urls, sources = history_fixture(baseline, year)
    before = {p.name: p.read_bytes() for p in baseline.iterdir()}
    if changed:
        sources[urls[0]] = monthly_source(1, value="2", year=year)
    calls = []

    def fetch(url):
        calls.append(url)
        return sources[url]

    output = tmp_path / "audit"
    report = audit(output, tmp_path / "cache", year=year, history_baseline=baseline, fetch=fetch)
    assert report["year"] == year and report["status"] == ("candidate_requires_review" if changed else "unchanged")
    assert len(report["source_revisions"]) == int(changed)
    assert set(calls) == set(sources)
    assert report["after"]["monthly_rows"] == 120
    assert {p.name: p.read_bytes() for p in baseline.iterdir()} == before
    assert "annual_modal_rows" not in report
    archive = output / "review-candidate.zip"
    assert archive.exists() == changed
    if changed:
        with ZipFile(archive) as bundle:
            assert f"deployment/historical-year-review/{year}/annual.json" in bundle.namelist()
            assert not any("brazil_modes" in name or "brazil_gas/" in name for name in bundle.namelist())


def test_changed_legacy_unit_document_blocks_historical_candidate(tmp_path):
    baseline = tmp_path / "history"
    _, sources = history_fixture(baseline, 2021)
    sources[LEGACY_UNITS_URL] = b"changed units"
    with pytest.raises(ValueError, match="unit dictionary"):
        audit(tmp_path / "audit", tmp_path / "cache", year=2021,
              history_baseline=baseline, fetch=sources.__getitem__)
    report = json.loads((tmp_path / "audit/report.json").read_text())
    assert report["status"] == "validation_failed"
    assert not (tmp_path / "audit/review-candidate.zip").exists()


def test_unreviewed_audit_year_is_rejected_before_creating_output(tmp_path):
    with pytest.raises(ValueError, match="reviewed ANP years"):
        audit(tmp_path / "audit", tmp_path / "cache", year=2020)
    assert not (tmp_path / "audit").exists()
