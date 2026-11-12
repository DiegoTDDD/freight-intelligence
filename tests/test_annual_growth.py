import polars as pl
import pytest

from freight_intelligence.analytics import annual_cagr, annual_growth


def run(module, tmp_path, monkeypatch, years, values):
    source = tmp_path / "annual.parquet"
    output = tmp_path / "result.parquet"
    pl.DataFrame({"metric_type": ["tons"] * len(years), "year": years, "total_value": values}).write_parquet(source)
    monkeypatch.setattr(module, "INPUT_PATH", str(source))
    monkeypatch.setattr(module, "OUTPUT_PATH", str(output))
    module.main()
    return pl.read_parquet(output)


def test_interval_growth_is_distinct_from_annualized_rate(tmp_path, monkeypatch):
    result = run(annual_growth, tmp_path, monkeypatch, [2020, 2025], [100.0, 200.0])
    assert result["elapsed_years"].to_list() == [None, 5]
    assert result["growth_rate"][1] == 1.0
    assert result["annualized_growth_rate"][1] == pytest.approx(2 ** 0.2 - 1)


def test_zero_denominator_is_unavailable_not_infinite(tmp_path, monkeypatch):
    result = run(annual_growth, tmp_path, monkeypatch, [2020, 2021, 2022], [0.0, 10.0, 0.0])
    assert result["growth_rate"].to_list() == [None, None, -1.0]
    assert result["annualized_growth_rate"].to_list() == [None, None, -1.0]


@pytest.mark.parametrize("years,values", [([2020], [10.0]), ([2020, 2025], [0.0, 10.0])])
def test_cagr_undefined_endpoints_are_null(tmp_path, monkeypatch, years, values):
    result = run(annual_cagr, tmp_path, monkeypatch, years, values)
    assert result["cagr"].item() is None


@pytest.mark.parametrize("module", [annual_growth, annual_cagr])
def test_duplicate_years_fail_before_writing(tmp_path, monkeypatch, module):
    with pytest.raises(ValueError, match="Duplicate"):
        run(module, tmp_path, monkeypatch, [2020, 2020], [10.0, 20.0])
    assert not (tmp_path / "result.parquet").exists()
