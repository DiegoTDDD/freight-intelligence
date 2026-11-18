from decimal import Decimal

from fastapi.testclient import TestClient

from freight_intelligence.api.app import create_app
from freight_intelligence.brazil_gas_history import load_gas_history, missing_groups
from freight_intelligence.brazil_gas_results import load_gas
from freight_intelligence.ingestion.brazil_gas import parse_number


def test_reviewed_history_has_complete_months_and_disclosed_exclusions():
    data, annuals, metadata = load_gas_history()
    assert data.height == 120 and set(data["year"]) == {2024}
    assert set(data["month"]) == set(range(1, 13))
    assert data.filter(data["month"] == 2)["calendar_days"].unique().to_list() == [29]
    assert annuals[0]["missing_daily_values"] == {"receipt": 7734, "delivery": 79484}
    assert sum(source["exact_duplicate_rows_excluded"] for source in metadata["sources"]) == 30
    assert sum(source["missing_shipper_id_rows"] for source in metadata["sources"]) == 10
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
        assert client.get("/brazil/gas-movements?year=2023").status_code == 422
    with TestClient(create_app(gas_history_dir=tmp_path)) as client:
        assert client.get("/brazil/gas-movements?year=2024").status_code == 503
