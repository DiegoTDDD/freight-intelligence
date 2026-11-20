import hashlib
import json
import math
import re
import shutil

import polars as pl
import pytest
from fastapi.testclient import TestClient

from freight_intelligence.api.app import create_app
from freight_intelligence.brazil_inland import (
    COMPONENTS,
    DEFAULT_ROOT,
    FILES,
    annual_totals,
    load_inland,
    validate_details,
)
from scripts.prepare_brazil_inland import numeric, parse_history, prepare


def test_original_inland_exports_rebuild_and_reconcile_three_independent_views(tmp_path):
    root = tmp_path / "water"
    shutil.copytree(DEFAULT_ROOT, root)
    before = {name: (root / name).read_bytes() for name in FILES.values()}
    prepare(root)
    assert {name: (root / name).read_bytes() for name in before} == before
    tables, metadata = load_inland(root)
    assert {view: table.height for view, table in tables.items()} == {
        "monthly": 62, "annual": 6, "navigation": 3, "commodities": 117}
    assert tables["annual"]["full_year"].to_list() == [True] * 5 + [False]
    for row in tables["annual"].to_dicts():
        assert abs(row["total_tonnes"] - math.fsum(row[name] for name in COMPONENTS)) < 0.0001
        assert abs(row["export_minus_display_tonnes"]) <= 0.5
        text = (root / f"inland_history_{row['year']}-overview.txt").read_text(encoding="utf-8")
        assert f"No campo Carga.NRAno, {row['year']} está selecionado." in text
        assert "No campo Carga Mês," not in text
        match = re.search(rf"container KPI Transporte Vias Interiores - {row['year']}\(Jan - (?:Dez|Fev)\) ([\d.]+)", text)
        assert int(match[1].replace(".", "")) == row["displayed_total_tonnes"]
    cargo = tables["commodities"]
    assert cargo["tonnes"].null_count() == 8
    assert cargo.filter(pl.col("tonnes") == 0).height == 46
    assert cargo.filter(pl.col("quantity_status") == "source_dash")["tonnes"].null_count() == 8
    assert math.isclose(cargo["tonnes"].sum(), 144893597.202, rel_tol=0, abs_tol=0.0001)
    assert metadata["partial_years"] == {"2026": [1, 2]}


@pytest.mark.parametrize("defect", ["calendar", "component", "total", "dash", "zero", "share"])
def test_changed_calendar_components_missing_policy_or_denominator_are_rejected(defect):
    tables, metadata = load_inland()
    tables = dict(tables)
    if defect == "calendar":
        tables["monthly"] = tables["monthly"].with_columns(pl.lit("2025-01").alias("period"))
    elif defect in {"component", "total"}:
        field = "total_tonnes" if defect == "total" else COMPONENTS[0]
        tables["monthly"] = tables["monthly"].with_columns((pl.col(field) + 1).alias(field))
    elif defect == "dash":
        tables["commodities"] = tables["commodities"].with_columns(pl.col("tonnes").fill_null(0))
    elif defect == "zero":
        tables["commodities"] = tables["commodities"].with_columns(
            pl.when(pl.col("tonnes") == 0).then(None).otherwise(pl.col("tonnes")).alias("tonnes"))
    else:
        tables["commodities"] = tables["commodities"].with_columns(pl.lit(0.5).alias("share"))
    with pytest.raises(ValueError):
        annual_totals(tables["monthly"], metadata)
        validate_details(tables)


@pytest.mark.parametrize("name", ["inland_monthly.csv", "inland_history_2025.xlsx", "inland_2025-overview.txt", "inland_provenance.json"])
def test_source_and_provenance_changes_fail_closed_after_cache_warmup(tmp_path, name):
    root = tmp_path / "water"
    shutil.copytree(DEFAULT_ROOT, root)
    load_inland(root)
    path = root / name
    path.write_bytes(path.read_bytes() + b"changed")
    if name != "inland_provenance.json":
        metadata = json.loads((root / "inland_provenance.json").read_bytes())
        next(row for row in metadata["files"] if row["path"] == name)["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        (root / "inland_provenance.json").write_text(json.dumps(metadata))
    with pytest.raises(ValueError):
        load_inland(root)


def test_parser_rejects_wrong_calendar_and_fake_numeric_values():
    with pytest.raises(ValueError):
        parse_history(DEFAULT_ROOT / "inland_history_2026.xlsx", 2025)
    for value in ("-", None, True, float("inf"), float("nan"), -1):
        with pytest.raises(ValueError):
            numeric(value)
    assert numeric(0) == 0


def test_api_preserves_partial_calendar_nulls_zeros_and_full_source_shares(tmp_path):
    with TestClient(create_app()) as client:
        assert client.get("/brazil/inland-transport").json()["total"] == 62
        result = client.get("/brazil/inland-transport?year=2026").json()
        assert result["count"] == 2 and [row["month"] for row in result["data"]] == [1, 2]
        assert client.get("/brazil/inland-transport?view=annual&year=2026").json()["data"][0]["full_year"] is False
        result = client.get("/brazil/inland-transport?view=commodities&limit=500").json()
        rows = result["data"]
        assert len(rows) == 117 and sum(row["tonnes"] is None for row in rows) == 8
        assert sum(row["tonnes"] == 0 for row in rows) == 46
        selected = client.get("/brazil/inland-transport", params={"view": "commodities", "commodity": "Soja"}).json()
        assert selected["count"] == 1 and selected["data"][0]["share"] == next(row["share"] for row in rows if row["commodity"] == "Soja")
        assert client.get("/brazil/inland-transport?view=commodities&offset=100").json()["count"] == 17
        assert client.get("/brazil/inland-transport?year=2026&month=3").json()["count"] == 0
        for query in ("year=2020", "view=annual&month=1", "commodity=Soja", "view=commodities&year=2024", "limit=501"):
            assert client.get("/brazil/inland-transport?" + query).status_code == 422
    with TestClient(create_app(water_dir=tmp_path)) as client:
        assert client.get("/brazil/inland-transport").status_code == 503
