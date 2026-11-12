"""Evaluate the documented 2017-2021 historical portion of local FAF5.5.1 Gold KPIs."""

import argparse
import hashlib
import io
import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import polars as pl

from freight_intelligence.ml.historical_evaluation import historical_report

YEARS = list(range(2017, 2022))
UNITS = {"tons": "thousand tons", "value": "million 2017 dollars", "tmiles": "million ton-miles"}


def prepare_report(gold_bytes, documentation, prepared_at):
    text = documentation.decode("utf-8-sig")
    if not all(marker in text for marker in (
        "2023-09-29", "FAF5.5", "Annual estimates (Y + 1 through Y + 4)",
        "2017 constant dollars",
    )):
        raise ValueError("Expected archived FAF5.5 documentation dated 2023-09-29")
    data = pl.read_parquet(gold_bytes)
    required = {"metric_type", "year", "total_value"}
    if not required.issubset(data.columns):
        raise ValueError("Gold input requires annual KPI columns")
    history = data.filter(pl.col("year").is_in(YEARS)).select(sorted(required))
    pairs = {(row["metric_type"], row["year"]) for row in history.to_dicts()}
    if pairs != {(metric, year) for metric in UNITS for year in YEARS} or history.height != 15:
        raise ValueError("Expected one historical total for each of three metrics in 2017-2021")
    source = history.sort("metric_type", "year").write_csv().encode("utf-8")
    manifest = {
        "dataset_id": "local-gold-faf5.5.1-historical-2017-2021",
        "source": "Local annual Gold derived from FAF5.5.1 HiLoForecasts; https://doi.org/10.21949/1529116",
        "retrieved_at": prepared_at,
        "scope": "Local Gold aggregate across all included FAF flow records; 2017 benchmark and "
        "2018-2021 annual estimates only. Preparation date is not original download date.",
        "record_kind": "historical_estimates",
        "units": UNITS,
    }
    # Five points: train 2017-2018, validate 2019-2020, reserve 2021.
    report = historical_report(source, json.dumps(manifest).encode(), 2, 1)
    lineage = {
        "gold_sha256": hashlib.sha256(gold_bytes).hexdigest(),
        "documentation_sha256": hashlib.sha256(documentation).hexdigest(),
        "included_years": YEARS,
        "excluded_years": sorted(set(data["year"]) - set(YEARS)),
        "classification_basis": "Archived README: base Y=2017; annual estimates Y+1 through Y+4",
        "validation": "2019 and 2020 expanding origins; only two initial training points",
        "reserved_test": "2021 only; too short to establish robust predictive accuracy",
        "limitations": "Derived from existing local Gold. No raw reaggregation or independent "
        "verification of Gold provenance. Estimates are not direct observations. Does not "
        "benchmark or mix vintages with newer FAF releases. No forecast generated.",
    }
    output = io.BytesIO()
    with ZipFile(io.BytesIO(report)) as original, ZipFile(output, "w", ZIP_DEFLATED) as bundle:
        for name in original.namelist():
            bundle.writestr(name, original.read(name))
        bundle.writestr("lineage.json", json.dumps(lineage, indent=2))
        bundle.writestr("source_readme.txt", documentation)
    return output.getvalue()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gold", required=True, type=Path)
    parser.add_argument("--documentation", required=True, type=Path)
    parser.add_argument("--prepared-at", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        if args.gold.stat().st_size > 2 * 1024 * 1024:
            raise ValueError("Expected a small annual Gold file (at most 2 MiB)")
        if args.documentation.stat().st_size > 65536:
            raise ValueError("Documentation exceeds 64 KiB")
        result = prepare_report(
            args.gold.read_bytes(), args.documentation.read_bytes(), args.prepared_at
        )
        with args.output.open("xb") as destination:
            destination.write(result)
    except (OSError, ValueError, pl.exceptions.PolarsError) as error:
        parser.exit(2, f"FAF historical preparation failed: {error}\n")
    print("Prepared 15 historical estimate rows; 2022 onward excluded; Gold preserved.")


if __name__ == "__main__":
    main()
