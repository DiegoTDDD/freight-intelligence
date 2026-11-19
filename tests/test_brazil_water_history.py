import hashlib
import json
import math
import re
import shutil

import polars as pl
import pytest
from fastapi.testclient import TestClient

from freight_intelligence.api.app import create_app
from freight_intelligence.brazil_water import load_water
from freight_intelligence.brazil_water_history import (
    DEFAULT_ROOT,
    annual_totals,
    load_water_history,
)
from scripts.prepare_brazil_water_history import parse_workbook, prepare


def test_original_numeric_history_rebuilds_and_reconciles_independent_headlines(tmp_path):
    root = tmp_path / "water"
    shutil.copytree(DEFAULT_ROOT, root)
    before = {name: (root / name).read_bytes() for name in ("history_monthly.csv", "history_annual.csv")}
    prepare(root)
    assert {name: (root / name).read_bytes() for name in before} == before
    tables, metadata = load_water_history(root)
    monthly, annual = tables["monthly"], tables["annual"]
    assert monthly.height == 62 and monthly["period"].n_unique() == 62
    assert annual["months_observed"].to_list() == [12, 12, 12, 12, 12, 2]
    assert annual["full_year"].to_list() == [True] * 5 + [False]
    for row in annual.to_dicts():
        assert abs(row["export_minus_display_tonnes"]) <= 0.5
        text = (root / f"history_{row['year']}-overview.txt").read_text(encoding="utf-8")
        assert f"No campo Carga.NRAno, {row['year']} está selecionado." in text
        headline = re.search(rf"container KPI Movimentação Portuária - {row['year']}\(Jan - (?:Dez|Fev)\) ([\d.]+)", text)
        assert int(headline[1].replace(".", "")) == row["displayed_total_tonnes"]
    exported = monthly.filter(pl.col("year") == 2025)["tonnes"].to_list()
    archived, _ = load_water()
    archived = archived.filter(pl.col("dataset") == "port_monthly").sort("category")
    assert list(map(round, exported)) == archived["value"].to_list()
    assert sum(map(round, exported)) == 1402731832
    assert round(math.fsum(exported)) == 1402731833
    assert metadata["partial_years"] == {"2026": [1, 2]}


@pytest.mark.parametrize("defect", ["month", "period", "year", "negative", "nan", "total"])
def test_changed_calendar_or_nonreconciling_values_are_rejected(defect):
    tables, metadata = load_water_history()
    data = tables["monthly"]
    if defect == "month":
        data = data.with_columns(pl.when(pl.col("period") == "2026-02").then(3).otherwise(pl.col("month")).alias("month"))
    elif defect == "period":
        data = data.with_columns(pl.lit("2025-01").alias("period"))
    elif defect == "year":
        data = data.with_columns(pl.lit(2020).alias("year"))
    else:
        value = {"negative": -1.0, "nan": float("nan"), "total": 1.0}[defect]
        data = data.with_columns(pl.when(pl.col("period") == "2026-02").then(value).otherwise(pl.col("tonnes")).alias("tonnes"))
    with pytest.raises(ValueError):
        annual_totals(data, metadata)


@pytest.mark.parametrize("filename", ["history_2024.xlsx", "history_2026-context.jpg", "history_monthly.csv", "history_provenance.json"])
def test_modified_export_or_context_invalidates_cache_and_contract(tmp_path, filename):
    root = tmp_path / "water"
    shutil.copytree(DEFAULT_ROOT, root)
    load_water_history(root)
    target = root / filename
    target.write_bytes(target.read_bytes() + b"changed")
    if filename != "history_provenance.json":
        metadata = json.loads((root / "history_provenance.json").read_bytes())
        row = next(item for item in metadata["files"] if item["path"] == filename)
        row["sha256"] = hashlib.sha256(target.read_bytes()).hexdigest()
        (root / "history_provenance.json").write_text(json.dumps(metadata))
    with pytest.raises(ValueError):
        load_water_history(root)


def test_export_parser_rejects_wrong_period():
    with pytest.raises(ValueError):
        parse_workbook(DEFAULT_ROOT / "history_2025.xlsx", 2024)
    with pytest.raises(ValueError):
        parse_workbook(DEFAULT_ROOT / "history_2026.xlsx", 2025)


def test_history_api_preserves_partial_calendar_and_validates_filters(tmp_path):
    with TestClient(create_app()) as client:
        assert client.get("/brazil/water-history").json()["total"] == 62
        result = client.get("/brazil/water-history?year=2026").json()
        assert result["count"] == 2 and [row["month"] for row in result["data"]] == [1, 2]
        result = client.get("/brazil/water-history?view=annual&year=2026").json()
        assert result["data"][0]["full_year"] is False
        assert client.get("/brazil/water-history?year=2026&month=3").json()["count"] == 0
        assert client.get("/brazil/water-history?offset=61&limit=2").json()["count"] == 1
        for query in ("year=2020", "year=2027", "view=annual&month=1", "month=13", "limit=501"):
            assert client.get("/brazil/water-history?" + query).status_code == 422
    with TestClient(create_app(water_dir=tmp_path)) as client:
        assert client.get("/brazil/water-history").status_code == 503
