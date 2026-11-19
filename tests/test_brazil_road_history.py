import hashlib
import json
import shutil

import polars as pl
import pytest
from fastapi.testclient import TestClient

from freight_intelligence.api.app import create_app
from freight_intelligence.brazil_road import load_road_monthly
from freight_intelligence.brazil_road_history import (
    DEFAULT_ROOT,
    load_road_history,
    parse_capture,
    source_integer,
)
from scripts.prepare_brazil_road_history import prepare


def test_reviewed_months_account_split_and_partial_years_reconcile(tmp_path):
    shutil.copytree(DEFAULT_ROOT, tmp_path / "road")
    root = tmp_path / "road"
    before = (root / "monthly_history.csv").read_bytes()
    prepare(root)
    assert (root / "monthly_history.csv").read_bytes() == before
    tables, metadata = load_road_history(root)
    assert tables["monthly"].height == 56 and tables["monthly"]["period"].n_unique() == 28
    all_years = tables["annual"].filter(pl.col("account_type") == "all")
    assert all_years["months_observed"].to_list() == [6, 12, 10]
    assert all_years["full_year"].to_list() == [False, True, False]
    assert all_years["tonnes"].to_list() == [695019509, 1368627704, 1290502521]
    assert all_years["mdfe_documents"].to_list() == [44573360, 90060010, 84223450]
    assert tables["editions"]["difference_tonnes"].sum() == -71947
    assert metadata["panel_minus_yearbook_2025_tonnes"] == -71947
    archived, _ = load_road_monthly()
    assert archived["tonnes"].sum() == 1368699651


def test_missing_month_or_bad_numeric_display_is_rejected():
    capture = json.loads((DEFAULT_ROOT / "history_capture.json").read_bytes())
    capture["tonnes"].pop("jul 24")
    with pytest.raises(ValueError, match="calendar"):
        parse_capture(json.dumps(capture))
    assert source_integer("5.827.884") == 5827884
    for value in ("1,2", "1.23", "-1", "", 100):
        with pytest.raises(ValueError):
            source_integer(value)


@pytest.mark.parametrize("defect", ["capture", "context", "values", "annual", "units", "coverage"])
def test_history_evidence_and_period_contract_fail_closed(tmp_path, defect):
    root = tmp_path / "road"
    shutil.copytree(DEFAULT_ROOT, root)
    load_road_history(root)
    path = root / "history_provenance.json"
    metadata = json.loads(path.read_bytes())
    if defect == "units":
        metadata["units"]["tonnes"] = "million_tonnes"
    elif defect == "coverage":
        metadata["coverage"]["2024"]["full_year"] = True
    else:
        filename = {"capture": "history_capture.json", "context": "history_context.jpg",
                    "values": "monthly_history.csv", "annual": "annual_history.csv"}[defect]
        target = root / filename
        if defect == "values":
            pl.read_csv(target).with_columns((pl.col("tonnes") + 1).alias("tonnes")).write_csv(target)
        elif defect == "annual":
            pl.read_csv(target).with_columns(pl.lit(True).alias("full_year")).write_csv(target)
        else:
            target.write_bytes(b"changed evidence")
        next(record for record in metadata["files"] if record["path"] == filename)["sha256"] = hashlib.sha256(target.read_bytes()).hexdigest()
    path.write_text(json.dumps(metadata))
    with pytest.raises(ValueError):
        load_road_history(root)


def test_history_api_filters_and_preserves_partial_years(tmp_path):
    with TestClient(create_app()) as client:
        assert client.get("/brazil/road-history").json()["count"] == 56
        result = client.get("/brazil/road-history?year=2024&account_type=own_account").json()
        assert result["count"] == 6 and {row["month"] for row in result["data"]} == set(range(7, 13))
        result = client.get("/brazil/road-history?view=annual&year=2024&account_type=all").json()
        assert result["data"][0]["full_year"] is False
        assert result["data"][0]["tonnes"] == 695019509
        result = client.get("/brazil/road-history?view=editions").json()
        assert result["count"] == 12 and sum(row["difference_tonnes"] for row in result["data"]) == -71947
        assert client.get("/brazil/road-history?year=2023").status_code == 422
        assert client.get("/brazil/road-history?account_type=all").status_code == 422
        assert client.get("/brazil/road-history?view=editions&account_type=own_account").status_code == 422
        assert client.get("/brazil/road-history?limit=5&offset=55").json()["count"] == 1
    with TestClient(create_app(road_dir=tmp_path)) as client:
        assert client.get("/brazil/road-history").status_code == 503
