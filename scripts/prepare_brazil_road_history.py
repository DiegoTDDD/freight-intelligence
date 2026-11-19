"""Rebuild reviewed ANTT display tables; preserve original yearbook observations."""

import hashlib
import json

import polars as pl

from freight_intelligence.brazil_road import DEFAULT_ROOT, load_road_monthly
from freight_intelligence.brazil_road_history import (
    CATALOGUE,
    EVIDENCE,
    FILES,
    FILTERS,
    SCOPE,
    SOURCE,
    derive_tables,
    parse_capture,
)


def prepare(root=DEFAULT_ROOT):
    files = []
    for name, expected in EVIDENCE.items():
        raw = (root / name).read_bytes()
        if hashlib.sha256(raw).hexdigest() != expected:
            raise ValueError("Changed ANTT display evidence; review before rebuilding")
        files.append({"path": name, "bytes": len(raw), "sha256": expected})
    archived, archived_metadata = load_road_monthly(root)
    tables = derive_tables(parse_capture((root / "history_capture.json").read_bytes()), archived)
    annual_2025 = tables["annual"].filter(pl.col("year") == 2025)
    metadata = {"schema_version": 1, "source": SOURCE, "catalogue": CATALOGUE, "scope": SCOPE,
                "reviewed_on": "2026-11-19", "period_start": "2024-07", "period_end": "2026-10",
                "months_observed": 28, "filters": FILTERS,
                "units": {"tonnes": "published_integer_tonnes", "mdfe_documents": "documents"},
                "method": "Read rendered Show as table rows for Toneladas por mês and Emissão mensal de MDFes; JSON is an archived UI transcription, not an upstream raw download",
                "precision": "Integer values displayed by the official tables; source rounding retained, not unrounded individual measurements",
                "account_mapping": {"N": "non_own_account", "S": "own_account"},
                "coverage": {"2024": {"months": 6, "full_year": False},
                             "2025": {"months": 12, "full_year": True},
                             "2026": {"months": 10, "full_year": False}},
                "displayed_update_stamp": "SUROC última atualização: mar/26",
                "update_stamp_note": "The displayed stamp predates the last table month October 2026; it is not a reliable freshness guarantee. Coverage follows observed table labels and capture date.",
                "quality_notes": ["MDF-e documents are not unique trips or consignments; all documented exemptions apply.",
                                  "October 2025 has a source-documented reporting-layout change; a reported drop does not prove a fall in physical demand.",
                                  "All source geographic values were retained; EX/exterior was not excluded.",
                                  "No 2024/2026 annualization, missing-month imputation, forecasting or source-edition splicing."],
                "yearbook_reference": archived_metadata["monthly_source"],
                "yearbook_2025_tonnes": archived["tonnes"].sum(),
                "panel_2025_totals": annual_2025.to_dicts(),
                "panel_minus_yearbook_2025_tonnes": tables["editions"]["difference_tonnes"].sum(),
                "regional_reference_note": "The independently reported 2025 non-own-account subtotal rounds to the yearbook's 1.165 billion regional reference; this is numerical agreement across editions, not proof of identical scope.",
                "files": files}
    outputs = {}
    for view, name in FILES.items():
        raw = tables[view].write_csv().encode()
        outputs[name] = raw
        files.append({"path": name, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()})
    for name, raw in outputs.items():
        (root / name).write_bytes(raw)
    (root / "history_provenance.json").write_bytes((json.dumps(metadata, indent=2) + "\n").encode())
    return tables


if __name__ == "__main__":
    print(f"Prepared {prepare()['monthly'].height} reviewed monthly account-category records")
