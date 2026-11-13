import hashlib
import json

import pytest

from freight_intelligence.brazil_road import DEFAULT_ROOT
from scripts.audit_brazil_road import ROOT, audit


def test_changed_source_is_quarantined_without_promoting_values(tmp_path):
    before = (DEFAULT_ROOT / "monthly.csv").read_bytes()
    report = audit(tmp_path / "audit", fetch=lambda _: b"%PDF-1.7\nchanged source")
    assert report["status"] == "source_changed_requires_review"
    assert report["reviewed_annual_tonnes"] == 1368699651
    assert (DEFAULT_ROOT / "monthly.csv").read_bytes() == before
    assert (tmp_path / "audit/unreviewed-source.pdf").read_bytes().startswith(b"%PDF-")


def test_unchanged_source_report_and_no_candidate(tmp_path):
    import shutil

    baseline = tmp_path / "baseline"
    shutil.copytree(DEFAULT_ROOT, baseline)
    raw = b"%PDF-1.7\nreviewed test source"
    path = baseline / "provenance.json"
    metadata = json.loads(path.read_bytes())
    metadata["monthly_source"]["sha256"] = hashlib.sha256(raw).hexdigest()
    path.write_text(json.dumps(metadata))
    result = audit(tmp_path / "audit", fetch=lambda _: raw, baseline=baseline)
    assert result["status"] == "unchanged"
    assert not (tmp_path / "audit/unreviewed-source.pdf").exists()


def test_invalid_response_fails_and_preserves_failure_report(tmp_path):
    with pytest.raises(ValueError):
        audit(tmp_path / "audit", fetch=lambda _: b"<html>unavailable</html>")
    report = json.loads((tmp_path / "audit/report.json").read_bytes())
    assert report["status"] == "validation_failed"
    assert not (tmp_path / "audit/unreviewed-source.pdf").exists()


def test_audit_never_writes_inside_served_snapshot():
    with pytest.raises(ValueError):
        audit(ROOT / "deployment/brazil_road/audit", fetch=lambda _: pytest.fail("network"))
