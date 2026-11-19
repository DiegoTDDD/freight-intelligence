"""Review-pinned ANTT monthly table observations; never splice source editions."""

import hashlib
import json
import re
from functools import lru_cache
from pathlib import Path

import polars as pl

from freight_intelligence.brazil_road import DEFAULT_ROOT, load_road_monthly

CATALOGUE = "https://www.gov.br/antt/pt-br/assuntos/cargas/dadostrc/movimentacao-de-cargas"
SOURCE = ("https://app.powerbi.com/view?r=eyJrIjoiYWNhMTRjYmQtZjczYy00OGJkLThiZWQtOTAwYjEwMmNjOWY4"
          "IiwidCI6Ijg3YmJlOWRlLWE4OTItNGNkZS1hNDY2LTg4Zjk4MmZiYzQ5MCJ9")
EVIDENCE = {
    "history_capture.json": "88f0a49db4a5fd739df09327cfa41660c927be7d4d622c357fcb2e9d8d0287fd",
    "history_overview.txt": "7f63e2e6c7f110f99f8e071c95d5ac76f163ec67a0401ac6259cce677fdcc258",
    "history_context.jpg": "b453b1432a241fbdb7584c4c572667f7951f1bfb7375147b540e76c19c03c5eb",
    "history_tonnes_first.jpg": "eb5b76925f7a5b89e54934a9ac195b2c22e4c14a2d4fbd9bfe36e108c3f7fb76",
    "history_tonnes_last.jpg": "65a620176a503430c35b5834a29e4ead0a3205df77421141a8e3d77199b7f2d1",
    "history_mdfe_first.jpg": "062d304f664d26def84a50570812daf43bb56d235d91653e16c90fc61a8b6b9e",
    "history_mdfe_last.jpg": "22fce1f77e332353a38ecb571fc20387e2762e4eb17f7ab952e8b34d0bba93dd",
}
FILES = {"monthly": "monthly_history.csv", "annual": "annual_history.csv", "editions": "yearbook_comparison.csv"}
FILTERS = {"date": "all source months", "own_account": "both N and S", "vehicle": "unfiltered",
           "cargo": "unfiltered", "geography": "unfiltered; source EX category not excluded",
           "subcontracting": "unfiltered"}
MONTHS = ("jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez")
SCOPE = ("Reported monthly MDF-e road movements, July 2024 to October 2026, split by the "
         "source's own-account flag N/S. All geographic source categories, including EX when "
         "reported. 2024 and 2026 are partial years. Tonnes are published integer table values; "
         "MDF-e documents are not unique trips or consignments. No missing month is filled with zero.")


def source_integer(value):
    if not isinstance(value, str) or not re.fullmatch(r"(?:[0-9]+|[0-9]{1,3}(?:\.[0-9]{3})+)", value):
        raise ValueError("Invalid integer in reviewed ANTT table")
    return int(value.replace(".", ""))


def parse_capture(raw):
    capture = json.loads(raw)
    periods = [(year, month) for year in (2024, 2025, 2026) for month in range(1, 13)
               if (2024, 7) <= (year, month) <= (2026, 10)]
    labels = {f"{MONTHS[month - 1]} {year % 100}" for year, month in periods}
    if set(capture) != {"tonnes", "mdfe"} or any(set(table) != labels for table in capture.values()):
        raise ValueError("Incomplete or changed ANTT monthly source calendar")
    rows = []
    for year, month in periods:
        label = f"{MONTHS[month - 1]} {year % 100}"
        if any(len(capture[metric][label]) != 2 for metric in ("tonnes", "mdfe")):
            raise ValueError("ANTT N/S categories differ from reviewed source")
        for index, account in enumerate(("non_own_account", "own_account")):
            rows.append({"year": year, "month": month, "period": f"{year}-{month:02d}",
                         "account_type": account, "tonnes": source_integer(capture["tonnes"][label][index]),
                         "mdfe_documents": source_integer(capture["mdfe"][label][index])})
    return pl.DataFrame(rows).sort("year", "month", "account_type")


