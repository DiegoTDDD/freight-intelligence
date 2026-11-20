import hashlib
import io
import json
import shutil

import pytest

from freight_intelligence.brazil_air import DEFAULT_ROOT
from scripts.audit_brazil_air import (
    CHUNK_BYTES,
    MAX_BYTES,
    ROOT,
    SOURCE,
    audit,
    download_source,
    validate_header,
)

HEADER = ["ANO", "MES", "NATUREZA", "GRUPO_DE_VOO", "CARGA_PAGA_KG", "CARGA_GRATIS_KG", "CORREIO_KG",
          *[f"AEROPORTO_DE_{side}_{field}" for side in ("ORIGEM", "DESTINO") for field in ("SIGLA", "NOME", "PAIS")]]
RAW = ("Atualizado em: 2026-11-20\n" + ";".join(HEADER) + "\n" + ";".join(["1"] * len(HEADER)) + "\n").encode()


class Response(io.BytesIO):
    def __init__(self, raw, *, url=SOURCE, declared=None):
        super().__init__(raw)
        self.url = url
        self.headers = {} if declared is None else {"Content-Length": str(declared)}
        self.read_sizes = []

    def geturl(self):
        return self.url

    def read(self, size=-1):
        self.read_sizes.append(size)
        return super().read(size)


def opener_for(response):
    def opener(request, timeout):
        assert request.full_url == SOURCE and timeout == 30
        assert request.get_header("Accept-encoding") == "identity"
        return response
    return opener


@pytest.mark.parametrize("changed", [False, True])
def test_audit_streams_and_quarantines_only_changed_source_without_touching_baseline(tmp_path, changed):
    baseline = tmp_path / "air"
    shutil.copytree(DEFAULT_ROOT, baseline)
    path = baseline / "provenance.json"
    metadata = json.loads(path.read_bytes())
    metadata["source_sha256"] = hashlib.sha256(RAW).hexdigest()
    path.write_text(json.dumps(metadata))
    before = {p.name: p.read_bytes() for p in baseline.iterdir()}
    raw = RAW + b"changed row\n" if changed else RAW
    response = Response(raw, declared=len(raw))
    output = tmp_path / "audit"
    report = audit(output, baseline=baseline, opener=opener_for(response))
    assert report["status"] == ("source_changed_requires_review" if changed else "unchanged")
    assert report["header_validated"] and not report["full_data_rows_validated"]
    assert not report["automatic_promotion"]
    assert {p.name: p.read_bytes() for p in baseline.iterdir()} == before
    candidate = output / "unreviewed-source.csv"
    assert candidate.exists() == changed
    if changed:
        assert candidate.read_bytes() == raw
    assert not (output / "source.csv.part").exists()
    assert all(0 < size <= CHUNK_BYTES for size in response.read_sizes)
    assert json.loads((output / "report.json").read_text())["status"] == report["status"]


@pytest.mark.parametrize("defect", ["redirect", "declared_oversize", "stream_oversize", "truncated", "html", "timeout"])
def test_invalid_transfers_fail_with_report_and_without_partial_or_candidate(tmp_path, defect):
    response = Response(b"<html>error</html>" if defect == "html" else RAW)
    limit = len(RAW) + 1
    clock = lambda: 0
    if defect == "redirect":
        response.url = "https://example.com/source.csv"
    elif defect == "declared_oversize":
        response.headers["Content-Length"] = str(limit + 1)
    elif defect == "stream_oversize":
        limit = len(RAW) - 1
    elif defect == "truncated":
        response.headers["Content-Length"] = str(len(RAW) + 1)
    elif defect == "timeout":
        calls = iter((0, 301))
        clock = lambda: next(calls)
    output = tmp_path / "audit"
    with pytest.raises((ValueError, TimeoutError)):
        audit(output, opener=opener_for(response), max_bytes=limit, clock=clock, deadline_seconds=300)
    report = json.loads((output / "report.json").read_text())
    assert report["status"] == "validation_failed" and report["failure_type"]
    assert list(output.iterdir()) == [output / "report.json"]


def test_header_validation_ignores_partial_body_utf8_but_rejects_changed_contract():
    assert validate_header(RAW + b"\xc3") == "Atualizado em: 2026-11-20"
    for raw in (b"<html>error</html>", RAW.replace(b"ANO;", b"OTHER;"),
                RAW.replace(b"ANO;MES;", b"ANO;ANO;"), RAW.replace(b"2026-11-20", b"2026-13-99")):
        with pytest.raises(ValueError):
            validate_header(raw)


def test_stream_download_preserves_an_existing_file(tmp_path):
    path = tmp_path / "source.csv.part"
    path.write_bytes(b"user file")
    with pytest.raises(FileExistsError):
        download_source(path, opener=opener_for(Response(RAW)))
    assert path.read_bytes() == b"user file"


def test_audit_rejects_served_snapshot_output_before_network():
    with pytest.raises(ValueError, match="outside served"):
        audit(ROOT / "deployment/brazil_air/audit", opener=lambda *args, **kwargs: pytest.fail("network"))


def test_invalid_transfer_budgets_never_start_a_download(tmp_path):
    for size, seconds in ((-1, 300), (0, 300), (MAX_BYTES + 1, 300), (MAX_BYTES, 0), (MAX_BYTES, float("nan"))):
        with pytest.raises(ValueError, match="budget"):
            download_source(tmp_path / "partial", max_bytes=size, deadline_seconds=seconds,
                            opener=lambda *args, **kwargs: pytest.fail("network"))
    assert not (tmp_path / "partial").exists()
