"""Detect revisions of the reviewed ANTT PDF without changing served snapshots."""

import argparse
import hashlib
import json
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

from freight_intelligence.brazil_road import DEFAULT_ROOT, load_road_monthly

ROOT = Path(__file__).resolve().parents[1]
MAX_BYTES = 8 * 1024 * 1024


def fetch_source(url):
    request = urllib.request.Request(url, headers={"User-Agent": "LogiNexus-source-audit/1.0"})
    with urllib.request.urlopen(request, timeout=30) as response:
        final = urlparse(response.geturl())
        if final.scheme != "https" or final.hostname != "www.gov.br":
            raise ValueError("Unexpected ANTT source destination")
        return response.read(MAX_BYTES + 1)


def audit(output, *, fetch=fetch_source, baseline=DEFAULT_ROOT):
    output = Path(output).resolve()
    protected = ROOT / "deployment"
    if output == protected or protected in output.parents:
        raise ValueError("Audit output must be outside served snapshots")
    output.mkdir(parents=True, exist_ok=False)
    report = {"checked_at": datetime.now(UTC).isoformat(), "status": "validation_failed",
              "publication": "This audit never changes served snapshots or deploys a service"}
    try:
        monthly, metadata = load_road_monthly(baseline)
        source = metadata["monthly_source"]
        raw = fetch(source["url"])
        if not isinstance(raw, bytes) or not raw.startswith(b"%PDF-") or len(raw) > MAX_BYTES:
            raise ValueError("Invalid or oversized ANTT PDF response")
        checksum = hashlib.sha256(raw).hexdigest()
        changed = checksum != source["sha256"]
        report.update(status="source_changed_requires_review" if changed else "unchanged",
                      source_url=source["url"], reviewed_sha256=source["sha256"],
                      fetched_sha256=checksum, monthly_rows=monthly.height,
                      reviewed_annual_tonnes=int(monthly["tonnes"].sum()))
        if changed:
            (output / "unreviewed-source.pdf").write_bytes(raw)
            report["candidate"] = "unreviewed-source.pdf; no new values have been extracted or approved"
    except Exception as error:
        report["failure_type"] = type(error).__name__
        raise
    finally:
        (output / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.output)
    if result["status"] == "source_changed_requires_review":
        print("::warning::ANTT source PDF changed; review before updating published figures")
    print(json.dumps({"status": result["status"], "reviewed_annual_tonnes": result["reviewed_annual_tonnes"]}))
