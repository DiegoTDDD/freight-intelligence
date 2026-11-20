"""Check the pinned operator PDF without promoting new tariffs or legal rules."""

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from urllib.request import Request, build_opener

from freight_intelligence.optimization.geographic_routing import NoRedirect
from freight_intelligence.optimization.trip_planning import DEFAULT_ROOT, load_rules

SOURCE = "https://rodovias.motiva.com.br/content/dam/projetos/rodovias/canal-site-rodovias-grupoccr/pt/transparencia/autoban/pdf/transp_regulatoria_autoban_2026.pdf"
MAX_BYTES = 1024 * 1024


def audit(output, root=DEFAULT_ROOT, opener=None):
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        raise FileExistsError("Preserve existing tariff audit reports")
    report = {"checked_at": datetime.now(UTC).isoformat(), "status": "validation_failed",
              "automatic_promotion": False, "scope": "Operator tariff PDF bytes only; legal changes require separate review"}
    try:
        rules = load_rules(root)
        source = next(s for s in rules["sources"] if s["id"] == "tariffs")
        if source["url"] != SOURCE:
            raise ValueError("Unexpected tariff source")
        opener = opener or build_opener(NoRedirect()).open
        with opener(Request(SOURCE, headers={"User-Agent": "LogiNexusTariffAudit/1.0"}), timeout=30) as response:
            if response.geturl() != SOURCE:
                raise ValueError("Tariff source redirects are not accepted")
            raw = response.read(MAX_BYTES + 1)
            declared = response.headers.get("Content-Length")
            if (not raw.startswith(b"%PDF-") or not raw.rstrip().endswith(b"%%EOF") or len(raw) > MAX_BYTES
                    or declared is not None and int(declared) != len(raw)):
                raise ValueError("Empty, invalid, truncated or oversized tariff PDF")
        fetched = hashlib.sha256(raw).hexdigest()
        report.update(status="unchanged" if fetched == source["sha256"] else "source_changed_requires_review",
                      source_url=SOURCE, reviewed_sha256=source["sha256"], fetched_sha256=fetched, bytes=len(raw))
    except Exception as error:
        report["failure_type"] = type(error).__name__
        raise
    finally:
        output.write_bytes((json.dumps(report, indent=2) + "\n").encode())
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.output)
    if result["status"] == "source_changed_requires_review":
        print("::warning::Operator tariff PDF changed; review before updating prices")
    print(json.dumps(result))
