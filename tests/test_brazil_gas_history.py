from decimal import Decimal

from fastapi.testclient import TestClient

from freight_intelligence.api.app import create_app
from freight_intelligence.brazil_gas_history import load_gas_history, missing_groups
from freight_intelligence.brazil_gas_results import load_gas
from freight_intelligence.ingestion.brazil_gas import parse_number


def test_reviewed_history_has_complete_months_and_disclosed_exclusions():
    data, annuals, metadata = load_gas_history()
    assert data.height == 360 and set(data["year"]) == {2022, 2023, 2024}
    assert set(data["month"]) == set(range(1, 13))
    assert data.filter((data["month"] == 2) & (data["year"] == 2024))["calendar_days"].unique().to_list() == [29]
    assert {a["year"]: a["missing_daily_values"] for a in annuals} == {
        2022: {"receipt": 947, "delivery": 15109},
        2023: {"receipt": 1994, "delivery": 25812},
        2024: {"receipt": 7734, "delivery": 79484},
    }
    assert sum(source["exact_duplicate_rows_excluded"] for source in metadata["sources"]) == 35
    assert sum(source["missing_shipper_id_rows"] for source in metadata["sources"]) == 34
    assert parse_number("- 445,07 ") == Decimal("-445.07")


def test_2025_missing_cells_are_traced_without_imputation():
    _, annual, metadata = load_gas()
    receipts = missing_groups(metadata, "receipt")
    deliveries = missing_groups(metadata, "delivery")
    assert len(receipts) == 1 and receipts[0]["point_name"] == "GARUVA"
    assert receipts[0]["missing_days"] == 31 and receipts[0]["dates"][0] == "2025-01-01"
    assert {tuple(group["dates"]) for group in deliveries} == {("2025-05-31",)}
    assert len(deliveries) == 2 and annual["missing_daily_values"]["delivery"] == 2


def test_year_filter_and_paginated_diagnostics(tmp_path):
    with TestClient(create_app()) as client:
        response = client.get("/brazil/gas-movements?year=2024&month=2&point_type=receipt").json()
        assert response["year"] == 2024 and response["count"] == 5
        assert not response["diagnostics_included"]
        assert all(row["year"] == 2024 for row in response["data"])
        response = client.get("/brazil/gas-movements?include_diagnostics=true&point_type=receipt").json()
        assert response["diagnostics_total"] == 1 and response["diagnostics"][0]["missing_days"] == 31
        response = client.get("/brazil/gas-movements?year=2024&include_diagnostics=true&diagnostics_limit=1").json()
        assert response["diagnostics_total"] > 1 and len(response["diagnostics"]) == 1
        for year in (2022, 2023):
            response = client.get(f"/brazil/gas-movements?year={year}&include_diagnostics=true").json()
            assert response["count"] == 120
            assert all(row["year"] == year for row in response["data"])
            assert all(date.startswith(str(year)) for group in response["diagnostics"] for date in group["dates"])
            assert all(source["year"] == year for source in response["sources"])
        assert client.get("/brazil/gas-movements?year=2021").status_code == 422
    with TestClient(create_app(gas_history_dir=tmp_path)) as client:
        assert client.get("/brazil/gas-movements?year=2024").status_code == 503
