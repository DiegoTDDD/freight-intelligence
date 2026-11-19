"""Fetch source revisions into an isolated candidate; never publish or replace baseline data."""

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse
from zipfile import ZIP_DEFLATED, ZipFile

import polars as pl

from freight_intelligence.brazil_gas_history import DEFAULT_ROOT as HISTORY_ROOT
from freight_intelligence.brazil_gas_history import load_gas_history
from freight_intelligence.brazil_gas_results import load_gas
from freight_intelligence.brazil_modes import load_modes
from freight_intelligence.ingestion.brazil_gas import (
    LEGACY_UNITS_FILE,
    LEGACY_UNITS_SHA256,
    LEGACY_UNITS_URL,
)
from scripts.prepare_brazil_gas import fetch_report
from scripts.prepare_brazil_gas import prepare as prepare_gas
from scripts.prepare_brazil_modes import prepare as prepare_modes

ROOT = Path(__file__).resolve().parents[1]


def source_changes(before, after):
    old = {row["url"]: row["sha256"] for row in before["sources"]}
    new = {row["url"]: row["sha256"] for row in after["sources"]}
    if len(old) != 12 or set(old) != set(new):
        raise ValueError("ANP source population changed; a new ingestion contract is required")
    return [{"url": url, "before_sha256": old[url], "after_sha256": new[url]}
            for url in sorted(old) if old[url] != new[url]]


def snapshot_summary(monthly, annual):
    return {"monthly_rows": monthly.height, "operators": monthly["operator_id"].n_unique(),
            "receipt_observed_million_m3": annual["receipt"],
            "delivery_observed_million_m3": annual["delivery"],
            "missing_daily_values": annual["missing_daily_values"],
            "negative_daily_values": annual["negative_daily_values"]}


def historical_baseline(root, year):
    data, annuals, metadata = load_gas_history(root)
    sources = sorted((row for row in metadata["sources"] if row["year"] == year), key=lambda row: row["month"])
    if len(sources) != 12 or len({row["url"] for row in sources}) != 12:
        raise ValueError("Historical ANP audit requires twelve distinct reviewed sources")
    for source in sources:
        parsed = urlparse(source["url"])
        prefix = "/anp/pt-br/centrais-de-conteudo/dados-abertos/arquivos/arquivos-movimentacao-de-gas-natural-em-gasodutos-de-transporte/"
        if (parsed.scheme != "https" or parsed.netloc != "www.gov.br" or parsed.query or parsed.fragment
                or not parsed.path.startswith(prefix + str(year) + "/") or not parsed.path.endswith(".csv")):
            raise ValueError("Historical ANP source is outside the reviewed official year")
    return (data.filter(pl.col("year") == year), next(row for row in annuals if row["year"] == year),
            {"sources": sources})


def audit(output, cache, *, fetch=None, baseline=ROOT / "deployment/brazil_gas",
          year=2025, history_baseline=HISTORY_ROOT):
    if year not in (2021, 2022, 2023, 2024, 2025):
        raise ValueError("Only reviewed ANP years 2021–2025 can be audited")
    output = Path(output).resolve()
    baseline = Path(baseline).resolve()
    # Never allow the audit output/cache to overwrite committed serving snapshots.
    protected = ROOT / "deployment"
    cache = Path(cache).resolve()
    if any(path == protected or protected in path.parents for path in (output, cache)):
        raise ValueError("Audit output and raw cache must be outside deployment snapshots")
    output.mkdir(parents=True, exist_ok=False)
    report = {"checked_at": datetime.now(UTC).isoformat(), "status": "validation_failed",
              "year": year,
              "publication": "No tracked snapshot or deployed service is changed by this audit"}
    try:
        if year == 2025:
            old_data, old_annual, old_metadata = load_gas(baseline)
        else:
            old_data, old_annual, old_metadata = historical_baseline(history_baseline, year)
        candidate = output / "candidate/deployment"
        # Historical per-year bundles are review inputs, not drop-in replacements
        # for the combined multi-year serving snapshot.
        gas = candidate / ("brazil_gas" if year == 2025 else f"historical-year-review/{year}")
        if year == 2021:
            unit_raw = (fetch or fetch_report)(LEGACY_UNITS_URL)
            if len(unit_raw) > 2 * 1024**2 or hashlib.sha256(unit_raw).hexdigest() != LEGACY_UNITS_SHA256:
                raise ValueError("Historical ANP unit dictionary changed; review required")
            gas.mkdir(parents=True)
            (gas / LEGACY_UNITS_FILE).write_bytes(unit_raw)
            report["unit_contract"] = {"url": LEGACY_UNITS_URL, "sha256": LEGACY_UNITS_SHA256}
        prepare_gas(cache, gas, refresh=True, fetch=fetch, year=year,
                    source_urls=None if year == 2025 else [row["url"] for row in old_metadata["sources"]],
                    deduplicate_identical=year < 2025,
                    legacy_unit_contract=LEGACY_UNITS_SHA256 if year == 2021 else None)
        data, annual, metadata = load_gas(gas, expected_year=year)
        changes = source_changes(old_metadata, metadata)
        if year == 2025:
            modes = candidate / "brazil_modes"
            prepare_modes(modes, gas_dir=gas)
            modal_data, _ = load_modes(modes)
            report["annual_modal_rows"] = modal_data.height
        else:
            report["integration"] = "Review per-year bundle and rebuild combined historical snapshot; current 2025 modal indicators are unchanged"
        report.update(status="candidate_requires_review" if changes else "unchanged",
                      source_revisions=changes, before=snapshot_summary(old_data, old_annual),
                      after=snapshot_summary(data, annual))
        if changes:
            archive = output / "review-candidate.zip"
            staging = output / "review-candidate.zip.part"
            with ZipFile(staging, "x", ZIP_DEFLATED) as bundle:
                for path in sorted(candidate.rglob("*")):
                    if path.is_file():
                        bundle.write(path, path.relative_to(candidate.parent).as_posix())
                bundle.writestr("audit-report.json", json.dumps(report, indent=2))
            with ZipFile(staging) as bundle:
                if bundle.testzip() is not None:
                    raise ValueError("Candidate archive integrity failure")
            staging.replace(archive)
            report["candidate_sha256"] = hashlib.sha256(archive.read_bytes()).hexdigest()
    except Exception as error:
        report["status"] = "validation_failed"
        report["failure_type"] = type(error).__name__
        raise
    finally:
        (output / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cache-dir", type=Path, required=True)
    parser.add_argument("--year", type=int, choices=range(2021, 2026), default=2025)
    args = parser.parse_args()
    result = audit(args.output, args.cache_dir, year=args.year)
    print(json.dumps({"status": result["status"], "changed_sources": len(result["source_revisions"])}))
