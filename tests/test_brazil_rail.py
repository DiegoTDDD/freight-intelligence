import polars as pl
import pytest

from freight_intelligence.ingestion.brazil_rail import (
    COLUMNS,
    aggregate_movements,
    parse_movements,
    parse_number,
)
from freight_intelligence.ml.temporal_evaluation import evaluate_temporally


def source(year=2024):
    lines = [";".join(COLUMNS)]
    lines += [
        f"{month:02}/{year};EFC;Minério;Carajás;PA;Itaqui;MA;1.234,5;2.345.678"
        for month in range(1, 13)
    ]
    return ("\n".join(lines)).encode("cp1252")


def test_brazilian_numbers_encoding_coverage_and_aggregation():
    frame = parse_movements(source(), 2024)
    assert frame["commodity"][0] == "Minério"
    assert frame["tons"].sum() == 12 * 1234.5
    tables, observations = aggregate_movements(frame)
    assert tables["monthly"].height == 12
    assert tables["corridors"].height == 1
    assert (
        observations.filter(pl.col("metric_type") == "tonne_km")["total_value"][0] == 12 * 2345678
    )
    with pytest.raises(ValueError, match="twelve"):
        parse_movements(source().rsplit(b"\n", 1)[0], 2024)
    with pytest.raises(ValueError, match="Year mismatch"):
        parse_movements(source(), 2023)


@pytest.mark.parametrize("value", ["-1", "NaN", "1.25", "1,2,3", "", "1e6"])
def test_rejects_ambiguous_or_invalid_numbers(value):
    with pytest.raises(ValueError):
        parse_number(value)


def test_temporal_evaluation_preserves_tonne_km_unit_identifier():
    data = pl.DataFrame(
        {
            "metric_type": ["tonne_km"] * 12,
            "year": list(range(2010, 2022)),
            "total_value": [float(value) for value in range(100, 112)],
        }
    )
    predictions, _, choices = evaluate_temporally(data)
    assert choices["tonne_km"] == "linear"
    assert predictions["metric_type"].unique().to_list() == ["tonne_km"]
