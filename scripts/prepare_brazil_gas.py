"""Download and validate the twelve official ANP gas-point files for 2025."""

import argparse
import csv
import hashlib
import io
import json
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

from freight_intelligence.ingestion.brazil_gas import MAX_BYTES, annual_volumes, parse_month

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ("https://www.gov.br/anp/pt-br/centrais-de-conteudo/dados-abertos/"
          "dados-consolidados-movimentacao-de-gas-natural-em-gasodutos-de-transporte")
BASE = ("https://www.gov.br/anp/pt-br/centrais-de-conteudo/dados-abertos/arquivos/"
        "arquivos-movimentacao-de-gas-natural-em-gasodutos-de-transporte/2025/")
# Exact links published on the source page; January/February use different names.
FILES = ["gn-janeiro.csv", "gn-fevereiro.csv", "gn_marco_2025.csv", "gn_abril_2025.csv",
         "gn_maio_2025.csv", "gn_junho_2025.csv", "gn_julho_2025.csv", "gn_agosto_2025.csv",
         "gn_setembro_2025.csv", "gn_outubro_2025.csv", "gn_novembro_2025.csv",
         "gn_dezembro_2025.csv"]


def fetch_report(url):
    request = urllib.request.Request(url, headers={
        "User-Agent": "LogiNexus/0.1 (https://github.com/DiegoTDDD/freight-intelligence)"
    })
    with urllib.request.urlopen(request, timeout=30) as response:
        if response.geturl() != url:
            raise ValueError("Unexpected ANP source redirect")
        return response.read(MAX_BYTES + 1)


def prepare(cache, output, *, refresh=False, fetch=None):
    cache, output = Path(cache), Path(output)
    cache.mkdir(parents=True, exist_ok=True)
    monthly, sources = [], []
    for month, filename in enumerate(FILES, 1):
        path = cache / filename
        if path.exists() and not refresh:
            raw = path.read_bytes()
        else:
            raw = (fetch or fetch_report)(BASE + filename)
        rows, provenance = parse_month(raw, 2025, month)
        # Cache only complete, validated monthly downloads.
        if not path.exists() or refresh:
            staging = path.with_suffix(".part")
            staging.write_bytes(raw)
            staging.replace(path)
        monthly.extend(rows)
        sources.append({**provenance, "url": BASE + filename})
        print(f"Validated ANP gas month {month:02}: {provenance['realized_volume_rows']} volume rows")
    annual = annual_volumes(monthly)
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=list(monthly[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(monthly)
    files = {"monthly.csv": buffer.getvalue().encode(),
             "annual.json": (json.dumps(annual, indent=2) + "\n").encode()}
    manifest = {
        "schema_version": 1, "source": SOURCE, "prepared_on": datetime.now(UTC).date().isoformat(),
        "year": 2025, "unit": "source thousand m3; annual outputs million m3",
        "interpretation": (
            "Realized point movements reported by operators, separated into receipts and "
            "deliveries. Inter-operator transfers can repeat the same gas. Neither series is "
            "unique national supply, gas production or a quantity to add to the other. "
            "Missing daily cells are counted and excluded, never filled with zero; affected "
            "aggregates are observed subtotals. Signed source values, including tiny negatives, "
            "are retained and counted without clipping."
        ),
        "operators": sorted({row["operator"] for row in monthly}),
        "sources": sources,
        "files": [{"path": name, "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}
                  for name, raw in files.items()],
    }
    output.mkdir(parents=True, exist_ok=True)
    for name, raw in files.items():
        (output / name).write_bytes(raw)
    (output / "provenance.json").write_bytes((json.dumps(manifest, indent=2) + "\n").encode())
    return annual


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache-dir", type=Path, default=ROOT / "data/raw/anp/gas/2025")
    parser.add_argument("--output", type=Path, default=ROOT / "deployment/brazil_gas")
    parser.add_argument("--refresh", action="store_true", help="Re-fetch even when raw cache exists")
    args = parser.parse_args()
    print(json.dumps(prepare(args.cache_dir, args.output, refresh=args.refresh)))
