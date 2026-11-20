import csv
import hashlib
import json
import shutil
from io import BytesIO
from zipfile import ZipFile

import polars as pl
import pytest
from fastapi.testclient import TestClient

from freight_intelligence.api.app import create_app
from freight_intelligence.brazil_air import DEFAULT_ROOT, load_air
from scripts.prepare_brazil_air import aggregate, prepare
from scripts.prepare_brazil_air_forecasts import prepare as prepare_forecasts


@pytest.fixture
def air_source(tmp_path):
    path = tmp_path / "anac.csv"
    fields = ["ANO", "MES", "NATUREZA", "GRUPO_DE_VOO", "CARGA_PAGA_KG", "CARGA_GRATIS_KG", "CORREIO_KG"]
    for side in ("ORIGEM", "DESTINO"):
        fields.extend(f"AEROPORTO_DE_{side}_{name}" for name in ("SIGLA", "NOME", "PAIS"))
    rows = []
    for year in range(2010, 2026):
        for month in range(1, 13):
            for nature in ("DOMÉSTICA", "INTERNACIONAL"):
                rows.append([year, month, nature, "REGULAR", 10, 2, 1,
                             "SBGR", "Guarulhos", "BRASIL", "SBEG", "Manaus", "BRASIL"])
    # A missing paid field is an observed subtotal, not a zero measurement.
    rows[0][4] = ""
    rows.extend([[2026, 1, "DOMÉSTICA", "REGULAR", 99, 0, 0, "SBGR", "Guarulhos", "BRASIL", "SBEG", "Manaus", "BRASIL"],
                 [2025, 1, "INTERNACIONAL", "REGULAR", 99, 0, 0, "KMIA", "Miami", "USA", "KJFK", "New York", "USA"]])
    with path.open("w", encoding="utf-8", newline="") as stream:
        stream.write("Atualizado em: 2026-11-13\n")
        writer = csv.writer(stream, delimiter=";")
        writer.writerow(fields)
        writer.writerows(rows)
    return path


def test_source_aggregation_keeps_units_missingness_and_population(air_source, tmp_path):
    monthly, pairs, annual, _, details = aggregate(air_source)
    assert monthly.height == 16 * 12 * 2 and pairs.height == 2 * 12 * 2
    assert annual["paid_cargo_kg"].sum() == 3830
    assert annual["free_cargo_kg"].sum() == 768
    assert annual["mail_kg"].sum() == 384
    assert annual["missing_paid_cargo_kg"].sum() == 1
    assert details["counts"]["excluded_future_or_partial_year_rows"] == 1
    assert details["counts"]["excluded_no_brazil_endpoint_rows"] == 1
    root = tmp_path / "snapshot"
    prepare(air_source, root)
    tables, _, report = load_air(root)
    assert tables["annual"].equals(annual)
    assert report["metadata"]["selection_uses"] == "validation_only"
    tests = report["predictions"].filter(pl.col("phase") == "test")
    assert set(tests["year"]) == {2023, 2024, 2025}
    assert set(report["forecast"]["year"]) == {2026, 2027, 2028}


def test_reviewed_air_snapshot_and_source_contract():
    tables, metadata, report = load_air()
    assert tables["monthly"].height == 624 and tables["pairs"].height == 36860
    assert metadata["source_sha256"] == "d8b5e856ce56a355727132e8e0868766c8f16d539d817cb240f20390c7bf7730"
    review = json.loads((DEFAULT_ROOT.parents[1] / "docs/evidence/anac_source_review_20261120.json").read_bytes())
    comparison = review["body_comparison"]
    assert comparison["body_bytes_unchanged"]
    assert comparison["reviewed_local_source"]["body_sha256"] == comparison["new_unreviewed_source"]["body_sha256"]
    assert comparison["new_unreviewed_source"]["full_sha256"] == metadata["source_sha256"]
    assert metadata["source_update_line"] == ["Atualizado em: 2026-11-20"]
    annual = tables["annual"].filter((pl.col("year") == 2025) & (pl.col("nature") == "domestic"))
    assert annual["paid_cargo_kg"].item() == 431833387
    assert report["metadata"]["test_points"] == 3


