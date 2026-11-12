"""Download bounded official ANTT archives and prepare a reproducible railway snapshot."""

import argparse
import hashlib
import json
import re
import urllib.request
from datetime import date
from pathlib import Path

import polars as pl

from freight_intelligence.ingestion.brazil_rail import (
    CATALOG_URL,
    aggregate_movements,
    parse_movements,
)
from freight_intelligence.ml.historical_evaluation import historical_report


def download(url, limit=10 * 1024 * 1024):
    if not url.startswith("https://dados.antt.gov.br/"):
        raise ValueError("Only official ANTT HTTPS resources are accepted")
    request = urllib.request.Request(
        url, headers={"User-Agent": "LogiNexus/0.1 public-data research"}
    )
    with urllib.request.urlopen(request, timeout=45) as response:
        if not response.url.startswith("https://dados.antt.gov.br/"):
            raise ValueError("Unexpected resource redirect")
        data = response.read(limit + 1)
    if len(data) > limit:
        raise ValueError("Official resource exceeds download bound")
    return data


def prepare(output, raw, start=2006, end=2025):
    if output.exists():
        raise ValueError("Output already exists; choose another directory")
    if not 2006 <= start <= end < date.today().year or end - start > 30:
        raise ValueError("Use bounded completed calendar years starting in 2006")
    catalog_bytes = download(CATALOG_URL)
    catalog = json.loads(catalog_bytes)["result"]
    resources = {}
    for resource in catalog["resources"]:
        match = re.search(r"/producao_origem_destino_(\d{4})\.csv$", resource["url"])
        if match:
            resources[int(match[1])] = resource
    raw.mkdir(parents=True, exist_ok=True)
    frames, records = [], []
    for year in range(start, end + 1):
        resource = resources[year]
        path = raw / f"producao_origem_destino_{year}.csv"
        payload = download(resource["url"])
        # Preserve earlier local source bytes, even if the publisher revises a release.
        digest = hashlib.sha256(payload).hexdigest()
        if path.exists() and hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError(f"Local source differs for {year}; choose a fresh raw directory")
        if not path.exists():
            with path.open("xb") as destination:
                destination.write(payload)
        frame = parse_movements(payload, year)
        frames.append(frame)
        records.append(
            {
                "year": year,
                "url": resource["url"],
                "sha256": digest,
                "bytes": len(payload),
                "rows": frame.height,
                "months": 12,
            }
        )
        print(f"ANTT {year}: {frame.height} reported flows", flush=True)
    tables, observations = aggregate_movements(pl.concat(frames))
    manifest = {
        "dataset_id": f"antt-siade-rail-{start}-{end}",
        "source": CATALOG_URL,
        "retrieved_at": date.today().isoformat(),
        "scope": "Reported cargo movements on federally conceded Brazilian railways; not all modes. "
        "TU sums movements and may count cargo again on successive reporting flows. "
        "Administrative reports may be revised; coverage can change between years.",
        "record_kind": "historical_observations",
        "units": {"tons": "toneladas úteis (TU)", "tonne_km": "toneladas-quilômetro úteis (TKU)"},
    }
    source = observations.write_csv().encode()
    manifest_bytes = json.dumps(manifest, ensure_ascii=False, indent=2).encode()
    report = historical_report(
        source, manifest_bytes, min_train_points=8, test_points=3, forecast_years=3
    )
    output.mkdir(parents=True)
    for name, table in tables.items():
        table.write_parquet(output / f"{name}.parquet")
    (output / "observations.csv").write_bytes(source)
    (output / "source_manifest.json").write_bytes(manifest_bytes)
    (output / "historical_evaluation.zip").write_bytes(report)
    provenance = {
        "catalog_url": CATALOG_URL,
        "catalog_sha256": hashlib.sha256(catalog_bytes).hexdigest(),
        "retrieved_at": date.today().isoformat(),
        "license": catalog.get("license_title"),
        "excluded_partial_years": f"{end + 1} onward",
        "resources": records,
        "interpretation": manifest["scope"],
        "files": [
            {
                "path": path.name,
                "bytes": path.stat().st_size,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
            for path in sorted(output.iterdir())
            if path.is_file()
        ],
    }
    (output / "provenance.json").write_text(
        json.dumps(provenance, indent=2, ensure_ascii=False), encoding="utf-8", newline="\n"
    )
    return provenance


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--raw", required=True, type=Path)
    args = parser.parse_args()
    prepare(args.output, args.raw)


if __name__ == "__main__":
    main()