def derive_tables(monthly, archived):
    annual = []
    for year in (2024, 2025, 2026):
        for account in ("non_own_account", "own_account", "all"):
            rows = monthly.filter(pl.col("year") == year)
            if account != "all":
                rows = rows.filter(pl.col("account_type") == account)
            months = rows["month"].n_unique()
            annual.append({"year": year, "account_type": account, "months_observed": months,
                           "full_year": months == 12, "tonnes": rows["tonnes"].sum(),
                           "mdfe_documents": rows["mdfe_documents"].sum()})
    totals = monthly.filter(pl.col("year") == 2025).group_by("year", "month").agg(
        pl.col("tonnes").sum().alias("panel_tonnes"))
    comparison = totals.join(archived.select("year", "month", pl.col("tonnes").alias("yearbook_tonnes")),
                             on=["year", "month"], how="inner").with_columns(
        (pl.col("panel_tonnes") - pl.col("yearbook_tonnes")).alias("difference_tonnes"))
    if comparison.height != 12:
        raise ValueError("Archived yearbook calendar cannot be reconciled")
    return {"monthly": monthly, "annual": pl.DataFrame(annual), "editions": comparison.sort("month")}


def load_road_history(root=DEFAULT_ROOT):
    root = Path(root).resolve()
    names = [*EVIDENCE, *FILES.values(), "history_provenance.json", "monthly.csv", "provenance.json"]
    signature = tuple((name, (root / name).stat().st_mtime_ns, (root / name).stat().st_size) for name in names)
    return _load_history(root, signature)


@lru_cache(maxsize=1)
def _load_history(root, signature):
    raw = (root / "history_provenance.json").read_bytes()
    if len(raw) > 65536:
        raise ValueError("Oversized ANTT road history manifest")
    metadata = json.loads(raw)
    expected_names = set(EVIDENCE) | set(FILES.values())
    if (metadata.get("schema_version") != 1 or metadata.get("scope") != SCOPE
            or metadata.get("source") != SOURCE or metadata.get("filters") != FILTERS
            or metadata.get("period_start") != "2024-07" or metadata.get("period_end") != "2026-10"
            or metadata.get("units") != {"tonnes": "published_integer_tonnes", "mdfe_documents": "documents"}
            or len(metadata["files"]) != len(expected_names)
            or {record["path"] for record in metadata["files"]} != expected_names):
        raise ValueError("Invalid ANTT road history manifest, units or period")
    for record in metadata["files"]:
        content = (root / record["path"]).read_bytes()
        digest = hashlib.sha256(content).hexdigest()
        if (len(content) > 1024**2 or digest != record["sha256"]
                or (record["path"] in EVIDENCE and digest != EVIDENCE[record["path"]])):
            raise ValueError("ANTT road history evidence integrity mismatch")
    archived, archived_metadata = load_road_monthly(root)
    expected = derive_tables(parse_capture((root / "history_capture.json").read_bytes()), archived)
    tables = {view: pl.read_csv(root / name) for view, name in FILES.items()}
    for view, data in tables.items():
        if not data.equals(expected[view]):
            raise ValueError("ANTT road history values differ from reviewed source tables")
    coverage = {str(year): {"months": rows["month"].n_unique(), "full_year": rows["month"].n_unique() == 12}
                for year in (2024, 2025, 2026)
                for rows in [tables["monthly"].filter(pl.col("year") == year)]}
    if (metadata.get("coverage") != coverage or metadata.get("months_observed") != 28
            or metadata.get("yearbook_reference") != archived_metadata["monthly_source"]
            or metadata.get("displayed_update_stamp") != "SUROC última atualização: mar/26"
            or metadata.get("account_mapping") != {"N": "non_own_account", "S": "own_account"}
            or metadata.get("panel_2025_totals") != tables["annual"].filter(pl.col("year") == 2025).to_dicts()
            or metadata.get("yearbook_2025_tonnes") != archived["tonnes"].sum()
            or metadata.get("panel_minus_yearbook_2025_tonnes") != tables["editions"]["difference_tonnes"].sum()):
        raise ValueError("ANTT road history coverage or edition comparison disagrees")
    return tables, metadata
