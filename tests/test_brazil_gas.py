import calendar
import csv
import hashlib
import io
import json
import shutil
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from freight_intelligence.api.app import create_app
from freight_intelligence.brazil_gas_results import DEFAULT_ROOT, load_gas
from freight_intelligence.ingestion.brazil_gas import (
    HEADERS,
    annual_volumes,
    parse_month,
    parse_number,
)


def source_rows(month=1):
    days = calendar.monthrange(2025, month)[1]
    header = [*HEADERS, *[f"{day:02}/{month:02}/2025" for day in range(1, days + 1)]]
    base = ["pipeline1", "Pipe", "Point", "point1", "Ponto de Recebimento",
            "City", "SP", "Operator", "123", "Shipper", "456", "contract",
            "Volume Realizado (mil m³)"]
    receipt = [*base, *["1,0"] * days]
    delivery = [*base, *["2,0"] * days]
    delivery[3:5] = ["point2", "Ponto de Entrega"]
    requested = [*receipt]
    requested[12] = "Volume Solicitado (mil m³)"
    return [header, receipt, delivery, requested]


def encoded(rows):
    buffer = io.StringIO(newline="")
    csv.writer(buffer, delimiter=";", lineterminator="\n").writerows(rows)
    return buffer.getvalue().encode("cp1252")


def test_requested_volume_is_excluded_and_point_types_stay_separate():
    data, metadata = parse_month(encoded(source_rows()), 2025, 1)
    assert {r["point_type"]: r["volume_thousand_m3"] for r in data} == {
        "receipt": 31.0, "delivery": 62.0,
    }
    assert metadata["source_rows"] == 3
    assert metadata["realized_volume_rows"] == 2


def test_missing_cell_is_counted_and_not_zero_imputed():
    rows = source_rows()
    rows[1][13] = ""
    data, _ = parse_month(encoded(rows), 2025, 1)
    receipt = next(r for r in data if r["point_type"] == "receipt")
    assert receipt["missing_daily_values"] == 1
    assert receipt["observed_daily_values"] == 30
    assert receipt["volume_thousand_m3"] == 30


def test_signed_roundoff_is_retained_and_counted():
    rows = source_rows()
    rows[1][13] = "-1,5E-14"
    data, metadata = parse_month(encoded(rows), 2025, 1)
    assert metadata["negative_daily_values"] == 1
    assert parse_number("-1,5E-14") == Decimal("-1.5E-14")
    assert data


@pytest.mark.parametrize("value", ["", "NaN", "inf", "1.2.3", "1,2,3", "1E999"])
def test_invalid_numbers_rejected(value):
    with pytest.raises(ValueError):
        parse_number(value)


def test_duplicate_contract_and_wrong_calendar_are_rejected():
    rows = source_rows()
    with pytest.raises(ValueError, match="Duplicate"):
        parse_month(encoded([*rows, rows[1]]), 2025, 1)
    with pytest.raises(ValueError, match="calendar"):
        parse_month(encoded(rows), 2025, 2)


def test_empty_calendar_padding_is_allowed_but_values_in_padding_are_not():
    rows = source_rows(2)
    for row in rows:
        row.extend([""] * 3)
    assert parse_month(encoded(rows), 2025, 2)[1]["daily_values"] == 56
    rows[1][-1] = "1"
    with pytest.raises(ValueError, match="outside calendar"):
        parse_month(encoded(rows), 2025, 2)


def test_full_year_converts_source_units_without_combining_directions():
    monthly = [r for month in range(1, 13)
               for r in parse_month(encoded(source_rows(month)), 2025, month)[0]]
    annual = annual_volumes(monthly)
    assert annual["receipt"] == 0.365
    assert annual["delivery"] == 0.730
    assert annual["missing_daily_values"] == {"receipt": 0, "delivery": 0}
    with pytest.raises(ValueError, match="twelve-month"):
        annual_volumes(monthly[:-2])


def test_real_snapshot_has_five_operators_and_explicit_missing_coverage():
    data, annual, metadata = load_gas()
    assert data.height == 120
    assert data["operator_id"].n_unique() == 5
    assert annual["missing_daily_values"] == {"receipt": 31, "delivery": 2}
    assert annual["negative_daily_values"] == 118
    assert len(metadata["sources"]) == 12
    assert annual["receipt"] == pytest.approx(33538.538272275495)


def test_gas_api_filters_and_missing_bundle(tmp_path):
    with TestClient(create_app()) as client:
        response = client.get("/brazil/gas-movements?month=12&point_type=receipt")
        assert response.status_code == 200
        assert response.json()["count"] == 5
        assert {row["month"] for row in response.json()["data"]} == {12}
        assert client.get("/brazil/gas-movements?month=13").status_code == 422
        assert client.get("/brazil/gas-movements?point_type=both").status_code == 422
    with TestClient(create_app(gas_dir=tmp_path)) as client:
        assert client.get("/brazil/gas-movements").status_code == 503


@pytest.mark.parametrize("defect", ["corrupt_csv", "annual_disagrees", "missing_source"])
def test_gas_snapshot_integrity_and_consistency_fail_closed(tmp_path, defect):
    root = tmp_path / "gas"
    shutil.copytree(DEFAULT_ROOT, root)
    path = root / "provenance.json"
    manifest = json.loads(path.read_bytes())
    if defect == "corrupt_csv":
        (root / "monthly.csv").write_bytes(b"broken")
    elif defect == "annual_disagrees":
        annual = json.loads((root / "annual.json").read_bytes())
        annual["receipt"] += 1
        raw = json.dumps(annual).encode()
        (root / "annual.json").write_bytes(raw)
        next(r for r in manifest["files"] if r["path"] == "annual.json")["sha256"] = (
            hashlib.sha256(raw).hexdigest()
        )
    else:
        manifest["sources"].pop()
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError):
        load_gas(root)