def test_air_reader_rejects_changed_annual_monthly_reconciliation(tmp_path):
    root = tmp_path / "air"
    shutil.copytree(DEFAULT_ROOT, root)
    path = root / "monthly.parquet"
    data = pl.read_parquet(path).with_columns((pl.col("paid_cargo_kg") + 1).alias("paid_cargo_kg"))
    data.write_parquet(path)
    manifest = root / "provenance.json"
    metadata = json.loads(manifest.read_bytes())
    metadata["files"][0]["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    manifest.write_text(json.dumps(metadata))
    with pytest.raises(ValueError, match="annual and monthly"):
        load_air(root)


def test_air_api_filters_pagination_and_unavailable(tmp_path):
    with TestClient(create_app()) as client:
        result = client.get("/brazil/air-freight?view=pairs&year=2025&origin=SBGR&limit=2").json()
        assert result["count"] == 2 and result["total"] > 2
        assert all(row["origin"] == "SBGR" and row["year"] == 2025 for row in result["data"])
        assert client.get("/brazil/air-freight?view=pairs&year=2010").json()["count"] == 0
        assert client.get("/brazil/air-freight?view=annual&month=1").status_code == 422
        assert client.get("/brazil/air-freight?view=monthly&origin=SBGR").status_code == 422
        assert client.get("/brazil/air-freight?limit=1001").status_code == 422
        forecast = client.get("/brazil/air-freight?view=forecast&nature=domestic").json()
        assert forecast["count"] == 3
    with TestClient(create_app(air_dir=tmp_path)) as client:
        assert client.get("/brazil/air-freight").status_code == 503


@pytest.mark.parametrize("measure,tag", [("free_cargo_kg", "free"), ("mail_kg", "mail")])
def test_additional_air_targets_preserve_split_units_and_api_filters(measure, tag):
    tables, _, report = load_air()
    with TestClient(create_app()) as client:
        for nature in ("domestic", "international"):
            query = f"nature={nature}&measure={measure}"
            forecast = client.get(f"/brazil/air-freight?view=forecast&{query}").json()
            assert forecast["count"] == 3
            assert {r["metric_type"] for r in forecast["data"]} == {f"{nature}_{tag}_observed_subtotal"}
            assert {r["unit"] for r in forecast["data"]} == {"kg"}
            assert {r["year"] for r in forecast["data"]} == {2026, 2027, 2028}
            predictions = client.get(f"/brazil/air-freight?view=predictions&phase=test&{query}").json()["data"]
            assert len(predictions) == 9 and {r["origin_year"] for r in predictions} == {2022}
            annual = tables["annual"].filter(pl.col("nature") == nature)
            actual = dict(zip(annual["year"], annual[measure], strict=True))
            assert all(r["actual"] == actual[r["year"]] for r in predictions)
            scores = client.get(f"/brazil/air-freight?view=scores&phase=test&{query}").json()["data"]
            assert {r["model"] for r in scores} == {"persistence", "linear", "cagr"}
            assert sum(r["selected"] for r in scores) == 1
        assert client.get(f"/brazil/air-freight?view=annual&measure={measure}").status_code == 422
        assert client.get("/brazil/air-freight?view=forecast&phase=test").status_code == 422
        assert client.get("/brazil/air-freight?view=forecast&measure=unknown").status_code == 422
    assert len(report["metadata"]["selected_models"]) == 6


@pytest.mark.parametrize("defect", ["unit", "test_origin", "actual", "selected", "missing_target"])
def test_air_reader_rejects_invalid_new_target_report_even_with_updated_archive_hash(tmp_path, defect):
    root = tmp_path / "air"
    shutil.copytree(DEFAULT_ROOT, root)
    path = root / "forecast.zip"
    with ZipFile(path) as archive:
        files = {name: archive.read(name) for name in archive.namelist()}
    name = "forecast" if defect in {"unit", "missing_target"} else "predictions"
    data = pl.read_csv(files[name + ".csv"])
    target = pl.col("metric_type") == "domestic_mail_observed_subtotal"
    if defect == "unit":
        data = data.with_columns(pl.when(target).then(pl.lit("tonnes")).otherwise(pl.col("unit")).alias("unit"))
    elif defect == "missing_target":
        data = data.filter(~target)
    else:
        field, value = {"test_origin": ("origin_year", 2024), "actual": ("actual", -1),
                        "selected": ("selected", False)}[defect]
        data = data.with_columns(pl.when(target).then(pl.lit(value)).otherwise(pl.col(field)).alias(field))
    files[name + ".csv"] = data.write_csv().encode()
    output = BytesIO()
    with ZipFile(output, "w") as archive:
        for member, raw in files.items():
            archive.writestr(member, raw)
    path.write_bytes(output.getvalue())
    manifest = json.loads((root / "provenance.json").read_bytes())
    record = next(r for r in manifest["files"] if r["path"] == "forecast.zip")
    record.update(sha256=hashlib.sha256(path.read_bytes()).hexdigest(), bytes=path.stat().st_size)
    (root / "provenance.json").write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="ANAC"):
        load_air(root)


def test_forecast_only_rebuild_keeps_source_and_prior_results(tmp_path):
    before = {p.name: p.read_bytes() for p in DEFAULT_ROOT.iterdir() if p.is_file()}
    staged = tmp_path / "review"
    prepare_forecasts(staged)
    _, _, previous = load_air()
    _, _, rebuilt = load_air(staged)
    assert rebuilt["metadata"]["provenance"] == previous["metadata"]["provenance"]
    for name in ("scores", "predictions", "forecast"):
        assert rebuilt[name].equals(previous[name])
    assert before == {p.name: p.read_bytes() for p in DEFAULT_ROOT.iterdir() if p.is_file()}
    with pytest.raises(FileExistsError):
        prepare_forecasts(staged)
    for destination in (DEFAULT_ROOT, DEFAULT_ROOT / "nested"):
        with pytest.raises(ValueError, match="outside"):
            prepare_forecasts(destination)
