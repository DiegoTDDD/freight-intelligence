"""Rebuild the small ANAC evaluation in a new staging directory, without raw ingestion."""

import argparse
import hashlib
import json
import shutil
from pathlib import Path

from freight_intelligence.brazil_air import DEFAULT_ROOT, load_air
from scripts.prepare_brazil_air import build_forecast


def prepare(output, source=DEFAULT_ROOT):
    output, source = Path(output).resolve(), Path(source).resolve()
    if output == source or source in output.parents:
        raise ValueError("Forecast staging must be outside the reviewed source bundle")
    tables, metadata, previous = load_air(source)
    report = build_forecast(tables["annual"], previous["metadata"]["provenance"]["retrieved_at"])
    shutil.copytree(source, output)  # Exclusive staging preserves the reviewed bundle.
    (output / "forecast.zip").write_bytes(report)
    record = next(item for item in metadata["files"] if item["path"] == "forecast.zip")
    record.update(bytes=len(report), sha256=hashlib.sha256(report).hexdigest())
    (output / "provenance.json").write_bytes((json.dumps(metadata, indent=2) + "\n").encode())
    load_air(output)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    prepare(args.output)
    print("Six separate ANAC targets evaluated in staging; serving data preserved.")
