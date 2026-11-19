import hashlib
import json
import re
import shutil

import polars as pl
import pytest
from fastapi.testclient import TestClient

from freight_intelligence.api.app import create_app
from freight_intelligence.brazil_road_od import DEFAULT_ROOT, load_state_pairs, parse_capture
from scripts.prepare_brazil_road_od import prepare


def test_transcription_matches_archived_filtered_views_and_detail_rows():
    capture = json.loads((DEFAULT_ROOT / "state_od_capture.json").read_bytes())
    for origin, expected in capture["pairs"].items():
        text = (DEFAULT_ROOT / f"state_od_{origin}.txt").read_text(encoding="utf-8")
        assert "Description: Ano, Mes, Value: 2025 " in text
        assert re.findall(r"row Description: UF de origem ([A-Z]{2})\. Toneladas", text) == [origin]
        pairs = dict(re.findall(r"row Description: UF de destino ([A-Z]{2})\. Toneladas ([\d.]+)\.,", text))
        detail = DEFAULT_ROOT / f"state_od_{origin}-table.txt"
        if detail.exists():
            for destination, value in re.findall(r"\d+ row ([A-Z]{2}) ([\d.]+)\n", detail.read_text(encoding="utf-8")):
                if destination in pairs:
                    assert pairs[destination] == value
                pairs[destination] = value
        assert pairs == expected
    overview = (DEFAULT_ROOT / "state_od_overview.txt").read_text(encoding="utf-8")
    for label, key in (("origem", "origin_margins"), ("destino", "destination_margins")):
        assert dict(re.findall(rf"row Description: UF de {label} ([A-Z]{{2}})\. Toneladas ([\d.]+)\.,", overview)) == capture[key]


def test_all_reviewed_state_pairs_rebuild_and_reconcile(tmp_path):
    root = tmp_path / "road"
    shutil.copytree(DEFAULT_ROOT, root)
    before = (root / "state_od.csv").read_bytes()
    assert prepare(root).height == 775
    assert (root / "state_od.csv").read_bytes() == before
    data, metadata = load_state_pairs(root)
    assert data["tonnes"].sum() == metadata["tonnes"] == 1368627704
    assert data["origin_state"].n_unique() == data["destination_state"].n_unique() == 28
    capture = json.loads((root / "state_od_capture.json").read_bytes())
    for field, margin in (("origin_state", "origin_margins"), ("destination_state", "destination_margins")):
        assert dict(data.group_by(field).agg(pl.col("tonnes").sum()).iter_rows()) == {
            code: int(value.replace(".", "")) for code, value in capture[margin].items()}
    assert data.filter((pl.col("origin_state") == "TO") & (pl.col("destination_state") == "AC"))["tonnes"][0] == 47
    assert data.filter((pl.col("origin_state") == "SP") & (pl.col("destination_state") == "SP"))["tonnes"][0] == 126486098
    assert data.height < 28 * 28  # No synthetic zero-filled pairs.


@pytest.mark.parametrize("defect", ["year", "pair", "missing_origin", "margin"])
def test_capture_rejects_wrong_filter_or_unreconciled_pairs(defect):
    capture = json.loads((DEFAULT_ROOT / "state_od_capture.json").read_bytes())
    if defect == "year":
        capture["year"] = 2024
    elif defect == "pair":
        capture["pairs"]["SP"]["SP"] = "126.486.099"
    elif defect == "missing_origin":
        capture["pairs"].pop("EX")
    else:
        capture["destination_margins"]["AC"] = "1"
    with pytest.raises(ValueError):
        parse_capture(json.dumps(capture))


@pytest.mark.parametrize("filename", ["state_od.csv", "state_od_MG.txt", "state_od_capture.json", "state_od_provenance.json"])
def test_changed_evidence_invalidates_cache_and_fails_closed(tmp_path, filename):
    root = tmp_path / "road"
    shutil.copytree(DEFAULT_ROOT, root)
    load_state_pairs(root)
    target = root / filename
    target.write_bytes(target.read_bytes() + b"changed")
    if filename != "state_od_provenance.json":
        # Even rewriting the manifest hash cannot authorize a changed source.
        metadata = json.loads((root / "state_od_provenance.json").read_bytes())
        record = next(row for row in metadata["files"] if row["path"] == filename)
        record["sha256"] = hashlib.sha256(target.read_bytes()).hexdigest()
        (root / "state_od_provenance.json").write_text(json.dumps(metadata))
    with pytest.raises(ValueError):
        load_state_pairs(root)


def test_state_pairs_api_filters_pagination_and_scoped_unavailability(tmp_path):
    with TestClient(create_app()) as client:
        result = client.get("/brazil/road-state-pairs?limit=500").json()
        assert result["total"] == 775 and result["count"] == 500
        assert client.get("/brazil/road-state-pairs?offset=500&limit=500").json()["count"] == 275
        result = client.get("/brazil/road-state-pairs?origin_state=SP&destination_state=MG").json()
        assert result["count"] == 1 and result["filtered_tonnes"] == 20814789
        assert client.get("/brazil/road-state-pairs?origin_state=EX").json()["filtered_tonnes"] == 141482
        result = client.get("/brazil/road-state-pairs?same_state=true").json()
        assert all(row["origin_state"] == row["destination_state"] for row in result["data"])
        for query in ("year=2024", "origin_state=XX", "limit=501", "offset=-1"):
            assert client.get("/brazil/road-state-pairs?" + query).status_code == 422
    with TestClient(create_app(road_dir=tmp_path)) as client:
        assert client.get("/brazil/road-state-pairs").status_code == 503
