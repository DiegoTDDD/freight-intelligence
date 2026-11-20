"""Stream and compare the reviewed ANAC CSV; quarantine revisions without promotion."""

import argparse
import csv
import hashlib
import io
import json
import math
import time
import urllib.request
from datetime import UTC, date, datetime
from pathlib import Path

from freight_intelligence.brazil_air import DEFAULT_ROOT, load_air

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ("https://sistemas.anac.gov.br/dadosabertos/Voos%20e%20opera%C3%A7%C3%B5es%20a%C3%A9reas/"
          "Dados%20Estat%C3%ADsticos%20do%20Transporte%20A%C3%A9reo/Dados_Estatisticos.csv")
MAX_BYTES = 450 * 1024**2
CHUNK_BYTES = 1024**2
PREFIX_BYTES = 64 * 1024
DEADLINE_SECONDS = 900


def validate_header(prefix):
    # Decode complete header lines only; a chunk may end inside a UTF-8 character.
    lines = prefix.split(b"\n")
    if len(lines) < 3:
        raise ValueError("Missing complete ANAC source headers")
    updated = lines[0].decode("utf-8-sig").strip()
    marker = "Atualizado em: "
    if not updated.startswith(marker):
        raise ValueError("Invalid ANAC update line")
    date.fromisoformat(updated.removeprefix(marker))
    header = next(csv.reader(io.StringIO(lines[1].decode("utf-8")), delimiter=";"))
    required = {"ANO", "MES", "NATUREZA", "GRUPO_DE_VOO", "CARGA_PAGA_KG", "CARGA_GRATIS_KG", "CORREIO_KG"}
    for side in ("ORIGEM", "DESTINO"):
        required.update(f"AEROPORTO_DE_{side}_{field}" for field in ("SIGLA", "NOME", "PAIS"))
    if len(header) != len(set(header)) or not required.issubset(header):
        raise ValueError("Changed or invalid ANAC source columns")
    return updated


def download_source(path, *, opener=urllib.request.urlopen, clock=time.monotonic,
                    max_bytes=MAX_BYTES, deadline_seconds=DEADLINE_SECONDS):
    if not 0 < max_bytes <= MAX_BYTES or not math.isfinite(deadline_seconds) or not 0 < deadline_seconds <= DEADLINE_SECONDS:
        raise ValueError("Invalid ANAC transfer budget")
    path = Path(path)
    started = clock()
    request = urllib.request.Request(SOURCE, headers={
        "User-Agent": "LogiNexus-source-audit/1.0", "Accept-Encoding": "identity"})
    created = False
    try:
        with opener(request, timeout=30) as response:
            if response.geturl() != SOURCE:
                raise ValueError("Unexpected ANAC source redirect")
            declared = response.headers.get("Content-Length")
            declared = int(declared) if declared is not None else None
            if declared is not None and not 0 < declared <= max_bytes:
                raise ValueError("Invalid or oversized ANAC response length")
            checksum, total, prefix = hashlib.sha256(), 0, bytearray()
            with path.open("xb") as output:
                created = True
                while True:
                    if clock() - started > deadline_seconds:
                        raise TimeoutError("ANAC transfer exceeded its elapsed-time budget")
                    chunk = response.read(min(CHUNK_BYTES, max_bytes + 1 - total))
                    if not isinstance(chunk, bytes):
                        raise TypeError("Invalid ANAC response body")
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > max_bytes:
                        raise ValueError("Oversized ANAC source")
                    checksum.update(chunk)
                    if len(prefix) < PREFIX_BYTES:
                        prefix.extend(chunk[:PREFIX_BYTES - len(prefix)])
                    output.write(chunk)
            if not total or (declared is not None and total != declared):
                raise ValueError("Empty or truncated ANAC source")
            updated = validate_header(bytes(prefix))
            return {"sha256": checksum.hexdigest(), "bytes": total, "source_update_line": updated}
    except Exception:
        if created:
            path.unlink(missing_ok=True)
        raise


def audit(output, *, baseline=DEFAULT_ROOT, opener=urllib.request.urlopen,
          clock=time.monotonic, max_bytes=MAX_BYTES, deadline_seconds=DEADLINE_SECONDS):
    output = Path(output).resolve()
    protected = (ROOT / "deployment").resolve()
    if output == protected or protected in output.parents:
        raise ValueError("Audit output must be outside served snapshots")
    output.mkdir(parents=True, exist_ok=False)
    report = {"checked_at": datetime.now(UTC).isoformat(), "status": "validation_failed",
              "publication": "No served snapshot or deployed service is changed by this audit",
              "automatic_promotion": False, "full_data_rows_validated": False,
              "limits": {"max_bytes": max_bytes, "chunk_bytes": CHUNK_BYTES,
                         "header_prefix_bytes": PREFIX_BYTES, "socket_timeout_seconds": 30,
                         "elapsed_budget_seconds_checked_between_chunks": deadline_seconds}}
    try:
        tables, metadata, _ = load_air(baseline)
        if metadata["source"] != SOURCE:
            raise ValueError("ANAC baseline source differs from fixed official endpoint")
        partial = output / "source.csv.part"
        fetched = download_source(partial, opener=opener, clock=clock, max_bytes=max_bytes,
                                  deadline_seconds=deadline_seconds)
        changed = fetched["sha256"] != metadata["source_sha256"]
        report.update(status="source_changed_requires_review" if changed else "unchanged",
                      source_url=SOURCE, reviewed_sha256=metadata["source_sha256"], fetched=fetched,
                      header_validated=True, reviewed_end_year=metadata["end_year"],
                      reviewed_pair_start_year=metadata["pair_start_year"],
                      reviewed_rows={name: table.height for name, table in tables.items()})
        if changed:
            partial.rename(output / "unreviewed-source.csv")
            report["candidate"] = "unreviewed-source.csv; header checked, row values not approved or promoted"
        else:
            partial.unlink()
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
    args = parser.parse_args()
    result = audit(args.output)
    if result["status"] == "source_changed_requires_review":
        print("::warning::ANAC source changed; review the quarantined CSV before updating public data")
    print(json.dumps({"status": result["status"], "bytes": result["fetched"]["bytes"]}))
