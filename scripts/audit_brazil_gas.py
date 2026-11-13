"""Fetch source revisions into an isolated candidate; never publish or replace baseline data."""

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from freight_intelligence.brazil_gas_results import load_gas
from freight_intelligence.brazil_modes import load_modes
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


def audit(output, cache, *, fetch=None, baseline=ROOT / "deployment/brazil_gas"):
    output = Path(output).resolve()
    baseline = Path(baseline).resolve()
    # Never allow the audit output/cache to overwrite committed serving snapshots.
    protected = ROOT / "deployment"
    cache = Path(cache).resolve()
    if any(path == protected or protected in path.parents for path in (output, cache)):
        raise ValueError("Audit output and raw cache must be outside deployment snapshots")
    output.mkdir(parents=True, exist_ok=False)
    report = {"checked_at": datetime.now(UTC).isoformat(), "status": "validation_failed",
              "publication": "No tracked snapshot or deployed service is changed by this audit"}
    try:
        old_data, old_annual, old_metadata = load_gas(baseline)
        candidate = output / "candidate/deployment"
        gas = candidate / "brazil_gas"
        prepare_gas(cache, gas, refresh=True, fetch=fetch)
        data, annual, metadata = load_gas(gas)
        changes = source_changes(old_metadata, metadata)
        modes = candidate / "brazil_modes"
        prepare_modes(modes, gas_dir=gas)
        modal_data, _ = load_modes(modes)
        report.update(status="candidate_requires_review" if changes else "unchanged",
                      source_revisions=changes, before=snapshot_summary(old_data, old_annual),
                      after=snapshot_summary(data, annual), annual_modal_rows=modal_data.height)
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
    args = parser.parse_args()
    result = audit(args.output, args.cache_dir)
    print(json.dumps({"status": result["status"], "changed_sources": len(result["source_revisions"])}))
