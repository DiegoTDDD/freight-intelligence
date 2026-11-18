"""Discover official annual ANP links; validate historical years before publishing."""

import argparse
import hashlib
import json
import re
import tempfile
import urllib.request
from collections import defaultdict
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urljoin, urlparse

import polars as pl

from freight_intelligence.brazil_gas_results import load_gas
from scripts.prepare_brazil_gas import ROOT, SOURCE, prepare

MONTHS = ("janeiro", "fevereiro", "marco", "abril", "maio", "junho", "julho", "agosto",
          "setembro", "outubro", "novembro", "dezembro")


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.urls = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self.urls.extend(value for name, value in attrs if name == "href" and value)


def discover(html, years):
    parser = Links()
    parser.feed(html)
    result = {}
    for year in years:
        months = {}
        for href in parser.urls:
            url = urljoin(SOURCE, href)
            parsed = urlparse(url)
            if parsed.scheme != "https" or parsed.hostname != "www.gov.br":
                continue
            decoded = unquote(url).lower().replace("ç", "c")
            if f"/{year}/" not in decoded or not decoded.endswith(".csv"):
                continue
            for month, name in enumerate(MONTHS, 1):
                if re.search(rf"(?:_|-){name}(?:_|\.|-)", decoded):
                    if month in months and months[month] != url:
                        raise ValueError("Ambiguous ANP historical month links")
                    months[month] = url
        if set(months) != set(range(1, 13)):
            raise ValueError(f"Missing official twelve-month ANP link set for {year}")
        result[year] = [months[month] for month in range(1, 13)]
    return result


def build(cache, output, years=(2022, 2023, 2024)):
    with urllib.request.urlopen(SOURCE, timeout=30) as response:
        html = response.read(2 * 1024**2).decode("utf-8")
    links = discover(html, years)
    frames, annuals, sources = [], [], []
    with tempfile.TemporaryDirectory(prefix="loginexus-gas-history-") as staging:
        for year in years:
            directory = Path(staging) / str(year)
            prepare(Path(cache) / str(year), directory, year=year, source_urls=links[year],
                    deduplicate_identical=True)
            data, annual, metadata = load_gas(directory, expected_year=year)
            frames.append(data)
            annuals.append(annual)
            for source in metadata["sources"]:
                groups = defaultdict(list)
                for cell in source.pop("missing_cells", []):
                    key = tuple(cell[name] for name in ("operator_id", "point_id", "point_name",
                                                        "point_type", "source_record", "reason"))
                    groups[key].append(cell["date"])
                source["missing_groups"] = [dict(zip(
                    ("operator_id", "point_id", "point_name", "point_type", "source_record", "reason"),
                    key, strict=True), dates=dates) for key, dates in groups.items()]
                sources.append(source)
    monthly = pl.concat(frames).sort("year", "month", "operator_id", "point_type")
    files = {"monthly.csv": monthly.write_csv().encode(),
             "annual.json": (json.dumps(annuals, indent=2) + "\n").encode()}
    metadata = {"schema_version": 1, "source": SOURCE, "years": list(years), "sources": sources,
                "interpretation": "ANP historical realized receipt/delivery-point movements. Observed subtotals; operator coverage can change. Inter-operator transfers repeat gas; not unique national supply or production.",
                "exact_duplicate_policy": "Exclude only identical full volume rows and count exclusions; conflicting duplicate keys fail validation",
                "realized_label_policy": "Volume Realizado (mil m³); 2022 additionally accepts reviewed Realizado (mil m³). Unitless labels are not accepted.",
                "files": [{"path": name, "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}
                          for name, raw in files.items()]}
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    for name, raw in files.items():
        (output / name).write_bytes(raw)
    (output / "provenance.json").write_bytes((json.dumps(metadata, indent=2) + "\n").encode())
    print(json.dumps({"historical_years": list(years), "monthly_rows": monthly.height}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache-dir", type=Path, default=ROOT / "data/raw/anp/gas/history")
    parser.add_argument("--output", type=Path, default=ROOT / "deployment/brazil_gas_history")
    args = parser.parse_args()
    build(args.cache_dir, args.output)
