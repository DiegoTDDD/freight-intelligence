"""Reproduce reviewed ANTAQ report indicators; never infer unlabeled chart points or OD pairs."""

import argparse
import csv
import hashlib
import io
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = "https://www.gov.br/antaq/pt-br/central-de-conteudos/publicacoes-da-antaq/Anuario2025.pdf"
SOURCE_HASH = "75a258baeb9267d1cf1c0be8b9353aa31850b950b55197e79b9072e484961e2e"
RELEASE = ("https://www.gov.br/antaq/pt-br/central-de-conteudos/noticias/2026/"
           "setor-aquaviario-brasileiro-movimentou-em-2025-1-4-bi-de-toneladas/")
RELEASE_HASH = "99bd0e6ca46d959066a39f7a7ee0fac96f2122fa8672a339ce738d3ee67a1426"


def prepare(output, source_pdf=None):
    if source_pdf and hashlib.sha256(Path(source_pdf).read_bytes()).hexdigest() != SOURCE_HASH:
        raise ValueError("ANTAQ PDF differs from reviewed edition")
    rows = []

    def add(dataset, category, direction, year, value, unit, page, scope, source=SOURCE):
        rows.append({"dataset": dataset, "category": category, "direction": direction,
                     "year": year, "value": float(value), "unit": unit, "source_page": page,
                     "source_url": source, "scope": scope})

    add("navigation_totals", "Port throughput", "not_applicable", 2025, 1403.1,
        "million_tonnes", 2, "ANTAQ port handling; not unique shipments or modal transport work")
    add("navigation_totals", "Coastal cabotage", "not_applicable", 2025, 303.7,
        "million_tonnes", 0, "ANTAQ reported coastal cabotage handling; source press release",
        RELEASE)
    add("navigation_totals", "Inland navigation", "not_applicable", 2025, 91.3,
        "million_tonnes", 22, "ANTAQ navigation category Interior; not all traffic on inland waterways")
    commodities = {"Soybeans": 31.8, "Maize": 20.2, "Iron ore": 8.8, "Oil products": 7.3,
                   "Fertilizers": 4.9, "Pulp": 3.8, "Box semi-trailers": 2.8,
                   "Wood": 2.1, "Oilseeds": 1.6, "Containers": 1.3}
    for category, value in commodities.items():
        add("inland_commodities", category, "not_applicable", 2025, value, "million_tonnes", 22,
            "Selected leading cargo categories in the ANTAQ inland-navigation chart; not all cargo")
    origins = {"AM": 316.4, "PA": 31.7, "CE": 274.5, "PE": 290.5, "BA": 64.4,
               "ES": 157.3, "RJ": 210.7, "SP": 536.6, "PR": 115.1, "SC": 340.2, "RS": 75.4}
    destinations = {"AM": 223.0, "PA": 29.0, "CE": 256.4, "PE": 234.0, "BA": 156.8,
                    "ES": 113.5, "RJ": 198.3, "SP": 538.9, "PR": 202.8, "SC": 318.3, "RS": 87.4}
    for direction, values in (("origin", origins), ("destination", destinations)):
        for state, value in values.items():
            add("coastal_state_endpoints", state, direction, 2025, value, "thousand_TEU", 20,
                "Labeled states in coastal container chart; marginal endpoints, not paired OD routes; "
                "unlabeled states are unavailable, not zero; TEU must not be converted to tonnes")
    for region, movement, exports in (
        ("Arco Norte", {2024: 94.6, 2025: 106.5}, {2024: 52.4, 2025: 56.5}),
        ("Rest of Brazil", {2024: 84.4, 2025: 95.2}, {2024: 82.8, 2025: 93.0}),
    ):
        for direction, values in (("movements", movement), ("exports", exports)):
            for year, value in values.items():
                add("grain_regions", region, direction, year, value, "million_tonnes", 14,
                    "Maize/soybean geographic port aggregates; movements and exports overlap; "
                    "not individual origin-destination corridors or navigable itineraries")
    rows.sort(key=lambda r: (r["dataset"], r["year"], r["direction"], r["category"]))
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=list(rows[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    raw = buffer.getvalue().encode()
    provenance = {
        "schema_version": 1, "country": "Brazil", "prepared_on": "2026-11-13",
        "method": "Reviewed transcription of labeled official report figures; no chart digitization",
        "sources": [{"url": SOURCE, "sha256": SOURCE_HASH, "pages": [2, 14, 20, 22]},
                    {"url": RELEASE, "sha256": RELEASE_HASH,
                     "description": "HTML bytes archived when reviewed; site navigation can change"}],
        "quality_notes": [
            "Keep tonnes, TEU and statistical populations separate; do not sum overlapping indicators.",
            "Coastal origin/destination states are marginals; no OD links are inferred.",
            "Interior navigation is a navigation category, not all maritime/coastal traffic on rivers.",
            "Unlabeled years/states/categories remain unavailable; chart points are not estimated by eye.",
            "Reported values retain rounding and may be revised; selected categories do not form a census.",
        ],
        "files": [{"path": "water.csv", "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}],
    }
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    (output / "water.csv").write_bytes(raw)
    (output / "provenance.json").write_bytes((json.dumps(provenance, indent=2) + "\n").encode())
    return len(rows)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "deployment/brazil_water")
    parser.add_argument("--source-pdf", type=Path)
    args = parser.parse_args()
    print(f"Prepared {prepare(args.output, args.source_pdf)} scoped ANTAQ records")
